"""Interactive CLI: the required user interface for the Deep Agent."""
from __future__ import annotations

import os
import sys
import traceback

if sys.platform == "win32":
    # Persian text breaks rich's legacy Windows console renderer (cp1252) and the
    # default stdin codepage mangles piped UTF-8 into lone surrogates. Force UTF-8
    # everywhere so RTL/Persian input and output round-trip correctly.
    for _stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from deepagent import planning
from deepagent.config import check_config, get_llm
from deepagent.graph import build_graph
from deepagent.memory import MemoryStore
from deepagent.skills.base import all_skills
from deepagent.workspace import Workspace, slugify, unique_slug

console = Console(legacy_windows=False)

BANNER = (
    "[bold cyan]AI Frontend Builder — Deep Agent[/bold cyan]\n"
    "یک ایده برای وب‌سایت یا محصول خود (به فارسی) بنویس تا تیمی از Agent های هوشمند "
    "تحلیل، طراحی و کدنویسی آن را برایت انجام دهند.\n\n"
    "دستورات: [green]/plan[/green]  [green]/memory[/green]  [green]/skills[/green]  "
    "[green]/resume <slug>[/green]  [green]/exit[/green]"
)


def _is_shaping_capable_terminal() -> bool:
    """Detect terminals known to render Persian/Arabic text correctly (contextual
    letter joining + bidi). The classic Windows console host (conhost.exe, used by
    default cmd.exe/PowerShell windows) has neither and cannot be fixed from here --
    Windows Terminal, VS Code's terminal, and most others use a real text-shaping
    engine and render fine."""
    if sys.platform != "win32":
        return True
    return any(os.environ.get(var) for var in ("WT_SESSION", "TERM_PROGRAM", "ConEmuPID"))


LEGACY_CONSOLE_WARNING = (
    "[yellow]هشدار:[/yellow] به نظر می‌رسد در کنسول کلاسیک ویندوز (conhost.exe) اجرا می‌شوی. "
    "این کنسول از اتصال حروف فارسی/عربی و جهت‌دهی RTL پشتیبانی نمی‌کند و متن فارسی می‌تواند "
    "بریده‌بریده یا نامرتب نمایش داده شود -- این یک محدودیت خودِ کنسول است، نه اشکال برنامه. "
    "برای نمایش صحیح، این برنامه را در [bold]Windows Terminal[/bold] اجرا کن."
)


def _print_checklist(workspace: Workspace) -> None:
    plan = planning.get_plan(workspace)
    icons = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}
    table = Table(show_header=False, box=None, padding=(0, 1))
    for step in plan["steps"]:
        table.add_row(icons.get(step["status"], "⬜"), step["title"])
    console.print(Panel(table, title=f"Todo Plan — {workspace.slug}", border_style="cyan"))


def _run_pipeline(idea: str) -> Workspace:
    for problem in check_config():
        console.print(f"[yellow]هشدار:[/yellow] {problem}")

    base_slug = unique_slug(slugify(idea))
    workspace = Workspace(base_slug)
    memory = MemoryStore(workspace)
    llm = get_llm()

    console.print(f"\n[bold]پروژه در مسیر زیر ساخته می‌شود:[/bold] workspace/{workspace.slug}\n")

    graph = build_graph(workspace, memory, llm)
    initial_state = {"idea": idea, "slug": workspace.slug, "workspace_dir": str(workspace.dir)}

    try:
        for chunk in graph.stream(initial_state, {"recursion_limit": 60}, stream_mode="updates"):
            for _node_name, updates in chunk.items():
                for line in (updates or {}).get("logs") or []:
                    console.print(f"  [dim]›[/dim] {line}")
                _print_checklist(workspace)
    except Exception as exc:  # noqa: BLE001 - surface the error, don't crash the CLI loop
        console.print(f"[red]خطا در اجرای پایپ‌لاین:[/red] {exc}")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

    return workspace


def _print_summary(workspace: Workspace) -> None:
    readme = workspace.read_text("README.md", "")
    if readme:
        console.print(Panel(readme, title="خلاصه پروژه", border_style="green"))
    console.print(
        "\n[bold green]آماده شد![/bold green] برای اجرای سایت:\n"
        f"  cd workspace/{workspace.slug}/site\n"
        "  npm install\n"
        "  npm run dev\n"
    )


def _cmd_plan(workspace: Workspace | None) -> None:
    if not workspace:
        console.print("[yellow]هنوز پروژه‌ای در این نشست شروع نشده است. از /resume <slug> استفاده کن.[/yellow]")
        return
    _print_checklist(workspace)


def _cmd_memory(workspace: Workspace | None) -> None:
    if not workspace:
        console.print("[yellow]هنوز پروژه‌ای در این نشست شروع نشده است. از /resume <slug> استفاده کن.[/yellow]")
        return
    memory = MemoryStore(workspace)
    console.print(Panel(memory.as_markdown(), title="Memory (تصمیمات ثبت‌شده)", border_style="magenta"))


def _cmd_skills() -> None:
    table = Table(title="Skills موجود")
    table.add_column("نام")
    table.add_column("مرحله")
    table.add_column("توضیح")
    for skill in all_skills():
        table.add_row(skill.name, skill.stage, skill.description)
    console.print(table)


def _cmd_resume(slug: str) -> Workspace:
    workspace = Workspace(slug)
    console.print(f"[cyan]پروژه '{slug}' بارگذاری شد.[/cyan]")
    _print_checklist(workspace)
    return workspace


def main() -> None:
    if not _is_shaping_capable_terminal():
        console.print(LEGACY_CONSOLE_WARNING)
        console.print()
    console.print(Panel.fit(BANNER, border_style="cyan"))
    current_workspace: Workspace | None = None

    while True:
        try:
            user_input = console.input("\n[bold]>[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nخداحافظ!")
            break

        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            console.print("خداحافظ!")
            break
        if user_input == "/plan":
            _cmd_plan(current_workspace)
            continue
        if user_input == "/memory":
            _cmd_memory(current_workspace)
            continue
        if user_input == "/skills":
            _cmd_skills()
            continue
        if user_input.startswith("/resume"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                console.print("استفاده: /resume <slug>")
                continue
            current_workspace = _cmd_resume(parts[1].strip())
            continue

        current_workspace = _run_pipeline(user_input)
        _print_summary(current_workspace)


if __name__ == "__main__":
    main()
