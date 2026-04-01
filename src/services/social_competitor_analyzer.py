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

MAX_POST_CHARS = 200  # truncate each post — keeps prompt lean
MAX_POSTS_IN_PROMPT = 15


def _build_social_analysis_prompt(
    competitor_url: str,
    platform: str,
    posts: List[Dict[str, Any]],
    language: str,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    followers_count: Optional[int] = None,
) -> str:
    # Mark pinned posts in the posts block
    posts_block = ""
    for i, post in enumerate(posts[:MAX_POSTS_IN_PROMPT], 1):
        text = (post.get("text") or "").strip()[:MAX_POST_CHARS]
        date = post.get("date", "")
        likes = post.get("likes", "")
        comments = post.get("comments", "")
        shares = post.get("shares", "")
        views = post.get("views", "")
        is_pinned = post.get("is_pinned", False)
        meta_parts = []
        if date:
            meta_parts.append(date)
        if likes != "":
            meta_parts.append(f"{likes} likes")
        if comments != "":
            meta_parts.append(f"{comments} comments")
        if shares != "":
            meta_parts.append(f"{shares} shares")
        if views != "" and platform == "tiktok":
            meta_parts.append(f"{views} views")
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""
        pin_label = " 📌[PINNED]" if is_pinned else ""
        posts_block += f"{i}.{pin_label}{meta_str} {text}\n"

    # Build engagement context block — handle TikTok pinned/regular split
    engagement_block = ""
    m = engagement_metrics or {}

    def _metric_lines(label: str, data: dict, fc: Optional[int] = None) -> List[str]:
        lines = [f"  [{label}]"]
        if fc:
            lines.append(f"  - Followers: {fc:,}")
        if data.get("posts_analyzed") is not None:
            lines.append(f"  - Posts in sample: {data['posts_analyzed']}")
        if data.get("avg_likes") is not None:
            lines.append(f"  - Avg likes / post: {data['avg_likes']}")
        if data.get("avg_comments") is not None:
            lines.append(f"  - Avg comments / post: {data['avg_comments']}")
        if data.get("avg_shares") is not None:
            lines.append(f"  - Avg shares / post: {data['avg_shares']}")
        if data.get("avg_views") is not None:
            lines.append(f"  - Avg views / post: {data['avg_views']}")
        if data.get("engagement_rate_pct") is not None:
            lines.append(f"  - Engagement rate: {data['engagement_rate_pct']}%")
        if data.get("top_post_by_likes"):
            tp = data["top_post_by_likes"]
            lines.append(
                f"  - Top post ({tp['likes']} likes, {tp.get('views','?')} views): {(tp.get('text') or '')[:100]}"
            )
        return lines

    if m.get("has_pinned_split"):
        # TikTok with pinned posts — show three sections
        all_lines: List[str] = []
        if followers_count:
            all_lines.append(f"- Followers: {followers_count:,}")
        all_lines.append(
            "⚠️ NOTE: This TikTok page has PINNED posts. Pinned posts are usually brand highlight/promo videos that accumulate views over months/years. They SKEW overall averages significantly."
        )
        all_lines.append(
            "Use REGULAR post metrics to judge actual channel health and typical content performance."
        )
        all_lines.append("")

        if m.get("pinned"):
            all_lines += _metric_lines(
                "PINNED POSTS (brand highlight / promo — NOT representative of daily performance)",
                m["pinned"],
            )
            all_lines.append("")

        if m.get("regular"):
            all_lines += _metric_lines(
                "REGULAR POSTS (actual daily channel performance)", m["regular"]
            )
            all_lines.append("")

        if m.get("all"):
            all_lines += _metric_lines(
                "ALL POSTS COMBINED (skewed by pinned)", m["all"]
            )

        engagement_block = (
            "\n=== ENGAGEMENT METRICS ===\n" + "\n".join(all_lines) + "\n"
        )

    elif m:
        # Normal (no pinned split)
        lines = []
        if followers_count:
            lines.append(f"- Followers: {followers_count:,}")
        if m.get("avg_likes") is not None:
            lines.append(f"- Average likes / post: {m['avg_likes']}")
        if m.get("avg_comments") is not None:
            lines.append(f"- Average comments / post: {m['avg_comments']}")
        if m.get("avg_shares") is not None:
            lines.append(f"- Average shares / post: {m['avg_shares']}")
        if m.get("avg_views") is not None:
            lines.append(f"- Average views / post: {m['avg_views']}")
        if m.get("engagement_rate_pct") is not None:
            lines.append(
                f"- Engagement rate: {m['engagement_rate_pct']}% (interactions / followers)"
            )
        if m.get("video_post_count") is not None:
            lines.append(
                f"- Video posts: {m['video_post_count']}  |  Photo posts: {m['photo_post_count']}"
            )
        if m.get("avg_likes_video") is not None:
            lines.append(
                f"- Avg likes — video: {m['avg_likes_video']}  |  photo: {m['avg_likes_photo']}"
            )
        if m.get("top_post_by_likes"):
            tp = m["top_post_by_likes"]
            lines.append(
                f"- Top post ({tp['likes']} likes): {(tp.get('text') or '')[:120]}"
            )
        if lines:
            engagement_block = (
                "\n=== ENGAGEMENT METRICS ===\n" + "\n".join(lines) + "\n"
            )

    # Is TikTok with pinned split? Affects prompt instructions
    has_pinned_split = isinstance(engagement_metrics, dict) and engagement_metrics.get(
        "has_pinned_split"
    )

    if language in ("en", "fr"):
        lang_instruction = (
            "Respond entirely in English."
            if language == "en"
            else "Répondez entièrement en français."
        )
        intro = "You are a competitive intelligence expert. Analyze the following social media posts from a competitor."
        lbl = {
            "target_audience": "Target audience they are aiming at",
            "problem_solved": "Problem they are solving for customers",
            "solution": "Solution / value proposition being communicated",
            "tone_of_voice": "Tone of voice (e.g. professional, casual, humorous, educational…)",
            "posting_schedule": "Typical posting times / days (if detectable from dates)",
            "post_frequency": "Estimated posting frequency (posts per day or week)",
            "content_themes": "Main content themes or topics",
            "best_content_type": "Which content type gets the most engagement — base on likes/comments/views data from REGULAR posts",
            "engagement_verdict": (
                "TikTok channel health based on REGULAR posts only (excluding pinned). Rate as High/Medium/Low/Very Low and explain. "
                "Also explain what pinned posts reveal about their brand strategy."
                if has_pinned_split
                else "Based on followers count and avg likes/comments — is this page highly engaged, average, or poorly engaged? Explain why."
            ),
            "pinned_post_analysis": "Analysis of PINNED posts: what they reveal about the brand's top-performing content strategy, topic, and why they chose to pin it",
            "improvement_suggestions": "2-3 things we could do better than this competitor based on their weaknesses",
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
            "best_content_type": "Dạng nội dung nào được like/comment/view nhiều nhất — dựa trên dữ liệu các bài THƯỜNG (không tính bài ghim)",
            "engagement_verdict": (
                "Sức khỏe kênh TikTok dựa trên các bài THƯỜNG (không tính bài ghim). "
                "Đánh giá: Cao/Trung bình/Thấp/Rất thấp và giải thích tại sao. "
                "Nêu rõ bài ghim cho thấy điều gì về chiến lược nội dung của họ."
                if has_pinned_split
                else "Nhận xét về mức độ thu hút thực sự của trang này dựa trên tỉ lệ like/comment so với số followers — có thực sự hiệu quả không?"
            ),
            "pinned_post_analysis": "Phân tích bài ghim (pinned posts): nội dung gì được ghim, tại sao họ chọn ghim, bài ghim thể hiện chiến lược nội dung gì của thương hiệu",
            "improvement_suggestions": "2-3 điều chúng ta có thể làm tốt hơn đối thủ này dựa trên điểm yếu của họ",
            "summary": "Tóm tắt một đoạn về đối thủ này dựa trên dữ liệu bài đăng",
        }

    pinned_field = (
        f',\n  "pinned_post_analysis": "{lbl["pinned_post_analysis"]}"'
        if has_pinned_split
        else ""
    )

    return f"""{intro}

=== SOURCE: {platform.upper()} — {competitor_url} ===
{posts_block.strip()}
{engagement_block}
=== INSTRUCTIONS ===
{lang_instruction}
{"⚠️ IMPORTANT: This TikTok page has PINNED posts (marked 📌). Pinned posts accumulate views/likes over months and DO NOT represent typical daily content performance. Base your engagement_verdict and best_content_type on REGULAR posts only." if has_pinned_split else ""}
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
  "best_content_type": "{lbl['best_content_type']}",
  "engagement_verdict": "{lbl['engagement_verdict']}"{pinned_field},
  "improvement_suggestions": [
    "Suggestion 1",
    "Suggestion 2"
  ],
  "summary": "{lbl['summary']}"
}}"""


async def analyze_social_posts(
    competitor_url: str,
    platform: str,
    posts: List[Dict[str, Any]],
    language: str = "vi",
    engagement_metrics: Optional[Dict[str, Any]] = None,
    followers_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Analyze a competitor's social posts with DeepSeek R1 reasoning.
    Always uses DeepSeek regardless of language — competitor analysis benefits from deep thinking.
    """
    if not posts:
        return {
            "_error": "No posts to analyze",
            "_url": competitor_url,
            "_platform": platform,
        }

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    prompt = _build_social_analysis_prompt(
        competitor_url,
        platform,
        posts,
        language,
        engagement_metrics=engagement_metrics,
        followers_count=followers_count,
    )

    client = openai.AsyncOpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )

    logger.info(
        f"[SocialAnalyzer] Analyzing {len(posts)} posts from {platform}: {competitor_url}"
    )
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
    if engagement_metrics:
        result["_engagement_metrics"] = engagement_metrics
    logger.info(f"[SocialAnalyzer] ✅ Analysis done for {competitor_url}")
    return result


async def analyze_multiple_social(
    scraped_results: List[Dict[str, Any]],
    language: str = "vi",
    followers_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """
    Analyze multiple scraped competitor results sequentially.
    Sequential (not parallel) to avoid DeepSeek R1 rate limits.

    followers_counts: optional dict mapping URL → follower count
    """
    analyses = []
    for scraped in scraped_results:
        url = scraped.get("url", "")
        platform = scraped.get("platform", "unknown")
        posts = scraped.get("posts", [])
        metrics = scraped.get("engagement_metrics")
        fc = (followers_counts or {}).get(url) or scraped.get("page_followers")

        # If followers_count given, recompute metrics with it
        if fc and metrics:
            from src.services.apify_scraper import compute_engagement_metrics

            metrics = compute_engagement_metrics(posts, followers_count=fc)

        if scraped.get("_error"):
            analyses.append(
                {"_url": url, "_error": scraped["_error"], "_platform": platform}
            )
            continue

        try:
            analysis = await analyze_social_posts(
                url,
                platform,
                posts,
                language,
                engagement_metrics=metrics,
                followers_count=fc,
            )
            analyses.append(analysis)
        except Exception as e:
            logger.error(f"[SocialAnalyzer] Failed for {url}: {e}")
            analyses.append({"_url": url, "_error": str(e), "_platform": platform})

    return analyses
