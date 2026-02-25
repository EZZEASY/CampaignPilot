"""
CLI entry point for CampaignPilot agent.

Auto-detects mode:
  - If KIBANA_URL is set → Agent Builder converse API
  - Otherwise → OpenRouter fallback agent

Usage:
    python -m agent.cli
    python -m agent.cli --openrouter   # Force OpenRouter mode
"""

import argparse
import os
import sys

from dotenv import load_dotenv
import requests

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def chat_agent_builder(message: str, conversation_id: str | None = None) -> tuple[str, str]:
    """Send a message via Agent Builder converse API."""
    kibana_url = os.environ.get("KIBANA_URL", "").rstrip("/")
    api_key = os.environ.get("KIBANA_API_KEY", "")

    # Find agent ID
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }

    resp = requests.get(f"{kibana_url}/api/agent_builder/agents", headers=headers, timeout=10)
    if resp.status_code != 200:
        return f"ERROR: Failed to list agents (HTTP {resp.status_code})", ""
    resp_data = resp.json()
    agents = resp_data.get("results", []) if isinstance(resp_data, dict) else resp_data or []
    agent_id = None
    for a in agents:
        if a.get("name") == "CampaignPilot":
            agent_id = a.get("id")
            break

    if not agent_id:
        return "ERROR: CampaignPilot agent not found in Agent Builder.", ""

    body = {"input": message, "agent_id": agent_id}
    if conversation_id:
        body["conversation_id"] = conversation_id

    resp = requests.post(
        f"{kibana_url}/api/agent_builder/converse",
        headers=headers,
        json=body,
        timeout=120,
    )

    if resp.status_code != 200:
        return f"ERROR: Agent Builder returned {resp.status_code}: {resp.text[:300]}", ""

    data = resp.json()

    # Robustly extract text reply: try common key paths
    reply = None
    for key in ("response", "message", "output", "text", "content"):
        val = data.get(key)
        if isinstance(val, str):
            reply = val
            break
        if isinstance(val, dict):
            for inner_key in ("content", "message", "text", "response"):
                inner = val.get(inner_key)
                if isinstance(inner, str):
                    reply = inner
                    break
            if reply:
                break

    if not reply:
        reply = str(data)

    # Clean literal \n (API sometimes returns escaped newlines)
    reply = reply.replace("\\n", "\n")

    conv_id = data.get("conversation_id", conversation_id or "")
    return reply, conv_id


def run_interactive(mode: str):
    """Run interactive chat loop."""
    print("=" * 60)
    print(f"CampaignPilot Agent ({mode} mode)")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    history = None
    conversation_id = None

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if mode == "agent_builder":
            reply, conversation_id = chat_agent_builder(user_input, conversation_id)
        else:
            from agent.loop import run_conversation
            reply, history = run_conversation(user_input, history)

        print(f"\nCampaignPilot: {reply}\n")


def main():
    parser = argparse.ArgumentParser(description="CampaignPilot Agent CLI")
    parser.add_argument("--openrouter", action="store_true", help="Force OpenRouter mode")
    args = parser.parse_args()

    kibana_url = os.environ.get("KIBANA_URL", "").strip()
    kibana_key = os.environ.get("KIBANA_API_KEY", "").strip()

    if args.openrouter or not kibana_url or not kibana_key:
        mode = "openrouter"
        # Validate OpenRouter key exists
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("ERROR: OPENROUTER_API_KEY must be set in .env")
            sys.exit(1)
    else:
        mode = "agent_builder"

    run_interactive(mode)


if __name__ == "__main__":
    main()
