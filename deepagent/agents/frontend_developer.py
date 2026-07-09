"""Frontend Developer Agent: scaffolds the real Next.js project, then generates the
component library extras, header/footer, and every page from the condensed specs
produced by the other agents.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from deepagent.llm_utils import call_files
from deepagent.memory import MemoryStore
from deepagent.nextjs_templates import CORE_PRIMITIVE_NAMES, get_scaffold_files
from deepagent.prompts import frontend_developer as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    tokens = state.get("design_tokens") or {}
    product_spec = state.get("product_spec") or {}
    branding = state.get("branding") or {}
    pages: List[dict] = state.get("pages") or []

    project_name = product_spec.get("project_name") or branding.get("brand_name") or workspace.slug
    tagline = product_spec.get("tagline", "")
    tone = product_spec.get("tone", "")
    brand_name = branding.get("brand_name") or project_name

    written: List[str] = []

    # 1. Deterministic scaffold: config files + guaranteed-to-build core primitives.
    scaffold = get_scaffold_files(tokens, project_name, tagline, workspace.slug)
    written += workspace.write_files(scaffold, base="site")

    # 2. Extra primitives the UI Components Agent asked for, beyond the core five.
    components_spec = state.get("components_spec") or {}
    primitives = components_spec.get("primitives", []) or []
    extra = [p for p in primitives if (p.get("name") or "").strip().lower() not in CORE_PRIMITIVE_NAMES]
    if extra:
        try:
            extra_files = call_files(
                llm,
                P.COMPONENT_LIBRARY_SYSTEM,
                P.COMPONENT_LIBRARY_USER.format(
                    design_summary=state.get("design_system_summary", ""),
                    primitives_json=json.dumps(extra, ensure_ascii=False),
                ),
            )
            written += workspace.write_files(extra_files, base="site")
            _extend_ui_barrel(workspace, extra_files.keys())
        except Exception as exc:  # noqa: BLE001 - keep the pipeline going, log and move on
            workspace.write_text("review/frontend-warnings.md", f"- extra primitives generation failed: {exc}\n")

    # 3. Header + Footer (shared across every page -> Multi Page Support).
    header_footer_files = call_files(
        llm,
        P.HEADER_FOOTER_SYSTEM,
        P.HEADER_FOOTER_USER.format(
            brand_name=brand_name,
            tone=tone,
            pages_json=json.dumps(
                [{"title": p.get("title"), "route": p.get("route")} for p in pages], ensure_ascii=False
            ),
        ),
    )
    written += workspace.write_files(header_footer_files, base="site")

    # 4. One page at a time, in its own LLM call.
    for page in pages:
        route = page.get("route", "/")
        slug = page.get("slug", "page")
        route_path = "" if route == "/" else route.strip("/") + "/"
        page_files = call_files(
            llm,
            P.PAGE_SYSTEM,
            P.PAGE_USER.format(
                product_summary=state.get("product_summary", ""),
                page_title=page.get("title", slug),
                route=route,
                slug=slug,
                purpose=page.get("purpose", ""),
                sections=", ".join(page.get("sections", [])),
                components_summary=state.get("components_summary", ""),
                animations_summary=state.get("animations_summary", ""),
                brand_name=brand_name,
                tone=tone,
                route_path=route_path,
            ),
        )
        written += workspace.write_files(page_files, base="site")

    memory.record("frontend_developer", "pages_generated", [p.get("slug") for p in pages])

    return {
        "generated_files": written,
        "logs": [f"Frontend Developer: {len(written)} فایل در پروژه Next.js تولید شد."],
    }


def _extend_ui_barrel(workspace: Workspace, extra_relpaths) -> None:
    """Keep components/ui/index.ts re-exporting every extra primitive too, so both
    `@/components/ui/badge` and the folder-level `@/components/ui` import resolve."""
    added = []
    for relpath in extra_relpaths:
        if not relpath.startswith("components/ui/") or relpath.endswith("index.ts"):
            continue
        module = relpath[len("components/ui/") :].rsplit(".", 1)[0]
        added.append(f'export * from "./{module}";')
    if not added:
        return
    current = workspace.read_text("site/components/ui/index.ts", "")
    workspace.write_text("site/components/ui/index.ts", current.rstrip("\n") + "\n" + "\n".join(added) + "\n")


def _resolve_existing(workspace: Workspace, relpath: str) -> str:
    if workspace.exists(relpath):
        return relpath
    alt = relpath if relpath.startswith("site/") else f"site/{relpath}"
    if workspace.exists(alt):
        return alt
    return relpath


def run_fix(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    """Bounded fix loop: regenerate only the files Code Review flagged as high severity."""
    issues = [i for i in (state.get("review_notes") or []) if i.get("severity") == "high"]
    iteration = state.get("fix_iteration", 0) + 1

    if not issues:
        return {"fix_iteration": iteration}

    target_files = sorted({i.get("file") for i in issues if i.get("file")})
    contents = []
    for relpath in target_files:
        resolved = _resolve_existing(workspace, relpath)
        content = workspace.read_text(resolved, "")
        if content:
            contents.append(f"### {relpath}\n```\n{content}\n```")

    if not contents:
        return {"fix_iteration": iteration}

    written: List[str] = []
    try:
        fixed_files = call_files(
            llm,
            P.FIX_SYSTEM,
            P.FIX_USER.format(
                issues_json=json.dumps(issues, ensure_ascii=False),
                files_content="\n\n".join(contents),
            ),
        )
        normalized = {(k[5:] if k.startswith("site/") else k): v for k, v in fixed_files.items()}
        written = workspace.write_files(normalized, base="site")
    except Exception as exc:  # noqa: BLE001 - a failed fix pass shouldn't crash the pipeline
        workspace.write_text("review/fix-warnings.md", f"- fix pass #{iteration} failed: {exc}\n")

    memory.record("frontend_developer", f"fix_iteration_{iteration}_files", written)

    return {
        "generated_files": written,
        "fix_iteration": iteration,
        "logs": [f"Frontend Developer: چرخه رفع اشکال #{iteration} — {len(written)} فایل اصلاح شد."],
    }
