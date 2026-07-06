import json
import logging
import os
import re
import requests
from typing import List, Union

from loguru import logger
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletion

from app.config import config
from app.models.schema import NormalizedCollectorKeywords, normalize_collector_keywords

_max_retries = 5
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_DEPRECATED_GEMINI_MODELS = {"gemini-pro", "gemini-1.0-pro"}
MIN_SCRIPT_PARAGRAPH_NUMBER = 1
MAX_SCRIPT_PARAGRAPH_NUMBER = 10
MAX_SCRIPT_PROMPT_LENGTH = 2000
MAX_SCRIPT_SYSTEM_PROMPT_LENGTH = 8000
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*$", re.IGNORECASE | re.DOTALL)

DEFAULT_SCRIPT_SYSTEM_PROMPT = """
# Role: Video Script Generator

## Goals:
Generate a script for a video, depending on the subject of the video.

## Constrains:
1. the script is to be returned as a string with the specified number of paragraphs.
2. do not under any circumstance reference this prompt in your response.
3. get straight to the point, don't start with unnecessary things like, "welcome to this video".
4. you must not include any type of markdown or formatting in the script, never use a title.
5. only return the raw content of the script.
6. do not include "voiceover", "narrator" or similar indicators of what should be spoken at the beginning of each paragraph or line.
7. you must not mention the prompt, or anything about the script itself. also, never talk about the amount of paragraphs or lines. just write the script.
8. respond in the same language as the video subject.
""".strip()

# Prompt base para vídeos de monetização no Facebook (60–90s, 1 curiosidade).
# Use em config.toml -> [ui] -> custom_system_prompt com use_custom_system_prompt = true.
BR_FACEBOOK_MONETIZATION_SCRIPT_SYSTEM_PROMPT = """
# Role: Roteirista especializado em vídeos para Facebook

## Objetivo:
Gerar um roteiro narrado para vídeo, com base no tema fornecido.

## Regras obrigatórias:
1. O roteiro deve durar entre 60 e 90 segundos quando narrado em velocidade normal.
2. Use entre 180 e 250 palavras.
3. Explique apenas UMA curiosidade — sem listas, sem múltiplos tópicos.
4. Comece com um gancho forte (pergunta ou afirmação que gere curiosidade).
5. Não use introduções genéricas como "neste vídeo", "hoje vamos falar" ou similares.
6. Mantenha o interesse durante todo o vídeo com frases curtas.
7. Cada frase deve gerar curiosidade para a próxima.
8. Use exemplos concretos no meio do roteiro.
9. Termine com uma informação surpreendente.
10. Linguagem simples para brasileiros.
11. Não use emojis, markdown, títulos ou formatação.
12. Retorne apenas o texto do roteiro.

## Estrutura sugerida:
- Gancho (5 segundos)
- Explicação rápida
- Contexto cultural
- Exemplo real
- Fato surpreendente
- Conclusão impactante

## Restrições técnicas:
- Retorne o script como string com o número especificado de parágrafos.
- Não mencione o prompt, parágrafos, regras ou instruções.
- Não inclua indicadores como "voiceover", "narrador" ou similares.
- Responda no mesmo idioma do tema do vídeo quando não houver idioma especificado.
""".strip()

# Prompt base para Reels curtos de crescimento (25–35s, 1 curiosidade).
BR_SHORT_REELS_SCRIPT_SYSTEM_PROMPT = """
# Role: Especialista em roteiros virais para Facebook Reels, Instagram Reels e YouTube Shorts

## Objetivo:
Gerar um roteiro narrado curto, com base no tema fornecido.

## Regras obrigatórias:
1. O roteiro deve durar entre 25 e 35 segundos quando narrado em velocidade normal.
2. Use entre 70 e 100 palavras.
3. Fale apenas sobre UMA curiosidade — sem listas, sem múltiplos tópicos.
4. Comece com uma pergunta ou afirmação que gere curiosidade.
5. Não use introduções genéricas.
6. Use frases curtas; cada frase deve gerar curiosidade para a próxima.
7. O final deve surpreender o espectador.
8. Linguagem simples para brasileiros.
9. Não use emojis, markdown, títulos ou formatação.
10. Retorne apenas o texto do roteiro.

## Estrutura sugerida:
- Gancho (3 segundos)
- Explicação rápida
- Curiosidade surpreendente
- Final impactante

## Restrições técnicas:
- Retorne o script como string com o número especificado de parágrafos.
- Não mencione o prompt, parágrafos, regras ou instruções.
- Não inclua indicadores como "voiceover", "narrador" ou similares.
- Responda no mesmo idioma do tema do vídeo quando não houver idioma especificado.
""".strip()


def _normalize_text_response(content, llm_provider: str) -> str:
    # 不同 LLM SDK 在异常或被拦截场景下，可能返回 None、空字符串，
    # 甚至返回非字符串对象。这里统一做兜底校验，避免后续直接调用
    # `.replace()` 时抛出 `NoneType` 之类的属性错误。
    if content is None:
        raise ValueError(f"[{llm_provider}] returned empty text content")

    if not isinstance(content, str):
        raise TypeError(
            f"[{llm_provider}] returned non-text content: {type(content).__name__}"
        )

    # MiniMax M3、DeepSeek R1 这类 reasoning 模型可能会把内部推理包在
    # `<think>...</think>` 中返回。视频脚本和关键词只需要最终可朗读文本，
    # 如果不在服务层统一清理，WebUI、字幕和配音都会把思考过程当正文处理。
    content = _THINK_BLOCK_RE.sub("", content)
    content = _UNCLOSED_THINK_BLOCK_RE.sub("", content).strip()
    if not content:
        raise ValueError(f"[{llm_provider}] returned empty text content")

    return content.replace("\n", "")


def _extract_chat_completion_text(response, llm_provider: str) -> str:
    # OpenAI 兼容接口在异常场景下，可能返回没有 choices、
    # 或者 choices/message/content 为空的响应对象。
    # 这里统一做结构校验，避免出现 `NoneType is not subscriptable`
    # 这类底层属性访问错误。
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError(f"[{llm_provider}] returned empty choices")

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None:
        raise ValueError(f"[{llm_provider}] returned empty message")

    content = getattr(message, "content", None)
    return _normalize_text_response(content, llm_provider)


def _get_response_field(value, key: str):
    """兼容 dict 和 SDK 响应对象的字段读取。"""
    if isinstance(value, dict):
        return value.get(key)

    try:
        return value[key]
    except (KeyError, TypeError, AttributeError):
        return getattr(value, key, None)


def _extract_qwen_generation_text(response) -> str:
    """
    从 DashScope Generation 响应中提取文本。

    Qwen 使用 `messages` 调用时返回的是 chat 结构：
    `output.choices[0].message.content`；旧 completion 形态才会返回
    `output.text`。这里两个路径都兼容，避免 `output.text` 为 None 时
    继续 `.replace()` 触发不可诊断的 AttributeError。
    """
    output = _get_response_field(response, "output")
    choices = _get_response_field(output, "choices") if output else None
    if choices is not None:
        if not choices:
            logger.warning("Qwen returned an empty choices list")
            raise ValueError("[qwen] returned empty choices")

        first_choice = choices[0]
        message = _get_response_field(first_choice, "message")
        content = _get_response_field(message, "content") if message else None
        if content is not None:
            return _normalize_text_response(content, "qwen")

    text = _get_response_field(output, "text") if output else None
    return _normalize_text_response(text, "qwen")


def _bedrock_litellm_model_id(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return model_name
    if model_name.startswith("bedrock/"):
        return model_name
    return f"bedrock/{model_name}"


_BEDROCK_BEARER_PREFIXES = ("ABSK", "bedrock-api-key-")
DEFAULT_BEDROCK_MODEL = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_BEDROCK_MANTLE_OPENAI_MODEL = "openai.gpt-5.4"
_DEPRECATED_BEDROCK_MODELS = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": DEFAULT_BEDROCK_MODEL,
    "anthropic.claude-3-5-sonnet-20240620-v1:0": DEFAULT_BEDROCK_MODEL,
}
_BEDROCK_MANTLE_RESPONSES_MODELS = frozenset(
    {
        "openai.gpt-5.5",
        "openai.gpt-5.4",
    }
)
_BEDROCK_MANTLE_MODEL_ALIASES = {
    "gpt-5.5-mini": DEFAULT_BEDROCK_MANTLE_OPENAI_MODEL,
    "openai.gpt-5.5-mini": DEFAULT_BEDROCK_MANTLE_OPENAI_MODEL,
    "gpt-5.5 mini": DEFAULT_BEDROCK_MANTLE_OPENAI_MODEL,
}
_BEDROCK_MANTLE_MODEL_REGIONS = {
    "openai.gpt-5.5": ("us-east-2",),
    "openai.gpt-5.4": ("us-east-2", "us-west-2"),
}

# Curated Bedrock model IDs for the WebUI selectbox (not fetched live — Bedrock API keys
# do not support ListFoundationModels; enable models in the console first).
BEDROCK_MODEL_OPTIONS = [
    # Anthropic Claude 4.5 — region us-east-1
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Amazon Nova — region us-east-1
    "amazon.nova-micro-v1:0",
    "amazon.nova-lite-v1:0",
    "amazon.nova-pro-v1:0",
    "amazon.nova-premier-v1:0",
    # Meta Llama — use us. inference profiles in us-east-1
    "us.meta.llama3-3-70b-instruct-v1:0",
    "us.meta.llama3-2-90b-instruct-v1:0",
    "us.meta.llama3-2-11b-instruct-v1:0",
    "us.meta.llama3-2-3b-instruct-v1:0",
    "us.meta.llama3-2-1b-instruct-v1:0",
    # Mistral
    "mistral.mistral-small-2402-v1:0",
    "mistral.mistral-large-2402-v1:0",
    # Cohere
    "cohere.command-r-v1:0",
    "cohere.command-r-plus-v1:0",
    # OpenAI on Bedrock Mantle — region us-east-2 (separate model access)
    "openai.gpt-5.4",
    "openai.gpt-5.5",
]

DEFAULT_BEDROCK_SELECT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
ANTHROPIC_MODEL_OPTIONS = [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


def _anthropic_litellm_model_id(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return f"anthropic/{DEFAULT_ANTHROPIC_MODEL}"
    if model_name.startswith("anthropic/"):
        return model_name
    return f"anthropic/{model_name}"


def normalize_bedrock_mantle_model_name(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return DEFAULT_BEDROCK_MANTLE_OPENAI_MODEL
    alias = _BEDROCK_MANTLE_MODEL_ALIASES.get(model_name) or _BEDROCK_MANTLE_MODEL_ALIASES.get(
        model_name.lower()
    )
    if alias:
        logger.warning(
            f"bedrock mantle: '{model_name}' is not available on Bedrock, "
            f"using '{alias}' instead"
        )
        return alias
    return model_name


def is_bedrock_mantle_responses_model(model_name: str) -> bool:
    normalized = normalize_bedrock_mantle_model_name(model_name)
    return normalized in _BEDROCK_MANTLE_RESPONSES_MODELS


def normalize_bedrock_model_name(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return DEFAULT_BEDROCK_MODEL
    if is_bedrock_mantle_responses_model(model_name):
        return normalize_bedrock_mantle_model_name(model_name)
    if model_name in _DEPRECATED_BEDROCK_MODELS:
        replacement = _DEPRECATED_BEDROCK_MODELS[model_name]
        logger.warning(
            f"bedrock model '{model_name}' is deprecated, fallback to '{replacement}'"
        )
        return replacement
    return model_name


def is_valid_bedrock_bearer_token(token: str) -> bool:
    value = str(token or "").strip()
    if not value:
        return False
    return value.startswith(_BEDROCK_BEARER_PREFIXES)


def looks_like_aws_access_key_id(token: str) -> bool:
    value = str(token or "").strip()
    return value.startswith(("AKIA", "ASIA"))


def looks_like_bedrock_iam_username(token: str) -> bool:
    """Bedrock console creates IAM users named BedrockAPIKey-xxxx — not the bearer token."""
    value = str(token or "").strip()
    return value.startswith("BedrockAPIKey-")


def _resolve_bedrock_bearer_token() -> str | None:
    raw = config.app.get("bedrock_api_key") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    token = str(raw or "").strip()
    if not token:
        return None
    if is_valid_bedrock_bearer_token(token):
        return token
    if looks_like_bedrock_iam_username(token):
        raise ValueError(
            "bedrock: this looks like the IAM username (BedrockAPIKey-...), not the API key. "
            "In the Bedrock console → API keys → Generate, copy the full token that starts "
            "with ABSK... (long-term) or bedrock-api-key-... (short-term)."
        )
    if looks_like_aws_access_key_id(token):
        raise ValueError(
            "bedrock: bedrock_api_key looks like an AWS Access Key (AKIA/ASIA). "
            "Put Access Key + Secret Key in the IAM credentials section, or generate "
            "a Bedrock API key in the console (prefix ABSK... or bedrock-api-key-...)."
        )
    logger.warning(
        "bedrock_api_key has an invalid Bedrock bearer format; "
        "ignoring it and falling back to IAM credentials"
    )
    return None


def _bedrock_litellm_kwargs() -> dict:
    region = (
        config.app.get("bedrock_region")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    kwargs = {"aws_region_name": str(region).strip(), "drop_params": True}

    bearer_token = _resolve_bedrock_bearer_token()
    if bearer_token:
        kwargs["api_key"] = bearer_token
        return kwargs

    access_key = config.app.get("bedrock_aws_access_key_id") or os.environ.get(
        "AWS_ACCESS_KEY_ID"
    )
    secret_key = config.app.get("bedrock_aws_secret_access_key") or os.environ.get(
        "AWS_SECRET_ACCESS_KEY"
    )
    session_token = config.app.get("bedrock_aws_session_token") or os.environ.get(
        "AWS_SESSION_TOKEN"
    )

    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key
    if session_token:
        kwargs["aws_session_token"] = session_token

    return kwargs


def _bedrock_mantle_api_base(region: str) -> str:
    return f"https://bedrock-mantle.{region.strip()}.api.aws/openai/v1"


def _resolve_bedrock_mantle_region(model_name: str, configured_region: str) -> str:
    allowed = _BEDROCK_MANTLE_MODEL_REGIONS.get(
        model_name, ("us-east-2",)
    )
    region = (configured_region or allowed[0]).strip()
    if region in allowed:
        return region
    fallback = allowed[0]
    logger.warning(
        f"bedrock mantle: region '{region}' is not supported for {model_name}, "
        f"using '{fallback}'"
    )
    return fallback


def _extract_bedrock_mantle_response_text(response, provider: str) -> str:
    if not response:
        raise ValueError(f"[{provider}] returned empty response")

    output_text = getattr(response, "output_text", None)
    if output_text:
        return _normalize_text_response(output_text, provider)

    parts: list[str] = []
    for item in getattr(response, "output", None) or []:
        for block in getattr(item, "content", None) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)

    if not parts:
        raise ValueError(f"[{provider}] returned empty response")
    return _normalize_text_response("".join(parts), provider)


def _bedrock_mantle_responses(prompt: str, model_name: str) -> str:
    mantle_model = normalize_bedrock_mantle_model_name(model_name)
    bearer_token = _resolve_bedrock_bearer_token()
    if not bearer_token:
        raise ValueError(
            "bedrock mantle: OpenAI models (openai.gpt-5.4 / openai.gpt-5.5) require "
            "a Bedrock API key (ABSK... or bedrock-api-key-...) from the Bedrock console."
        )

    configured_region = (
        config.app.get("bedrock_region")
        or os.environ.get("BEDROCK_MANTLE_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-2"
    )
    region = _resolve_bedrock_mantle_region(mantle_model, str(configured_region))
    api_base = _bedrock_mantle_api_base(region)
    logger.info(
        f"requesting bedrock mantle responses, model: {mantle_model}, region: {region}"
    )

    client = OpenAI(api_key=bearer_token, base_url=api_base)
    response = client.responses.create(model=mantle_model, input=prompt)
    return _extract_bedrock_mantle_response_text(response, "bedrock")


def _generate_response(prompt: str) -> str:
    try:
        content = ""
        llm_provider = str(config.app.get("llm_provider", "openai")).strip().lower()
        logger.info(f"llm provider: {llm_provider}")
        if llm_provider == "g4f":
            if not config.app.get("enable_g4f", False):
                raise ValueError(
                    "g4f provider is disabled by default because it relies on "
                    "reverse-engineered third-party endpoints. Set enable_g4f=true "
                    "in config.toml only if you understand and accept the security, "
                    "reliability, and legal risks."
                )

            logger.warning(
                "g4f provider is enabled. This provider may be unstable and carries "
                "supply-chain and terms-of-service risks. Prefer official providers, "
                "OpenAI-compatible APIs, LiteLLM, Ollama, or local inference for production."
            )
            try:
                import g4f
            except ImportError as e:
                raise ValueError(
                    "g4f package is not installed by default. Install the optional "
                    "dependency with `uv sync --extra g4f` only if you understand "
                    "and accept the provider risks."
                ) from e

            model_name = config.app.get("g4f_model_name", "")
            if not model_name:
                model_name = "gpt-3.5-turbo-16k-0613"
            content = g4f.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            api_version = ""  # for azure
            api_key = ""
            model_name = ""
            base_url = ""
            secret_key = ""
            account_id = ""
            if llm_provider == "moonshot":
                api_key = config.app.get("moonshot_api_key")
                model_name = config.app.get("moonshot_model_name")
                base_url = "https://api.moonshot.cn/v1"
            elif llm_provider == "ollama":
                # api_key = config.app.get("openai_api_key")
                api_key = "ollama"  # any string works but you are required to have one
                model_name = config.app.get("ollama_model_name")
                base_url = config.app.get("ollama_base_url", "")
                if not base_url:
                    base_url = config.get_default_ollama_base_url()
            elif llm_provider == "openai":
                api_key = config.app.get("openai_api_key")
                model_name = config.app.get("openai_model_name")
                base_url = config.app.get("openai_base_url", "")
                if not base_url:
                    base_url = "https://api.openai.com/v1"
            elif llm_provider == "aihubmix":
                api_key = config.app.get("aihubmix_api_key")
                model_name = config.app.get("aihubmix_model_name")
                base_url = config.app.get("aihubmix_base_url", "")
                # AIHubMix 兼容 OpenAI Chat Completions 协议。这里使用独立
                # provider 保存合作方的默认网关和推荐模型，避免把推广链接、
                # 默认模型等合作配置混进普通 OpenAI provider，影响现有用户。
                if not base_url:
                    base_url = "https://aihubmix.com/v1"
                if not model_name:
                    model_name = "gpt-5.4-mini"
            elif llm_provider == "oneapi":
                api_key = config.app.get("oneapi_api_key")
                model_name = config.app.get("oneapi_model_name")
                base_url = config.app.get("oneapi_base_url", "")
            elif llm_provider == "azure":
                api_key = config.app.get("azure_api_key")
                model_name = config.app.get("azure_model_name")
                base_url = config.app.get("azure_base_url", "")
                api_version = config.app.get("azure_api_version", "2024-02-15-preview")
            elif llm_provider == "gemini":
                api_key = config.app.get("gemini_api_key")
                model_name = config.app.get("gemini_model_name")
                base_url = config.app.get("gemini_base_url", "")
                # Gemini 旧模型名已经陆续下线，这里自动兼容历史配置，
                # 避免用户沿用旧值时直接收到 404。
                if not model_name:
                    model_name = _DEFAULT_GEMINI_MODEL
                elif model_name in _DEPRECATED_GEMINI_MODELS:
                    logger.warning(
                        f"gemini model '{model_name}' is deprecated, fallback to '{_DEFAULT_GEMINI_MODEL}'"
                    )
                    model_name = _DEFAULT_GEMINI_MODEL
            elif llm_provider == "grok":
                api_key = config.app.get("grok_api_key")
                model_name = config.app.get("grok_model_name")
                base_url = config.app.get("grok_base_url", "")
                if not base_url:
                    base_url = "https://api.x.ai/v1"
            elif llm_provider == "groq":
                api_key = config.app.get("groq_api_key")
                model_name = config.app.get("groq_model_name")
                if not model_name:
                    model_name = "llama-3.3-70b-versatile"
                base_url = config.app.get("groq_base_url", "")
                if not base_url:
                    base_url = "https://api.groq.com/openai/v1"
            elif llm_provider == "qwen":
                api_key = config.app.get("qwen_api_key")
                model_name = config.app.get("qwen_model_name")
                base_url = "***"
            elif llm_provider == "cloudflare":
                api_key = config.app.get("cloudflare_api_key")
                model_name = config.app.get("cloudflare_model_name")
                account_id = config.app.get("cloudflare_account_id")
                base_url = "***"
            elif llm_provider == "minimax":
                api_key = config.app.get("minimax_api_key")
                model_name = config.app.get("minimax_model_name")
                base_url = config.app.get("minimax_base_url", "")
                if not base_url:
                    base_url = "https://api.minimax.io/v1"
            elif llm_provider == "mimo":
                api_key = config.app.get("mimo_api_key")
                model_name = config.app.get("mimo_model_name")
                base_url = config.app.get("mimo_base_url", "")
                # Xiaomi MiMo 官方文档说明其兼容 OpenAI Chat Completions 协议。
                # 这里使用独立 provider 保存默认地址和模型名，用户不用把 MiMo
                # 当作 OpenAI 自定义 base_url 配置，也便于后续继续接入 MiMo
                # 多模态或 TTS 能力时保持边界清晰。
                if not base_url:
                    base_url = "https://api.xiaomimimo.com/v1"
                if not model_name:
                    model_name = "mimo-v2.5-pro"
            elif llm_provider == "deepseek":
                api_key = config.app.get("deepseek_api_key")
                model_name = config.app.get("deepseek_model_name")
                base_url = config.app.get("deepseek_base_url")
                if not base_url:
                    base_url = "https://api.deepseek.com"
            elif llm_provider == "modelscope":
                api_key = config.app.get("modelscope_api_key")
                model_name = config.app.get("modelscope_model_name")
                base_url = config.app.get("modelscope_base_url")
                if not base_url:
                    base_url = "https://api-inference.modelscope.cn/v1/"
            elif llm_provider == "ernie":
                api_key = config.app.get("ernie_api_key")
                secret_key = config.app.get("ernie_secret_key")
                base_url = config.app.get("ernie_base_url")
                model_name = "***"
                if not secret_key:
                    raise ValueError(
                        f"{llm_provider}: secret_key is not set, please set it in the config.toml file."
                    )
            elif llm_provider == "pollinations":
                try:
                    base_url = config.app.get("pollinations_base_url", "")
                    if not base_url:
                        base_url = "https://text.pollinations.ai/openai"
                    model_name = config.app.get("pollinations_model_name", "openai-fast")
                   
                    # Prepare the payload
                    payload = {
                        "model": model_name,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "seed": 101  # Optional but helps with reproducibility
                    }
                    
                    # Optional parameters if configured
                    if config.app.get("pollinations_private"):
                        payload["private"] = True
                    if config.app.get("pollinations_referrer"):
                        payload["referrer"] = config.app.get("pollinations_referrer")
                    
                    headers = {
                        "Content-Type": "application/json"
                    }
                    
                    # Make the API request
                    response = requests.post(base_url, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    if result and "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        return _normalize_text_response(content, llm_provider)
                    else:
                        raise Exception(f"[{llm_provider}] returned an invalid response format")
                        
                except requests.exceptions.RequestException as e:
                    raise Exception(f"[{llm_provider}] request failed: {str(e)}")
                except Exception as e:
                    raise Exception(f"[{llm_provider}] error: {str(e)}")

            elif llm_provider == "anthropic":
                api_key = config.app.get("anthropic_api_key") or os.environ.get(
                    "ANTHROPIC_API_KEY"
                )
                model_name = config.app.get("anthropic_model_name")
                if not model_name:
                    model_name = DEFAULT_ANTHROPIC_MODEL
            elif llm_provider == "litellm":
                model_name = config.app.get("litellm_model_name")
            elif llm_provider == "bedrock":
                model_name = config.app.get("bedrock_model_name")

            if llm_provider not in [
                "pollinations",
                "ollama",
                "litellm",
                "bedrock",
                "anthropic",
            ]:  # Skip validation for providers that don't require API key
                if not api_key:
                    raise ValueError(
                        f"{llm_provider}: api_key is not set, please set it in the config.toml file."
                    )
                if not model_name:
                    raise ValueError(
                        f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                    )
                if not base_url and llm_provider not in ["gemini"]:
                    raise ValueError(
                        f"{llm_provider}: base_url is not set, please set it in the config.toml file."
                    )

            if llm_provider == "qwen":
                import dashscope
                from dashscope.api_entities.dashscope_response import GenerationResponse

                dashscope.api_key = api_key
                response = dashscope.Generation.call(
                    model=model_name, messages=[{"role": "user", "content": prompt}]
                )
                if response:
                    if isinstance(response, GenerationResponse):
                        status_code = response.status_code
                        if status_code != 200:
                            raise Exception(
                                f'[{llm_provider}] returned an error response: "{response}"'
                            )

                        return _extract_qwen_generation_text(response)
                    else:
                        raise Exception(
                            f'[{llm_provider}] returned an invalid response: "{response}"'
                        )
                else:
                    raise Exception(f"[{llm_provider}] returned an empty response")

            if llm_provider == "gemini":
                import google.generativeai as genai

                if not base_url:
                    genai.configure(api_key=api_key, transport="rest")
                else:
                    genai.configure(api_key=api_key, transport="rest", client_options={'api_endpoint': base_url})

                generation_config = {
                    "temperature": 0.5,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 2048,
                }

                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_ONLY_HIGH",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_ONLY_HIGH",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_ONLY_HIGH",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_ONLY_HIGH",
                    },
                ]

                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )

                try:
                    response = model.generate_content(prompt)
                    candidates = response.candidates
                    generated_text = candidates[0].content.parts[0].text
                except (AttributeError, IndexError) as e:
                    logger.warning(
                        f"gemini returned invalid response content: {str(e)}"
                    )
                    raise ValueError(
                        f"[{llm_provider}] returned invalid response content"
                    )

                return _normalize_text_response(generated_text, llm_provider)

            if llm_provider == "cloudflare":
                response = requests.post(
                    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a friendly assistant",
                            },
                            {"role": "user", "content": prompt},
                        ]
                    },
                )
                result = response.json()
                logger.info(result)
                return _normalize_text_response(result["result"]["response"], llm_provider)

            if llm_provider == "ernie":
                response = requests.post(
                    "https://aip.baidubce.com/oauth/2.0/token", 
                    params={
                        "grant_type": "client_credentials",
                        "client_id": api_key,
                        "client_secret": secret_key,
                    }
                )
                access_token = response.json().get("access_token")
                url = f"{base_url}?access_token={access_token}"

                payload = json.dumps(
                    {
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                        "top_p": 0.8,
                        "penalty_score": 1,
                        "disable_search": False,
                        "enable_citation": False,
                        "response_format": "text",
                    }
                )
                headers = {"Content-Type": "application/json"}

                response = requests.request(
                    "POST", url, headers=headers, data=payload
                ).json()
                return _normalize_text_response(response.get("result"), llm_provider)

            if llm_provider == "anthropic":
                import litellm

                if not api_key:
                    raise ValueError(
                        f"{llm_provider}: api_key is not set, please set it in the config.toml file."
                    )
                if not model_name:
                    raise ValueError(
                        f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                    )

                anthropic_model = _anthropic_litellm_model_id(model_name)
                logger.info(f"requesting anthropic chat completion, model: {anthropic_model}")

                response = litellm.completion(
                    model=anthropic_model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=api_key,
                    drop_params=True,
                )

                if not response:
                    raise ValueError(f"[{llm_provider}] returned empty response")
                if not getattr(response, "choices", None):
                    raise ValueError(f"[{llm_provider}] returned empty response")

                return _extract_chat_completion_text(response, llm_provider)

            if llm_provider == "litellm":
                import litellm

                if not model_name:
                    raise ValueError(
                        f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                    )

                response = litellm.completion(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    drop_params=True,
                )

                if not response:
                    raise ValueError(f"[{llm_provider}] returned empty response")
                if not getattr(response, "choices", None):
                    raise ValueError(f"[{llm_provider}] returned empty response")

                return _extract_chat_completion_text(response, llm_provider)

            if llm_provider == "bedrock":
                if not model_name:
                    raise ValueError(
                        f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                    )

                if is_bedrock_mantle_responses_model(model_name):
                    return _bedrock_mantle_responses(prompt, model_name)

                import litellm

                bedrock_model = _bedrock_litellm_model_id(
                    normalize_bedrock_model_name(model_name)
                )
                bedrock_kwargs = _bedrock_litellm_kwargs()
                logger.info(
                    f"requesting bedrock chat completion, model: {bedrock_model}, "
                    f"region: {bedrock_kwargs.get('aws_region_name')}"
                )

                response = litellm.completion(
                    model=bedrock_model,
                    messages=[{"role": "user", "content": prompt}],
                    **bedrock_kwargs,
                )

                if not response:
                    raise ValueError(f"[{llm_provider}] returned empty response")
                if not getattr(response, "choices", None):
                    raise ValueError(f"[{llm_provider}] returned empty response")

                return _extract_chat_completion_text(response, llm_provider)

            if llm_provider in {"litellm", "bedrock", "anthropic"}:
                raise ValueError(
                    f"{llm_provider}: request did not complete; check model name and credentials."
                )

            if llm_provider == "azure":
                # Azure OpenAI SDK 使用 `azure_endpoint` 和 `api_version` 生成专用请求地址，
                # 不能继续复用下面普通 OpenAI-compatible 的 `base_url` 初始化逻辑。
                # 这里在 Azure 分支内完成请求并立即返回，避免客户端被后续 fallback
                # 覆盖，导致用户配置的 Azure 凭证通过校验但实际请求没有被使用。
                logger.info(f"requesting azure chat completion, model: {model_name}")
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=base_url,
                )
                response = client.chat.completions.create(
                    model=model_name, messages=[{"role": "user", "content": prompt}]
                )
                if response:
                    if isinstance(response, ChatCompletion):
                        return _extract_chat_completion_text(response, llm_provider)
                    else:
                        raise Exception(
                            f'[{llm_provider}] returned an invalid response: "{response}", please check your network '
                            f"connection and try again."
                        )
                else:
                    raise Exception(
                        f"[{llm_provider}] returned an empty response, please check your network connection and try again."
                    )

            if llm_provider == "modelscope":
                content = ''
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    extra_body={"enable_thinking": False},
                    stream=True
                )
                if response:
                    for chunk in response:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            content += delta.content
                    
                    if not content.strip():
                        raise ValueError("Empty content in stream response")
                    
                    return _normalize_text_response(content, llm_provider)
                else:
                    raise Exception(f"[{llm_provider}] returned an empty response")

            else:
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )

            response = client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": prompt}]
            )
            if response:
                if isinstance(response, ChatCompletion):
                    return _extract_chat_completion_text(response, llm_provider)
                else:
                    raise Exception(
                        f'[{llm_provider}] returned an invalid response: "{response}", please check your network '
                        f"connection and try again."
                    )
            else:
                raise Exception(
                    f"[{llm_provider}] returned an empty response, please check your network connection and try again."
                )

        return _normalize_text_response(content, llm_provider)
    except Exception as e:
        return f"Error: {str(e)}"


def _limit_script_text(text: str | None, max_length: int, field_name: str) -> str:
    value = (text or "").strip()
    if len(value) <= max_length:
        return value

    # API 层已经用 Pydantic 做长度校验；这里继续兜底，是为了保护
    # WebUI 或内部服务直接调用 generate_script 时不会把超长提示词发送给模型，
    # 避免 token 成本异常和请求失败。
    logger.warning(
        f"{field_name} is too long and will be truncated to {max_length} characters."
    )
    return value[:max_length]


def _normalize_script_paragraph_number(paragraph_number: int | None) -> int:
    try:
        value = int(paragraph_number or MIN_SCRIPT_PARAGRAPH_NUMBER)
    except (TypeError, ValueError):
        value = MIN_SCRIPT_PARAGRAPH_NUMBER

    if value < MIN_SCRIPT_PARAGRAPH_NUMBER or value > MAX_SCRIPT_PARAGRAPH_NUMBER:
        # WebUI 和 API 都会限制范围；这里兜底处理内部调用，避免异常参数直接扩大
        # LLM 生成成本或生成空结果。
        logger.warning(
            "script paragraph_number is out of range and will be clamped: "
            f"{value}"
        )
        return max(MIN_SCRIPT_PARAGRAPH_NUMBER, min(value, MAX_SCRIPT_PARAGRAPH_NUMBER))

    return value


def build_script_prompt(
    video_subject: str,
    language: str = "",
    paragraph_number: int = 1,
    video_script_prompt: str = "",
    custom_system_prompt: str = "",
) -> str:
    paragraph_number = _normalize_script_paragraph_number(paragraph_number)
    video_script_prompt = _limit_script_text(
        video_script_prompt, MAX_SCRIPT_PROMPT_LENGTH, "video_script_prompt"
    )
    custom_system_prompt = _limit_script_text(
        custom_system_prompt, MAX_SCRIPT_SYSTEM_PROMPT_LENGTH, "custom_system_prompt"
    )

    # 将“脚本生成规则”和“运行时上下文”分开拼接。这样高级用户即使覆盖默认
    # system prompt，也不会漏掉视频主题、语言、段落数这些每次生成都必须带上的参数。
    prompt = custom_system_prompt or DEFAULT_SCRIPT_SYSTEM_PROMPT
    prompt += f"""

# Initialization:
- video subject: {video_subject}
- number of paragraphs: {paragraph_number}
""".rstrip()
    if language:
        prompt += f"\n- language: {language}"
    if video_script_prompt:
        prompt += f"""

# Additional User Requirements:
{video_script_prompt}
""".rstrip()

    return prompt


def generate_script(
    video_subject: str,
    language: str = "",
    paragraph_number: int = 1,
    video_script_prompt: str = "",
    custom_system_prompt: str = "",
) -> str:
    paragraph_number = _normalize_script_paragraph_number(paragraph_number)
    video_script_prompt = _limit_script_text(
        video_script_prompt, MAX_SCRIPT_PROMPT_LENGTH, "video_script_prompt"
    )
    custom_system_prompt = _limit_script_text(
        custom_system_prompt, MAX_SCRIPT_SYSTEM_PROMPT_LENGTH, "custom_system_prompt"
    )
    prompt = build_script_prompt(
        video_subject=video_subject,
        language=language,
        paragraph_number=paragraph_number,
        video_script_prompt=video_script_prompt,
        custom_system_prompt=custom_system_prompt,
    )
    final_script = ""
    logger.info(
        "generating video script: "
        f"subject={video_subject}, paragraph_number={paragraph_number}, "
        f"has_custom_prompt={bool(video_script_prompt.strip())}, "
        f"has_custom_system_prompt={bool(custom_system_prompt.strip())}"
    )

    def format_response(response):
        # Clean the script
        # Remove asterisks, hashes
        response = response.replace("*", "")
        response = response.replace("#", "")

        # Remove markdown syntax
        response = re.sub(r"\[.*\]", "", response)
        response = re.sub(r"\(.*\)", "", response)

        # Split the script into paragraphs
        paragraphs = response.split("\n\n")

        # Select the specified number of paragraphs
        # selected_paragraphs = paragraphs[:paragraph_number]

        # Join the selected paragraphs into a single string
        return "\n\n".join(paragraphs)

    for i in range(_max_retries):
        try:
            response = _generate_response(prompt=prompt)
            if response:
                final_script = format_response(response)
            else:
                logging.error("gpt returned an empty response")

            # g4f may return an error message
            if final_script and "当日额度已消耗完" in final_script:
                raise ValueError(final_script)

            if final_script:
                break
        except Exception as e:
            logger.error(f"failed to generate script: {e}")

        if i < _max_retries:
            logger.warning(f"failed to generate video script, trying again... {i + 1}")
    if "Error: " in final_script:
        logger.error(f"failed to generate video script: {final_script}")
    else:
        logger.success(f"completed: \n{final_script}")
    return final_script.strip()


def polish_script(
    brief: str,
    video_subject: str = "",
    duration_seconds: int = 60,
    language: str = "",
) -> str:
    """Turn a rough brief into hook → body → CTA narration."""
    brief = (brief or "").strip()
    if not brief:
        raise ValueError("empty polish output")

    subject = (video_subject or "").strip()
    lang_hint = language or "same language as the brief"
    prompt = f"""
You are a short-form video scriptwriter.

Turn the creator brief below into a polished voiceover with:
1) a provocative hook (1-2 sentences)
2) a concise body with one concrete detail
3) a single clear CTA

Constraints:
- Keep the same language as the brief ({lang_hint})
- Target about {duration_seconds} seconds spoken (~{max(40, duration_seconds * 2)} words)
- Do not use markdown, bullets, or scene labels
- Preserve factual claims from the brief

Subject context (optional): {subject or "none"}

Brief:
{brief}
""".strip()

    response = _generate_response(prompt=prompt)
    polished = (response or "").replace("*", "").replace("#", "").strip()
    if not polished:
        raise ValueError("empty polish output")
    return polished


def _parse_generated_terms_response(
    response: str,
) -> NormalizedCollectorKeywords | None:
    if not response:
        return None
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\[.*]", response, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, list) or not parsed:
        return None

    if all(isinstance(item, str) for item in parsed):
        return normalize_collector_keywords(parsed)

    if all(isinstance(item, dict) for item in parsed):
        if not all(str(item.get("term", "")).strip() for item in parsed):
            return None
        return normalize_collector_keywords(parsed)

    return None


_WEIGHTED_TERMS_OUTPUT_RULES = """
Return only a JSON array of objects with this shape:
[
  { "term": "main visual topic", "weight": 1.0 },
  { "term": "supporting scene", "weight": 0.7 }
]

Weight rules:
- Use English search terms only.
- Each term should contain 1-5 words and be searchable on stock footage sites.
- weight must be between 0.0 and 1.0.
- 1.0 = primary editorial keyword.
- 0.7-0.9 = strong supporting visuals.
- 0.4-0.6 = optional B-roll / context.
- Weights are relative; they do not need to sum to 1.0.
""".strip()


def generate_terms(
    video_subject: str,
    video_script: str,
    amount: int = 5,
    match_script_order: bool = False,
) -> Union[NormalizedCollectorKeywords, str]:
    if match_script_order:
        goal = (
            f"Generate {amount} chronological stock-video search terms that follow "
            "the order of topics in the video script."
        )
        ordering_rule = (
            "Keep the terms in the same order as the script narration; "
            "earlier terms must describe earlier visual moments."
        )
        output_example = json.dumps(
            [
                {"term": "opening visual topic", "weight": 1.0},
                {"term": "middle script visual topic", "weight": 0.85},
                {"term": "final visual topic", "weight": 0.7},
            ][:amount],
            ensure_ascii=False,
        )
        prompt = f"""
# Role: Video Search Terms Generator

## Goals:
{goal}

## Constraints:
1. Return only a JSON array of objects with `term` and `weight`.
2. Each search term should consist of 1-5 words and include the main subject when relevant.
3. Do not return anything else besides the JSON array.
4. The search terms must be related to the subject of the video.
5. {ordering_rule}

{_WEIGHTED_TERMS_OUTPUT_RULES}

## Output Example:
{output_example}

## Context:
### Video Subject
{video_subject}

### Video Script
{video_script}
""".strip()
    else:
        prompt = f"""
# Role

Stock Footage Search Terms Generator

# Goal

Generate high-quality stock footage search terms that maximize visual coverage of the entire video.

The goal is not simply to describe the topic, but to help find diverse and relevant footage for platforms such as Pexels, Pixabay, Coverr, Storyblocks and Shutterstock.

# Rules

1. Generate exactly {amount} search terms.
2. Use both the video subject and the video script.
3. If the subject contains a specific food, place, landmark, object, animal, product or named entity, the highest-weight term must be the exact entity name.
4. Do not focus exclusively on the main subject.
5. Include supporting visual scenes that naturally appear in the script.
6. Prioritize footage that is likely to exist in stock libraries.

# Coverage Requirements

Generate a balanced mix of:

- Main subject footage
- Locations
- Environments
- People
- Activities
- Supporting B-roll

Generate:

- 1 subject term
- 1 location/environment term
- 1 people term
- 1 activity term
- 1 supporting context term

# Avoid

Do not generate:

- Abstract concepts
- Emotions
- Explanations
- Cultural theories
- Social values
- Opinions
- Facts that cannot be visually filmed

For abstract or cultural topics, prioritize modern everyday scenes.

Use scenes that people can actually film in daily life.

Avoid symbolic representations unless explicitly mentioned in the script.

# Good Search Terms

- Tokyo street
- Japan train station
- Japanese neighborhood
- People using vending machines
- Bullet train Japan
- Sushi restaurant
- Office workers Japan
- Japanese countryside
- Taiyaki
- Mount Fuji
- Fushimi Inari

# Bad Search Terms

- Japanese efficiency
- High trust society
- Convenience culture
- Social behavior
- Work ethic
- Japanese culture
- Social harmony
- Zen meditation
- Temple spirituality
- Nature sounds

{_WEIGHTED_TERMS_OUTPUT_RULES}

# Context

## Video Subject
{video_subject}

## Video Script
{video_script}

# Output Example

[
  {{ "term": "Tokyo street", "weight": 1.0 }},
  {{ "term": "Japan train station", "weight": 0.85 }},
  {{ "term": "Japanese neighborhood", "weight": 0.75 }},
  {{ "term": "People using vending machines", "weight": 0.65 }},
  {{ "term": "Japanese countryside", "weight": 0.5 }}
]
""".strip()

    logger.info(
        f"subject: {video_subject}, match_script_order: {match_script_order}"
    )

    search_terms: NormalizedCollectorKeywords | None = None
    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if "Error: " in response:
                logger.error(f"failed to generate video script: {response}")
                return response
            search_terms = _parse_generated_terms_response(response)
            if search_terms is None:
                logger.error("response is not a valid weighted keyword list.")
                continue

        except Exception as e:
            logger.warning(f"failed to generate video terms: {str(e)}")
            if response:
                search_terms = _parse_generated_terms_response(response)

        if search_terms and search_terms.keywords:
            break
        if i < _max_retries:
            logger.warning(f"failed to generate video terms, trying again... {i + 1}")

    if not search_terms or not search_terms.keywords:
        return "Error: failed to generate video terms."

    logger.success(
        f"completed: \n{[keyword.model_dump() for keyword in search_terms.keywords]}"
    )
    return search_terms


# =============================================================================
# Social publishing metadata
#
# 根据视频主题和脚本生成发布到短视频平台时常用的 title、caption 和 hashtags。
# 这块能力只复用现有 LLM provider，不接入任何外部发布服务，也不影响视频生成主链路。
# =============================================================================

# 不同平台的文案长度和 hashtag 数量偏好不同。这里使用保守上限，避免模型返回
# 过长内容后调用方还需要二次裁剪。
SOCIAL_PLATFORMS = {
    "tiktok": {"title_max": 100, "caption_max": 2200, "hashtag_count": 5},
    "youtube_shorts": {"title_max": 100, "caption_max": 5000, "hashtag_count": 3},
    "instagram_reels": {"title_max": 125, "caption_max": 2200, "hashtag_count": 8},
    "facebook_reels": {"title_max": 125, "caption_max": 2200, "hashtag_count": 5},
}
DEFAULT_SOCIAL_PLATFORM = "tiktok"
DEFAULT_SOCIAL_LANGUAGE = "auto"
MAX_SOCIAL_SUBJECT_LENGTH = 500
MAX_SOCIAL_SCRIPT_LENGTH = 8000
MAX_SOCIAL_LANGUAGE_LENGTH = 64

SOCIAL_PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "youtube_shorts": "YouTube Shorts",
    "instagram_reels": "Instagram Reels",
    "facebook_reels": "Facebook Reels",
}

# LLM 不可用时的通用兜底标签。这里故意不绑定某个国家或语种，保证 API
# 对中文、英文、越南语等不同场景都能返回可用结构。
DEFAULT_SOCIAL_HASHTAGS = [
    "#shorts",
    "#viral",
    "#trending",
    "#fyp",
    "#video",
    "#reels",
    "#creator",
    "#content",
]


def _resolve_social_platform(platform: str | None) -> str:
    value = (platform or "").strip().lower()
    return value if value in SOCIAL_PLATFORMS else DEFAULT_SOCIAL_PLATFORM


def _normalize_social_language(language: str | None) -> str:
    value = (language or DEFAULT_SOCIAL_LANGUAGE).strip()
    if len(value) > MAX_SOCIAL_LANGUAGE_LENGTH:
        logger.warning(
            "social metadata language is too long and will be truncated to "
            f"{MAX_SOCIAL_LANGUAGE_LENGTH} characters."
        )
        value = value[:MAX_SOCIAL_LANGUAGE_LENGTH]
    return value or DEFAULT_SOCIAL_LANGUAGE


def _limit_social_text(text: str | None, max_length: int, field_name: str) -> str:
    value = (text or "").strip()
    if len(value) <= max_length:
        return value

    # API 层会限制长度；这里继续兜底，是为了保护内部调用或未来 WebUI
    # 直接调用时不会把超长内容发送给模型，避免 token 成本异常。
    logger.warning(
        f"{field_name} is too long and will be truncated to {max_length} characters."
    )
    return value[:max_length]


def _social_language_instruction(language: str | None) -> str:
    language = _normalize_social_language(language)
    if language.lower() == DEFAULT_SOCIAL_LANGUAGE:
        return (
            "Use the same language as the video subject and script. If the subject "
            "and script use different languages, prefer the script language."
        )

    return f'Write "title" and "caption" in this language: {language}.'


def _clamp_text(text, max_length: int) -> str:
    value = ("" if text is None else str(text)).strip()
    if max_length and len(value) > max_length:
        return value[:max_length].rstrip()
    return value


def _normalize_hashtags(raw, count: int) -> List[str]:
    """
    将 LLM 返回的 hashtag 统一整理成 `#tag` 格式。

    LLM 可能返回字符串、数组、带空格的词组、重复标签或包含标点的内容。
    这里集中清洗，可以让接口响应结构稳定，也避免平台发布时出现空标签、
    重复标签或不符合常见格式的 hashtag。
    """
    if isinstance(raw, str):
        candidates = re.split(r"[\s,]+", raw)
    elif isinstance(raw, (list, tuple)):
        # 数组里的每一项视为一个完整标签，因此 "du lich" 会变成
        # "#dulich"，而不是拆成两个标签。
        candidates = [str(entry) for entry in raw]
    else:
        candidates = []

    seen = set()
    result: List[str] = []
    for item in candidates:
        tag = re.sub(r"[^\w]", "", item, flags=re.UNICODE)
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(f"#{tag}")
        if count and len(result) >= count:
            break
    return result


def build_social_metadata_prompt(
    video_subject: str,
    video_script: str = "",
    language: str = DEFAULT_SOCIAL_LANGUAGE,
    platform: str = DEFAULT_SOCIAL_PLATFORM,
) -> str:
    video_subject = _limit_social_text(
        video_subject, MAX_SOCIAL_SUBJECT_LENGTH, "video_subject"
    )
    video_script = _limit_social_text(
        video_script, MAX_SOCIAL_SCRIPT_LENGTH, "video_script"
    )
    platform = _resolve_social_platform(platform)
    spec = SOCIAL_PLATFORMS[platform]
    label = SOCIAL_PLATFORM_LABELS.get(platform, platform)
    language_instruction = _social_language_instruction(language)

    prompt = f"""
# Role: Short-Video Social Media Copywriter

## Goal
Write engaging publishing metadata for a short video that will be posted on {label}.

## Constraints
1. Respond ONLY with a single valid minified JSON object. No markdown, no code fences, no commentary.
2. The JSON must contain exactly these keys: "title", "caption", "hashtags".
3. "title": a catchy hook, at most {spec['title_max']} characters.
4. "caption": an engaging description that ends with a call to action, at most {spec['caption_max']} characters. Do not put hashtags inside the caption.
5. "hashtags": a JSON array of exactly {spec['hashtag_count']} strings. Each must start with "#", contain no spaces, and be relevant to the topic and to {label}.
6. {language_instruction}

## Output Example
{{"title":"...","caption":"...","hashtags":["#example","#video"]}}

## Context
### Video Subject
{video_subject}

### Video Script
{video_script}
""".strip()
    return prompt


def _parse_social_metadata(response: str, platform: str) -> dict:
    spec = SOCIAL_PLATFORMS[_resolve_social_platform(platform)]

    data = None
    try:
        data = json.loads(response)
    except Exception:
        # 部分模型会在 JSON 外层包一段说明文字或 markdown fence。
        # API 调用方只需要稳定结构，所以这里尝试提取第一个 JSON object。
        match = re.search(r"\{.*\}", response or "", re.DOTALL)
        if match:
            data = json.loads(match.group())

    if not isinstance(data, dict):
        raise ValueError("social metadata response is not a JSON object")

    title = _clamp_text(data.get("title", ""), spec["title_max"])
    caption = _clamp_text(data.get("caption", ""), spec["caption_max"])
    hashtags = _normalize_hashtags(data.get("hashtags", []), spec["hashtag_count"])

    if not title and not caption:
        raise ValueError("social metadata response is missing both title and caption")

    return {"title": title, "caption": caption, "hashtags": hashtags}


def _fallback_social_metadata(
    video_subject: str, video_script: str, platform: str
) -> dict:
    spec = SOCIAL_PLATFORMS[_resolve_social_platform(platform)]
    subject = (video_subject or "").strip()
    script = (video_script or "").strip()

    title = subject
    if not title and script:
        # 没有主题时，用脚本第一句兜底生成 title，避免接口返回空标题。
        title = re.split(r"(?<=[.!?。！？])\s+", script)[0]

    return {
        "title": _clamp_text(title, spec["title_max"]),
        "caption": _clamp_text(script or subject, spec["caption_max"]),
        "hashtags": _normalize_hashtags(
            DEFAULT_SOCIAL_HASHTAGS, spec["hashtag_count"]
        ),
    }


def generate_social_metadata(
    video_subject: str,
    video_script: str = "",
    language: str = DEFAULT_SOCIAL_LANGUAGE,
    platform: str = DEFAULT_SOCIAL_PLATFORM,
) -> dict:
    """
    生成短视频发布文案元数据。

    返回结构固定为 `{"title": str, "caption": str, "hashtags": List[str]}`。
    如果 LLM 不可用或返回格式异常，会降级为通用启发式结果，保证 API
    调用方始终拿到可展示、可发布前编辑的数据结构。
    """
    platform = _resolve_social_platform(platform)
    language = _normalize_social_language(language)
    video_subject = _limit_social_text(
        video_subject, MAX_SOCIAL_SUBJECT_LENGTH, "video_subject"
    )
    video_script = _limit_social_text(
        video_script, MAX_SOCIAL_SCRIPT_LENGTH, "video_script"
    )
    prompt = build_social_metadata_prompt(
        video_subject=video_subject,
        video_script=video_script,
        language=language,
        platform=platform,
    )
    logger.info(
        f"generating social metadata: platform={platform}, language={language}"
    )

    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if isinstance(response, str) and "Error: " in response:
                logger.error(f"failed to generate social metadata: {response}")
                break
            metadata = _parse_social_metadata(response, platform)
            logger.success(f"completed: \n{metadata}")
            return metadata
        except Exception as e:
            logger.warning(f"failed to parse social metadata: {str(e)}")

        if i < _max_retries - 1:
            logger.warning(
                f"failed to generate social metadata, trying again... {i + 1}"
            )

    logger.warning("falling back to heuristic social metadata")
    return _fallback_social_metadata(video_subject, video_script, platform)


if __name__ == "__main__":
    video_subject = "生命的意义是什么"
    script = generate_script(
        video_subject=video_subject, language="zh-CN", paragraph_number=1
    )
    print("######################")
    print(script)
    search_terms = generate_terms(
        video_subject=video_subject, video_script=script, amount=5
    )
    print("######################")
    print(search_terms)
    
