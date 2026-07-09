"""Shared LangGraph state schema threaded through every agent node."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # input
    idea: str
    slug: str
    workspace_dir: str

    # product analysis
    product_spec: Dict[str, Any]
    pages: List[Dict[str, Any]]
    product_summary: str

    # design system
    design_tokens: Dict[str, Any]
    design_system_summary: str

    # color & branding
    branding: Dict[str, Any]
    branding_summary: str

    # ui components
    components_spec: Dict[str, Any]
    components_summary: str

    # animation
    animations: Dict[str, Any]
    animations_summary: str

    # figma export skill
    figma_export_done: bool

    # frontend developer
    generated_files: Annotated[List[str], operator.add]
    current_page_index: int

    # code review
    review_notes: List[Dict[str, Any]]
    fix_iteration: int
    review_passed: bool

    # bookkeeping
    logs: Annotated[List[str], operator.add]
