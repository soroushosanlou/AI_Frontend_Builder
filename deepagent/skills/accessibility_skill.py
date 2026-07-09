"""Accessibility skill: heuristic scan for common a11y gaps in the generated code."""
from __future__ import annotations

import re

from deepagent.skills.base import Skill, register

IMG_NO_ALT_RE = re.compile(r"<img(?![^>]*\balt=)[^>]*>", re.IGNORECASE)
ICON_BUTTON_RE = re.compile(r"<button(?![^>]*aria-label)[^>]*>\s*<(svg|[A-Z]\w*)", re.IGNORECASE)


class AccessibilitySkill(Skill):
    name = "accessibility_skill"
    description = "بررسی دسترس‌پذیری (alt text، aria-label) در کد تولیدشده"
    stage = "code_review"

    def run(self, context: dict) -> dict:
        workspace = context["workspace"]
        state = context["state"]
        generated_files = state.get("generated_files") or []

        issues: list[dict] = []
        checked = 0
        for relpath in generated_files:
            if not relpath.endswith((".tsx", ".ts")):
                continue
            content = workspace.read_text(relpath, "")
            if not content:
                continue
            checked += 1
            if IMG_NO_ALT_RE.search(content):
                issues.append(
                    {
                        "file": relpath,
                        "severity": "medium",
                        "problem": "تگ <img> بدون attribute alt یافت شد.",
                        "suggestion": "برای هر <img> یک alt توصیفی اضافه شود.",
                    }
                )
            if ICON_BUTTON_RE.search(content):
                issues.append(
                    {
                        "file": relpath,
                        "severity": "medium",
                        "problem": "دکمه‌ی فقط-آیکون بدون aria-label یافت شد.",
                        "suggestion": "به دکمه‌های فقط-آیکون aria-label اضافه شود.",
                    }
                )

        body = "\n".join(f"- [{i['severity']}] `{i['file']}` — {i['problem']}" for i in issues) or "مشکلی یافت نشد."
        workspace.write_text("review/accessibility.md", f"# Accessibility Check\n\n{checked} فایل بررسی شد.\n\n{body}")

        return {
            "logs": [f"Accessibility Skill: {checked} فایل بررسی شد، {len(issues)} مورد یافت شد."],
            "review_issues": issues,
        }


register(AccessibilitySkill())
