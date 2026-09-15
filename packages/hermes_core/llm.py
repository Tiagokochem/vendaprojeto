"""Cliente OpenAI opcional (stdlib). Sem key → None."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("hermes_core.llm")


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict | None = None


def configured(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip())


def chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    messages: list[dict] | None = None,
    temperature: float = 0.4,
    max_tokens: int = 400,
    timeout: int = 30,
) -> LLMResult | None:
    if not configured(api_key):
        return None

    payload_messages: list[dict] = [{"role": "system", "content": system}]
    if messages:
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if not content:
                continue
            # Map human → assistant for OpenAI
            if role == "human":
                role = "assistant"
            if role not in ("user", "assistant", "system"):
                continue
            payload_messages.append({"role": role, "content": str(content)[:2000]})
    payload_messages.append({"role": "user", "content": user})

    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": payload_messages,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("OpenAI chat falhou: %s", exc)
        return None

    try:
        text = raw["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    usage = raw.get("usage") or {}
    return LLMResult(
        text=text,
        model=raw.get("model") or model,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        raw=raw,
    )


def parse_json_object(text: str) -> dict | None:
    """Extrai primeiro objeto JSON de uma resposta (com ou sem markdown)."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
