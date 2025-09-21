"""
Enhanced Callback Handler with Hybrid Search Strategy
Implements individual product/service storage with AI categorization
"""

import json
import uuid
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
import aiohttp  # ✅ FIXED: Use aiohttp like in file_routes.py
import numpy as np
import httpx
import traceback

from src.utils.logger import setup_logger
from src.services.qdrant_company_service import get_qdrant_service
from src.services.embedding_service import get_embedding_service
from src.services.product_catalog_service import get_product_catalog_service

# ✅ FIXED: Use unified collection name for all companies
UNIFIED_COLLECTION_NAME = "multi_company_data"

router = APIRouter(tags=["Webhook Callbacks"])
logger = setup_logger(__name__)

# ===== CALLBACK REQUEST MODELS =====


class CallbackRequest(BaseModel):
    """Simplified callback request - Worker 2 xử lý dữ liệu từ Worker 1 và lưu Qdrant"""

    task_id: str
    status: str
    structured_data: Optional[Dict[str, Any]] = None
    raw_content: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: str


# ===== ENHANCED CALLBACK HANDLER =====


@router.post("/api/webhooks/ai/extraction-callback")
async def enhanced_extraction_callback(
    request: CallbackRequest, background_tasks: BackgroundTasks
):
    """
    Enhanced Callback Handler - Worker 2 xử lý dữ liệu từ Worker 1 và lưu Qdrant
    🎯 RESPONSIBILITY: Lưu từng product/service vào Qdrant và trả về IDs cho backend
    """
    logger.info(f"🔄 Received callback for task {request.task_id}")
    logger.info(f"   📊 Status: {request.status}")

    try:
        if request.status == "completed" and request.structured_data:
            logger.info(
                f"✅ Processing successful extraction for task {request.task_id}"
            )

            # Extract company_id from metadata
            company_id = (
                request.extraction_metadata.get("company_id")
                if request.extraction_metadata
                else None
            )
            if not company_id:
                raise HTTPException(
                    status_code=400,
                    detail="company_id not found in extraction metadata",
                )

            # ✅ ROBUST FILE INFO EXTRACTION: Handle multiple possible locations and field names
            file_id = None
            file_name = None

            if request.extraction_metadata:
                logger.info(f"📁 Extracting file info from extraction_metadata...")

                # 🎯 STRATEGY 1: Try top-level keys first (most direct)
                file_id = request.extraction_metadata.get("file_id")
                file_name = request.extraction_metadata.get(
                    "file_name"
                ) or request.extraction_metadata.get(
                    "filename"
                )  # ✅ FIX: Check both 'file_name' and 'filename'

                logger.info(
                    f"   🔍 Top-level - file_id: {file_id}, file_name: {file_name}"
                )

                # 🎯 STRATEGY 2: If not found, check inside processing_metadata (common fallback)
                if not file_id or not file_name:
                    processing_meta = request.extraction_metadata.get(
                        "processing_metadata", {}
                    )

                    if not file_id:
                        file_id = processing_meta.get("file_id")
                        if file_id:
                            logger.info(
                                f"   ✅ Found file_id in processing_metadata: {file_id}"
                            )

                    if not file_name:
                        file_name = processing_meta.get(
                            "file_name"
                        ) or processing_meta.get("original_filename")
                        if file_name:
                            logger.info(
                                f"   ✅ Found file_name in processing_metadata: {file_name}"
                            )

                # 🎯 STRATEGY 3: Final fallback to original_name if still no file name
                if not file_name:
                    file_name = request.extraction_metadata.get("original_name")
                    if file_name:
                        logger.info(
                            f"   ✅ Found file_name as original_name: {file_name}"
                        )

            logger.info(
                f"📁 FINAL file info after robust extraction - ID: {file_id}, Name: {file_name}"
            )

            # Validate we have at least basic info
            if not file_id:
                logger.warning(
                    "⚠️ No file_id found in any location - this may affect delete operations"
                )
            if not file_name:
                logger.warning("⚠️ No file_name found in any location - using fallback")
                file_name = "unknown_file"

            # Initialize services
            qdrant_manager = get_qdrant_service()
            embedding_service = get_embedding_service()
            catalog_service = (
                await get_product_catalog_service()
            )  # ✅ STEP 2: Get catalog service

            # Process products - lưu từng product vào Qdrant và MongoDB Catalog
            products_stored = []
            if request.structured_data.get("products"):
                logger.info(
                    f"📦 Processing {len(request.structured_data['products'])} products"
                )

                for i, product_data in enumerate(request.structured_data["products"]):
                    try:
                        # Lấy thông tin cơ bản từ raw data (theo template mới)
                        product_name = product_data.get("name", f"Product {i+1}")
                        product_desc = product_data.get("description", "")
                        product_category = product_data.get("category", "unknown")
                        product_tags = product_data.get("tags", [])

                        # ✅ Extract pricing info từ template mới - UNIVERSAL FORMAT SUPPORT
                        # Support BOTH direct fields AND nested "prices" structure
                        prices_obj = product_data.get("prices", {})

                        # Try direct first (new AI format), then nested (old AI format)
                        price_1 = product_data.get("price_1") or prices_obj.get(
                            "price_1", 0
                        )
                        price_2 = product_data.get("price_2") or prices_obj.get(
                            "price_2", 0
                        )
                        price_3 = product_data.get("price_3") or prices_obj.get(
                            "price_3", 0
                        )

                        # Currency handling with fallback chain
                        currency_1 = (
                            product_data.get("currency_1")
                            or product_data.get("currency")
                            or prices_obj.get("currency", "VND")
                        )
                        currency_2 = (
                            product_data.get("currency_2")
                            or product_data.get("currency")
                            or prices_obj.get("currency", "VND")
                        )

                        # Conditions handling with nested support
                        conditions_obj = product_data.get("conditions", {})
                        condition_price_1 = product_data.get(
                            "condition_price_1"
                        ) or conditions_obj.get("condition_price_1", "")
                        condition_price_2 = product_data.get(
                            "condition_price_2"
                        ) or conditions_obj.get("condition_price_2", "")

                        quantity = product_data.get("quantity", 1)

                        logger.info(
                            f"💰 Product pricing - Price 1: {price_1} {currency_1}, Price 2: {price_2} {currency_2}, Qty: {quantity}"
                        )
                        logger.info(
                            f"💰 Product conditions - C1: {condition_price_1}, C2: {condition_price_2}"
                        )

                        # 🔍 DEBUG: Log what we're sending to catalog service
                        logger.info(
                            f"🔍 DEBUG: item_data keys for catalog service: {list(product_data.keys())}"
                        )
                        logger.info(
                            f"🔍 DEBUG: price_1={price_1}, price_2={price_2}, price_3={price_3}"
                        )
                        if "price" in product_data:
                            logger.info(
                                f"🔍 DEBUG: legacy 'price' field = {product_data['price']}"
                            )

                        # ✅ STEP 2: Register product in internal catalog to get product_id
                        logger.info(
                            f"💾 Registering product '{product_name}' in internal catalog..."
                        )
                        logger.info(
                            f"   📋 Input product_data: {json.dumps(product_data, ensure_ascii=False, default=str)}"
                        )

                        enriched_product = await catalog_service.register_item(
                            item_data=product_data,
                            company_id=company_id,
                            item_type="product",
                            file_id=file_id,
                            file_name=file_name,
                        )

                        # 🔍 DETAILED MONGODB LOG: Check what was returned from catalog service
                        logger.info(
                            f"   📤 MongoDB Result - enriched_product: {json.dumps(enriched_product, ensure_ascii=False, default=str)}"
                        )

                        product_id = enriched_product.get(
                            "product_id"
                        )  # Real UUID generated

                        # 🚨 CRITICAL FIX: Đảm bảo product_id luôn tồn tại
                        if not product_id:
                            product_id = f"prod_{uuid.uuid4()}"
                            logger.warning(
                                f"⚠️ Catalog service didn't return product_id, generated: {product_id}"
                            )
                            enriched_product["product_id"] = product_id
                            logger.warning(
                                f"   🔧 Final enriched_product after manual ID: {json.dumps(enriched_product, ensure_ascii=False, default=str)}"
                            )

                        logger.info(f"✅ Product registered with ID: {product_id}")
                        logger.info(
                            f"   💾 MongoDB Storage Status: {'SUCCESS' if product_id.startswith('prod_') else 'UNKNOWN'}"
                        )

                        # ✅ Sử dụng content_for_embedding từ AI (luôn có theo template mới)
                        product_content = product_data.get("content_for_embedding", "")

                        # Fallback nếu AI không trả về content_for_embedding
                        if not product_content:
                            product_content = f"{product_name}\n{product_desc}\nCategory: {product_category}"

                        # Generate embedding
                        embedding = await embedding_service.generate_embedding(
                            product_content
                        )

                        # Tạo unique Qdrant point ID (UUID đầy đủ như trong hệ thống)
                        point_id = str(uuid.uuid4())

                        # ✅ NEW: Lấy thẳng retrieval_context đã được AI tạo sẵn từ template
                        retrieval_context = product_data.get("retrieval_context", "")

                        # Fallback nếu vì lý do nào đó context bị thiếu
                        if not retrieval_context:
                            logger.warning(
                                f"⚠️ retrieval_context not found for product '{product_name}'. Creating fallback context."
                            )
                            # Tạo context đơn giản từ dữ liệu có sẵn
                            retrieval_context = f"Sản phẩm {product_name} thuộc loại {product_category}. Mô tả: {product_desc}. Giá: {price_1} {currency_1}. Số lượng: {quantity}."

                        # Tạo payload với retrieval_context thay vì raw data
                        point_payload = {
                            "content": product_content,
                            "content_type": "extracted_product",
                            "item_type": "product",
                            "company_id": company_id,
                            "task_id": request.task_id,
                            "created_at": datetime.now().isoformat(),
                            # ✅ STEP 2: Add product_id to Qdrant payload
                            "product_id": product_id,
                            # ✅ CRITICAL FIX: Add file_id and file_name to enable delete operations
                            "file_id": file_id or "unknown",
                            "file_name": file_name or "unknown",
                            # ✅ CRITICAL FIX: Add data_type for proper categorization
                            "data_type": "products_services",
                            # ✅ CHANGED: Thay thế raw_product_data bằng retrieval_context sạch sẽ
                            "retrieval_context": retrieval_context,
                        }

                        # Lưu vào Qdrant
                        success = await qdrant_manager.upsert_points(
                            collection_name=UNIFIED_COLLECTION_NAME,
                            points=[
                                {
                                    "id": point_id,
                                    "vector": embedding,
                                    "payload": point_payload,
                                }
                            ],
                        )

                        if success:
                            # 🔍 CALCULATE FINAL CATALOG PRICE FOR LOGGING
                            final_catalog_price = (
                                enriched_product.get("catalog_price")
                                or price_1
                                or price_2
                                or price_3
                                or 0
                            )

                            products_stored.append(
                                {
                                    "name": product_name,
                                    "product_id": product_id,  # ✅ STEP 2: Real product ID for backend
                                    "qdrant_point_id": point_id,  # Backend cần ID này để xóa
                                    "category": product_category,
                                    "original_data": enriched_product,  # ✅ STEP 2: Enriched data with product_id (đã có retrieval_context)
                                    # ✅ PRICING DATA từ AI extraction
                                    "price_1": price_1,
                                    "currency_1": currency_1,
                                    "condition_price_1": condition_price_1,
                                    "price_2": price_2,
                                    "currency_2": currency_2,
                                    "condition_price_2": condition_price_2,
                                    "price_3": price_3,
                                    "original_price": product_data.get(
                                        "original_price"
                                    ),
                                    "quantity": quantity,
                                    # ✅ ENHANCED CATALOG DATA: Use smart fallback for pricing
                                    "catalog_price": final_catalog_price,
                                    "catalog_quantity": (
                                        enriched_product.get("catalog_quantity")
                                        or quantity
                                        or 1
                                    ),
                                }
                            )
                            logger.info(
                                f"✅ Product stored: {product_name} (Product ID: {product_id}, Qdrant ID: {point_id})"
                            )
                            logger.info(
                                f"   💰 Final catalog_price sent to Backend: {final_catalog_price:,.0f} VND"
                            )
                            logger.info(
                                f"   📦 Final catalog_quantity: {(enriched_product.get('catalog_quantity') or quantity or 1)}"
                            )
                        else:
                            logger.error(f"❌ Failed to store product: {product_name}")

                    except Exception as e:
                        logger.error(f"❌ Error processing product {i}: {str(e)}")
                        traceback.print_exc()
                        continue

            # Process services - lưu từng service vào Qdrant và MongoDB Catalog
            services_stored = []
            if request.structured_data.get("services"):
                logger.info(
                    f"🔧 Processing {len(request.structured_data['services'])} services"
                )

                for i, service_data in enumerate(request.structured_data["services"]):
                    try:
                        # Lấy thông tin cơ bản từ raw data (theo template mới)
                        service_name = service_data.get("name", f"Service {i+1}")
                        service_desc = service_data.get("description", "")
                        service_category = service_data.get("category", "unknown")
                        service_tags = service_data.get("tags", [])

                        # ✅ Extract pricing info từ template mới - FIXED FORMAT
                        # Services có structure khác products
                        price_type = service_data.get("price_type", "unknown")
                        price_min = service_data.get("price_min", 0)
                        price_max = service_data.get("price_max", 0)
                        currency = service_data.get("currency", "VND")
                        service_details = service_data.get("service_details", "")
                        service_policies = service_data.get("service_policies", [])
                        quantity = service_data.get("quantity", 1)

                        logger.info(
                            f"💰 Service pricing - Type: {price_type}, Min: {price_min}, Max: {price_max} {currency}, Qty: {quantity}"
                        )
                        logger.info(
                            f"💰 Service details - Details: {service_details}, Policies: {len(service_policies)} items"
                        )

                        # ✅ STEP 2: Register service in internal catalog to get service_id
                        logger.info(
                            f"💾 Registering service '{service_name}' in internal catalog..."
                        )
                        logger.info(
                            f"   📋 Input service_data: {json.dumps(service_data, ensure_ascii=False, default=str)}"
                        )

                        enriched_service = await catalog_service.register_item(
                            item_data=service_data,
                            company_id=company_id,
                            item_type="service",
                            file_id=file_id,
                            file_name=file_name,
                        )

                        # 🔍 DETAILED MONGODB LOG: Check what was returned from catalog service
                        logger.info(
                            f"   📤 MongoDB Result - enriched_service: {json.dumps(enriched_service, ensure_ascii=False, default=str)}"
                        )

                        service_id = enriched_service.get(
                            "service_id"
                        )  # Real UUID generated

                        # 🚨 CRITICAL FIX: Đảm bảo service_id luôn tồn tại
                        if not service_id:
                            service_id = f"serv_{uuid.uuid4()}"
                            logger.warning(
                                f"⚠️ Catalog service didn't return service_id, generated: {service_id}"
                            )
                            enriched_service["service_id"] = service_id
                            logger.warning(
                                f"   🔧 Final enriched_service after manual ID: {json.dumps(enriched_service, ensure_ascii=False, default=str)}"
                            )

                        logger.info(f"✅ Service registered with ID: {service_id}")
                        logger.info(
                            f"   💾 MongoDB Storage Status: {'SUCCESS' if service_id.startswith('serv_') else 'UNKNOWN'}"
                        )

                        # ✅ Sử dụng content_for_embedding từ AI (luôn có theo template mới)
                        service_content = service_data.get("content_for_embedding", "")

                        # Fallback nếu AI không trả về content_for_embedding
                        if not service_content:
                            service_content = f"{service_name}\n{service_desc}\nCategory: {service_category}"

                        # Generate embedding
                        embedding = await embedding_service.generate_embedding(
                            service_content
                        )

                        # Tạo unique Qdrant point ID (UUID đầy đủ như trong hệ thống)
                        point_id = str(uuid.uuid4())

                        # ✅ NEW: Lấy thẳng retrieval_context đã được AI tạo sẵn từ template
                        retrieval_context = service_data.get("retrieval_context", "")

                        # Fallback nếu vì lý do nào đó context bị thiếu
                        if not retrieval_context:
                            logger.warning(
                                f"⚠️ retrieval_context not found for service '{service_name}'. Creating fallback context."
                            )
                            # Tạo context đơn giản từ dữ liệu có sẵn
                            retrieval_context = f"Dịch vụ {service_name} thuộc loại {service_category}. Mô tả: {service_desc}. Loại giá: {price_type}, từ {price_min} đến {price_max} {currency}."

                        # Tạo payload với retrieval_context thay vì raw data
                        point_payload = {
                            "content": service_content,
                            "content_type": "extracted_service",
                            "item_type": "service",
                            "company_id": company_id,
                            "task_id": request.task_id,
                            "created_at": datetime.now().isoformat(),
                            # ✅ STEP 2: Add service_id to Qdrant payload
                            "service_id": service_id,
                            # ✅ CRITICAL FIX: Add file_id and file_name to enable delete operations
                            "file_id": file_id or "unknown",
                            "file_name": file_name or "unknown",
                            # ✅ CRITICAL FIX: Add data_type for proper categorization
                            "data_type": "products_services",
                            # ✅ CHANGED: Thay thế raw_service_data bằng retrieval_context sạch sẽ
                            "retrieval_context": retrieval_context,
                        }

                        # Lưu vào Qdrant
                        success = await qdrant_manager.upsert_points(
                            collection_name=UNIFIED_COLLECTION_NAME,
                            points=[
                                {
                                    "id": point_id,
                                    "vector": embedding,
                                    "payload": point_payload,
                                }
                            ],
                        )

                        if success:
                            services_stored.append(
                                {
                                    "name": service_name,
                                    "service_id": service_id,  # ✅ STEP 2: Real service ID for backend
                                    "qdrant_point_id": point_id,  # Backend cần ID này để xóa
                                    "category": service_category,
                                    "original_data": enriched_service,  # ✅ STEP 2: Enriched data with service_id (đã có retrieval_context)
                                    # ✅ PRICING DATA từ AI extraction (services structure)
                                    "price_type": price_type,
                                    "price_min": price_min,
                                    "price_max": price_max,
                                    "currency": currency,
                                    "service_details": service_details,
                                    "service_policies": service_policies,
                                    "quantity": quantity,
                                    # ✅ ENHANCED CATALOG DATA: Use smart fallback for services
                                    "catalog_price": (
                                        enriched_service.get("catalog_price")
                                        or price_min
                                        or price_max
                                        or 0
                                    ),
                                    "catalog_quantity": (
                                        enriched_service.get("catalog_quantity")
                                        or quantity
                                        or 1
                                    ),
                                }
                            )
                            logger.info(
                                f"✅ Service stored: {service_name} (Service ID: {service_id}, Qdrant ID: {point_id})"
                            )
                        else:
                            logger.error(f"❌ Failed to store service: {service_name}")

                    except Exception as e:
                        logger.error(f"❌ Error processing service {i}: {str(e)}")
                        traceback.print_exc()
                        continue

            # Tạo callback data với Qdrant IDs cho backend
            callback_data = {
                "task_id": request.task_id,
                "status": "completed",
                "company_id": company_id,
                "raw_content": request.raw_content,
                "structured_data": {
                    "products": products_stored,  # Bao gồm qdrant_point_id và original_data
                    "services": services_stored,  # Bao gồm qdrant_point_id và original_data
                },
                "extraction_metadata": {
                    **request.extraction_metadata,
                    "total_products_stored": len(products_stored),
                    "total_services_stored": len(services_stored),
                    "storage_strategy": "individual_qdrant_points",
                    "processed_by": "worker_2_enhanced_callback",
                },
                "processing_time": request.processing_time,
                "timestamp": request.timestamp,
            }

            # Send to Backend với Qdrant IDs
            background_tasks.add_task(send_backend_callback, callback_data)

            logger.info(f"✅ Callback processing completed for task {request.task_id}")
            logger.info(f"   📦 Products stored: {len(products_stored)}")
            logger.info(f"   🔧 Services stored: {len(services_stored)}")

            return {
                "success": True,
                "message": "Callback processed and data stored in Qdrant",
                "products_stored": len(products_stored),
                "services_stored": len(services_stored),
            }

        elif request.status == "failed":
            logger.error(
                f"❌ Extraction failed for task {request.task_id}: {request.error}"
            )

            # Send failure callback to Backend
            callback_data = {
                "task_id": request.task_id,
                "status": "failed",
                "error": request.error,
                "timestamp": request.timestamp,
            }

            background_tasks.add_task(send_backend_callback, callback_data)

            return {
                "success": True,
                "message": "Failure callback forwarded to backend",
            }

        else:
            logger.warning(f"⚠️ Unexpected callback status: {request.status}")
            return {
                "success": True,
                "message": f"Callback with status '{request.status}' acknowledged",
            }

    except Exception as e:
        logger.error(f"❌ Callback processing error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Callback processing failed: {str(e)}"
        )


# ===== BACKGROUND TASK để send callback to Backend =====


async def send_backend_callback(callback_data: Dict[str, Any]) -> bool:
    """Send enhanced callback to Backend with Qdrant IDs and categorization"""
    try:
        # Get Backend callback URL from environment or extraction metadata
        backend_callback_url = callback_data.get("extraction_metadata", {}).get(
            "callback_url"
        )

        # Use fixed backend callback URL if not provided in metadata
        if not backend_callback_url:
            backend_callback_url = f"{os.getenv('BACKEND_WEBHOOK_URL', 'https://api.agent8x.io.vn')}/api/webhooks/ai/extraction-callback"
            logger.info("🔗 Using default backend callback URL from config")

        # ✅ SIMPLIFIED: Sử dụng webhook secret trực tiếp, không mã hóa
        webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook-secret-for-signature")

        logger.info(f"📤 Sending enhanced callback to Backend: {backend_callback_url}")
        logger.info(
            f"   📊 Products: {len(callback_data.get('structured_data', {}).get('products', []))}"
        )
        logger.info(
            f"   🔧 Services: {len(callback_data.get('structured_data', {}).get('services', []))}"
        )

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30.0)
        ) as session:
            async with session.post(
                backend_callback_url,
                json=callback_data,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Source": "ai-service",
                    "X-Webhook-Secret": webhook_secret,  # ✅ Sử dụng secret trực tiếp
                    "User-Agent": "Agent8x-AI-Service/1.0",
                },
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Enhanced callback sent successfully to Backend")
                    return True
                else:
                    response_text = await response.text()
                    logger.error(
                        f"❌ Backend callback failed: {response.status} - {response_text}"
                    )
                    return False

    except Exception as e:
        logger.error(f"❌ Failed to send enhanced callback to Backend: {str(e)}")
        return False


# ===== STORAGE AND CALLBACK FUNCTION =====


async def store_structured_data_and_callback(
    task_id: str,
    structured_data: Dict[str, Any],
    company_id: str,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    🎯 STORAGE ONLY function - receives structured_data and handles storage + callback.
    This function DOES NOT call AI - it only processes already extracted data.

    **RESPONSIBILITY:**
    - Receive structured_data (already extracted by AI)
    - Generate embeddings for each item
    - Store in Qdrant as individual points with full UUIDs
    - Send final callback to backend with qdrant_point_id for each item

    Args:
        task_id: Task identifier
        structured_data: Already extracted data from AI (products/services)
        company_id: Company identifier
        callback_url: Optional callback URL
        metadata: Task metadata

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"💾 [STORAGE] Processing structured data for task {task_id}")
        logger.info(f"   🏢 Company: {company_id}")

        # ✅ CRITICAL FIX: Extract file_id and file_name from metadata for proper delete operations
        file_id = None
        file_name = None

        if metadata:
            logger.info(f"📁 [STORAGE] Extracting file info from metadata...")

            # Strategy 1: Direct keys
            file_id = metadata.get("file_id")
            file_name = metadata.get("file_name") or metadata.get("filename")

            # Strategy 2: Check processing_metadata
            if not file_id or not file_name:
                processing_meta = metadata.get("processing_metadata", {})
                if not file_id:
                    file_id = processing_meta.get("file_id")
                if not file_name:
                    file_name = processing_meta.get("file_name") or processing_meta.get(
                        "original_filename"
                    )

            # Strategy 3: Fallback to original_name
            if not file_name:
                file_name = metadata.get("original_name")

        logger.info(f"📁 [STORAGE] File info - ID: {file_id}, Name: {file_name}")

        # Set defaults if missing
        if not file_id:
            file_id = "unknown"
            logger.warning("⚠️ [STORAGE] No file_id found - using 'unknown'")
        if not file_name:
            file_name = "unknown"
            logger.warning("⚠️ [STORAGE] No file_name found - using 'unknown'")

        # ✅ Handle both normalized and direct structure formats
        if "structured_data" in structured_data and isinstance(
            structured_data["structured_data"], dict
        ):
            # Worker 1 normalized format: {structured_data: {products: [...], services: [...]}}
            inner_data = structured_data["structured_data"]
            products = inner_data.get("products", [])
            services = inner_data.get("services", [])
            logger.info(f"   📋 Data format: Worker 1 normalized structure")
        else:
            # Direct format: {products: [...], services: [...]}
            products = structured_data.get("products", [])
            services = structured_data.get("services", [])
            logger.info(f"   📋 Data format: Direct structure")

        logger.info(f"   📊 Products to store: {len(products)}")
        logger.info(f"   🔧 Services to store: {len(services)}")

        if not products and not services:
            logger.warning(f"⚠️ [STORAGE] No products or services to store")
            return True

        # Initialize services for storage only
        qdrant_manager = get_qdrant_service()
        embedding_service = get_embedding_service()
        catalog_service = await get_product_catalog_service()  # ✅ Add catalog service

        products_stored = []
        services_stored = []

        # Store products individually (raw data processing - no model validation)
        for i, product_data in enumerate(products):
            try:
                # Lấy thông tin cơ bản từ raw data (không validate model)
                product_name = product_data.get("name", f"Product {i+1}")
                product_desc = product_data.get("description", "")
                product_category = product_data.get("category", "unknown")
                product_tags = product_data.get("tags", [])

                # 🚨 CRITICAL FIX: Tạo product_id nếu chưa có
                product_id = product_data.get("product_id")
                logger.info(
                    f"🔍 [STORAGE] Product '{product_name}' - Existing product_id: {product_id}"
                )

                if not product_id:
                    product_id = f"prod_{uuid.uuid4()}"
                    product_data["product_id"] = product_id
                    logger.info(
                        f"🔧 Generated product_id for '{product_name}': {product_id}"
                    )
                else:
                    logger.info(
                        f"✅ Using existing product_id for '{product_name}': {product_id}"
                    )

                # ✅ Enrich product data with catalog service to get catalog_price
                enriched_product = await catalog_service.register_item(
                    item_data=product_data,
                    company_id=company_id,
                    item_type="product",
                    # ✅ FIX: Truyền file_id và file_name vào đây
                    file_id=file_id,
                    file_name=file_name,
                )

                # � CRITICAL FIX: Lấy product_id MỚI NHẤT từ catalog service
                product_id = enriched_product.get("product_id")

                # Fallback để đảm bảo ID luôn tồn tại
                if not product_id:
                    product_id = f"prod_{uuid.uuid4()}"
                    logger.warning(
                        f"⚠️ [STORAGE] Catalog service didn't return product_id, generated: {product_id}"
                    )
                    enriched_product["product_id"] = product_id

                logger.info(f"✅ [STORAGE] Product registered with CONSISTENT ID: {product_id}")

                # �🔍 LOG FINAL PRODUCT DATA BEFORE QDRANT
                logger.info(
                    f"   📋 Final enriched_product with ID: {json.dumps(enriched_product, ensure_ascii=False, default=str)}"
                )

                # ✅ Sử dụng content_for_embedding từ AI (luôn có theo template mới)
                product_content = product_data.get("content_for_embedding", "")

                # Fallback nếu AI không trả về content_for_embedding
                if not product_content:
                    product_content = (
                        f"{product_name}\n{product_desc}\nCategory: {product_category}"
                    )

                # Generate embedding
                embedding = await embedding_service.generate_embedding(product_content)

                # Tạo unique Qdrant point ID (UUID đầy đủ như trong hệ thống)
                point_id = str(uuid.uuid4())

                # ✅ NEW: Lấy thẳng retrieval_context đã được AI tạo sẵn từ template
                retrieval_context = product_data.get("retrieval_context", "")

                # Fallback nếu vì lý do nào đó context bị thiếu
                if not retrieval_context:
                    logger.warning(
                        f"⚠️ [STORAGE] retrieval_context not found for product '{product_name}'. Creating fallback context."
                    )
                    retrieval_context = f"Sản phẩm {product_name} thuộc loại {product_category}. Mô tả: {product_desc}. Số lượng: {product_data.get('quantity', 1)}."

                # Tạo payload với retrieval_context thay vì raw data
                point_payload = {
                    "content": product_content,
                    "content_type": "extracted_product",
                    "item_type": "product",
                    "company_id": company_id,
                    "task_id": task_id,
                    "created_at": datetime.now().isoformat(),
                    "product_id": product_id,  # ✅ Add product_id to Qdrant
                    # ✅ CRITICAL FIX: Add file_id and file_name for delete operations
                    "file_id": file_id,
                    "file_name": file_name,
                    # ✅ CRITICAL FIX: Add data_type for proper categorization
                    "data_type": "products_services",
                    # ✅ CHANGED: Thay thế raw_product_data bằng retrieval_context sạch sẽ
                    "retrieval_context": retrieval_context,
                }

                # Lưu vào Qdrant
                success = await qdrant_manager.upsert_points(
                    collection_name=UNIFIED_COLLECTION_NAME,
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": point_payload,
                        }
                    ],
                )

                if success:
                    products_stored.append(
                        {
                            "name": product_name,
                            "product_id": product_id,  # ✅ CRITICAL: Add product_id for backend
                            "qdrant_point_id": point_id,  # Backend cần ID này để xóa
                            "category": product_category,
                            "original_data": product_data,  # Raw data từ AI với product_id (đã có retrieval_context)
                            # Legacy fields for backward compatibility - from catalog service
                            "catalog_price": enriched_product.get(
                                "catalog_price", product_data.get("price_1", 0)
                            ),
                            "catalog_quantity": enriched_product.get(
                                "catalog_quantity", product_data.get("quantity", 1)
                            ),
                        }
                    )
                    logger.info(
                        f"✅ [STORAGE] Product stored: {product_name} (Product ID: {product_id}, Qdrant ID: {point_id})"
                    )
                else:
                    logger.error(
                        f"❌ [STORAGE] Failed to store product: {product_name}"
                    )

            except Exception as e:
                logger.error(f"❌ [STORAGE] Error processing product {i}: {str(e)}")
                continue

        # Store services individually (raw data processing - no model validation)
        for i, service_data in enumerate(services):
            try:
                # Lấy thông tin cơ bản từ raw data (không validate model)
                service_name = service_data.get("name", f"Service {i+1}")
                service_desc = service_data.get("description", "")
                service_category = service_data.get("category", "unknown")
                service_tags = service_data.get("tags", [])

                # ✅ CONSISTENCY FIX: Không tự tạo service_id, để catalog service quyết định
                # Chỉ log existing service_id từ AI nếu có
                ai_service_id = service_data.get("service_id")
                logger.info(
                    f"� [STORAGE] Service '{service_name}' - AI provided service_id: {ai_service_id}"
                )

                # ✅ Enrich service data with catalog service to get catalog_price
                enriched_service = await catalog_service.register_item(
                    item_data=service_data,
                    company_id=company_id,
                    item_type="service",
                    # ✅ FIX: Truyền file_id và file_name vào đây
                    file_id=file_id,
                    file_name=file_name,
                )

                # � CRITICAL FIX: Lấy service_id MỚI NHẤT từ catalog service
                service_id = enriched_service.get("service_id")

                # Fallback để đảm bảo ID luôn tồn tại
                if not service_id:
                    service_id = f"serv_{uuid.uuid4()}"
                    logger.warning(
                        f"⚠️ [STORAGE] Catalog service didn't return service_id, generated: {service_id}"
                    )
                    enriched_service["service_id"] = service_id

                logger.info(f"✅ [STORAGE] Service registered with CONSISTENT ID: {service_id}")

                # �🔍 LOG FINAL SERVICE DATA BEFORE QDRANT
                logger.info(
                    f"   📋 Final enriched_service with ID: {json.dumps(enriched_service, ensure_ascii=False, default=str)}"
                )

                # ✅ Sử dụng content_for_embedding từ AI (luôn có theo template mới)
                service_content = service_data.get("content_for_embedding", "")

                # Fallback nếu AI không trả về content_for_embedding
                if not service_content:
                    service_content = (
                        f"{service_name}\n{service_desc}\nCategory: {service_category}"
                    )

                # Generate embedding
                embedding = await embedding_service.generate_embedding(service_content)

                # Tạo unique Qdrant point ID (UUID đầy đủ như trong hệ thống)
                point_id = str(uuid.uuid4())

                # ✅ NEW: Lấy thẳng retrieval_context đã được AI tạo sẵn từ template
                retrieval_context = service_data.get("retrieval_context", "")

                # Fallback nếu vì lý do nào đó context bị thiếu
                if not retrieval_context:
                    logger.warning(
                        f"⚠️ [STORAGE] retrieval_context not found for service '{service_name}'. Creating fallback context."
                    )
                    retrieval_context = f"Dịch vụ {service_name} thuộc loại {service_category}. Mô tả: {service_desc}."

                # Tạo payload với retrieval_context thay vì raw data
                point_payload = {
                    "content": service_content,
                    "content_type": "extracted_service",
                    "item_type": "service",
                    "company_id": company_id,
                    "task_id": task_id,
                    "created_at": datetime.now().isoformat(),
                    "service_id": service_id,  # ✅ Add service_id to Qdrant
                    # ✅ CRITICAL FIX: Add file_id and file_name for delete operations
                    "file_id": file_id,
                    "file_name": file_name,
                    # ✅ CRITICAL FIX: Add data_type for proper categorization
                    "data_type": "products_services",
                    # ✅ CHANGED: Thay thế raw_service_data bằng retrieval_context sạch sẽ
                    "retrieval_context": retrieval_context,
                }

                # Lưu vào Qdrant
                success = await qdrant_manager.upsert_points(
                    collection_name=UNIFIED_COLLECTION_NAME,
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": point_payload,
                        }
                    ],
                )

                if success:
                    # Extract pricing data from service_data
                    price_type = service_data.get("price_type", "unknown")
                    price_min = service_data.get("price_min", 0)
                    price_max = service_data.get("price_max", 0)
                    currency = service_data.get("currency", "VND")
                    service_details = service_data.get("service_details", "")
                    service_policies = service_data.get("service_policies", "")
                    quantity = service_data.get("quantity", 1)

                    services_stored.append(
                        {
                            "name": service_name,
                            "service_id": service_id,  # ✅ CRITICAL: Add service_id for backend
                            "qdrant_point_id": point_id,  # Backend cần ID này để xóa
                            "category": service_category,
                            "original_data": service_data,  # Raw data từ AI với service_id (đã có retrieval_context)
                            # ✅ PRICING DATA từ AI extraction (services structure)
                            "price_type": price_type,
                            "price_min": price_min,
                            "price_max": price_max,
                            "currency": currency,
                            "service_details": service_details,
                            "service_policies": service_policies,
                            "quantity": quantity,
                            # Legacy fields for backward compatibility - from catalog service
                            "catalog_price": enriched_service.get(
                                "catalog_price", service_data.get("price_min", 0)
                            ),
                            "catalog_quantity": enriched_service.get(
                                "catalog_quantity", service_data.get("quantity", 1)
                            ),
                        }
                    )
                    logger.info(
                        f"✅ [STORAGE] Service stored: {service_name} (Service ID: {service_id}, Qdrant ID: {point_id})"
                    )
                else:
                    logger.error(
                        f"❌ [STORAGE] Failed to store service: {service_name}"
                    )

            except Exception as e:
                logger.error(f"❌ [STORAGE] Error processing service {i}: {str(e)}")
                continue

        # === STEP 5: Build Enhanced Callback Payload ===
        callback_payload = {
            "task_id": task_id,
            "status": "completed",
            "company_id": company_id,
            "timestamp": datetime.now().isoformat(),
            "raw_content": structured_data.get("raw_content", ""),
            "structured_data": {
                "products": products_stored,
                "services": services_stored,
            },
            "extraction_metadata": {
                **metadata,
                "callback_url": callback_url,
                "total_products_stored": len(products_stored),
                "total_services_stored": len(services_stored),
                "storage_strategy": "individual_qdrant_points",
                "processed_by": "worker_2_storage_callback",
            },
        }

        # === STEP 6: Send Enhanced Callback to Backend ===
        if callback_url:
            logger.info(f"📤 Sending enhanced callback to Backend: {callback_url}")
            logger.info(f"   📊 Products: {len(products_stored)}")
            logger.info(f"   🔧 Services: {len(services_stored)}")

            # ✅ GHI LOG CHI TIẾT: Ghi lại toàn bộ payload trước khi gửi
            try:
                payload_json_for_log = json.dumps(
                    callback_payload, indent=2, ensure_ascii=False, default=str
                )
                logger.info(f"📋 Callback Payload to be sent:\n{payload_json_for_log}")
            except Exception as log_e:
                logger.warning(f"⚠️ Could not serialize payload for logging: {log_e}")

            success = await send_webhook_callback(
                url=callback_url, payload=callback_payload
            )
            if not success:
                logger.error(f"❌ Backend callback failed for task {task_id}")
                return False  # Propagate failure
        else:
            logger.info("✅ No callback URL provided, skipping callback.")

        # === Final Summary ===
        logger.info(f"🎉 [STORAGE] Storage completed successfully for task {task_id}")
        logger.info(f"   📊 Products stored: {len(products_stored)}")
        logger.info(f"   🔧 Services stored: {len(services_stored)}")

        return True

    except Exception as e:
        logger.error(f"❌ [STORAGE] Failed to store data for task {task_id}: {e}")
        logger.error(traceback.format_exc())
        # Optionally send an error callback
        if callback_url:
            await send_webhook_callback(
                url=callback_url,
                payload={
                    "task_id": task_id,
                    "status": "failed",
                    "company_id": company_id,
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Storage and callback process failed: {str(e)}",
                    "extraction_metadata": {
                        "callback_url": callback_url,
                        "processed_by": "worker_2_storage_callback",
                    },
                },
            )
        return False


async def send_webhook_callback(url: str, payload: dict) -> bool:
    """
    Sends a webhook callback to the specified URL with simple secret and retry logic.
    Gửi webhook callback đến URL được chỉ định với secret đơn giản và retry logic.
    """
    max_retries = 3
    base_timeout = 15.0  # Reduced from 30s to 15s

    for attempt in range(max_retries):
        try:
            # ✅ SIMPLIFIED: Chỉ sử dụng WEBHOOK_SECRET trực tiếp trong header, không mã hóa
            webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook-secret-for-signature")

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Source": "ai-service",
                "X-Webhook-Secret": webhook_secret,  # ✅ Sử dụng secret trực tiếp
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            # Increase timeout for each retry
            timeout = base_timeout + (attempt * 10)

            logger.info(
                f"🔄 Attempt {attempt + 1}/{max_retries} - Sending callback to {url} (timeout: {timeout}s)"
            )

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url, json=payload, headers=headers
                )  # ✅ Sử dụng json= thay vì content=

                if 200 <= response.status_code < 300:
                    logger.info(
                        f"✅ Callback sent successfully to {url} (Status: {response.status_code}) on attempt {attempt + 1}"
                    )
                    return True
                else:
                    # ✅ GHI LOG CHI TIẾT: Ghi lại nội dung lỗi từ backend
                    error_content = response.text
                    logger.error(
                        f"❌ Backend callback to {url} failed with status {response.status_code} on attempt {attempt + 1}"
                    )
                    logger.error(
                        f"   📄 Response Body: {error_content[:1000]}"
                    )  # Log first 1000 chars

                    # Don't retry on 4xx errors (client errors)
                    if 400 <= response.status_code < 500:
                        logger.error(
                            f"❌ Client error ({response.status_code}), not retrying"
                        )
                        return False

        except httpx.ReadTimeout as e:
            logger.error(
                f"⏰ Attempt {attempt + 1}/{max_retries} - ReadTimeout to {url} after {timeout}s: {e}"
            )
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"❌ All {max_retries} attempts failed due to timeout")
                return False
            else:
                wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                logger.info(f"🔄 Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        except httpx.RequestError as e:
            logger.error(
                f"❌ HTTP request to {url} failed on attempt {attempt + 1}: {e.__class__.__name__} - {e}"
            )
            if attempt == max_retries - 1:  # Last attempt
                return False
            else:
                wait_time = 2**attempt
                logger.info(f"🔄 Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(
                f"❌ Failed to send callback to {url} on attempt {attempt + 1}: {e}"
            )
            logger.error(traceback.format_exc())
            if attempt == max_retries - 1:  # Last attempt
                return False
            else:
                wait_time = 2**attempt
                logger.info(f"🔄 Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

    return False
