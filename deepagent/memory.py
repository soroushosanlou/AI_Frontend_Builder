"""Persistent project memory + context-management helpers.

MemoryStore is distinct from LangGraph's in-run state: it survives across
separate CLI invocations (a project can be resumed later) and holds the
*decisions* each agent made, so re-running or continuing a project keeps
design/branding/content choices consistent instead of drifting.

``summarize_for_context`` is the Context Management primitive: large
artifacts are always saved to the filesystem in full, but only a condensed
version is threaded through the LangGraph state/prompts passed to
downstream agents, to keep prompts from growing unbounded across an
8-agent pipeline.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from deepagent.workspace import Workspace

MEMORY_FILE = "memory/decisions.json"


class MemoryStore:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        if not self.workspace.exists(MEMORY_FILE):
            self.workspace.write_json(MEMORY_FILE, {"decisions": [], "facts": {}})

    def _read(self) -> dict:
        return self.workspace.read_json(MEMORY_FILE, {"decisions": [], "facts": {}})

    def _write(self, data: dict) -> None:
        self.workspace.write_json(MEMORY_FILE, data)

    def record(self, agent: str, key: str, value: Any, reason: str = "") -> None:
        data = self._read()
        data["decisions"].append(
            {
                "agent": agent,
                "key": key,
                "value": value,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["facts"][key] = value
        self._write(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._read()["facts"].get(key, default)

    def all_decisions(self) -> list[dict]:
        return self._read()["decisions"]

    def as_markdown(self) -> str:
        decisions = self.all_decisions()
        if not decisions:
            return "(هنوز تصمیمی ثبت نشده است)"
        lines = [f"- **{d['agent']}** → `{d['key']}` = {d['value']}" + (f" _( {d['reason']} )_" if d["reason"] else "") for d in decisions]
        return "\n".join(lines)


def summarize_for_context(llm, label: str, content: str, max_chars: int = 4000) -> str:
    """Condense a large artifact into a short bullet summary for downstream prompts."""
    if content is None:
        return ""
    if len(content) <= max_chars:
        return content
    prompt = (
        f"متن زیر خروجی کامل مرحله «{label}» از یک پایپ‌لاین چند-ایجنتی است. "
        "آن را در حداکثر ۱۰ نکته‌ی خلاصه، دقیق و قابل استفاده برای مرحله بعد بازنویسی کن. "
        "فقط تصمیم‌ها، نام‌ها، مقادیر عددی/رنگی و قوانین کلیدی را نگه دار؛ توضیح اضافه ننویس.\n\n"
        f"---\n{content}\n---"
    )
    try:
        resp = llm.invoke([SystemMessage(content="تو یک خلاصه‌ساز فنی دقیق هستی."), HumanMessage(content=prompt)])
        return resp.content.strip()
    except Exception:
        # Fall back to a hard truncation if the summarizer call itself fails.
        return content[:max_chars] + "\n...(خلاصه شد)"
