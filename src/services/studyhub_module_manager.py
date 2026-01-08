"""
StudyHub Module Manager Service
Business logic for module and content management
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId

from src.models.studyhub_models import (
    ModuleResponse,
    ModuleContentResponse,
    ContentType,
)

logger = logging.getLogger("chatbot")


class StudyHubModuleManager:
    """Manager for StudyHub module and content operations"""
    
    def __init__(self, db, user_id: Optional[str] = None):
        """
        Initialize manager
        
        Args:
            db: MongoDB database instance
            user_id: Current user ID (optional for public access)
        """
        self.db = db
        self.user_id = user_id
        self.subjects = db["studyhub_subjects"]
        self.modules = db["studyhub_modules"]
        self.contents = db["studyhub_module_contents"]
        self.enrollments = db["studyhub_enrollments"]
    
    def _to_object_id(self, id_str: str) -> ObjectId:
        """Convert string to ObjectId"""
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {id_str}")
    
    def _check_subject_permission(self, subject_id: ObjectId) -> bool:
        """Check if user can modify subject (owner only)"""
        if not self.user_id:
            return False
        
        subject = self.subjects.find_one({"_id": subject_id})
        if not subject:
            return False
        
        return subject["owner_id"] == self.user_id
    
    def _serialize_module(self, module: Dict) -> Dict:
        """Serialize module document to response format"""
        if not module:
            return None
        
        # Count contents
        content_count = self.contents.count_documents({"module_id": module["_id"]})
        
        return {
            "_id": str(module["_id"]),
            "subject_id": str(module["subject_id"]),
            "title": module["title"],
            "description": module.get("description"),
            "order_index": module["order_index"],
            "content_count": content_count,
            "created_at": module["created_at"],
            "updated_at": module["updated_at"],
        }
    
    def _serialize_content(self, content: Dict) -> Dict:
        """Serialize content document to response format"""
        if not content:
            return None
        
        return {
            "_id": str(content["_id"]),
            "module_id": str(content["module_id"]),
            "content_type": content["content_type"],
            "title": content["title"],
            "order_index": content["order_index"],
            "data": content["data"],
            "is_required": content.get("is_required", False),
            "created_at": content["created_at"],
            "reference_data": content.get("reference_data"),
        }
    
    async def create_module(
        self,
        subject_id: str,
        title: str,
        description: Optional[str] = None,
    ) -> Optional[ModuleResponse]:
        """
        Create a new module in subject
        
        Args:
            subject_id: Subject ID
            title: Module title
            description: Module description
            
        Returns:
            ModuleResponse or None if no permission
        """
        subject_oid = self._to_object_id(subject_id)
        
        # Check permission
        if not self._check_subject_permission(subject_oid):
            return None
        
        # Get max order_index
        last_module = self.modules.find_one(
            {"subject_id": subject_oid},
            sort=[("order_index", -1)]
        )
        order_index = (last_module["order_index"] + 1) if last_module else 0
        
        now = datetime.now(timezone.utc)
        
        module_doc = {
            "subject_id": subject_oid,
            "title": title,
            "description": description,
            "order_index": order_index,
            "created_at": now,
            "updated_at": now,
        }
        
        result = self.modules.insert_one(module_doc)
        module_doc["_id"] = result.inserted_id
        
        # Update subject metadata
        self.subjects.update_one(
            {"_id": subject_oid},
            {
                "$inc": {"metadata.total_modules": 1},
                "$set": {"updated_at": now}
            }
        )
        
        logger.info(f"Created module {result.inserted_id} in subject {subject_id}")
        
        return ModuleResponse(**self._serialize_module(module_doc))
    
    async def get_modules(self, subject_id: str) -> List[ModuleResponse]:
        """
        Get all modules in subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            List of ModuleResponse
        """
        subject_oid = self._to_object_id(subject_id)
        
        # Check if subject exists and user can access
        subject = self.subjects.find_one({"_id": subject_oid})
        if not subject:
            return []
        
        # Check access permission
        if subject["visibility"] == "private":
            if not self.user_id:
                return []
            if subject["owner_id"] != self.user_id:
                # Check enrollment
                enrollment = self.enrollments.find_one({
                    "subject_id": subject_oid,
                    "user_id": self.user_id,
                    "status": {"$ne": "dropped"}
                })
                if not enrollment:
                    return []
        
        # Get modules sorted by order_index
        modules = list(self.modules.find({"subject_id": subject_oid})
                      .sort("order_index", 1))
        
        return [ModuleResponse(**self._serialize_module(m)) for m in modules]
    
    async def update_module(
        self,
        module_id: str,
        updates: Dict[str, Any],
    ) -> Optional[ModuleResponse]:
        """
        Update module
        
        Args:
            module_id: Module ID
            updates: Fields to update
            
        Returns:
            Updated ModuleResponse or None
        """
        module_oid = self._to_object_id(module_id)
        module = self.modules.find_one({"_id": module_oid})
        
        if not module:
            return None
        
        # Check permission
        if not self._check_subject_permission(module["subject_id"]):
            return None
        
        # Prepare updates
        update_data = {k: v for k, v in updates.items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        # Update module
        self.modules.update_one(
            {"_id": module_oid},
            {"$set": update_data}
        )
        
        # Fetch updated module
        updated_module = self.modules.find_one({"_id": module_oid})
        
        logger.info(f"Updated module {module_id}")
        
        return ModuleResponse(**self._serialize_module(updated_module))
    
    async def delete_module(self, module_id: str) -> bool:
        """
        Delete module and all its contents
        
        Args:
            module_id: Module ID
            
        Returns:
            True if deleted, False otherwise
        """
        module_oid = self._to_object_id(module_id)
        module = self.modules.find_one({"_id": module_oid})
        
        if not module:
            return False
        
        # Check permission
        if not self._check_subject_permission(module["subject_id"]):
            return False
        
        # Delete all contents
        self.contents.delete_many({"module_id": module_oid})
        
        # Delete module
        self.modules.delete_one({"_id": module_oid})
        
        # Re-index remaining modules
        remaining_modules = list(self.modules.find(
            {"subject_id": module["subject_id"]}
        ).sort("order_index", 1))
        
        for idx, mod in enumerate(remaining_modules):
            self.modules.update_one(
                {"_id": mod["_id"]},
                {"$set": {"order_index": idx}}
            )
        
        # Update subject metadata
        self.subjects.update_one(
            {"_id": module["subject_id"]},
            {
                "$inc": {"metadata.total_modules": -1},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        logger.info(f"Deleted module {module_id} and re-indexed {len(remaining_modules)} modules")
        
        return True
    
    async def reorder_module(
        self,
        module_id: str,
        new_order_index: int,
    ) -> Optional[List[ModuleResponse]]:
        """
        Reorder module position
        
        Args:
            module_id: Module ID
            new_order_index: New position (0-based)
            
        Returns:
            Updated list of modules or None
        """
        module_oid = self._to_object_id(module_id)
        module = self.modules.find_one({"_id": module_oid})
        
        if not module:
            return None
        
        # Check permission
        if not self._check_subject_permission(module["subject_id"]):
            return None
        
        old_index = module["order_index"]
        
        if old_index == new_order_index:
            # No change needed
            return await self.get_modules(str(module["subject_id"]))
        
        # Get all modules in subject
        all_modules = list(self.modules.find(
            {"subject_id": module["subject_id"]}
        ).sort("order_index", 1))
        
        # Validate new_order_index
        if new_order_index < 0 or new_order_index >= len(all_modules):
            raise ValueError(f"Invalid order_index: {new_order_index}")
        
        # Remove from old position
        all_modules.pop(old_index)
        # Insert at new position
        all_modules.insert(new_order_index, module)
        
        # Update all order_index values
        for idx, mod in enumerate(all_modules):
            self.modules.update_one(
                {"_id": mod["_id"]},
                {"$set": {"order_index": idx, "updated_at": datetime.now(timezone.utc)}}
            )
        
        logger.info(f"Reordered module {module_id} from {old_index} to {new_order_index}")
        
        return await self.get_modules(str(module["subject_id"]))
    
    async def add_content(
        self,
        module_id: str,
        content_type: str,
        title: str,
        data: Dict[str, Any],
        is_required: bool = False,
    ) -> Optional[ModuleContentResponse]:
        """
        Add content to module
        
        Args:
            module_id: Module ID
            content_type: Type of content
            title: Content title
            data: Content-specific data
            is_required: Is content required for completion
            
        Returns:
            ModuleContentResponse or None
        """
        module_oid = self._to_object_id(module_id)
        module = self.modules.find_one({"_id": module_oid})
        
        if not module:
            return None
        
        # Check permission
        if not self._check_subject_permission(module["subject_id"]):
            return None
        
        # Get max order_index
        last_content = self.contents.find_one(
            {"module_id": module_oid},
            sort=[("order_index", -1)]
        )
        order_index = (last_content["order_index"] + 1) if last_content else 0
        
        now = datetime.now(timezone.utc)
        
        content_doc = {
            "module_id": module_oid,
            "content_type": content_type,
            "title": title,
            "order_index": order_index,
            "data": data,
            "is_required": is_required,
            "created_at": now,
        }
        
        result = self.contents.insert_one(content_doc)
        content_doc["_id"] = result.inserted_id
        
        # Update module
        self.modules.update_one(
            {"_id": module_oid},
            {"$set": {"updated_at": now}}
        )
        
        logger.info(f"Added content {result.inserted_id} to module {module_id}")
        
        return ModuleContentResponse(**self._serialize_content(content_doc))
    
    async def get_contents(self, module_id: str) -> List[ModuleContentResponse]:
        """
        Get all contents in module
        
        Args:
            module_id: Module ID
            
        Returns:
            List of ModuleContentResponse
        """
        module_oid = self._to_object_id(module_id)
        module = self.modules.find_one({"_id": module_oid})
        
        if not module:
            return []
        
        # Check access permission
        subject = self.subjects.find_one({"_id": module["subject_id"]})
        if subject and subject["visibility"] == "private":
            if not self.user_id:
                return []
            if subject["owner_id"] != self.user_id:
                # Check enrollment
                enrollment = self.enrollments.find_one({
                    "subject_id": module["subject_id"],
                    "user_id": self.user_id,
                    "status": {"$ne": "dropped"}
                })
                if not enrollment:
                    return []
        
        # Get contents sorted by order_index
        contents = list(self.contents.find({"module_id": module_oid})
                       .sort("order_index", 1))
        
        return [ModuleContentResponse(**self._serialize_content(c)) for c in contents]
    
    async def delete_content(self, module_id: str, content_id: str) -> bool:
        """
        Delete content from module
        
        Args:
            module_id: Module ID
            content_id: Content ID
            
        Returns:
            True if deleted, False otherwise
        """
        module_oid = self._to_object_id(module_id)
        content_oid = self._to_object_id(content_id)
        
        module = self.modules.find_one({"_id": module_oid})
        if not module:
            return False
        
        # Check permission
        if not self._check_subject_permission(module["subject_id"]):
            return False
        
        content = self.contents.find_one({
            "_id": content_oid,
            "module_id": module_oid
        })
        
        if not content:
            return False
        
        # Delete content
        self.contents.delete_one({"_id": content_oid})
        
        # Re-index remaining contents
        remaining_contents = list(self.contents.find(
            {"module_id": module_oid}
        ).sort("order_index", 1))
        
        for idx, cnt in enumerate(remaining_contents):
            self.contents.update_one(
                {"_id": cnt["_id"]},
                {"$set": {"order_index": idx}}
            )
        
        # Update module
        self.modules.update_one(
            {"_id": module_oid},
            {"$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        
        logger.info(f"Deleted content {content_id} and re-indexed {len(remaining_contents)} contents")
        
        return True
