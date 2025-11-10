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

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get Firebase user by email address

        Returns user data including uid, or None if user not found
        """
        if not self.app:
            logger.warning("🔧 Development mode: Firebase Auth not available")
            return None

        try:
            user = auth.get_user_by_email(email)
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
            }
        except auth.UserNotFoundError:
            logger.warning(f"⚠️ Firebase user not found: {email}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting Firebase user by email: {e}")
            return None

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify Firebase ID token"""
        logger.debug(f"🔍 verify_token() called with token length: {len(token)}")

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
            logger.debug("🔍 Calling auth.verify_id_token()...")
            decoded_token = auth.verify_id_token(token)
            logger.debug(
                f"✅ verify_id_token() SUCCESS - User: {decoded_token.get('email')}"
            )
            logger.debug(f"   Issuer: {decoded_token.get('iss')}")
            return decoded_token
        except Exception as e:
            logger.error(f"❌ Token verification failed: {e}")
            raise


# Global Firebase config instance
firebase_config = FirebaseConfig()
