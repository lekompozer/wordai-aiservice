"""
Admin API routes for task status management.
Provides endpoints to check status of queued tasks and manage task lifecycle.
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from src.middleware.auth import verify_internal_api_key
from src.utils.logger import setup_logger
from src.queue.queue_dependencies import get_extraction_queue, get_document_queue

logger = setup_logger(__name__)
router = APIRouter(tags=["Admin - Task Status"])


class TaskStatusResponse(BaseModel):
    """Response model for task status queries"""

    task_id: str
    status: str
    message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    worker_id: Optional[str] = None

    # Task specific data
    company_id: Optional[str] = None
    r2_url: Optional[str] = None
    progress_percentage: Optional[float] = None
    estimated_remaining_time: Optional[str] = None

    # Queue information
    queue_position: Optional[int] = None
    queue_size: Optional[int] = None


@router.get(
    "/tasks/extraction/{task_id}/status",
    response_model=TaskStatusResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_extraction_task_status(
    task_id: str = Path(..., description="Task ID to check status"),
    queue_manager=Depends(get_extraction_queue),
) -> TaskStatusResponse:
    """
    Get status of an extraction task by task_id.
    Returns detailed task information including progress and queue position.
    """
    try:
        logger.info(f"📊 Checking extraction task status: {task_id}")

        # Get task status from queue manager
        task_status = await queue_manager.get_task_status(task_id)

        if not task_status:
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} not found or expired"
            )

        # Get current queue information
        queue_size = await queue_manager.get_queue_size()

        # Build response
        response = TaskStatusResponse(
            task_id=task_status.task_id,
            status=task_status.status,
            message=f"Task is {task_status.status}",
            created_at=task_status.created_at,
            updated_at=task_status.updated_at,
            completed_at=task_status.completed_at,
            error_message=task_status.error_message,
            retry_count=task_status.retry_count,
            worker_id=task_status.worker_id,
            company_id=getattr(
                task_status, "user_id", None
            ),  # user_id maps to company_id
            r2_url=getattr(
                task_status, "document_id", None
            ),  # document_id maps to r2_url
            queue_size=queue_size,
            progress_percentage=_calculate_progress_percentage(task_status.status),
            estimated_remaining_time=_estimate_remaining_time(task_status.status),
        )

        logger.info(f"✅ Task {task_id} status: {task_status.status}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get task status {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve task status: {str(e)}"
        )


@router.get(
    "/tasks/document/{task_id}/status",
    response_model=TaskStatusResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_document_task_status(
    task_id: str = Path(..., description="Task ID to check status"),
    queue_manager=Depends(get_document_queue),
) -> TaskStatusResponse:
    """
    Get status of a document processing task by task_id.
    Returns detailed task information including progress and queue position.
    """
    try:
        logger.info(f"📊 Checking document task status: {task_id}")

        # Get task status from queue manager
        task_status = await queue_manager.get_task_status(task_id)

        if not task_status:
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} not found or expired"
            )

        # Get current queue information
        queue_size = await queue_manager.get_queue_size()

        # Build response
        response = TaskStatusResponse(
            task_id=task_status.task_id,
            status=task_status.status,
            message=f"Task is {task_status.status}",
            created_at=task_status.created_at,
            updated_at=task_status.updated_at,
            completed_at=task_status.completed_at,
            error_message=task_status.error_message,
            retry_count=task_status.retry_count,
            worker_id=task_status.worker_id,
            company_id=getattr(
                task_status, "user_id", None
            ),  # user_id maps to company_id
            r2_url=getattr(
                task_status, "document_id", None
            ),  # document_id maps to r2_url
            queue_size=queue_size,
            progress_percentage=_calculate_progress_percentage(task_status.status),
            estimated_remaining_time=_estimate_remaining_time(task_status.status),
        )

        logger.info(f"✅ Task {task_id} status: {task_status.status}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get task status {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve task status: {str(e)}"
        )


@router.get(
    "/tasks/{company_id}/list",
    dependencies=[Depends(verify_internal_api_key)],
)
async def list_company_tasks(
    company_id: str = Path(..., description="Company ID"),
    queue_type: str = Query(
        "all", description="Queue type: extraction, document, or all"
    ),
    limit: int = Query(20, description="Maximum number of tasks to return"),
    status: Optional[str] = Query(
        None, description="Filter by status: pending, processing, completed, failed"
    ),
) -> Dict[str, Any]:
    """
    List recent tasks for a company across different queues.
    """
    try:
        logger.info(f"📋 Listing tasks for company {company_id}, type: {queue_type}")

        tasks = []

        if queue_type in ["extraction", "all"]:
            extraction_queue = await get_extraction_queue()
            extraction_tasks = await extraction_queue.get_user_tasks(company_id, limit)

            for task in extraction_tasks:
                if status is None or task.status == status:
                    tasks.append(
                        {
                            "task_id": task.task_id,
                            "queue_type": "extraction",
                            "status": task.status,
                            "created_at": task.created_at,
                            "updated_at": task.updated_at,
                            "completed_at": task.completed_at,
                            "error_message": task.error_message,
                        }
                    )

        if queue_type in ["document", "all"]:
            document_queue = await get_document_queue()
            document_tasks = await document_queue.get_user_tasks(company_id, limit)

            for task in document_tasks:
                if status is None or task.status == status:
                    tasks.append(
                        {
                            "task_id": task.task_id,
                            "queue_type": "document",
                            "status": task.status,
                            "created_at": task.created_at,
                            "updated_at": task.updated_at,
                            "completed_at": task.completed_at,
                            "error_message": task.error_message,
                        }
                    )

        # Sort by created_at descending
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        tasks = tasks[:limit]  # Apply final limit

        return {
            "success": True,
            "company_id": company_id,
            "total_tasks": len(tasks),
            "queue_type": queue_type,
            "status_filter": status,
            "tasks": tasks,
        }

    except Exception as e:
        logger.error(f"❌ Failed to list tasks for company {company_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve tasks: {str(e)}"
        )


# Helper functions


def _calculate_progress_percentage(status: str) -> float:
    """Calculate approximate progress percentage based on task status"""
    progress_map = {
        "pending": 0.0,
        "queued": 5.0,
        "processing": 50.0,
        "uploading": 80.0,
        "completed": 100.0,
        "failed": 0.0,
        "retry": 25.0,
    }
    return progress_map.get(status, 0.0)


def _estimate_remaining_time(status: str) -> str:
    """Estimate remaining time based on task status"""
    time_estimates = {
        "pending": "2-5 minutes",
        "queued": "1-3 minutes",
        "processing": "30-90 seconds",
        "uploading": "10-30 seconds",
        "completed": "0 seconds",
        "failed": "N/A",
        "retry": "1-2 minutes",
    }
    return time_estimates.get(status, "Unknown")
