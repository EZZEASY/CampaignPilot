"""
Agentic conversation loop for the Python fallback agent.
Uses OpenRouter via the OpenAI SDK with tool calling.
"""

import json

from agent.client import get_openrouter_client, get_model
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DEFINITIONS, dispatch_tool


def run_conversation(
    user_message: str,
    history: list[dict] | None = None,
    max_tool_rounds: int = 10,
) -> tuple[str, list[dict]]:
    """
    Run an agentic conversation turn.

    Args:
        user_message: The user's input message.
        history: Prior conversation messages (mutated in-place).
        max_tool_rounds: Max consecutive tool-calling rounds before forcing a text reply.

    Returns:
        (assistant_reply, updated_history)
    """
    client = get_openrouter_client()
    model = get_model()

    if history is None:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]

    history.append({"role": "user", "content": user_message})

    for _ in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=model,
            messages=history,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # Append assistant message to history
        history.append(msg.model_dump(exclude_none=True))

        # If no tool calls, we have the final text reply
        if not msg.tool_calls:
            return msg.content or "", history

        # Process tool calls
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            result = dispatch_tool(fn_name, fn_args)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # If we exhausted tool rounds, ask for a summary
    history.append({
        "role": "user",
        "content": "Please summarize your findings based on the data you've gathered.",
    })
    response = client.chat.completions.create(
        model=model,
        messages=history,
    )
    reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    return reply, history
