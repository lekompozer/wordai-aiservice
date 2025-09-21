"""
Firebase Admin SDK Configuration
Cấu hình Firebase Admin SDK cho backend authentication
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional, Dict, Any
from src.utils.logger import setup_logger

logger = setup_logger()


class FirebaseConfig:
    """Firebase Admin SDK Configuration Manager"""

    def __init__(self):
        self.app = None
        self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            if firebase_admin._apps:
                self.app = firebase_admin.get_app()
                logger.info("✅ Firebase Admin SDK already initialized")
                return

            # Try to initialize from service account file (Google standard)
            service_account_path = os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            ) or os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

            if service_account_path and os.path.exists(service_account_path):
                # Initialize with service account file
                cred = credentials.Certificate(service_account_path)
                self.app = firebase_admin.initialize_app(cred)
                logger.info(
                    "✅ Firebase Admin SDK initialized with service account file"
                )

            else:
                # Initialize with environment variables
                project_id = os.getenv("FIREBASE_PROJECT_ID")
                private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")
                client_email = os.getenv("FIREBASE_CLIENT_EMAIL")

                # Check if we have basic Firebase config
                if not project_id:
                    # No project ID - development mode without real Firebase
                    logger.warning(
                        "⚠️ Firebase project ID not configured - running in development mode"
                    )
                    self.app = None
                    return

                service_account_key = {
                    "type": "service_account",
                    "project_id": project_id,
                    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": private_key,
                    "client_email": client_email,
                    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
                }

                # Validate required fields
                required_fields = ["project_id", "private_key", "client_email"]
                missing_fields = [
                    field
                    for field in required_fields
                    if not service_account_key.get(field)
                ]

                if missing_fields:
                    logger.warning(
                        f"⚠️ Missing Firebase config fields: {missing_fields} - running in development mode"
                    )
                    self.app = None
                    return

                # Initialize with credentials dict
                cred = credentials.Certificate(service_account_key)
                self.app = firebase_admin.initialize_app(cred)
                logger.info(
                    "✅ Firebase Admin SDK initialized with environment variables"
                )

        except Exception as e:
            logger.warning(
                f"⚠️ Failed to initialize Firebase Admin SDK: {e} - running in development mode"
            )
            self.app = None

    def get_auth(self):
        """Get Firebase Auth instance"""
        if not self.app:
            logger.warning("🔧 Development mode: Firebase Auth not available")
            return None
        return auth

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify Firebase ID token"""
        if not self.app:
            # Development mode - create mock user data
            logger.warning(
                "🔧 Development mode: Using mock Firebase token verification"
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

        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            logger.error(f"❌ Token verification failed: {e}")
            raise

    def create_session_cookie(self, id_token: str, expires_in_hours: int = 24) -> str:
        """
        Tạo session cookie từ ID token với thời hạn dài hơn

        Args:
            id_token: Firebase ID token
            expires_in_hours: Thời gian hết hạn (giờ), mặc định 24h

        Returns:
            Session cookie string
        """
        try:
            # Chuyển đổi hours thành seconds (Firebase expects seconds, not milliseconds)
            expires_in_seconds = expires_in_hours * 60 * 60

            # Firebase max duration là 14 ngày (1209600 seconds)
            max_duration = 14 * 24 * 60 * 60  # 14 days in seconds
            if expires_in_seconds > max_duration:
                expires_in_seconds = max_duration
                logger.warning(
                    f"⚠️ Session cookie duration capped at {max_duration}s (14 days)"
                )

            # Tạo session cookie
            session_cookie = auth.create_session_cookie(
                id_token, expires_in=expires_in_seconds
            )

            logger.info(
                f"✅ Session cookie created with {expires_in_hours}h expiry ({expires_in_seconds}s)"
            )
            return session_cookie

        except Exception as e:
            logger.error(f"❌ Failed to create session cookie: {e}")
            raise

    def verify_session_cookie(self, session_cookie: str) -> Dict[str, Any]:
        """
        Verify session cookie và trả về decoded claims

        Args:
            session_cookie: Session cookie string

        Returns:
            Decoded token claims
        """
        try:
            decoded_claims = auth.verify_session_cookie(
                session_cookie, check_revoked=True
            )
            return decoded_claims

        except Exception as e:
            logger.error(f"❌ Session cookie verification failed: {e}")
            raise


# Global Firebase config instance
firebase_config = FirebaseConfig()
