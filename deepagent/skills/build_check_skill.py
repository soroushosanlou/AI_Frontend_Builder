"""Build Check skill: actually runs `npm install` + `next build` against the generated
Next.js project in `site/` and turns real compiler/build failures into review issues.

The regex-based checks in agents/code_review.py catch common LLM-codegen mistakes
(export/import mismatches, missing "use client", etc.) but can't replace an actual
TypeScript/Next.js build -- this closes that gap with ground truth. Skips itself
gracefully (with a log message) if npm isn't on PATH, so the pipeline still works in
environments without Node.js installed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any, Dict, List

from deepagent.skills.base import Skill, register

INSTALL_TIMEOUT_SECONDS = 600
BUILD_TIMEOUT_SECONDS = 300
MAX_ISSUE_MESSAGE_CHARS = 400
MAX_LOG_CHARS = 4000

# Matches a Next.js build error's file header, e.g. "./app/page.tsx:12:3" (type error)
# or "./components/blocks/header.tsx" on its own line (module-not-found errors omit
# the line:col suffix).
_FILE_LOCATOR_RE = re.compile(r"^\./(?P<file>\S+?)(?::(?P<line>\d+):(?P<col>\d+))?\s*$", re.MULTILINE)


def _run(cmd: List[str], cwd, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _parse_build_errors(output: str) -> List[Dict[str, Any]]:
    """Turn Next.js's build failure output into one issue per distinct file, each with
    the file path pre-resolved so the fix loop (frontend_developer.run_fix) can act on
    it directly -- issues without a resolvable "file" key are silently skipped there."""
    matches = list(_FILE_LOCATOR_RE.finditer(output))
    issues: List[Dict[str, Any]] = []
    seen_files: set[str] = set()
    for i, m in enumerate(matches):
        file = m.group("file")
        if file in seen_files:
            continue
        seen_files.add(file)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(output), start + 800)
        message = output[start:end].strip()
        location = f":{m.group('line')}:{m.group('col')}" if m.group("line") else ""
        issues.append(
            {
                "file": f"site/{file}",
                "severity": "high",
                "problem": f"خطای build (Next.js{location}): {message[:MAX_ISSUE_MESSAGE_CHARS]}",
                "suggestion": "این فایل باید بر اساس پیام خطای build بالا اصلاح شود تا پروژه واقعاً compile شود.",
            }
        )
    return issues


class BuildCheckSkill(Skill):
    name = "build_check_skill"
    description = "اجرای واقعی npm install + next build روی پروژه تولیدشده و تبدیل خطاهای build به review issue"
    stage = "code_review"

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        workspace = context["workspace"]
        site_dir = workspace.site_dir

        npm_path = shutil.which("npm")
        if not npm_path:
            return {"logs": ["Build Check Skill: npm روی سیستم یافت نشد؛ این مرحله رد شد."]}
        if not workspace.exists("site/package.json"):
            return {"logs": ["Build Check Skill: package.json یافت نشد؛ این مرحله رد شد."]}

        log_lines = ["# Build Check (npm install + next build)", ""]

        if not (site_dir / "node_modules").exists():
            try:
                install = _run(
                    [npm_path, "install", "--no-audit", "--no-fund", "--loglevel=error"],
                    site_dir,
                    INSTALL_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                log_lines.append("`npm install` بیش از حد طول کشید (timeout).")
                workspace.write_text("review/build-check.md", "\n".join(log_lines))
                return {"logs": ["Build Check Skill: npm install تایم‌اوت شد؛ build اجرا نشد."]}

            if install.returncode != 0:
                tail = (install.stdout + install.stderr)[-MAX_LOG_CHARS:]
                log_lines += ["## npm install شکست خورد", "```", tail, "```"]
                workspace.write_text("review/build-check.md", "\n".join(log_lines))
                return {
                    "logs": ["Build Check Skill: npm install شکست خورد."],
                    "review_issues": [
                        {
                            "file": None,
                            "severity": "high",
                            "problem": f"`npm install` با خطا شکست خورد: {tail[-MAX_ISSUE_MESSAGE_CHARS:]}",
                            "suggestion": "خروجی کامل در review/build-check.md را بررسی کن (معمولاً یک dependency نامعتبر در package.json).",
                        }
                    ],
                }
            log_lines.append("`npm install` موفق بود.")
        else:
            log_lines.append("`node_modules` از قبل موجود بود؛ install رد شد.")

        try:
            build = _run([npm_path, "run", "build"], site_dir, BUILD_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            log_lines.append("`next build` بیش از حد طول کشید (timeout).")
            workspace.write_text("review/build-check.md", "\n".join(log_lines))
            return {"logs": ["Build Check Skill: next build تایم‌اوت شد."]}

        output = build.stdout + build.stderr

        if build.returncode == 0:
            log_lines.append("`next build` موفق بود -- پروژه واقعاً compile می‌شود. ✅")
            workspace.write_text("review/build-check.md", "\n".join(log_lines))
            return {"logs": ["Build Check Skill: next build موفق بود."]}

        issues = _parse_build_errors(output)
        if not issues:
            issues = [
                {
                    "file": None,
                    "severity": "high",
                    "problem": f"`next build` شکست خورد اما خطا به فایل خاصی نسبت داده نشد: {output.strip()[-MAX_ISSUE_MESSAGE_CHARS:]}",
                    "suggestion": "خروجی کامل در review/build-check.md را بررسی کن.",
                }
            ]

        log_lines.append(f"`next build` شکست خورد -- {len(issues)} مورد خطا شناسایی شد. ❌")
        log_lines += ["", "## خروجی کامل", "```", output[-MAX_LOG_CHARS:], "```"]
        workspace.write_text("review/build-check.md", "\n".join(log_lines))

        return {
            "logs": [f"Build Check Skill: next build شکست خورد ({len(issues)} مورد)."],
            "review_issues": issues,
        }


register(BuildCheckSkill())
