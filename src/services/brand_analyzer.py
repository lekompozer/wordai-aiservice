"""
Brand Analyzer Service

Given a website URL, auto-discovers and crawls key pages (About/Products/Pricing/Team),
then uses an LLM to produce a structured Brand Profile card similar to Cremyx's
"Content Engine" website analysis output.

Model routing:
  language="en" → ChatGPT gpt-5.4  (best for English brand analysis)
  language="vi" → DeepSeek R1 thinking (deepseek-reasoner) — deeper reasoning for VN market

Output schema:
  brand_name, description, problem_solved, solution, target_audience,
  use_cases, key_features, competitive_advantages, competitors (auto-detected),
  industry, colors, logo_url, website_url
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import openai

logger = logging.getLogger(__name__)

MAX_COMBINED_TEXT = 6000  # chars fed to LLM

# ─────────────────────────────────────────────────────────────────────────────
# Shared prompt builder
# ─────────────────────────────────────────────────────────────────────────────


def _build_prompt(
    url: str,
    combined_text: str,
    primary_color: str,
    logo_url: str,
    language: str,
    extra_hint: Optional[str],
) -> str:
    hint_block = f"\n\n=== USER HINT ===\n{extra_hint}" if extra_hint else ""

    if language == "en":
        lang_instruction = "Respond entirely in English."
        intro = "You are a brand strategy expert. Analyze the website content below and extract a complete Brand Profile."
        content_label = f"=== WEBSITE CONTENT ({url}) ==="
        req_label = "=== REQUIREMENTS ==="
        json_labels = {
            "brand_name": "Brand name",
            "industry": "Industry (e.g. EdTech, SaaS, E-commerce, F&B...)",
            "description": "2-3 sentence description: who they are, what they do, who they serve",
            "problem_solved": "Problem they solve for customers (1-2 sentences)",
            "solution": "Core solution (2-3 sentences)",
            "target_audience": "Target customer description (1-2 sentences)",
            "use_cases_label": "Use case 1: short description",
            "features_label": "Feature name: 1-sentence description",
            "adv_label": "Competitive advantage",
            "comp_type": '"Local" or "Global"',
            "comp_desc": "Why they are a competitor",
        }
    else:
        lang_instruction = "Trả lời hoàn toàn bằng tiếng Việt."
        intro = "Bạn là chuyên gia phân tích thương hiệu và chiến lược kinh doanh. Phân tích nội dung website dưới đây và tạo Brand Profile card đầy đủ."
        content_label = f"=== NỘI DUNG WEBSITE ({url}) ==="
        req_label = "=== YÊU CẦU ==="
        json_labels = {
            "brand_name": "Tên thương hiệu",
            "industry": "Ngành (e.g. EdTech, SaaS, E-commerce, F&B...)",
            "description": "Mô tả 2-3 câu: họ là ai, làm gì, phục vụ ai",
            "problem_solved": "Vấn đề họ giải quyết cho khách hàng (1-2 câu)",
            "solution": "Cách họ giải quyết — giải pháp cốt lõi (2-3 câu)",
            "target_audience": "Mô tả đối tượng khách hàng mục tiêu (1-2 câu)",
            "use_cases_label": "Use case 1: mô tả ngắn",
            "features_label": "Tên tính năng: mô tả 1 câu",
            "adv_label": "Lợi thế cạnh tranh",
            "comp_type": '"Local" hoặc "Global"',
            "comp_desc": "Mô tả ngắn tại sao là đối thủ",
        }

    lbl = json_labels
    return f"""{intro}

{content_label}
{combined_text or "(No content)" if language == "en" else combined_text or "(Không có nội dung)"}
{hint_block}

{req_label}
{lang_instruction}
Based on the website content, independently identify:
1. Competitors — MANDATORY: at least 3 LOCAL (same country/market) + at least 2 GLOBAL. Can list more if relevant. Base on industry and product overlap.
2. Brand colors (from meta tags or infer from industry)
3. All brand information below

Return JSON only (no other text):
{{
  "brand_name": "{lbl['brand_name']}",
  "industry": "{lbl['industry']}",
  "description": "{lbl['description']}",
  "problem_solved": "{lbl['problem_solved']}",
  "solution": "{lbl['solution']}",
  "target_audience": "{lbl['target_audience']}",
  "use_cases": [
    "{lbl['use_cases_label']}",
    "Use case 2"
  ],
  "key_features": [
    "{lbl['features_label']}",
    "Feature 2"
  ],
  "competitive_advantages": [
    "{lbl['adv_label']} 1",
    "{lbl['adv_label']} 2",
    "{lbl['adv_label']} 3"
  ],
  "competitors": [
    {{
      "name": "Competitor name",
      "type": {lbl['comp_type']},
      "category": "AI / EdTech / SaaS ...",
      "description": "{lbl['comp_desc']}",
      "website": "domain.com"
    }}
  ],
  "colors": {{
    "primary": "{primary_color}",
    "secondary": "",
    "tertiary": ""
  }},
  "logo_url": "{logo_url}",
  "website_url": "{url}"
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM callers
# ─────────────────────────────────────────────────────────────────────────────


async def _call_gpt54(prompt: str) -> str:
    """Call ChatGPT gpt-5.4 with JSON mode. Returns raw JSON string."""
    openai_key = os.getenv("CHATGPT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("CHATGPT_API_KEY not configured")
    client = openai.AsyncOpenAI(api_key=openai_key)
    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {
                "role": "system",
                "content": "You are a brand strategy expert. Always return valid JSON only, no other text.",
            },
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=3000,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


async def _call_deepseek_r1(prompt: str) -> str:
    """
    Call DeepSeek R1 thinking model (deepseek-reasoner).
    R1 does internal chain-of-thought before producing the final answer.
    Returns raw JSON string from message.content (not reasoning_content).
    Note: R1 does not support temperature or response_format.
    """
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")
    client = openai.AsyncOpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )
    response = await client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[
            {
                "role": "system",
                "content": "Bạn là chuyên gia phân tích thương hiệu. Luôn trả về JSON hợp lệ, không có text gì ngoài JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=16000,  # R1 uses reasoning tokens internally (can be large) + output
        # R1 does NOT support: temperature, response_format
    )
    content = response.choices[0].message.content or "{}"
    # R1 sometimes wraps output in ```json ... ``` fences — strip them
    content = content.strip()
    if content.startswith("```"):
        # Split on ``` and take the middle part (index 1), not the tail (index -1)
        parts = content.split("```", 2)
        content = parts[1] if len(parts) >= 2 else content
        content = content.lstrip("json").strip()
    return content


# ─────────────────────────────────────────────────────────────────────────────
# Main public functions
# ─────────────────────────────────────────────────────────────────────────────


async def analyze_website_url(
    url: str,
    language: str = "vi",
    extra_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: crawl website → LLM analysis → structured brand profile.

    Model routing:
      language="en" or "fr" → GPT-5.4
      all other languages     → DeepSeek R1 thinking (deepseek-reasoner)

    Args:
        url: Website URL provided by the user (homepage or /about)
        language: "vi" (default), "en", "fr", etc.
        extra_hint: Optional free-text context from the user

    Returns:
        Structured brand profile dict.
    """
    from src.services.brand_crawler import discover_and_crawl_website

    # ── Layer 1: crawl ──────────────────────────────────────────────────────
    logger.info(f"[BrandAnalyzer] Starting website crawl: {url}")
    brand_data = await discover_and_crawl_website(url)
    discovered_urls = brand_data.get("discovered_urls", [url])
    combined_text = brand_data.get("combined_text", "")[:MAX_COMBINED_TEXT]
    primary_color = brand_data.get("primary_color", "#000000")
    logo_url = brand_data.get("logo_url", "")

    _gpt_langs = {"en", "fr"}
    model_used = "gpt-5.4" if language in _gpt_langs else "deepseek-reasoner"
    logger.info(
        f"[BrandAnalyzer] {len(discovered_urls)} pages, {len(combined_text)} chars → {model_used}"
    )

    # ── Layer 2: LLM analysis ───────────────────────────────────────────────
    prompt = _build_prompt(
        url, combined_text, primary_color, logo_url, language, extra_hint
    )

    if language in _gpt_langs:
        raw = await _call_gpt54(prompt)
    else:
        raw = await _call_deepseek_r1(prompt)

    brand_profile = json.loads(raw)

    # Merge crawled colors/logo if LLM left them empty
    if not brand_profile.get("colors", {}).get("primary") or brand_profile.get(
        "colors", {}
    ).get("primary") in ("#000000", ""):
        brand_profile.setdefault("colors", {})["primary"] = primary_color
    if not brand_profile.get("logo_url"):
        brand_profile["logo_url"] = logo_url
    if not brand_profile.get("website_url"):
        brand_profile["website_url"] = url

    brand_profile["_model_used"] = model_used
    brand_profile["_crawled_urls"] = discovered_urls
    brand_profile["_crawled_pages_count"] = len(discovered_urls)

    logger.info(
        f"[BrandAnalyzer] ✅ Brand profile for '{brand_profile.get('brand_name', url)}' via {model_used}"
    )
    return brand_profile


async def analyze_website_url_compare(
    url: str,
    extra_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run BOTH GPT-5.4 (EN) and DeepSeek R1 thinking (VI) in parallel on the same URL.
    Returns {"gpt54": {...}, "deepseek_r1": {...}} for side-by-side comparison.
    """
    import asyncio
    from src.services.brand_crawler import discover_and_crawl_website

    logger.info(f"[BrandAnalyzer] Compare mode: {url}")
    brand_data = await discover_and_crawl_website(url)
    combined_text = brand_data.get("combined_text", "")[:MAX_COMBINED_TEXT]
    primary_color = brand_data.get("primary_color", "#000000")
    logo_url = brand_data.get("logo_url", "")
    discovered_urls = brand_data.get("discovered_urls", [url])

    prompt_en = _build_prompt(
        url, combined_text, primary_color, logo_url, "en", extra_hint
    )
    prompt_vi = _build_prompt(
        url, combined_text, primary_color, logo_url, "vi", extra_hint
    )

    raw_gpt, raw_r1 = await asyncio.gather(
        _call_gpt54(prompt_en),
        _call_deepseek_r1(prompt_vi),
        return_exceptions=True,
    )

    def _parse(raw, model_name):
        if isinstance(raw, Exception):
            return {"_error": str(raw), "_model_used": model_name}
        try:
            p = json.loads(raw)
            p["_model_used"] = model_name
            p["_crawled_urls"] = discovered_urls
            return p
        except Exception as e:
            return {
                "_error": f"JSON parse failed: {e}",
                "_raw": raw[:500],
                "_model_used": model_name,
            }

    return {
        "gpt54": _parse(raw_gpt, "gpt-5.4"),
        "deepseek_r1": _parse(raw_r1, "deepseek-reasoner"),
        "_crawled_urls": discovered_urls,
        "_crawled_pages_count": len(discovered_urls),
    }
