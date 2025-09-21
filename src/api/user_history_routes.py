"""
API Route for retrieving user chat history.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from src.models.user_history import UserHistory
from src.services.user_history_service import (
    UserHistoryService,
    get_user_history_service,
)

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.get("/history/by-device/{device_id}", response_model=UserHistory)
async def get_user_history_by_device(
    device_id: str, service: UserHistoryService = Depends(get_user_history_service)
):
    """
    Retrieves the conversation history for a given device ID.
    """
    history = await service.get_history_by_device_id(device_id)
    if not history:
        raise HTTPException(
            status_code=404, detail=f"No history found for device_id '{device_id}'"
        )
    return history
