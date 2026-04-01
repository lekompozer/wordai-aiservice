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
    ) -> Dict[str, Any]:
        """
        Generate Brand DNA from all analysis layer summaries.
        Uses ChatGPT gpt-5.4.

        New params (Layer 1 outputs):
            competitor_summaries: list of compact competitor dicts
            brand_doc_summary: merged PDF/doc summary string
            product_summary: compact product catalog summary

        Returns:
            Dict with brand_name, brand_voice, core_values, usp, target_audience,
            common_hashtags, suggested_topics, colors, platforms, industry, etc.
        """
        from src.services.competitor_analyzer import (
            format_competitor_summaries_for_prompt,
        )

        language = config.get("language", "vi")
        campaign_goal = config.get("campaign_goal", "awareness")
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

        platforms_str = ", ".join(platforms) if platforms else "TikTok, Facebook"
        industry_str = industry or "Chưa xác định"

        prompt = f"""Phân tích data sau và tạo Brand DNA cho chiến lược nội dung mạng xã hội:

=== THÔNG TIN DOANH NGHIỆP ===
Tên: {business_name}
Ngành: {industry_str}
Nền tảng target: {platforms_str}
Mục tiêu chiến dịch: {campaign_goal}
Đối tượng mục tiêu: {target_audience or "Chưa xác định"}
Màu chính brand: {primary_color}

=== WEBSITE DATA ===
{website_text or "Không có dữ liệu website"}

=== TIKTOK CAPTIONS (50 bài gần nhất) ===
{tiktok_text or "Không có dữ liệu TikTok"}{brand_doc_block}{product_block}{competitor_block}

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

        prompt = f"""Bạn là copywriter chuyên TikTok.

=== BRAND DNA ===
{brand_dna_str}

=== BÀI POST CẦN VIẾT ===
- Ngày: {post.get('day')} | Trụ nội dung: {post.get('content_pillar', 'educational')}
- Chủ đề: {post.get('topic', '')}
- Sản phẩm (nếu có): {post.get('product_ref') or 'Không có'}
- Ngôn ngữ: {language}{instruction_part}

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
