"""
Points-related custom exceptions
"""


class InsufficientPointsError(Exception):
    """
    Raised when user does not have enough points for an operation.

    This exception is caught by global exception handler in app.py
    and converted to HTTP 402 Payment Required with standardized error format.

    Attributes:
        message: Human-readable error message (Vietnamese)
        points_needed: Number of points required for the operation
        points_available: Current points balance
        service: Service type (e.g., "ai_chat_deepseek", "ai_document_chat_chatgpt")
        error_code: Fixed "INSUFFICIENT_POINTS" for frontend detection

    Frontend Usage:
        When catching HTTP 402 with error_code="INSUFFICIENT_POINTS",
        display a popup prompting user to purchase more points.

    Example:
        raise InsufficientPointsError(
            message="Không đủ points để chat với ChatGPT. Cần: 2, Còn: 0",
            points_needed=2,
            points_available=0,
            service="ai_chat_chatgpt"
        )
    """

    def __init__(
        self,
        message: str,
        points_needed: int,
        points_available: int,
        service: str = "unknown",
    ):
        self.message = message
        self.points_needed = points_needed
        self.points_available = points_available
        self.service = service
        self.error_code = "INSUFFICIENT_POINTS"
        super().__init__(self.message)

    def to_dict(self):
        """Convert to dict for JSON response"""
        return {
            "error": self.error_code,
            "message": self.message,
            "points_needed": self.points_needed,
            "points_available": self.points_available,
            "service": self.service,
            "action_required": "purchase_points",
            "purchase_url": "/pricing",
        }
