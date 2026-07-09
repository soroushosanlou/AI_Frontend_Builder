"""Product Analysis Agent: turns the user's Persian idea into a structured spec."""
from __future__ import annotations

from typing import Any, Dict

from deepagent.llm_utils import call_json
from deepagent.memory import MemoryStore, summarize_for_context
from deepagent.prompts import product_analysis as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    idea = state["idea"]
    spec = call_json(llm, P.SYSTEM, P.USER_TEMPLATE.format(idea=idea))

    pages = spec.get("pages") or []
    has_home = False
    for page in pages:
        slug = (page.get("slug") or "page").strip().lower().replace(" ", "-")
        route = page.get("route") or f"/{slug}"
        if not route.startswith("/"):
            route = "/" + route
        page["slug"] = slug
        page["route"] = route
        if route == "/":
            has_home = True
    if pages and not has_home:
        pages[0]["route"] = "/"
        pages[0]["slug"] = "home"

    md = _to_markdown(spec)
    workspace.write_text("spec/product-analysis.md", md)

    memory.record("product_analysis", "project_name", spec.get("project_name"))
    memory.record("product_analysis", "tone", spec.get("tone"))
    memory.record("product_analysis", "pages", [p["slug"] for p in pages])

    summary = summarize_for_context(llm, "تحلیل محصول", md)
    return {
        "product_spec": spec,
        "pages": pages,
        "product_summary": summary,
        "logs": [f"Product Analysis: {len(pages)} صفحه شناسایی شد ({', '.join(p['slug'] for p in pages)})."],
    }


def _to_markdown(spec: Dict[str, Any]) -> str:
    lines = [
        f"# {spec.get('project_name', '')}",
        f"**شعار:** {spec.get('tagline', '')}",
        "",
        f"**مخاطب:** {spec.get('audience', '')}",
        f"**لحن:** {spec.get('tone', '')}",
        "",
        "## ویژگی‌ها",
        *[f"- {feature}" for feature in spec.get("features", [])],
        "",
        "## صفحات",
    ]
    for page in spec.get("pages", []):
        lines.append(f"### {page.get('title')} ({page.get('route')})")
        lines.append(page.get("purpose", ""))
        lines.append("بخش‌ها: " + ", ".join(page.get("sections", [])))
        lines.append("")
    return "\n".join(lines)
