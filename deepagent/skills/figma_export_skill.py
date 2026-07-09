"""Figma Export skill (bonus): DTCG-format design tokens + per-page SVG wireframes.

A standalone Python app cannot drive Claude Code's live Figma MCP session, so this skill
produces artifacts a designer can import into Figma directly: a Design Tokens Community
Group (DTCG) JSON file (compatible with the "Figma Tokens" plugin) and one SVG wireframe
per page (Figma accepts pasted SVG directly onto the canvas).
"""
from __future__ import annotations

from typing import Any, Dict

from deepagent.skills.base import Skill, register

DEFAULT_PAGE = {"slug": "home", "title": "خانه", "route": "/", "sections": ["Header", "Hero", "Footer"]}


def _build_dtcg(tokens: Dict[str, Any]) -> Dict[str, Any]:
    design_system = tokens.get("design_system", {}) or {}
    color = tokens.get("color", {}) or {}
    palette = color.get("palette", {}) or {}
    light = color.get("light", {}) or {}
    dark = color.get("dark", {}) or {}
    spacing = design_system.get("spacing", {}) or {}
    radius = design_system.get("radius", {}) or {}
    type_scale = design_system.get("type_scale", {}) or {}
    font = design_system.get("font", {}) or {}

    dtcg: Dict[str, Any] = {"color": {}, "spacing": {}, "radius": {}, "typography": {}}

    for name, value in palette.items():
        dtcg["color"][name.replace("_", "-")] = {"$value": value, "$type": "color"}
    for name, value in light.items():
        dtcg["color"][f"light-{name}"] = {"$value": value, "$type": "color"}
    for name, value in dark.items():
        dtcg["color"][f"dark-{name}"] = {"$value": value, "$type": "color"}
    for name, value in spacing.items():
        dtcg["spacing"][name] = {"$value": value, "$type": "dimension"}
    for name, value in radius.items():
        dtcg["radius"][name] = {"$value": value, "$type": "dimension"}
    for name, size in type_scale.items():
        dtcg["typography"][name] = {
            "$value": {
                "fontFamily": font.get("family", "Vazirmatn"),
                "fontSize": size,
                "fontWeight": 700 if name in ("display", "h1", "h2") else 400,
            },
            "$type": "typography",
        }
    return dtcg


def _page_wireframe_svg(page: Dict[str, Any], tokens: Dict[str, Any]) -> str:
    color = tokens.get("color", {}) or {}
    light = color.get("light", {}) or {}
    bg = light.get("background", "#FFFFFF")
    border = light.get("border", "#E2E8F0")
    muted = light.get("muted", "#64748B")
    primary = (color.get("palette", {}) or {}).get("primary", "#4F46E5")

    sections = page.get("sections") or ["Header", "Content", "Footer"]
    width, header_h, section_h, gap = 1200, 72, 140, 16
    y = header_h + gap

    parts = [
        f'<rect x="0" y="0" width="{width}" height="{header_h}" fill="{primary}" />',
        f'<text x="24" y="{header_h / 2 + 6}" font-size="20" fill="#ffffff" font-family="sans-serif">{page.get("title", "")}</text>',
    ]
    for section in sections:
        parts.append(
            f'<rect x="24" y="{y}" width="{width - 48}" height="{section_h}" rx="12" '
            f'fill="{bg}" stroke="{border}" stroke-width="2" />'
        )
        parts.append(
            f'<text x="{width / 2}" y="{y + section_h / 2}" font-size="18" fill="{muted}" '
            f'text-anchor="middle" font-family="sans-serif">{section}</text>'
        )
        y += section_h + gap

    total_height = y + gap
    body = "\n  ".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_height}" '
        f'width="{width}" height="{total_height}">\n  {body}\n</svg>'
    )


class FigmaExportSkill(Skill):
    name = "figma_export_skill"
    description = "خروجی Design Tokens (DTCG) و Wireframe SVG برای import در Figma"
    stage = "figma_export"

    def run(self, context: dict) -> dict:
        workspace = context["workspace"]
        state = context["state"]
        tokens = state.get("design_tokens") or {}
        pages = state.get("pages") or [DEFAULT_PAGE]

        dtcg = _build_dtcg(tokens)
        workspace.write_json("design/design-tokens.figma.json", dtcg)

        for page in pages:
            svg = _page_wireframe_svg(page, tokens)
            workspace.write_text(f"design/wireframes/{page.get('slug', 'page')}.wireframe.svg", svg)

        workspace.write_text(
            "design/figma-export.md",
            "# Figma Export\n\n"
            "- `design/design-tokens.figma.json` — فرمت Design Tokens Community Group (DTCG)، "
            "سازگار با افزونه Figma Tokens.\n"
            f"- `design/wireframes/*.svg` — {len(pages)} wireframe که می‌توان مستقیماً روی بوم Figma paste کرد.\n",
        )
        return {"logs": [f"Figma Export Skill: design-tokens.figma.json + {len(pages)} wireframe SVG تولید شد."]}


register(FigmaExportSkill())
