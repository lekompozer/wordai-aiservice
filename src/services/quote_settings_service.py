"""Service for managing user quote settings"""

import logging
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.models.settings_models import (
    UserQuoteSettings,
    UpdateQuoteSettingsRequest,
    CompanyInfo,
    QuoteNotes,
)

logger = logging.getLogger(__name__)


class QuoteSettingsService:
    """Service for managing user quote settings"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.user_quote_settings

    async def get_user_settings(self, user_id: str) -> Optional[UserQuoteSettings]:
        """Lấy settings của user"""
        try:
            settings_doc = await self.collection.find_one({"user_id": user_id})

            if not settings_doc:
                logger.info(f"No settings found for user {user_id}")
                return None

            # Convert ObjectId to string
            if "_id" in settings_doc:
                settings_doc["_id"] = str(settings_doc["_id"])

            return UserQuoteSettings(**settings_doc)

        except Exception as e:
            logger.error(f"Error getting user settings: {str(e)}")
            raise Exception(f"Lỗi khi lấy cài đặt người dùng: {str(e)}")

    async def create_default_settings(self, user_id: str) -> UserQuoteSettings:
        """Tạo settings mặc định cho user mới"""
        try:
            default_settings = UserQuoteSettings(
                user_id=user_id,
                company_info=CompanyInfo(
                    name="Tên công ty",
                    address="Địa chỉ công ty",
                    phone="0901234567",
                    email="email@company.com",
                    website="https://company.com",
                    representative="Người đại diện",
                    position="Giám đốc",
                ),
                quote_notes=QuoteNotes(
                    default_notes="Cảm ơn quý khách đã quan tâm đến sản phẩm của chúng tôi.",
                    payment_terms="Báo giá có hiệu lực trong 30 ngày. Thanh toán 100% trước khi giao hàng.",
                ),
            )

            # Insert vào database
            result = await self.collection.insert_one(
                default_settings.dict(by_alias=True, exclude={"id"})
            )

            default_settings.id = str(result.inserted_id)
            logger.info(f"Created default settings for user {user_id}")

            return default_settings

        except Exception as e:
            logger.error(f"Error creating default settings: {str(e)}")
            raise Exception(f"Lỗi khi tạo cài đặt mặc định: {str(e)}")

    async def update_user_settings(
        self, user_id: str, update_request: UpdateQuoteSettingsRequest
    ) -> UserQuoteSettings:
        """Cập nhật settings của user"""
        try:
            # Kiểm tra xem user đã có settings chưa
            existing_settings = await self.get_user_settings(user_id)

            if not existing_settings:
                # Tạo mới nếu chưa có
                new_settings = UserQuoteSettings(
                    user_id=user_id,
                    company_info=update_request.company_info,
                    quote_notes=update_request.quote_notes or QuoteNotes(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                result = await self.collection.insert_one(
                    new_settings.dict(by_alias=True, exclude={"id"})
                )
                new_settings.id = str(result.inserted_id)

                logger.info(f"Created new settings for user {user_id}")
                return new_settings
            else:
                # Cập nhật existing settings
                update_data = {
                    "company_info": update_request.company_info.dict(),
                    "updated_at": datetime.now(),
                }

                if update_request.quote_notes:
                    update_data["quote_notes"] = update_request.quote_notes.dict()

                await self.collection.update_one(
                    {"user_id": user_id}, {"$set": update_data}
                )

                # Lấy lại settings đã cập nhật
                updated_settings = await self.get_user_settings(user_id)
                logger.info(f"Updated settings for user {user_id}")

                return updated_settings

        except Exception as e:
            logger.error(f"Error updating user settings: {str(e)}")
            raise Exception(f"Lỗi khi cập nhật cài đặt: {str(e)}")

    async def get_or_create_user_settings(self, user_id: str) -> UserQuoteSettings:
        """Lấy settings của user, tạo mặc định nếu chưa có"""
        try:
            settings = await self.get_user_settings(user_id)

            if not settings:
                settings = await self.create_default_settings(user_id)

            return settings

        except Exception as e:
            logger.error(f"Error getting or creating user settings: {str(e)}")
            raise Exception(f"Lỗi khi lấy hoặc tạo cài đặt người dùng: {str(e)}")

    async def delete_user_settings(self, user_id: str) -> bool:
        """Xóa settings của user"""
        try:
            result = await self.collection.delete_one({"user_id": user_id})

            if result.deleted_count > 0:
                logger.info(f"Deleted settings for user {user_id}")
                return True
            else:
                logger.warning(f"No settings found to delete for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting user settings: {str(e)}")
            raise Exception(f"Lỗi khi xóa cài đặt người dùng: {str(e)}")
