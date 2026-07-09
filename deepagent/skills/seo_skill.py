"""SEO skill: generates app/sitemap.ts + app/robots.ts for the produced Next.js site."""
from __future__ import annotations

from deepagent.skills.base import Skill, register


class SEOSkill(Skill):
    name = "seo_skill"
    description = "تولید sitemap.ts و robots.ts بر اساس صفحات سایت"
    stage = "frontend_dev"

    def run(self, context: dict) -> dict:
        workspace = context["workspace"]
        state = context["state"]
        pages = state.get("pages") or []
        product_spec = state.get("product_spec") or {}
        site_url = "https://example.com"

        entries = pages or [{"route": "/"}]
        sitemap_entries = ",\n".join(
            f'    {{ url: "{site_url}{p.get("route", "/")}", changeFrequency: "monthly", priority: {1.0 if p.get("route") == "/" else 0.7} }}'
            for p in entries
        )

        sitemap_ts = f"""import type {{ MetadataRoute }} from "next";

export default function sitemap(): MetadataRoute.Sitemap {{
  return [
{sitemap_entries}
  ];
}}
"""
        robots_ts = f"""import type {{ MetadataRoute }} from "next";

export default function robots(): MetadataRoute.Robots {{
  return {{
    rules: {{ userAgent: "*", allow: "/" }},
    sitemap: "{site_url}/sitemap.xml",
  }};
}}
"""
        workspace.write_files({"app/sitemap.ts": sitemap_ts, "app/robots.ts": robots_ts}, base="site")
        workspace.write_text(
            "design/seo.md",
            "# SEO\n\n"
            f"- `app/sitemap.ts` و `app/robots.ts` بر اساس {len(entries)} صفحه تولید شد.\n"
            f"- عنوان و توضیحات پیش‌فرض از مشخصات محصول (`{product_spec.get('project_name', '')}`) در `app/layout.tsx` تنظیم شده است.\n",
        )
        return {"logs": [f"SEO Skill: sitemap.ts/robots.ts برای {len(entries)} صفحه تولید شد."]}


register(SEOSkill())
