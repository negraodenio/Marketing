from __future__ import annotations

import os
import sys

# Forcar UTF-8 no stdout/stderr — critico no Windows (CP1252 nao suporta emojis)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from typing import Optional, Dict, List, Any

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(_env_path, override=True) # Carrega as chaves antes de tudo

from routes.modules import modules_bp
from routes.seo_engine import seo_bp
import requests
import json
import asyncio
import ipaddress
import socket
from bs4 import BeautifulSoup
import edge_tts
from flask import Flask, request, jsonify, render_template, redirect, Response, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from datetime import datetime, timedelta
import threading
import uuid
import re
import random
import hashlib
import logging
import subprocess
import importlib.util
from pathlib import Path
from urllib.parse import urlparse
from contextvars import ContextVar
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# load_dotenv removido daqui
app = Flask(__name__)
app.register_blueprint(modules_bp)
app.register_blueprint(seo_bp)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or os.getenv("SUPABASE_SECRET_ROLE")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("FLASK_SECRET_KEY must be set in production")

def _rate_limit_key():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        return "token:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return get_remote_address()

limiter = Limiter(
    key_func=_rate_limit_key,
    app=app,
    default_limits=["300 per hour", "60 per minute"],
)

logger = logging.getLogger("mktpilot")

def _load_pipeline_v2():
    """Carrega pipeline_v2 via path para evitar conflitos com app.py."""
    try:
        module_path = Path(__file__).resolve().parent / "app" / "services" / "pipeline_v2.py"
        if not module_path.exists():
            return None
        spec = importlib.util.spec_from_file_location("pipeline_v2_module", str(module_path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.warning("Falha ao carregar pipeline_v2: %s", e)
        return None

PIPELINE_V2 = _load_pipeline_v2()
PIPELINE_V2_ENABLED = os.getenv("ENABLE_PIPELINE_V2", "true").lower() == "true"

# ==========================================
# CONFIGURAÇÕES E SUPABASE
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_anon_key") # Aceita o nome padrão do Supabase
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "meta-llama/llama-3-70b-instruct"
OPENROUTER_ANALYSIS_MODEL = os.getenv("OPENROUTER_ANALYSIS_MODEL", "minimax/minimax-m2.7")
BACKGROUND_THREADS_ENABLED = os.getenv("ENABLE_BACKGROUND_THREADS", "false").lower() == "true" and not os.getenv("VERCEL")
AUTOPILOT_WORKER_ENABLED = os.getenv("ENABLE_AUTOPILOT_WORKER", "false").lower() == "true" and not os.getenv("VERCEL")
CAMPAIGN_REFINEMENT_ENABLED = os.getenv("ENABLE_CAMPAIGN_REFINEMENT", "true").lower() == "true"
OAUTH_STATE_TTL_SECONDS = int(os.getenv("OAUTH_STATE_TTL_SECONDS", "600"))

# Guard rails de custo (daily)
DAILY_MAX_IA_CALLS = int(os.getenv("DAILY_MAX_IA_CALLS", "150"))
DAILY_MAX_IMAGE_GENS = int(os.getenv("DAILY_MAX_IMAGE_GENS", "20"))
DAILY_MAX_VIDEO_GENS = int(os.getenv("DAILY_MAX_VIDEO_GENS", "5"))
DAILY_MAX_ESTIMATED_COST_USD = float(os.getenv("DAILY_MAX_ESTIMATED_COST_USD", "3.0"))

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
print(f"[BOOT] SERPAPI_KEY loaded: {bool(SERPAPI_KEY)}", flush=True)

MAX_IMAGES = 3
CACHE_IMAGE_URLS = {}

# ==========================================
# ASSET CACHE (persistente em disco)
# ==========================================
ASSET_CACHE_FILE = os.path.join(os.path.dirname(__file__), "static", "asset_cache.json")
ASSET_CACHE = {}
ASSET_CACHE_MAX_AGE_SECS = 7 * 24 * 3600  # 7 days

def _load_asset_cache():
    global ASSET_CACHE
    try:
        if os.path.exists(ASSET_CACHE_FILE):
            with open(ASSET_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Purge expired
            now = time.time()
            ASSET_CACHE = {k: v for k, v in data.items() if now - v.get("ts", 0) < ASSET_CACHE_MAX_AGE_SECS}
    except Exception:
        ASSET_CACHE = {}

def _save_asset_cache():
    try:
        os.makedirs(os.path.dirname(ASSET_CACHE_FILE), exist_ok=True)
        with open(ASSET_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ASSET_CACHE, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Falha ao salvar asset cache: %s", e)

def _asset_cache_key(product: str, prompt: str) -> str:
    return hashlib.md5(f"{product}||{prompt}".encode("utf-8")).hexdigest()

def _check_asset_cache(product: str, prompt: str) -> Optional[str]:
    key = _asset_cache_key(product, prompt)
    entry = ASSET_CACHE.get(key)
    if entry and isinstance(entry, dict) and entry.get("url"):
        logger.info("Asset cache HIT for key %s -> %s", key[:16], entry["url"][:60])
        return entry["url"]
    return None

def _set_asset_cache(product: str, prompt: str, url: str):
    if not url:
        return
    key = _asset_cache_key(product, prompt)
    ASSET_CACHE[key] = {"url": url, "ts": time.time()}
    _save_asset_cache()

_load_asset_cache()

# ==========================================
# CAMPAIGN MEMORY (Brand Kits persistentes)
# ==========================================

def _load_brand_memory(db, user_id: str, product_name: str) -> Optional[dict]:
    """Carrega memória de marca existente para o produto + usuário."""
    if not db or not user_id or not product_name:
        return None
    try:
        res = db.table("brand_kits").select("*").eq("user_id", str(user_id)).eq("product", product_name).limit(1).execute()
        if res.data and len(res.data) > 0:
            memory = res.data[0].get("memory_data", {})
            if isinstance(memory, str):
                memory = json.loads(memory)
            logger.info("Brand memory loaded for %s (user %s)", product_name[:40], user_id[:16])
            return memory
    except Exception as e:
        msg = str(e).lower()
        if "brand_kits" not in msg and "relation" not in msg and "does not exist" not in msg:
            logger.warning("Erro ao carregar brand memory: %s", e)
        # Tabela nao existe — skip gracioso
    return None

def _save_brand_memory(db, user_id: str, product_name: str, memory_data: dict):
    """Salva/atualiza memória de marca no Supabase."""
    if not db or not user_id or not product_name or not memory_data:
        return
    try:
        db.table("brand_kits").upsert({
            "user_id": str(user_id),
            "product": product_name,
            "memory_data": memory_data,
            "updated_at": datetime.utcnow().isoformat(),
        }, on_conflict="user_id,product").execute()
        logger.info("Brand memory saved for %s (user %s)", product_name[:40], user_id[:16])
    except Exception as e:
        msg = str(e).lower()
        if "brand_kits" not in msg and "relation" not in msg and "does not exist" not in msg:
            logger.warning("Erro ao salvar brand memory: %s", e)
        # Tabela nao existe — skip gracioso

# ==========================================
# BRAND KIT — General brand settings API
# ==========================================

@app.route('/api/brand/config', methods=['GET', 'POST'])
@limiter.limit("30 per hour")
def api_brand_config():
    user = get_user_from_request(request)
    if not user:
        return jsonify({"erro": "Não autorizado"}), 401

    if request.method == 'GET':
        try:
            db = get_db(request)
            if not db:
                logger.error("DB is None in /api/brand/config GET")
                return jsonify({"erro": "authentication required"}), 401
            res = db.table("brand_kits").select("*").eq("user_id", str(user.id)).eq("product", "__brand__").limit(1).execute()
            if res.data and res.data[0]:
                data = res.data[0]
                settings = data.get("memory_data", {})
                if isinstance(settings, str):
                    settings = json.loads(settings)
                return jsonify({"settings": settings}), 200
        except Exception:
            pass
        # Fallback: return empty settings
        return jsonify({"settings": {}}), 200

    # POST — Save brand settings
    dados, err = get_json_payload()
    if err:
        return err
    settings = dados.get("settings", {})
    if not isinstance(settings, dict):
        return jsonify({"erro": "settings deve ser um objeto JSON"}), 400

    try:
        db = get_db(request)
        if db:
            db.table("brand_kits").upsert({
                "user_id": str(user.id),
                "product": "__brand__",
                "memory_data": settings,
                "updated_at": datetime.utcnow().isoformat(),
            }, on_conflict="user_id,product").execute()
            return jsonify({"ok": True}), 200
    except Exception as e:
        msg = str(e).lower()
        if "brand_kits" not in msg and "relation" not in msg and "does not exist" not in msg:
            logger.warning("Erro ao salvar brand config: %s", e)
        return jsonify({"ok": False, "erro": "Tabela de configurações indisponível"}), 200

    return jsonify({"ok": False}), 200

# ==========================================
# SSE EVENT STREAMING
# ==========================================
_sse_queues: dict[str, list] = {}
_sse_lock = threading.Lock()

def _push_sse_event(job_id: str, event_type: str, data: dict):
    """Push an event to the SSE queue for a given job_id."""
    with _sse_lock:
        if job_id in _sse_queues:
            _sse_queues[job_id].append({"event": event_type, "data": data})

def _ensure_sse_queue(job_id: str):
    """Create SSE queue for a job if not exists."""
    with _sse_lock:
        if job_id not in _sse_queues:
            _sse_queues[job_id] = []

def _cleanup_sse_queue(job_id: str):
    """Clean up SSE queue after job completes."""
    with _sse_lock:
        _sse_queues.pop(job_id, None)

def _drain_sse_events(job_id: str) -> list:
    """Atomically drain all pending events for a job_id."""
    with _sse_lock:
        events = _sse_queues.get(job_id, [])
        _sse_queues[job_id] = []
        return events

_oauth_state_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="mktpilot-oauth-state-v1")

_cost_guard_user_id = ContextVar("cost_guard_user_id", default=None)
_cost_guard_db = ContextVar("cost_guard_db", default=None)

import time
import requests

def sanitize_input(text):
    """Proteção básica contra Prompt Injection e estouro de contexto"""
    if not text: return ""
    clean = str(text).replace("ignore all previous", "[REDACTED]").replace("system prompt", "[REDACTED]")
    return clean[:1000]

def get_json_payload(required_fields=None):
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, (jsonify({"erro": "Payload JSON inválido"}), 400)
    if required_fields:
        missing = [f for f in required_fields if not dados.get(f)]
        if missing:
            return None, (jsonify({"erro": f"Campos obrigatórios ausentes: {', '.join(missing)}"}), 400)
    return dados, None

def validate_public_http_url(url):
    if not url:
        raise ValueError("URL vazia")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL deve usar http/https")
    if not parsed.hostname:
        raise ValueError("Hostname inválido")

    blocked_networks = [
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    ]

    try:
        resolved = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Falha ao resolver DNS da URL")

    for item in resolved:
        ip = ipaddress.ip_address(item[4][0])
        for blocked in blocked_networks:
            if ip in blocked:
                raise ValueError("URL resolve para IP privado/reservado")

def build_oauth_state(user_id, provider):
    payload = {
        "u": str(user_id),
        "p": provider,
        "n": uuid.uuid4().hex,
    }
    return _oauth_state_serializer.dumps(payload)

def parse_oauth_state(state, expected_provider):
    if not state:
        return None
    try:
        payload = _oauth_state_serializer.loads(state, max_age=OAUTH_STATE_TTL_SECONDS)
        if payload.get("p") != expected_provider:
            return None
        return payload
    except (BadSignature, SignatureExpired):
        return None

def _estimate_event_cost(kind):
    costs = {
        "ia_call": 0.002,
        "image_gen": 0.010,
        "video_gen": 0.100,
    }
    return costs.get(kind, 0.0)

def _check_and_consume_cost_guard(kind="ia_call"):
    user_id = _cost_guard_user_id.get()
    db = _cost_guard_db.get()
    if not user_id or not db:
        return True, None

    usage_date = datetime.utcnow().date().isoformat()
    try:
        res = db.table("ai_usage_daily").select("*").eq("user_id", str(user_id)).eq("usage_date", usage_date).limit(1).execute()
    except Exception as e:
        msg = str(e).lower()
        if "ai_usage_daily" in msg or "relation" in msg or "does not exist" in msg:
            # Compatibilidade: se migração ainda não foi aplicada, não derruba a produção
            return True, None
        return False, "Falha ao validar limites de uso"

    row = res.data[0] if res and getattr(res, "data", None) else {}
    ia_calls = int(row.get("ia_calls", 0))
    image_gens = int(row.get("image_gens", 0))
    video_gens = int(row.get("video_gens", 0))
    estimated_cost = float(row.get("estimated_cost_usd", 0) or 0)

    if kind == "ia_call" and ia_calls >= DAILY_MAX_IA_CALLS:
        return False, "Limite diário de chamadas IA atingido"
    if kind == "image_gen" and image_gens >= DAILY_MAX_IMAGE_GENS:
        return False, "Limite diário de geração de imagem atingido"
    if kind == "video_gen" and video_gens >= DAILY_MAX_VIDEO_GENS:
        return False, "Limite diário de geração de vídeo atingido"

    next_cost = estimated_cost + _estimate_event_cost(kind)
    if next_cost > DAILY_MAX_ESTIMATED_COST_USD:
        return False, "Limite diário de custo estimado atingido"

    payload = {
        "user_id": str(user_id),
        "usage_date": usage_date,
        "ia_calls": ia_calls + (1 if kind == "ia_call" else 0),
        "image_gens": image_gens + (1 if kind == "image_gen" else 0),
        "video_gens": video_gens + (1 if kind == "video_gen" else 0),
        "estimated_cost_usd": round(next_cost, 4),
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        db.table("ai_usage_daily").upsert(payload, on_conflict="user_id,usage_date").execute()
    except Exception as e:
        msg = str(e).lower()
        if "ai_usage_daily" in msg or "relation" in msg or "does not exist" in msg:
            return True, None
        return False, "Falha ao registrar consumo"

    return True, None

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

    print(f"[IMG] tentando SiliconFlow para: {prompt_en[:30]}...", flush=True)
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
                res_json = response.json()
                if res_json and 'data' in res_json and len(res_json['data']) > 0:
                    image_url = res_json['data'][0].get('url')
                    if image_url:
                        CACHE_IMAGE_URLS[cache_key] = image_url
                        print(f"[IMG OK] SiliconFlow: {image_url}", flush=True)
                        return image_url
                print(f"⚠️ SiliconFlow retornou JSON inesperado: {res_json}", flush=True)
            else:
                print(f"[IMG ERR] SiliconFlow ({response.status_code}): {response.text}", flush=True)
        except Exception as e:
            print(f"[IMG ERR] SiliconFlow excecao: {e}", flush=True)
            time.sleep(1)
    return None

def gerar_imagem_replicate(prompt_texto, produto):
    if not REPLICATE_API_TOKEN: 
        print("[WARN] Replicate Token ausente no .env", flush=True)
        return None
    print(f"[IMG] tentando Replicate Fallback para: {prompt_texto[:30]}...", flush=True)
    prompt = f"Professional commercial photography for {produto}. Realistic lighting, physically grounded, no floating objects, no fake logos, no distorted text. Natural composition. {prompt_texto[:200]}"
    try:
        output = replicate.run(
            REPLICATE_MODEL,
            input={"prompt": prompt, "width": 1024, "height": 1024, "num_outputs": 1}
        )
        url = str(output[0]) if output else None
        if url: print(f"[IMG OK] Replicate: {url}", flush=True)
        return url
    except Exception as e:
        print(f"[IMG ERR] Replicate: {e}", flush=True)
    return None

def placeholder_image(texto=""):
    return f"https://placehold.co/1024x1024/2c3e50/ffffff?text={texto.replace(' ', '+')[:20]}"

def gerar_imagem_com_fallback(prompt_texto, produto):
    # 0. Check asset cache first
    cached = _check_asset_cache(produto, prompt_texto)
    if cached:
        return cached

    ok, reason = _check_and_consume_cost_guard("image_gen")
    if not ok:
        print(f"⚠️ Geração de imagem bloqueada por custo: {reason}", flush=True)
        return placeholder_image("Limite de Uso")

    # 1. Tenta SiliconFlow
    url = gerar_imagem_siliconflow(prompt_texto, produto)
    if url:
        _set_asset_cache(produto, prompt_texto, url)
        return url
    
    # 2. Tenta Replicate (Fallback)
    url = gerar_imagem_replicate(prompt_texto, produto)
    if url:
        _set_asset_cache(produto, prompt_texto, url)
        return url
    
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
        validate_public_http_url(url)
        headers = {'User-Agent': 'MKTPilotBot/1.0'}
        response = requests.get(url, headers=headers, timeout=8, allow_redirects=False, stream=True)
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return ""
        raw = response.raw.read(5_000_000, decode_content=True)
        soup = BeautifulSoup(raw, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        texto = soup.get_text(separator=' ', strip=True)
        return texto[:3000] # Limita a 3000 caracteres para não estourar o prompt
    except Exception as e:
        print(f"[SCRAPE ERR] da URL {url}: {e}", flush=True)
        return ""

def upload_to_storage(file_path, filename, bucket_name="marketing_assets"):
    """Sobe um arquivo para o Supabase Storage e retorna a URL pública"""
    if not supabase_admin: return None
    try:
        # Garantir que o bucket existe (tenta criar se falhar)
        try:
            supabase_admin.storage.create_bucket(bucket_name, options={"public": True})
        except: pass

        with open(file_path, 'rb') as f:
            supabase_admin.storage.from_(bucket_name).upload(filename, f, {"content-type": "audio/mpeg"})
            
        res = supabase_admin.storage.from_(bucket_name).get_public_url(filename)
        return res
    except Exception as e:
        print(f"[STORAGE ERR] para Storage: {e}", flush=True)
        return None

async def generate_tts_async(text, output_path, voice="pt-BR-AntonioNeural"):
    """Gera áudio usando edge-tts de forma assíncrona"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def gerar_audio_tts(roteiro_completo, produto):
    """Função síncrona wrapper para gerar o áudio via Supabase Storage"""
    if not roteiro_completo: return None
    
    # Em ambientes serverless como Vercel, devemos usar /tmp
    temp_dir = "/tmp" if os.name != 'nt' else "static/audio"
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(temp_dir, filename)
    
    try:
        print(f"Gerando TTS para: {produto}...", flush=True)
        asyncio.run(generate_tts_async(roteiro_completo, filepath))
        
        # Sobe para o Storage (Vercel é read-only, não podemos servir local)
        public_url = upload_to_storage(filepath, filename)
        return public_url or f"/static/audio/{filename}" # Fallback local se não for Vercel
    except Exception as e:
        print(f"Erro ao gerar TTS: {e}", flush=True)
        return None

# ==========================================
# LEAD HUNTER (Prospecção de Leads)
# ==========================================
def buscar_leads_locais(nicho, cidade, db=None, user_id=None):
    """Busca leads no Google/Maps. Usa SerpApi se houver chave, senão usa Scraper Lite."""
    query = f"{nicho} {cidade}"
    leads = []
    
    print(f"[LEAD HUNTER] Busca: nicho='{nicho}' cidade='{cidade}' query='{query}'", flush=True)
    print(f"[LEAD HUNTER] SERPAPI_KEY configurada: {bool(SERPAPI_KEY)}", flush=True)
    
    if SERPAPI_KEY:
        try:
            params = {
                "engine": "google_maps",
                "q": f"{nicho} {cidade}",
                "api_key": SERPAPI_KEY
            }
            res = requests.get("https://serpapi.com/search", params=params, timeout=20)
            data = res.json()
            # SerpApi pode retornar place_results ou local_results dependendo da query
            places = data.get("place_results") or data.get("local_results") or []
            print(f"[LEAD HUNTER] SerpApi response keys: {list(data.keys())}", flush=True)
            print(f"[LEAD HUNTER] SerpApi status: {data.get('search_metadata', {}).get('status', 'unknown')}", flush=True)
            print(f"[LEAD HUNTER] SerpApi resultados: {len(places)}", flush=True)
            if isinstance(places, list):
                for place in places:
                    leads.append({
                        "nome": place.get("title"),
                        "telefone": place.get("phone"),
                        "site": place.get("website"),
                        "nota": place.get("rating", "N/A")
                    })
        except Exception as e:
            print(f"[LEAD HUNTER] SerpApi erro: {e}", flush=True)

    # Scraper Lite (Fallback usando busca pública)
    if not leads:
        print(f"[LEAD HUNTER] SerpApi sem resultados — tentando Scraper Lite...", flush=True)
        try:
            import re
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            ua = user_agents[hash(query) % len(user_agents)]
            headers = {'User-Agent': ua, 'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'}
            
            # --- TENTATIVA 1: Google ---
            print(f"[LEAD HUNTER] Tentando Google...", flush=True)
            try:
                search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}+whatsapp&hl=pt-BR"
                resp = requests.get(search_url, headers=headers, timeout=15)
                print(f"[LEAD HUNTER] Google HTTP {resp.status_code} ({len(resp.text)} bytes)", flush=True)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                selectors = ['.tF2Cxc', '.g', '.yuRUbf', '.MjjYud', '[data-hveid]', 'div.g', '.Gx5Zad', '.xpd', '[data-sokoban-container]']
                results = []
                for sel in selectors:
                    results = soup.select(sel)
                    if results:
                        print(f"[LEAD HUNTER] Google seletor '{sel}' → {len(results)} resultados", flush=True)
                        break
                if not results:
                    for div in soup.find_all('div'):
                        h3 = div.find('h3')
                        a = div.find('a', href=True)
                        if h3 and a and a['href'].startswith('http'):
                            results.append(div)
                    print(f"[LEAD HUNTER] Google fallback genérico → {len(results)} candidatos", flush=True)
                
                for res in results[:8]:
                    link_tag = res.find('a')
                    link = link_tag['href'] if link_tag else ""
                    nome_tag = res.find('h3')
                    nome = nome_tag.get_text() if nome_tag else "Empresa Local"
                    text = res.get_text()
                    zap_match = re.search(r'(\(?\d{2,3}\)?\s?\d{4,5}-?\d{4})', text)
                    telefone = zap_match.group(1) if zap_match else "Pendente"
                    if nome != "Empresa Local" and link:
                        leads.append({"nome": nome, "telefone": telefone, "site": link, "nota": "N/A"})
            except Exception as e:
                print(f"[LEAD HUNTER] Google erro: {e}", flush=True)
            
            # --- TENTATIVA 2: DuckDuckGo (menos bloqueio) ---
            if not leads:
                print(f"[LEAD HUNTER] Google sem resultados — tentando DuckDuckGo...", flush=True)
                try:
                    ua2 = user_agents[(hash(query) + 2) % len(user_agents)]
                    ddg_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query + ' contato whatsapp')}"
                    ddg_resp = requests.get(ddg_url, headers={'User-Agent': ua2}, timeout=15)
                    print(f"[LEAD HUNTER] DDG HTTP {ddg_resp.status_code} ({len(ddg_resp.text)} bytes)", flush=True)
                    ddg_soup = BeautifulSoup(ddg_resp.text, 'html.parser')
                    for a_tag in ddg_soup.select('a.result__a'):
                        href = a_tag.get('href', '')
                        text = a_tag.get_text(strip=True)
                        # DuckDuckGo wraps links in redirect
                        if 'uddg=' in href:
                            import urllib.parse as up
                            qs = up.parse_qs(up.urlparse(href).query)
                            real_url = qs.get('uddg', [href])[0]
                        else:
                            real_url = href
                        if text and real_url.startswith('http'):
                            leads.append({"nome": text, "telefone": "Pendente", "site": real_url, "nota": "N/A"})
                    print(f"[LEAD HUNTER] DDG encontrou {len(leads)} leads", flush=True)
                except Exception as e:
                    print(f"[LEAD HUNTER] DuckDuckGo erro: {e}", flush=True)
            
            # --- TENTATIVA 3: Bing (último recurso) ---
            if not leads:
                print(f"[LEAD HUNTER] DDG sem resultados — tentando Bing...", flush=True)
                try:
                    ua3 = user_agents[(hash(query) + 3) % len(user_agents)]
                    bing_url = f"https://www.bing.com/search?q={requests.utils.quote(query + ' contato whatsapp')}"
                    bing_resp = requests.get(bing_url, headers={'User-Agent': ua3}, timeout=15)
                    print(f"[LEAD HUNTER] Bing HTTP {bing_resp.status_code} ({len(bing_resp.text)} bytes)", flush=True)
                    bing_soup = BeautifulSoup(bing_resp.text, 'html.parser')
                    for li in bing_soup.select('#b_results li.b_algo'):
                        h2 = li.find('h2')
                        a = li.find('a')
                        if h2 and a:
                            nome = h2.get_text(strip=True)
                            link = a.get('href', '')
                            if nome and link.startswith('http'):
                                leads.append({"nome": nome, "telefone": "Pendente", "site": link, "nota": "N/A"})
                    print(f"[LEAD HUNTER] Bing encontrou {len(leads)} leads", flush=True)
                except Exception as e:
                    print(f"[LEAD HUNTER] Bing erro: {e}", flush=True)
                    
        except Exception as e:
            print(f"[LEAD HUNTER] Erro no Scraper Lite: {e}", flush=True)
    
    print(f"[LEAD HUNTER] Total leads encontrados: {len(leads)}", flush=True)

    # ENRIQUECIMENTO NINJA COM IA
    enriched_leads = []
    for lead in leads[:5]: # Analisar apenas os top 5 para evitar delay excessivo
        try:
            nome = lead['nome']
            # Análise de Dor & Oportunidade
            lang_leads = _detect_lang(f"{nome} {nicho}")
            lang_inst_leads = _lang_instruction(lang_leads)
            pain_labels = {
                "en": "Identify 1 likely pain point (e.g. lack of digital presence) and 1 golden opportunity (e.g. dominate local paid traffic).",
                "pt": "Identifique 1 dor provável (ex: falta de presença digital) e 1 oportunidade de ouro (ex: dominar o tráfego pago local)."
            }
            prompt_analise = f"Analyze the business '{nome}' in the niche '{nicho}'. {pain_labels.get(lang_leads, pain_labels['pt'])} Be short and direct (max 15 words each).\n{lang_inst_leads}"
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
            prompt_pitch = f"Generate a short, killer WhatsApp message for the owner of '{nome}'. Use the pain point: {dor}. Offer a quick AI-powered solution. Use emojis. Max 200 characters.\n{lang_inst_leads}"
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

            # Heuristic health score based on real signals
            _hs = 40
            if lead.get('telefone') and lead['telefone'] not in ('Pendente', ''): _hs += 20
            if lead.get('site') and lead['site'] not in ('Pendente', ''): _hs += 20
            if lead.get('nota') and lead['nota'] != 'N/A': _hs += 10
            enriched_leads.append({
                **lead,
                "dor": dor,
                "oportunidade": oportunidade,
                "pitch_script": pitch_script,
                "health_score": min(_hs, 99)
            })
        except Exception as e:
            print(f"Erro ao enriquecer lead {lead['nome']}: {e}")
            enriched_leads.append(lead)

    return enriched_leads if enriched_leads else leads


# ==========================================
# GERAÇÃO DE VÍDEO (Replicate & SiliconFlow Fallback)
# ==========================================
def traduzir_prompt_video(roteiro, produto, plataforma="Multicanal"):
    """Gera um production brief cinematográfico com direção de câmera, som, iluminação e continuity visual."""

    platform_config = {
        "TikTok": {
            "style": "UGC creator, handheld iPhone, raw authentic footage, fast-paced cuts, no cinematic lighting",
            "camera": "handheld, slight natural shake, eye-level, dynamic zooms, selfie-style openings",
            "pacing": "fast — hook in first 1.5 seconds, quick cuts, energetic transitions",
            "sound": "ambient room tone, natural voice, no studio sound, authentic environment audio",
            "reference": "Apple Shot on iPhone campaign, authentic creator style, raw emotional connection"
        },
        "Meta/Instagram": {
            "style": "High-end commercial aesthetic, polished, 4k, elegant composition, premium lighting",
            "camera": "cinematic tracking, smooth gimbal, controlled dolly, precise framing, macro product shots",
            "pacing": "medium — build tension slowly, reveal at 3-4s, emotional release at 7-8s",
            "sound": "cinematic sound design, emotional soundtrack, layered ambient audio, smooth transitions",
            "reference": "Apple mainline ads, Nike brand films, high-end performance marketing"
        },
        "Multicanal": {
            "style": "Premium commercial with authentic feel — hybrid of cinematic quality and human authenticity",
            "camera": "mixed: cinematic establishing shots + handheld emotional moments + macro product details",
            "pacing": "dynamic — start intimate, build to cinematic reveal, end with emotional resonance",
            "sound": "layered: ambient foundation, emotional music swell, clean dialogue space",
            "reference": "Porsche cinematic ads, Apple product films, premium lifestyle branding"
        }
    }

    cfg = platform_config.get(plataforma, platform_config["Multicanal"])

    prompt_ia = f"""You are Apple/Nike-level commercial director. Create a video production brief for AI video generation.

PRODUCT: {produto}
SCRIPT: {roteiro}
PLATFORM: {plataforma}

CRITICAL — MUST OBEY:
- BRAND CONTINUITY: Product must maintain EXACT same appearance, colors, proportions, and position in EVERY scene
- PHYSICS: NO floating objects, NO surreal motion, NO impossible physics, NO abstract visuals
- TEXT: NO fake logos, NO AI-generated text, NO distorted letters — video models cannot write text
- REALISM: Everything must feel like real-world filming — hands, faces, objects must look natural
- CONTINUITY: Each scene must connect logically to the next — emotional + visual continuity required

CINEMATIC DIRECTION — PER SCENE:
Each scene needs: camera angle, lighting, emotional tone, sound design

Scene 1 — Problem/Context:
  Camera: {cfg['camera']}
  Lighting: natural ambient, slightly underexposed for tension
  Emotional: curiosity + mild anxiety
  Sound: {cfg['sound']}
  Transition to Scene 2: slow reveal or quick cut depending on tension

Scene 2 — Product Reveal:
  Camera: macro close-up, slow cinematic reveal of product details
  Lighting: product-focused, clean commercial lighting, soft reflections
  Emotional: discovery + desire
  Sound: sound design emphasizes product texture/weight
  Transition to Scene 3: emotional music swell

Scene 3 — Solution/Transformation:
  Camera: wider shot showing person enjoying result, emotional capture
  Lighting: warm, aspirational, slightly overexposed for hope
  Emotional: relief + confidence + satisfaction
  Sound: emotional soundtrack peaks, ambient warmth
  Transition to Scene 4: slow visual dissolve

Scene 4 — Brand Moment:
  Camera: static, symmetrical, iconic composition
  Lighting: perfect commercial lighting, clean, bright
  Emotional: trust + desire to belong
  Sound: soundtrack resolves, clean ambient end

OVERALL DIRECTIVES:
- Style: {cfg['style']}
- Pacing: {cfg['pacing']}
- Reference: {cfg['reference']}
- Tone: emotionally intelligent, never corporate, never AI-sounding

OUTPUT: Return ONLY the enriched English video prompt — one continuous paragraph, detailed, cinematic, no markdown."""

    try:
        traduzido = chamar_ia(prompt_ia, system_message="You are an Apple/Nike-level commercial director and video prompt engineer. Return ONLY the production prompt. No yapping.")
        if traduzido and len(traduzido) > 10:
            return traduzido
    except:
        pass

    ref_style = cfg['style']
    return f"Premium commercial for {produto}. {ref_style}. {roteiro}. Scene continuity, product consistency, no text, no floating objects, cinematic realism."

VIDEO_NEGATIVE_PROMPT = "text, watermark, logo, letters, subtitles, low quality, blurry, static, distorted faces, distorted hands, floating objects, surreal, fantasy, abstract, impossible physics, fake branding, random objects, glitch, disfigured, ugly, bad anatomy, extra limbs"

def gerar_video_replicate(roteiro_completo, produto, plataforma="Multicanal"):
    """Gera um vídeo real usando Replicate (Wan 2.2 ou superior)"""
    if not REPLICATE_API_TOKEN:
        return None

    prompt_en = traduzir_prompt_video(roteiro_completo, produto, plataforma)
    
    print(f"[VID] gerando video Replicate: {prompt_en[:100]}...", flush=True)
    try:
        output = replicate.run(
            REPLICATE_VIDEO_MODEL,
            input={
                "prompt": prompt_en,
                "negative_prompt": VIDEO_NEGATIVE_PROMPT,
                "num_frames": 81,
                "aspect_ratio": "9:16" if "TikTok" in roteiro_completo or "Instagram" in roteiro_completo else "16:9",
                "sample_steps": 30,
            },
            timeout=180
        )
        video_url = str(output)
        if video_url.startswith("http"):
            print(f"[VID OK] Replicate: {video_url}", flush=True)
            return video_url
    except Exception as e:
        print(f"[VID ERR] Replicate: {e}", flush=True)
    return None

def gerar_video_siliconflow(roteiro_completo, produto, plataforma="Multicanal"):
    """Fallback: tenta gerar vídeo via SiliconFlow se disponível"""
    if not SILICONFLOW_API_KEY: return None
    
    prompt_en = traduzir_prompt_video(roteiro_completo, produto, plataforma)
    print(f"🎬 [IMG] tentando SiliconFlow Vídeo Fallback...", flush=True)
    
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
    # Atualmente a SiliconFlow prioriza modelos de imagem e chat. 
    # Vídeo será integrado via SDK oficial assim que o endpoint Pro estabilizar.
    return None

# ==========================================
# BRAND OVERLAY — pós-processamento de vídeo
# ==========================================

def apply_brand_overlay(video_url: str, product_name: str, headline: str = "", cta: str = "") -> Optional[str]:
    """Baixa o vídeo, aplica overlay de marca (logo + texto), e faz upload para Storage."""
    if not video_url or not video_url.startswith("http"):
        return video_url

    temp_dir = os.path.join(os.path.dirname(__file__), "static", "temp")
    os.makedirs(temp_dir, exist_ok=True)

    input_path = os.path.join(temp_dir, f"input_{uuid.uuid4().hex}.mp4")
    output_path = os.path.join(temp_dir, f"branded_{uuid.uuid4().hex}.mp4")

    try:
        # 1. Download video
        resp = requests.get(video_url, timeout=60, stream=True)
        if resp.status_code != 200:
            return video_url
        with open(input_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # 2. Apply FFmpeg overlay (product name bottom-left, headline top-center, CTA bottom-right)
        safe_product = product_name.replace("'", "'\\\\''")[:40]
        safe_headline = headline.replace("'", "'\\\\''")[:60]
        safe_cta = cta.replace("'", "'\\\\''")[:30]

        # Cross-platform font path detection
        font_path = "C\\:/Windows/Fonts/arial.ttf" if os.name == "nt" else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_path_fallback = os.path.join(os.path.dirname(__file__), "static", "fonts", "Inter-Regular.ttf")
        if os.path.exists(font_path_fallback.replace("\\", "/")):
            font_path = font_path_fallback.replace("\\", "/")

        drawtext_filters = []
        if safe_headline:
            drawtext_filters.append(
                f"drawtext=text='{safe_headline}':fontcolor=white:fontsize=28:"
                f"x=(w-text_w)/2:y=40:box=1:boxcolor=black@0.4:boxborderw=8:fontfile='{font_path}'"
            )
        if safe_product:
            drawtext_filters.append(
                f"drawtext=text='{safe_product}':fontcolor=white:fontsize=22:"
                f"x=20:y=h-text_h-20:box=1:boxcolor=black@0.4:boxborderw=6:fontfile='{font_path}'"
            )
        if safe_cta:
            drawtext_filters.append(
                f"drawtext=text='{safe_cta}':fontcolor=white:fontsize=24:"
                f"x=w-text_w-20:y=h-text_h-20:box=1:boxcolor=black@0.4:boxborderw=6:fontfile='{font_path}'"
            )

        if not drawtext_filters:
            return video_url

        filter_complex = ",".join(drawtext_filters)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", filter_complex,
            "-c:a", "copy",
            "-preset", "ultrafast",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[BRAND OVERLAY] FFmpeg falhou: {result.stderr[:200]}", flush=True)
            return video_url

        # 3. Upload to Supabase Storage
        filename = f"branded_{uuid.uuid4().hex}.mp4"
        public_url = upload_to_storage(output_path, filename)
        if public_url:
            print(f"[BRAND OVERLAY] OK: {public_url}", flush=True)
            return public_url

        return video_url

    except Exception as e:
        print(f"[BRAND OVERLAY] Erro (graceful): {e}", flush=True)
        return video_url
    finally:
        # Cleanup temp files
        for p in [input_path, output_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


def gerar_video_com_fallback(roteiro_completo, produto, plataforma="Multicanal"):
    """Prioriza Replicate e usa SiliconFlow como fallback"""
    # 0. Check asset cache first
    cached = _check_asset_cache(produto, roteiro_completo)
    if cached:
        return cached

    ok, reason = _check_and_consume_cost_guard("video_gen")
    if not ok:
        print(f"⚠️ Geração de vídeo bloqueada por custo: {reason}", flush=True)
        return None

    # 1. Tenta Replicate
    url = gerar_video_replicate(roteiro_completo, produto, plataforma)
    if url:
        _set_asset_cache(produto, roteiro_completo, url)
        return url
    
    # 2. Tenta SiliconFlow (Fallback)
    url = gerar_video_siliconflow(roteiro_completo, produto, plataforma)
    if url:
        _set_asset_cache(produto, roteiro_completo, url)
        return url
    
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
    Retorna o cliente Supabase com o token do usuário autenticado (RLS).
    NUNCA retorna o admin client por padrão — apenas com token explícito.
    """
    if not req:
        return None

    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            user_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            user_client.postgrest.auth(token)
            return user_client
        except Exception as e:
            logger.error("get_db() failed for token %s...: %s", str(token)[:12], e)
    
    return None

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
def _detect_lang(text: str) -> str:
    """Detect if text is primarily Portuguese or English using stopword overlap."""
    if not text or not text.strip():
        return "pt"
    text_lower = text.lower()
    pt_words = {"para", "como", "mais", "uma", "com", "das", "dos", "muito", "por", "sobre", "entre", "também", "porque", "você", "são", "seus", "suas", "pode", "mas", "ainda", "assim", "depois", "sempre", "tudo", "vai", "fazer", "tem", "era", "foram", "ser", "está", "muito", "bem", "cada", "eles", "elas", "esse", "essa", "isso", "aquele", "através", "então", "quando", "onde"}
    en_words = {"the", "and", "for", "with", "that", "this", "from", "your", "will", "have", "more", "about", "also", "than", "their", "what", "would", "make", "which", "think", "they", "them", "some", "could", "there", "been", "other", "into", "here", "then", "just", "well", "very", "much", "each", "those", "these", "should", "through", "while", "because", "when", "where"}
    words = set(text_lower.split())
    pt_score = len(words & pt_words)
    en_score = len(words & en_words)
    return "pt" if pt_score >= en_score else "en"

def _lang_instruction(lang: str) -> str:
    if lang == "en":
        return "Respond in fluent American English."
    return "Responda em português do Brasil."

def chamar_ia(prompt, system_message="Você é um assistente de marketing especialista.", modelo_forcado=None, modelos_override=None):
    """
    Motor de IA com Redundância (Cascata de Fallback).
    Se modelos_override for fornecido, usa essa lista (mantendo fallback entre eles).
    Se modelo_forcado for fornecido, usa APENAS esse modelo (sem fallback).
    Caso contrário, usa a lista padrão: Llama 3 → GPT-4o-Mini → Gemini Flash.
    """
    if not OPENROUTER_API_KEY:
        return f"[Simulação IA]: {prompt[:40]}..."

    ok, reason = _check_and_consume_cost_guard("ia_call")
    if not ok:
        return f"Erro de limite: {reason}"

    if modelos_override:
        modelos = modelos_override
    elif modelo_forcado:
        modelos = [modelo_forcado]
    else:
        modelos = [
            OPENROUTER_MODEL,
            "openai/gpt-4o-mini",
            "google/gemini-2.0-flash-001"
        ]

    for model in modelos:
        if not model: continue
        print(f"[AI] tentando modelo {model}...", flush=True)
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://mktpilot.io",
            "X-Title": "MKTPilot Pro",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"{system_message}\n\nSTRICT: Return ONLY the raw data requested. No conversational filler."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if response.status_code != 200:
                print(f"[WARN] modelo {model} falhou ({response.status_code}). Tentando próximo...", flush=True)
                continue
                
            data = response.json()
            if data and 'choices' in data and len(data['choices']) > 0:
                finish = data['choices'][0].get('finish_reason', '')
                if finish == 'length':
                    print(f"[WARN] modelo {model} truncou output. Tentando próximo...", flush=True)
                    continue
                content = data['choices'][0].get('message', {}).get('content')
                if content and len(content.strip()) > 10:
                    print(f"[OK] sucesso com {model}", flush=True)
                    return content
            
            print(f"[WARN] resposta invalida de {model}. Tentando próximo...", flush=True)
        except Exception as e:
            print(f"[ERR] conexao com {model}: {e}. Tentando próximo...", flush=True)
            continue

    return "Erro Crítico: Todos os modelos de IA falharam. Por favor, verifique sua conexão ou API Key."

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
@limiter.limit("12 per minute")
def register():
    dados, err = get_json_payload(required_fields=["email", "password"])
    if err: return err
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
@limiter.limit("12 per minute")
def login():
    dados, err = get_json_payload(required_fields=["email", "password"])
    if err: return err
    email = dados.get("email")
    senha = dados.get("password")

    if not supabase: return jsonify({"erro": "Supabase não configurado."}), 500

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
        if res.session:
            return jsonify({"user": res.user.email, "token": res.session.access_token}), 200
        else:
            return jsonify({"erro": "E-mail não confirmado."}), 400
    except Exception as e:
        return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    user = get_user_from_request(request)
    if not user:
        return jsonify({"erro": "Não autorizado"}), 401
    return jsonify({"email": user.email, "id": user.id}), 200

# ==========================================
# GESTOR DE JOBS EM SEGUNDO PLANO
# ==========================================
def process_campaign_job(job_id, user_id, dados):
    """Processa a geração completa da campanha em background."""
    print(f"[JOB START] job_id={job_id} user_id={user_id}", flush=True)
    
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
        # Push SSE events
        _ensure_sse_queue(job_id)
        if status == "completed":
            _push_sse_event(job_id, "completed", {"progress": 100, "current_step": "Concluido!", "result": result or {}})
            _cleanup_sse_queue(job_id)
        elif status == "failed":
            _push_sse_event(job_id, "failed", {"error": error or "Erro desconhecido"})
            _cleanup_sse_queue(job_id)
        else:
            _push_sse_event(job_id, "progress", {
                "progress": progress or 0,
                "current_step": step or "Processando...",
                "status": status or "processing",
            })

    ctx_user = _cost_guard_user_id.set(str(user_id))
    ctx_db = _cost_guard_db.set(db)

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

        # 2. Brand Memory — carrega memória existente da marca
        brand_memory = _load_brand_memory(db, user_id, produto)
        if brand_memory:
            logger.info("Brand memory loaded for %s — injecting context", produto[:40])
            contexto_spy += f"\n\nBRAND MEMORY (campanhas anteriores):\n{json.dumps(brand_memory, ensure_ascii=False)[:2000]}"

        # 2. Geração de Copy (IA) - PIPELINE V2 (Stages 1-4)
        update_job(progress=25, step="Analisando mercado e ICP...")

        def usage_hook(stage_name, usage, estimated_cost):
            try:
                logger.info(
                    "pipeline_v2 usage stage=%s prompt_tokens=%s completion_tokens=%s est_cost=%.6f",
                    stage_name,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    estimated_cost,
                )
            except Exception:
                pass

        campaign_data = None
        engine_meta = {
            "engine": "legacy",
            "pipeline_v2_attempted": False,
            "pipeline_v2_succeeded": False,
            "fallback_reason": None,
            "stages_completed": 0,
            "models_used": [],
            "total_estimated_cost_usd": 0.0,
            "total_duration_ms": 0,
            "stage_failures": [],
        }
        if PIPELINE_V2_ENABLED and PIPELINE_V2 and hasattr(PIPELINE_V2, "run_pipeline_v2"):
            engine_meta["pipeline_v2_attempted"] = True
            try:
                # Pipeline V2 com progresso granular por estágio
                # Stage 1: Market Analysis
                update_job(progress=8, step="Analisando inteligência de mercado...")
                market, stage_meta_market = PIPELINE_V2.run_market_analysis(produto, nicho, objetivo, publico_alvo, contexto_spy, usage_hook=usage_hook)
                update_job(progress=15, step="Segmentação de mercado concluída")
                
                # Stage 2: ICP Mapping
                update_job(progress=18, step="Mapeando perfil psicológico do público...")
                icp, stage_meta_icp = PIPELINE_V2.run_icp_mapping(produto, market, usage_hook=usage_hook)
                update_job(progress=25, step="Perfis de ICP finalizados")
                
                # Stage 3: Creative Strategy
                update_job(progress=28, step="Desenvolvendo estratégia criativa...")
                strategy, stage_meta_strategy = PIPELINE_V2.run_creative_strategy(produto, objetivo, market, icp, usage_hook=usage_hook)
                update_job(progress=33, step="Big Idea e estratégia definidas")

                # Stage 3.5: Narrative Coherence Memory
                update_job(progress=36, step="Gerando memória narrativa central...")
                coherence = None
                try:
                    coherence = PIPELINE_V2.generate_coherence_memory(produto, market, strategy, icp)
                except Exception:
                    pass
                update_job(progress=40, step="Memória narrativa estabelecida")
                
                # Stage 4: Hook Generation
                update_job(progress=42, step="Gerando hooks de alto impacto...")
                hooks, stage_meta_hooks = PIPELINE_V2.run_hook_generation(strategy, market, icp, usage_hook=usage_hook)
                update_job(progress=50, step="Hooks e headlines prontos")
                
                # Stage 5: Campaign Builder
                update_job(progress=52, step="Construindo campanha completa...")
                campaign, stage_meta_campaign = PIPELINE_V2._build_legacy_campaign_payload(
                    product=produto, niche=nicho, goal=objetivo, audience=publico_alvo,
                    tone=tom_de_voz, strategy=strategy, hooks=hooks, market=market, icp=icp,
                    coherence=coherence, usage_hook=usage_hook
                )
                update_job(progress=55, step="Campanha estruturada")
                
                campaign_data = campaign.model_dump()
                si = {
                    "market_analysis": market.model_dump(),
                    "icp_mapping": icp.model_dump(),
                    "creative_strategy": strategy.model_dump(),
                    "stage_meta": [stage_meta_market.model_dump(), stage_meta_icp.model_dump(), stage_meta_strategy.model_dump(), stage_meta_hooks.model_dump(), stage_meta_campaign.model_dump()],
                }
                if coherence:
                    try:
                        si["coherence_memory"] = coherence.model_dump()
                    except Exception:
                        pass
                campaign_data["strategy_insights"] = si
                campaign_data["hooks_lab"] = hooks.model_dump()
                engine_meta["engine"] = "pipeline_v2"
                engine_meta["pipeline_v2_succeeded"] = True
                engine_meta["stages_completed"] = 5
                engine_meta["models_used"] = [stage_meta_market.model_used, stage_meta_icp.model_used, stage_meta_strategy.model_used, stage_meta_hooks.model_used, stage_meta_campaign.model_used]
                engine_meta["total_estimated_cost_usd"] = round(
                    sum(s.estimated_cost_usd for s in [stage_meta_market, stage_meta_icp, stage_meta_strategy, stage_meta_hooks, stage_meta_campaign]), 6
                )
                engine_meta["total_duration_ms"] = sum(s.duration_ms for s in [stage_meta_market, stage_meta_icp, stage_meta_strategy, stage_meta_hooks, stage_meta_campaign])
            except Exception as pipeline_error:
                engine_meta["fallback_reason"] = str(pipeline_error)[:240]
                print(
                    json.dumps(
                        {
                            "service": "pipeline_v2",
                            "event": "pipeline_fallback_to_legacy",
                            "error": str(pipeline_error)[:240],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

        # Fallback legado para continuidade de negócio
        if not campaign_data:
            if not engine_meta["fallback_reason"]:
                if not PIPELINE_V2_ENABLED:
                    engine_meta["fallback_reason"] = "pipeline_v2_disabled"
                elif not PIPELINE_V2:
                    engine_meta["fallback_reason"] = "pipeline_v2_module_not_loaded"
                else:
                    engine_meta["fallback_reason"] = "pipeline_v2_unknown"
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
            prompt = f"""Crie uma campanha de marketing completa para "{produto}".
Nicho: {nicho}. Objetivo: {objetivo}.{contexto_spy}
Público: {publico_alvo}. Tom: {tom_de_voz}.

REGRAS:
- Gere 3 variações de Meta Ads.
- Gere 2 posts Instagram.
- Gere 1 script de vídeo e 2 e-mails.

RETORNE APENAS JSON:
{json.dumps(schema, indent=2)}"""
            system_msg = "Você é o motor de IA do MKTPilot Pro. Retorne APENAS JSON puro. Nenhum texto fora do JSON. Nenhum markdown. Nenhum ```json."
            resposta_bruta = chamar_ia(prompt, system_message=system_msg)
            t = (resposta_bruta or "").strip()
            t = re.sub(r'```json\s*', '', t, flags=re.IGNORECASE)
            t = re.sub(r'```\s*', '', t)
            # Remove trailing commas e comentarios (repair global)
            t = re.sub(r',\s*([\]}])', r'\1', t)
            t = re.sub(r'//.*?\n', '\n', t)
            # Extrai JSON balanceado — tolera texto antes/depois e múltiplos blocos
            campaign_data = None
            depth = 0
            start_idx = -1
            for i, ch in enumerate(t):
                if ch == "{":
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        candidate = t[start_idx : i + 1]
                        try:
                            campaign_data = json.loads(candidate)
                            break
                        except json.JSONDecodeError:
                            start_idx = -1
            if not campaign_data:
                print(f"[LEGACY RAW] {(resposta_bruta or '')[:1500]}", flush=True)
                raise Exception("Falha de parse na geração legada — JSON inválido")

        # 2.5. Refinement Layer — polimento criativo da copy
        if CAMPAIGN_REFINEMENT_ENABLED and PIPELINE_V2 and hasattr(PIPELINE_V2, "refine_campaign"):
            update_job(progress=62, step="Refinando copy com IA criativa...")
            try:
                refined = PIPELINE_V2.refine_campaign(campaign_data, produto, nicho, objetivo, publico_alvo)
                if refined and isinstance(refined, dict):
                    campaign_data = refined
            except Exception as refine_err:
                print(f"[REFINE WARN] {refine_err}", flush=True)

        update_job(progress=66, step="Iniciando geração de criativos visuais...")

        # Extract coherence memory for visual/style guidance
        _viz_prompt = ""
        _coherence_visual = ""
        try:
            si = campaign_data.get("strategy_insights", {}) or {}
            cm = si.get("coherence_memory", {}) or {}
            if cm:
                _viz_prompt = f"Visual direction: {cm.get('visual_identity', '')}. "
                _coherence_visual = cm.get('visual_identity', '')
        except Exception:
            pass

        # 3. Geração de Imagens
        if "instagram_posts" in campaign_data:
            update_job(progress=70, step="Renderizando imagens IA...")
            for idx, post in enumerate(campaign_data["instagram_posts"]):
                if idx >= MAX_IMAGES: break
                enhanced_caption = (_viz_prompt + post.get("caption", ""))[:300]
                post["image_url"] = gerar_imagem_com_fallback(enhanced_caption, produto)
            update_job(progress=78, step="Imagens concluídas")

        # 4. Geração de Vídeo e Áudio
        if "video_script" in campaign_data:
            update_job(progress=82, step="Produzindo vídeo IA...")
            vs = campaign_data["video_script"]
            roteiro = f"{vs.get('hook')}. {vs.get('body')}. {vs.get('cta')}"
            if _coherence_visual:
                roteiro = f"[Visual Direction: {_coherence_visual}] {roteiro}"

            # Vídeo
            v_url = gerar_video_com_fallback(roteiro, produto, plataforma)
            if v_url:
                vs["video_url"] = v_url
                # Brand overlay: extrai headline e CTA do facebook_ad
                _headline_overlay = ""
                _cta_overlay = ""
                try:
                    _fb = campaign_data.get("facebook_ad") or {}
                    _headline_overlay = _fb.get("headline_a") or _fb.get("headline") or ""
                    _cta_overlay = _fb.get("cta") or ""
                except Exception:
                    pass
                branded_url = apply_brand_overlay(v_url, produto, _headline_overlay, _cta_overlay)
                if branded_url and branded_url != v_url:
                    vs["video_url"] = branded_url
                    vs["branded"] = True
            else: vs["image_url"] = gerar_imagem_com_fallback(vs.get("hook", ""), produto)
            update_job(progress=88, step="Vídeo renderizado")

            # Áudio
            a_url = gerar_audio_tts(roteiro, produto)
            if a_url: vs["audio_url"] = a_url

        # 5. Persistência Final
        update_job(progress=94, step="Finalizando e salvando campanha...")

        # Anexa metadados de engine ao payload final (visível ao frontend)
        campaign_data["_engine_meta"] = engine_meta

        insert_res = db.table("campaigns").insert({
            "user_id": user_id,
            "product": produto,
            "goal": objetivo,
            "result_text": json.dumps(campaign_data, ensure_ascii=False)
        }).execute()
        
        camp_id = None
        if insert_res and hasattr(insert_res, 'data') and insert_res.data and len(insert_res.data) > 0:
            camp_id = insert_res.data[0].get('id')
        
        # Salvar brand memory para campanhas futuras
        try:
            si = campaign_data.get("strategy_insights") or {}
            coherence = si.get("coherence_memory") or {}
            if coherence or si.get("market_analysis"):
                _save_brand_memory(db, user_id, produto, {
                    "coherence_memory": coherence,
                    "market_analysis": si.get("market_analysis"),
                    "creative_strategy": si.get("creative_strategy"),
                    "last_campaign_id": camp_id,
                    "last_generated_at": datetime.utcnow().isoformat(),
                })
        except Exception:
            pass
        
        # Concluir Job
        update_job(status="completed", progress=100, step="Concluído!", result={"campaign_id": camp_id, "data": campaign_data})
        print(f"[JOB OK] {job_id} concluído com sucesso!", flush=True)

    except Exception as e:
        print(f"[JOB ERR] {job_id}: {e}", flush=True)
        update_job(status="failed", error=str(e), step="Erro no processamento")
    finally:
        _cost_guard_user_id.reset(ctx_user)
        _cost_guard_db.reset(ctx_db)

# ==========================================
# ROTAS DO SAAS (Protegidas)
# ==========================================
@app.route('/api/copilot/gerar', methods=['POST'])
@limiter.limit("6 per hour; 2 per minute")
def api_copilot_gerar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401

    dados, err = get_json_payload()
    if err: return err
    
    # 1. Cria o registro do Job no banco
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/copilot/gerar — auth token invalido ou expirado")
            return jsonify({"erro": "authentication required"}), 401
        job_res = db.table("background_jobs").insert({
            "user_id": user.id,
            "status": "pending",
            "payload": dados,
            "current_step": "Aguardando fila..."
        }).execute()
        
        if not job_res.data:
            return jsonify({"erro": "Falha ao criar tarefa no servidor"}), 500
            
        job_id = job_res.data[0]['id']
        _ensure_sse_queue(job_id)
        
        # 2. Processamento seguro (thread opcional; fallback síncrono)
        if BACKGROUND_THREADS_ENABLED:
            thread = threading.Thread(target=process_campaign_job, args=(job_id, user.id, dados), daemon=True)
            thread.start()
        else:
            process_campaign_job(job_id, user.id, dados)
        
        return jsonify({"job_id": job_id, "mensagem": "Tarefa iniciada"}), 202
        
    except Exception as e:
        return jsonify({"erro": f"Erro ao iniciar processamento: {str(e)}"}), 500

@app.route('/api/copilot/status/<job_id>', methods=['GET'])
def api_copilot_status(job_id):
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/copilot/status — auth token invalido ou expirado")
            return jsonify({"erro": "authentication required"}), 401
        res = db.table("background_jobs").select("*").eq("id", job_id).eq("user_id", user.id).limit(1).execute()
        
        if not res.data:
            return jsonify({"erro": "Tarefa não encontrada"}), 404
            
        return jsonify(res.data[0]), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/copilot/jobs/active', methods=['GET'])
def api_copilot_jobs_active():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/copilot/jobs/active — auth token invalido ou expirado")
            return jsonify({"erro": "authentication required"}), 401
        # Reap zombie jobs (>15 min in processing/pending)
        cutoff = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        try:
            db.table("background_jobs").update({"status": "failed", "error": "timeout — zombie job reclaimed"}).eq("user_id", user.id).in_("status", ["pending", "processing"]).lt("created_at", cutoff).execute()
        except Exception:
            pass
        res = db.table("background_jobs").select("id, status, progress, current_step, created_at").eq("user_id", user.id).in_("status", ["pending", "processing"]).order("created_at", desc=True).execute()
        return jsonify({"jobs": res.data}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/copilot/stream/<job_id>', methods=['GET'])
def api_copilot_stream(job_id):
    """SSE endpoint for real-time job progress streaming."""
    user = get_user_from_request(request)
    if not user:
        return jsonify({"erro": "Não autorizado"}), 401

    def generate():
        _ensure_sse_queue(job_id)
        yield f"event: connected\ndata: {json.dumps({'job_id': job_id})}\n\n"
        last_activity = time.time()
        while True:
            try:
                events = _drain_sse_events(job_id)
                if events:
                    for ev in events:
                        yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
                        last_activity = time.time()
                        if ev['event'] in ('completed', 'failed'):
                            return
                else:
                    if time.time() - last_activity > 15:
                        yield f": heartbeat {time.time()}\n\n"
                        last_activity = time.time()
                    time.sleep(0.5)
            except GeneratorExit:
                break
            except Exception:
                break

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "supabase": supabase is not None,
        "openrouter": OPENROUTER_API_KEY is not None,
        "replicate": REPLICATE_API_TOKEN is not None,
        "timestamp": datetime.utcnow().isoformat(),
    })

@app.route('/api/copilot/jobs/list', methods=['GET'])
def api_copilot_jobs_list():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/copilot/jobs/list")
            return jsonify({"erro": "authentication required"}), 401
        res = db.table("background_jobs").select("id, status, progress, current_step, created_at, error").eq("user_id", user.id).order("created_at", desc=True).limit(5).execute()
        return jsonify({"jobs": res.data}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/campaigns/update', methods=['POST'])
@limiter.limit("60 per hour")
def api_campaigns_update():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados, err = get_json_payload(required_fields=["id", "result_text"])
    if err: return err
    campanha_id = dados.get('id')
    novos_dados = dados.get('result_text') # Objeto JSON completo
    
    if not campanha_id or not novos_dados:
        return jsonify({"erro": "Dados incompletos"}), 400
        
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/campaigns/update")
            return jsonify({"erro": "authentication required"}), 401
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
        if not db:
            logger.error("DB is None in /api/campanhas/historico")
            return jsonify({"erro": "authentication required"}), 401
        res = db.table("campaigns").select("*").eq("user_id", user.id).order("created_at", desc=True).execute()
        return jsonify({"campanhas": res.data}), 200
    except Exception as e:
        return jsonify({"erro": "Falha ao buscar campanhas"}), 500

@app.route('/api/campanhas/otimizar', methods=['POST'])
@limiter.limit("20 per hour")
def api_campanhas_otimizar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401

    dados, err = get_json_payload()
    if err: return err
    relatorio_manual = dados.get('relatorio', '')
    auto_mode = dados.get('auto', False)
    
    # Modo automático: busca campanhas do banco
    historico_texto = ""
    if auto_mode:
        try:
            db = get_db(request)
            if not db:
                logger.error("DB is None in /api/campanhas/otimizar")
                return jsonify({"erro": "authentication required"}), 401
            res = db.table("campaigns").select("product, goal, result_text, created_at").eq("user_id", user.id).order("created_at", desc=True).limit(10).execute()
            if res.data:
                for i, camp in enumerate(res.data):
                    historico_texto += f"\n--- Campanha {i+1} ({camp.get('created_at','')[:10]}) ---\n"
                    historico_texto += f"Produto: {camp.get('product','')}\n"
                    historico_texto += f"Objetivo: {camp.get('goal','')}\n"
                    raw = camp.get('result_text', '')
                    if isinstance(raw, str):
                        import json as _json
                        try:
                            parsed = _json.loads(raw)
                            fb = parsed.get("facebook_ad") or {}
                            si = parsed.get("strategy_insights") or {}
                            hooks = parsed.get("hooks_lab") or {}
                            video = parsed.get("video_script") or {}
                            historico_texto += f"Headlines: {fb.get('headline_a','')} | {fb.get('headline_b','')} | {fb.get('headline_c','')}\n"
                            historico_texto += f"Textos: {fb.get('primary_text_a','')} | {fb.get('primary_text_b','')}\n"
                            historico_texto += f"CTA: {fb.get('cta','')}\n"
                            historico_texto += f"Big Idea: {si.get('big_idea','')[:200]}\n"
                            historico_texto += f"Ângulo: {si.get('chosen_angle','')[:200]}\n"
                            if hooks.get("hooks"):
                                for h in hooks["hooks"][:3]:
                                    historico_texto += f"Hook: {h.get('text','')[:150]}\n"
                            historico_texto += f"Video Hook: {video.get('hook','')[:150]}\n"
                            historico_texto += f"Video Body: {video.get('body','')[:200]}\n"
                        except (_json.JSONDecodeError, Exception):
                            historico_texto += f"Copy bruta: {raw[:1000]}\n"
                    else:
                        historico_texto += f"Copy bruta: {str(raw)[:1000]}\n"
                print(f"Eva Brain: Analisando {len(res.data)} campanhas do banco", flush=True)
            else:
                return jsonify({"resultado": "⚠️ Nenhuma campanha encontrada no seu histórico. Gere campanhas primeiro na aba 'Nova Campanha'."}), 200
        except Exception as e:
            print(f"Erro ao buscar histórico: {e}", flush=True)
            return jsonify({"erro": "Falha ao buscar campanhas do banco."}), 500

    conteudo = sanitize_input(relatorio_manual) or historico_texto
    if not conteudo.strip():
        return jsonify({"erro": "Cole dados de campanha ou clique em 'Análise Automática' para usar o histórico do banco."}), 400

    lang = _detect_lang(conteudo)
    lang_instruction = _lang_instruction(lang)
    lang_labels = {"en": {"analysis": "Copy Quality Diagnosis", "strengths": "What's Working", "weaknesses": "Copy Problems", "ab_tests": "A/B Tests Suggested", "positioning": "Positioning Recommendations", "coherence": "Coherence Analysis", "prompt_title": "copy quality and positioning", "prompt_detail": "Point out exact excerpts and suggest concrete rewrites."},
                   "pt": {"analysis": "Diagnóstico de Copy", "strengths": "Pontos Fortes", "weaknesses": "Problemas de Copy", "ab_tests": "Testes A/B Sugeridos", "positioning": "Recomendações de Positioning", "coherence": "Análise de Coerência", "prompt_title": "copywriting e positioning", "prompt_detail": "aponte trechos exatos e sugira rewrites concretos."}}
    l = lang_labels.get(lang, lang_labels["pt"])

    system_message = f"""Você é um Analista Sênior de Copywriting e Positioning — 15 anos de experiência em Meta Ads e TikTok Ads.

ATENÇÃO: VOCÊ NÃO TEM ACESSO A DADOS DE PERFORMANCE (CTR, CPC, ROAS, impressões, conversões). Os dados abaixo são APENAS as copies criativas das campanhas. Sua análise deve se limitar ao que está presente:

1. 📊 {l["analysis"]} — Qualidade dos headlines, textos, hooks e CTA
2. ✅ {l["strengths"]} — O que está bem escrito, que mecanismos de persuasão foram usados
3. ❌ {l["weaknesses"]} — Headlines fracas, CTAs genéricas, falta de especificidade, tom inconsistente
4. 🧪 {l["ab_tests"]} — Mínimo 3 variações de copy concretas
5. 💡 {l["positioning"]} — Sugestões de ângulo, promessa e mecanismo único
6. 📝 {l["coherence"]} — As copies contam a mesma história? O gancho do vídeo conecta com o headline?

NÃO invente métricas de performance. NÃO dê previsão de ROAS. Foque exclusivamente no que está escrito.

{lang_instruction} Use markdown com negrito, listas e emojis."""

    prompt = f"""Analise a qualidade das copies criativas abaixo e forneça um relatório de otimização focado em {l["prompt_title"]}:

{conteudo}

Seja específico: {l["prompt_detail"]}"""

    modelos = [OPENROUTER_ANALYSIS_MODEL, "openai/gpt-4o-mini", "google/gemini-2.0-flash-001"]
    resultado = chamar_ia(prompt, system_message=system_message, modelo_forcado=None, modelos_override=modelos)
    
    return jsonify({"resultado": resultado}), 200

# =====================================================
# ROTAS META ADS (AUTH & PUBLISH) — MULTIUSUÁRIO
# =====================================================

@app.route('/api/oauth/meta/url', methods=['GET'])
@limiter.limit("30 per hour")
def api_oauth_meta_url():
    user = get_user_from_request(request)
    if not user:
        return jsonify({"erro": "Não autorizado"}), 401
    if not META_APP_ID:
        return jsonify({"erro": "META_APP_ID não configurado"}), 400

    scope = "ads_management,ads_read,business_management,pages_manage_posts,pages_read_engagement"
    state = build_oauth_state(user.id, "meta")
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={META_APP_ID}&redirect_uri={META_REDIRECT_URI}&scope={scope}&state={state}"
    return jsonify({"auth_url": auth_url}), 200

@app.route('/auth/meta/login')
def meta_login():
    if not META_APP_ID: return "META_APP_ID não configurado no .env", 400
    scope = "ads_management,ads_read,business_management,pages_manage_posts,pages_read_engagement"

    # Compatibilidade: aceita token query legado, mas nunca repassa JWT em state
    user = get_user_from_request(request)
    if not user:
        user_token = request.args.get('token', '')
        if user_token:
            user = get_user_from_token(user_token)
    if not user:
        return "Não autenticado", 401

    state = build_oauth_state(user.id, "meta")
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
    account_name = accounts_data[0]['name'] if accounts_data else ''
    
    # Identificar o usuário via state assinado
    state_payload = parse_oauth_state(request.args.get('state', ''), "meta")
    user_id = state_payload.get("u") if state_payload else None
    
    # Salvar token no banco (por usuário)
    try:
        db = get_db(request)
        if db and ad_account_id and user_id:
            db.table("user_meta_tokens").upsert({
                "user_id": str(user_id),
                "access_token": access_token,
                "ad_account_id": ad_account_id,
                "account_name": account_name
            }, on_conflict="user_id").execute()
            print(f"✅ Token Meta salvo para user {user_id} → {account_name} ({ad_account_id})", flush=True)
        elif not user_id:
            print("⚠️ OAuth Meta: usuário não identificado (state vazio)", flush=True)
    except Exception as e:
        print(f"⚠️ Erro ao salvar token Meta: {e}", flush=True)
    
    return f"""<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>MKTPilot — Meta Conectado</title><style>body{{background:#0a0c15;color:#fff;font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;}}.card{{background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(139,92,246,0.05));border:1px solid rgba(99,102,241,0.2);border-radius:24px;padding:48px;max-width:460px;text-align:center;}}.icon{{width:64px;height:64px;background:#10b981;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 24px;font-size:32px;}}h1{{color:#10b981;font-size:1.6rem;margin:0 0 12px;}}p{{color:rgba(255,255,255,0.6);line-height:1.6;margin:0 0 8px;}}.account{{background:rgba(255,255,255,0.05);border-radius:12px;padding:12px 16px;margin:20px 0;font-size:0.9rem;color:rgba(255,255,255,0.8);}}.btn{{display:inline-block;margin-top:24px;padding:12px 32px;background:var(--accent-primary,#8b5cf6);color:#fff;text-decoration:none;border-radius:12px;font-weight:600;transition:0.15s;}}.btn:hover{{background:#7c3aed;}}</style></head><body><div class="card"><div class="icon">✓</div><h1>Meta Ads Conectado!</h1><p>Sua conta foi vinculada ao MKTPilot com sucesso.</p><div class="account">📢 Conta: <strong>{ad_account_id or "N/D"}</strong></div><p style="font-size:0.85rem;">Agora você pode publicar campanhas diretamente do Copiloto para o Gerenciador de Anúncios Meta.</p><a href="/" class="btn">← Voltar ao MKTPilot</a></div></body></html>"""

@app.route('/api/campaigns/publish_to_meta', methods=['POST'])
@limiter.limit("20 per hour")
def api_publish_to_meta():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Buscar token do usuário no banco
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/campaigns/publish_to_meta")
            return jsonify({"erro": "authentication required"}), 401
        res = db.table("user_meta_tokens").select("*").eq("user_id", user.id).limit(1).execute()
        if not res.data or not res.data[0]:
            return jsonify({"erro": "Conecte sua conta Meta primeiro! Clique em 'Conectar Meta Ads' no menu."}), 400
        
        token = res.data[0]['access_token']
        ad_account = res.data[0]['ad_account_id']
        
        # Dados da campanha
        dados, err = get_json_payload()
        if err: return err
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

@app.route('/api/oauth/tiktok/url', methods=['GET'])
@limiter.limit("30 per hour")
def api_oauth_tiktok_url():
    user = get_user_from_request(request)
    if not user:
        return jsonify({"erro": "Não autorizado"}), 401
    if not TIKTOK_APP_ID:
        return jsonify({"erro": "TIKTOK_APP_ID não configurado"}), 400

    state = build_oauth_state(user.id, "tiktok")
    auth_url = (
        f"https://business-api.tiktok.com/portal/auth?"
        f"app_id={TIKTOK_APP_ID}"
        f"&redirect_uri={TIKTOK_REDIRECT_URI}"
        f"&state={state}"
    )
    return jsonify({"auth_url": auth_url}), 200

@app.route('/auth/tiktok/login')
def tiktok_login():
    if not TIKTOK_APP_ID: return "TIKTOK_APP_ID não configurado no .env", 400
    user = get_user_from_request(request)
    if not user:
        user_token = request.args.get('token', '')
        if user_token:
            user = get_user_from_token(user_token)
    if not user:
        return "Não autenticado", 401

    state = build_oauth_state(user.id, "tiktok")
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
    
    # Identificar o usuário via state assinado
    state_payload = parse_oauth_state(request.args.get('state', ''), "tiktok")
    user_id = state_payload.get("u") if state_payload else None
    
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
    
    return f"""<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>MKTPilot — TikTok Conectado</title><style>body{{background:#0a0c15;color:#fff;font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;}}.card{{background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(139,92,246,0.05));border:1px solid rgba(99,102,241,0.2);border-radius:24px;padding:48px;max-width:460px;text-align:center;}}.icon{{width:64px;height:64px;background:#10b981;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 24px;font-size:32px;}}h1{{color:#10b981;font-size:1.6rem;margin:0 0 12px;}}p{{color:rgba(255,255,255,0.6);line-height:1.6;margin:0 0 8px;}}.account{{background:rgba(255,255,255,0.05);border-radius:12px;padding:12px 16px;margin:20px 0;font-size:0.9rem;color:rgba(255,255,255,0.8);}}.btn{{display:inline-block;margin-top:24px;padding:12px 32px;background:var(--accent-primary,#8b5cf6);color:#fff;text-decoration:none;border-radius:12px;font-weight:600;transition:0.15s;}}.btn:hover{{background:#7c3aed;}}</style></head><body><div class="card"><div class="icon">✓</div><h1>TikTok Ads Conectado!</h1><p>Sua conta foi vinculada ao MKTPilot com sucesso.</p><div class="account">🎵 Advertiser: <strong>{advertiser_id or "N/D"}</strong></div><p style="font-size:0.85rem;">Agora você pode publicar vídeos gerados por IA direto no TikTok Ads Manager.</p><a href="/" class="btn">← Voltar ao MKTPilot</a></div></body></html>"""

@app.route('/api/tiktok/status', methods=['GET'])
def api_tiktok_status():
    user = get_user_from_request(request)
    if not user: return jsonify({"connected": False}), 200
    if not TIKTOK_APP_ID:
        return jsonify({"connected": False, "unconfigured": True}), 200
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/tiktok/status")
            return jsonify({"connected": False}), 200
        res = db.table("user_tiktok_tokens").select("*").eq("user_id", user.id).limit(1).execute()
        if res.data and res.data[0]:
            token = res.data[0]
            return jsonify({
                "connected": True,
                "advertiser_id": token.get('advertiser_id'),
                "account_name": token.get('account_name', '')
            }), 200
    except: pass
    return jsonify({"connected": False}), 200

@app.route('/api/meta/status', methods=['GET'])
def api_meta_status():
    user = get_user_from_request(request)
    if not user: return jsonify({"connected": False}), 200
    if not META_APP_ID:
        return jsonify({"connected": False, "unconfigured": True}), 200
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/meta/status")
            return jsonify({"connected": False}), 200
        res = db.table("user_meta_tokens").select("*").eq("user_id", user.id).limit(1).execute()
        if res.data and res.data[0]:
            token = res.data[0]
            return jsonify({
                "connected": True,
                "ad_account_id": token.get('ad_account_id'),
                "account_name": token.get('account_name', '')
            }), 200
    except: pass
    return jsonify({"connected": False}), 200

@app.route('/api/campaigns/publish_to_tiktok', methods=['POST'])
@limiter.limit("20 per hour")
def api_publish_to_tiktok():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    # Buscar token do usuário
    try:
        db = get_db(request)
        if not db:
            logger.error("DB is None in /api/campaigns/publish_to_tiktok")
            return jsonify({"erro": "authentication required"}), 401
        res = db.table("user_tiktok_tokens").select("*").eq("user_id", user.id).limit(1).execute()
        if not res.data or not res.data[0]:
            return jsonify({"erro": "Conecte sua conta TikTok primeiro! Clique em 'Conectar TikTok' no menu."}), 400
        
        token = res.data[0]['access_token']
        advertiser_id = res.data[0]['advertiser_id']
        dados, err = get_json_payload()
        if err: return err
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
@limiter.limit("10 per hour")
def api_leads_buscar():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados, err = get_json_payload(required_fields=["nicho", "cidade"])
    if err: return err
    nicho = sanitize_input(dados.get('nicho'))
    cidade = sanitize_input(dados.get('cidade'))
    
    if not nicho or not cidade:
        return jsonify({"erro": "Nicho e Cidade são obrigatórios"}), 400

    db = get_db(request)
    if not db:
        logger.error("DB is None in /api/leads/buscar")
        leads = buscar_leads_locais(nicho, cidade)
    else:
        leads = buscar_leads_locais(nicho, cidade, db=db, user_id=user.id)
    return jsonify({"leads": leads}), 200



@app.route('/api/leads/pitch', methods=['POST'])
@limiter.limit("20 per hour")
def api_leads_pitch():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados, err = get_json_payload(required_fields=["nome"])
    if err: return err
    lead_nome = dados.get('nome')
    lead_site = dados.get('site')
    meu_produto = dados.get('meu_produto', 'Marketing Digital')
    
    lang = _detect_lang(f"{lead_nome} {lead_site} {meu_produto}")
    lang_instruction = _lang_instruction(lang)

    prompt = f"""Crie uma mensagem de abordagem para o WhatsApp para prospectar o cliente "{lead_nome}".
Website do cliente: {lead_site}
Meu produto/serviço: {meu_produto}

Regras:
- Seja curto, profissional e gere curiosidade.
- Cite que você viu o site deles e que pode melhorar a presença digital.
- Use emojis moderadamente.
- Termine com uma pergunta.
- {lang_instruction}"""

    pitch = chamar_ia(prompt, system_message="Você é um SDR Senior focado em agendamento de reuniões.")
    return jsonify({"pitch": pitch}), 200

@app.route('/api/campaigns/score', methods=['POST'])
def api_campaigns_score():
    """Ad Performance Oracle 2.0: Avalia Copy + Imagem com fallback."""
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401

    dados = request.json or {}
    texto = dados.get('texto', '')
    image_url = dados.get('image_url', '')

    # Try vision-capable models first, then text-only fallback
    resultado = None
    if image_url:
        vision_prompt = f"""Analise tecnicamente este anúncio (Copy + Criativo). Dê uma nota de 0 a 100.

Texto: "{texto}"

Analise também este criativo visual: {image_url}. Avalie o contraste, a clareza da mensagem na imagem e se o design atrai cliques (Scroll-Stop).

Responda ESTRITAMENTE em JSON (use null para analise_visual se não conseguir processar a imagem):
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
        vision_models = ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"]
        resultado = chamar_ia(vision_prompt, system_message="Você é o Ad Performance Oracle, um avaliador de criativos de alta conversão.", modelos_override=vision_models)

    # Text-only fallback (no image, or vision models all failed)
    if not resultado:
        text_prompt = f"""Analise tecnicamente este anúncio (Copy). Dê uma nota de 0 a 100.

Texto: "{texto}"

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
  "analise_visual": null,
  "dica": "Sugestão técnica para subir o score."
}}
"""
        resultado = chamar_ia(text_prompt, system_message="Você é o Ad Performance Oracle, um avaliador de criativos.")

    # Parse JSON from response
    try:
        import json as pyjson
        start = resultado.find('{')
        end = resultado.rfind('}') + 1
        if start >= 0 and end > start:
            data = pyjson.loads(resultado[start:end])
        else:
            raise ValueError("JSON não encontrado")
    except Exception:
        data = {"score": 50, "status": "Regular", "metrics": {"clareza": 50, "urgencia": 50, "emocao": 50, "ctr": 50, "especificidade": 50}, "analise_visual": None, "dica": "Continue editando..."}

    # Persistência
    if data.get('score'):
        try:
            db = get_db(request)
            if db:
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

@app.route('/api/campaigns/proposal/<id>', methods=['GET'])
def api_campaign_proposal(id):
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    try:
        db = get_db(request)
        if not db:
            return jsonify({"erro": "Não autorizado"}), 401
        res = db.table("campaigns").select("*").eq("id", id).eq("user_id", user.id).limit(1).execute()
        if not res.data: return jsonify({"erro": "Campanha não encontrada"}), 404
        
        camp = res.data[0]
        result_str = camp.get('result_text', '{}')
        try:
            data = json.loads(result_str) if isinstance(result_str, str) else (result_str or {})
        except Exception:
            data = {}
        product_name = camp.get('product', 'Não especificado')
        goal_name = camp.get('goal', 'Não especificado')
        niche_name = camp.get('nicho', 'Geral')
        
        # HTML Da Proposta Profissional
        html = f"""
        <html>
        <head>
            <title>Proposta de Marketing - {product_name}</title>
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
                <p>Preparada para: <strong>{product_name}</strong> | Gerado via MKTPilot</p>
                <button onclick="window.print()" class="no-print" style="background:#8b5cf6; color:white; border:none; padding:10px 20px; border-radius:6px; cursor:pointer; margin-top:10px;">Imprimir Proposta</button>
            </div>

            <div class="section">
                <h2>1. Estratégia Recomendada</h2>
                <p>Nossa inteligência identificou que para o objetivo de <strong>{goal_name}</strong>, devemos atuar em múltiplos ângulos psicológicos para maximizar o ROI.</p>
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
            if db:
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
        if not db:
            logger.error("DB is None in /api/calendar/generate")
            brand_data = {}
        else:
            res = db.table("user_configs").select("*").eq("user_id", user.id).limit(1).execute()
            brand_data = (res.data and res.data[0]) or {}
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
@limiter.limit("8 per hour")
def api_funnel_clone():
    user = get_user_from_request(request)
    if not user: return jsonify({"erro": "Não autorizado"}), 401
    
    dados, err = get_json_payload(required_fields=["url"])
    if err: return err
    url = dados.get('url')
    if not url: return jsonify({"erro": "URL obrigatória"}), 400

    try:
        validate_public_http_url(url)
    except Exception:
        return jsonify({"erro": "URL inválida para análise"}), 400
    
    # Scrape profundo
    conteudo = scrape_concorrente(url)
    
    lang_funil = _detect_lang(conteudo[:3000])
    lang_inst_funil = _lang_instruction(lang_funil)
    prompt = f"""Analise esta Landing Page e desconstrua o funil de vendas.
Conteúdo: {conteudo[:3000]}

Responda estruturadamente:
1. Gancho Principal (Hook)
2. Promessa Única (Vantagem)
3. Gatilhos Mentais Utilizados
4. Estrutura do Funil (Lead Magnet -> Tripwire -> Core Offer)
5. Como podemos superar este funil?
{lang_inst_funil}
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
    user = get_user_from_request(request)
    try:
        db = get_db(request)
        if not db:
            return jsonify({"templates": []}), 200
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
        if not db:
            logger.error("DB is None in /api/marketplace/publish")
            return jsonify({"erro": "authentication required"}), 401
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
        if not db:
            logger.error("DB is None in /api/competitors/watch")
            return jsonify({"erro": "authentication required"}), 401
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
    user = get_user_from_request(request)
    try:
        db = get_db(request)
        if not db:
            return jsonify({"challenge": None}), 200
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
if AUTOPILOT_WORKER_ENABLED:
    threading.Thread(target=autopilot_worker, daemon=True).start()

if __name__ == '__main__':
    is_production = os.getenv("ENV", "development").lower() == "production"
    debug_enabled = (not is_production) and os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print("INICIADO NA PORTA 5000")
    print("=> Verificando Banco Supabase: " + ("Conectado!" if supabase else "AUSENTE"), flush=True)
    print("=> Cliente Admin (service_role): " + ("OK" if supabase_admin else "Aviso: Usando anon_key"), flush=True)
    print("=> Chave OpenRouter: " + ("OK" if OPENROUTER_API_KEY else "AUSENTE"), flush=True)
    print("=> Chave SiliconFlow: " + ("OK" if SILICONFLOW_API_KEY else "AUSENTE"), flush=True)
    app.run(host='0.0.0.0', port=5000, debug=debug_enabled, use_reloader=False)
