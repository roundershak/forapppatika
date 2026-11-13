"""Claude çağrıları için ortak yardımcı (JSON şemalı yanıt, görsel desteği)."""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

MODEL = os.environ.get("KICKCLIP_MODEL", "claude-opus-5-5")


def available() -> bool:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def image_block(jpeg: bytes) -> dict:
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.standard_b64encode(jpeg).decode("ascii")}}


def ask_json(system: str, content: list | str, schema: dict, effort: str = "medium",
             max_tokens: int = 16000, model: Optional[str] = None) -> dict:
    """Claude'a sorar, şemaya uygun JSON döndürür. Hata durumunda RuntimeError."""
    import anthropic
    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=model or MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model isteği reddetti")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("yanıt yarıda kesildi")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)
