"""Hero Images skill: sources one on-topic, real photo per page from Unsplash for the
hero section the Frontend Developer Agent already scaffolded (see the `<Image
src="/images/<slug>-hero.jpg">` + `<PhotoCredit>` pattern in prompts/frontend_developer.py).

Requires UNSPLASH_ACCESS_KEY in .env; skips itself gracefully (with a log message) if
that isn't configured, so the pipeline still works without it -- pages just keep
rendering a 404 for the (never downloaded) hero image until it's set.

Unsplash API guideline compliance: every used photo triggers the required
`download_location` tracking ping, and the rendered page carries a visible
photographer + Unsplash credit link via the PhotoCredit component (see
nextjs_templates.get_scaffold_files).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from deepagent.config import UNSPLASH_ACCESS_KEY
from deepagent.llm_utils import call_json
from deepagent.skills.base import Skill, register

UNSPLASH_API = "https://api.unsplash.com"
GENERIC_FALLBACK_QUERY = "modern business"

SEARCH_TERMS_SYSTEM = """تو به ازای هر صفحه‌ی یک وب‌سایت، یک عبارت جستجوی عکس به
زبان انگلیسی (۲ تا ۵ کلمه، مناسب برای جستجو در Unsplash) تولید می‌کنی که موضوع/صنعت
و هدف آن صفحه را به تصویر بکشد. همچنین یک کلید ویژه "_general" اضافه کن که یک عبارت
جستجوی کلی‌تر و رایج‌تر (نه خیلی خاص/کم‌یاب) برای کل کسب‌وکار باشد -- این به‌عنوان
fallback استفاده می‌شود اگر عبارت دقیق یک صفحه نتیجه‌ای نداشت، پس باید چیزی باشد که
احتمال بالایی دارد در Unsplash عکس واقعی برایش پیدا شود (مثلاً به‌جای یک عبارت خیلی
خاص و کم‌یاب، از کلمات عمومی‌تر ولی هنوز مرتبط با حوزه کسب‌وکار استفاده کن).
فقط یک JSON با ساختار {"<page-slug>": "search terms", ..., "_general": "..."} برگردان."""

SEARCH_TERMS_USER = """برند: {brand_name}
صنعت/حوزه: {project_name}

صفحات:
{pages_json}

برای هر page-slug و برای کلید "_general" یک عبارت جستجوی عکس انگلیسی مناسب برگردان."""


def _search_unsplash_photo(client: httpx.Client, query: str) -> Optional[Dict[str, Any]]:
    resp = client.get(
        f"{UNSPLASH_API}/search/photos",
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        params={"query": query, "orientation": "landscape", "content_filter": "high", "per_page": 1},
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    results = resp.json().get("results") or []
    return results[0] if results else None


def _fetch_best_photo(client: httpx.Client, queries: List[str]) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Try each query in order (specific -> general -> generic last resort); returns
    the first real match plus which query actually found it, so a forced fallback to a
    generic/unrelated query is traceable instead of silently mismatched."""
    for q in queries:
        if not q:
            continue
        photo = _search_unsplash_photo(client, q)
        if photo:
            return photo, q
    return None, None


class HeroImagesSkill(Skill):
    name = "hero_images_skill"
    description = "دانلود یک عکس واقعی و مرتبط از Unsplash برای Hero هر صفحه"
    stage = "frontend_dev"

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not UNSPLASH_ACCESS_KEY:
            return {"logs": ["Hero Images Skill: UNSPLASH_ACCESS_KEY تنظیم نشده؛ این مرحله رد شد."]}

        workspace = context["workspace"]
        state = context["state"]
        llm = context["llm"]
        pages: List[dict] = state.get("pages") or []
        if not pages:
            return {"logs": ["Hero Images Skill: صفحه‌ای برای تولید عکس Hero یافت نشد."]}

        product_spec = state.get("product_spec") or {}
        branding = state.get("branding") or {}

        try:
            queries = call_json(
                llm,
                SEARCH_TERMS_SYSTEM,
                SEARCH_TERMS_USER.format(
                    brand_name=branding.get("brand_name") or product_spec.get("project_name", ""),
                    project_name=product_spec.get("project_name", ""),
                    pages_json=json.dumps(
                        [{"slug": p.get("slug"), "purpose": p.get("purpose")} for p in pages], ensure_ascii=False
                    ),
                ),
            )
        except Exception:
            queries = {}

        general_query = queries.get("_general") or product_spec.get("project_name", "")

        credits: Dict[str, Any] = json.loads(workspace.read_text("site/public/images/credits.json", "{}") or "{}")
        sourced: List[str] = []
        degraded: List[tuple[str, str]] = []  # (slug, query actually used) when it fell back
        failed: List[str] = []

        with httpx.Client() as client:
            for page in pages:
                slug = page.get("slug", "page")
                key = f"{slug}-hero"
                specific_query = queries.get(slug) or f"{product_spec.get('project_name', '')} {page.get('purpose', '')}".strip()

                try:
                    photo, used_query = _fetch_best_photo(
                        client, [specific_query, general_query, GENERIC_FALLBACK_QUERY]
                    )
                    if not photo:
                        failed.append(slug)
                        continue

                    image_bytes = client.get(photo["urls"]["regular"], timeout=30).content
                    workspace.path(f"site/public/images/{key}.jpg").write_bytes(image_bytes)

                    download_location = photo.get("links", {}).get("download_location")
                    if download_location:
                        try:
                            client.get(
                                download_location,
                                headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
                                timeout=15,
                            )
                        except Exception:
                            pass  # tracking ping failing shouldn't fail the whole skill

                    credits[key] = {
                        "photographer": photo.get("user", {}).get("name", "Unsplash"),
                        "photographerUrl": photo.get("user", {}).get("links", {}).get("html", "https://unsplash.com"),
                        "photoUrl": photo.get("links", {}).get("html", "https://unsplash.com"),
                        "query": used_query,
                    }
                    sourced.append(slug)
                    if used_query != specific_query:
                        degraded.append((slug, used_query))
                except Exception:
                    failed.append(slug)

        workspace.write_text("site/public/images/credits.json", json.dumps(credits, ensure_ascii=False, indent=2))

        md_lines = ["# Hero Images (Unsplash)", ""]
        for slug in sourced:
            c = credits.get(f"{slug}-hero", {})
            note = " _(جستجوی دقیق‌تر نتیجه‌ای نداشت؛ با عبارت کلی‌تر جایگزین شد)_" if any(s == slug for s, _ in degraded) else ""
            md_lines.append(f"- `{slug}`: عکس از [{c.get('photographer')}]({c.get('photographerUrl')}) — جستجو: `{c.get('query')}`{note}")
        for slug in failed:
            md_lines.append(f"- `{slug}`: هیچ عکس مرتبطی حتی با fallback پیدا نشد.")
        workspace.write_text("design/images.md", "\n".join(md_lines))

        summary = f"Hero Images Skill: {len(sourced)} عکس از Unsplash دانلود شد"
        if degraded:
            summary += f"، {len(degraded)} مورد با جستجوی کلی‌تر (fallback)"
        if failed:
            summary += f"، {len(failed)} مورد ناموفق"
        summary += "."

        return {"logs": [summary]}


register(HeroImagesSkill())
