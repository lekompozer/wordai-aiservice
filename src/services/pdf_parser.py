"""
PDF Parser Service

Parses uploaded PDFs (stored in R2 via social_plan_assets) into structured JSON.
Two modes:
  - "business_info": extracts brand/company information as structured dict
  - "product_list": extracts a list of products with name/description/price/etc.

Reuses PDF extraction + chunking patterns from BrandDocAnalyzer.
"""

import json
import logging
import os
from io import BytesIO
from typing import Any, Dict, List

import boto3

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 3000
MAX_CHUNKS = 8  # ~24k chars ≈ ~40 pages


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages)
    except Exception as e:
        logger.warning(f"pypdf failed: {e}, trying PyPDF2")
        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            return "\n".join(
                (page.extract_text() or "").strip() for page in reader.pages
            )
        except Exception as e2:
            logger.error(f"PDF extraction failed: {e2}")
            return ""


def _chunk_text(text: str) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, current, current_len = [], [], 0
    for para in paragraphs:
        if current_len + len(para) > CHUNK_SIZE_CHARS and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks[:MAX_CHUNKS]


def _download_asset_from_r2(r2_key: str) -> bytes:
    bucket = os.getenv("R2_BUCKET_NAME", "wordai")
    s3 = _get_r2_client()
    obj = s3.get_object(Bucket=bucket, Key=r2_key)
    return obj["Body"].read()


async def parse_business_pdf(pdf_bytes: bytes, llm_client) -> Dict[str, Any]:
    """
    Parse a business/company PDF into structured business_info JSON.

    Returns dict with: brand_name, industry, description, target_audience,
    key_values, products_summary, contacts, founding_year, etc.
    """
    text = _extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        logger.warning("PDF yielded no text")
        return {}

    chunks = _chunk_text(text)
    logger.info(f"[PDFParser:business] {len(chunks)} chunks from PDF")

    # Summarize each chunk to compact context
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            resp = await llm_client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {
                        "role": "system",
                        "content": "Tóm tắt thông tin doanh nghiệp từ đoạn văn bản sau thành bullet points ngắn gọn.",
                    },
                    {"role": "user", "content": chunk[:CHUNK_SIZE_CHARS]},
                ],
                max_tokens=500,
                temperature=0.1,
            )
            chunk_summaries.append(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.warning(f"Chunk {i} summary failed: {e}")

    combined = "\n\n".join(chunk_summaries) if chunk_summaries else text[:6000]

    # Final structured extraction
    extraction_prompt = f"""Dựa trên thông tin dưới đây, trích xuất thông tin doanh nghiệp thành JSON chuẩn.

{combined}

Trả về JSON (chỉ JSON, không text khác):
{{
  "brand_name": "tên thương hiệu / công ty",
  "industry": "ngành nghề",
  "description": "mô tả tổng quan về doanh nghiệp (2-3 câu)",
  "founding_year": "năm thành lập hoặc null",
  "target_audience": "đối tượng khách hàng mục tiêu",
  "key_values": ["giá trị cốt lõi 1", "giá trị cốt lõi 2"],
  "products_summary": "mô tả ngắn về sản phẩm / dịch vụ chính",
  "competitive_advantages": ["lợi thế cạnh tranh 1"],
  "brand_voice": "giọng điệu thương hiệu (nếu có)",
  "contacts": {{
    "website": "url hoặc null",
    "phone": "số điện thoại hoặc null",
    "email": "email hoặc null",
    "address": "địa chỉ hoặc null"
  }}
}}"""

    try:
        resp = await llm_client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia trích xuất thông tin. Luôn trả về JSON hợp lệ.",
                },
                {"role": "user", "content": extraction_prompt},
            ],
            max_tokens=1000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = json.loads(resp.choices[0].message.content)
        logger.info(
            f"[PDFParser:business] Extracted: brand_name={result.get('brand_name')}"
        )
        return result
    except Exception as e:
        logger.error(f"[PDFParser:business] Extraction failed: {e}")
        return {}


async def parse_product_pdf(pdf_bytes: bytes, llm_client) -> Dict[str, Any]:
    """
    Parse a product catalog PDF into a list of products.

    Returns dict with: products (list), total (int).
    Each product: name, description, price, category, highlight, sku.
    """
    text = _extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        logger.warning("[PDFParser:product] PDF yielded no text")
        return {"products": [], "total": 0}

    chunks = _chunk_text(text)
    logger.info(f"[PDFParser:product] {len(chunks)} chunks from PDF")

    all_products: List[Dict] = []

    for i, chunk in enumerate(chunks):
        extraction_prompt = f"""Trích xuất danh sách sản phẩm từ đoạn văn bản catalog dưới đây.
Mỗi sản phẩm trả về JSON object. Nếu không có sản phẩm, trả về mảng rỗng.

=== NỘI DUNG ===
{chunk[:CHUNK_SIZE_CHARS]}

Trả về JSON array (chỉ JSON, không text khác):
[
  {{
    "name": "tên sản phẩm",
    "description": "mô tả ngắn",
    "price": "giá (ví dụ: 299,000đ) hoặc null",
    "category": "danh mục hoặc null",
    "highlight": "điểm nổi bật / USP hoặc null",
    "sku": "mã SKU hoặc null"
  }}
]"""
        try:
            resp = await llm_client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là chuyên gia trích xuất catalog sản phẩm. Luôn trả về JSON array hợp lệ.",
                    },
                    {"role": "user", "content": extraction_prompt},
                ],
                max_tokens=1500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
            # Handle {"products": [...]} or [...]
            chunk_products = (
                raw
                if isinstance(raw, list)
                else raw.get("products", raw.get("items", []))
            )
            # Deduplicate by name
            existing_names = {p["name"].lower() for p in all_products}
            for p in chunk_products:
                if (
                    isinstance(p, dict)
                    and p.get("name")
                    and p["name"].lower() not in existing_names
                ):
                    all_products.append(p)
                    existing_names.add(p["name"].lower())
        except Exception as e:
            logger.warning(f"[PDFParser:product] Chunk {i} failed: {e}")

    logger.info(f"[PDFParser:product] Extracted {len(all_products)} products total")
    return {"products": all_products, "total": len(all_products)}


async def parse_asset_pdf(
    asset_doc: dict,
    parse_type: str,
    llm_client,
) -> Dict[str, Any]:
    """
    High-level helper: given a social_plan_assets document,
    download PDF from R2 and parse it.

    Args:
        asset_doc: MongoDB doc from social_plan_assets (must have r2_key)
        parse_type: "business_info" | "product_list"
        llm_client: OpenAI AsyncOpenAI client

    Returns parsed result dict.
    """
    r2_key = asset_doc.get("r2_key", "")
    if not r2_key:
        raise ValueError(f"Asset {asset_doc.get('asset_id')} has no r2_key")

    logger.info(f"[PDFParser] Downloading {r2_key} for {parse_type}")
    pdf_bytes = _download_asset_from_r2(r2_key)

    if parse_type == "business_info":
        return await parse_business_pdf(pdf_bytes, llm_client)
    elif parse_type == "product_list":
        return await parse_product_pdf(pdf_bytes, llm_client)
    else:
        raise ValueError(f"Unknown parse_type: {parse_type}")
