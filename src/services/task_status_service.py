"""
Callback and Task Status Services for Worker
Helper services for async extraction workflow
"""

import json
import redis
import aiohttp
import asyncio
from typing import Optional, Dict
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TaskStatusService:
    """Service to manage task status and results"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.task_prefix = "task_status:"
        self.result_prefix = "task_result:"
        self.ttl = 3600  # 1 hour TTL for task data

    async def create_task(self, task_id: str, company_id: str, submitted_at) -> bool:
        """Create initial task status"""
        try:
            task_data = {
                "task_id": task_id,
                "status": "queued",
                "submitted_at": submitted_at.isoformat(),
                "company_id": company_id,
            }

            # Store with TTL
            key = f"{self.task_prefix}{task_id}"
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.redis.setex(key, self.ttl, json.dumps(task_data))
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create task status for {task_id}: {e}")
            return False

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status"""
        try:
            key = f"{self.task_prefix}{task_id}"
            data = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.get, key
            )

            if not data:
                return None

            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return None

    async def get_task_result(self, task_id: str) -> Optional[Dict]:
        """Get task result"""
        try:
            key = f"{self.result_prefix}{task_id}"
            data = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.get, key
            )

            if not data:
                return None

            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get task result for {task_id}: {e}")
            return None

    async def update_task_status(
        self, task_id: str, status: str, progress: Optional[Dict] = None
    ) -> bool:
        """Update task status"""
        try:
            key = f"{self.task_prefix}{task_id}"

            # Get existing data
            existing_data = await asyncio.get_event_loop().run_in_executor(
                None, self.redis.get, key
            )

            if not existing_data:
                return False

            task_data = json.loads(existing_data)
            task_data["status"] = status

            if progress:
                task_data["progress"] = progress

            if status in ["completed", "failed"]:
                task_data["completed_at"] = datetime.now().isoformat()

            # Update with TTL
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.redis.setex(key, self.ttl, json.dumps(task_data))
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update task status for {task_id}: {e}")
            return False

    async def store_task_result(self, task_id: str, result_data: Dict) -> bool:
        """Store task result"""
        try:
            key = f"{self.result_prefix}{task_id}"

            # Add timestamp
            result_data["stored_at"] = datetime.now().isoformat()

            # Store with TTL
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.redis.setex(key, self.ttl, json.dumps(result_data))
            )

            # Update task status to completed
            await self.update_task_status(task_id, "completed")
            return True
        except Exception as e:
            logger.error(f"Failed to store task result for {task_id}: {e}")
            return False


class CallbackService:
    """Service to handle callback notifications"""

    @staticmethod
    async def send_callback(
        callback_url: str, task_id: str, status: str, data: Optional[Dict] = None
    ):
        """Send callback notification to backend"""
        if not callback_url:
            return

        try:
            callback_payload = {
                "task_id": task_id,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "data": data or {},
            }

            logger.info(f"📞 Sending callback for {task_id} to {callback_url}")

            # Send async HTTP request
            timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    callback_url,
                    json=callback_payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Callback sent successfully for {task_id}")
                    else:
                        logger.warning(
                            f"⚠️ Callback returned status {response.status} for {task_id}"
                        )

        except Exception as e:
            logger.error(f"❌ Failed to send callback for {task_id}: {e}")

    @staticmethod
    async def send_completion_callback(
        callback_url: str, task_id: str, extraction_result: Dict
    ):
        """Send completion callback with extraction results"""
        completion_data = {
            "success": extraction_result.get("success", False),
            "processing_time": extraction_result.get("processing_time"),
            "total_items_extracted": extraction_result.get("total_items_extracted"),
            "ai_provider": extraction_result.get("ai_provider"),
            "template_used": extraction_result.get("template_used"),
            "industry": extraction_result.get("industry"),
            "data_type": extraction_result.get("data_type"),
            "extraction_summary": {
                "products_count": len(
                    extraction_result.get("structured_data", {}).get("products", [])
                ),
                "services_count": len(
                    extraction_result.get("structured_data", {}).get("services", [])
                ),
                "has_raw_content": bool(extraction_result.get("raw_content")),
            },
        }

        await CallbackService.send_callback(
            callback_url, task_id, "completed", completion_data
        )

    @staticmethod
    async def send_error_callback(
        callback_url: str,
        task_id: str,
        error_message: str,
        error_details: Optional[Dict] = None,
    ):
        """Send error callback"""
        error_data = {
            "error": error_message,
            "error_details": error_details or {},
            "failed_at": datetime.now().isoformat(),
        }

        await CallbackService.send_callback(callback_url, task_id, "failed", error_data)
