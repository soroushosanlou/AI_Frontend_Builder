"""Todo Plan primitive: created once up front, updated as the Coordinator runs each stage."""
from __future__ import annotations

from deepagent.workspace import Workspace

PLAN_FILE = "plan.json"

STAGES: list[tuple[str, str]] = [
    ("product_analysis", "تحلیل نیازمندی‌های محصول و استخراج صفحات"),
    ("design_system", "تعریف Design System (تایپوگرافی، فاصله‌گذاری، گرید)"),
    ("color_branding", "انتخاب رنگ، برندینگ و تم روشن/تاریک"),
    ("ui_components", "طراحی مشخصات کامپوننت‌های UI"),
    ("animation", "طراحی انیمیشن و Micro Interaction"),
    ("figma_export", "خروجی Design Tokens و Wireframe برای Figma"),
    ("frontend_dev", "تولید کد Next.js (صفحات و کامپوننت‌ها)"),
    ("code_review", "بازبینی کیفیت کد"),
    ("finalize", "جمع‌بندی و تحویل پروژه"),
]


def create_plan(workspace: Workspace) -> dict:
    plan = {
        "steps": [
            {"id": sid, "title": title, "status": "pending"} for sid, title in STAGES
        ]
    }
    workspace.write_json(PLAN_FILE, plan)
    return plan


def get_plan(workspace: Workspace) -> dict:
    # NOTE: must not pass `default=create_plan(workspace)` -- Python evaluates keyword
    # arguments eagerly, so that would call create_plan() (and overwrite plan.json with
    # a fresh all-pending plan) on *every* read, silently wiping prior progress.
    existing = workspace.read_json(PLAN_FILE, default=None)
    if existing is not None:
        return existing
    return create_plan(workspace)


def update_step(workspace: Workspace, step_id: str, status: str) -> dict:
    plan = get_plan(workspace)
    for step in plan["steps"]:
        if step["id"] == step_id:
            step["status"] = status
    workspace.write_json(PLAN_FILE, plan)
    return plan


def render_checklist(plan: dict) -> str:
    icons = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}
    lines = [f"{icons.get(s['status'], '⬜')} {s['title']}" for s in plan["steps"]]
    return "\n".join(lines)
