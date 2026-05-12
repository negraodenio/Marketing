from flask import Blueprint, request, jsonify, session
import openai
import json, re, datetime
import os

modules_bp = Blueprint("modules", __name__, url_prefix="/api/modules")

# ─── cliente OpenRouter ───────────────────────────────────────────────────────
client = openai.OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct")

def llm(system: str, user: str, max_tokens=800) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

def llm_json(system: str, user: str, max_tokens=1200) -> dict | list:
    raw = llm(system + "\n\nResponde APENAS em JSON válido, sem markdown.", user, max_tokens)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(clean)
    except:
        # Fallback se a IA falhar no JSON
        return {"error": "IA falhou ao gerar JSON", "raw": clean}


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCORE DE CAMPANHA EM TEMPO REAL
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/score", methods=["POST"])
def score_copy():
    data  = request.get_json()
    copy  = data.get("copy", "").strip()
    if not copy:
        return jsonify({"error": "copy vazio"}), 400

    brand_kit = session.get("brand_kit", {})
    contexto  = f"Tom: {brand_kit.get('tom','neutro')} | Público: {brand_kit.get('publico','geral')}"

    result = llm_json(
        system=(
            "És um especialista em copywriting e psicologia do consumidor. "
            "Avalia o copy recebido e devolve um JSON com estas chaves exatas: "
            "score (0-100, inteiro), clareza (0-100), urgencia (0-100), "
            "emocional (0-100), ctr_estimado (0-100), especificidade (0-100), "
            "grade (string: Fraco|Regular|Bom|Ótimo|Excelente), "
            "tip (string: sugestão concreta de melhoria, máx 120 chars). "
            f"Contexto da marca — {contexto}."
        ),
        user=f"Copy: {copy}",
    )
    return jsonify(result)


@modules_bp.route("/score/improve", methods=["POST"])
def improve_copy():
    data   = request.get_json()
    copy   = data.get("copy", "")
    target = data.get("target_score", 90)

    result = llm_json(
        system=(
            "És um copywriter de elite. Reescreve o copy para atingir "
            f"score ≥{target}/100. "
            "Devolve JSON: { improved_copy: string, changes: [string] }"
        ),
        user=f"Copy original: {copy}",
    )
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CLONADOR DE FUNIL
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/funil/analisar", methods=["POST"])
def analisar_funil():
    data       = request.get_json()
    url        = data.get("url", "")
    produto    = data.get("meu_produto", "")
    brand_kit  = session.get("brand_kit", {})

    result = llm_json(
        system=(
            "Simula a análise de um funil de vendas concorrente e gera uma versão superior. "
            "Devolve JSON com dois objectos: "
            "concorrente { headline, prova_social, cta, garantia, falhas:[str], score } "
            "e superior { headline, prova_social, cta, garantia, diferenciais:[str], "
            "copy_completo, score }. "
            f"Tom da marca: {brand_kit.get('tom','persuasivo')}. "
            f"Público-alvo: {brand_kit.get('publico','empreendedores')}."
        ),
        user=f"URL do concorrente: {url}\nMeu produto: {produto}",
        max_tokens=1400,
    )
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# 3. CALENDÁRIO 30 DIAS
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/calendario/gerar", methods=["POST"])
def gerar_calendario():
    data     = request.get_json()
    nicho    = data.get("nicho", "marketing digital")
    objetivo = data.get("objetivo", "gerar leads")
    canais   = data.get("canais", ["ig", "fb", "email"])
    mes      = data.get("mes", datetime.date.today().strftime("%Y-%m"))
    brand    = session.get("brand_kit", {})

    result = llm_json(
        system=(
            "Cria um calendário editorial de 30 dias. "
            "Distribui conteúdo pelos canais de forma estratégica: "
            "semana 1=awareness, 2=educação, 3=prova social, 4=conversão. "
            "Devolve JSON: { dias: [ { dia(1-30), canal, tipo(reel|post|story|email|tiktok), "
            "titulo, copy_curto(máx 80 chars), hashtags:[str] } ] }. "
            f"Tom: {brand.get('tom','profissional')}. "
            f"Público: {brand.get('publico','empreendedores')}."
        ),
        user=f"Nicho: {nicho}\nObjetivo: {objetivo}\nCanais: {', '.join(canais)}\nMês: {mes}",
        max_tokens=2000,
    )
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# 4. HOOKS VIRAIS
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/hooks/listar", methods=["GET"])
def listar_hooks():
    nicho  = request.args.get("nicho",  "negócios")
    angulo = request.args.get("angulo", "all")
    canal  = request.args.get("canal",  "all")

    filtros = ""
    if angulo != "all": filtros += f" Ângulo obrigatório: {angulo}."
    if canal   != "all": filtros += f" Plataforma obrigatória: {canal}."

    result = llm_json(
        system=(
            "Gera uma biblioteca de 9 hooks virais para marketing digital. "
            "Cada hook deve ter: texto, angulo(medo|ganho|curiosidade|prova_social), "
            "score(0-100), plataforma, ctr_estimado(percentagem, float), calor(1-5). "
            "Devolve JSON: { hooks: [...] }." + filtros
        ),
        user=f"Nicho: {nicho}",
        max_tokens=1200,
    )
    return jsonify(result)


@modules_bp.route("/hooks/adaptar", methods=["POST"])
def adaptar_hook():
    data    = request.get_json()
    hook    = data.get("hook", "")
    produto = data.get("produto", "")
    nicho   = data.get("nicho", "")

    result = llm_json(
        system=(
            "Adapta um hook viral para um produto específico, "
            "mantendo a estrutura psicológica que o torna viral. "
            "Devolve JSON: { hook_adaptado, variacao_a, variacao_b }."
        ),
        user=f"Hook: {hook}\nProduto: {produto}\nNicho: {nicho}",
    )
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# 5. A/B GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/ab/gerar", methods=["POST"])
def gerar_ab():
    data     = request.get_json()
    copy     = data.get("copy", "")
    produto  = data.get("produto", "")
    objetivo = data.get("objetivo", "conversão")
    brand    = session.get("brand_kit", {})

    result = llm_json(
        system=(
            "Gera 3 variações A/B/C de copy publicitário. "
            "Cada variação usa um ângulo psicológico diferente: "
            "A=medo da perda, B=ganho concreto, C=curiosidade. "
            "Devolve JSON: { variantes: [ { label(A|B|C), angulo, copy, "
            "ctr_estimado(percentagem float), notas } ] }. "
            f"Tom: {brand.get('tom','persuasivo')}."
        ),
        user=f"Copy original: {copy}\nProduto: {produto}\nObjetivo: {objetivo}",
        max_tokens=1000,
    )
    return jsonify(result)


@modules_bp.route("/ab/exportar-meta", methods=["POST"])
def exportar_ab_meta():
    data      = request.get_json()
    variantes = data.get("variantes", [])
    orcamento = data.get("orcamento", 10)
    duracao   = data.get("duracao_dias", 7)

    ads = []
    for v in variantes:
        ads.append({
            "name":          f"MKTPilot A/B — Variação {v.get('label','?')}",
            "status":        "PAUSED",
            "daily_budget":  int(orcamento / max(len(variantes), 1) * 100),  # centavos
            "body":          v.get("copy", ""),
            "call_to_action": {"type": "LEARN_MORE"},
            "optimization":  "LINK_CLICKS",
        })

    return jsonify({
        "meta_ads_draft": ads,
        "campanha":       "MKTPilot_AB_" + datetime.date.today().isoformat(),
        "duracao_dias":   duracao,
        "nota":           "Importa este JSON no Meta Ads Manager > Criar campanha > Importar.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# 6. VIRAL EM 24H
# ══════════════════════════════════════════════════════════════════════════════
@modules_bp.route("/viral/tendencias", methods=["GET"])
def listar_tendencias():
    nicho = request.args.get("nicho", "negócios")
    canal = request.args.get("canal", "all")

    result = llm_json(
        system=(
            "Simula as tendências virais desta semana nas redes sociais. "
            "Gera 4 tendências reais plausíveis para 2026. "
            "Devolve JSON: { tendencias: [ { titulo, canal, views_semana(string), "
            "descricao, adaptacao(copy adaptado ao nicho), calor(1-5), "
            "formato(reel|tiktok|short|post) } ] }."
        ),
        user=f"Nicho: {nicho}\nCanal preferido: {canal}",
        max_tokens=1000,
    )
    return jsonify(result)


@modules_bp.route("/viral/campanha", methods=["POST"])
def campanha_viral():
    data      = request.get_json()
    tendencia = data.get("tendencia", {})
    produto   = data.get("produto", "")
    nicho     = data.get("nicho", "")
    brand     = session.get("brand_kit", {})

    result = llm_json(
        system=(
            "Cria uma campanha completa que surfa uma tendência viral. "
            "Devolve JSON: { headline, copy_principal, cta, "
            "roteiro_video_30s(string com indicações de cena), "
            "hashtags:[str], melhor_horario, nota_urgencia }. "
            f"Tom: {brand.get('tom','viral')}. "
            f"Público: {brand.get('publico','empreendedores')}."
        ),
        user=(
            f"Tendência: {json.dumps(tendencia, ensure_ascii=False)}\n"
            f"Produto: {produto}\nNicho: {nicho}"
        ),
        max_tokens=1200,
    )
    return jsonify(result)
