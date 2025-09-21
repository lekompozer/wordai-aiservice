"""
Service for managing User Chat History.
"""

from typing import Dict, Optional
from src.models.user_history import UserHistory, ChatMessage

# In-memory database for simplicity
# In a real application, this would be a connection to a persistent database.
_history_db: Dict[str, UserHistory] = {}


class UserHistoryService:
    def __init__(self, db: Dict[str, UserHistory]):
        self.db = db

    async def get_history_by_device_id(self, device_id: str) -> Optional[UserHistory]:
        """
        Retrieves the full history object for a given device ID.
        """
        return self.db.get(device_id)

    async def add_message_to_history(self, device_id: str, message: ChatMessage):
        """
        Adds a new message to a user's history. Creates a new history if one
        doesn't exist.
        """
        if device_id not in self.db:
            self.db[device_id] = UserHistory(device_id=device_id)

        self.db[device_id].history.append(message)
        return self.db[device_id]

    def get_formatted_history_string(
        self, history: Optional[UserHistory], limit: int = 10
    ) -> str:
        """
        Formats the last N messages into a string for the LLM prompt.
        """
        if not history or not history.history:
            return "No previous conversation history."

        recent_messages = history.history[-limit:]

        formatted = ["### Previous Conversation History:"]
        for msg in recent_messages:
            formatted.append(f"- {msg.role.capitalize()}: {msg.content}")

        return "\n".join(formatted)


# Dependency-injection function
def get_user_history_service() -> UserHistoryService:
    # For demonstration, we can add some dummy data
    if "test_device_123" not in _history_db:
        _history_db["test_device_123"] = UserHistory(
            device_id="test_device_123",
            history=[
                ChatMessage(
                    role="user", content="Hello, I'm interested in your products."
                ),
                ChatMessage(
                    role="assistant",
                    content="Welcome! I can help with that. What kind of products are you looking for?",
                ),
            ],
        )
    return UserHistoryService(db=_history_db)
