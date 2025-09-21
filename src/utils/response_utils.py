"""
Response utilities for API endpoints
"""

from typing import Dict, Any, Optional


def create_success_response(
    data: Any = None, message: str = "Success", code: str = "SUCCESS"
) -> Dict[str, Any]:
    """Create standardized success response"""
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "timestamp": None,  # Will be set by middleware if needed
    }


def create_error_response(
    message: str = "Error occurred",
    error_code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized error response"""
    return {
        "success": False,
        "code": error_code,
        "message": message,
        "error": details,
        "timestamp": None,  # Will be set by middleware if needed
    }


def create_validation_error_response(
    field: str, message: str, value: Any = None
) -> Dict[str, Any]:
    """Create validation error response"""
    return create_error_response(
        message="Validation error",
        error_code="VALIDATION_ERROR",
        details={"field": field, "message": message, "value": value},
    )
