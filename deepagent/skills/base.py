"""Skill System: drop a new file in deepagent/skills/ implementing Skill and it is
auto-discovered and wired into the pipeline stage it targets -- no changes needed
anywhere else in the architecture.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, List


class Skill:
    """Base interface every skill implements."""

    name: str = "base_skill"
    description: str = ""
    stage: str = ""  # pipeline stage id (see deepagent.planning.STAGES) this skill hooks into

    def applies_to(self, stage: str) -> bool:
        return stage == self.stage

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the skill. ``context`` holds workspace, memory, llm and pipeline state.
        Returns a dict describing what it did (for logging); writes its own artifacts.
        """
        raise NotImplementedError


_REGISTRY: List[Skill] = []
_DISCOVERED = False


def register(skill: Skill) -> Skill:
    _REGISTRY.append(skill)
    return skill


def discover_skills() -> List[Skill]:
    global _DISCOVERED
    if not _DISCOVERED:
        import deepagent.skills as pkg

        for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
            if modname in ("base",):
                continue
            importlib.import_module(f"deepagent.skills.{modname}")
        _DISCOVERED = True
    return _REGISTRY


def skills_for_stage(stage: str) -> List[Skill]:
    return [s for s in discover_skills() if s.applies_to(stage)]


def all_skills() -> List[Skill]:
    return list(discover_skills())
