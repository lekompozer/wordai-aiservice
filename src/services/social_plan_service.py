"""
Social Plan Service
Handles Brand DNA generation (ChatGPT gpt-5.4) and content generation per post (DeepSeek).
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
        openai_key = os.getenv("OPENAI_API_KEY")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")

        if not openai_key:
            raise ValueError("OPENAI_API_KEY not configured")
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
    ) -> Dict[str, Any]:
        """
        Generate Brand DNA from crawled website data and TikTok posts.
        Uses ChatGPT gpt-5.4.

        Returns:
            Dict with brand_name, brand_voice, core_values, usp, target_audience,
            common_hashtags, suggested_topics, colors, etc.
        """
        language = config.get("language", "vi")
        campaign_goal = config.get("campaign_goal", "awareness")
        target_audience = config.get("target_audience", "")
        business_name = config.get("business_name", "")

        website_text = brand_data.get("combined_text", "")[:3000]
        tiktok_text = tiktok_insights.get("combined_text", "")[:2000]
        primary_color = brand_data.get("primary_color", "#000000")

        prompt = f"""Phân tích data sau và tạo Brand DNA cho chiến lược TikTok:

=== THÔNG TIN DOANH NGHIỆP ===
Tên: {business_name}
Mục tiêu chiến dịch: {campaign_goal}
Đối tượng mục tiêu: {target_audience or "Chưa xác định"}
Màu chính brand: {primary_color}

=== WEBSITE DATA ===
{website_text or "Không có dữ liệu website"}

=== TIKTOK CAPTIONS (50 bài gần nhất) ===
{tiktok_text or "Không có dữ liệu TikTok"}

=== YÊU CẦU ===
Ngôn ngữ output: {language}

Trả về JSON (chỉ JSON, không có text khác):
{{
  "brand_name": "tên brand",
  "brand_voice": "Mô tả giọng văn 2-3 câu",
  "core_values": ["giá trị 1", "giá trị 2"],
  "usp": "Unique Selling Proposition",
  "target_audience": "mô tả đối tượng",
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
                    "content": "Bạn là chuyên gia brand strategy và TikTok marketing. Luôn trả về JSON hợp lệ.",
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
    ) -> List[Dict[str, Any]]:
        """
        Generate 30-day plan structure (topic + pillar only, no captions).
        Uses ChatGPT gpt-5.4 in chunks of 15 posts.

        Returns:
            List of post dicts with day, date, content_pillar, topic, image_style_hint, product_ref
        """
        language = config.get("language", "vi")
        posts_per_week = config.get("posts_per_week", 5)
        total_posts = min(posts_per_week * 4, 60)  # 4 weeks
        products = config.get("products", [])
        start_date = config.get("start_date", "2026-04-01")

        product_names = [p.get("name", "") for p in products if p.get("name")]
        product_list_str = ", ".join(product_names) if product_names else "Chưa có"

        brand_dna_str = json.dumps(brand_dna, ensure_ascii=False)[:2000]

        # Generate in chunks of 15 posts
        chunk_size = 15
        all_posts = []

        for chunk_start in range(0, total_posts, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_posts)
            chunk_count = chunk_end - chunk_start
            existing_topics = [p.get("topic", "") for p in all_posts]

            prompt = f"""Bạn là chuyên gia chiến lược nội dung TikTok.

=== BRAND DNA ===
{brand_dna_str}

=== DANH SÁCH SẢN PHẨM ===
{product_list_str}

=== YÊU CẦU ===
Tạo CẤU TRÚC {chunk_count} bài TikTok (bài {chunk_start + 1} đến {chunk_end} trong tổng {total_posts} bài).
- Ngày bắt đầu: {start_date} (day=1)
- Ngôn ngữ: {language}
- Content mix: 40% educational, 20% promotional, 25% engagement, 15% entertaining
- KHÔNG viết caption, hook hay hashtags — chỉ lên kế hoạch chủ đề
- KHÔNG lặp topic: {json.dumps(existing_topics[:20], ensure_ascii=False) if existing_topics else "Chưa có"}

Với mỗi bài, trả về:
- day (số ngày 1-{total_posts})
- content_pillar (educational/promotional/engagement/entertaining)
- topic (tiêu đề ngắn, gợi ý nội dung rõ ràng, không trùng lặp)
- image_style_hint (educational_infographic / product_hero / lifestyle / fun_meme)
- product_ref (tên sản phẩm nếu content_pillar=promotional, null nếu không)

Trả về JSON array với đúng {chunk_count} objects. Chỉ JSON, không text khác."""

            response = await self.chatgpt.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là chuyên gia TikTok marketing. Luôn trả về JSON array hợp lệ.",
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
