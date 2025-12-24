"""
Sharing Service for Presentation Sharing Configuration
Handles public/private sharing, sharing settings, and access management
"""

import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from src.database.mongodb_service import get_mongodb_service
from src.models.slide_narration_models import (
    PresentationSharingConfig,
    SharingSettings,
    SharedWithUser,
)


class SharingService:
    """Service for managing presentation sharing"""

    def __init__(self):
        self.db = get_mongodb_service().db
        self.sharing_configs = self.db.presentation_sharing_config

    def generate_public_token(self) -> str:
        """Generate unique public token for sharing URL"""
        while True:
            # Generate 32-character URL-safe token
            token = secrets.token_urlsafe(24)
            # Check uniqueness
            existing = self.sharing_configs.find_one({"public_token": token})
            if not existing:
                return token

    async def get_or_create_config(
        self, presentation_id: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Get sharing config for presentation, create default if not exists

        Args:
            presentation_id: Presentation document ID
            user_id: Owner user ID

        Returns:
            Sharing config document
        """
        # Try to find existing config
        config = self.sharing_configs.find_one({"presentation_id": presentation_id})

        if config:
            config["_id"] = str(config["_id"])
            return config

        # Create default config
        default_config = {
            "presentation_id": presentation_id,
            "user_id": user_id,
            "is_public": False,
            "public_token": None,
            "sharing_settings": {
                "include_content": True,
                "include_subtitles": True,
                "include_audio": True,
                "allowed_languages": [],  # Empty = all languages
                "default_language": "vi",
                "require_attribution": True,
            },
            "shared_with_users": [],
            "access_stats": {
                "total_views": 0,
                "unique_visitors": 0,
                "last_accessed": None,
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": None,
        }

        result = self.sharing_configs.insert_one(default_config)
        default_config["_id"] = str(result.inserted_id)

        return default_config

    async def update_config(
        self,
        presentation_id: str,
        user_id: str,
        is_public: Optional[bool] = None,
        sharing_settings: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Update sharing configuration

        Args:
            presentation_id: Presentation document ID
            user_id: Owner user ID
            is_public: Enable/disable public access
            sharing_settings: Sharing settings dict
            expires_at: Expiration timestamp

        Returns:
            Updated sharing config
        """
        # Get or create config
        config = await self.get_or_create_config(presentation_id, user_id)

        # Verify ownership
        if config["user_id"] != user_id:
            raise ValueError("Only owner can update sharing config")

        # Build update dict
        update_fields = {"updated_at": datetime.utcnow()}

        # Update public access
        if is_public is not None:
            update_fields["is_public"] = is_public
            # Generate token if enabling public access
            if is_public and not config.get("public_token"):
                update_fields["public_token"] = self.generate_public_token()
            # Don't remove token when disabling (keep for re-enable)

        # Update sharing settings
        if sharing_settings:
            # Merge with existing settings
            current_settings = config.get("sharing_settings", {})
            current_settings.update(sharing_settings)
            update_fields["sharing_settings"] = current_settings

        # Update expiration
        if expires_at is not None:
            update_fields["expires_at"] = expires_at

        # Update database
        self.sharing_configs.update_one(
            {"presentation_id": presentation_id}, {"$set": update_fields}
        )

        # Return updated config
        updated_config = self.sharing_configs.find_one(
            {"presentation_id": presentation_id}
        )
        updated_config["_id"] = str(updated_config["_id"])

        return updated_config

    async def share_with_user(
        self,
        presentation_id: str,
        owner_user_id: str,
        target_user_id: str,
        permission: str = "view",
    ) -> Dict[str, Any]:
        """
        Share presentation with specific user

        Args:
            presentation_id: Presentation document ID
            owner_user_id: Owner user ID
            target_user_id: User to share with
            permission: Permission level (view, comment, edit)

        Returns:
            Updated sharing config
        """
        # Get config
        config = await self.get_or_create_config(presentation_id, owner_user_id)

        # Verify ownership
        if config["user_id"] != owner_user_id:
            raise ValueError("Only owner can share presentation")

        # Check if already shared
        shared_users = config.get("shared_with_users", [])
        existing = None
        for idx, user in enumerate(shared_users):
            if user["user_id"] == target_user_id:
                existing = idx
                break

        # Update or add
        if existing is not None:
            # Update permission
            shared_users[existing]["permission"] = permission
        else:
            # Add new
            shared_users.append(
                {
                    "user_id": target_user_id,
                    "permission": permission,
                    "granted_at": datetime.utcnow(),
                }
            )

        # Update database
        self.sharing_configs.update_one(
            {"presentation_id": presentation_id},
            {
                "$set": {
                    "shared_with_users": shared_users,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Return updated config
        updated_config = self.sharing_configs.find_one(
            {"presentation_id": presentation_id}
        )
        updated_config["_id"] = str(updated_config["_id"])

        return updated_config

    async def remove_shared_user(
        self, presentation_id: str, owner_user_id: str, target_user_id: str
    ) -> Dict[str, Any]:
        """
        Remove user from shared access

        Args:
            presentation_id: Presentation document ID
            owner_user_id: Owner user ID
            target_user_id: User to remove

        Returns:
            Updated sharing config
        """
        # Get config
        config = await self.get_or_create_config(presentation_id, owner_user_id)

        # Verify ownership
        if config["user_id"] != owner_user_id:
            raise ValueError("Only owner can remove shared users")

        # Remove user
        shared_users = config.get("shared_with_users", [])
        shared_users = [u for u in shared_users if u["user_id"] != target_user_id]

        # Update database
        self.sharing_configs.update_one(
            {"presentation_id": presentation_id},
            {
                "$set": {
                    "shared_with_users": shared_users,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Return updated config
        updated_config = self.sharing_configs.find_one(
            {"presentation_id": presentation_id}
        )
        updated_config["_id"] = str(updated_config["_id"])

        return updated_config

    async def get_public_presentation(
        self, public_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get presentation by public token (no authentication required)

        Args:
            public_token: Public sharing token

        Returns:
            Sharing config if public access enabled, None otherwise
        """
        # Find config by token
        config = self.sharing_configs.find_one(
            {"public_token": public_token, "is_public": True}
        )

        if not config:
            return None

        # Check expiration
        if config.get("expires_at"):
            if datetime.utcnow() > config["expires_at"]:
                return None

        config["_id"] = str(config["_id"])
        return config

    async def increment_access_stats(
        self, config_id: str, unique_visitor: bool = False
    ):
        """
        Increment access statistics

        Args:
            config_id: Sharing config ID
            unique_visitor: Whether this is a unique visitor
        """
        update_fields = {
            "access_stats.total_views": 1,
            "access_stats.last_accessed": datetime.utcnow(),
        }

        if unique_visitor:
            update_fields["access_stats.unique_visitors"] = 1

        self.sharing_configs.update_one(
            {"_id": ObjectId(config_id)}, {"$inc": update_fields}
        )

    async def check_user_access(
        self, presentation_id: str, user_id: str
    ) -> Optional[str]:
        """
        Check if user has access to presentation

        Args:
            presentation_id: Presentation document ID
            user_id: User ID to check

        Returns:
            Permission level if has access, None otherwise
        """
        config = self.sharing_configs.find_one({"presentation_id": presentation_id})

        if not config:
            return None

        # Owner has full access
        if config["user_id"] == user_id:
            return "owner"

        # Check shared users
        for shared_user in config.get("shared_with_users", []):
            if shared_user["user_id"] == user_id:
                return shared_user["permission"]

        return None


# Singleton instance
_sharing_service_instance = None


def get_sharing_service() -> SharingService:
    """Get SharingService singleton instance"""
    global _sharing_service_instance
    if _sharing_service_instance is None:
        _sharing_service_instance = SharingService()
    return _sharing_service_instance
