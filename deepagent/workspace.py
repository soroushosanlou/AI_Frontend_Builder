"""Filesystem abstraction: the single place every agent/skill reads and writes through.

Layout created under ``workspace/<slug>/``::

    plan.json
    memory/decisions.json
    spec/product-analysis.md
    design/design-tokens.json
    design/design-system.md
    design/branding.md
    design/components-spec.md
    design/animations.md
    design/wireframes/<page>.svg
    review/code-review.md
    site/                 <- the real generated Next.js project
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from deepagent.config import WORKSPACE_ROOT

_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def slugify(text: str, max_len: int = 40) -> str:
    """Build a filesystem-safe slug, transliterating nothing (Persian stays Persian-free):
    we hash-free it by keeping ascii letters/digits from a naive transliteration attempt,
    falling back to a timestamp-based slug when the idea is pure Persian (the common case).
    """
    text = text.translate(_ARABIC_DIGITS)
    ascii_only = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if len(ascii_only) >= 3:
        return ascii_only[:max_len]
    stamp = datetime.now().strftime("project-%Y%m%d-%H%M%S")
    return stamp


def unique_slug(base: str) -> str:
    candidate = base
    i = 2
    while (WORKSPACE_ROOT / candidate).exists():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


class Workspace:
    """All file I/O for one generated project lives behind this class."""

    SUBDIRS = ("memory", "spec", "design", "design/wireframes", "review", "site")

    def __init__(self, slug: str, root: Path | None = None):
        self.slug = slug
        self.root = root or WORKSPACE_ROOT
        self.dir = self.root / slug
        for sub in self.SUBDIRS:
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    # -- generic file ops -------------------------------------------------
    def path(self, relpath: str) -> Path:
        p = self.dir / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write_text(self, relpath: str, content: str) -> Path:
        p = self.path(relpath)
        p.write_text(content, encoding="utf-8")
        return p

    def read_text(self, relpath: str, default: str = "") -> str:
        p = self.dir / relpath
        return p.read_text(encoding="utf-8") if p.exists() else default

    def write_json(self, relpath: str, data: Any) -> Path:
        return self.write_text(relpath, json.dumps(data, ensure_ascii=False, indent=2))

    def read_json(self, relpath: str, default: Any = None) -> Any:
        text = self.read_text(relpath, "")
        if not text:
            return default
        return json.loads(text)

    def write_files(self, files: dict[str, str], base: str = "site") -> list[str]:
        """Write a {relative_path: content} map under ``base`` (default: the Next.js project)."""
        written = []
        for relpath, content in files.items():
            relpath = relpath.lstrip("/\\")
            self.write_text(f"{base}/{relpath}", content)
            written.append(f"{base}/{relpath}")
        return written

    def list_tree(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.dir)).replace("\\", "/")
            for p in self.dir.rglob("*")
            if p.is_file()
        )

    def exists(self, relpath: str) -> bool:
        return (self.dir / relpath).exists()

    @property
    def site_dir(self) -> Path:
        return self.dir / "site"
