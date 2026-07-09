"""Color & Branding Agent: palette, light/dark theme tokens, brand identity."""
from __future__ import annotations

from typing import Any, Dict

from deepagent.llm_utils import call_json
from deepagent.memory import MemoryStore, summarize_for_context
from deepagent.prompts import color_branding as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    branding = call_json(llm, P.SYSTEM, P.USER_TEMPLATE.format(product_summary=state.get("product_summary", "")))

    merged = dict(state.get("design_tokens") or {})
    merged["color"] = {
        "palette": branding.get("palette", {}),
        "light": branding.get("light", {}),
        "dark": branding.get("dark", {}),
    }
    workspace.write_json("design/design-tokens.json", merged)

    md = (
        f"# Branding\n\n**نام برند:** {branding.get('brand_name', '')}\n\n"
        f"**مفهوم لوگو:** {branding.get('logo_concept', '')}\n\n"
        f"**رنگ اصلی:** {branding.get('palette', {}).get('primary', '')}\n"
    )
    workspace.write_text("design/branding.md", md)

    memory.record("color_branding", "brand_name", branding.get("brand_name"))
    memory.record("color_branding", "palette", branding.get("palette"))

    summary = summarize_for_context(llm, "برندینگ و رنگ", md + "\n" + str(branding))
    return {
        "design_tokens": merged,
        "branding": branding,
        "branding_summary": summary,
        "logs": [f"رنگ و برندینگ مشخص شد (برند: {branding.get('brand_name', '?')}, تم روشن/تاریک آماده شد)."],
    }
