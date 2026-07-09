"""Code Review Agent: LLM review + lightweight deterministic static checks."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from deepagent.llm_utils import call_json
from deepagent.memory import MemoryStore
from deepagent.prompts import code_review as P
from deepagent.state import GraphState
from deepagent.workspace import Workspace

MAX_EXCERPT_CHARS = 12000

_IMPORT_RE = re.compile(
    r'import\s+(?:'
    r'(?P<default>[A-Za-z_$][\w$]*)(?:\s*,\s*\{\s*(?P<named1>[^}]+?)\s*\})?'
    r'|\{\s*(?P<named2>[^}]+?)\s*\}'
    r')\s*from\s+["\'](?P<path>@/[^"\']+)["\']'
)


def _collect_excerpt(workspace: Workspace, generated_files: List[str]) -> str:
    priority = [f for f in generated_files if f.endswith(("layout.tsx", "globals.css", "header.tsx", "footer.tsx"))]
    rest = [f for f in generated_files if f not in priority]
    ordered = priority + rest
    chunks: List[str] = []
    total = 0
    for relpath in ordered:
        content = workspace.read_text(relpath, "")
        if not content:
            continue
        chunk = f"### {relpath}\n```\n{content[:2000]}\n```\n"
        if total + len(chunk) > MAX_EXCERPT_CHARS:
            break
        chunks.append(chunk)
        total += len(chunk)
    return "\n".join(chunks)


def _static_checks(workspace: Workspace, pages: List[dict]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for page in pages:
        route = page.get("route", "/")
        route_path = "app/page.tsx" if route == "/" else f"app/{route.strip('/')}/page.tsx"
        full = f"site/{route_path}"
        if not workspace.exists(full):
            issues.append(
                {
                    "file": full,
                    "severity": "high",
                    "problem": f"فایل صفحه برای route '{route}' یافت نشد.",
                    "suggestion": "این فایل باید دوباره تولید شود.",
                }
            )
            continue
        page_content = workspace.read_text(full, "")
        if "export default" not in page_content:
            issues.append(
                {
                    "file": full,
                    "severity": "high",
                    "problem": "این فایل صفحه (page.tsx) هیچ `export default` ندارد؛ Next.js App Router برای page.tsx الزاماً به default export نیاز دارد.",
                    "suggestion": "کامپوننت اصلی صفحه را با `export default function ...` تعریف کن (نه یک named export جدا).",
                }
            )
    for must_exist in ("site/app/layout.tsx", "site/components/blocks/header.tsx", "site/components/blocks/footer.tsx"):
        if not workspace.exists(must_exist):
            issues.append(
                {
                    "file": must_exist,
                    "severity": "high",
                    "problem": "فایل ضروری پروژه تولید نشده است.",
                    "suggestion": "این فایل باید دوباره تولید شود.",
                }
            )

    header = workspace.read_text("site/components/blocks/header.tsx", "")
    if header and "ThemeToggle" not in header:
        issues.append(
            {
                "file": "site/components/blocks/header.tsx",
                "severity": "high",
                "problem": "ThemeToggle در Header رندر نشده است، پس کاربر راهی برای تغییر تم روشن/تاریک ندارد.",
                "suggestion": "`import { ThemeToggle } from \"@/components/theme-toggle\"` را اضافه و `<ThemeToggle />` را داخل Header رندر کن.",
            }
        )

    # Informational only (severity=medium): a missing hero photo means the Unsplash
    # skill couldn't source one (missing API key, rate limit, network) -- regenerating
    # the page's code wouldn't fix that, so this must never block the fix loop.
    for page in pages:
        slug = page.get("slug", "page")
        if not workspace.exists(f"site/public/images/{slug}-hero.jpg"):
            issues.append(
                {
                    "file": f"site/public/images/{slug}-hero.jpg",
                    "severity": "medium",
                    "problem": f"عکس Hero صفحه '{slug}' دانلود نشده است (احتمالاً UNSPLASH_ACCESS_KEY تنظیم نشده یا Skill ناموفق بوده).",
                    "suggestion": "`UNSPLASH_ACCESS_KEY` را در .env بررسی کن یا `design/images.md` را برای جزئیات ببین.",
                }
            )
    return issues


def _resolve_component_path(workspace: Workspace, import_path: str) -> Optional[str]:
    relative = import_path[2:]  # strip the leading "@/"
    for candidate in (
        f"site/{relative}.tsx",
        f"site/{relative}.ts",
        f"site/{relative}/index.ts",
        f"site/{relative}/index.tsx",
    ):
        if workspace.exists(candidate):
            return candidate
    return None


def _export_import_checks(workspace: Workspace, generated_files: List[str]) -> List[Dict[str, Any]]:
    """Deterministically catch named/default export-import mismatches between a local
    component file and whatever imports it -- the single most common bug the model
    produces, and one a full `next build` would catch but our pipeline doesn't run."""
    issues: List[Dict[str, Any]] = []
    checked: set[str] = set()
    for relpath in generated_files:
        if relpath in checked or not relpath.endswith((".tsx", ".ts")):
            continue
        checked.add(relpath)
        content = workspace.read_text(relpath, "")
        if not content:
            continue
        for m in _IMPORT_RE.finditer(content):
            path = m.group("path")
            if not (path.startswith("@/components/") or path.startswith("@/lib/")):
                continue
            target = _resolve_component_path(workspace, path)
            if not target:
                continue
            target_content = workspace.read_text(target, "")
            if "export *" in target_content:
                continue  # barrel re-export -- can't statically verify, trust it

            default_name = m.group("default")
            if default_name and "export default" not in target_content:
                issues.append(
                    {
                        "file": relpath,
                        "severity": "high",
                        "problem": f"'{default_name}' به‌صورت default از '{path}' import شده، اما آن فایل default export ندارد.",
                        "suggestion": f'در {relpath} از `import {{ {default_name} }} from "{path}"` استفاده کن (یا export را در {target} به default تبدیل کن).',
                    }
                )

            named = m.group("named1") or m.group("named2")
            if named:
                for raw_name in named.split(","):
                    name = raw_name.strip().split(" as ")[0].strip()
                    if not name:
                        continue
                    if not re.search(rf"export\s+(function|const|class)\s+{re.escape(name)}\b", target_content):
                        issues.append(
                            {
                                "file": relpath,
                                "severity": "high",
                                "problem": f"'{name}' به‌صورت named از '{path}' import شده، اما در آن فایل چنین export ای پیدا نشد.",
                                "suggestion": f"صادرات '{name}' را در {target} بررسی/اصلاح کن یا سبک import در {relpath} را با export واقعی هماهنگ کن.",
                            }
                        )
    return issues


_ANY_IMPORT_RE = re.compile(
    r"import\s+(?:"
    r"(?P<default>[A-Za-z_$][\w$]*)(?:\s*,\s*\{\s*(?P<named1>[^}]+?)\s*\})?"
    r"|\{\s*(?P<named2>[^}]+?)\s*\}"
    r"|\*\s+as\s+(?P<namespace>[A-Za-z_$][\w$]*)"
    r')\s*from\s+["\'][^"\']+["\']'
)
_LOCAL_DEF_RE = re.compile(r"(?:function|const|class)\s+([A-Z][A-Za-z0-9_]*)\b")
# Negative lookbehind excludes TS generics (`Record<Foo>`, `React.forwardRef<Foo>`,
# `interface X extends Y<Foo>`) -- those always have an identifier char glued to the
# `<`, whereas a real JSX opening tag's `<` is preceded by whitespace/`(`/`>`/newline.
_JSX_TAG_RE = re.compile(r"(?<![A-Za-z0-9_$])<([A-Z][A-Za-z0-9]*)\b")


def _missing_import_checks(workspace: Workspace, generated_files: List[str]) -> List[Dict[str, Any]]:
    """General version: any capitalized JSX tag (<Foo />) must resolve to something
    imported or locally defined in the same file. Catches the model using a component
    it forgot to import (even one it *did* create the file for, like a custom block),
    not just the two hardcoded next/image + PhotoCredit cases this used to special-case.
    This is exactly the class of bug a real `next build`/typecheck would catch as
    "'Foo' is not defined" but our pipeline doesn't run one."""
    issues: List[Dict[str, Any]] = []
    for relpath in generated_files:
        if not relpath.endswith(".tsx"):
            continue
        content = workspace.read_text(relpath, "")
        if not content:
            continue

        bound: set[str] = set()
        for m in _ANY_IMPORT_RE.finditer(content):
            if m.group("default"):
                bound.add(m.group("default"))
            if m.group("namespace"):
                bound.add(m.group("namespace"))
            named = m.group("named1") or m.group("named2")
            if named:
                for raw_name in named.split(","):
                    name = raw_name.strip().split(" as ")[-1].strip()
                    if name:
                        bound.add(name)
        for m in _LOCAL_DEF_RE.finditer(content):
            bound.add(m.group(1))

        used = set(_JSX_TAG_RE.findall(content))
        for name in sorted(used - bound):
            issues.append(
                {
                    "file": relpath,
                    "severity": "high",
                    "problem": f"از <{name}> استفاده شده اما هیچ import یا تعریفی برای آن در این فایل وجود ندارد.",
                    "suggestion": f"خط import مربوط به {name} را اضافه کن (اگر فایل کامپوننتش وجود ندارد، آن را هم بساز).",
                }
            )
    return issues


_BAD_USE_CLIENT_RE = re.compile(r'^\s*import\s+["\']use client["\'];?\s*$', re.MULTILINE)


def _use_client_syntax_checks(workspace: Workspace, generated_files: List[str]) -> List[Dict[str, Any]]:
    """`"use client"` is a directive (a bare string-literal statement), not a module
    import -- `import "use client";` compiles to an actual (nonexistent) module
    resolution and breaks the build with a confusing "Module not found" error."""
    issues: List[Dict[str, Any]] = []
    for relpath in generated_files:
        if not relpath.endswith((".tsx", ".ts")):
            continue
        content = workspace.read_text(relpath, "")
        if content and _BAD_USE_CLIENT_RE.search(content):
            issues.append(
                {
                    "file": relpath,
                    "severity": "high",
                    "problem": '`import "use client";` نوشته شده که یک import نامعتبر است، نه دایرکتیو.',
                    "suggestion": 'آن خط را با دایرکتیو صحیح `"use client";` (بدون کلمه import) در همان خط اول فایل جایگزین کن.',
                }
            )
    return issues


_USE_CLIENT_DIRECTIVE_RE = re.compile(r'^\s*["\']use client["\'];?\s*$', re.MULTILINE)
_METADATA_EXPORT_RE = re.compile(r"export\s+(?:const\s+metadata\b|(?:async\s+)?function\s+generateMetadata\b)")


def _client_metadata_conflict_checks(workspace: Workspace, generated_files: List[str]) -> List[Dict[str, Any]]:
    """Next.js forbids exporting `metadata`/`generateMetadata` from a file marked
    `"use client"` (metadata is a Server Component-only feature) -- a combination the
    model sometimes produces when it defensively adds "use client" to a page.tsx that
    doesn't actually need it."""
    issues: List[Dict[str, Any]] = []
    for relpath in generated_files:
        if not relpath.endswith(".tsx"):
            continue
        content = workspace.read_text(relpath, "")
        if content and _USE_CLIENT_DIRECTIVE_RE.search(content) and _METADATA_EXPORT_RE.search(content):
            issues.append(
                {
                    "file": relpath,
                    "severity": "high",
                    "problem": 'این فایل هم `"use client"` دارد هم `metadata`/`generateMetadata` را export می‌کند -- Next.js این ترکیب را ممنوع می‌کند.',
                    "suggestion": 'خط `"use client"` را از این فایل حذف کن (صفحه Server Component بماند)؛ اگر بخشی از صفحه واقعاً به تعامل نیاز دارد، آن بخش را در یک کامپوننت جدا با `"use client"` مخصوص به خودش بساز.',
                }
            )
    return issues


def run(state: GraphState, llm, workspace: Workspace, memory: MemoryStore) -> Dict[str, Any]:
    generated_files = state.get("generated_files") or []
    pages = state.get("pages") or []

    static_issues = (
        _static_checks(workspace, pages)
        + _export_import_checks(workspace, generated_files)
        + _missing_import_checks(workspace, generated_files)
        + _use_client_syntax_checks(workspace, generated_files)
        + _client_metadata_conflict_checks(workspace, generated_files)
    )
    excerpt = _collect_excerpt(workspace, generated_files)

    llm_result: Dict[str, Any] = {"summary": "", "issues": []}
    if excerpt:
        try:
            llm_result = call_json(llm, P.SYSTEM, P.USER_TEMPLATE.format(files_excerpt=excerpt))
        except Exception as exc:  # noqa: BLE001 - review failing shouldn't crash the pipeline
            llm_result = {"summary": f"بازبینی خودکار با خطا مواجه شد: {exc}", "issues": []}

    all_issues = static_issues + (llm_result.get("issues") or [])
    passed = not any(i.get("severity") == "high" for i in all_issues)

    md_lines = ["# Code Review", "", f"**جمع‌بندی:** {llm_result.get('summary', '(بدون جمع‌بندی)')}", ""]
    if all_issues:
        md_lines.append("## مشکلات")
        for issue in all_issues:
            md_lines.append(
                f"- **[{issue.get('severity')}]** `{issue.get('file')}` — {issue.get('problem')}\n"
                f"  - پیشنهاد: {issue.get('suggestion')}"
            )
    else:
        md_lines.append("مشکلی یافت نشد.")
    workspace.write_text("review/code-review.md", "\n".join(md_lines))

    memory.record("code_review", "passed", passed)

    return {
        "review_notes": all_issues,
        "review_passed": passed,
        "fix_iteration": state.get("fix_iteration", 0),
        "logs": [f"Code Review: {len(all_issues)} مورد پیدا شد (passed={passed})."],
    }
