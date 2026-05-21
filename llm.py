"""Shared LLM SDK helpers with OpenAI and Anthropic provider support."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH_ENV = "LLM_CONFIG_PATH"
DEFAULT_CONFIG_PATH = PROJECT_DIR / "llm_config.json"

DEFAULT_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
API_KEY_ENV = "MY_API_KEY"
BASE_URL_ENV = "MY_BASE_URL"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
ANTHROPIC_BASE_URL_ENV = "ANTHROPIC_BASE_URL"
TIMEOUT_ENV = "MY_LLM_TIMEOUT_SECONDS"
MAX_RETRIES_ENV = "MY_LLM_MAX_RETRIES"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_RETRIES = 0

Message = dict[str, str]


def _provider_config(payload: dict[str, Any], provider: str) -> dict[str, Any]:
    providers = payload.get("providers")
    if isinstance(providers, dict) and isinstance(providers.get(provider), dict):
        return providers[provider]
    nested = payload.get(provider)
    return nested if isinstance(nested, dict) else {}


def _configured_default_model() -> str:
    config_path = Path(os.getenv(CONFIG_PATH_ENV, str(DEFAULT_CONFIG_PATH)))
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            payload = {}
    provider = str(payload.get("provider") or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    provider_payload = _provider_config(payload, provider)
    default_model = DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_OPENAI_MODEL
    return str(provider_payload.get("model") or payload.get("model") or os.getenv("LLM_MODEL") or default_model)


DEFAULT_MODEL = _configured_default_model()


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    timeout: float
    max_retries: int


def _read_config_file() -> dict[str, Any]:
    config_path = Path(os.getenv(CONFIG_PATH_ENV, str(DEFAULT_CONFIG_PATH)))
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid LLM config JSON: {config_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"LLM config must be a JSON object: {config_path}")
    return payload


def _config_value(provider_payload: dict[str, Any], root_payload: dict[str, Any], key: str, env_name: str | None = None) -> Any:
    if provider_payload.get(key) not in (None, ""):
        return provider_payload.get(key)
    if root_payload.get(key) not in (None, ""):
        return root_payload.get(key)
    return os.getenv(env_name) if env_name else None


def _required(value: str | None, label: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required LLM configuration: {label}")
    return value


@lru_cache(maxsize=1)
def get_llm_config() -> LlmConfig:
    payload = _read_config_file()
    provider = str(payload.get("provider") or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider not in {"openai", "anthropic"}:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    provider_payload = _provider_config(payload, provider)
    default_model = DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_OPENAI_MODEL
    api_key_env = ANTHROPIC_API_KEY_ENV if provider == "anthropic" else API_KEY_ENV
    base_url_env = ANTHROPIC_BASE_URL_ENV if provider == "anthropic" else BASE_URL_ENV
    model = str(_config_value(provider_payload, payload, "model") or os.getenv("LLM_MODEL") or default_model)
    timeout = float(_config_value(provider_payload, payload, "timeout", TIMEOUT_ENV) or DEFAULT_TIMEOUT_SECONDS)
    max_retries = int(_config_value(provider_payload, payload, "max_retries", MAX_RETRIES_ENV) or DEFAULT_MAX_RETRIES)
    api_key = _config_value(provider_payload, payload, "api_key", api_key_env)
    base_url = _config_value(provider_payload, payload, "base_url", base_url_env)

    return LlmConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
    )


def default_model() -> str:
    return get_llm_config().model


@lru_cache(maxsize=1)
def get_openai_client() -> Any:
    from openai import OpenAI

    config = get_llm_config()
    return OpenAI(
        api_key=_required(config.api_key, "openai.api_key or MY_API_KEY"),
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


@lru_cache(maxsize=1)
def get_anthropic_client() -> Any:
    from anthropic import Anthropic

    config = get_llm_config()
    kwargs: dict[str, Any] = {
        "api_key": _required(config.api_key, "anthropic.api_key or ANTHROPIC_API_KEY"),
        "timeout": config.timeout,
        "max_retries": config.max_retries,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return Anthropic(**kwargs)


def get_llm_client() -> Any:
    """Return a cached SDK client for the configured provider."""
    config = get_llm_config()
    if config.provider == "anthropic":
        return get_anthropic_client()
    return get_openai_client()


def chat_completion(
    messages: Sequence[Message],
    *,
    model: str | None = None,
    **kwargs: Any,
) -> Any:
    """Create a chat completion with the configured LLM provider."""
    config = get_llm_config()
    selected_model = model or config.model
    if config.provider == "anthropic":
        return _anthropic_chat_completion(messages, model=selected_model, **kwargs)
    kwargs.setdefault("timeout", config.timeout)
    return get_openai_client().chat.completions.create(
        model=selected_model,
        messages=list(messages),
        **kwargs,
    )


def _anthropic_chat_completion(
    messages: Sequence[Message],
    *,
    model: str,
    **kwargs: Any,
) -> Any:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            anthropic_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})

    kwargs.pop("response_format", None)
    # 部分代理或推理型模型（如 opus-4-7）拒绝 temperature，统一在此处丢弃。
    kwargs.pop("temperature", None)
    timeout = kwargs.pop("timeout", get_llm_config().timeout)
    max_tokens = kwargs.pop("max_tokens", None) or kwargs.pop("max_completion_tokens", None) or 2048
    if "stream" in kwargs:
        kwargs.pop("stream")

    request: dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
        "timeout": timeout,
        **kwargs,
    }
    if system_parts:
        request["system"] = "\n\n".join(system_parts)

    response = get_anthropic_client().messages.create(**request)
    return _openai_compatible_completion(response)


def _openai_compatible_completion(response: Any) -> Any:
    text_parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    content = "".join(text_parts)
    return SimpleNamespace(
        id=getattr(response, "id", None),
        model=getattr(response, "model", None),
        choices=[
            SimpleNamespace(
                index=0,
                message=SimpleNamespace(role="assistant", content=content),
                finish_reason=getattr(response, "stop_reason", None),
            )
        ],
        usage=getattr(response, "usage", None),
        raw_response=response,
    )


def chat_text(
    messages: Sequence[Message],
    *,
    model: str | None = None,
    **kwargs: Any,
) -> str:
    """Return the first text response from a chat completion."""
    completion = chat_completion(messages, model=model, **kwargs)
    message = completion.choices[0].message
    return message.content or ""


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    body = stripped[3:]
    newline = body.find("\n")
    if newline != -1 and body[:newline].strip().lower() in {"json", ""}:
        body = body[newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body


def _repair_inline_quotes(text: str) -> str:
    """Escape stray double quotes that appear inside JSON string values.

    Walks the text as a JSON state machine. Inside a string, a `"` followed by
    something other than JSON structural punctuation (`,`、`:`、`}`、`]` or EOF)
    is treated as a content quote and escaped, which fixes the common LLM bug
    of emitting `定位"偏弱可规避"` inside a value.
    """
    out: list[str] = []
    n = len(text)
    in_string = False
    i = 0
    while i < n:
        c = text[i]
        if not in_string:
            out.append(c)
            if c == '"':
                in_string = True
            i += 1
            continue
        if c == "\\":
            out.append(c)
            if i + 1 < n:
                out.append(text[i + 1])
                i += 2
            else:
                i += 1
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            next_char = text[j] if j < n else ""
            if next_char in {",", ":", "}", "]", ""}:
                out.append(c)
                in_string = False
                i += 1
            else:
                out.append('\\"')
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_llm_json(content: str) -> dict[str, Any]:
    """Parse LLM output that should be a JSON object, with tolerant fallbacks.

    Falls back to `{"raw_text": content}` only when every recovery attempt
    fails, matching the previous error contract callers expect.
    """
    if not content:
        return {}
    candidates = [content, _strip_code_fence(content)]
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        return {"raw_value": parsed}
    repaired = _repair_inline_quotes(_strip_code_fence(content))
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError:
        return {"raw_text": content}
    if isinstance(parsed, dict):
        return parsed
    return {"raw_value": parsed}
