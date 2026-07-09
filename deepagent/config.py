"""Environment/config loading and LLM client factory for the Deep Agent."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None
LLM_API_KEY = os.getenv("LLM_API_KEY") or "sk-not-set"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Optional: powers the hero_images_skill (real on-topic photos instead of gradient
# placeholders). Pipeline runs fine without it -- the skill just skips itself.
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY") or None

WORKSPACE_ROOT = ROOT_DIR / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)


def get_llm(temperature: float = 0.6) -> ChatOpenAI:
    """Build a chat client against the configured OpenAI-compatible proxy."""
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        temperature=temperature,
        timeout=120,
    )


def check_config() -> list[str]:
    """Return a list of human-readable problems with the current config (empty if OK)."""
    problems = []
    if not LLM_API_KEY or LLM_API_KEY == "sk-not-set":
        problems.append("LLM_API_KEY در فایل .env تنظیم نشده است.")
    if not LLM_MODEL:
        problems.append("LLM_MODEL در فایل .env تنظیم نشده است.")
    return problems
