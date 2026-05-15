import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import requests
from pydantic import BaseModel, Field, ValidationError, conint

logger = logging.getLogger("pipeline_v2")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_TIMEOUT = int(os.getenv("PIPELINE_V2_TIMEOUT", "45"))

MODEL_ROUTING: Dict[str, Dict[str, str]] = {
    "market_analysis": {
        "premium": os.getenv("PIPELINE_V2_MARKET_PREMIUM", "anthropic/claude-sonnet-4"),
        "scalable": os.getenv("PIPELINE_V2_MARKET_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_MARKET_FALLBACK", "anthropic/claude-haiku"),
    },
    "icp_mapping": {
        "premium": os.getenv("PIPELINE_V2_ICP_PREMIUM", "anthropic/claude-sonnet-4"),
        "scalable": os.getenv("PIPELINE_V2_ICP_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_ICP_FALLBACK", "anthropic/claude-haiku"),
    },
    "creative_strategy": {
        "premium": os.getenv("PIPELINE_V2_STRATEGY_PREMIUM", "anthropic/claude-sonnet-4"),
        "scalable": os.getenv("PIPELINE_V2_STRATEGY_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_STRATEGY_FALLBACK", "anthropic/claude-haiku"),
    },
    "hook_generation": {
        "premium": os.getenv("PIPELINE_V2_HOOK_PREMIUM", "openai/gpt-4o"),
        "scalable": os.getenv("PIPELINE_V2_HOOK_SCALABLE", "anthropic/claude-haiku"),
        "fallback": os.getenv("PIPELINE_V2_HOOK_FALLBACK", "meta-llama/llama-3.1-70b-instruct"),
    },
    "legacy_campaign_builder": {
        "premium": os.getenv("PIPELINE_V2_LEGACY_PREMIUM", "anthropic/claude-sonnet-4"),
        "scalable": os.getenv("PIPELINE_V2_LEGACY_SCALABLE", "openai/gpt-4o"),
        "fallback": os.getenv("PIPELINE_V2_LEGACY_FALLBACK", "anthropic/claude-haiku"),
    },
}

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
    archetype: str = Field(min_length=10, max_length=160)
    last_month_friction_scene: str = Field(min_length=40, max_length=500)
    midnight_self_talk: str = Field(min_length=10, max_length=220)
    micro_win_this_week: str = Field(min_length=10, max_length=220)
    twelve_month_fear: str = Field(min_length=20, max_length=320)
    cultural_reference: str = Field(min_length=5, max_length=120)
    unspoken_buying_trigger: str = Field(min_length=20, max_length=320)


class ICPMapping(BaseModel):
    icp_obvious: ICPPsychology
    icp_non_obvious: ICPPsychology


class MessageArc(BaseModel):
    tension: str = Field(min_length=20, max_length=300)
    revelation: str = Field(min_length=20, max_length=300)
    action: str = Field(min_length=20, max_length=300)


class CreativeStrategy(BaseModel):
    chosen_angle: str = Field(min_length=15, max_length=220)
    big_idea: str = Field(min_length=8, max_length=120)
    unique_mechanism_name: str = Field(min_length=6, max_length=80)
    unique_mechanism_explanation: str = Field(min_length=30, max_length=500)
    measurable_promise: str = Field(min_length=10, max_length=160)
    message_arc: MessageArc
    primary_icp: str = Field(default="obvious")
    forbidden_words_for_this_campaign: List[str] = Field(default_factory=list)


class HookItem(BaseModel):
    text: str = Field(min_length=8, max_length=160)
    framework: str = Field(min_length=4, max_length=40)
    estimated_read_seconds: conint(ge=1, le=4)
    self_score: conint(ge=0, le=100)
    why_it_works_for_this_icp: str = Field(min_length=20, max_length=280)


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


def _count_words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def _contains_generic_terms(text: str, forbidden_extra: Optional[List[str]] = None) -> List[str]:
    terms = list(AI_ISMS)
    if forbidden_extra:
        terms.extend([x.lower() for x in forbidden_extra])
    text_l = (text or "").lower()
    return [term for term in terms if term in text_l]


def _extract_first_json(raw: str) -> Optional[str]:
    if not raw:
        return None
    t = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE).strip()
    t = re.sub(r"```", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return t[start : end + 1]


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


def _post_openrouter(model: str, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = 1800) -> Tuple[Optional[str], Dict[str, int], Optional[str]]:
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


def _validate_icp(result: ICPMapping) -> List[str]:
    issues: List[str] = []
    for tag, icp in [("obvious", result.icp_obvious), ("non_obvious", result.icp_non_obvious)]:
        if not re.match(r"^(eu|tô|to|eu\s)", icp.midnight_self_talk.strip().lower()):
            issues.append(f"midnight_self_talk do ICP {tag} deveria estar em 1a pessoa")
    return issues


def _validate_strategy(result: CreativeStrategy, market: MarketAnalysis) -> List[str]:
    issues: List[str] = []
    if _count_words(result.big_idea) > 14:
        issues.append("big_idea acima de 14 palavras")
    if any(a.lower().strip() == result.chosen_angle.lower().strip() for a in market.saturated_angles):
        issues.append("chosen_angle coincide com ângulo saturado")
    if _contains_generic_terms(result.big_idea, result.forbidden_words_for_this_campaign):
        issues.append("big_idea contém linguagem genérica")
    if not re.search(r"\d", result.measurable_promise) and "sem" not in result.measurable_promise.lower():
        issues.append("measurable_promise sem número ou contraste mensurável")
    return issues


def _validate_hooks(result: HookBatch, strategy: CreativeStrategy) -> List[str]:
    issues: List[str] = []
    frameworks = [h.framework for h in result.hooks]
    expected = {"callout", "pattern_interrupt", "contradiction", "story_tease"}
    if not expected.issubset(set(frameworks)):
        issues.append("frameworks incompletos")
    if any(_count_words(h.text) > 22 for h in result.hooks):
        issues.append("há hooks com mais de 22 palavras")
    opening_pairs = []
    for hook in result.hooks:
        tokens = re.findall(r"\w+", hook.text.lower())
        opening_pairs.append(tuple(tokens[:2]))
        if _contains_generic_terms(hook.text, strategy.forbidden_words_for_this_campaign):
            issues.append("hook contém linguagem genérica/proibida")
    if len(opening_pairs) != len(set(opening_pairs)):
        issues.append("hooks com abertura repetitiva")
    return issues


def _validate_campaign_payload(result: LegacyCampaignPayload, strategy: CreativeStrategy) -> List[str]:
    issues: List[str] = []
    payload_text = json.dumps(result.model_dump(), ensure_ascii=False).lower()
    for phrase in AI_ISMS + [w.lower() for w in strategy.forbidden_words_for_this_campaign]:
        if phrase and phrase in payload_text:
            issues.append(f"linguagem genérica detectada: {phrase}")
            break
    if strategy.unique_mechanism_name.lower() not in payload_text:
        issues.append("payload não cita unique_mechanism_name")
    return issues


def _run_stage(
    stage_name: str,
    schema: Type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    validator: Optional[Callable[[Any], List[str]]] = None,
    usage_hook: Optional[Callable[[str, Dict[str, int], float], None]] = None,
    max_attempts: int = 3,
) -> Tuple[Any, StageExecution]:
    started = time.time()
    attempts = 0
    validation_issues: List[str] = []
    models = [
        MODEL_ROUTING[stage_name]["premium"],
        MODEL_ROUTING[stage_name]["scalable"],
        MODEL_ROUTING[stage_name]["fallback"],
    ]

    last_error = ""
    for model in models:
        repair_suffix = ""
        for _ in range(max_attempts):
            attempts += 1
            prompt = user_prompt + repair_suffix
            content, usage, error = _post_openrouter(model, system_prompt, prompt, temperature)
            if error or not content:
                last_error = error or "resposta vazia"
                continue

            json_blob = _extract_first_json(content)
            if not json_blob:
                last_error = "JSON não identificado na resposta"
                repair_suffix = "\n\nA resposta anterior não estava em JSON válido. Reenvie APENAS JSON puro."
                continue
            try:
                parsed = schema.model_validate(json.loads(json_blob))
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = str(e)
                repair_suffix = f"\n\nSchema inválido: {e}. Reenvie APENAS JSON válido e completo."
                continue

            issues = validator(parsed) if validator else []
            if issues:
                validation_issues = issues
                repair_suffix = "\n\nA saída violou regras de qualidade: " + "; ".join(issues) + ". Reescreva mantendo schema idêntico."
                last_error = "; ".join(issues)
                continue

            est_cost = _estimate_cost(model, usage)
            if usage_hook:
                try:
                    usage_hook(stage_name, usage, est_cost)
                except Exception:
                    pass
            meta = StageExecution(
                stage=stage_name,
                success=True,
                model_used=model,
                attempts=attempts,
                duration_ms=int((time.time() - started) * 1000),
                validation_issues=[],
                fallback_used=model == MODEL_ROUTING[stage_name]["fallback"],
                usage_prompt_tokens=usage.get("prompt_tokens", 0),
                usage_completion_tokens=usage.get("completion_tokens", 0),
                estimated_cost_usd=est_cost,
            )
            return parsed, meta

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
    stages: List[StageExecution] = []
    warnings: List[str] = []

    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY ausente para pipeline_v2")

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
