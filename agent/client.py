"""
OpenRouter LLM client for CampaignPilot fallback agent.
Uses the OpenAI SDK pointed at OpenRouter's API.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def get_openrouter_client() -> OpenAI:
    """Create an OpenAI client configured for OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY must be set in .env")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def get_model() -> str:
    """Get the configured model name."""
    return os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
