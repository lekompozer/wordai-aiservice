"""
Pydantic Models for User Chat History
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    role: str = Field(
        ..., description="Role of the message sender (e.g., 'user', 'assistant')."
    )
    content: str = Field(..., description="Content of the chat message.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserHistory(BaseModel):
    device_id: str = Field(..., description="The unique device ID of the user.")
    history: List[ChatMessage] = Field(
        default_factory=list, description="A list of chat messages."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Any additional metadata."
    )
