"""Wires all 8 agents + skill hooks into a LangGraph StateGraph.

Flow::

    product_analysis -> design_system -> color_branding -> figma_export(skill)
    -> ui_components -> animation -> frontend_dev -> frontend_dev(skills: seo)
    -> code_review -> code_review(skills: accessibility)
    -> [fix -> code_review]*  (bounded, max MAX_FIX_ITERATIONS)
    -> finalize
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from deepagent import planning
from deepagent.agents import (
    animation,
    code_review,
    color_branding,
    coordinator,
    design_system,
    frontend_developer,
    product_analysis,
    ui_components,
)
from deepagent.config import get_llm
from deepagent.memory import MemoryStore
from deepagent.skills.base import skills_for_stage
from deepagent.state import GraphState
from deepagent.workspace import Workspace

MAX_FIX_ITERATIONS = 2


def _stage_node(stage_id, fn, llm, workspace, memory):
    def node(state: GraphState):
        planning.update_step(workspace, stage_id, "in_progress")
        updates = fn(state, llm, workspace, memory) or {}
        planning.update_step(workspace, stage_id, "done")
        return updates

    return node


def _skills_node(stage_id, llm, workspace, memory):
    def node(state: GraphState):
        logs = []
        extra_issues = []
        for skill in skills_for_stage(stage_id):
            context = {"workspace": workspace, "memory": memory, "llm": llm, "state": state}
            try:
                result = skill.run(context) or {}
                logs.extend(result.get("logs") or [f"Skill '{skill.name}' اجرا شد."])
                extra_issues.extend(result.get("review_issues") or [])
            except Exception as exc:  # noqa: BLE001 - a skill failing shouldn't crash the pipeline
                logs.append(f"Skill '{skill.name}' با خطا مواجه شد: {exc}")
        updates: dict = {"logs": logs}
        if extra_issues:
            combined_notes = (state.get("review_notes") or []) + extra_issues
            updates["review_notes"] = combined_notes
            # A skill (e.g. build_check_skill) can find its own high-severity issues
            # *after* code_review.run already decided review_passed -- without
            # recomputing it here, _should_fix would never see them and the fix loop
            # would silently never trigger for skill-discovered problems.
            if any(i.get("severity") == "high" for i in extra_issues):
                updates["review_passed"] = not any(i.get("severity") == "high" for i in combined_notes)
        return updates

    return node


def _fix_node(llm, workspace, memory):
    def node(state: GraphState):
        planning.update_step(workspace, "code_review", "in_progress")
        updates = frontend_developer.run_fix(state, llm, workspace, memory) or {}
        return updates

    return node


def _finalize_node(llm, workspace, memory):
    def node(state: GraphState):
        planning.update_step(workspace, "finalize", "in_progress")
        updates = coordinator.finalize(state, llm, workspace, memory) or {}
        planning.update_step(workspace, "finalize", "done")
        return updates

    return node


def _should_fix(state: GraphState) -> str:
    if state.get("review_passed", True):
        return "finalize"
    if state.get("fix_iteration", 0) >= MAX_FIX_ITERATIONS:
        return "finalize"
    return "fix"


def build_graph(workspace: Workspace, memory: MemoryStore, llm=None):
    llm = llm or get_llm()
    planning.create_plan(workspace)

    graph = StateGraph(GraphState)

    graph.add_node("product_analysis", _stage_node("product_analysis", product_analysis.run, llm, workspace, memory))
    graph.add_node("design_system", _stage_node("design_system", design_system.run, llm, workspace, memory))
    graph.add_node("color_branding", _stage_node("color_branding", color_branding.run, llm, workspace, memory))
    graph.add_node("figma_export", _stage_node("figma_export", lambda *a: {}, llm, workspace, memory))
    graph.add_node("figma_export_skills", _skills_node("figma_export", llm, workspace, memory))
    graph.add_node("ui_components", _stage_node("ui_components", ui_components.run, llm, workspace, memory))
    graph.add_node("animation", _stage_node("animation", animation.run, llm, workspace, memory))
    graph.add_node("frontend_dev", _stage_node("frontend_dev", frontend_developer.run, llm, workspace, memory))
    graph.add_node("frontend_dev_skills", _skills_node("frontend_dev", llm, workspace, memory))
    graph.add_node("code_review", _stage_node("code_review", code_review.run, llm, workspace, memory))
    graph.add_node("code_review_skills", _skills_node("code_review", llm, workspace, memory))
    graph.add_node("fix", _fix_node(llm, workspace, memory))
    graph.add_node("finalize", _finalize_node(llm, workspace, memory))

    graph.set_entry_point("product_analysis")
    graph.add_edge("product_analysis", "design_system")
    graph.add_edge("design_system", "color_branding")
    graph.add_edge("color_branding", "figma_export")
    graph.add_edge("figma_export", "figma_export_skills")
    graph.add_edge("figma_export_skills", "ui_components")
    graph.add_edge("ui_components", "animation")
    graph.add_edge("animation", "frontend_dev")
    graph.add_edge("frontend_dev", "frontend_dev_skills")
    graph.add_edge("frontend_dev_skills", "code_review")
    graph.add_edge("code_review", "code_review_skills")
    graph.add_conditional_edges("code_review_skills", _should_fix, {"fix": "fix", "finalize": "finalize"})
    graph.add_edge("fix", "code_review")
    graph.add_edge("finalize", END)

    return graph.compile()
