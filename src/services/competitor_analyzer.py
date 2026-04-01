"""
Competitor Analyzer Service

Layer 1 analysis: Given competitor data (name, description, website_url, facebook_url,
example_posts_text), crawl available URLs and LLM-summarize each competitor into a compact
JSON summary (~300 tokens) for use in Brand DNA synthesis.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_EXAMPLE_POSTS_CHARS = 1500
MAX_WEBSITE_TEXT_CHARS = 1500
MAX_COMPETITORS = 6


async def _crawl_text(url: str) -> str:
    """Crawl a URL and return plain body text (best-effort, non-fatal)."""
    try:
        from src.services.brand_crawler import crawl_brand_url

        data = await crawl_brand_url(url)
        parts = []
        if data.get("title"):
            parts.append(data["title"])
        if data.get("meta_description"):
            parts.append(data["meta_description"])
        parts.extend(data.get("h1_texts", []))
        parts.extend(data.get("h2_texts", []))
        if data.get("body_text"):
            parts.append(data["body_text"])
        return " | ".join(p for p in parts if p)[:MAX_WEBSITE_TEXT_CHARS]
    except Exception as e:
        logger.warning(f"Competitor crawl failed for {url}: {e}")
        return ""


async def analyze_competitor(
    competitor: Dict[str, Any],
    deepseek_client,
) -> Dict[str, Any]:
    """
    Analyze a single competitor and return a compact summary dict.

    Input competitor keys:
        name, description, website_url, facebook_url, example_posts_text

    Returns compact dict:
        {
            "name": str,
            "content_style": str,        # e.g. "educational, informal, emoji-heavy"
            "key_messages": [str],        # top 2-3 selling points they push
            "tone_voice": str,            # e.g. "friendly, youthful"
            "strengths": [str],           # from public content
            "weaknesses": [str],          # gaps / what they lack
            "differentiator_vs_brand": str  # how our brand stands out
        }
    """
    name = competitor.get("name", "Unknown Competitor")
    description = competitor.get("description", "")
    website_url = competitor.get("website_url", "")
    facebook_url = competitor.get("facebook_url", "")
    example_posts = (competitor.get("example_posts_text", "") or "")[
        :MAX_EXAMPLE_POSTS_CHARS
    ]

    async def _empty() -> str:
        return ""

    # Crawl website / facebook in parallel (best-effort)
    crawl_tasks = [
        _crawl_text(website_url) if website_url else _empty(),
        _crawl_text(facebook_url) if facebook_url else _empty(),
    ]

    website_text, facebook_text = await asyncio.gather(
        *crawl_tasks, return_exceptions=True
    )
    website_text = website_text if isinstance(website_text, str) else ""
    facebook_text = facebook_text if isinstance(facebook_text, str) else ""

    # Build context block
    context_parts = []
    if description:
        context_parts.append(f"Description: {description}")
    if website_text:
        context_parts.append(
            f"Website content: {website_text[:MAX_WEBSITE_TEXT_CHARS]}"
        )
    if facebook_text:
        context_parts.append(f"Facebook content: {facebook_text[:800]}")
    if example_posts:
        context_parts.append(f"Example posts:\n{example_posts}")

    if not context_parts:
        # No data at all — return stub
        return {
            "name": name,
            "content_style": "unknown",
            "key_messages": [],
            "tone_voice": "unknown",
            "strengths": [],
            "weaknesses": [],
            "differentiator_vs_brand": "",
        }

    context_str = "\n\n".join(context_parts)

    prompt = f"""Bạn là chuyên gia phân tích cạnh tranh thương hiệu.

Phân tích đối thủ cạnh tranh dựa trên dữ liệu sau:

=== ĐỐI THỦ: {name} ===
{context_str}

Trả về JSON với các trường sau (ngắn gọn, súc tích):
{{
  "name": "{name}",
  "content_style": "Mô tả ngắn gọn phong cách nội dung (≤20 từ)",
  "key_messages": ["Thông điệp chính 1", "Thông điệp chính 2"],
  "tone_voice": "Giọng điệu / phong cách truyền thông (≤10 từ)",
  "strengths": ["Điểm mạnh 1", "Điểm mạnh 2"],
  "weaknesses": ["Điểm yếu / gap 1", "Điểm yếu / gap 2"],
  "differentiator_vs_brand": "Khoảng trống mà brand của chúng ta có thể khai thác (≤30 từ)"
}}

Chỉ trả về JSON, không text khác."""

    try:
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a brand strategist. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        result["name"] = name  # ensure name is preserved
        return result
    except Exception as e:
        logger.error(f"Competitor analysis failed for {name}: {e}")
        return {
            "name": name,
            "content_style": "analysis_failed",
            "key_messages": [],
            "tone_voice": "",
            "strengths": [],
            "weaknesses": [],
            "differentiator_vs_brand": "",
        }


async def analyze_all_competitors(
    competitors: List[Dict[str, Any]],
    deepseek_client,
) -> List[Dict[str, Any]]:
    """
    Analyze up to MAX_COMPETITORS competitors in parallel (3 at a time to avoid rate limits).

    Returns:
        List of competitor summary dicts (compact, ~300 tokens each)
    """
    if not competitors:
        return []

    limited = competitors[:MAX_COMPETITORS]
    logger.info(f"🔍 Analyzing {len(limited)} competitors...")

    # Process in groups of 3 to avoid overwhelming crawl/API
    results = []
    for i in range(0, len(limited), 3):
        chunk = limited[i : i + 3]
        chunk_results = await asyncio.gather(
            *[analyze_competitor(c, deepseek_client) for c in chunk],
            return_exceptions=True,
        )
        for j, r in enumerate(chunk_results):
            if isinstance(r, Exception):
                logger.error(
                    f"Competitor {chunk[j].get('name')} analysis exception: {r}"
                )
                results.append({"name": chunk[j].get("name", ""), "error": str(r)})
            else:
                results.append(r)

    logger.info(f"✅ Competitor analysis complete: {len(results)} competitors analyzed")
    return results


def format_competitor_summaries_for_prompt(summaries: List[Dict[str, Any]]) -> str:
    """
    Format competitor summaries into a compact string for LLM prompts.
    Target: ~300 tokens per competitor.
    """
    if not summaries:
        return "Không có dữ liệu đối thủ."

    lines = []
    for c in summaries:
        name = c.get("name", "Unknown")
        style = c.get("content_style", "")
        tone = c.get("tone_voice", "")
        strengths = ", ".join(c.get("strengths", []))
        weaknesses = ", ".join(c.get("weaknesses", []))
        diff = c.get("differentiator_vs_brand", "")
        messages = " / ".join(c.get("key_messages", []))

        lines.append(
            f"• {name}: phong cách={style}, giọng={tone}, thông điệp=[{messages}], "
            f"điểm mạnh=[{strengths}], điểm yếu=[{weaknesses}], cơ hội=[{diff}]"
        )

    return "\n".join(lines)
