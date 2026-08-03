import json
import logging

import groq
from groq import Groq

from src.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama-3.3-70b-versatile"
_MAX_ATTEMPTS = 3

_RETRY_NUDGE = (
    "\n\nIMPORTANT: You MUST call the tool with EVERY required property listed in "
    "its schema, using the exact property names given — do not invent or rename "
    "any parameter."
)


def _to_openai_tool(anthropic_tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool.get("description", ""),
            "parameters": anthropic_tool["input_schema"],
        },
    }


def _api_keys() -> list[str]:
    keys = [settings.GROQ_API_KEY]
    fallback = getattr(settings, "GROQ_API_KEY_FALLBACK", "")
    if fallback:
        keys.append(fallback)
    extra = getattr(settings, "GROQ_API_KEY_FALLBACKS", "")
    for key in extra.split(","):
        key = key.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def call_tool(
    system: str,
    tool: dict,
    user_content: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> dict:
    """Drop-in replacement for the old anthropic.Anthropic().messages.create(...)
    forced tool_use pattern used across agents/ — takes the same Anthropic-style
    tool schema ({"name", "description", "input_schema"}) and returns the same
    dict shape that used to come from `dict(tool_block.input)`.

    Retries on schema-validation / malformed-JSON failures — Groq's smaller/faster
    models occasionally invent parameter names on a forced tool call, and a retry
    (optionally with a stronger schema reminder) resolves most of these non-fatally.

    On a rate-limit error, immediately fails over to the next configured key
    (GROQ_API_KEY_FALLBACK, then any comma-separated keys in
    GROQ_API_KEY_FALLBACKS, in order) — retrying won't help a quota error, so
    it switches keys rather than burning attempts. Any number of fallback
    keys can be added via GROQ_API_KEY_FALLBACKS without further code changes.
    """
    fn_name = tool["name"]
    openai_tool = _to_openai_tool(tool)
    keys = _api_keys()

    last_error: Exception | None = None
    for key_index, api_key in enumerate(keys):
        client = Groq(api_key=api_key)
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            active_system = system if attempt == 1 else system + _RETRY_NUDGE
            try:
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": active_system},
                        {"role": "user", "content": user_content},
                    ],
                    tools=[openai_tool],
                    tool_choice={"type": "function", "function": {"name": fn_name}},
                )
                message = response.choices[0].message
                tool_call = message.tool_calls[0]
                return json.loads(tool_call.function.arguments)
            except groq.RateLimitError as e:
                last_error = e
                logger.warning(
                    "call_tool: key %d/%d rate-limited for tool '%s' — %s",
                    key_index + 1, len(keys), fn_name,
                    "failing over to next key" if key_index + 1 < len(keys) else "no more keys",
                )
                break
            except (groq.BadRequestError, json.JSONDecodeError, IndexError, AttributeError) as e:
                last_error = e
                logger.warning(
                    "call_tool: attempt %d/%d failed for tool '%s': %s",
                    attempt, _MAX_ATTEMPTS, fn_name, e,
                )

    raise last_error
