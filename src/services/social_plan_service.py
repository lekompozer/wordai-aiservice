"""
Social Plan Service
Handles Brand DNA generation (ChatGPT gpt-5.4) and content generation per post (DeepSeek).

Multi-layer analysis pipeline:
  Layer 1 (parallel analyzers):
    - Brand website crawler → website summary
    - TikTok parser → TikTok insights
    - CompetitorAnalyzer → per-competitor summaries
    - BrandDocAnalyzer → PDF/doc summaries
    - ProductAnalyzer → product catalog summary
  Layer 2: Brand DNA synthesis (GPT-5.4, consumes only summaries)
  Layer 3: Plan structure (GPT-5.4, chunked 15 posts)
  Layer 4: Post content (DeepSeek, batched 5 posts)
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional

import openai

logger = logging.getLogger(__name__)


class SocialPlanService:
    """
    Orchestrates AI calls for social marketing plan generation.
    - Brand DNA: ChatGPT gpt-5.4
    - Plan Structure: ChatGPT gpt-5.4
    - Post Content: DeepSeek
    """

    def __init__(self):
        openai_key = os.getenv("CHATGPT_API_KEY") or os.getenv("OPENAI_API_KEY")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")

        if not openai_key:
            raise ValueError("CHATGPT_API_KEY not configured")
        if not deepseek_key:
            raise ValueError("DEEPSEEK_API_KEY not configured")

        self.chatgpt = openai.AsyncOpenAI(api_key=openai_key)
        self.deepseek = openai.AsyncOpenAI(
            api_key=deepseek_key, base_url="https://api.deepseek.com"
        )

    # ─────────────────────────────────────────
    # Phase 3: Brand DNA Generation
    # ─────────────────────────────────────────

    async def generate_brand_dna(
        self,
        brand_data: Dict[str, Any],
        tiktok_insights: Dict[str, Any],
        config: Dict[str, Any],
        competitor_summaries: Optional[List[Dict[str, Any]]] = None,
        brand_doc_summary: Optional[str] = None,
        product_summary: Optional[str] = None,
        audit_reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate Brand DNA from all analysis layer summaries.
        Uses ChatGPT gpt-5.4.

        New params (Layer 1 outputs):
            competitor_summaries: list of compact competitor dicts
            brand_doc_summary: merged PDF/doc summary string
            product_summary: compact product catalog summary
            audit_reference: snapshot from brand_comparisons (my_weaknesses, improvement_plan, etc.)

        Returns:
            Dict with brand_name, brand_voice, core_values, usp, target_audience,
            common_hashtags, suggested_topics, colors, platforms, industry, etc.
        """
        from src.services.competitor_analyzer import (
            format_competitor_summaries_for_prompt,
        )

        language = config.get("language", "vi")
        campaign_goal = config.get("campaign_goal", "awareness")
        goals = config.get("goals", "")  # free-text goals (v2)
        target_audience = config.get("target_audience", "")
        business_name = config.get("business_name", "")
        industry = config.get("industry", "")
        platforms = config.get("platforms", [])

        website_text = brand_data.get("combined_text", "")[:3000]
        tiktok_text = tiktok_insights.get("combined_text", "")[:2000]
        primary_color = brand_data.get("primary_color", "#000000")

        # Format optional context blocks
        competitor_block = ""
        if competitor_summaries:
            competitor_block = f"\n=== PHÂN TÍCH ĐỐI THỦ ===\n{format_competitor_summaries_for_prompt(competitor_summaries)}"

        brand_doc_block = ""
        if brand_doc_summary and brand_doc_summary.strip():
            brand_doc_block = (
                f"\n=== TÀI LIỆU THƯƠNG HIỆU ===\n{brand_doc_summary[:1500]}"
            )

        product_block = ""
        if product_summary and product_summary.strip():
            product_block = f"\n=== SẢN PHẨM / DỊCH VỤ ===\n{product_summary[:800]}"

        audit_block = ""
        if audit_reference and isinstance(audit_reference, dict):
            weaknesses = audit_reference.get("my_weaknesses", [])
            improvement = audit_reference.get("improvement_plan", "")
            recs = audit_reference.get("content_strategy_recommendations", [])
            parts = []
            if weaknesses:
                parts.append("Điểm yếu hiện tại: " + "; ".join(weaknesses[:3]))
            if improvement:
                parts.append(f"Hướng cải thiện: {improvement[:300]}")
            if recs:
                parts.append("Đề xuất content: " + "; ".join(recs[:3]))
            if parts:
                audit_block = "\n=== PHÂN TÍCH SOCIAL AUDIT ===\n" + "\n".join(parts)

        platforms_str = ", ".join(platforms) if platforms else "TikTok, Facebook"
        industry_str = industry or "Chưa xác định"
        goal_str = goals or campaign_goal

        prompt = f"""Phân tích data sau và tạo Brand DNA cho chiến lược nội dung mạng xã hội:

=== THÔNG TIN DOANH NGHIỆP ===
Tên: {business_name}
Ngành: {industry_str}
Nền tảng target: {platforms_str}
Mục tiêu: {goal_str}
Đối tượng mục tiêu: {target_audience or "Chưa xác định"}
Màu chính brand: {primary_color}

=== WEBSITE DATA ===
{website_text or "Không có dữ liệu website"}

=== TIKTOK CAPTIONS (50 bài gần nhất) ===
{tiktok_text or "Không có dữ liệu TikTok"}{brand_doc_block}{product_block}{competitor_block}{audit_block}

=== YÊU CẦU ===
Ngôn ngữ output: {language}
Dựa trên phân tích đối thủ (nếu có), hãy xác định điểm khác biệt và cơ hội content.

Trả về JSON (chỉ JSON, không có text khác):
{{
  "brand_name": "tên brand",
  "industry": "{industry_str}",
  "target_platforms": {json.dumps(platforms if platforms else ["tiktok", "facebook"])},
  "brand_voice": "Mô tả giọng văn 2-3 câu",
  "core_values": ["giá trị 1", "giá trị 2"],
  "usp": "Unique Selling Proposition",
  "target_audience": "mô tả đối tượng",
  "competitive_advantage": "Lợi thế cạnh tranh so với đối thủ (dựa trên phân tích)",
  "content_opportunities": ["Cơ hội content 1", "Cơ hội content 2"],
  "typical_caption_structure": "cấu trúc caption điển hình",
  "common_hashtags": ["#hashtag1", "#hashtag2"],
  "topics_used": ["topic đã dùng"],
  "suggested_topics": ["topic mới 1", "topic mới 2"],
  "colors": {{
    "primary": "{primary_color}",
    "secondary": "#ffffff"
  }}
}}"""

        response = await self.chatgpt.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia brand strategy và social media marketing. Luôn trả về JSON hợp lệ.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content
        brand_dna = json.loads(result_text)

        # Ensure colors are set correctly
        if not brand_dna.get("colors"):
            brand_dna["colors"] = {"primary": primary_color, "secondary": "#ffffff"}
        elif not brand_dna["colors"].get("primary"):
            brand_dna["colors"]["primary"] = primary_color

        logger.info(
            f"✅ Brand DNA generated for '{brand_dna.get('brand_name', business_name)}'"
        )
        return brand_dna

    # ─────────────────────────────────────────
    # Phase 4: Plan Structure Generation
    # ─────────────────────────────────────────

    async def generate_plan_structure(
        self,
        brand_dna: Dict[str, Any],
        config: Dict[str, Any],
        product_analysis: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate 30/60-day plan structure (topic + pillar only, no captions).
        Uses ChatGPT gpt-5.4 in chunks of 15 posts.

        Args:
            product_analysis: output from ProductAnalyzer (optional, richer than raw products)

        Returns:
            List of post dicts with day, date, content_pillar, topic, image_style_hint, product_ref,
            platform (new)
        """
        from src.services.product_analyzer import format_products_for_plan_prompt

        language = config.get("language", "vi")
        posts_per_week = config.get("posts_per_week", 5)
        total_posts = min(posts_per_week * 4, 60)  # 4 weeks
        products = config.get("products", [])
        start_date = config.get("start_date", "2026-04-01")
        platforms = config.get("platforms", [])

        # Use richer product analysis if available
        if product_analysis and product_analysis.get("product_list"):
            product_list_str = format_products_for_plan_prompt(
                product_analysis["product_list"]
            )
        else:
            product_names = [p.get("name", "") for p in products if p.get("name")]
            product_list_str = ", ".join(product_names) if product_names else "Chưa có"

        platforms_str = ", ".join(platforms) if platforms else "TikTok"
        # Include competitive advantage if available from brand DNA
        competitive_advantage = brand_dna.get("competitive_advantage", "")
        content_opportunities = brand_dna.get("content_opportunities", [])

        brand_dna_str = json.dumps(brand_dna, ensure_ascii=False)[:2000]

        # Generate in chunks of 15 posts
        chunk_size = 15
        all_posts = []

        for chunk_start in range(0, total_posts, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_posts)
            chunk_count = chunk_end - chunk_start
            existing_topics = [p.get("topic", "") for p in all_posts]

            competitive_hint = ""
            if competitive_advantage or content_opportunities:
                ops_str = (
                    ", ".join(content_opportunities[:3])
                    if content_opportunities
                    else ""
                )
                competitive_hint = (
                    f"\n- Khai thác lợi thế cạnh tranh: {competitive_advantage}"
                )
                if ops_str:
                    competitive_hint += (
                        f"\n- Cơ hội content từ phân tích đối thủ: {ops_str}"
                    )

            prompt = f"""Bạn là chuyên gia chiến lược nội dung mạng xã hội.

=== BRAND DNA ===
{brand_dna_str}

=== DANH SÁCH SẢN PHẨM ===
{product_list_str}

=== YÊU CẦU ===
Tạo CẤU TRÚC {chunk_count} bài (bài {chunk_start + 1} đến {chunk_end} trong tổng {total_posts} bài).
- Nền tảng: {platforms_str}
- Ngày bắt đầu: {start_date} (day=1)
- Ngôn ngữ: {language}
- Content mix: 40% educational, 20% promotional, 25% engagement, 15% entertaining{competitive_hint}
- KHÔNG viết caption, hook hay hashtags — chỉ lên kế hoạch chủ đề
- KHÔNG lặp topic: {json.dumps(existing_topics[:20], ensure_ascii=False) if existing_topics else "Chưa có"}

Với mỗi bài, trả về:
- day (số ngày 1-{total_posts})
- content_pillar (educational/promotional/engagement/entertaining)
- topic (tiêu đề ngắn, gợi ý nội dung rõ ràng, không trùng lặp)
- image_style_hint (educational_infographic / product_hero / lifestyle / fun_meme)
- product_ref (tên sản phẩm nếu content_pillar=promotional, null nếu không)
- platform (nền tảng phù hợp nhất: {platforms_str.split(",")[0].strip().lower() if platforms else "tiktok"})

Trả về JSON array với đúng {chunk_count} objects. Chỉ JSON, không text khác."""

            response = await self.chatgpt.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là chuyên gia social media marketing. Luôn trả về JSON array hợp lệ.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=3000,
                temperature=0.7,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            parsed = json.loads(result_text)

            # Handle both {"posts": [...]} and [...]
            if isinstance(parsed, dict):
                chunk_posts = parsed.get(
                    "posts",
                    parsed.get("items", list(parsed.values())[0] if parsed else []),
                )
            else:
                chunk_posts = parsed

            all_posts.extend(chunk_posts[:chunk_count])
            logger.info(
                f"   📅 Generated structure for posts {chunk_start + 1}-{chunk_end}"
            )

        # Normalize and add IDs
        import uuid
        from datetime import datetime, timedelta

        primary_platform = platforms[0].lower() if platforms else "tiktok"

        try:
            base_date = datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            base_date = datetime(2026, 4, 1)

        normalized = []
        for i, p in enumerate(all_posts[:total_posts]):
            day = p.get("day", i + 1)
            post_date = base_date + timedelta(days=day - 1)
            normalized.append(
                {
                    "post_id": f"post_{uuid.uuid4().hex[:12]}",
                    "day": day,
                    "date": post_date.strftime("%Y-%m-%d"),
                    "platform": p.get("platform", primary_platform),
                    "content_pillar": p.get("content_pillar", "educational"),
                    "topic": p.get("topic", f"Post ngày {day}"),
                    "image_style_hint": p.get("image_style_hint", "lifestyle"),
                    "product_ref": p.get("product_ref"),
                    # Phase 5 fields (DeepSeek fills later)
                    "hook": None,
                    "caption": None,
                    "hashtags": None,
                    "image_prompt": None,
                    "cta": None,
                    # Phase 6 fields (image worker fills later)
                    "image_url": None,
                    "image_job_id": None,
                    "image_generated_at": None,
                    # Custom image (user upload)
                    "custom_image_url": None,
                }
            )

        logger.info(f"✅ Plan structure generated: {len(normalized)} posts")
        return normalized

    # ─────────────────────────────────────────
    # Phase 4a: Plan Summary (30-day overview)
    # ─────────────────────────────────────────

    async def generate_plan_summary(
        self,
        brand_dna: Dict[str, Any],
        config: Dict[str, Any],
        audit_reference: Optional[Dict[str, Any]] = None,
        business_info: Optional[Dict[str, Any]] = None,
        product_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a 30-day overview plan split into 4 weeks.
        Uses ChatGPT gpt-5.4.

        Returns:
            {
              "overview": "...",
              "weeks": [
                {
                  "week": 1,
                  "theme": "...",
                  "objectives": "...",
                  "style_notes": "...",
                  "image_guidance": "...",
                  "images_per_post": 1,
                  "posts_count": 5,
                  "weekly_goal": "..."
                }, ...
              ]
            }
        """
        from src.services.product_analyzer import format_products_for_plan_prompt

        language = config.get("language", "vi")
        campaign_name = config.get("campaign_name", "")
        goals = config.get("goals", config.get("campaign_goal", "awareness"))
        platforms = config.get("platforms", [])
        posts_per_week = config.get("posts_per_week", 5)
        total_posts = min(posts_per_week * 4, 60)
        package = config.get("package", "")

        brand_name = brand_dna.get("brand_name", config.get("business_name", ""))
        brand_voice = brand_dna.get("brand_voice", "")
        usp = brand_dna.get("usp", "")
        target_audience = brand_dna.get(
            "target_audience", config.get("target_audience", "")
        )
        platforms_str = ", ".join(platforms) if platforms else "Facebook"

        # Business info block
        biz_block = ""
        if business_info and isinstance(business_info, dict):
            biz_parts = []
            if business_info.get("description"):
                biz_parts.append(f"Mô tả: {business_info['description'][:300]}")
            if business_info.get("key_values"):
                biz_parts.append(
                    "Giá trị cốt lõi: " + ", ".join(business_info["key_values"][:4])
                )
            if business_info.get("competitive_advantages"):
                biz_parts.append(
                    "Lợi thế: " + ", ".join(business_info["competitive_advantages"][:2])
                )
            if biz_parts:
                biz_block = "\n=== THÔNG TIN DOANH NGHIỆP ===\n" + "\n".join(biz_parts)

        # Products block
        product_block = ""
        if product_analysis and product_analysis.get("product_list"):
            product_block = (
                "\n=== SẢN PHẨM ===\n"
                + format_products_for_plan_prompt(product_analysis["product_list"])[
                    :600
                ]
            )
        elif config.get("products"):
            names = [p.get("name", "") for p in config["products"] if p.get("name")]
            if names:
                product_block = "\n=== SẢN PHẨM ===\n" + ", ".join(names)

        # Audit reference block
        audit_block = ""
        if audit_reference and isinstance(audit_reference, dict):
            parts = []
            if audit_reference.get("my_weaknesses"):
                parts.append(
                    "Điểm yếu hiện tại: "
                    + "; ".join(audit_reference["my_weaknesses"][:3])
                )
            if audit_reference.get("improvement_plan"):
                parts.append(
                    f"Hướng cải thiện: {audit_reference['improvement_plan'][:300]}"
                )
            if audit_reference.get("content_strategy_recommendations"):
                parts.append(
                    "Đề xuất nội dung: "
                    + "; ".join(audit_reference["content_strategy_recommendations"][:3])
                )
            if parts:
                audit_block = (
                    "\n=== PHÂN TÍCH SOCIAL AUDIT (THAM KHẢO) ===\n" + "\n".join(parts)
                )

        prompt = f"""Bạn là CMO của thương hiệu {brand_name}.

CAMPAIGN: {campaign_name or 'Chiến dịch marketing tháng này'}
MỤC TIÊU: {goals}
KÊNH: {platforms_str} — {posts_per_week} bài/tuần trong 4 tuần, tổng {total_posts} bài

BRAND DNA:
- Giọng văn: {brand_voice}
- USP: {usp}
- Đối tượng: {target_audience}{biz_block}{product_block}{audit_block}

Hãy tạo KẾ HOẠCH TỔNG QUAN 30 ngày (4 tuần) bao gồm:
- Tổng quan chiến lược campaign
- Chủ đề mỗi tuần
- Mục tiêu cụ thể từng tuần
- Hướng dẫn giọng văn & style tổng quát cho tuần đó
- Hướng dẫn hình ảnh (màu sắc, bố cục, phong cách)
- Số hình ảnh khuyến nghị mỗi bài (dựa trên kênh và package: {package})
- Mục tiêu cuối tháng (ở tuần 4)

Trả về JSON (chỉ JSON):
{{
  "overview": "Tổng quan chiến lược campaign 2-3 câu",
  "weeks": [
    {{
      "week": 1,
      "theme": "Chủ đề tuần",
      "objectives": "Mục tiêu tuần này",
      "style_notes": "Hướng dẫn giọng văn, tone, emoji, cấu trúc bài",
      "image_guidance": "Hướng dẫn hình ảnh: màu sắc, bố cục, số ảnh/bài",
      "images_per_post": 1,
      "posts_count": {posts_per_week},
      "weekly_goal": "Kết quả mong đợi cuối tuần"
    }}
  ]
}}"""

        response = await self.chatgpt.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia chiến lược nội dung mạng xã hội. Luôn trả về JSON hợp lệ.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        # Ensure weeks is a list
        if not isinstance(result.get("weeks"), list):
            result["weeks"] = []
        for i, week in enumerate(result["weeks"]):
            week.setdefault("week", i + 1)
            week.setdefault("posts_count", posts_per_week)
        logger.info(f"✅ Plan summary generated: {len(result.get('weeks', []))} weeks")
        return result

    # ─────────────────────────────────────────
    # Phase 4b: Weekly Detail Plans
    # ─────────────────────────────────────────

    async def generate_weekly_plan(
        self,
        week_summary: Dict[str, Any],
        brand_dna: Dict[str, Any],
        config: Dict[str, Any],
        existing_topics: Optional[List[str]] = None,
        week_start_day: int = 1,
        week_start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate daily breakdown for one week from the week_summary.
        Uses ChatGPT gpt-5.4.

        Returns:
            {
              "week": 1,
              "days": [
                {
                  "day": 1, "date": "YYYY-MM-DD",
                  "topic": "...", "content_pillar": "educational",
                  "hook_direction": "...", "image_guidance": "...",
                  "platform": "facebook"
                }, ...
              ]
            }
        """
        language = config.get("language", "vi")
        platforms = config.get("platforms", [])
        primary_platform = platforms[0].lower() if platforms else "facebook"
        posts_count = week_summary.get("posts_count", config.get("posts_per_week", 5))
        week_num = week_summary.get("week", 1)
        existing = existing_topics or []

        brand_dna_short = {
            "brand_name": brand_dna.get("brand_name"),
            "brand_voice": brand_dna.get("brand_voice"),
            "usp": brand_dna.get("usp"),
        }

        prompt = f"""Tạo KẾ HOẠCH CHI TIẾT tuần {week_num}.

=== TÓM TẮT TUẦN {week_num} ===
Chủ đề: {week_summary.get('theme', '')}
Mục tiêu: {week_summary.get('objectives', '')}
Giọng văn & style: {week_summary.get('style_notes', '')}
Hướng dẫn hình ảnh: {week_summary.get('image_guidance', '')}

=== BRAND DNA ===
{json.dumps(brand_dna_short, ensure_ascii=False)}

=== YÊU CẦU ===
- Ngôn ngữ: {language}
- Kênh chính: {primary_platform}
- Số bài trong tuần: {posts_count}
- Ngày bắt đầu (day số): {week_start_day}
- Ngày bắt đầu (date): {week_start_date or 'tính từ day'}
- Content mix: 40% educational, 20% promotional, 25% engagement, 15% entertaining
- KHÔNG lặp topic: {json.dumps(existing[:15], ensure_ascii=False) if existing else '[]'}

Với mỗi bài, trả về:
- day (số ngày tuyệt đối, từ {week_start_day})
- date (YYYY-MM-DD nếu biết)
- topic (chủ đề cụ thể, không trùng)
- content_pillar (educational/promotional/engagement/entertaining/brand_story/behind_scenes)
- hook_direction (hướng viết câu mở đầu)
- image_guidance (hướng dẫn hình ảnh cụ thể cho bài này)
- platform

Trả về JSON (chỉ JSON):
{{"week": {week_num}, "days": [{{"day": N, "date": "YYYY-MM-DD", "topic": "...", "content_pillar": "...", "hook_direction": "...", "image_guidance": "...", "platform": "{primary_platform}"}}]}}"""

        response = await self.chatgpt.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia social media marketing. Luôn trả về JSON hợp lệ.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        if not isinstance(result.get("days"), list):
            result = {"week": week_num, "days": []}
        result["week"] = week_num
        logger.info(
            f"✅ Weekly plan generated: week {week_num} → {len(result.get('days', []))} days"
        )
        return result

    # ─────────────────────────────────────────
    # Phase 5 helper: Flatten week_plans → posts[]
    # ─────────────────────────────────────────

    def flatten_week_plans_to_posts(
        self,
        week_plans: Dict[str, Any],
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert week_plans dict (from generate_weekly_plan) into a flat posts[] list,
        adding post_id, date, and empty content fields.
        """
        import uuid as _uuid
        from datetime import datetime as _dt, timedelta

        start_date_str = config.get("start_date", "2026-04-01")
        platforms = config.get("platforms", [])
        primary_platform = platforms[0].lower() if platforms else "facebook"

        try:
            base_date = _dt.strptime(start_date_str, "%Y-%m-%d")
        except Exception:
            base_date = _dt(2026, 4, 1)

        posts = []
        for week_key in sorted(week_plans.keys(), key=lambda k: int(k)):
            week_data = week_plans[week_key]
            for day_item in week_data.get("days", []):
                day = day_item.get("day", 1)
                date_str = day_item.get("date") or (
                    base_date + timedelta(days=day - 1)
                ).strftime("%Y-%m-%d")
                posts.append(
                    {
                        "post_id": f"post_{_uuid.uuid4().hex[:12]}",
                        "day": day,
                        "date": date_str,
                        "platform": day_item.get("platform", primary_platform),
                        "content_pillar": day_item.get("content_pillar", "educational"),
                        "topic": day_item.get("topic", f"Post ngày {day}"),
                        "image_style_hint": day_item.get("image_guidance", ""),
                        "hook_direction": day_item.get("hook_direction", ""),
                        "product_ref": day_item.get("product_ref"),
                        "hook": None,
                        "caption": None,
                        "hashtags": None,
                        "image_prompt": None,
                        "cta": None,
                        "image_url": None,
                        "image_job_id": None,
                        "image_generated_at": None,
                        "custom_image_url": None,
                    }
                )

        # Sort by day
        posts.sort(key=lambda p: p["day"])
        logger.info(f"✅ Flattened {len(posts)} posts from week_plans")
        return posts

    # ─────────────────────────────────────────
    # Phase 5: Content Generation per Post (DeepSeek)
    # ─────────────────────────────────────────

    async def generate_post_content(
        self,
        brand_dna: Dict[str, Any],
        post: Dict[str, Any],
        config: Dict[str, Any],
        custom_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate content for a single post using DeepSeek.

        Returns:
            Dict with hook, caption, hashtags, image_prompt, cta
        """
        language = config.get("language", "vi")
        brand_dna_str = json.dumps(brand_dna, ensure_ascii=False)[:1500]

        instruction_part = (
            f"\nYêu cầu đặc biệt: {custom_instruction}" if custom_instruction else ""
        )
        hook_direction = post.get("hook_direction", "")
        hook_hint = f"\n- Hướng mở đầu: {hook_direction}" if hook_direction else ""
        platforms = config.get("platforms", [])
        platform_str = post.get("platform") or (
            platforms[0].lower() if platforms else "facebook"
        )

        prompt = f"""Bạn là copywriter chuyên mạng xã hội ({platform_str}).

=== BRAND DNA ===
{brand_dna_str}

=== BÀI POST CẦN VIẾT ===
- Ngày: {post.get('day')} | Kênh: {platform_str} | Trụ nội dung: {post.get('content_pillar', 'educational')}
- Chủ đề: {post.get('topic', '')}
- Hướng hình ảnh: {post.get('image_style_hint', '')}
- Sản phẩm (nếu có): {post.get('product_ref') or 'Không có'}
- Ngôn ngữ: {language}{hook_hint}{instruction_part}

Viết nội dung theo ĐÚNG giọng văn brand_voice ở trên.

Trả về JSON (chỉ JSON):
{{
  "hook": "Câu mở đầu thu hút trong 3 giây đầu (≤15 từ)",
  "caption": "Caption đầy đủ 150-200 từ, đúng giọng brand, kết thúc bằng CTA",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "image_prompt": "Mô tả chi tiết ảnh minh hoạ cho post này, màu sắc theo brand",
  "cta": "Call-to-action ngắn gọn"
}}"""

        response = await self.deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a TikTok copywriter. Always return valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "hook": result.get("hook", ""),
            "caption": result.get("caption", ""),
            "hashtags": result.get("hashtags", []),
            "image_prompt": result.get("image_prompt", ""),
            "cta": result.get("cta", ""),
        }

    async def generate_all_content(
        self,
        brand_dna: Dict[str, Any],
        posts: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate content for all posts in batches.
        Processes 5 posts per batch, 3 batches in parallel.

        Returns:
            Updated posts list with hook/caption/hashtags/image_prompt/cta filled in
        """
        batch_size = 5
        max_parallel = 3

        updated_posts = posts.copy()

        # Create batches
        batches = [posts[i : i + batch_size] for i in range(0, len(posts), batch_size)]
        logger.info(
            f"📝 Generating content for {len(posts)} posts in {len(batches)} batches..."
        )

        # Process batches in parallel groups
        batch_idx = 0
        while batch_idx < len(batches):
            parallel_batches = batches[batch_idx : batch_idx + max_parallel]

            async def process_batch(batch):
                results = []
                for post in batch:
                    try:
                        content = await self.generate_post_content(
                            brand_dna, post, config
                        )
                        results.append((post["post_id"], content))
                    except Exception as e:
                        logger.error(
                            f"Failed to generate content for post {post.get('post_id')}: {e}"
                        )
                        results.append((post["post_id"], None))
                return results

            tasks = [process_batch(batch) for batch in parallel_batches]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Apply results to posts
            post_map = {p["post_id"]: i for i, p in enumerate(updated_posts)}
            for batch_result in batch_results:
                if isinstance(batch_result, Exception):
                    logger.error(f"Batch failed: {batch_result}")
                    continue
                for post_id, content in batch_result:
                    if content and post_id in post_map:
                        idx = post_map[post_id]
                        updated_posts[idx].update(content)

            batch_idx += max_parallel
            logger.info(
                f"   ✅ Processed {min(batch_idx * batch_size, len(posts))}/{len(posts)} posts"
            )

        return updated_posts
