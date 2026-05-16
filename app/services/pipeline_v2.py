import json
import logging
import os
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import requests
from pydantic import BaseModel, Field, ValidationError, conint

logger = logging.getLogger("pipeline_v2")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_TIMEOUT = int(os.getenv("PIPELINE_V2_TIMEOUT", "45"))

MODEL_ROUTING: Dict[str, Dict[str, str]] = {
    "market_analysis": {
        "premium": os.getenv("PIPELINE_V2_MARKET_PREMIUM", "anthropic/claude-sonnet-4.5"),
        "scalable": os.getenv("PIPELINE_V2_MARKET_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_MARKET_FALLBACK", "anthropic/claude-haiku-4.5"),
    },
    "icp_mapping": {
        "premium": os.getenv("PIPELINE_V2_ICP_PREMIUM", "anthropic/claude-sonnet-4.5"),
        "scalable": os.getenv("PIPELINE_V2_ICP_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_ICP_FALLBACK", "anthropic/claude-haiku-4.5"),
    },
    "creative_strategy": {
        "premium": os.getenv("PIPELINE_V2_STRATEGY_PREMIUM", "anthropic/claude-sonnet-4.5"),
        "scalable": os.getenv("PIPELINE_V2_STRATEGY_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_STRATEGY_FALLBACK", "openai/gpt-4o-mini"),
    },
    "hook_generation": {
        "premium": os.getenv("PIPELINE_V2_HOOK_PREMIUM", "openai/gpt-4o"),
        "scalable": os.getenv("PIPELINE_V2_HOOK_SCALABLE", "anthropic/claude-haiku-4.5"),
        "fallback": os.getenv("PIPELINE_V2_HOOK_FALLBACK", "openai/gpt-4o-mini"),
    },
    "legacy_campaign_builder": {
        "premium": os.getenv("PIPELINE_V2_LEGACY_PREMIUM", "anthropic/claude-sonnet-4.5"),
        "scalable": os.getenv("PIPELINE_V2_LEGACY_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_LEGACY_FALLBACK", "openai/gpt-4o-mini"),
    },
}

# Dynamic model router — cost & complexity aware
# Uses ContextVar for thread-safe per-campaign cost tracking
_COST_CONTEXT: ContextVar[float] = ContextVar("_cost_context", default=0.0)
_BUDGET_PER_CAMPAIGN_USD = float(os.getenv("PIPELINE_V2_BUDGET_PER_CAMPAIGN", "0.15"))

def _get_accumulated_cost() -> float:
    return _COST_CONTEXT.get()

def _reset_cost():
    _COST_CONTEXT.set(0.0)

def _add_stage_cost(est_cost: float):
    current = _COST_CONTEXT.get()
    _COST_CONTEXT.set(current + est_cost)

def _estimate_prompt_tokens(text: str) -> int:
    """Rough estimate: ~4 chars per token for Portuguese text."""
    return len(text) // 3

def _select_model_for_stage(stage_name: str, user_prompt: str, temperature: float) -> str:
    """Dynamically select model tier based on prompt complexity and remaining budget."""
    prompt_chars = len(user_prompt)
    budget_remaining = _BUDGET_PER_CAMPAIGN_USD - _get_accumulated_cost()
    is_complex_atomic = temperature >= 0.6
    is_large_prompt = prompt_chars > 3000
    is_low_budget = budget_remaining < 0.03

    if is_low_budget:
        return MODEL_ROUTING[stage_name]["scalable"]
    if is_large_prompt and not is_complex_atomic:
        return MODEL_ROUTING[stage_name]["scalable"]
    return MODEL_ROUTING[stage_name]["premium"]

# Structured event logger (single stdout JSON line per event)
def _emit_event(event: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {
        "ts": round(time.time(), 3),
        "service": "pipeline_v2",
        "event": event,
    }
    payload.update(fields)
    try:
        print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)
    except Exception:
        # fallback: print sem ensure_ascii em casos exóticos
        try:
            print(f"PIPELINE_V2_EVENT {event} {fields}", flush=True)
        except Exception:
            pass

AI_ISMS = [
    "descubra",
    "revolucione",
    "transforme sua vida",
    "no próximo nível",
    "imagine poder",
    "não perca essa oportunidade",
    "potencialize",
    "alavanque",
    "eleve",
    "desvende",
    "game changer",
    "disruptivo",
]


class StageExecution(BaseModel):
    stage: str
    success: bool
    model_used: str
    attempts: int = 0
    duration_ms: int = 0
    validation_issues: List[str] = Field(default_factory=list)
    fallback_used: bool = False
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0
    estimated_cost_usd: float = 0.0


class MarketAnalysis(BaseModel):
    sofistication_stage: conint(ge=1, le=5)
    sofistication_rationale: str = Field(min_length=30, max_length=500)
    awareness_stage: str = Field(min_length=5, max_length=40)
    awareness_rationale: str = Field(min_length=30, max_length=500)
    saturated_angles: List[str] = Field(min_length=3, max_length=3)
    fresh_angles: List[str] = Field(min_length=2, max_length=2)
    audience_vocabulary: List[str] = Field(min_length=8, max_length=16)
    objections: List[str] = Field(min_length=4, max_length=8)


class ICPPsychology(BaseModel):
    archetype: str = Field(min_length=10, max_length=300)
    last_month_friction_scene: str = Field(min_length=40, max_length=1000)
    midnight_self_talk: str = Field(min_length=10, max_length=600)
    micro_win_this_week: str = Field(min_length=10, max_length=500)
    twelve_month_fear: str = Field(min_length=20, max_length=600)
    cultural_reference: str = Field(min_length=5, max_length=400)
    unspoken_buying_trigger: str = Field(min_length=20, max_length=600)


class ICPMapping(BaseModel):
    icp_obvious: ICPPsychology
    icp_non_obvious: ICPPsychology


class MessageArc(BaseModel):
    tension: str = Field(min_length=20, max_length=500)
    revelation: str = Field(min_length=20, max_length=500)
    action: str = Field(min_length=20, max_length=500)


class CreativeStrategy(BaseModel):
    chosen_angle: str = Field(min_length=15, max_length=220)
    big_idea: str = Field(min_length=8, max_length=200)
    unique_mechanism_name: str = Field(min_length=6, max_length=80)
    unique_mechanism_explanation: str = Field(min_length=30, max_length=500)
    measurable_promise: str = Field(min_length=10, max_length=300)
    message_arc: MessageArc
    primary_icp: str = Field(default="obvious")
    forbidden_words_for_this_campaign: List[str] = Field(default_factory=list)


class HookItem(BaseModel):
    text: str = Field(min_length=8, max_length=250)
    framework: str = Field(min_length=4, max_length=40)
    estimated_read_seconds: conint(ge=1, le=8)
    self_score: float = Field(ge=0, le=100)
    why_it_works_for_this_icp: str = Field(min_length=20, max_length=350)


class HookBatch(BaseModel):
    hooks: List[HookItem] = Field(min_length=8, max_length=8)


class FacebookAd(BaseModel):
    headline_a: str
    headline_b: str
    headline_c: str
    primary_text_a: str
    primary_text_b: str
    primary_text_c: str
    cta: str = "Saiba Mais"


class InstagramPost(BaseModel):
    caption: str
    hashtags: str = ""


class EmailBlock(BaseModel):
    subject_a: str
    subject_b: str
    body_a: str
    body_b: str


class VideoScript(BaseModel):
    hook: str
    body: str
    cta: str


class LegacyCampaignPayload(BaseModel):
    facebook_ad: FacebookAd
    instagram_posts: List[InstagramPost] = Field(min_length=2, max_length=2)
    email: EmailBlock
    video_script: VideoScript


class PipelineV2Result(BaseModel):
    success: bool
    market_analysis: MarketAnalysis
    icp_mapping: ICPMapping
    creative_strategy: CreativeStrategy
    hook_generation: HookBatch
    campaign_payload: LegacyCampaignPayload
    stages: List[StageExecution]
    warnings: List[str] = Field(default_factory=list)


class CoherenceMemory(BaseModel):
    """Memória narrativa central — compartilhada por todos os assets da campanha."""
    core_big_idea: str = Field(min_length=20, max_length=250)
    emotional_tension: str = Field(min_length=20, max_length=200)
    buyer_identity: str = Field(min_length=20, max_length=250)
    narrative_language: List[str] = Field(min_length=5, max_length=15)
    forbidden_language: List[str] = Field(min_length=5, max_length=12)
    core_transformation: str = Field(min_length=20, max_length=250)
    primary_objection: str = Field(min_length=15, max_length=200)
    trust_mechanism: str = Field(min_length=15, max_length=200)
    visual_identity: str = Field(min_length=30, max_length=350)
    cta_philosophy: str = Field(min_length=20, max_length=250)


def _count_words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def _contains_generic_terms(text: str, forbidden_extra: Optional[List[str]] = None) -> List[str]:
    terms = list(AI_ISMS)
    if forbidden_extra:
        terms.extend([x.lower() for x in forbidden_extra])
    text_l = (text or "").lower()
    return [term for term in terms if term in text_l]


def _repair_json(text: str) -> str:
    """Tenta reparar JSON quebrado com problemas comuns de LLM output."""
    if not text:
        return ""
    # Remove comentários de linha e bloco
    t = re.sub(r"//.*?\n", "\n", text)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.DOTALL)
    # Remove trailing commas antes de ] ou }
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return t


def _extract_first_json(raw: str) -> Optional[str]:
    """Extrai o primeiro JSON válido e balanceado do texto, tolerando markdown e prose."""
    if not raw:
        return None
    # Remove wrappers de markdown
    cleaned = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    # Tenta encontrar o primeiro { balanceado
    depth = 0
    start = -1
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = cleaned[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    # Tenta reparar antes de desistir
                    repaired = _repair_json(candidate)
                    try:
                        json.loads(repaired)
                        return repaired
                    except json.JSONDecodeError:
                        pass
                # Se parse falhou, continua procurando próximo { balanceado
                start = -1
    return None


def _estimate_cost(model: str, usage: Dict[str, int]) -> float:
    # Hook simples para observabilidade de custo (aproximação conservadora)
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    # USD por 1k tokens (estimado genérico para telemetria interna)
    if "sonnet" in model:
        in_rate, out_rate = 0.004, 0.012
    elif "gpt-4o" in model and "mini" not in model:
        in_rate, out_rate = 0.005, 0.015
    elif "haiku" in model or "mini" in model or "flash" in model:
        in_rate, out_rate = 0.001, 0.003
    else:
        in_rate, out_rate = 0.002, 0.006
    return round((prompt / 1000.0) * in_rate + (completion / 1000.0) * out_rate, 6)


def _post_openrouter(model: str, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = 3000) -> Tuple[Optional[str], Dict[str, int], Optional[str]]:
    if not OPENROUTER_API_KEY:
        return None, {}, "OPENROUTER_API_KEY ausente"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://mktpilot.io",
        "X-Title": "MKTPilot PipelineV2",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=OPENROUTER_TIMEOUT,
        )
        if response.status_code != 200:
            return None, {}, f"HTTP {response.status_code}: {response.text[:240]}"
        data = response.json()
        finish = data.get("choices", [{}])[0].get("finish_reason", "")
        if finish == "length":
            return None, {"prompt_tokens": 0, "completion_tokens": 0}, f"output truncado (finish_reason=length, max_tokens={max_tokens})"
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        usage = data.get("usage", {}) or {}
        usage_obj = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        }
        return content, usage_obj, None
    except Exception as e:
        return None, {}, str(e)


def _validate_market(result: MarketAnalysis) -> List[str]:
    issues: List[str] = []
    if result.awareness_stage not in {"unaware", "problem-aware", "solution-aware", "product-aware", "most-aware"}:
        issues.append("awareness_stage fora da enum permitida")
    if len(set(x.lower() for x in result.saturated_angles)) < 3:
        issues.append("saturated_angles repetidos")
    if len(set(x.lower() for x in result.fresh_angles)) < 2:
        issues.append("fresh_angles repetidos")
    return issues


_PT_FIRST_PERSON = re.compile(
    r"^(eu\b|t[ôo]\b|tava\b|achei\b|acho\b|sinto\b|senti\b|fui\b|preciso\b|queria\b|fic[oa]\b|s[oó]\b)",
    re.IGNORECASE,
)


def _validate_icp(result: ICPMapping) -> List[str]:
    issues: List[str] = []
    for tag, icp in [("obvious", result.icp_obvious), ("non_obvious", result.icp_non_obvious)]:
        if not _PT_FIRST_PERSON.match(icp.midnight_self_talk.strip()):
            # Warning soft — nao bloqueia o stage, so loga
            logger.info("icp_%s midnight_self_talk pode nao estar em 1a pessoa: %s", tag, icp.midnight_self_talk[:80])
    return issues


def _validate_strategy(result: CreativeStrategy, market: MarketAnalysis) -> List[str]:
    issues: List[str] = []
    if _count_words(result.big_idea) > 30:
        issues.append("big_idea acima de 30 palavras")
    if any(a.lower().strip() == result.chosen_angle.lower().strip() for a in market.saturated_angles):
        issues.append("chosen_angle coincide com ângulo saturado")
    if _contains_generic_terms(result.big_idea, result.forbidden_words_for_this_campaign):
        logger.info("big_idea contém linguagem genérica (soft): %s", result.big_idea[:80])
    if not re.search(r"\d", result.measurable_promise) and "sem" not in result.measurable_promise.lower():
        issues.append("measurable_promise sem número ou contraste mensurável")
    return issues


def _validate_hooks(result: HookBatch, strategy: CreativeStrategy) -> List[str]:
    issues: List[str] = []
    frameworks = [h.framework for h in result.hooks]
    if len(set(frameworks)) < 1:
        issues.append("zero frameworks distintos")
    if any(_count_words(h.text) > 40 for h in result.hooks):
        issues.append("há hooks com mais de 40 palavras")
    for hook in result.hooks:
        tokens = re.findall(r"\w+", hook.text.lower())
        if _contains_generic_terms(hook.text, strategy.forbidden_words_for_this_campaign):
            logger.info("hook com linguagem genérica (soft): %s", hook.text[:60])
    return issues


def _validate_campaign_payload(result: LegacyCampaignPayload, strategy: CreativeStrategy) -> List[str]:
    issues: List[str] = []
    # Apenas o texto dos ativos finais entra na varredura — não meta/insights
    asset_text_parts: List[str] = []
    ad = result.facebook_ad
    asset_text_parts.extend([
        ad.headline_a, ad.headline_b, ad.headline_c,
        ad.primary_text_a, ad.primary_text_b, ad.primary_text_c,
        ad.cta or "",
    ])
    for post in result.instagram_posts:
        asset_text_parts.append(post.caption or "")
        asset_text_parts.append(post.hashtags or "")
    em = result.email
    asset_text_parts.extend([em.subject_a, em.subject_b, em.body_a, em.body_b])
    vs = result.video_script
    asset_text_parts.extend([vs.hook, vs.body, vs.cta])
    asset_text = " ".join(asset_text_parts).lower()

    for phrase in AI_ISMS + [w.lower() for w in strategy.forbidden_words_for_this_campaign]:
        if phrase and phrase in asset_text:
            logger.info("campanha contém linguagem genérica (soft): %s", phrase)
            break
    if strategy.unique_mechanism_name.lower() not in asset_text:
        logger.info("campanha não cita unique_mechanism_name (soft): %s", strategy.unique_mechanism_name)
    return issues


def _run_stage(
    stage_name: str,
    schema: Type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    validator: Optional[Callable[[Any], List[str]]] = None,
    usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None,
    max_attempts: int = 1,
    max_tokens: int = 3000,
) -> Tuple[Any, StageExecution]:
    started = time.time()
    attempts = 0
    validation_issues: List[str] = []
    # Dynamic model selection
    primary = _select_model_for_stage(stage_name, user_prompt, temperature)
    models = [
        primary,
        MODEL_ROUTING[stage_name]["scalable"],
        MODEL_ROUTING[stage_name]["fallback"],
    ]
    # Deduplicate in case primary == scalable
    seen = set()
    models = [m for m in models if not (m in seen or seen.add(m))]
    # Endurece system prompt contra markdown e prose
    hardened_system = (
        system_prompt.strip()
        + "\n\nCRITICAL OUTPUT RULES:\n"
        "- Return ONLY raw JSON.\n"
        "- No markdown code blocks (no ```json).\n"
        "- No explanations before or after.\n"
        "- No comments inside JSON.\n"
        "- No trailing commas."
    )
    _emit_event("stage_start", stage=stage_name, models=models, temperature=temperature)

    last_error = ""
    for model in models:
        repair_suffix = ""
        for _ in range(max_attempts):
            attempts += 1
            prompt = user_prompt + repair_suffix
            _emit_event("stage_attempt", stage=stage_name, model=model, attempt=attempts)
            content, usage, error = _post_openrouter(model, hardened_system, prompt, temperature, max_tokens=max_tokens)
            if error or not content:
                last_error = error or "resposta vazia"
                _emit_event(
                    "stage_api_fail",
                    stage=stage_name,
                    model=model,
                    attempt=attempts,
                    error=(last_error or "")[:240],
                )
                continue

            json_blob = _extract_first_json(content)
            if not json_blob:
                last_error = "JSON não identificado na resposta"
                repair_suffix = "\n\nReenvie APENAS JSON puro válido. Nada além de JSON."
                _emit_event(
                    "stage_json_extract_fail",
                    stage=stage_name,
                    model=model,
                    attempt=attempts,
                    raw_preview=(content or "")[:500],
                )
                continue
            parsed = None
            parse_error = None
            try:
                parsed = schema.model_validate(json.loads(json_blob))
            except (ValidationError, json.JSONDecodeError) as e:
                parse_error = e
                last_error = str(e)
                # Log do raw output EXATO para debug
                _emit_event(
                    "stage_schema_fail",
                    stage=stage_name,
                    model=model,
                    attempt=attempts,
                    error=str(e)[:240],
                    raw_json_preview=json_blob[:800],
                )
                repair_suffix = "\n\nReenvie APENAS JSON válido e completo. Nada além de JSON."
                continue
            if parse_error:
                # se parse_error persistiu, continua loop
                continue

            issues = validator(parsed) if validator else []
            if issues:
                validation_issues = issues
                repair_suffix = "\n\nReescreva mantendo schema idêntico. Regras violadas: " + "; ".join(issues)
                last_error = "; ".join(issues)
                _emit_event(
                    "stage_validation_fail",
                    stage=stage_name,
                    model=model,
                    attempt=attempts,
                    issues=issues,
                )
                continue

            est_cost = _estimate_cost(model, usage)
            _add_stage_cost(est_cost)
            if usage_hook:
                try:
                    usage_hook(stage_name, usage, est_cost)
                except Exception:
                    pass
            duration_ms = int((time.time() - started) * 1000)
            meta = StageExecution(
                stage=stage_name,
                success=True,
                model_used=model,
                attempts=attempts,
                duration_ms=duration_ms,
                validation_issues=[],
                fallback_used=model == MODEL_ROUTING[stage_name]["fallback"],
                usage_prompt_tokens=usage.get("prompt_tokens", 0),
                usage_completion_tokens=usage.get("completion_tokens", 0),
                estimated_cost_usd=est_cost,
            )
            _emit_event(
                "stage_success",
                stage=stage_name,
                model=model,
                attempts=attempts,
                duration_ms=duration_ms,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                estimated_cost_usd=est_cost,
                fallback_used=meta.fallback_used,
            )
            return parsed, meta

    _emit_event(
        "stage_exhausted",
        stage=stage_name,
        attempts=attempts,
        last_error=(last_error or "")[:240],
        validation_issues=validation_issues,
    )
    logger.warning("Stage %s falhou. Último erro: %s", stage_name, last_error)
    failed_meta = StageExecution(
        stage=stage_name,
        success=False,
        model_used=MODEL_ROUTING[stage_name]["fallback"],
        attempts=attempts,
        duration_ms=int((time.time() - started) * 1000),
        validation_issues=validation_issues or ([last_error] if last_error else ["falha desconhecida"]),
        fallback_used=True,
    )
    raise RuntimeError(f"Stage {stage_name} failed: {last_error}")


MARKET_SYSTEM_PROMPT = """
Você é um analista de marketing direto formado na escola de Eugene Schwartz.
Classifique estágio de sofisticação (1-5), awareness stage, ângulos saturados, ângulos frescos,
vocabulário real do público e objeções concretas.
Retorne APENAS JSON válido.
""".strip()

ICP_SYSTEM_PROMPT = """
Você é pesquisadora qualitativa de comportamento de compra.
Crie ICP psicológico específico (com cena real, fala interna em 1a pessoa e gatilho oculto de compra).
Nada de persona corporativa genérica. Retorne APENAS JSON.
""".strip()

STRATEGY_SYSTEM_PROMPT = """
Você é creative director de performance.
Escolha ângulo, Big Idea (<=14 palavras), mecanismo único nomeável, promessa mensurável e arco de mensagem.
Evite linguagem clichê e evite ângulos saturados.
Retorne APENAS JSON.
""".strip()

HOOK_SYSTEM_PROMPT = """
Você escreve hooks para TikTok e Meta com linguagem natural e específica.
Gere 8 hooks distribuídos: 2 callout, 2 pattern_interrupt, 2 contradiction, 2 story_tease.
Sem clichê, sem repetição de abertura, sem linguagem genérica.
Retorne APENAS JSON.
""".strip()

LEGACY_BUILDER_SYSTEM_PROMPT = """
Você é redator de performance e deve montar o payload final de campanha no schema legado.
Use estratégia e hooks já definidos. Linguagem natural e persuasiva, sem clichês.
Retorne APENAS JSON válido no schema solicitado.
""".strip()


def run_market_analysis(product: str, niche: str, audience: str, goal: str, competitor_context: str = "", usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None) -> Tuple[MarketAnalysis, StageExecution]:
    user_prompt = f"""
PRODUTO: {product}
NICHO: {niche}
PÚBLICO: {audience}
OBJETIVO: {goal}
CONTEXTO DE CONCORRÊNCIA: {competitor_context[:2200]}

Devolva:
- sofistication_stage (1-5)
- sofistication_rationale
- awareness_stage (unaware/problem-aware/solution-aware/product-aware/most-aware)
- awareness_rationale
- saturated_angles (3)
- fresh_angles (2)
- audience_vocabulary (10-15)
- objections (5)
""".strip()
    return _run_stage(
        "market_analysis",
        MarketAnalysis,
        MARKET_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.3,
        validator=_validate_market,
        usage_hook=usage_hook,
    )


def run_icp_mapping(product: str, market: MarketAnalysis, usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None) -> Tuple[ICPMapping, StageExecution]:
    user_prompt = f"""
PRODUTO: {product}
MARKET_ANALYSIS: {json.dumps(market.model_dump(), ensure_ascii=False)}

Gere dois ICPs:
- icp_obvious
- icp_non_obvious

Campos obrigatórios por ICP:
archetype, last_month_friction_scene, midnight_self_talk,
micro_win_this_week, twelve_month_fear, cultural_reference,
unspoken_buying_trigger.
""".strip()
    return _run_stage(
        "icp_mapping",
        ICPMapping,
        ICP_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.4,
        validator=_validate_icp,
        usage_hook=usage_hook,
    )


def run_creative_strategy(product: str, goal: str, market: MarketAnalysis, icp: ICPMapping, usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None) -> Tuple[CreativeStrategy, StageExecution]:
    user_prompt = f"""
PRODUTO: {product}
OBJETIVO: {goal}
MARKET_ANALYSIS: {json.dumps(market.model_dump(), ensure_ascii=False)}
ICP_MAPPING: {json.dumps(icp.model_dump(), ensure_ascii=False)}

Devolva:
- chosen_angle
- big_idea (máx 14 palavras)
- unique_mechanism_name
- unique_mechanism_explanation
- measurable_promise
- message_arc {{tension,revelation,action}}
- primary_icp
- forbidden_words_for_this_campaign
""".strip()
    return _run_stage(
        "creative_strategy",
        CreativeStrategy,
        STRATEGY_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.6,
        validator=lambda r: _validate_strategy(r, market),
        usage_hook=usage_hook,
    )


def run_hook_generation(strategy: CreativeStrategy, market: MarketAnalysis, icp: ICPMapping, usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None) -> Tuple[HookBatch, StageExecution]:
    primary_icp = icp.icp_non_obvious if strategy.primary_icp == "non_obvious" else icp.icp_obvious
    user_prompt = f"""
ESTRATÉGIA: {json.dumps(strategy.model_dump(), ensure_ascii=False)}
VOCABULÁRIO DO PÚBLICO: {json.dumps(market.audience_vocabulary, ensure_ascii=False)}
ICP_PRIMÁRIO: {json.dumps(primary_icp.model_dump(), ensure_ascii=False)}

Gere 8 hooks distribuídos:
- 2 callout
- 2 pattern_interrupt
- 2 contradiction
- 2 story_tease

Cada hook com:
text, framework, estimated_read_seconds, self_score, why_it_works_for_this_icp
""".strip()
    return _run_stage(
        "hook_generation",
        HookBatch,
        HOOK_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.9,
        validator=lambda r: _validate_hooks(r, strategy),
        usage_hook=usage_hook,
    )


COHERENCE_SYSTEM = """You are the Narrative Coherence Engine of a marketing AI system.
Your role is NOT to generate ads. Your role is to create a CENTRAL CAMPAIGN MEMORY.
All future assets (Meta Ads, Instagram, TikTok, Email, Hooks, CTAs, Visual prompts) will reference this memory.
The entire campaign must feel derived from the SAME strategic mind.
Rules: No corporate language. No generic slogans. No empty motivational fluff. Psychologically sophisticated."""


def generate_coherence_memory(
    product: str,
    market: MarketAnalysis,
    strategy: CreativeStrategy,
    icp: ICPMapping,
) -> CoherenceMemory:
    """Gera a memória narrativa central da campanha — referência para todos os assets downstream."""
    user_prompt = f"""PRODUCT: {product}
BIG IDEA: {strategy.big_idea}
CREATIVE ANGLE: {strategy.chosen_angle}
UNIQUE MECHANISM: {strategy.unique_mechanism_name}
PROMISE: {strategy.measurable_promise}
PRIMARY ICP: {icp.icp_obvious.model_dump_json()}
NON-OBVIOUS ICP: {icp.icp_non_obvious.model_dump_json()}
AUDIENCE VOCABULARY: {json.dumps(market.audience_vocabulary)}
FRESH ANGLES: {json.dumps(market.fresh_angles)}

Create the central narrative memory. All campaign assets will obey this memory.
Return ONLY valid JSON with these fields:
- core_big_idea (emotional thesis)
- emotional_tension (dominant anxiety/desire/fear)
- buyer_identity (how the buyer wants to see themselves)
- narrative_language (5-12 allowed words/phrases/expressions)
- forbidden_language (5-10 banned generic words)
- core_transformation (perceived transformation)
- primary_objection (main psychological objection)
- trust_mechanism (credibility mechanism)
- visual_identity (consistent visual style description)
- cta_philosophy (how CTAs should sound)"""

    try:
        content, usage, error = _post_openrouter(
            MODEL_ROUTING["creative_strategy"]["scalable"],
            COHERENCE_SYSTEM,
            user_prompt,
            temperature=0.5,
            max_tokens=2000,
        )
        if error or not content:
            logger.warning("Coherence generation failed: %s", error)
            return None
        json_blob = _extract_first_json(content)
        if not json_blob:
            return None
        return CoherenceMemory.model_validate(json.loads(json_blob))
    except Exception as e:
        logger.warning("Coherence exception: %s", e)
        return None


def _build_legacy_campaign_payload(
    product: str,
    niche: str,
    goal: str,
    audience: str,
    tone: str,
    strategy: CreativeStrategy,
    hooks: HookBatch,
    market: MarketAnalysis,
    icp: ICPMapping,
    coherence: Optional[CoherenceMemory] = None,
    usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None,
) -> Tuple[LegacyCampaignPayload, StageExecution]:
    top_hooks = sorted(hooks.hooks, key=lambda h: h.self_score, reverse=True)[:3]
    schema_hint = {
        "facebook_ad": {
            "headline_a": "...",
            "headline_b": "...",
            "headline_c": "...",
            "primary_text_a": "...",
            "primary_text_b": "...",
            "primary_text_c": "...",
            "cta": "Saiba Mais",
        },
        "instagram_posts": [
            {"caption": "...", "hashtags": "#..."},
            {"caption": "...", "hashtags": "#..."},
        ],
        "email": {
            "subject_a": "...",
            "subject_b": "...",
            "body_a": "...",
            "body_b": "...",
        },
        "video_script": {"hook": "...", "body": "...", "cta": "..."},
    }
    user_prompt = f"""
PRODUTO: {product}
NICHO: {niche}
OBJETIVO: {goal}
PÚBLICO: {audience}
TOM: {tone}

MARKET: {json.dumps(market.model_dump(), ensure_ascii=False)}
ICP: {json.dumps(icp.model_dump(), ensure_ascii=False)}
STRATEGY: {json.dumps(strategy.model_dump(), ensure_ascii=False)}
TOP_HOOKS: {json.dumps([h.model_dump() for h in top_hooks], ensure_ascii=False)}

Use o unique_mechanism_name e measurable_promise em todos os blocos.
Evite qualquer linguagem da lista proibida: {json.dumps(strategy.forbidden_words_for_this_campaign, ensure_ascii=False)}
{"" if not coherence else f'''
NARRATIVE COHERENCE MEMORY (ALL assets must obey this):
- Big Idea: {coherence.core_big_idea}
- Emotional Tension: {coherence.emotional_tension}
- Buyer Identity: {coherence.buyer_identity}
- Allowed Language: {json.dumps(coherence.narrative_language, ensure_ascii=False)}
- Forbidden Language: {json.dumps(coherence.forbidden_language, ensure_ascii=False)}
- Core Transformation: {coherence.core_transformation}
- Primary Objection: {coherence.primary_objection}
- Trust Mechanism: {coherence.trust_mechanism}
- Visual Identity: {coherence.visual_identity}
- CTA Philosophy: {coherence.cta_philosophy}
'''}

Retorne APENAS JSON no schema abaixo:
{json.dumps(schema_hint, ensure_ascii=False, indent=2)}
""".strip()
    return _run_stage(
        "legacy_campaign_builder",
        LegacyCampaignPayload,
        LEGACY_BUILDER_SYSTEM_PROMPT,
        user_prompt,
        temperature=0.75,
        validator=lambda r: _validate_campaign_payload(r, strategy),
        usage_hook=usage_hook,
        max_tokens=6000,
    )


def run_pipeline_v2(
    product: str,
    niche: str,
    goal: str,
    audience: str,
    tone: str,
    competitor_context: str = "",
    usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None,
) -> PipelineV2Result:
    pipeline_started = time.time()
    stages: List[StageExecution] = []
    warnings: List[str] = []
    _reset_cost()

    if not OPENROUTER_API_KEY:
        _emit_event("pipeline_abort", reason="OPENROUTER_API_KEY ausente")
        raise RuntimeError("OPENROUTER_API_KEY ausente para pipeline_v2")

    _emit_event(
        "pipeline_start",
        product=str(product)[:80],
        niche=str(niche)[:60],
        goal=str(goal)[:60],
        has_competitor_context=bool(competitor_context),
    )

    try:
        market, meta_market = run_market_analysis(product, niche, audience, goal, competitor_context, usage_hook=usage_hook)
        stages.append(meta_market)

        icp, meta_icp = run_icp_mapping(product, market, usage_hook=usage_hook)
        stages.append(meta_icp)

        strategy, meta_strategy = run_creative_strategy(product, goal, market, icp, usage_hook=usage_hook)
        stages.append(meta_strategy)

        hooks, meta_hooks = run_hook_generation(strategy, market, icp, usage_hook=usage_hook)
        stages.append(meta_hooks)

        campaign, meta_campaign = _build_legacy_campaign_payload(
            product=product,
            niche=niche,
            goal=goal,
            audience=audience,
            tone=tone,
            strategy=strategy,
            hooks=hooks,
            market=market,
            icp=icp,
            usage_hook=usage_hook,
        )
        stages.append(meta_campaign)
    except Exception as e:
        _emit_event(
            "pipeline_failed",
            error=str(e)[:240],
            stages_completed=len(stages),
            duration_ms=int((time.time() - pipeline_started) * 1000),
        )
        raise

    total_cost = round(sum(s.estimated_cost_usd for s in stages), 6)
    _emit_event(
        "pipeline_success",
        stages_completed=len(stages),
        duration_ms=int((time.time() - pipeline_started) * 1000),
        total_estimated_cost_usd=total_cost,
        models_used=[s.model_used for s in stages],
    )

    return PipelineV2Result(
        success=True,
        market_analysis=market,
        icp_mapping=icp,
        creative_strategy=strategy,
        hook_generation=hooks,
        campaign_payload=campaign,
        stages=stages,
        warnings=warnings,
    )


# ==========================================
# REFINEMENT LAYER (Stage 6)
# ==========================================

REFINEMENT_MODEL = os.getenv("PIPELINE_V2_REFINEMENT_MODEL", "openai/gpt-4o")

BANNED_WORDS = [
    "alta qualidade", "excelência", "melhor solução", "inovação",
    "líder de mercado", "feito para você", "resultados incríveis",
    "produto premium", "experiência única", "descubra", "revolucione",
    "transforme sua vida", "no próximo nível", "imagine poder",
    "não perca essa oportunidade", "potencialize", "alavanque",
    "eleve", "desvende", "game changer", "disruptivo",
]

REFINEMENT_SYSTEM = """You are the Creative Intelligence Refinement Layer of MKTPilot.
Your job is NOT to generate generic marketing copy.
You transform campaigns into HIGH-CONVERSION, emotionally persuasive, psychologically intelligent campaigns.

RULES:
- NEVER use cliché marketing language
- NEVER use corporate filler or robotic tone
- NEVER use vague claims
- Make copy feel human, emotionally specific, and believable
- Create visual imagination and trigger curiosity
- Enhance: nostalgia, exclusivity, status, belonging, transformation, urgency
- Hooks must stop scrolling, create curiosity, be short and punchy
- Big Idea must be emotionally strong, strategically differentiated
- CTA must feel natural, create action momentum

Return ONLY valid JSON. No markdown. No explanations."""


def refine_campaign(campaign_data: Dict[str, Any], product: str, niche: str, goal: str, audience: str) -> Dict[str, Any]:
    """Refina copy de campanha existente com psicologia de conversão avançada."""
    if not OPENROUTER_API_KEY:
        return campaign_data

    hooks_text = json.dumps(campaign_data.get("hooks_lab", {}), ensure_ascii=False)[:2000]
    strategy_text = json.dumps(campaign_data.get("strategy_insights", {}), ensure_ascii=False)[:2000]
    fb_ad = campaign_data.get("facebook_ad", {})
    ig_posts = campaign_data.get("instagram_posts", [])
    video = campaign_data.get("video_script", {})

    headlines = [
        fb_ad.get("headline_a", ""),
        fb_ad.get("headline_b", ""),
        fb_ad.get("headline_c", ""),
    ]
    primary_texts = [
        fb_ad.get("primary_text_a", ""),
        fb_ad.get("primary_text_b", ""),
        fb_ad.get("primary_text_c", ""),
    ]
    hooks_raw = [video.get("hook", "")] if video else []
    ctas = [fb_ad.get("cta", ""), video.get("cta", "")]

    campaign_snapshot = json.dumps({
        "product": product,
        "niche": niche,
        "goal": goal,
        "audience": audience,
        "headlines": [h for h in headlines if h],
        "primary_texts": [t[:300] for t in primary_texts if t],
        "hooks": hooks_raw,
        "ctas": [c for c in ctas if c],
        "strategy_insights": strategy_text[:1500],
    }, ensure_ascii=False)

    user_prompt = f"""Refine this campaign into elite direct-response marketing.

BANNED WORDS (do NOT use): {', '.join(BANNED_WORDS[:15])}

CAMPAIGN TO REFINE:
{campaign_snapshot}

Return ONLY this JSON schema:
{{
  "big_idea": "refined big idea",
  "psychological_angle": "core psychological trigger",
  "emotional_driver": "primary emotion targeted",
  "hooks": [
    {{"framework": "callout|pattern_interrupt|contradiction|story_tease", "text": "hook text"}}
  ],
  "headlines": ["refined headline A", "refined headline B", "refined headline C"],
  "ctas": ["refined CTA"],
  "primary_texts": ["refined text A", "refined text B", "refined text C"],
  "video_hook": "refined video hook",
  "video_body": "refined video body (keep existing style)",
  "video_cta": "refined video CTA",
  "strategic_insight": "why this campaign works psychologically",
  "forbidden_words_used": []
}}"""

    try:
        content, usage, error = _post_openrouter(
            REFINEMENT_MODEL, REFINEMENT_SYSTEM, user_prompt, temperature=0.7, max_tokens=3000
        )
        if error or not content:
            logger.warning("Refinement API falhou: %s", error)
            return campaign_data

        json_blob = _extract_first_json(content)
        if not json_blob:
            logger.warning("Refinement JSON extraction falhou")
            return campaign_data

        refined = json.loads(json_blob)
        logger.info("Refinement OK — big_idea: %s", refined.get("big_idea", "")[:60])

        # Merge refined copy back into campaign
        if refined.get("headlines"):
            fb_ad["headline_a"] = refined["headlines"][0] if len(refined["headlines"]) > 0 else fb_ad.get("headline_a")
            fb_ad["headline_b"] = refined["headlines"][1] if len(refined["headlines"]) > 1 else fb_ad.get("headline_b")
            fb_ad["headline_c"] = refined["headlines"][2] if len(refined["headlines"]) > 2 else fb_ad.get("headline_c")

        if refined.get("primary_texts"):
            fb_ad["primary_text_a"] = refined["primary_texts"][0] if len(refined["primary_texts"]) > 0 else fb_ad.get("primary_text_a")
            fb_ad["primary_text_b"] = refined["primary_texts"][1] if len(refined["primary_texts"]) > 1 else fb_ad.get("primary_text_b")
            fb_ad["primary_text_c"] = refined["primary_texts"][2] if len(refined["primary_texts"]) > 2 else fb_ad.get("primary_text_c")

        if refined.get("big_idea"):
            if "strategy_insights" not in campaign_data:
                campaign_data["strategy_insights"] = {}
            campaign_data["strategy_insights"]["refined_big_idea"] = refined["big_idea"]
            campaign_data["strategy_insights"]["psychological_angle"] = refined.get("psychological_angle", "")
            campaign_data["strategy_insights"]["emotional_driver"] = refined.get("emotional_driver", "")
            campaign_data["strategy_insights"]["strategic_insight"] = refined.get("strategic_insight", "")

        if refined.get("ctas"):
            fb_ad["cta"] = refined["ctas"][0] if refined["ctas"] else fb_ad.get("cta")

        if video:
            if refined.get("video_hook"):
                video["hook"] = refined["video_hook"]
            if refined.get("video_body"):
                video["body"] = refined["video_body"]
            if refined.get("video_cta"):
                video["cta"] = refined["video_cta"]

        # Update hooks_lab with refined hooks
        refined_hooks = refined.get("hooks") or []
        if refined_hooks and "hooks_lab" in campaign_data:
            existing_hooks = campaign_data["hooks_lab"].get("hooks", []) if isinstance(campaign_data["hooks_lab"], dict) else []
            if existing_hooks:
                for i, rh in enumerate(refined_hooks[:len(existing_hooks)]):
                    if rh.get("text"):
                        existing_hooks[i]["text"] = rh["text"]
                        existing_hooks[i]["framework"] = rh.get("framework", existing_hooks[i].get("framework", ""))

        # Attach refinement metadata
        est_cost = _estimate_cost(REFINEMENT_MODEL, usage)
        campaign_data["_engine_meta"]["refinement_applied"] = True
        campaign_data["_engine_meta"]["refinement_cost_usd"] = round(est_cost, 6)
        campaign_data["_engine_meta"]["total_estimated_cost_usd"] = round(
            campaign_data["_engine_meta"].get("total_estimated_cost_usd", 0) + est_cost, 6
        )

        return campaign_data

    except Exception as e:
        logger.warning("Refinement exception: %s", e)
        return campaign_data
