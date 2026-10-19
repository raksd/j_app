from __future__ import annotations

import asyncio
import json
import os
import re
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-5"

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = AsyncAnthropic(api_key=key)
    return _client


def model_name() -> str:
    return os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)


_claude_code_slots = asyncio.Semaphore(2)


def backend_name() -> str:
    return os.environ.get("LLM_BACKEND", "claude_code").strip().lower()


async def _complete_claude_code(system: str, user: str) -> str:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model_name(),
        tools=[],
        max_turns=1,
        setting_sources=[],
        extra_args={"no-session-persistence": None},
    )
    parts: list[str] = []
    async with _claude_code_slots:
        async for msg in query(prompt=user, options=options):
            if isinstance(msg, AssistantMessage):
                parts.extend(b.text for b in msg.content if isinstance(b, TextBlock))
            elif isinstance(msg, ResultMessage) and msg.is_error:
                raise RuntimeError(f"Claude Code login failed or hit its usage limit: {msg.result}")
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Claude Code returned no text")
    return text


async def complete_text(system: str, user: str, max_tokens: int = 2000) -> str:
    if backend_name() == "claude_code":
        try:
            return await _complete_claude_code(system, user)
        except Exception:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise
    resp = await _get_client().messages.create(
        model=model_name(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


async def complete_json(system: str, user: str, schema: type[T], max_tokens: int = 4000) -> T:
    """Ask for JSON matching `schema`; retries once with the validation error."""
    schema_json = json.dumps(schema.model_json_schema())
    sys_prompt = (
        f"{system}\n\nRespond with ONLY a JSON object matching this JSON Schema, "
        f"no prose:\n{schema_json}"
    )
    prompt = user
    last_err: Exception | None = None
    for _ in range(2):
        text = await complete_text(sys_prompt, prompt, max_tokens=max_tokens)
        try:
            return schema.model_validate_json(_extract_json(text))
        except Exception as err:  # noqa: BLE001
            last_err = err
            prompt = f"{user}\n\nYour previous reply was invalid ({err}). Return valid JSON only."
    raise ValueError(f"LLM did not return valid JSON: {last_err}")
