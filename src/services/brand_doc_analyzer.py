"""
Brand Document Analyzer Service

Layer 1 analysis: Extracts text from PDF/text brand documents stored in R2,
then LLM-summarizes each document's content into a compact brand context summary
(~500 tokens) for use in Brand DNA synthesis.

Chunking strategy to avoid token overflow:
  1. Extract raw text from PDF
  2. Split into chunks of ~3000 characters
  3. Summarize each chunk → paragraph-level summaries
  4. Merge all chunk summaries → single brand doc summary
"""

import asyncio
import json
import logging
import os
from io import BytesIO
from typing import Any, Dict, List, Optional

import boto3

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 3000
MAX_CHUNKS_PER_DOC = 6  # Max 6 chunks per PDF (~18k chars = ~30 pages)
MAX_DOCS = 10
MAX_SUMMARY_TOKENS = 600


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text.strip())
        return "\n".join(pages_text)
    except Exception as e:
        logger.warning(f"pypdf extraction failed: {e}. Trying PyPDF2...")
        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            return "\n".join(
                (page.extract_text() or "").strip() for page in reader.pages
            )
        except Exception as e2:
            logger.error(f"PDF extraction failed entirely: {e2}")
            return ""


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS) -> List[str]:
    """Split text into chunks at paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > chunk_size and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para) + 1

    if current:
        chunks.append("\n".join(current))

    return chunks[:MAX_CHUNKS_PER_DOC]


async def _summarize_chunk(
    chunk_text: str,
    doc_name: str,
    chunk_idx: int,
    deepseek_client,
) -> str:
    """Summarize one chunk of a brand document into a short paragraph."""
    prompt = f"""Tóm tắt đoạn tài liệu thương hiệu sau thành 2-3 câu ngắn gọn,
chỉ giữ lại thông tin quan trọng về thương hiệu, sản phẩm, giọng điệu, khách hàng mục tiêu.

=== TÀI LIỆU: {doc_name} (phần {chunk_idx + 1}) ===
{chunk_text[:CHUNK_SIZE_CHARS]}

Trả về đoạn tóm tắt ngắn gọn (không cần JSON)."""

    try:
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia tóm tắt tài liệu thương hiệu. Trả lời ngắn gọn, xúc tích.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Chunk summary failed (doc={doc_name}, chunk={chunk_idx}): {e}")
        return chunk_text[:400]  # fallback: raw text truncated


async def _summarize_document(
    doc_name: str,
    doc_text: str,
    deepseek_client,
) -> str:
    """
    Summarize a full document via chunked-then-merged approach.

    Returns:
        Compact summary string (~500 tokens)
    """
    if not doc_text.strip():
        return f"[{doc_name}: empty document]"

    chunks = _chunk_text(doc_text)
    logger.info(f"  📄 {doc_name}: {len(chunks)} chunks to summarize")

    # Summarize all chunks in parallel (up to 5 at a time)
    chunk_summaries = []
    for i in range(0, len(chunks), 5):
        batch = chunks[i : i + 5]
        results = await asyncio.gather(
            *[
                _summarize_chunk(c, doc_name, i + j, deepseek_client)
                for j, c in enumerate(batch)
            ],
            return_exceptions=True,
        )
        for r in results:
            chunk_summaries.append(r if isinstance(r, str) else "")

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    # Merge chunk summaries into final document summary
    merged_text = "\n".join(f"- {s}" for s in chunk_summaries if s)
    merge_prompt = f"""Dưới đây là các đoạn tóm tắt từ tài liệu thương hiệu "{doc_name}".
Hãy tổng hợp thành 1 đoạn tóm tắt cuối cùng (≤150 từ), tập trung vào:
- Giá trị cốt lõi của thương hiệu
- Sản phẩm/dịch vụ chính
- Khách hàng mục tiêu
- Giọng điệu và phong cách truyền thông

=== CÁC ĐOẠN TÓM TẮT ===
{merged_text[:3000]}

Trả về tóm tắt cuối (không cần JSON, không cần tiêu đề)."""

    try:
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Tóm tắt tài liệu thương hiệu ngắn gọn."},
                {"role": "user", "content": merge_prompt},
            ],
            max_tokens=250,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Document merge summary failed for {doc_name}: {e}")
        return merged_text[:800]


async def fetch_and_analyze_brand_docs(
    asset_ids: List[str],
    db,
    deepseek_client,
) -> str:
    """
    Fetch brand document assets (PDFs/text files) from R2, extract text,
    and return a merged brand context summary string.

    Args:
        asset_ids: List of plan_asset_id strings (type='brand_doc')
        db: MongoDB database handle
        deepseek_client: AsyncOpenAI-compatible DeepSeek client

    Returns:
        Merged summary string of all brand documents (~500 tokens)
    """
    if not asset_ids:
        return ""

    # Look up R2 keys from MongoDB
    assets = list(
        db["social_plan_assets"].find(
            {"asset_id": {"$in": asset_ids}, "type": "brand_doc"},
            {"_id": 0, "asset_id": 1, "r2_key": 1, "filename": 1, "file_type": 1},
        )
    )

    if not assets:
        logger.warning(f"No brand_doc assets found for ids: {asset_ids}")
        return ""

    limited = assets[:MAX_DOCS]
    logger.info(f"📚 Analyzing {len(limited)} brand documents...")

    r2 = _get_r2_client()
    bucket = os.getenv("R2_BUCKET_NAME", "wordai-assets")

    doc_summaries = []

    async def process_asset(asset: Dict[str, Any]) -> Optional[str]:
        r2_key = asset.get("r2_key", "")
        filename = asset.get("filename", "document")
        file_type = asset.get("file_type", "")

        try:
            # Download from R2 (sync boto3 wrapped in executor)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: r2.get_object(Bucket=bucket, Key=r2_key),
            )
            file_bytes = response["Body"].read()
        except Exception as e:
            logger.error(f"Failed to download brand doc {r2_key}: {e}")
            return None

        # Extract text
        if file_type in ("pdf",) or filename.lower().endswith(".pdf"):
            raw_text = _extract_text_from_pdf_bytes(file_bytes)
        else:
            try:
                raw_text = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                raw_text = ""

        if not raw_text.strip():
            logger.warning(f"No text extracted from {filename}")
            return None

        summary = await _summarize_document(filename, raw_text, deepseek_client)
        return f"[{filename}] {summary}"

    tasks = [process_asset(a) for a in limited]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, str) and r:
            doc_summaries.append(r)
        elif isinstance(r, Exception):
            logger.error(f"Brand doc processing error: {r}")

    if not doc_summaries:
        return ""

    merged = "\n\n".join(doc_summaries)
    logger.info(f"✅ Brand doc analysis complete: {len(doc_summaries)} docs summarized")
    return merged[:2000]  # Hard cap for final context input
