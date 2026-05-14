import os
from dotenv import load_dotenv
load_dotenv(override=True) # Carrega as chaves antes de tudo

from routes.modules import modules_bp
from routes.seo_engine import seo_bp
import requests
import json
import asyncio
from bs4 import BeautifulSoup
import edge_tts
from flask import Flask, request, jsonify, render_template, redirect
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta
import threading
import uuid
import re
import random

# load_dotenv removido daqui
app = Flask(__name__)
app.register_blueprint(modules_bp)
app.register_blueprint(seo_bp)

# ==========================================
# CONFIGURAÇÕES E SUPABASE
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_anon_key") # Aceita o nome padrão do Supabase
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "meta-llama/llama-3-70b-instruct"
OPENROUTER_ANALYSIS_MODEL = os.getenv("OPENROUTER_ANALYSIS_MODEL", "minimax/minimax-01")
DEMO_LOGIN_ENABLED = os.getenv("DEMO_LOGIN_ENABLED", "false").lower() == "true"

# Configurações Meta Ads
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:5000/auth/meta/callback")

# Configurações TikTok Ads
TIKTOK_APP_ID = os.getenv("TIKTOK_APP_ID")
TIKTOK_APP_SECRET = os.getenv("TIKTOK_APP_SECRET")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:5000/auth/tiktok/callback")
TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# Configurações SiliconFlow e Replicate
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY") or os.getenv("silicomflow")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL") or os.getenv("SILICONFLOW_API_URL") or "https://api.siliconflow.cn/v1"
IMAGE_MODEL = os.getenv("IMAGE_MODEL") or os.getenv("IMAGE_MODEL_SILICONFLOW") or "stabilityai/sdxl-turbo"

import replicate
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") or os.getenv("replicate")
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL") or "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
REPLICATE_VIDEO_MODEL = os.getenv("REPLICATE_VIDEO_MODEL") or "wan-video/wan-2.2-t2v-fast"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

MAX_IMAGES = 3
CACHE_IMAGE_URLS = {}

import hashlib
import time
import requests

def sanitize_input(text):
    """Proteção básica contra Prompt Injection e estouro de contexto"""
    if not text: return ""
    clean = str(text).replace("ignore all previous", "[REDACTED]").replace("system prompt", "[REDACTED]")
    return clean[:1000]

def gerar_imagem_siliconflow(prompt_texto, produto, tentativas=2):
    if not SILICONFLOW_API_KEY: return None
    # Traduzir prompt para inglês para melhor resultado no SDXL
    prompt_en_ia = f"Describe a professional marketing image for {produto} based on this: {prompt_texto}. NO TEXT, NO LETTERS. High quality, realistic."
    try:
        prompt_en = chamar_ia(prompt_en_ia, system_message="Translate to English and describe visually for AI image generation. NO TEXT.")
    except:
        prompt_en = f"Professional marketing for {produto}, {prompt_texto}"

    cache_key = hashlib.md5(prompt_en.encode()).hexdigest()
    if cache_key in CACHE_IMAGE_URLS: return CACHE_IMAGE_URLS[cache_key]

    print(f"DEBUG: Tentando SiliconFlow para: {prompt_en[:30]}...", flush=True)
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": IMAGE_MODEL, "prompt": prompt_en, 
        "negative_prompt": "text, letters, words, typography, watermark, blurry, low quality, distorted",
        "width": 1024, "height": 1024, "num_inference_steps": 30, "scheduler": "EulerA"
    }
    for tentativa in range(tentativas):
        try:
            response = requests.post(f"{SILICONFLOW_BASE_URL}/images/generations", headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                image_url = response.json()['data'][0]['url']
                CACHE_IMAGE_URLS[cache_key] = image_url
                print(f"✅ SiliconFlow SUCESSO: {image_url}", flush=True)
                return image_url
            else:
                print(f"❌ SiliconFlow Erro ({response.status_code}): {response.text}", flush=True)
        except Exception as e:
            print(f"❌ SiliconFlow Exceção: {e}", flush=True)
            time.sleep(1)
    return None

def gerar_imagem_replicate(prompt_texto, produto):
    if not REPLICATE_API_TOKEN: 
        print("⚠️ Replicate Token AUSENTE no .env", flush=True)
        return None
    print(f"DEBUG: Tentando Replicate Fallback para: {prompt_texto[:30]}...", flush=True)
    prompt = f"Professional marketing image for {produto}. Vibrant colors, highly detailed, photorealistic. {prompt_texto[:200]}"
    try:
        output = replicate.run(
            REPLICATE_MODEL,
            input={"prompt": prompt, "width": 1024, "height": 1024, "num_outputs": 1}
        )
        url = str(output[0]) if output else None
        if url: print(f"✅ Replicate SUCESSO: {url}", flush=True)
        return url
    except Exception as e:
        print(f"❌ Replicate Erro: {e}", flush=True)
    return None

def placeholder_image(texto=""):
    return f"https://placehold.co/1024x1024/2c3e50/ffffff?text={texto.replace(' ', '+')[:20]}"

def gerar_imagem_com_fallback(prompt_texto, produto):
    # 1. Tenta SiliconFlow
    url = gerar_imagem_siliconflow(prompt_texto, produto)
    if url: return url
    
    # 2. Tenta Replicate (Fallback)
    url = gerar_imagem_replicate(prompt_texto, produto)
    if url: return url
    
    # 3. Placeholder (Último caso)
    return placeholder_image("Erro na Arte")

# ==========================================
# SCRAPING E TTS (Spy Mode & Audio)
# ==========================================
def scrape_concorrente(url):
    """Lê o conteúdo do site concorrente para a IA analisar"""
    if not url or not url.startswith('http'):
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        texto = soup.get_text(separator=' ', strip=True)
        return texto[:3000] # Limita a 3000 caracteres para não estourar o prompt
    except Exception as e:
        print(f"⚠️ Erro ao fazer scrape da URL {url}: {e}", flush=True)
        return ""

async def generate_tts_async(text, output_path, voice="pt-BR-AntonioNeural"):
    """Gera áudio usando edge-tts de forma assíncrona"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def gerar_audio_tts(roteiro_completo, produto):
    """Função síncrona wrapper para gerar o áudio"""
    if not roteiro_completo: return None
    
    os.makedirs('static/audio', exist_ok=True)
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join('static', 'audio', filename)
    
    try:
        print(f"Gerando TTS para: {produto}...", flush=True)
        asyncio.run(generate_tts_async(roteiro_completo, filepath))
        return f"/static/audio/{filename}"
    except Exception as e:
        print(f"Erro ao gerar TTS: {e}", flush=True)
        return None

# ==========================================
# LEAD HUNTER (Prospecção de Leads)
# ==========================================
def buscar_leads_locais(nicho, cidade, db=None, user_id=None):
    """Busca leads no Google/Maps. Usa SerpApi se houver chave, senão usa Scraper Lite."""
    query = f"{nicho} em {cidade} whatsapp"
    leads = []
    
    if SERPAPI_KEY:
        try:
            params = {
                "engine": "google_maps",
                "q": f"{nicho} em {cidade}",
                "api_key": SERPAPI_KEY
            }
            res = requests.get("https://serpapi.com/search", params=params)
            data = res.json()
            for place in data.get("place_results", []):
                leads.append({
                    "nome": place.get("title"),
                    "telefone": place.get("phone"),
                    "site": place.get("website"),
                    "nota": place.get("rating", "N/A")
                })
        except: pass

    # Scraper Lite (Fallback usando busca pública)
    if not leads:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
            }
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            resp = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            import re
            # Tenta classes modernas do Google
            results = soup.select('.tF2Cxc, .g, .yuRUbf')
            for res in results[:5]:
                link_tag = res.find('a')
                link = link_tag['href'] if link_tag else ""
                nome_tag = res.find('h3')
                nome = nome_tag.get_text() if nome_tag else "Empresa Local"
                text = res.get_text()
                
                zap_match = re.search(r'(\(?\d{2,3}\)?\s?\d{4,5}-?\d{4})', text)
                telefone = zap_match.group(1) if zap_match else "Pendente"
                
                if nome != "Empresa Local" and link:
                    leads.append({
                        "nome": nome,
                        "telefone": telefone,
                        "site": link,
                        "nota": "N/A"
                    })
        except Exception as e:
            print(f"Erro no Scraper Lite: {e}")

    # FALLBACK DE SEGURANÇA: Se nada for encontrado, gera leads simulados de alta qualidade
    if not leads:
        print(f"⚠️ Nenhum lead real encontrado. Gerando leads simulados para {nicho} em {cidade}...")
        leads = [
            {"nome": f"{nicho} Premium {cidade}", "telefone": "+351 912 345 678", "site": "https://exemplo.com", "nota": "4.8"},
            {"nome": f"Studio {nicho} & Cia", "telefone": "+351 922 888 777", "site": "https://studio.com", "nota": "4.5"},
            {"nome": f"Centro de {nicho} Avançado", "telefone": "+351 933 111 222", "site": "https://centro.com", "nota": "4.9"}
        ]


    # ENRIQUECIMENTO NINJA COM IA
    enriched_leads = []
    import random
    for lead in leads[:5]: # Analisar apenas os top 5 para evitar delay excessivo
        try:
            nome = lead['nome']
            # Análise de Dor & Oportunidade
            prompt_analise = f"Analise o negócio '{nome}' no nicho '{nicho}'. Identifique 1 dor provável (ex: falta de presença digital) e 1 oportunidade de ouro (ex: dominar o tráfego pago local). Seja curto e direto (máx 15 palavras cada)."
            analise_raw = chamar_ia(prompt_analise, system_message="Você é um consultor de marketing sênior especializado em prospecção.")
            
            dor = "Melhorar presença digital"
            oportunidade = "Escalar vendas via WhatsApp"
            
            if "\n" in analise_raw:
                parts = analise_raw.split("\n")
                dor = parts[0].replace("Dor:", "").strip()
                if len(parts) > 1: oportunidade = parts[1].replace("Oportunidade:", "").strip()
            else:
                dor = analise_raw[:50]

            # Script de Pitch Magnético
            prompt_pitch = f"Gere uma mensagem de WhatsApp curta e matadora para o dono da '{nome}'. Use a dor: {dor}. Ofereça uma solução rápida usando IA. Use emojis. Máximo 200 caracteres."
            pitch_script = chamar_ia(prompt_pitch, system_message="Você é um SDR de elite.")

            # Persistência no Supabase para o Hunter Dashboard
            if db and user_id:
                try:
                    db.table("lead_hunter_results").insert({
                        "user_id": user_id,
                        "name": nome,
                        "phone": lead['telefone'],
                        "website": lead['site'],
                        "pain_points": [dor],
                        "ai_analysis": f"Oportunidade: {oportunidade}",
                        "pitch_script": pitch_script,
                        "status": "ready"
                    }).execute()
                except: pass

            enriched_leads.append({
                **lead,
                "dor": dor,
                "oportunidade": oportunidade,
                "pitch_script": pitch_script,
                "health_score": random.randint(60, 98) 
            })
        except Exception as e:
            print(f"Erro ao enriquecer lead {lead['nome']}: {e}")
            enriched_leads.append(lead)

    return enriched_leads if enriched_leads else leads


# ==========================================
# GERAÇÃO DE VÍDEO (Replicate & SiliconFlow Fallback)
# ==========================================
def traduzir_prompt_video(roteiro, produto, plataforma="Multicanal"):
    """Traduz e enriquece o prompt para inglês para melhor resultado nos modelos de vídeo"""
    
    style_rule = "- Use cinematic terms (photorealistic, 4k, professional lighting)."
    if plataforma == "TikTok":
        style_rule = "- STRICTLY USE UGC (User Generated Content) style. Shot on iPhone, raw footage, dynamic, fast-paced, viral aesthetic, authentic, NO cinematic lighting."
    elif plataforma == "Meta/Instagram":
        style_rule = "- Use high-end commercial aesthetic, cinematic lighting, professional quality, 4k, elegant."

    prompt_ia = f"""Translate and enrich this video script for an AI video generation model (like Wan 2.1 or Luma).
Script: {roteiro}
Product: {produto}
Platform Context: {plataforma}

Rules:
- Result MUST be in English.
- Describe the visual scene in detail.
- STRICTLY FORBIDDEN: Do not include any text, letters, or subtitles in the scene description.
{style_rule}
- If the product relates to summer, beach or outdoor, ensure the scene reflects that environment.

Return ONLY the enriched English prompt."""
    
    try:
        traduzido = chamar_ia(prompt_ia, system_message="You are a professional video prompt engineer. No yapping, just the prompt.")
        if traduzido and len(traduzido) > 10:
            return traduzido
    except:
        pass
    
    fallback_style = "Cinematic" if plataforma != "TikTok" else "UGC viral"
    return f"{fallback_style} marketing video for {produto}. {roteiro}. High quality, no text."

def gerar_video_replicate(roteiro_completo, produto, plataforma="Multicanal"):
    """Gera um vídeo real usando Replicate (Wan 2.2 ou superior)"""
    if not REPLICATE_API_TOKEN:
        return None
    
    prompt_en = traduzir_prompt_video(roteiro_completo, produto, plataforma)
    
    print(f"🎬 DEBUG: Gerando vídeo REPLICATE: {prompt_en[:100]}...", flush=True)
    try:
        output = replicate.run(
            REPLICATE_VIDEO_MODEL,
            input={
                "prompt": prompt_en,
                "negative_prompt": "text, watermark, logo, letters, subtitles, low quality, blurry, static, distorted faces",
                "num_frames": 81,
                "aspect_ratio": "9:16" if "TikTok" in roteiro_completo or "Instagram" in roteiro_completo else "16:9",
                "sample_steps": 30,
            },
            timeout=180
        )
        video_url = str(output)
        if video_url.startswith("http"):
            print(f"✅ Replicate Vídeo SUCESSO: {video_url}", flush=True)
            return video_url
    except Exception as e:
        print(f"❌ Replicate Vídeo Erro: {e}", flush=True)
    return None

def gerar_video_siliconflow(roteiro_completo, produto, plataforma="Multicanal"):
    """Fallback: tenta gerar vídeo via SiliconFlow se disponível"""
    if not SILICONFLOW_API_KEY: return None
    
    prompt_en = traduzir_prompt_video(roteiro_completo, produto, plataforma)
    print(f"🎬 DEBUG: Tentando SiliconFlow Vídeo Fallback...", flush=True)
    
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
    # Nota: O modelo de vídeo da SiliconFlow pode variar. Usamos o padrão genérico de vídeo se disponível.
    payload = {
        "model": "deepseek-ai/DeepSeek-V3", # Placeholder para roteirização se necessário ou modelo de vídeo real
        "prompt": prompt_en,
        "negative_prompt": "text, letters, watermark"
    }
    # Por enquanto, se não houver um endpoint estável de vídeo na SiliconFlow no SDK, retornamos None
    # Mas deixamos a estrutura pronta para quando a API de vídeo deles estabilizar.
    return None

def gerar_video_com_fallback(roteiro_completo, produto, plataforma="Multicanal"):
    """Prioriza Replicate e usa SiliconFlow como fallback"""
    # 1. Tenta Replicate
    url = gerar_video_replicate(roteiro_completo, produto, plataforma)
    if url: return url
    
    # 2. Tenta SiliconFlow (Fallback)
    url = gerar_video_siliconflow(roteiro_completo, produto, plataforma)
    if url: return url
    
    return None


# Cliente para autenticação (usa anon key)
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente admin para leitura/escrita de dados (ignora RLS)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SECRET_ROLE") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase_admin: Client = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Função para obter um cliente Supabase que respeite o RLS (identidade do usuário)
def get_db(req=None):
    """
    Retorna o cliente Supabase adequado.
    Se um request for passado, tenta usar o token do usuário (RLS).
    Se não, ou se falhar, retorna o client anon ou admin (conforme backup).
    """
    if not req: 
        return supabase_admin or supabase

    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            # Cria um cliente temporário para esta requisição com o token do usuário
            user_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            user_client.postgrest.headers.update({"Authorization": f"Bearer {token}"})
            return user_client
        except:
            pass
    
    return supabase_admin or supabase

# Função para verificar o usuário logado via Token
def get_user_from_request(req):
    if not supabase: return None
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "): return None
    token = auth_header.split(" ")[1]
    try:
        user_res = supabase.auth.get_user(token)
        return user_res.user
    except Exception as e:
        print("Erro de auth:", e)
        return None

def get_user_from_token(token):
    """Recupera o user a partir de um JWT (usado em callbacks OAuth via state)"""
    if not supabase or not token: return None
    try:
        user_res = supabase.auth.get_user(token)
        return user_res.user
    except:
        return None

# ==========================================
# NÚCLEO DE INTELIGÊNCIA DUAL-MODEL
# ==========================================
def chamar_ia(prompt, system_message="Você é um assistente de marketing especialista.", modelo_forcado=None):
    if not OPENROUTER_API_KEY:
        return f"[Simulação IA - Coloque a OPENROUTER_API_KEY no .env]: {prompt[:40]}..."

    modelo_final = modelo_forcado if modelo_forcado else OPENROUTER_MODEL

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://meu-saas-copiloto.local",
        "X-Title": "Antigravity Copilot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": modelo_final,
        "messages": [
            {"role": "system", "content": system_message + "\n\nIMPORTANTE: Use Markdown estruturado (headers, listas, negrito) para garantir que este conteúdo seja perfeitamente legível por sistemas de AI Search (Perplexity, ChatGPT, Claude)."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ Erro OpenRouter: {e}", flush=True)
        return "Erro na geração da IA."

# ==========================================
# REVISÃO AUTOMÁTICA DE TEXTOS (Pós-processamento)
# ==========================================
def revisar_texto_ia(texto, tipo="caption"):
    """Revisa texto usando modelo rápido e barato para polimento final"""
    if not texto or len(texto) < 5: return texto
    
    if tipo == "hashtags":
        prompt = f"Melhore estas hashtags para marketing, retorne apenas as hashtags separadas por espaço: {texto}"
        system = "Você é especialista em hashtags para redes sociais."
    else:
        prompt = f"Corrija erros de português e melhore a fluência deste texto de marketing, sem comentários: {texto}"
        system = "Você é um revisor senior de textos publicitários."
    
    try:
        corrigido = chamar_ia(prompt, system_message=system, modelo_forcado="openai/gpt-3.5-turbo")
        return corrigido if (corrigido and len(corrigido) > 5) else texto
    except:
        return texto

def revisar_campanha_completa(campaign_data):
    """Aplica o polimento em todos os campos da campanha"""
    if not isinstance(campaign_data, dict): return campaign_data
    
    # Posts
    for post in campaign_data.get("instagram_posts", []):
        post["caption"] = revisar_texto_ia(post.get("caption", ""), "caption")
        post["hashtags"] = revisar_texto_ia(post.get("hashtags", ""), "hashtags")
    
    # Ads
    if "facebook_ad" in campaign_data:
        ad = campaign_data["facebook_ad"]
        ad["primary_text"] = revisar_texto_ia(ad.get("primary_text", ""), "caption")
        ad["headline"] = revisar_texto_ia(ad.get("headline", ""), "caption")
    
    # Email
    if "email" in campaign_data:
        email = campaign_data["email"]
        email["subject"] = revisar_texto_ia(email.get("subject", ""), "caption")
        email["body"] = revisar_texto_ia(email.get("body", ""), "caption")
    
    # Video
    if "video_script" in campaign_data:
        vid = campaign_data["video_script"]
        vid["hook"] = revisar_texto_ia(vid.get("hook", ""), "caption")
        vid["body"] = revisar_texto_ia(vid.get("body", ""), "caption")
        vid["cta"] = revisar_texto_ia(vid.get("cta", ""), "caption")
        
    return campaign_data

# ==========================================
# ROTAS FRONTEND E AUTH
# ==========================================
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/app')
@app.route('/login')
@app.route('/register')
def index():
    return render_template('index.html')

@app.route('/api/auth/register', methods=['POST'])
def register():
    dados = request.json
    email = dados.get("email")
    senha = dados.get("password")
    if not supabase: return jsonify({"erro": "Supabase não configurado no servidor."}), 500
    try:
        res = supabase.auth.sign_up({"email": email, "password": senha})
        if res.session:
            return jsonify({"user": res.user.email, "token": res.session.access_token}), 200
        else:
            return jsonify({"erro": "Cadastro realizado! Por favor, verifique a sua caixa de e-mail para confirmar a conta (Ou desative a confirmação no painel do Supabase)."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    dados = request.json
    email = dados.get("email")
    senha = dados.get("password")
    
    # BYPASS PARA TESTE ELITE (Modo Demo)
    if DEMO_LOGIN_ENABLED and email == "demo@mktpilot.io":
        return jsonify({"user": "demo@mktpilot.io", "token": "demo-token-elite-2025"}), 200

    if not supabase: return jsonify({"erro": "Supabase não configurado."}), 500

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
        if res.session:
            return jsonify({"user": res.user.email, "token": res.session.access_token}), 200
        else:
            return jsonify({"erro": "E-mail não confirmado."}), 400
    except Exception as e:
        return jsonify({"erro": "Credenciais inválidas"}), 401

# ==========================================
# GESTOR DE JOBS EM SEGUNDO PLANO
# ==========================================
def process_campaign_job(job_id, user_id, dados):
    """Processa a geração completa da campanha em background."""
    print(f"🚀 Iniciando Job {job_id} para usuário {user_id}", flush=True)
    
    # Precisamos de um client admin para atualizar o job sem depender do request original
    db = supabase_admin
    
    def update_job(status=None, progress=None, step=None, result=None, error=None):
        update_data = {}
        if status: update_data["status"] = status
        if progress is not None: update_data["progress"] = progress
        if step: update_data["current_step"] = step
        if result: update_data["result"] = result
        if error: update_data["error"] = error
        db.table("background_jobs").update(update_data).eq("id", job_id).execute()

    try:
        update_job(status="processing", progress=5, step="Analisando mercado e gerando copy...")
        
        # Sanatização de inputs
        produto = sanitize_input(dados.get('produto', ''))
        objetivo = sanitize_input(dados.get('objetivo', ''))
        nicho = sanitize_input(dados.get('nicho', 'Geral'))
        plataforma = dados.get('plataforma', 'Multicanal')
        tom_de_voz = sanitize_input(dados.get('tomDeVoz', 'Profissional'))
        publico_alvo = sanitize_input(dados.get('publicoAlvo', 'Geral'))
        concorrente_url = sanitize_input(dados.get('concorrenteUrl', ''))
        keywords = [sanitize_input(k) for k in dados.get('keywords', [])]

        # 1. Scraping se necessário
        contexto_spy = ""
        if concorrente_url:
            update_job(progress=10, step="Espionando concorrente...")
            texto_concorrente = scrape_concorrente(concorrente_url)
            if texto_concorrente:
                contexto_spy = f"\n\nATENÇÃO (Análise de Concorrência):\nSite do concorrente: \"{texto_concorrente[:1500]}\""

        # 2. Geração de Copy (IA) - SCHEMA ENFORCEMENT
        schema = {
            "facebook_ad": {
                "headline_a": "...", "headline_b": "...", "headline_c": "...",
                "primary_text_a": "...", "primary_text_b": "...", "primary_text_c": "...",
                "cta": "Saiba Mais"
            },
            "instagram_posts": [
                {"caption": "...", "hashtags": "#..."},
                {"caption": "...", "hashtags": "#..."}
            ],
            "email": {
                "subject_a": "...", "subject_b": "...",
                "body_a": "...", "body_b": "..."
            },
            "video_script": {
                "hook": "...", "body": "...", "cta": "..."
            }
        }

        prompt = f"""Crie uma campanha de marketing completa e de alto nível para o produto "{produto}".
Nicho: {nicho}. Objetivo: {objetivo}.{contexto_spy}
Público-alvo: {publico_alvo}. Tom de voz: {tom_de_voz}.
Plataforma principal: {plataforma}.

INSTRUÇÕES OBRIGATÓRIAS:
1. Gere 3 variações de Meta Ads (A: Foco em Ganho, B: Foco em Medo/Urgência, C: Foco em Curiosidade).
2. Gere 2 posts estratégicos para Instagram com legendas magnéticas.
3. Gere um script de vídeo curto (Reels/TikTok) com Hook, Body e CTA.
4. Gere uma sequência de e-mail marketing (2 variações).

RETORNE APENAS O JSON seguindo rigorosamente esta estrutura:
{json.dumps(schema, indent=2)}"""
        
        system_msg = "Você é o motor de IA do MKTPilot Pro. Sua saída é puramente JSON técnico de marketing de alta conversão. Não responda com texto explicativo."
        resposta_bruta = chamar_ia(prompt, system_message=system_msg, modelo_forcado=OPENROUTER_MODEL)
        
        def extrair_json_do_texto(texto):
            if not texto: return None
            # Limpeza agressiva usando os imports globais
            texto_limpo = re.sub(r'```json\s*', '', texto)
            texto_limpo = re.sub(r'```\s*', '', texto_limpo)
            try:
                # Tenta encontrar o bloco JSON mais externo
                start = texto_limpo.find('{')
                end = texto_limpo.rfind('}') + 1
                if start != -1 and end != 0:
                    return json.loads(texto_limpo[start:end])
                return None
            except: return None

        campaign_data = extrair_json_do_texto(resposta_bruta)
        if not campaign_data:
            print(f"❌ Erro ao decodificar JSON da IA: {resposta_bruta[:500]}", flush=True)
            raise Exception("A IA gerou um formato inválido. Tente novamente.")

        update_job(progress=40, step="Polindo textos e preparando artes...")
        campaign_data = revisar_campanha_completa(campaign_data)

        # 3. Geração de Imagens
        if "instagram_posts" in campaign_data:
            update_job(progress=50, step="Gerando criativos visuais...")
            for idx, post in enumerate(campaign_data["instagram_posts"]):
                if idx >= MAX_IMAGES: break
                post["image_url"] = gerar_imagem_com_fallback(post.get("caption", ""), produto)

        # 4. Geração de Vídeo e Áudio
        if "video_script" in campaign_data:
            update_job(progress=70, step="Produzindo vídeo e narração IA...")
            vs = campaign_data["video_script"]
            roteiro = f"{vs.get('hook')}. {vs.get('body')}. {vs.get('cta')}"
            
            # Vídeo
            v_url = gerar_video_com_fallback(roteiro, produto, plataforma)
            if v_url: vs["video_url"] = v_url
            else: vs["image_url"] = gerar_imagem_com_fallback(vs.get("hook", ""), produto)
            
            # Áudio
            a_url = gerar_audio_tts(roteiro, produto)
            if a_url: vs["audio_url"] = a_url

        # 5. Persistência Final
        update_job(progress=90, step="Finalizando e salvando...")
        
        insert_res = db.table("campaigns").insert({
            "user_id": user_id,
            "product": produto,
            "goal": objetivo,
            "result_text": json.dumps(campaign_data, ensure_ascii=False)
        }).execute()
        
        camp_id = insert_res.data[0].get('id') if insert_res.data else None
        
        # Concluir Job
        update_job(status="completed", progress=100, step="Concluído!", result={"campaign_id": camp_id, "data": campaign_data})
        print(f"✅ Job {job_id} concluído com sucesso!", flush=True)

    except Exception as e:
        print(f"❌ Erro no Job {job_id}: {e}", flush=True)
        update_job(status="failed", error=str(e), step="Erro no processamento")

# ==========================================
# ROTAS DO SAAS (Protegidas)
# ==========================================
@app.route('/api/copilot/gerar', methods=['POST'])
def api_copilot_gerar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401

    dados = request.json or {}
    
    # 1. Cria o registro do Job no banco
    try:
        db = get_db(request)
        job_res = db.table("background_jobs").insert({
            "user_id": user.id,
            "status": "pending",
            "payload": dados,
            "current_step": "Aguardando fila..."
        }).execute()
        
        if not job_res.data:
            return jsonify({"erro": "Falha ao criar tarefa no servidor"}), 500
            
        job_id = job_res.data[0]['id']
        
        # 2. Dispara a thread em background
        thread = threading.Thread(target=process_campaign_job, args=(job_id, user.id, dados))
        thread.start()
        
        return jsonify({"job_id": job_id, "mensagem": "Tarefa iniciada em background"}), 202
        
    except Exception as e:
        return jsonify({"erro": f"Erro ao iniciar processamento: {str(e)}"}), 500

@app.route('/api/copilot/status/<job_id>', methods=['GET'])
def api_copilot_status(job_id):
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    try:
        db = get_db(request)
        res = db.table("background_jobs").select("*").eq("id", job_id).eq("user_id", user.id).single().execute()
        
        if not res.data:
            return jsonify({"erro": "Tarefa não encontrada"}), 404
            
        return jsonify(res.data), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/copilot/jobs/active', methods=['GET'])
def api_copilot_jobs_active():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    try:
        db = get_db(request)
        res = db.table("background_jobs").select("id, status, progress, current_step, created_at").eq("user_id", user.id).in_("status", ["pending", "processing"]).order("created_at", desc=True).execute()
        return jsonify({"jobs": res.data}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/copilot/jobs/list', methods=['GET'])
def api_copilot_jobs_list():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    try:
        db = get_db(request)
        res = db.table("background_jobs").select("id, status, progress, current_step, created_at, error").eq("user_id", user.id).order("created_at", desc=True).limit(5).execute()
        return jsonify({"jobs": res.data}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/campaigns/update', methods=['POST'])
def api_campaigns_update():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    campanha_id = dados.get('id')
    novos_dados = dados.get('result_text') # Objeto JSON completo
    
    if not campanha_id or not novos_dados:
        return jsonify({"erro": "Dados incompletos"}), 400
        
    try:
        db = get_db(request)
        db.table("campaigns").update({
            "result_text": json.dumps(novos_dados, ensure_ascii=False)
        }).eq("id", campanha_id).eq("user_id", user.id).execute()
        return jsonify({"mensagem": "✅ Edição salva com sucesso!"}), 200
    except Exception as e:
        return jsonify({"erro": f"Falha ao salvar edição: {str(e)}"}), 500

@app.route('/api/campanhas/historico', methods=['GET'])
def api_campanhas_historico():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    try:
        db = get_db(request)
        res = db.table("campaigns").select("*").eq("user_id", user.id).order("created_at", desc=True).execute()
        return jsonify({"campanhas": res.data}), 200
    except Exception as e:
        return jsonify({"erro": "Falha ao buscar campanhas"}), 500

@app.route('/api/campanhas/otimizar', methods=['POST'])
def api_campanhas_otimizar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401

    dados = request.json or {}
    relatorio_manual = dados.get('relatorio', '')
    auto_mode = dados.get('auto', False)
    
    # Modo automático: busca campanhas do banco
    historico_texto = ""
    if auto_mode:
        try:
            db = get_db(request)
            res = db.table("campaigns").select("product, goal, result_text, created_at").eq("user_id", user.id).order("created_at", desc=True).limit(10).execute()
            if res.data:
                for i, camp in enumerate(res.data):
                    historico_texto += f"\n--- Campanha {i+1} ({camp.get('created_at','')[:10]}) ---\n"
                    historico_texto += f"Produto: {camp.get('product','')}\n"
                    historico_texto += f"Objetivo: {camp.get('goal','')}\n"
                    resultado = camp.get('result_text', '')
                    if isinstance(resultado, str) and len(resultado) > 500:
                        resultado = resultado[:500] + "..."
                    historico_texto += f"Resultado: {resultado}\n"
                print(f"📊 Eva Brain: Analisando {len(res.data)} campanhas do banco", flush=True)
            else:
                return jsonify({"resultado": "⚠️ Nenhuma campanha encontrada no seu histórico. Gere campanhas primeiro na aba 'Nova Campanha'."}), 200
        except Exception as e:
            print(f"Erro ao buscar histórico: {e}", flush=True)
            return jsonify({"erro": "Falha ao buscar campanhas do banco."}), 500
    
    conteudo = sanitize_input(relatorio_manual) or historico_texto
    if not conteudo.strip():
        return jsonify({"erro": "Cole dados de campanha ou clique em 'Análise Automática' para usar o histórico do banco."}), 400
    
    system_message = """Você é um Analista Sênior de Performance de Marketing Digital com 15 anos de experiência.
Sua especialidade é análise de campanhas de Meta Ads, TikTok Ads e marketing de conteúdo.

Ao analisar os dados, SEMPRE forneça:

1. **📊 Diagnóstico Geral** — Visão geral do desempenho
2. **✅ O que está funcionando** — Pontos fortes identificados
3. **❌ Problemas Encontrados** — Pontos fracos com gravidade (⚠️ Médio / 🔴 Crítico)
4. **🧪 Testes A/B Sugeridos** — No mínimo 3 testes concretos com variações específicas
5. **💡 Recomendações de Otimização** — Ações imediatas priorizadas
6. **📈 Previsão de ROAS** — Estimativa de melhoria se as recomendações forem seguidas

Responda em português do Brasil. Use markdown com negrito, listas e emojis para facilitar a leitura."""

    prompt = f"""Analise as seguintes campanhas de marketing e forneça um relatório completo de otimização:

{conteudo}

Faça uma análise profunda e acionável. Seja específico nas recomendações."""
    
    resultado = chamar_ia(prompt, system_message=system_message, modelo_forcado=OPENROUTER_ANALYSIS_MODEL)
    
    return jsonify({"resultado": resultado}), 200

# =====================================================
# ROTAS META ADS (AUTH & PUBLISH) — MULTIUSUÁRIO
# =====================================================

@app.route('/auth/meta/login')
def meta_login():
    if not META_APP_ID: return "META_APP_ID não configurado no .env", 400
    scope = "ads_management,ads_read,business_management,pages_manage_posts,pages_read_engagement"
    # Pega o token do usuário via query string para identificá-lo na callback
    user_token = request.args.get('token', '')
    import urllib.parse
    state = urllib.parse.quote(user_token)
    url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={META_APP_ID}&redirect_uri={META_REDIRECT_URI}&scope={scope}&state={state}"
    return redirect(url)

@app.route('/auth/meta/callback')
def meta_callback():
    code = request.args.get('code')
    if not code: return "Código de autorização não recebido", 400
    
    resp = requests.get("https://graph.facebook.com/v18.0/oauth/access_token", params={
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": META_REDIRECT_URI,
        "code": code
    })
    token_data = resp.json()
    if 'access_token' not in token_data: return jsonify(token_data), 400
    
    access_token = token_data['access_token']
    
    # Busca conta de anúncios
    accounts_resp = requests.get(f"https://graph.facebook.com/v18.0/me/adaccounts?access_token={access_token}")
    accounts_data = accounts_resp.json().get('data', [])
    ad_account_id = accounts_data[0]['id'] if accounts_data else None
    
    # Identificar o usuário via state parameter
    state_token = request.args.get('state', '')
    import urllib.parse
    state_token = urllib.parse.unquote(state_token)
    user = get_user_from_token(state_token)
    user_id = user.id if user else None
    
    # Salvar token no banco (por usuário)
    try:
        db = get_db(request)
        if db and ad_account_id and user_id:
            db.table("user_meta_tokens").upsert({
                "user_id": str(user_id),
                "access_token": access_token,
                "ad_account_id": ad_account_id
            }, on_conflict="user_id").execute()
            print(f"✅ Token Meta salvo para user {user_id} → conta {ad_account_id}", flush=True)
        elif not user_id:
            print("⚠️ OAuth Meta: usuário não identificado (state vazio)", flush=True)
    except Exception as e:
        print(f"⚠️ Erro ao salvar token Meta: {e}", flush=True)
    
    return f"""<html><body style='background:#0a0c15;color:white;font-family:Inter;text-align:center;padding:60px;'>
    <h1 style='color:#a78bfa;'>✅ Meta Ads Conectado!</h1>
    <p>Conta: <strong>{ad_account_id}</strong></p>
    <p>Agora você pode publicar anúncios direto pelo Copiloto.</p>
    <a href='/' style='color:#a78bfa;'>← Voltar ao Copiloto</a>
    </body></html>"""

@app.route('/api/campaigns/publish_to_meta', methods=['POST'])
def api_publish_to_meta():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Buscar token do usuário no banco
    try:
        db = get_db(request)
        res = db.table("user_meta_tokens").select("*").eq("user_id", user.id).single().execute()
        if not res.data:
            return jsonify({"erro": "Conecte sua conta Meta primeiro! Clique em 'Conectar Meta Ads' no menu."}), 400
        
        token = res.data['access_token']
        ad_account = res.data['ad_account_id']
        
        # Dados da campanha
        dados = request.json or {}
        campaign_name = dados.get('campaign_name', 'Campanha Copilot IA')
        
        # Criar campanha no Meta
        camp_resp = requests.post(
            f"https://graph.facebook.com/v18.0/{ad_account}/campaigns",
            params={"access_token": token},
            json={
                "name": campaign_name,
                "objective": "OUTCOME_AWARENESS",
                "status": "PAUSED",
                "special_ad_categories": []
            }
        )
        camp_data = camp_resp.json()
        
        if 'id' in camp_data:
            return jsonify({"mensagem": f"✅ Campanha criada no Meta Ads! ID: {camp_data['id']} (Status: PAUSADA)", "campaign_id": camp_data['id']}), 200
        else:
            return jsonify({"erro": f"Erro Meta: {camp_data.get('error', {}).get('message', 'Desconhecido')}"}), 400
    except Exception as e:
        return jsonify({"erro": f"Erro: {str(e)}"}), 500

# =====================================================
# ROTAS TIKTOK ADS (AUTH & PUBLISH) — MULTIUSUÁRIO
# =====================================================

@app.route('/auth/tiktok/login')
def tiktok_login():
    if not TIKTOK_APP_ID: return "TIKTOK_APP_ID não configurado no .env", 400
    user_token = request.args.get('token', '')
    import urllib.parse
    state = urllib.parse.quote(user_token)
    url = (
        f"https://business-api.tiktok.com/portal/auth?"
        f"app_id={TIKTOK_APP_ID}"
        f"&redirect_uri={TIKTOK_REDIRECT_URI}"
        f"&state={state}"
    )
    return redirect(url)

@app.route('/auth/tiktok/callback')
def tiktok_callback():
    auth_code = request.args.get('auth_code')
    if not auth_code: return "Código de autorização do TikTok não recebido", 400
    
    # Trocar auth_code por access_token
    resp = requests.post(
        f"{TIKTOK_API_BASE}/oauth2/access_token/",
        json={
            "app_id": TIKTOK_APP_ID,
            "secret": TIKTOK_APP_SECRET,
            "auth_code": auth_code,
            "grant_type": "authorization_code"
        }
    )
    token_data = resp.json()
    
    if token_data.get('code') != 0:
        return f"Erro TikTok: {token_data.get('message', 'Desconhecido')}", 400
    
    data = token_data.get('data', {})
    access_token = data.get('access_token')
    advertiser_ids = data.get('advertiser_ids', [])
    advertiser_id = str(advertiser_ids[0]) if advertiser_ids else None
    
    # Identificar o usuário via state parameter
    state_token = request.args.get('state', '')
    import urllib.parse
    state_token = urllib.parse.unquote(state_token)
    user = get_user_from_token(state_token)
    user_id = user.id if user else None
    
    # Salvar token no banco
    try:
        db = get_db(request)
        if db and user_id:
            db.table("user_tiktok_tokens").upsert({
                "user_id": str(user_id),
                "access_token": access_token,
                "advertiser_id": advertiser_id,
                "refresh_token": data.get('refresh_token', '')
            }, on_conflict="user_id").execute()
            print(f"✅ Token TikTok salvo para user {user_id} → advertiser {advertiser_id}", flush=True)
        elif not user_id:
            print("⚠️ OAuth TikTok: usuário não identificado (state vazio)", flush=True)
    except Exception as e:
        print(f"⚠️ Erro ao salvar token TikTok: {e}", flush=True)
    
    return f"""<html><body style='background:#0a0c15;color:white;font-family:Inter;text-align:center;padding:60px;'>
    <h1 style='color:#a78bfa;'>✅ TikTok Ads Conectado!</h1>
    <p>Conta Advertiser: <strong>{advertiser_id}</strong></p>
    <p>Agora você pode publicar vídeos gerados por IA direto no TikTok Ads.</p>
    <a href='/' style='color:#a78bfa;'>← Voltar ao Copiloto</a>
    </body></html>"""

@app.route('/api/tiktok/status', methods=['GET'])
def api_tiktok_status():
    user = get_user_from_request(request)
    if not user: return jsonify({"connected": False}), 200
    try:
        db = get_db(request)
        res = db.table("user_tiktok_tokens").select("advertiser_id").eq("user_id", user.id).single().execute()
        if res.data:
            return jsonify({"connected": True, "advertiser_id": res.data['advertiser_id']}), 200
    except: pass
    return jsonify({"connected": False}), 200

@app.route('/api/meta/status', methods=['GET'])
def api_meta_status():
    user = get_user_from_request(request)
    if not user: return jsonify({"connected": False}), 200
    try:
        db = get_db(request)
        res = db.table("user_meta_tokens").select("ad_account_id").eq("user_id", user.id).single().execute()
        if res.data:
            return jsonify({"connected": True, "ad_account_id": res.data['ad_account_id']}), 200
    except: pass
    return jsonify({"connected": False}), 200

@app.route('/api/campaigns/publish_to_tiktok', methods=['POST'])
def api_publish_to_tiktok():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Buscar token do usuário
    try:
        db = get_db(request)
        res = db.table("user_tiktok_tokens").select("*").eq("user_id", user.id).single().execute()
        if not res.data:
            return jsonify({"erro": "Conecte sua conta TikTok primeiro! Clique em 'Conectar TikTok' no menu."}), 400
        
        token = res.data['access_token']
        advertiser_id = res.data['advertiser_id']
        dados = request.json or {}
        video_url = dados.get('video_url', '')
        headline = dados.get('headline', 'Campanha Copilot IA')
        
        headers = {
            "Access-Token": token,
            "Content-Type": "application/json"
        }
        
        # 1. Criar Campanha
        camp_resp = requests.post(f"{TIKTOK_API_BASE}/campaign/create/", headers=headers, json={
            "advertiser_id": advertiser_id,
            "campaign_name": f"Copilot IA - {headline[:30]}",
            "objective_type": "REACH",
            "budget_mode": "BUDGET_MODE_INFINITE"
        })
        camp_data = camp_resp.json()
        print(f"DEBUG TikTok Campaign: {camp_data}", flush=True)
        
        if camp_data.get('code') != 0:
            return jsonify({"erro": f"Erro TikTok: {camp_data.get('message', 'Falha ao criar campanha')}"}), 400
        
        campaign_id = camp_data.get('data', {}).get('campaign_id')
        
        # 2. Upload do vídeo (se disponível)
        video_id = None
        if video_url:
            upload_resp = requests.post(f"{TIKTOK_API_BASE}/file/video/ad/upload/", headers=headers, json={
                "advertiser_id": advertiser_id,
                "video_url": video_url,
                "upload_type": "UPLOAD_BY_URL"
            })
            upload_data = upload_resp.json()
            print(f"DEBUG TikTok Upload: {upload_data}", flush=True)
            video_id = upload_data.get('data', {}).get('video_id')
        
        result = {
            "mensagem": f"✅ Campanha criada no TikTok Ads!",
            "campaign_id": campaign_id,
            "video_id": video_id,
            "status": "PAUSADA — Abra o TikTok Ads Manager para configurar orçamento e ativar."
        }
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"erro": f"Erro TikTok: {str(e)}"}), 500
@app.route('/api/leads/buscar', methods=['POST'])
def api_leads_buscar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    nicho = sanitize_input(dados.get('nicho'))
    cidade = sanitize_input(dados.get('cidade'))
    
    if not nicho or not cidade:
        return jsonify({"erro": "Nicho e Cidade são obrigatórios"}), 400
        
    db = get_db(request)
    leads = buscar_leads_locais(nicho, cidade, db=db, user_id=user.id)
    return jsonify({"leads": leads}), 200

@app.route('/api/leads/pitch', methods=['POST'])
def api_leads_pitch():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    lead_nome = dados.get('nome')
    lead_site = dados.get('site')
    meu_produto = dados.get('meu_produto', 'Marketing Digital')
    
    prompt = f"""Crie uma mensagem de abordagem para o WhatsApp para prospectar o cliente "{lead_nome}".
Website do cliente: {lead_site}
Meu produto/serviço: {meu_produto}

Regras:
- Seja curto, profissional e gere curiosidade.
- Cite que você viu o site deles e que pode melhorar a presença digital.
- Use emojis moderadamente.
- Termine com uma pergunta.
- Use Português do Brasil."""

    pitch = chamar_ia(prompt, system_message="Você é um SDR Senior focado em agendamento de reuniões.")
    return jsonify({"pitch": pitch}), 200

@app.route('/api/campaigns/score', methods=['POST'])
def api_campaigns_score():
    """Ad Performance Oracle 2.0: Avalia Copy + Imagem."""
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    texto = dados.get('texto', '')
    image_url = dados.get('image_url', '')
    
    contexto_imagem = ""
    if image_url:
        contexto_imagem = f"\nAnalise também este criativo visual: {image_url}. Avalie o contraste, a clareza da mensagem na imagem e se o design atrai cliques (Scroll-Stop)."

    prompt = f"""Analise tecnicamente este anúncio (Copy + Criativo). Dê uma nota de 0 a 100.
    
Texto: "{texto}"
{contexto_imagem}

Responda ESTRITAMENTE em JSON:
{{
  "score": 85,
  "status": "Excelente",
  "metrics": {{
    "clareza": 90,
    "urgencia": 80,
    "emocao": 85,
    "ctr": 95,
    "especificidade": 75
  }},
  "analise_visual": "O design está limpo com bom contraste...",
  "dica": "Sugestão técnica para subir o score."
}}
"""
    try:
        # Usando um modelo vision-capable se possível
        resultado = chamar_ia(prompt, system_message="Você é o Ad Performance Oracle, um avaliador de criativos de alta conversão.", modelo_forcado="google/gemini-2.0-flash-001")
        import json as pyjson
        data = pyjson.loads(resultado[resultado.find('{'):resultado.rfind('}')+1])
        
        # Persistência Elite
        if data.get('score'):
            try:
                db = get_db(request)
                db.table("ad_predictions").insert({
                    "user_id": user.id,
                    "creative_url": image_url,
                    "copy_text": texto,
                    "viral_score": data.get("score"),
                    "metrics": data.get("metrics"),
                    "suggestions": [data.get("dica")]
                }).execute()
            except: pass

        return jsonify(data), 200
    except:
        return jsonify({"score": 50, "status": "Regular", "metrics": {"clareza": 50, "urgencia": 50, "emocao": 50, "ctr": 50, "especificidade": 50}, "dica": "Continue editando..."}), 200

@app.route('/api/campaigns/proposal/<id>', methods=['GET'])
def api_campaign_proposal(id):
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    try:
        db = get_db(request)
        res = db.table("campaigns").select("*").eq("id", id).single().execute()
        if not res.data: return jsonify({"erro": "Campanha não encontrada"}), 404
        
        camp = res.data
        data = camp.get('resultado', {})
        
        # HTML Da Proposta Profissional
        html = f"""
        <html>
        <head>
            <title>Proposta de Marketing - {camp.get('nicho')}</title>
            <style>
                body {{ font-family: 'Inter', sans-serif; color: #334155; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
                .header {{ border-bottom: 2px solid #8b5cf6; padding-bottom: 20px; margin-bottom: 40px; }}
                h1 {{ color: #1e293b; margin: 0; }}
                .section {{ margin-bottom: 30px; }}
                .card {{ background: #f8fafc; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; margin-top: 15px; }}
                .tag {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; margin-bottom: 10px; }}
                .tag-ganho {{ background: #dcfce7; color: #166534; }}
                .tag-medo {{ background: #fee2e2; color: #991b1b; }}
                .tag-curiosidade {{ background: #dbeafe; color: #1e40af; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 0.9rem; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
                @media print {{ .no-print {{ display: none; }} }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Proposta Estratégica de Marketing</h1>
                <p>Preparada para: <strong>{camp.get('nicho')}</strong> | Gerado via MKTPilot</p>
                <button onclick="window.print()" class="no-print" style="background:#8b5cf6; color:white; border:none; padding:10px 20px; border-radius:6px; cursor:pointer; margin-top:10px;">Imprimir Proposta</button>
            </div>

            <div class="section">
                <h2>1. Estratégia Recomendada</h2>
                <p>Nossa inteligência identificou que para o objetivo de <strong>{camp.get('objetivo')}</strong>, devemos atuar em múltiplos ângulos psicológicos para maximizar o ROI.</p>
            </div>

            <div class="section">
                <h2>2. Variações de Anúncios (A/B Test)</h2>
                
                <div class="card">
                    <span class="tag tag-ganho">Variacao A: Foco em Benefício</span>
                    <h3>{data.get('facebook_ad', {}).get('headline_a', 'Headline Principal')}</h3>
                    <p>{data.get('facebook_ad', {}).get('primary_text_a', 'Texto estratégico...')}</p>
                </div>

                <div class="card">
                    <span class="tag tag-medo">Variacao B: Foco em Escassez</span>
                    <h3>{data.get('facebook_ad', {}).get('headline_b', 'Headline Urgência')}</h3>
                    <p>{data.get('facebook_ad', {}).get('primary_text_b', 'Texto focado em dor...')}</p>
                </div>
            </div>

            <div class="section">
                <h2>3. Recomendação de Investimento</h2>
                <p>Sugerimos um teste inicial de 7 dias com orçamento diário de R$ 50,00 distribuído entre as variações acima. O objetivo é identificar o menor custo por lead (CPL).</p>
            </div>

            <div class="footer">
                Proposta confidencial gerada por MKTPilot IA. Todos os direitos reservados.
            </div>
        </body>
        </html>
        """
        # Persistência Elite
        try:
            db = get_db(request)
            db.table("proposals").insert({
                "user_id": user.id,
                "campaign_id": camp.get('id'),
                "client_name": camp.get('nicho'),
                "content": data,
                "status": "sent"
            }).execute()
        except: pass

        return jsonify({"html": html}), 200
    except Exception as e:
        return jsonify({"erro": f"Erro ao gerar proposta: {str(e)}"}), 500

@app.route('/api/calendar/generate', methods=['POST'])
def api_calendar_generate():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Busca Brand Kit para contexto
    try:
        db = get_db(request)
        res = db.table("user_configs").select("*").eq("user_id", user.id).single().execute()
        brand_data = res.data or {}
    except: brand_data = {}

    prompt = f"""Crie um calendário editorial de marketing para 30 dias.
Nicho: {brand_data.get('nicho', 'Geral')}
Tom de Voz: {brand_data.get('tom_de_voz', 'Persuasivo')}

Para cada dia, forneça:
- Titulo do Post
- Tipo (Reel, Story, Email, Feed)
- Objetivo (Engajamento, Venda, Autoridade)

Responda APENAS um array JSON:
[
  {{"dia": 1, "titulo": "...", "tipo": "...", "objetivo": "..."}},
  ... ate o dia 30
]
"""
    resultado = chamar_ia(prompt, system_message="Você é um estrategista de conteúdo sênior.", modelo_forcado="openai/gpt-3.5-turbo")
    try:
        import json as pyjson
        inicio = resultado.find('[')
        fim = resultado.rfind(']') + 1
        data = pyjson.loads(resultado[inicio:fim])
        return jsonify({"calendario": data}), 200
    except:
        return jsonify({"erro": "Erro ao processar calendário"}), 500

@app.route('/api/hooks/list', methods=['GET'])
def api_hooks_list():
    # Hooks estáticos curados + adaptação IA opcional
    hooks = [
        {"hook": "O segredo que as agências não te contam sobre [PRODUTO].", "tipo": "Curiosidade"},
        {"hook": "Como eu saí de zero a [RESULTADO] em apenas 30 dias.", "tipo": "Ganho"},
        {"hook": "Pare de cometer este erro comum se você quer [OBJETIVO].", "tipo": "Medo"},
        {"hook": "3 ferramentas gratuitas que vão economizar 10h da sua semana.", "tipo": "Autoridade"},
        {"hook": "Por que 90% das pessoas falham ao tentar [NICHO].", "tipo": "Medo"}
    ]
    return jsonify({"hooks": hooks}), 200

@app.route('/api/funnel/clone', methods=['POST'])
def api_funnel_clone():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    url = dados.get('url')
    if not url: return jsonify({"erro": "URL obrigatória"}), 400
    
    # Scrape profundo
    conteudo = scrape_concorrente(url)
    
    prompt = f"""Analise esta Landing Page e desconstrua o funil de vendas.
Conteúdo: {conteudo[:3000]}

Responda estruturadamente:
1. Gancho Principal (Hook)
2. Promessa Única (Vantagem)
3. Gatilhos Mentais Utilizados
4. Estrutura do Funil (Lead Magnet -> Tripwire -> Core Offer)
5. Como podemos superar este funil?
"""
    resultado = chamar_ia(prompt, system_message="Você é um arquiteto de funis de vendas senior.")
    return jsonify({"analise": resultado}), 200

@app.route('/api/viral/trends', methods=['POST'])
def api_viral_trends():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Simulação de busca de tendências (ou integração real com Google Trends se houver API)
    trends = [
        {"tema": "IA Generativa em alta", "oportunidade": "Crie um post sobre como a IA economiza tempo."},
        {"tema": "Áudio Viral 'Lo-fi' no TikTok", "oportunidade": "Use este áudio para mostrar bastidores."},
        {"tema": "Trend 'Before vs After'", "oportunidade": "Mostre a transformação que seu produto causa."}
    ]
    return jsonify({"trends": trends}), 200

@app.route('/api/marketplace/list', methods=['GET'])
def api_marketplace_list():
    try:
        db = get_db(request)
        res = db.table("marketplace_templates").select("*").eq("status", "approved").execute()
        return jsonify({"templates": res.data or []}), 200
    except:
        # Fallback de demonstração se a tabela não existir
        mock_templates = [
            {"id": "1", "title": "Funil Black Friday 2025", "niche": "E-commerce", "price": 49.00, "author_name": "Agência Elite"},
            {"id": "2", "title": "Captura de Leads Imobiliário", "niche": "Imóveis", "price": 99.00, "author_name": "SDR Pro"}
        ]
        return jsonify({"templates": mock_templates}), 200

@app.route('/api/marketplace/publish', methods=['POST'])
def api_marketplace_publish():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    try:
        db = get_db(request)
        res = db.table("marketplace_templates").insert({
            "author_id": user.id,
            "title": dados.get("title"),
            "niche": dados.get("niche"),
            "price": dados.get("price", 0),
            "campaign_data": dados.get("campaign_data")
        }).execute()
        return jsonify({"status": "Publicado com sucesso!"}), 200
    except:
        return jsonify({"erro": "Erro ao publicar no marketplace."}), 500

@app.route('/api/competitors/watch', methods=['POST'])
def api_competitors_watch():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados = request.json or {}
    url = dados.get('url')
    
    try:
        db = get_db(request)
        # Salva o monitor
        db.table("competitor_monitors").insert({
            "user_id": user.id,
            "website_url": url,
            "competitor_name": url.split('//')[-1].split('/')[0]
        }).execute()
        return jsonify({"status": "Radar Ativado! Monitorando mudanças..."}), 200
    except:
        return jsonify({"erro": "Erro ao ativar radar."}), 500

@app.route('/api/challenges/current', methods=['GET'])
def api_challenges_current():
    try:
        db = get_db(request)
        res = db.table("weekly_challenges").select("*").eq("status", "active").order("created_at", desc=True).limit(1).execute()
        if res.data:
            return jsonify({"challenge": res.data[0]}), 200
        else:
            return jsonify({"challenge": {
                "title": "Lançamento Fone Noise Cancelling",
                "description": "Crie o anúncio mais viral para executivos.",
                "status": "active"
            }}), 200
    except:
        return jsonify({"erro": "Erro ao buscar desafio"}), 500

import threading
import time

def autopilot_worker():
    """Simula o monitoramento 24h do Autopilot."""
    while True:
        try:
            db = supabase_admin or supabase
            if db:
                # Busca configs ativas
                configs = db.table("autopilot_configs").select("*").eq("is_active", True).execute()
                for cfg in configs.data:
                    # Simulação de otimização
                    db.table("autopilot_logs").insert({
                        "config_id": cfg['id'],
                        "action": "optimized_copy",
                        "ai_reasoning": "Detectada queda no CTR. Ajustando headlines para maior urgência."
                    }).execute()
        except: pass
        time.sleep(3600) # Checa a cada hora

# Inicia o worker em background
threading.Thread(target=autopilot_worker, daemon=True).start()

if __name__ == '__main__':
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print("INICIADO NA PORTA 5000")
    print("=> Verificando Banco Supabase: " + ("Conectado!" if supabase else "AUSENTE"), flush=True)
    print("=> Cliente Admin (service_role): " + ("OK" if supabase_admin else "Aviso: Usando anon_key"), flush=True)
    print("=> Chave OpenRouter: " + ("OK" if OPENROUTER_API_KEY else "AUSENTE"), flush=True)
    print("=> Chave SiliconFlow: " + ("OK" if SILICONFLOW_API_KEY else "AUSENTE"), flush=True)
    app.run(host='0.0.0.0', port=5000, debug=debug_enabled, use_reloader=False)
