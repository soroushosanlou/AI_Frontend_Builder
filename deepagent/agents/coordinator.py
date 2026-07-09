"""Coordinator Agent: owns Planning + Memory bookkeeping and writes the final handoff."""
from __future__ import annotations

from typing import Any, Dict

from deepagent.memory import MemoryStore
from deepagent.state import GraphState
from deepagent.workspace import Workspace


def _bonus_features_section(state: GraphState, workspace: Workspace) -> list[str]:
    pages = state.get("pages") or []
    components_spec = state.get("components_spec") or {}
    branding = state.get("branding") or {}
    primitives = [c.get("name") for c in components_spec.get("primitives", []) if c.get("name")]

    lines = ["## امتیازات اضافی (Bonus)", ""]

    lines.append(f"- **Multi Page Support**: {len(pages)} صفحه — " + "، ".join(p.get("title", p.get("slug", "")) for p in pages))

    has_light_dark = bool(branding.get("light")) and bool(branding.get("dark"))
    lines.append(
        "- **Theme Generator (روشن/تاریک)**: "
        + ("فعال — دکمه تغییر تم در Header (`components/theme-toggle.tsx`)" if has_light_dark else "یافت نشد")
    )

    lines.append(f"- **Component Library**: {len(primitives)} کامپوننت پایه در `site/components/ui/` — " + "، ".join(primitives))

    figma_files = [p for p in ("design/design-tokens.figma.json", "design/figma-export.md") if workspace.exists(p)]
    wireframe_count = len([p for p in workspace.list_tree() if p.startswith("design/wireframes/")])
    if figma_files or wireframe_count:
        lines.append(
            "- **Figma Export**: `design/design-tokens.figma.json` (فرمت DTCG) + "
            f"{wireframe_count} فایل wireframe در `design/wireframes/*.svg` — قابل import/paste مستقیم در Figma."
        )
    else:
        lines.append("- **Figma Export**: تولید نشد.")

    return lines


def finalize(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    product_spec = state.get("product_spec") or {}
    pages = state.get("pages") or []
    review_notes = state.get("review_notes") or []

    lines = [
        f"# {product_spec.get('project_name', workspace.slug)}",
        "",
        f"**شعار:** {product_spec.get('tagline', '')}",
        "",
        "این پروژه به‌طور کامل توسط AI Frontend Builder (Deep Agent) تولید شده است.",
        "",
        "## صفحات تولیدشده",
        *[f"- {p.get('title')} — `{p.get('route')}`" for p in pages],
        "",
        *_bonus_features_section(state, workspace),
        "",
        "## اجرای پروژه",
        "```bash",
        f"cd workspace/{workspace.slug}/site",
        "npm install",
        "npm run dev",
        "```",
        "",
        "## بازبینی کد",
        f"{len(review_notes)} مورد ثبت شد — جزئیات کامل در `review/code-review.md`.",
        "",
        "## تصمیمات کلیدی پروژه (Memory)",
        memory.as_markdown(),
        "",
        "## ساختار Workspace",
        "```",
        *sorted({p.split("/")[0] for p in workspace.list_tree()}),
        "```",
    ]
    workspace.write_text("README.md", "\n".join(lines))

    return {"logs": ["Coordinator: خلاصه نهایی پروژه در README.md نوشته شد."]}
