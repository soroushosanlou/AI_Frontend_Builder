"""Design System Agent: typography, spacing, grid, component rules -> design tokens."""
from __future__ import annotations

import json
from typing import Any, Dict

from deepagent.llm_utils import call_json
from deepagent.memory import MemoryStore, summarize_for_context
from deepagent.prompts import design_system as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    tokens = call_json(llm, P.SYSTEM, P.USER_TEMPLATE.format(product_summary=state.get("product_summary", "")))

    merged = dict(state.get("design_tokens") or {})
    merged["design_system"] = tokens
    workspace.write_json("design/design-tokens.json", merged)

    md = "# Design System\n\n```json\n" + json.dumps(tokens, ensure_ascii=False, indent=2) + "\n```"
    workspace.write_text("design/design-system.md", md)

    memory.record("design_system", "font_family", tokens.get("font", {}).get("family"))
    memory.record("design_system", "radius", tokens.get("radius"))

    summary = summarize_for_context(llm, "Design System", md)
    return {
        "design_tokens": merged,
        "design_system_summary": summary,
        "logs": [f"Design System آماده شد (فونت: {tokens.get('font', {}).get('family', '?')})."],
    }
