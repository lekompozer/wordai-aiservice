"""
Firebase Authentication Middleware
Middleware để xác thực user thông qua Firebase JWT token
"""

from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth
from src.config.firebase_config import firebase_config
from src.utils.logger import setup_logger

logger = setup_logger()

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


class FirebaseAuth:
    """Firebase Authentication Middleware"""

    def __init__(self):
        self.firebase_config = firebase_config

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Firebase ID token hoặc session cookie

        Args:
            token: Firebase ID token hoặc session cookie

        Returns:
            Dict containing user information from token

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Check for development token first (regardless of Firebase config)
            import os

            is_development = os.getenv("ENV", "").lower() in [
                "development",
                "dev",
            ] or os.getenv("ENVIRONMENT", "").lower() in ["development", "dev"]

            if is_development and (token == "dev_token" or token.startswith("dev_")):
                logger.info("🔧 Development mode: Using mock token verification")
                return {
                    "uid": "dev_user_123",
                    "email": "dev@example.com",
                    "name": "Development User",
                    "picture": "https://example.com/avatar.jpg",
                    "email_verified": True,
                    "firebase": {"sign_in_provider": "google"},
                    "auth_time": 1693123456,
                    "iat": 1693123456,
                    "exp": 1693127056,
                }

            # Check if Firebase is properly configured
            if not self.firebase_config.app:
                # Firebase not configured
                if token == "dev_token" or token.startswith("dev_"):
                    logger.info(
                        "🔧 Firebase not configured: Using mock token verification"
                    )
                    return {
                        "uid": "dev_user_123",
                        "email": "dev@example.com",
                        "name": "Development User",
                        "picture": "https://example.com/avatar.jpg",
                        "email_verified": True,
                        "firebase": {"sign_in_provider": "google"},
                        "auth_time": 1693123456,
                        "iat": 1693123456,
                        "exp": 1693127056,
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Firebase not configured - use 'dev_token' for development",
                    )

            # Try to verify as session cookie first (24-hour expiry, highest priority)
            try:
                decoded_token = self.firebase_config.verify_session_cookie(token)
                logger.debug(
                    f"✅ Session cookie verified for user: {decoded_token.get('email', decoded_token.get('uid'))}"
                )
                return decoded_token
            except Exception:
                # If session cookie fails, try as ID token (Firebase fallback)
                pass

            # Try to verify as ID token (Firebase ID token, lower priority)
            decoded_token = self.firebase_config.verify_token(token)
            logger.debug(
                f"✅ ID token verified for user: {decoded_token.get('email', decoded_token.get('uid'))}"
            )
            return decoded_token

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except auth.InvalidIdTokenError:
            logger.warning("❌ Invalid Firebase token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        except auth.ExpiredIdTokenError:
            logger.warning("❌ Expired Firebase token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
            )
        except Exception as e:
            logger.error(f"❌ Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
            )

    async def get_current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> Dict[str, Any]:
        """
        Get current authenticated user from Firebase token
        Support both session cookie (priority) and Authorization header (fallback)

        Args:
            request: FastAPI Request object
            credentials: HTTP Authorization credentials (optional)

        Returns:
            Dict containing user information

        Raises:
            HTTPException: If no token or invalid token
        """
        logger.info(f"🔐 AUTH CHECK: {request.method} {request.url.path}")
        logger.info(f"🍪 Cookies: {list(request.cookies.keys())}")
        logger.info(
            f"📋 Headers Authorization: {request.headers.get('authorization', 'NOT FOUND')[:50] if request.headers.get('authorization') else 'NOT FOUND'}"
        )

        # 🔄 PRIORITY 1: Check session cookie first (24h, highest priority)
        session_cookie = request.cookies.get("session")
        if session_cookie:
            try:
                user_data = await self.verify_token(session_cookie)
                logger.info("✅ Using session cookie for authentication")
                return user_data
            except Exception as e:
                logger.warning(
                    f"⚠️ Session cookie invalid, falling back to Authorization header: {e}"
                )

        # 🔄 PRIORITY 2: Fallback to Authorization Bearer header
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token required",
            )

        user_data = await self.verify_token(credentials.credentials)
        logger.debug("✅ Using Authorization Bearer token for authentication")
        return user_data

    async def get_current_user_optional(
        self, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Optional[Dict[str, Any]]:
        """
        Get current user if authenticated, otherwise return None
        Useful for endpoints that work for both authenticated and unauthenticated users

        Args:
            credentials: HTTP Authorization credentials (optional)

        Returns:
            Dict containing user information or None
        """
        if not credentials:
            return None

        try:
            return await self.verify_token(credentials.credentials)
        except HTTPException:
            return None

    def extract_user_info(self, decoded_token: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract standardized user information from Firebase token

        Args:
            decoded_token: Decoded Firebase token

        Returns:
            Dict with standardized user info
        """
        # Firebase token có thể có 'uid' hoặc 'user_id' tùy version
        user_id = decoded_token.get("uid") or decoded_token.get("user_id")

        return {
            "uid": user_id,  # Trả về key 'uid' để phù hợp với chat_routes.py
            "firebase_uid": user_id,
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False),
            "display_name": decoded_token.get("name"),
            "photo_url": decoded_token.get("picture"),
            "provider": decoded_token.get("firebase", {}).get(
                "sign_in_provider", "unknown"
            ),
            "auth_time": decoded_token.get("auth_time"),
            "iat": decoded_token.get("iat"),
            "exp": decoded_token.get("exp"),
        }


# Global Firebase auth instance
firebase_auth = FirebaseAuth()


# Dependency functions for FastAPI
async def get_current_user(
    request: Request,
    user_data: Dict[str, Any] = Depends(firebase_auth.get_current_user),
) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user"""
    return firebase_auth.extract_user_info(user_data)


async def get_current_user_optional(
    user_data: Optional[Dict[str, Any]] = Depends(
        firebase_auth.get_current_user_optional
    ),
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to get current user (optional)"""
    if user_data:
        return firebase_auth.extract_user_info(user_data)
    return None


async def require_auth(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """FastAPI dependency that requires authentication"""
    return user
