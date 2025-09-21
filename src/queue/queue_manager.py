"""
Queue Manager for handling asynchronous tasks including document processing and extraction.
Uses Redis as the message broker for task distribution.
Support for multiple queue types with configurable settings.
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    logging.warning("Redis not available for queue management")
    REDIS_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class IngestionTask:
    """Legacy document ingestion task - kept for backward compatibility"""

    task_id: str
    user_id: str
    document_id: str
    file_path: str
    filename: str
    file_type: str
    file_size: int
    upload_timestamp: str
    callback_url: Optional[str] = None
    additional_metadata: Optional[Dict[str, Any]] = None
    priority: int = 1  # 1 = normal, 2 = high, 3 = urgent
    max_retries: int = 3
    retry_count: int = 0
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class TaskStatus:
    """Represents the status of an ingestion task"""

    task_id: str
    status: str  # pending, processing, completed, failed
    user_id: str
    document_id: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    worker_id: Optional[str] = None


class QueueManager:
    """
    Manages document ingestion task queue using Redis.
    Handles task scheduling, status tracking, and result management.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        queue_name: str = "document_ingestion",
        status_expiry_hours: int = 24,
        max_queue_size: int = 10000,
    ):
        """
        Initialize queue manager.

        Args:
            redis_url: Redis connection URL
            queue_name: Name of the task queue
            status_expiry_hours: How long to keep task status (hours)
            max_queue_size: Maximum number of tasks in queue
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available. Please install: pip install redis")

        self.redis_url = redis_url
        self.queue_name = queue_name
        self.status_expiry_hours = status_expiry_hours
        self.max_queue_size = max_queue_size

        # Redis key patterns
        self.task_queue_key = f"queue:{queue_name}"
        self.task_status_key = lambda task_id: f"status:{queue_name}:{task_id}"
        self.processing_key = f"processing:{queue_name}"
        self.dead_letter_key = f"dead_letter:{queue_name}"
        self.stats_key = f"stats:{queue_name}"

        self.redis_client = None

    async def connect(self):
        """Establish Redis connection with retry logic and replica handling"""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Close existing connection if any
                if self.redis_client:
                    try:
                        await self.redis_client.close()
                    except:
                        pass
                    self.redis_client = None

                # Create new connection with specific settings for production
                self.redis_client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=10,  # 10 second connection timeout
                    socket_timeout=30,  # 30 second socket timeout
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError, TimeoutError],
                    health_check_interval=60,  # Check connection every 60s
                    max_connections=20,  # Connection pool size
                )

                # Test connection and check Redis role
                await self.redis_client.ping()

                # Check if Redis is master (can write)
                try:
                    info_result = await self.redis_client.info("replication")
                    role = info_result.get("role", "unknown")

                    if role == "slave":
                        logger.warning(
                            f"⚠️ Redis is in replica mode (slave), attempting to reconnect to master..."
                        )
                        # If it's a slave, we need to find the master
                        # For now, try to continue but log the issue
                    else:
                        logger.info(f"✅ Redis role: {role} (can write)")

                except Exception as role_check_error:
                    logger.warning(f"⚠️ Could not check Redis role: {role_check_error}")

                # Test write operation
                test_key = f"test_write_{int(time.time())}"
                await self.redis_client.set(test_key, "test", ex=5)
                await self.redis_client.delete(test_key)

                logger.info(
                    f"✅ Successfully connected to Redis (attempt {attempt + 1})"
                )
                logger.info(f"   URL: {self.redis_url}")
                logger.info(f"   Write test: PASSED")
                return

            except Exception as e:
                error_msg = str(e).lower()
                logger.error(
                    f"❌ Failed to connect to Redis (attempt {attempt + 1}): {e}"
                )

                # Special handling for read-only replica
                if "read only replica" in error_msg or "readonly" in error_msg:
                    logger.error("🚨 Redis is in read-only mode! This usually means:")
                    logger.error("   1. Redis container is running as replica/slave")
                    logger.error("   2. Redis cluster is in failover mode")
                    logger.error("   3. Redis configuration has replica-read-only yes")

                    # Try alternative connection strings for different Redis setups
                    if attempt < 2:  # Try different approaches first
                        alternative_urls = [
                            self.redis_url.replace("redis://", "redis://").replace(
                                ":6379", ":6380"
                            ),  # Try different port
                            self.redis_url.replace(
                                "redis://redis:", "redis://localhost:"
                            ),  # Try localhost
                            self.redis_url.replace("redis://", "rediss://"),  # Try SSL
                        ]

                        for alt_url in alternative_urls:
                            try:
                                logger.info(
                                    f"🔄 Trying alternative Redis URL: {alt_url}"
                                )
                                test_client = aioredis.from_url(
                                    alt_url, encoding="utf-8", decode_responses=True
                                )
                                await test_client.ping()
                                await test_client.close()
                                logger.info(f"✅ Alternative URL works: {alt_url}")
                                self.redis_url = alt_url
                                break
                            except:
                                continue

                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * 1.5, 30
                    )  # Exponential backoff, max 30s
                else:
                    logger.error("🚨 Max Redis connection retries reached")
                    logger.error("💡 Possible solutions:")
                    logger.error("   1. Check Redis container status: docker ps")
                    logger.error(
                        "   2. Check Redis logs: docker logs <redis_container>"
                    )
                    logger.error("   3. Restart Redis: docker-compose restart redis")
                    logger.error(
                        "   4. Check Redis config: docker exec <redis_container> redis-cli info replication"
                    )
                    raise ConnectionError(
                        f"Failed to connect to Redis after {max_retries} attempts. Last error: {e}"
                    )

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    async def enqueue_task(self, task: Union[IngestionTask, BaseModel]) -> bool:
        """
        Enqueue task to Redis with fallback processing
        Queue task với fallback processing nếu Redis lỗi
        """
        try:
            if not self.redis_client:
                await self.connect()

            task_data = self._serialize_task(task)
            task_id = getattr(task, "task_id", str(uuid.uuid4()))

            # Check queue size / Kiểm tra kích thước queue
            queue_size = await self.redis_client.llen(self.task_queue_key)
            logger.info(f"📊 Queue size before enqueue: {queue_size}")

            # Add to queue with priority
            priority = getattr(task, "priority", 1)
            if priority > 1:  # High priority goes to front
                await self.redis_client.lpush(self.task_queue_key, task_data)
            else:  # Normal priority goes to back
                await self.redis_client.rpush(self.task_queue_key, task_data)

            # Set task status
            status = TaskStatus(
                task_id=task_id,
                status="queued",
                user_id=getattr(task, "user_id", "unknown"),
                document_id=getattr(task, "document_id", "unknown"),
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                queue_position=queue_size + 1,
            )

            await self._set_task_status(status)
            await self._increment_stat("tasks_queued")

            logger.info(f"✅ Task {task_id} queued successfully (priority: {priority})")
            return True

        except Exception as e:
            # Log error but try fallback processing
            try:
                error_task_id = getattr(task, "task_id", "unknown")
            except:
                error_task_id = "unknown"

            logger.error(f"❌ Failed to queue task {error_task_id}: {e}")

            # 🚨 FALLBACK: Try immediate processing without queue
            if "read only replica" in str(e).lower() or "readonly" in str(e).lower():
                logger.warning(
                    "🔄 Redis read-only detected, attempting immediate processing fallback..."
                )
                try:
                    await self._process_task_immediately(task)
                    logger.info(
                        f"✅ Task {error_task_id} processed immediately (Redis fallback)"
                    )
                    return True
                except Exception as fallback_error:
                    logger.error(
                        f"❌ Immediate processing fallback failed: {fallback_error}"
                    )

            return False

    async def dequeue_task(
        self, worker_id: str, timeout: int = 10
    ) -> Optional[IngestionTask]:
        """
        Get next task from queue for processing.

        Args:
            worker_id: Identifier for the worker requesting the task
            timeout: Timeout for blocking pop operation

        Returns:
            IngestionTask if available, None if timeout or error
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Blocking pop from queue with timeout
            result = await asyncio.wait_for(
                self.redis_client.blpop(self.task_queue_key, timeout=timeout),
                timeout=timeout + 5,  # Extra 5 seconds for network
            )

            if not result:
                return None

            _, task_data = result
            task_dict = json.loads(task_data)
            task = IngestionTask(**task_dict)

            # Move to processing set with timestamp
            processing_data = {
                "task_id": task.task_id,
                "worker_id": worker_id,
                "started_at": datetime.utcnow().isoformat(),
                "task_data": task_data,
            }

            await self.redis_client.hset(
                self.processing_key, task.task_id, json.dumps(processing_data)
            )

            # Update task status
            status = TaskStatus(
                task_id=task.task_id,
                status="processing",
                user_id=task.user_id,
                document_id=task.document_id,
                created_at=task.created_at,
                started_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                worker_id=worker_id,
                retry_count=task.retry_count,
            )

            await self._set_task_status(status)
            await self._increment_stat("tasks_processing")

            logger.info(f"Dequeued task {task.task_id} for worker {worker_id}")
            return task

        except asyncio.TimeoutError:
            # Normal timeout, no task available
            return None
        except Exception as e:
            # Handle specific Redis errors differently
            error_msg = str(e).lower()

            if "unblocked" in error_msg and "replica" in error_msg:
                logger.warning(
                    f"Redis role changed (master->replica), reconnecting: {e}"
                )
                # Clear connection and reconnect for next attempt
                try:
                    if self.redis_client:
                        await self.redis_client.close()
                    self.redis_client = None
                except:
                    pass
                return None
            elif "connection" in error_msg:
                logger.warning(f"Redis connection issue, will retry: {e}")
                try:
                    if self.redis_client:
                        await self.redis_client.close()
                    self.redis_client = None
                except:
                    pass
                return None
            else:
                logger.error(f"Failed to dequeue task: {e}")
                # Try to reconnect for next attempt
                try:
                    if self.redis_client:
                        await self.redis_client.close()
                    self.redis_client = None
                except:
                    pass
                return None

    async def complete_task(
        self, task_id: str, success: bool, error_message: Optional[str] = None
    ):
        """
        Mark a task as completed or failed.

        Args:
            task_id: Task identifier
            success: Whether task completed successfully
            error_message: Error message if task failed
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Remove from processing set
            processing_data = await self.redis_client.hget(self.processing_key, task_id)
            if processing_data:
                await self.redis_client.hdel(self.processing_key, task_id)

                processing_info = json.loads(processing_data)

                # Update task status
                current_status = await self.get_task_status(task_id)
                if current_status:
                    current_status.status = "completed" if success else "failed"
                    current_status.completed_at = datetime.utcnow().isoformat()
                    current_status.error_message = error_message

                    await self._set_task_status(current_status)

                # Update stats
                if success:
                    await self._increment_stat("tasks_completed")
                else:
                    await self._increment_stat("tasks_failed")

                    # Handle retry logic for failed tasks
                    if error_message and "retry" not in error_message.lower():
                        task_data = json.loads(processing_info["task_data"])
                        task = IngestionTask(**task_data)

                        if task.retry_count < task.max_retries:
                            task.retry_count += 1
                            await self._retry_task(task, error_message)
                        else:
                            await self._send_to_dead_letter(task, error_message)

                logger.info(
                    f"Task {task_id} marked as {'completed' if success else 'failed'}"
                )

        except Exception as e:
            logger.error(f"Failed to complete task {task_id}: {e}")

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskStatus if found, None otherwise
        """
        try:
            if not self.redis_client:
                await self.connect()

            status_data = await self.redis_client.get(self.task_status_key(task_id))
            if status_data:
                status_dict = json.loads(status_data)
                return TaskStatus(**status_dict)

            return None

        except Exception as e:
            logger.error(f"Failed to get task status {task_id}: {e}")
            return None

    async def get_user_tasks(self, user_id: str, limit: int = 50) -> List[TaskStatus]:
        """
        Get recent tasks for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of tasks to return

        Returns:
            List of TaskStatus objects
        """
        try:
            if not self.redis_client:
                await self.connect()

            # This is a simplified implementation
            # In production, you might want to maintain user-specific indexes
            tasks = []

            # Scan for task status keys (not efficient for large scale)
            pattern = f"status:{self.queue_name}:*"
            async for key in self.redis_client.scan_iter(match=pattern):
                status_data = await self.redis_client.get(key)
                if status_data:
                    status_dict = json.loads(status_data)
                    if status_dict.get("user_id") == user_id:
                        tasks.append(TaskStatus(**status_dict))

                        if len(tasks) >= limit:
                            break

            # Sort by created_at descending
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            return tasks[:limit]

        except Exception as e:
            logger.error(f"Failed to get user tasks for {user_id}: {e}")
            return []

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Get basic counts
            pending_count = await self.redis_client.llen(self.task_queue_key)
            processing_count = await self.redis_client.hlen(self.processing_key)
            dead_letter_count = await self.redis_client.llen(self.dead_letter_key)

            # Get stats
            stats = await self.redis_client.hgetall(self.stats_key)

            return {
                "pending_tasks": pending_count,
                "processing_tasks": processing_count,
                "dead_letter_tasks": dead_letter_count,
                "total_queued": int(stats.get("tasks_queued", 0)),
                "total_completed": int(stats.get("tasks_completed", 0)),
                "total_failed": int(stats.get("tasks_failed", 0)),
                "total_retried": int(stats.get("tasks_retried", 0)),
            }

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}

    async def cleanup_old_tasks(self, hours: int = None):
        """
        Clean up old task status records.

        Args:
            hours: Age threshold in hours (uses instance default if None)
        """
        try:
            if hours is None:
                hours = self.status_expiry_hours

            if not self.redis_client:
                await self.connect()

            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            pattern = f"status:{self.queue_name}:*"
            cleaned = 0

            async for key in self.redis_client.scan_iter(match=pattern):
                status_data = await self.redis_client.get(key)
                if status_data:
                    status_dict = json.loads(status_data)
                    created_at = datetime.fromisoformat(status_dict["created_at"])

                    if created_at < cutoff_time:
                        await self.redis_client.delete(key)
                        cleaned += 1

            logger.info(f"Cleaned up {cleaned} old task status records")

        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")

    async def _set_task_status(self, status: TaskStatus):
        """Set task status with expiration"""
        status_data = json.dumps(asdict(status))
        await self.redis_client.setex(
            self.task_status_key(status.task_id),
            timedelta(hours=self.status_expiry_hours),
            status_data,
        )

    async def _increment_stat(self, stat_name: str):
        """Increment a statistic counter"""
        await self.redis_client.hincrby(self.stats_key, stat_name, 1)

    async def _retry_task(self, task: IngestionTask, error_message: str):
        """Retry a failed task"""
        task.retry_count += 1

        # Add delay before retry (exponential backoff)
        delay_seconds = min(300, 60 * (2 ** (task.retry_count - 1)))  # Max 5 minutes

        # In a real implementation, you might use a delayed queue
        # For now, just re-queue immediately
        await self.enqueue_task(task)
        await self._increment_stat("tasks_retried")

        logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count})")

    async def _send_to_dead_letter(self, task: IngestionTask, error_message: str):
        """Send task to dead letter queue after max retries"""
        dead_letter_data = {
            "task": asdict(task),
            "final_error": error_message,
            "failed_at": datetime.utcnow().isoformat(),
        }

        await self.redis_client.lpush(
            self.dead_letter_key, json.dumps(dead_letter_data)
        )

        logger.error(
            f"Task {task.task_id} sent to dead letter queue after {task.retry_count} retries"
        )

    async def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed task by re-queuing it.

        Args:
            task_id: Task identifier

        Returns:
            True if task was successfully re-queued
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Get task status
            status = await self.get_task_status(task_id)
            if not status or status.status not in ["failed"]:
                logger.warning(
                    f"Task {task_id} cannot be retried (status: {status.status if status else 'not found'})"
                )
                return False

            # Try to get task from dead letter queue
            dead_letter_data = await self.redis_client.lrange(
                self.dead_letter_key, 0, -1
            )

            for i, data in enumerate(dead_letter_data):
                dead_item = json.loads(data)
                if dead_item["task"]["task_id"] == task_id:
                    # Remove from dead letter queue
                    await self.redis_client.lrem(self.dead_letter_key, 1, data)

                    # Create new task with incremented retry count
                    task_dict = dead_item["task"]
                    task = IngestionTask(**task_dict)

                    # Reset retry count if max retries exceeded
                    if task.retry_count >= task.max_retries:
                        task.retry_count = 0

                    # Re-queue the task
                    success = await self.enqueue_task(task)
                    if success:
                        logger.info(f"Task {task_id} re-queued for retry")
                        return True
                    else:
                        # Put back in dead letter queue if re-queue failed
                        await self.redis_client.lpush(self.dead_letter_key, data)
                        return False

            logger.warning(f"Task {task_id} not found in dead letter queue")
            return False

        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {e}")
            return False

    async def enqueue_generic_task(self, task: BaseModel) -> bool:
        """
        Add a generic Pydantic task to the queue.

        Args:
            task: Pydantic model task to add to queue

        Returns:
            True if task was queued successfully
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Check queue size
            queue_size = await self.redis_client.llen(self.task_queue_key)
            if queue_size >= self.max_queue_size:
                logger.error(f"Queue is full ({queue_size} tasks)")
                return False

            # Serialize task using Pydantic
            task_data = task.model_dump_json()

            # Get priority from task if available
            priority = getattr(task, "priority", 1)

            # Add to queue based on priority
            if priority >= 3:
                # High priority - add to front
                await self.redis_client.lpush(self.task_queue_key, task_data)
            else:
                # Normal priority - add to back
                await self.redis_client.rpush(self.task_queue_key, task_data)

            # Set initial status if task has task_id
            if hasattr(task, "task_id"):
                status = TaskStatus(
                    task_id=task.task_id,
                    status="pending",
                    user_id=getattr(
                        task, "company_id", getattr(task, "user_id", "unknown")
                    ),
                    document_id=getattr(
                        task, "r2_url", getattr(task, "document_id", "unknown")
                    ),
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                )

                await self._set_task_status(status)

            # Update stats
            await self._increment_stat("tasks_queued")

            task_id = getattr(task, "task_id", "unknown")
            logger.info(f"Queued generic task {task_id} of type {type(task).__name__}")
            return True

        except Exception as e:
            task_id = getattr(task, "task_id", "unknown")
            logger.error(f"Failed to queue generic task {task_id}: {e}")
            return False

    async def dequeue_generic_task(
        self, worker_id: str, timeout: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Get next task from queue for processing (returns raw dict).

        Args:
            worker_id: Identifier for the worker requesting the task
            timeout: Timeout for blocking pop operation

        Returns:
            Task dict if available, None if timeout or error
        """
        try:
            if not self.redis_client:
                await self.connect()

            # Blocking pop from queue
            result = await self.redis_client.blpop(self.task_queue_key, timeout=timeout)

            if not result:
                return None

            _, task_data = result
            task_dict = json.loads(task_data)

            # Move to processing set for tracking
            task_id = task_dict.get("task_id", str(uuid.uuid4()))
            await self.redis_client.sadd(
                self.processing_key,
                json.dumps(
                    {
                        "task_id": task_id,
                        "worker_id": worker_id,
                        "started_at": datetime.now().isoformat(),
                    }
                ),
            )

            # Update stats
            await self._increment_stat("tasks_processed")

            logger.info(f"Dequeued task {task_id} for worker {worker_id}")
            return task_dict

        except Exception as e:
            logger.error(f"Failed to dequeue task: {e}")
            return None

    async def get_queue_size(self) -> int:
        """
        Get current queue size.

        Returns:
            Number of tasks in queue
        """
        try:
            if not self.redis_client:
                await self.connect()

            return await self.redis_client.llen(self.task_queue_key)

        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        worker_id: str = None,
        error_message: str = None,
    ):
        """
        Update task status.

        Args:
            task_id: Task ID to update
            status: New status ('queued', 'processing', 'completed', 'failed')
            worker_id: ID of worker processing the task
            error_message: Error message if status is 'failed'
        """
        try:
            # Create TaskStatus object
            from datetime import datetime

            now = datetime.now().isoformat()

            # Get current status to preserve some fields
            current_status = await self.get_task_status(task_id)

            if current_status:
                # Update existing status
                updated_status = TaskStatus(
                    task_id=task_id,
                    status=status,
                    user_id=current_status.user_id,
                    document_id=current_status.document_id,
                    created_at=current_status.created_at,
                    started_at=(
                        current_status.started_at if status != "processing" else now
                    ),
                    completed_at=now if status in ["completed", "failed"] else None,
                    updated_at=now,
                    error_message=error_message,
                    retry_count=current_status.retry_count,
                    worker_id=worker_id,
                )
            else:
                # Create new status (fallback)
                updated_status = TaskStatus(
                    task_id=task_id,
                    status=status,
                    user_id="unknown",
                    document_id="unknown",
                    created_at=now,
                    started_at=now if status == "processing" else None,
                    completed_at=now if status in ["completed", "failed"] else None,
                    updated_at=now,
                    error_message=error_message,
                    retry_count=0,
                    worker_id=worker_id,
                )

            await self._set_task_status(updated_status)
            logger.info(f"Updated task {task_id} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update task status for {task_id}: {e}")

    async def _process_task_immediately(self, task):
        """
        Process task immediately without Redis queue (fallback)
        Xử lý task ngay lập tức không qua Redis queue (fallback)
        """
        try:
            logger.info("🚨 FALLBACK: Processing task immediately without queue")

            # Import necessary workers
            from src.workers.document_processing_worker import DocumentProcessingWorker

            # Create a temporary worker
            worker = DocumentProcessingWorker(
                worker_id="fallback_worker", poll_interval=1.0, redis_url=self.redis_url
            )

            # Initialize worker
            await worker.initialize()

            # Process the task directly
            await worker.process_task(task)

            logger.info("✅ FALLBACK: Task processed successfully without queue")

        except Exception as e:
            logger.error(f"❌ FALLBACK: Immediate processing failed: {e}")
            raise


# Factory function
def create_queue_manager() -> QueueManager:
    """
    Create QueueManager from environment variables.

    Environment variables:
        REDIS_URL: Redis connection URL
        QUEUE_NAME: Name of the task queue
        TASK_STATUS_EXPIRY_HOURS: Task status retention
        MAX_QUEUE_SIZE: Maximum queue size

    Returns:
        Configured QueueManager instance
    """
    return QueueManager(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        queue_name=os.getenv("QUEUE_NAME", "document_ingestion"),
        status_expiry_hours=int(os.getenv("TASK_STATUS_EXPIRY_HOURS", "24")),
        max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "10000")),
    )
