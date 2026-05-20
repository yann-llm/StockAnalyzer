"""Shared OpenAI SDK helpers for LLM calls."""

from __future__ import annotations

import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from openai import OpenAI

DEFAULT_MODEL = "gpt-5.5"
API_KEY_ENV = "MY_API_KEY"
BASE_URL_ENV = "MY_BASE_URL"
TIMEOUT_ENV = "MY_LLM_TIMEOUT_SECONDS"
MAX_RETRIES_ENV = "MY_LLM_MAX_RETRIES"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_RETRIES = 0

Message = dict[str, str]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    """Return a cached OpenAI client configured from environment variables."""
    return OpenAI(
        api_key=_required_env(API_KEY_ENV),
        base_url=_required_env(BASE_URL_ENV),
        timeout=float(os.getenv(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS)),
        max_retries=int(os.getenv(MAX_RETRIES_ENV, DEFAULT_MAX_RETRIES)),
    )


def chat_completion(
    messages: Sequence[Message],
    *,
    model: str = DEFAULT_MODEL,
    **kwargs: Any,
) -> Any:
    """Create a chat completion with the shared OpenAI client."""
    kwargs.setdefault("timeout", float(os.getenv(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS)))
    return get_llm_client().chat.completions.create(
        model=model,
        messages=list(messages),
        **kwargs,
    )


def chat_text(
    messages: Sequence[Message],
    *,
    model: str = DEFAULT_MODEL,
    **kwargs: Any,
) -> str:
    """Return the first text response from a chat completion."""
    completion = chat_completion(messages, model=model, **kwargs)
    message = completion.choices[0].message
    return message.content or ""
