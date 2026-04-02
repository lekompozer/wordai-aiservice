"""
Brand vs Competitors Comparison Service

Given analyses of my brand page + up to 3 competitor pages (already produced by
social_competitor_analyzer), runs two additional AI steps:

Step A: Auto-screenshot pages with ScreenshotAPI → batch ChatGPT gpt-5.4 Vision
  (all 4 pages in ONE call) → visual_style, uses_real_people, uses_ai_generated,
  content_format, design_quality per page

Step B: DeepSeek R1 comparative analysis (my page vs competitors)
  → my_strengths, my_weaknesses, competitor_advantages, strategic_gap,
    improvement_plan, content_strategy_recommendations, design_recommendations, summary
"""

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
import openai

logger = logging.getLogger(__name__)

MAX_ANALYSIS_CHARS = 1500  # per-page analysis truncation for the comparison prompt
SCREENSHOT_API_BASE = "https://api.screenshotapi.com/take"


# ─────────────────────────────────────────────────────────────────────────────
# Step A1 — Auto-screenshot via ScreenshotAPI
# ─────────────────────────────────────────────────────────────────────────────


async def take_screenshot_url(page_url: str, api_key: str) -> Optional[str]:
    """
    Screenshot a URL using ScreenshotAPI.com.
    Returns the public S3 image URL, or None on failure.
    ScreenshotAPI default response: JSON {"outputUrl": "https://s3.amazonaws.com/..."}
    """
    params = {
        "url": page_url,
        "apiKey": api_key,
        "width": 1280,
        "height": 1080,
        "delay": 3000,  # wait 3s for JS-heavy pages (TikTok, Instagram)
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.get(SCREENSHOT_API_BASE, params=params)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            # JSON response: {"outputUrl": "https://s3.amazonaws.com/..."}
            if "application/json" in content_type:
                data = resp.json()
                output_url = data.get("outputUrl") or data.get("url")
                if output_url:
                    logger.info(f"[Screenshot] ✅ {page_url} → {output_url}")
                    return output_url
                logger.warning(
                    f"[Screenshot] No outputUrl in response for {page_url}: {data}"
                )
                return None

            # Direct image response (if API returns raw bytes)
            if content_type.startswith("image/") and len(resp.content) > 5000:
                # Upload to R2 if needed, or just return a base64 data URL
                b64 = base64.b64encode(resp.content).decode()
                logger.info(
                    f"[Screenshot] ✅ {page_url} (raw image, {len(resp.content):,} bytes)"
                )
                return f"data:{content_type};base64,{b64}"

            logger.warning(
                f"[Screenshot] Unexpected response for {page_url}: "
                f"content-type={content_type!r}, size={len(resp.content)} bytes"
            )
            return None
    except Exception as e:
        logger.error(f"[Screenshot] Failed for {page_url}: {e}")
        return None


async def take_screenshot_base64(page_url: str, api_key: str) -> Optional[str]:
    """Alias kept for compat — calls take_screenshot_url (which returns S3 URL or data URL)."""
    return await take_screenshot_url(page_url, api_key)


async def take_all_screenshots(
    page_urls: List[str], api_key: str
) -> List[Optional[str]]:
    """Take screenshots for all pages sequentially. Returns list of S3/data URLs (or None)."""
    results = []
    for url in page_urls:
        img_url = await take_screenshot_url(url, api_key)
        results.append(img_url)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step A2 — ChatGPT Vision: BATCH design analysis for all pages in ONE call
# ─────────────────────────────────────────────────────────────────────────────


async def analyze_all_designs_batch(
    page_urls: List[str],
    screenshots_b64: List[Optional[str]],
    language: str = "vi",
) -> Dict[str, Any]:
    """
    Send ALL page screenshots in a SINGLE ChatGPT gpt-5.4 Vision call.
    Returns dict mapping URL → design analysis dict.

    Supports up to 4 images (1 my page + 3 competitors).
    Falls back to empty dict if no valid screenshots.
    """
    openai_key = os.getenv("CHATGPT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.warning(
            "[BrandCompare] CHATGPT_API_KEY not set — skipping design analysis"
        )
        return {"_skipped": True, "reason": "CHATGPT_API_KEY not configured"}

    valid = [(url, b64) for url, b64 in zip(page_urls, screenshots_b64) if b64]
    if not valid:
        return {"_skipped": True, "reason": "No screenshots available"}

    # Build label → URL mapping for cleaner JSON keys
    labels = ["MY_PAGE"] + [f"COMPETITOR_{i}" for i in range(1, len(page_urls))]
    valid_labels = [labels[page_urls.index(url)] for url, _ in valid]

    label_desc = "\n".join(
        f"  - {lbl}: {url}" for lbl, url in zip(valid_labels, [u for u, _ in valid])
    )

    if language == "en":
        intro_text = (
            f"You are a social media design analyst. "
            f"I'm sending you {len(valid)} screenshots of TikTok / social media pages.\n"
            f"Pages:\n{label_desc}\n\n"
            "For EACH page, analyze the visual design style from the screenshot.\n"
            "Return a JSON object where each key is the page label and value is the design analysis:\n"
        )
    elif language == "fr":
        intro_text = (
            f"Vous êtes analyste design réseaux sociaux. "
            f"Je vous envoie {len(valid)} captures de pages TikTok / réseaux sociaux.\n"
            f"Pages:\n{label_desc}\n\n"
            "Pour CHAQUE page, analysez le style de design visuel.\n"
            "Retournez un objet JSON avec chaque clé = label de page et valeur = analyse:\n"
        )
    else:
        intro_text = (
            f"Bạn là chuyên gia phân tích thiết kế mạng xã hội. "
            f"Tôi gửi cho bạn {len(valid)} ảnh chụp màn hình của các trang TikTok / mạng xã hội.\n"
            f"Các trang:\n{label_desc}\n\n"
            "Với MỖI trang, phân tích phong cách thiết kế hình ảnh từ ảnh chụp.\n"
            "Trả về JSON với key = label trang và value = phân tích thiết kế:\n"
        )

    schema_per_page = (
        "{\n"
        '  "visual_style": "minimalist | editorial | bold | product-focused | lifestyle | educational | mixed",\n'
        '  "uses_real_people": true/false,\n'
        '  "uses_ai_generated": "yes | no | mixed | unclear",\n'
        '  "content_format": "talking-head | infographic | product-shots | lifestyle | text-overlay | meme | mixed",\n'
        '  "design_quality": "professional | amateur | mixed",\n'
        '  "brand_colors": "brief description of dominant colors seen",\n'
        '  "thumbnail_style": "describe thumbnail style: text-heavy | face-close-up | product-demo | abstract | etc.",\n'
        '  "summary": "1-2 sentence design style summary"\n'
        "}"
    )
    example_keys = ", ".join(f'"{lbl}"' for lbl in valid_labels)
    full_prompt = (
        intro_text
        + f"JSON format: {{{example_keys}: <analysis_object>}}\n\n"
        + f"Analysis schema per page:\n{schema_per_page}\n\n"
        + "Return ONLY valid JSON, no markdown fences or other text."
    )

    def _to_image_url_item(img: str) -> dict:
        """Convert screenshot value to OpenAI Vision image_url content item."""
        if img.startswith("http://") or img.startswith("https://"):
            return {"type": "image_url", "image_url": {"url": img}}
        if img.startswith("data:"):
            return {"type": "image_url", "image_url": {"url": img}}
        # Raw base64 string — assume JPEG
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img}"},
        }

    # Build content: text + one image per page
    content: List[dict] = [{"type": "text", "text": full_prompt}]
    for _url, img in valid:
        content.append(_to_image_url_item(img))

    client = openai.AsyncOpenAI(api_key=openai_key)
    try:
        response = await client.chat.completions.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=8000,
        )
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            parts = raw.split("```", 2)
            raw = parts[1].lstrip("json").strip() if len(parts) >= 2 else raw

        result_by_label = json.loads(raw)
        # Map labels back to URLs
        result_by_url: Dict[str, Any] = {}
        for lbl, (url, _) in zip(valid_labels, valid):
            result_by_url[url] = result_by_label.get(lbl, {"_missing": True})
        logger.info(
            f"[BrandCompare] ✅ Batch design analysis done for {len(valid)} pages"
        )
        return result_by_url

    except Exception as e:
        logger.error(f"[BrandCompare] Batch design analysis failed: {e}")
        return {"_error": str(e)}


async def analyze_design_with_chatgpt(
    image_url: str,
    page_url: str,
    language: str = "vi",
) -> Dict[str, Any]:
    """
    Send a single public-URL screenshot to ChatGPT gpt-5.4 Vision.
    (Kept for backward compat — prefer analyze_all_designs_batch for batch).
    """
    openai_key = os.getenv("CHATGPT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.warning(
            "[BrandCompare] CHATGPT_API_KEY not set — skipping design analysis"
        )
        return {"_skipped": True, "reason": "CHATGPT_API_KEY not configured"}

    if language == "en":
        lang_note = "Respond in English."
        prompt_text = (
            f"You are a social media design analyst. Analyze the screenshot of a social media post "
            f"from the page: {page_url}\n\n"
            "Return a JSON object with these fields:\n"
            "{\n"
            '  "visual_style": "one of: minimalist | editorial | bold | product-focused | lifestyle | educational | mixed",\n'
            '  "uses_real_people": true | false,\n'
            '  "uses_ai_generated": "yes | no | mixed | unclear",\n'
            '  "content_format": "one of: talking-head | infographic | product-shots | lifestyle | text-overlay | meme | mixed",\n'
            '  "design_quality": "professional | amateur | mixed",\n'
            '  "brand_colors": "brief description of dominant colors",\n'
            '  "summary": "1-2 sentence design style summary"\n'
            "}\n\n"
            "Return ONLY valid JSON, no other text."
        )
    elif language == "fr":
        lang_note = "Répondez en français."
        prompt_text = (
            f"Vous êtes un analyste de design de réseaux sociaux. Analysez la capture d'écran du post "
            f"de la page: {page_url}\n\n"
            "Retournez un objet JSON avec ces champs:\n"
            "{\n"
            '  "visual_style": "minimaliste | éditorial | audacieux | produit | lifestyle | éducatif | mixte",\n'
            '  "uses_real_people": true | false,\n'
            '  "uses_ai_generated": "oui | non | mixte | unclear",\n'
            '  "content_format": "talking-head | infographique | photos-produit | lifestyle | texte-superposé | meme | mixte",\n'
            '  "design_quality": "professionnel | amateur | mixte",\n'
            '  "brand_colors": "brève description des couleurs dominantes",\n'
            '  "summary": "résumé du style design en 1-2 phrases"\n'
            "}\n\nRetournez UNIQUEMENT du JSON valide."
        )
    else:
        lang_note = "Trả lời bằng tiếng Việt."
        prompt_text = (
            f"Bạn là chuyên gia phân tích thiết kế mạng xã hội. Phân tích ảnh chụp màn hình bài đăng "
            f"từ trang: {page_url}\n\n"
            "Trả về JSON với các trường sau:\n"
            "{\n"
            '  "visual_style": "một trong: minimalist | editorial | bold | product-focused | lifestyle | educational | mixed",\n'
            '  "uses_real_people": true hoặc false,\n'
            '  "uses_ai_generated": "yes/no/mixed/unclear — có dùng AI tạo ảnh không",\n'
            '  "content_format": "talking-head | infographic | product-shots | lifestyle | text-overlay | meme | mixed",\n'
            '  "design_quality": "professional | amateur | mixed",\n'
            '  "brand_colors": "mô tả ngắn màu sắc chủ đạo",\n'
            '  "summary": "tóm tắt phong cách thiết kế trong 1-2 câu"\n'
            "}\n\nChỉ trả về JSON hợp lệ, không thêm gì khác."
        )

    client = openai.AsyncOpenAI(api_key=openai_key)

    try:
        response = await client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_completion_tokens=1000,
        )
        content_str = (response.choices[0].message.content or "{}").strip()
        if content_str.startswith("```"):
            parts = content_str.split("```", 2)
            content_str = (
                parts[1].lstrip("json").strip() if len(parts) >= 2 else content_str
            )

        result = json.loads(content_str)
        result["_image_url"] = image_url
        result["_page_url"] = page_url
        return result

    except Exception as e:
        logger.error(f"[BrandCompare] Design analysis failed for {page_url}: {e}")
        return {"_error": str(e), "_page_url": page_url}


# ─────────────────────────────────────────────────────────────────────────────
# Step B — DeepSeek R1: comparative brand analysis
# ─────────────────────────────────────────────────────────────────────────────


def _truncate(text: str, max_chars: int = MAX_ANALYSIS_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


def _build_comparison_prompt(
    my_url: str,
    my_analysis: Dict[str, Any],
    competitor_analyses: List[Dict[str, Any]],
    my_design: Optional[Dict[str, Any]],
    competitor_designs: List[Optional[Dict[str, Any]]],
    language: str,
) -> str:
    def _fmt_analysis(label: str, analysis: dict, design: Optional[dict]) -> str:
        lines = [f"=== {label} ==="]
        lines.append(f"URL: {analysis.get('_url', '')}")
        metrics = analysis.get("_engagement_metrics") or {}
        if metrics.get("has_pinned_split"):
            reg = metrics.get("regular") or {}
            lines.append(f"Followers: {reg.get('followers_count', 'N/A')}")
            lines.append(
                f"Engagement rate (regular posts): {reg.get('engagement_rate_pct', 'N/A')}%"
            )
            lines.append(f"Avg likes (regular): {reg.get('avg_likes', 'N/A')}")
            lines.append(f"Avg views (regular): {reg.get('avg_views', 'N/A')}")
        elif metrics:
            lines.append(f"Followers: {metrics.get('followers_count', 'N/A')}")
            lines.append(
                f"Engagement rate: {metrics.get('engagement_rate_pct', 'N/A')}%"
            )
            lines.append(f"Avg likes: {metrics.get('avg_likes', 'N/A')}")

        # Key analysis fields
        for key in (
            "target_audience",
            "problem_solved",
            "solution",
            "tone_of_voice",
            "posting_schedule",
            "post_frequency",
            "best_content_type",
            "engagement_verdict",
        ):
            val = analysis.get(key)
            if val:
                lines.append(f"{key}: {_truncate(str(val), 300)}")

        themes = analysis.get("content_themes")
        if themes:
            lines.append(
                f"content_themes: {', '.join(themes) if isinstance(themes, list) else str(themes)}"
            )

        if design and not design.get("_skipped") and not design.get("_error"):
            lines.append("--- Design Style ---")
            lines.append(f"visual_style: {design.get('visual_style', '')}")
            lines.append(f"uses_real_people: {design.get('uses_real_people', '')}")
            lines.append(f"uses_ai_generated: {design.get('uses_ai_generated', '')}")
            lines.append(f"content_format: {design.get('content_format', '')}")
            lines.append(f"design_quality: {design.get('design_quality', '')}")
            lines.append(f"brand_colors: {design.get('brand_colors', '')}")
            lines.append(f"design_summary: {design.get('summary', '')}")

        return "\n".join(lines)

    sections = []
    sections.append(_fmt_analysis("MY BRAND PAGE", my_analysis, my_design))
    for i, (ca, cd) in enumerate(zip(competitor_analyses, competitor_designs), 1):
        sections.append(_fmt_analysis(f"COMPETITOR {i}", ca, cd))

    data_block = "\n\n".join(sections)

    has_design = any(
        d and not d.get("_skipped") and not d.get("_error")
        for d in ([my_design] + list(competitor_designs))
    )

    if language in ("en", "fr"):
        lang_instr = (
            "Respond entirely in English."
            if language == "en"
            else "Répondez entièrement en français."
        )
        intro = (
            "You are a senior social media strategist. "
            "Below is a structured analysis of MY BRAND PAGE and up to 3 COMPETITOR pages.\n"
            "Your task: produce a comparative brand intelligence report.\n\n"
        )
        output_fields = {
            "my_strengths": "List 3-5 concrete STRENGTHS of my brand page vs competitors (content, engagement, positioning)",
            "my_weaknesses": "List 3-5 concrete WEAKNESSES or gaps compared to competitors",
            "competitor_advantages": "Object mapping each competitor URL to a list of 2-3 advantages they have over my brand",
            "strategic_gap": "1-paragraph description of the biggest strategic gap my brand has vs competitors",
            "improvement_plan": (
                "Array of 3-5 actionable improvement items, each: "
                '{"action": "...", "rationale": "...", "priority": "high|medium|low"}'
            ),
            "content_strategy_recommendations": "3-5 concrete content strategy recommendations for my brand based on competitor analysis",
        }
        if has_design:
            output_fields["design_recommendations"] = (
                "Based on design style analyses: recommend specific design/visual improvements for my brand "
                "(visual style to adopt, whether to use real people vs AI, color palette, format)"
            )
        output_fields["summary"] = (
            "2-3 paragraph executive summary of my brand's competitive position and top priorities"
        )

    else:
        lang_instr = "Trả lời hoàn toàn bằng tiếng Việt."
        intro = (
            "Bạn là chuyên gia chiến lược mạng xã hội cấp cao. "
            "Dưới đây là phân tích có cấu trúc của TRANG THƯƠNG HIỆU CỦA TÔI và tối đa 3 trang đối thủ.\n"
            "Nhiệm vụ: tạo báo cáo phân tích cạnh tranh toàn diện.\n\n"
        )
        output_fields = {
            "my_strengths": "Liệt kê 3-5 ĐIỂM MẠNH cụ thể của trang tôi so với đối thủ (nội dung, tương tác, định vị)",
            "my_weaknesses": "Liệt kê 3-5 ĐIỂM YẾU hoặc khoảng trống so với đối thủ",
            "competitor_advantages": "Object mapping từng URL đối thủ → danh sách 2-3 lợi thế họ có so với thương hiệu của tôi",
            "strategic_gap": "1 đoạn mô tả khoảng trống chiến lược lớn nhất của thương hiệu tôi so với đối thủ",
            "improvement_plan": (
                "Mảng 3-5 hành động cải thiện, mỗi item: "
                '{"action": "...", "rationale": "...", "priority": "high|medium|low"}'
            ),
            "content_strategy_recommendations": "3-5 đề xuất chiến lược nội dung cụ thể dựa trên phân tích đối thủ",
        }
        if has_design:
            output_fields["design_recommendations"] = (
                "Dựa trên phân tích phong cách thiết kế: đề xuất cải thiện thiết kế/hình ảnh cho thương hiệu tôi "
                "(phong cách hình ảnh nên dùng, có dùng người thật hay AI không, bảng màu, định dạng)"
            )
        output_fields["summary"] = (
            "Tóm tắt điều hành 2-3 đoạn về vị thế cạnh tranh và các ưu tiên hàng đầu"
        )

    fields_desc = "\n".join(f'  "{k}": {v}' for k, v in output_fields.items())
    output_schema = (
        "Return a JSON object with these fields:\n"
        "{\n"
        f"{fields_desc}\n"
        "}\n\nReturn ONLY valid JSON."
    )

    return f"{lang_instr}\n\n{intro}{data_block}\n\n{output_schema}"


async def run_brand_comparison(
    my_url: str,
    my_analysis: Dict[str, Any],
    competitor_analyses: List[Dict[str, Any]],
    my_design: Optional[Dict[str, Any]] = None,
    competitor_designs: Optional[List[Optional[Dict[str, Any]]]] = None,
    language: str = "vi",
) -> Dict[str, Any]:
    """
    Run DeepSeek R1 comparative analysis: my brand vs competitors.
    Returns the brand_comparison dict.
    """
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    cd = competitor_designs or [None] * len(competitor_analyses)

    prompt = _build_comparison_prompt(
        my_url=my_url,
        my_analysis=my_analysis,
        competitor_analyses=competitor_analyses,
        my_design=my_design,
        competitor_designs=cd,
        language=language,
    )

    client = openai.AsyncOpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )

    logger.info(
        f"[BrandCompare] Running comparative analysis: my={my_url}, "
        f"competitors={[c.get('_url', '') for c in competitor_analyses]}"
    )

    try:
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {
                    "role": "system",
                    "content": "You are a competitive intelligence expert. Return valid JSON only, no other text.",
                },
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=16000,
        )
        content = (response.choices[0].message.content or "{}").strip()
        if content.startswith("```"):
            parts = content.split("```", 2)
            content = parts[1].lstrip("json").strip() if len(parts) >= 2 else content

        result = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"[BrandCompare] JSON parse error: {e}")
        result = {"_error": f"JSON parse failed: {e}"}
    except Exception as e:
        logger.error(f"[BrandCompare] DeepSeek error: {e}")
        raise

    logger.info("[BrandCompare] ✅ Comparative analysis complete")
    return result
