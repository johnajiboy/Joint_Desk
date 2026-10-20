"""The single place that calls the LLM (Anthropic API only).

complete_json() sends one letter-reading request and returns the arguments Claude
passed to a strict tool built from a pydantic JSON schema. It only reads; the pathway
is decided by rules.py. Caching (DEMO_MODE) and the quote check live in extract.py;
each cache file records model_name() so every result can be traced to the model that read it.
No fallback model: every letter is read by the one configured model.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import anthropic
from anthropic import transform_schema
from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5-5"
TOOL_NAME = "record_facts"
MAX_TOKENS = 16000
ATTEMPTS = 2  # tool_choice "auto" doesn't guarantee a call, so retry once

# Forced tool_choice is rejected on current models, so the prompt asks for the tool instead.
_USE_TOOL = f"Record your answer by calling the {TOOL_NAME} tool exactly once. Do not reply in text."


class LLMError(RuntimeError):
    """The model gave no usable structured answer."""


def model_name() -> str:
    """The model in use: CLAUDE_MODEL from .env, else DEFAULT_MODEL."""
    load_dotenv()
    return os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_MODEL


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    load_dotenv()
    if os.environ.get("ANTHROPIC_API_KEY", "").strip() in ("", "your-key-here"):
        raise LLMError("ANTHROPIC_API_KEY is not set in .env")
    return anthropic.Anthropic()


def complete_json(system: str, prompt: str, schema: dict) -> dict:
    """Ask Claude to fill `schema` (e.g. Model.model_json_schema()) from `prompt`.

    Returns the tool input as a dict. Validate it with the pydantic model afterwards:
    constraints the API can't enforce (min/max, lengths) are only described to it.
    """
    tool = {
        "name": TOOL_NAME,
        "description": "Record the facts read from the referral letter.",
        "input_schema": transform_schema(schema),
        "strict": True,
    }
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    model = model_name()

    for _ in range(ATTEMPTS):
        response = _client().messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            # The tool and system prompt are the same for every letter, so cache them.
            system=[{"type": "text", "text": f"{system}\n\n{_USE_TOOL}", "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=[tool],
            tool_choice={"type": "auto"},
            output_config={"effort": "medium"},
        )

        if response.stop_reason == "refusal":
            raise LLMError(f"{model} declined (request {response._request_id})")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"Answer cut off at max_tokens (request {response._request_id})")

        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                return dict(block.input)

        # No tool call: keep the reply and ask again.
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": _USE_TOOL},
        ]

    raise LLMError(f"No {TOOL_NAME} call after {ATTEMPTS} attempts")
