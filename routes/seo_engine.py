from flask import Blueprint, request, jsonify, session
import openai
import json, re, os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)

seo_bp = Blueprint("seo", __name__, url_prefix="/api/seo")

# ─── Auth Check ────────────────────────────────────────────────────────────────
def _check_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        sb = create_client(url, key)
        user = sb.auth.get_user(token)
        return user.user
    except Exception:
        return None

@seo_bp.before_request
def _require_auth():
    if request.method == "OPTIONS":
        return None
    if not _check_auth():
        return jsonify({"erro": "Não autorizado"}), 401

# Configuration
client = openai.OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct")

def llm_json(system: str, user: str, max_tokens=1200) -> dict | list:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system + "\n\nResponde APENAS em JSON válido, sem markdown."},
                {"role": "user",   "content": user},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except Exception as e:
        return {"error": f"IA falhou ao gerar JSON: {str(e)}"}

@seo_bp.route("/market-intelligence", methods=["POST"])
def market_intelligence():
    """Simula dados do Semrush para inteligência competitiva e SEO."""
    data = request.get_json()
    nicho = data.get("nicho", "Geral")
    produto = data.get("produto", "")
    
    # Se tivéssemos API Semrush, chamaríamos aqui. 
    # Como queremos "excelência" imediata, usamos a IA para gerar inteligência de mercado real.
    
    system_msg = (
        "Você é um especialista em SEO e Inteligência Competitiva (nível Semrush/Ahrefs). "
        "Analise o nicho e o produto fornecidos e gere dados estratégicos. "
        "Retorne um JSON com: "
        "keywords: [{term, volume, difficulty(0-100), intent(informational|commercial|transactional)}], "
        "competitors: [{name, estimated_traffic, strength(0-100), top_keywords:[str]}], "
        "market_trends: [str], "
        "seo_strategy: {focus_keywords: [str], content_gap_opportunity: str}"
    )
    
    user_msg = f"Nicho: {nicho}\nProduto: {produto}"
    
    result = llm_json(system_msg, user_msg)
    return jsonify(result)

@seo_bp.route("/analyze", methods=["POST"])
def analyze_copy():
    """Realiza um SEO Audit completo em um texto de marketing."""
    data = request.get_json()
    copy = data.get("copy", "")
    target_keywords = data.get("keywords", [])
    
    system_msg = (
        "Você é um Auditor de SEO Sênior. Sua missão é garantir que o conteúdo seja perfeitamente "
        "legível por motores de busca e IAs (Perplexity, ChatGPT, Claude). "
        "Analise o texto e retorne um JSON com: "
        "score: (0-100), "
        "readability: (0-100), "
        "ai_visibility_score: (0-100), "
        "issues: [{type(warning|critical), message, fix}], "
        "optimized_markdown: (versão do texto com tags markdown e estrutura semântica ideal para AI Search), "
        "metadata: {title_tag, meta_description, alt_text_suggestions: [str]}"
    )
    
    user_msg = f"Copy: {copy}\nPalavras-Chave Alvo: {', '.join(target_keywords)}"
    
    result = llm_json(system_msg, user_msg)
    return jsonify(result)

@seo_bp.route("/fix", methods=["POST"])
def fix_seo():
    """Aplica correções de SEO em um clique."""
    data = request.get_json()
    copy = data.get("copy", "")
    issues = data.get("issues", [])
    
    system_msg = (
        "Você é um especialista em otimização de conteúdo. "
        "Reescreva o copy fornecido corrigindo TODOS os problemas de SEO listados. "
        "Mantenha o tom de voz original mas melhore a estrutura semântica para AI Search. "
        "Use Markdown rico (headers, negrito estratégico). "
        "Retorne apenas o texto corrigido em Markdown."
    )
    
    user_msg = f"Copy Original: {copy}\nProblemas para corrigir: {json.dumps(issues, ensure_ascii=False)}"
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
        )
        return jsonify({"fixed_copy": resp.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
