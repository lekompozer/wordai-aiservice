"""
Extraction Processing Worker - Worker 1 in 2-Worker Architecture
Handles ONLY AI extraction using ai_extraction_service.py

Flow: Redis Queue -> ExtractionProcessingWorker -> ai_extraction_service.py -> StorageProcessingTask -> Redis Queue
"""

import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import Optional

from src.utils.logger import setup_logger
from src.queue.queue_dependencies import (
    get_extraction_queue,
    get_storage_queue,
)  # Use extraction queue for receiving, storage queue for sending
from src.queue.task_models import ExtractionProcessingTask, StorageProcessingTask
from src.services.ai_extraction_service import get_ai_service

logger = setup_logger(__name__)


class ExtractionProcessingWorker:
    """
    Worker 1: Extraction Processing Worker - ONLY handles AI extraction.
    Uses ai_extraction_service.py for actual AI processing.

    Responsibilities:
    - Poll Redis queue for ExtractionProcessingTask
    - Call ai_extraction_service.extract_from_r2_url()
    - Create StorageProcessingTask with structured_data
    - Push StorageProcessingTask to Redis queue for Worker 2
    """

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        poll_interval: float = 1.0,
        max_retries: int = 3,
    ):
        self.worker_id = (
            worker_id or f"extraction_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.running = False
        self.queue_manager = None
        self.ai_service = None

        logger.info(f"🔧 Extraction Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   ⏱️ Poll interval: {self.poll_interval}s")
        logger.info(f"   🔄 Max retries: {self.max_retries}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            # Get extraction queue manager (not document queue!)
            self.queue_manager = await get_extraction_queue()
            logger.info(
                f"✅ Extraction Worker {self.worker_id}: Connected to extraction queue (products_extraction)"
            )

            # Initialize AI service
            self.ai_service = get_ai_service()
            logger.info(f"✅ Extraction Worker {self.worker_id}: AI service ready")

        except Exception as e:
            logger.error(
                f"❌ Extraction Worker {self.worker_id}: Initialization failed: {e}"
            )
            raise

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Extraction Worker {self.worker_id}: Shutting down...")
        self.running = False
        logger.info(f"✅ Extraction Worker {self.worker_id}: Shutdown complete")

    async def run(self):
        """Main worker loop - continuously poll for ExtractionProcessingTask from Redis queue"""
        logger.info(f"🚀 Starting extraction processing worker {self.worker_id}")
        self.running = True

        while self.running:
            try:
                # Dequeue extraction tasks from Redis
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=2  # 2 second timeout for polling
                )

                if task_data:
                    logger.info(
                        f"🎯 [EXTRACTION WORKER] Processing extraction task: {task_data.get('task_id')}"
                    )

                    try:
                        # Check if this is an ExtractionProcessingTask (has processing_metadata)
                        if "processing_metadata" in task_data:
                            # Parse as ExtractionProcessingTask
                            task = ExtractionProcessingTask(**task_data)
                            await self.process_extraction_task(task)
                        else:
                            # This is not our task type, put it back in queue
                            logger.info(
                                f"🔄 [EXTRACTION WORKER] Task {task_data.get('task_id')} is not ExtractionProcessingTask, skipping"
                            )
                            # Note: In real implementation, you might want to put it back in queue
                            # For now, we'll just skip it

                    except Exception as task_error:
                        logger.error(
                            f"❌ [EXTRACTION WORKER] Task processing error: {task_error}"
                        )
                        logger.error(f"🔍 [EXTRACTION WORKER] Task data: {task_data}")

                else:
                    # No tasks, wait briefly before next poll
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ [EXTRACTION WORKER] Worker loop error: {e}")
                logger.error(
                    f"🔍 [EXTRACTION WORKER] Traceback: {traceback.format_exc()}"
                )
                await asyncio.sleep(self.poll_interval)

        logger.info(f"🛑 Extraction processing worker {self.worker_id} stopped")

    async def process_extraction_task(self, task: ExtractionProcessingTask) -> bool:
        """
        Process a single ExtractionProcessingTask.

        Worker 1 responsibilities:
        1. Receive ExtractionProcessingTask from Redis queue
        2. Call ai_extraction_service.extract_from_r2_url() for AI processing
        3. Create StorageProcessingTask with structured_data results
        4. Push StorageProcessingTask to Redis queue for Worker 2

        Args:
            task: ExtractionProcessingTask instance

        Returns:
            bool: True if successful, False otherwise
        """
        start_time = time.time()

        # Check for Hybrid Strategy flags
        processing_metadata = getattr(task, "processing_metadata", {}) or {}
        hybrid_strategy_enabled = processing_metadata.get(
            "hybrid_strategy_enabled", False
        )
        individual_storage_mode = processing_metadata.get(
            "individual_storage_mode", False
        )

        try:
            logger.info(
                f"🎯 [EXTRACTION WORKER] Processing extraction task {task.task_id}"
            )
            logger.info(f"   🏢 Company: {task.company_id}")
            logger.info(f"   🏭 Industry: {task.industry}")
            logger.info(f"   🌐 Language: {task.language}")
            logger.info(f"   📋 Data Type: {task.data_type}")
            logger.info(f"   📊 Categories: {task.target_categories}")
            logger.info(f"   🎯 Hybrid Strategy: {hybrid_strategy_enabled}")
            logger.info(f"   📊 Individual Storage: {individual_storage_mode}")

            # Prepare metadata for AI service
            metadata = {
                "original_name": task.file_name,
                "file_size": task.file_size,
                "file_type": task.file_type,
                "industry": task.industry,
                "language": task.language,
                "extraction_timestamp": datetime.now().isoformat(),
                "task_id": task.task_id,
                "company_id": task.company_id,
                "data_type": task.data_type,
                "processing_metadata": processing_metadata,
                # ✅ ADD FILE INFORMATION from processing_metadata
                "file_id": processing_metadata.get("file_id"),
                "filename": task.file_name,  # Also add as filename for compatibility
            }

            logger.info(
                f"🤖 [EXTRACTION WORKER] Calling ai_extraction_service.extract_from_r2_url()..."
            )

            # Call AI extraction service - this is our ONLY job!
            result = await self.ai_service.extract_from_r2_url(
                r2_url=task.r2_url,
                metadata=metadata,
                company_info=task.company_info,
                target_categories=task.target_categories,
            )

            extraction_time = time.time() - start_time
            logger.info(
                f"✅ [EXTRACTION WORKER] AI extraction completed in {extraction_time:.2f}s"
            )

            # ✅ NORMALIZE EXTRACTION RESULT: Ensure consistent structure
            normalized_result = self._normalize_extraction_result(result)

            # Extract normalized data for analysis
            extraction_metadata = normalized_result.get("extraction_metadata", {})
            structured_data = normalized_result.get("structured_data", {})
            extraction_summary = normalized_result.get("extraction_summary", {})

            # Get counts from normalized data
            products_count = extraction_summary.get("total_products", 0)
            services_count = extraction_summary.get("total_services", 0)
            total_items = extraction_summary.get("total_items", 0)
            logger.info(
                f"🔧 [EXTRACTION WORKER] Normalizing extraction result structure..."
            )
            normalized_result = self._normalize_extraction_result(result)

            # Extract normalized results
            structured_data = normalized_result.get("structured_data", {})
            products_count = len(structured_data.get("products", []))
            services_count = len(structured_data.get("services", []))

            # ✅ SAVE EXTRACTION RESULT TO FILE FOR DEBUG
            import json
            import os

            debug_dir = "debug_extraction_results"
            os.makedirs(debug_dir, exist_ok=True)

            # Save full extraction result from Worker 1 - OPTIMIZED: Only save normalized result
            debug_data = {
                "task_id": task.task_id,
                "timestamp": datetime.now().isoformat(),
                "company_id": task.company_id,
                "industry": str(task.industry),
                "processing_time": extraction_time,
                "worker": "ExtractionProcessingWorker",
                # ✅ REMOVED: raw_extraction_result (duplicate data)
                "extraction_result": normalized_result,  # Final processed result
                "products_count": products_count,
                "services_count": services_count,
                "total_items": total_items,
                "raw_content_length": len(normalized_result.get("raw_content", "")),
                "metadata": metadata,
                "ai_provider": extraction_metadata.get("ai_provider", "unknown"),
                "template_used": extraction_metadata.get("template_used", "unknown"),
            }

            debug_filename = f"extraction_debug_{task.task_id}_{int(time.time())}.json"
            debug_filepath = os.path.join(debug_dir, debug_filename)

            try:
                with open(debug_filepath, "w", encoding="utf-8") as f:
                    json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)

                logger.info(
                    f"💾 [EXTRACTION WORKER] Debug file saved: {debug_filepath}"
                )
                logger.info(
                    f"   📊 Products: {products_count}, Services: {services_count}"
                )
                logger.info(
                    f"   🤖 AI Provider: {extraction_metadata.get('ai_provider', 'unknown')}"
                )
            except Exception as debug_error:
                logger.error(
                    f"❌ [EXTRACTION WORKER] Failed to save debug file: {debug_error}"
                )

            logger.info(f"📊 [EXTRACTION WORKER] Extraction Results:")
            logger.info(f"   📦 Products: {products_count}")
            logger.info(f"   🔧 Services: {services_count}")
            logger.info(
                f"   🤖 AI Provider: {extraction_metadata.get('ai_provider', 'unknown')}"
            )

            # For Hybrid Strategy with individual storage, create StorageProcessingTask
            if hybrid_strategy_enabled and individual_storage_mode:
                logger.info(
                    f"🎯 [EXTRACTION WORKER] Creating StorageProcessingTask for Worker 2..."
                )

                # Create StorageProcessingTask with normalized extraction results
                storage_task = StorageProcessingTask(
                    task_id=f"storage_{task.task_id}",  # New task ID for storage
                    company_id=task.company_id,
                    structured_data=normalized_result,  # Use normalized structure
                    metadata=metadata,  # Pass complete metadata
                    callback_url=task.callback_url,
                    original_extraction_task_id=task.task_id,  # Reference to original task
                    created_at=datetime.utcnow(),
                )

                # Push StorageProcessingTask to Storage Redis queue for Worker 2
                logger.info(
                    f"📤 [EXTRACTION WORKER] Pushing StorageProcessingTask to Storage queue..."
                )

                # Get storage queue manager for sending storage tasks
                storage_queue = await get_storage_queue()
                success = await storage_queue.enqueue_generic_task(storage_task)

                if success:
                    logger.info(
                        f"✅ [EXTRACTION WORKER] StorageProcessingTask queued successfully to storage queue"
                    )
                    logger.info(f"   📋 Storage Task ID: {storage_task.task_id}")
                    logger.info(
                        f"   💾 Worker 2 will handle: Qdrant storage + backend callback (from storage queue)"
                    )
                else:
                    logger.error(
                        f"❌ [EXTRACTION WORKER] Failed to queue StorageProcessingTask"
                    )
                    return False

            else:
                # For standard mode, send immediate callback (backward compatibility)
                logger.info(
                    f"📋 [EXTRACTION WORKER] Standard mode - sending immediate callback..."
                )

                if task.callback_url:
                    await self._send_extraction_callback(
                        task, normalized_result, extraction_time
                    )
                    logger.info(f"✅ [EXTRACTION WORKER] Standard callback sent")

            total_time = time.time() - start_time
            logger.info(
                f"🎉 [EXTRACTION WORKER] Task {task.task_id} completed successfully in {total_time:.2f}s"
            )

            return True

        except Exception as e:
            error_time = time.time() - start_time
            logger.error(
                f"❌ [EXTRACTION WORKER] Task {task.task_id} failed after {error_time:.2f}s: {str(e)}"
            )
            logger.error(
                f"🔍 [EXTRACTION WORKER] Error details: {traceback.format_exc()}"
            )

            # Send error callback
            if task.callback_url:
                await self._send_extraction_error_callback(task, str(e))

            return False

    async def _send_extraction_callback(
        self, task: ExtractionProcessingTask, result: dict, processing_time: float
    ):
        """Send success callback for standard mode (non-hybrid strategy)"""
        import json
        import aiohttp

        raw_content = result.get("raw_content", "")
        structured_data = result.get("structured_data", {})
        extraction_metadata = result.get("extraction_metadata", {})

        # Get counts from structured_data
        products = structured_data.get("products", [])
        services = structured_data.get("services", [])

        # Remove 'id' field from products and services before sending to backend
        # Database will handle auto-increment IDs
        cleaned_products = []
        for product in products:
            cleaned_product = {k: v for k, v in product.items() if k != "id"}
            cleaned_products.append(cleaned_product)

        cleaned_services = []
        for service in services:
            cleaned_service = {k: v for k, v in service.items() if k != "id"}
            cleaned_services.append(cleaned_service)

        # Create cleaned structured_data for callback
        cleaned_structured_data = {
            "products": cleaned_products,
            "services": cleaned_services,
        }

        callback_data = {
            "task_id": task.task_id,
            "company_id": task.company_id,
            "status": "completed",
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat(),
            "results": {
                "products_count": len(products),
                "services_count": len(services),
                "total_items": len(products) + len(services),
                "ai_provider": extraction_metadata.get("ai_provider"),
                "template_used": extraction_metadata.get("template_used"),
            },
            "raw_content": raw_content,
            "structured_data": cleaned_structured_data,  # Use cleaned data without 'id' fields
            "extraction_metadata": {
                "r2_url": task.r2_url,
                "extraction_mode": "auto_categorization",
                "target_categories": task.target_categories,
                "ai_provider": extraction_metadata.get("ai_provider"),
                "template_used": extraction_metadata.get("template_used"),
                "industry": (
                    task.industry.value
                    if hasattr(task.industry, "value")
                    else str(task.industry)
                ),
                "data_type": task.data_type,
                "file_name": task.file_name,
                "language": (
                    task.language.value
                    if hasattr(task.language, "value")
                    else str(task.language)
                ),
                "extraction_timestamp": datetime.now().isoformat(),
                "source": "extraction_worker_v1",
            },
        }

        logger.info(
            f"📞 [EXTRACTION WORKER] Sending callback to {task.callback_url}..."
        )

        try:
            # Generate webhook signature
            webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook-secret-for-signature")

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Source": "ai-service",
                "X-Webhook-Secret": webhook_secret,  # ✅ Simplified: Use plain text secret
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    task.callback_url,
                    json=callback_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=headers,
                ) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        logger.info(
                            f"✅ [EXTRACTION WORKER] Callback sent successfully for task {task.task_id}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ [EXTRACTION WORKER] Callback returned status {response.status}"
                        )

        except Exception as e:
            logger.error(f"❌ [EXTRACTION WORKER] Failed to send callback: {str(e)}")

    async def _send_extraction_error_callback(
        self, task: ExtractionProcessingTask, error_message: str
    ):
        """Send error callback for extraction task"""
        import json
        import aiohttp

        callback_data = {
            "task_id": task.task_id,
            "company_id": task.company_id,
            "status": "failed",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"📞 [EXTRACTION WORKER] Sending error callback to {task.callback_url}..."
        )

        try:
            # Generate webhook signature
            webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook-secret-for-signature")

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Source": "ai-service",
                "X-Webhook-Secret": webhook_secret,  # ✅ Simplified: Use plain text secret
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    task.callback_url,
                    json=callback_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        logger.info(
                            f"✅ [EXTRACTION WORKER] Error callback sent successfully"
                        )
                    else:
                        logger.warning(
                            f"⚠️ [EXTRACTION WORKER] Error callback returned status {response.status}"
                        )

        except Exception as e:
            logger.error(
                f"❌ [EXTRACTION WORKER] Failed to send error callback: {str(e)}"
            )

    def _normalize_extraction_result(self, raw_result: dict) -> dict:
        """
        Normalize AI extraction result to ensure consistent structure
        Chuẩn hóa kết quả AI extraction để đảm bảo structure nhất quán

        Input: Raw AI result với format bất kỳ
        Output: Normalized result với structure chuẩn
        """
        normalized = {
            "raw_content": raw_result.get("raw_content", ""),
            "structured_data": {},
            "extraction_metadata": raw_result.get("extraction_metadata", {}),
            "extraction_summary": {},
        }

        # ✅ Extract products and services from various possible locations
        products = []
        services = []

        # Try direct keys first (current AI format)
        if "products" in raw_result:
            products = raw_result["products"]
        elif (
            "structured_data" in raw_result
            and "products" in raw_result["structured_data"]
        ):
            products = raw_result["structured_data"]["products"]

        if "services" in raw_result:
            services = raw_result["services"]
        elif (
            "structured_data" in raw_result
            and "services" in raw_result["structured_data"]
        ):
            services = raw_result["structured_data"]["services"]

        # ✅ Build consistent structured_data
        normalized["structured_data"] = {"products": products, "services": services}

        # ✅ Extract or calculate summary
        if "extraction_summary" in raw_result:
            summary = raw_result["extraction_summary"]
        else:
            summary = {}

        # Ensure counts are correct
        products_count = len(products)
        services_count = len(services)
        total_items = products_count + services_count

        normalized["extraction_summary"] = {
            "total_products": products_count,
            "total_services": services_count,
            "total_items": total_items,
            "data_quality": summary.get("data_quality", "good"),
            "categorization_notes": summary.get(
                "categorization_notes", "Auto-categorized"
            ),
            "industry_context": summary.get("industry_context", ""),
        }

        # ✅ Enhance extraction_metadata with counts
        metadata = normalized["extraction_metadata"]
        metadata.update(
            {
                "total_products_extracted": products_count,
                "total_services_extracted": services_count,
                "total_items_extracted": total_items,
                "extraction_success": total_items > 0,
                "structure_normalized": True,
                "normalization_timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(f"🔧 [NORMALIZATION] Data normalized successfully:")
        logger.info(f"   📦 Products: {products_count}")
        logger.info(f"   🔧 Services: {services_count}")
        logger.info(f"   📊 Total items: {total_items}")

        return normalized


# =============================================================================
# STANDALONE RUNNER FOR EXTRACTION WORKER
# =============================================================================


async def run_extraction_worker():
    """Standalone function to run extraction processing worker"""
    worker = ExtractionProcessingWorker()

    try:
        await worker.initialize()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("🛑 Extraction worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Extraction worker crashed: {e}")
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    """Run extraction worker as standalone process"""
    asyncio.run(run_extraction_worker())
