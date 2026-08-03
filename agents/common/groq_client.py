import json

from groq import Groq

from src.config import settings

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _to_openai_tool(anthropic_tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool.get("description", ""),
            "parameters": anthropic_tool["input_schema"],
        },
    }


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
    """
    client = Groq(api_key=settings.GROQ_API_KEY)
    fn_name = tool["name"]
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        tools=[_to_openai_tool(tool)],
        tool_choice={"type": "function", "function": {"name": fn_name}},
    )
    message = response.choices[0].message
    tool_call = message.tool_calls[0]
    return json.loads(tool_call.function.arguments)
