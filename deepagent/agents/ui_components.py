"""UI Components Agent: decides primitives + page blocks (basis of the Component Library)."""
from __future__ import annotations

from typing import Any, Dict

from deepagent.llm_utils import call_json
from deepagent.memory import MemoryStore, summarize_for_context
from deepagent.prompts import ui_components as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    spec = call_json(
        llm,
        P.SYSTEM,
        P.USER_TEMPLATE.format(
            product_summary=state.get("product_summary", ""),
            design_summary=state.get("design_system_summary", ""),
        ),
    )
    workspace.write_json("design/components-spec.json", spec)

    primitives = spec.get("primitives", []) or []
    blocks = spec.get("blocks", []) or []
    md_lines = ["# Components Spec", "", "## Primitives"]
    md_lines += [f"- **{c.get('name')}**: {', '.join(c.get('variants', []))} — {c.get('rtl_notes', '')}" for c in primitives]
    md_lines += ["", "## Blocks"]
    md_lines += [f"- **{b.get('name')}** ({', '.join(b.get('used_in_pages', []))}): {b.get('description', '')}" for b in blocks]
    md = "\n".join(md_lines)
    workspace.write_text("design/components-spec.md", md)

    memory.record("ui_components", "primitives", [c.get("name") for c in primitives])
    memory.record("ui_components", "blocks", [b.get("name") for b in blocks])

    summary = summarize_for_context(llm, "مشخصات کامپوننت‌ها", md)
    return {
        "components_spec": spec,
        "components_summary": summary,
        "logs": [f"مشخصات {len(primitives)} کامپوننت پایه و {len(blocks)} بلوک تولید شد."],
    }
