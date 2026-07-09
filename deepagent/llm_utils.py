"""Shared helpers for calling the LLM and parsing its output, used by every agent."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_FILE_BLOCK_RE = re.compile(
    r"===FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<content>.*?)\n===END===", re.DOTALL
)


def call_llm(llm, system: str, user: str) -> str:
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    return text


def parse_json(raw: str) -> Any:
    text = _extract_json_text(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            start_arr, end_arr = text.find("["), text.rfind("]")
            if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
                return json.loads(text[start_arr : end_arr + 1])
            raise
        return json.loads(text[start : end + 1])


def call_json(llm, system: str, user: str) -> Any:
    """Call the LLM expecting a JSON object/array back; retries once with a stricter
    instruction if the first response fails to parse."""
    raw = call_llm(llm, system, user)
    try:
        return parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        strict_user = (
            user
            + "\n\nمهم: پاسخ قبلی JSON معتبر نبود. این‌بار *فقط* یک JSON معتبر برگردان،"
            " بدون هیچ متن یا توضیح اضافه قبل یا بعد از آن."
        )
        raw2 = call_llm(llm, system, strict_user)
        return parse_json(raw2)


_LEADING_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\n")
_TRAILING_FENCE_RE = re.compile(r"\n```\s*$")


def _strip_code_fence(content: str) -> str:
    """Models sometimes wrap a file's content in a markdown code fence despite
    instructions not to; that fence would otherwise be written verbatim into the
    generated source file and break the parser/build."""
    content = _LEADING_FENCE_RE.sub("", content, count=1)
    content = _TRAILING_FENCE_RE.sub("", content, count=1)
    return content


def call_files(llm, system: str, user: str) -> dict[str, str]:
    """Call the LLM expecting one or more code files back in the format::

        ===FILE: relative/path.tsx===
        <file content>
        ===END===

    This avoids JSON-escaping issues with source code containing quotes/backticks.
    Returns {relative_path: content}.
    """
    raw = call_llm(llm, system, user)
    files = {
        m.group("path").strip(): _strip_code_fence(m.group("content"))
        for m in _FILE_BLOCK_RE.finditer(raw)
    }
    if not files:
        strict_user = (
            user
            + "\n\nمهم: خروجی باید دقیقاً با فرمت زیر برای هر فایل باشد و هیچ متن اضافه‌ای نداشته باشد:\n"
            "===FILE: relative/path===\n<محتوا>\n===END==="
        )
        raw2 = call_llm(llm, system, strict_user)
        files = {
            m.group("path").strip(): _strip_code_fence(m.group("content"))
            for m in _FILE_BLOCK_RE.finditer(raw2)
        }
        if not files:
            raise ValueError("Could not parse any ===FILE=== blocks from LLM output")
    return files


FILE_FORMAT_INSTRUCTIONS = (
    "خروجی را دقیقاً به شکل زیر و برای هر فایل تولیدشده بازگردان (بدون هیچ توضیح اضافه"
    " قبل، بعد یا بین بلوک‌ها):\n\n"
    "===FILE: relative/path/to/file.tsx===\n"
    "<کد کامل فایل>\n"
    "===END===\n\n"
    "می‌توانی چند بلوک FILE پشت سر هم بازگردانی."
)
