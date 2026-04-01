"""
Competitor Social Media Analyzer

Takes scraped posts from a competitor's social page and uses DeepSeek R1 (thinking)
to produce a structured competitive intelligence report.

Analysis output:
  - Target audience they're aiming at
  - Problem they solve
  - Solution / value proposition
  - Tone of voice
  - Posting schedule (typical times/days)
  - Posting frequency
  - Main content themes

Always responds in the language selected by the user.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import openai

logger = logging.getLogger(__name__)

MAX_POST_CHARS = 200    # truncate each post — keeps prompt lean
MAX_POSTS_IN_PROMPT = 15


def _build_social_analysis_prompt(
    competitor_url: str,
    platform: str,
    posts: List[Dict[str, Any]],
    language: str,
) -> str:
    posts_block = ""
    for i, post in enumerate(posts[:MAX_POSTS_IN_PROMPT], 1):
        text = (post.get("text") or "").strip()[:MAX_POST_CHARS]
        date = post.get("date", "")
        date_str = f" [{date}]" if date else ""
        posts_block += f"{i}.{date_str} {text}\n"

    if language in ("en", "fr"):
        lang_instruction = "Respond entirely in English." if language == "en" else "Répondez entièrement en français."
        intro = "You are a competitive intelligence expert. Analyze the following social media posts from a competitor."
        lbl = {
            "target_audience": "Target audience they are aiming at",
            "problem_solved": "Problem they are solving for customers",
            "solution": "Solution / value proposition being communicated",
            "tone_of_voice": "Tone of voice (e.g. professional, casual, humorous, educational…)",
            "posting_schedule": "Typical posting times / days (if detectable from dates)",
            "post_frequency": "Estimated posting frequency (posts per day or week)",
            "content_themes": "Main content themes or topics",
            "summary": "One-paragraph competitive intelligence summary",
        }
    else:
        lang_instruction = "Trả lời hoàn toàn bằng tiếng Việt."
        intro = "Bạn là chuyên gia phân tích đối thủ cạnh tranh. Phân tích các bài đăng mạng xã hội dưới đây."
        lbl = {
            "target_audience": "Đối tượng khách hàng họ đang nhắm tới là ai",
            "problem_solved": "Vấn đề họ đang giải quyết cho khách hàng",
            "solution": "Giải pháp và giá trị họ truyền tải",
            "tone_of_voice": "Giọng văn (Tone of voice) — ví dụ: chuyên nghiệp, gần gũi, hài hước, giáo dục…",
            "posting_schedule": "Thời gian đăng bài thường là khi nào (nếu đọc được từ ngày đăng)",
            "post_frequency": "Tần suất đăng bài — một ngày đăng mấy bài, hay mấy bài / tuần",
            "content_themes": "Chủ đề nội dung chính họ thường đăng",
            "summary": "Tóm tắt một đoạn về đối thủ này dựa trên dữ liệu bài đăng",
        }

    return f"""{intro}

=== SOURCE: {platform.upper()} — {competitor_url} ===
{posts_block.strip()}

=== INSTRUCTIONS ===
{lang_instruction}
Analyze these posts carefully and return JSON only (no other text):
{{
  "target_audience": "{lbl['target_audience']}",
  "problem_solved": "{lbl['problem_solved']}",
  "solution": "{lbl['solution']}",
  "tone_of_voice": "{lbl['tone_of_voice']}",
  "posting_schedule": "{lbl['posting_schedule']}",
  "post_frequency": "{lbl['post_frequency']}",
  "content_themes": [
    "Theme 1",
    "Theme 2",
    "Theme 3"
  ],
  "summary": "{lbl['summary']}"
}}"""


async def analyze_social_posts(
    competitor_url: str,
    platform: str,
    posts: List[Dict[str, Any]],
    language: str = "vi",
) -> Dict[str, Any]:
    """
    Analyze a competitor's social posts with DeepSeek R1 reasoning.
    Always uses DeepSeek regardless of language — competitor analysis benefits from deep thinking.
    """
    if not posts:
        return {"_error": "No posts to analyze", "_url": competitor_url, "_platform": platform}

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    prompt = _build_social_analysis_prompt(competitor_url, platform, posts, language)

    client = openai.AsyncOpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )

    logger.info(f"[SocialAnalyzer] Analyzing {len(posts)} posts from {platform}: {competitor_url}")
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

    try:
        result = json.loads(content)
    except Exception as e:
        logger.error(f"[SocialAnalyzer] JSON parse error: {e}")
        result = {"_error": f"JSON parse failed: {e}", "_raw": content[:500]}

    result["_url"] = competitor_url
    result["_platform"] = platform
    result["_posts_analyzed"] = len(posts)
    logger.info(f"[SocialAnalyzer] ✅ Analysis done for {competitor_url}")
    return result


async def analyze_multiple_social(
    scraped_results: List[Dict[str, Any]],
    language: str = "vi",
) -> List[Dict[str, Any]]:
    """
    Analyze multiple scraped competitor results sequentially.
    Sequential (not parallel) to avoid DeepSeek R1 rate limits.
    """
    analyses = []
    for scraped in scraped_results:
        url = scraped.get("url", "")
        platform = scraped.get("platform", "unknown")
        posts = scraped.get("posts", [])

        if scraped.get("_error"):
            analyses.append({"_url": url, "_error": scraped["_error"], "_platform": platform})
            continue

        try:
            analysis = await analyze_social_posts(url, platform, posts, language)
            analyses.append(analysis)
        except Exception as e:
            logger.error(f"[SocialAnalyzer] Failed for {url}: {e}")
            analyses.append({"_url": url, "_error": str(e), "_platform": platform})

    return analyses
