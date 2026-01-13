"""
StudyHub Content Manager
Handles linking Documents, Tests, Books, Files to StudyHub modules
"""

from typing import Optional, List, Dict, Any
from bson import ObjectId
from fastapi import HTTPException
from datetime import datetime, timezone

from src.database.db_manager import DBManager
from src.services.studyhub_permissions import StudyHubPermissions


class StudyHubContentManager:
    """Manager for StudyHub content operations"""

    def __init__(self, db=None, user_id: Optional[str] = None):
        self.db_manager = DBManager()
        self.db = db or self.db_manager.db
        self.user_id = user_id
        self.permissions = StudyHubPermissions()

    # ==================== DOCUMENT CONTENT ====================

    async def add_document_to_module(
        self,
        module_id: str,
        document_id: str,
        title: str,
        is_required: bool = False,
        is_preview: bool = False,
    ) -> dict:
        """
        Link document to module

        Args:
            module_id: Module ID
            document_id: Document ID from documents collection
            title: Content title
            is_required: Required for completion
            is_preview: Free preview content

        Returns:
            Created content document
        """
        # Check permission
        await self.permissions.check_module_owner(self.user_id, module_id)

        # Verify document exists and user owns it
        # Documents use document_id (string) and user_id (owner field)
        document = self.db.documents.find_one(
            {"document_id": document_id, "user_id": self.user_id}
        )

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have permission",
            )

        # Get module to get subject_id
        module = self.db.studyhub_modules.find_one({"_id": ObjectId(module_id)})

        # Get next order_index
        last_content = self.db.studyhub_module_contents.find_one(
            {"module_id": ObjectId(module_id)}, sort=[("order_index", -1)]
        )
        order_index = (last_content["order_index"] + 1) if last_content else 1

        # Create content record
        content_doc = {
            "module_id": ObjectId(module_id),
            "content_type": "document",
            "title": title,
            "data": {"document_id": document_id, "document_url": document.get("url")},
            "is_required": is_required,
            "is_preview": is_preview,
            "order_index": order_index,
            "created_at": datetime.now(timezone.utc),
        }

        result = self.db.studyhub_module_contents.insert_one(content_doc)
        content_doc["_id"] = result.inserted_id

        # Update studyhub_context in original document
        await self.permissions.update_content_studyhub_context(
            collection_name="documents",
            content_id=document_id,
            subject_id=str(module["subject_id"]),
            module_id=module_id,
            enabled=True,
            is_preview=is_preview,
        )

        return content_doc

    async def get_module_documents(self, module_id: str) -> List[dict]:
        """
        Get all documents in module

        Args:
            module_id: Module ID

        Returns:
            List of document contents
        """
        contents = list(
            self.db.studyhub_module_contents.find(
                {"module_id": ObjectId(module_id), "content_type": "document"}
            ).sort("order_index", 1)
        )

        # Enrich with document data
        for content in contents:
            doc_id = content["data"].get("document_id")
            if doc_id:
                document = self.db.documents.find_one({"document_id": doc_id})
                if document:
                    content["document_details"] = {
                        "title": document.get("title"),
                        "url": document.get("url"),
                        "type": document.get("type"),
                        "created_at": document.get("created_at"),
                    }

        return contents

    async def update_document_content(
        self,
        content_id: str,
        title: Optional[str] = None,
        is_required: Optional[bool] = None,
        is_preview: Optional[bool] = None,
    ) -> dict:
        """
        Update document content settings

        Args:
            content_id: Content ID
            title: New title
            is_required: Update required flag
            is_preview: Update preview flag

        Returns:
            Updated content
        """
        # Get content
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "document"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Document content not found")

        # Check permission
        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        # Build update
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if is_required is not None:
            update_data["is_required"] = is_required
        if is_preview is not None:
            update_data["is_preview"] = is_preview

        if update_data:
            self.db.studyhub_module_contents.update_one(
                {"_id": ObjectId(content_id)}, {"$set": update_data}
            )

            # Update studyhub_context if preview changed
            if is_preview is not None:
                module = self.db.studyhub_modules.find_one(
                    {"_id": content["module_id"]}
                )
                doc_id = content["data"].get("document_id")
                if doc_id:
                    await self.permissions.update_content_studyhub_context(
                        collection_name="documents",
                        content_id=doc_id,
                        subject_id=str(module["subject_id"]),
                        module_id=str(content["module_id"]),
                        enabled=True,
                        is_preview=is_preview,
                    )

        # Return updated content
        return self.db.studyhub_module_contents.find_one({"_id": ObjectId(content_id)})

    async def remove_document_from_module(self, content_id: str) -> bool:
        """
        Remove document from module (unlink)

        Args:
            content_id: Content ID to remove

        Returns:
            True if successful
        """
        # Get content
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "document"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Document content not found")

        # Check permission
        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        # Remove studyhub_context from original document
        doc_id = content["data"].get("document_id")
        if doc_id:
            await self.permissions.update_content_studyhub_context(
                collection_name="documents",
                content_id=doc_id,
                subject_id="",
                module_id="",
                enabled=False,
            )

        # Delete content record
        self.db.studyhub_module_contents.delete_one({"_id": ObjectId(content_id)})

        return True

    # ==================== TEST CONTENT ====================

    async def add_test_to_module(
        self,
        module_id: str,
        test_id: str,
        title: str,
        passing_score: int = 70,
        is_required: bool = False,
        is_preview: bool = False,
    ) -> dict:
        """
        Link test to module by duplicating to NEW test ID in SAME collection

        Benefits:
        - All 67 existing endpoints work (start, submit, grading, marketplace...)
        - No code duplication needed
        - Data isolation via separate test IDs
        """
        await self.permissions.check_module_owner(self.user_id, module_id)

        # Verify original test exists
        original_test = self.db.online_tests.find_one(
            {"_id": ObjectId(test_id), "creator_id": self.user_id}
        )

        if not original_test:
            raise HTTPException(status_code=404, detail="Test not found")

        module = self.db.studyhub_modules.find_one({"_id": ObjectId(module_id)})

        # Duplicate test in SAME collection with NEW ID
        # Copy ALL fields from original test, add StudyHub markers
        studyhub_test = {
            **original_test,  # Copy everything from original
            # Remove _id to get new one
            "_id": None,
            # StudyHub markers (NEW fields)
            "is_studyhub_copy": True,
            "source_test_id": ObjectId(test_id),
            "studyhub_context": {
                "subject_id": module["subject_id"],
                "module_id": ObjectId(module_id),
                "passing_score": passing_score,
                "is_required": is_required,
                "is_preview": is_preview,
            },
            # Allow custom title for StudyHub
            "title": title,
            # Reset timestamps
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Remove _id key (MongoDB will generate new one)
        studyhub_test.pop("_id", None)

        # Remove fields that should NOT be copied
        studyhub_test.pop("marketplace_config", None)  # Not for marketplace
        studyhub_test.pop("migration_metadata", None)  # Not needed

        # Insert duplicate into SAME collection (online_tests)
        result = self.db.online_tests.insert_one(studyhub_test)
        studyhub_test_id = result.inserted_id

        # Get next order_index
        last_content = self.db.studyhub_module_contents.find_one(
            {"module_id": ObjectId(module_id)}, sort=[("order_index", -1)]
        )
        order_index = (last_content["order_index"] + 1) if last_content else 1

        # Link NEW test ID to module
        content_doc = {
            "module_id": ObjectId(module_id),
            "content_type": "test",
            "title": title,
            "data": {
                "test_id": str(studyhub_test_id),  # NEW test ID
                "source_test_id": test_id,  # Original test reference
                "passing_score": passing_score,
            },
            "is_required": is_required,
            "is_preview": is_preview,
            "order_index": order_index,
            "created_at": datetime.now(timezone.utc),
        }

        result = self.db.studyhub_module_contents.insert_one(content_doc)
        content_doc["_id"] = result.inserted_id

        return content_doc

    async def get_module_tests(self, module_id: str) -> List[dict]:
        """Get all tests in module"""
        contents = list(
            self.db.studyhub_module_contents.find(
                {"module_id": ObjectId(module_id), "content_type": "test"}
            ).sort("order_index", 1)
        )

        # Enrich with test data
        for content in contents:
            test_id = content["data"].get("test_id")
            if test_id:
                test = self.db.online_tests.find_one({"_id": ObjectId(test_id)})
                if test:
                    content["test_details"] = {
                        "title": test.get("title"),
                        "total_questions": len(test.get("questions", [])),
                        "time_limit": test.get("time_limit"),
                        "created_at": test.get("created_at"),
                    }

        return contents

    async def update_test_content(
        self,
        content_id: str,
        title: Optional[str] = None,
        passing_score: Optional[int] = None,
        is_required: Optional[bool] = None,
        is_preview: Optional[bool] = None,
    ) -> dict:
        """Update test content settings"""
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "test"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Test content not found")

        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        update_data = {}
        if title is not None:
            update_data["title"] = title
        if is_required is not None:
            update_data["is_required"] = is_required
        if is_preview is not None:
            update_data["is_preview"] = is_preview
        if passing_score is not None:
            update_data["data.passing_score"] = passing_score

        if update_data:
            self.db.studyhub_module_contents.update_one(
                {"_id": ObjectId(content_id)}, {"$set": update_data}
            )

            if is_preview is not None:
                module = self.db.studyhub_modules.find_one(
                    {"_id": content["module_id"]}
                )
                test_id = content["data"].get("test_id")
                if test_id:
                    await self.permissions.update_content_studyhub_context(
                        collection_name="online_tests",
                        content_id=test_id,
                        subject_id=str(module["subject_id"]),
                        module_id=str(content["module_id"]),
                        enabled=True,
                        is_preview=is_preview,
                    )

        return self.db.studyhub_module_contents.find_one({"_id": ObjectId(content_id)})

    async def remove_test_from_module(self, content_id: str) -> bool:
        """Remove test from module"""
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "test"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Test content not found")

        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        test_id = content["data"].get("test_id")
        if test_id:
            await self.permissions.update_content_studyhub_context(
                collection_name="online_tests",
                content_id=test_id,
                subject_id="",
                module_id="",
                enabled=False,
            )

        self.db.studyhub_module_contents.delete_one({"_id": ObjectId(content_id)})
        return True

    # ==================== BOOK CONTENT ====================

    async def add_book_to_module(
        self,
        module_id: str,
        book_id: str,
        title: str,
        selected_chapters: Optional[List[str]] = None,
        is_required: bool = False,
        is_preview: bool = False,
    ) -> dict:
        """Link book to module"""
        await self.permissions.check_module_owner(self.user_id, module_id)

        book = self.db.online_books.find_one(
            {"book_id": book_id, "user_id": self.user_id}
        )

        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        module = self.db.studyhub_modules.find_one({"_id": ObjectId(module_id)})

        last_content = self.db.studyhub_module_contents.find_one(
            {"module_id": ObjectId(module_id)}, sort=[("order_index", -1)]
        )
        order_index = (last_content["order_index"] + 1) if last_content else 1

        content_doc = {
            "module_id": ObjectId(module_id),
            "content_type": "book",
            "title": title,
            "data": {
                "book_id": book_id,
                "selected_chapters": selected_chapters or [],
            },
            "is_required": is_required,
            "is_preview": is_preview,
            "order_index": order_index,
            "created_at": datetime.now(timezone.utc),
        }

        result = self.db.studyhub_module_contents.insert_one(content_doc)
        content_doc["_id"] = result.inserted_id

        await self.permissions.update_content_studyhub_context(
            collection_name="online_books",
            content_id=book_id,
            subject_id=str(module["subject_id"]),
            module_id=module_id,
            enabled=True,
            is_preview=is_preview,
        )

        return content_doc

    async def get_module_books(self, module_id: str) -> List[dict]:
        """Get all books in module"""
        contents = list(
            self.db.studyhub_module_contents.find(
                {"module_id": ObjectId(module_id), "content_type": "book"}
            ).sort("order_index", 1)
        )

        for content in contents:
            book_id = content["data"].get("book_id")
            if book_id:
                book = self.db.online_books.find_one({"_id": ObjectId(book_id)})
                if book:
                    content["book_details"] = {
                        "title": book.get("title"),
                        "total_chapters": len(book.get("chapters", [])),
                        "cover_url": book.get("cover_url"),
                        "created_at": book.get("created_at"),
                    }

        return contents

    async def update_book_content(
        self,
        content_id: str,
        title: Optional[str] = None,
        selected_chapters: Optional[List[str]] = None,
        is_required: Optional[bool] = None,
        is_preview: Optional[bool] = None,
    ) -> dict:
        """Update book content settings"""
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "book"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Book content not found")

        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        update_data = {}
        if title is not None:
            update_data["title"] = title
        if is_required is not None:
            update_data["is_required"] = is_required
        if is_preview is not None:
            update_data["is_preview"] = is_preview
        if selected_chapters is not None:
            update_data["data.selected_chapters"] = selected_chapters

        if update_data:
            self.db.studyhub_module_contents.update_one(
                {"_id": ObjectId(content_id)}, {"$set": update_data}
            )

            if is_preview is not None:
                module = self.db.studyhub_modules.find_one(
                    {"_id": content["module_id"]}
                )
                book_id = content["data"].get("book_id")
                if book_id:
                    await self.permissions.update_content_studyhub_context(
                        collection_name="online_books",
                        content_id=book_id,
                        subject_id=str(module["subject_id"]),
                        module_id=str(content["module_id"]),
                        enabled=True,
                        is_preview=is_preview,
                    )

        return self.db.studyhub_module_contents.find_one({"_id": ObjectId(content_id)})

    async def remove_book_from_module(self, content_id: str) -> bool:
        """Remove book from module"""
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "book"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Book content not found")

        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        book_id = content["data"].get("book_id")
        if book_id:
            await self.permissions.update_content_studyhub_context(
                collection_name="online_books",
                content_id=book_id,
                subject_id="",
                module_id="",
                enabled=False,
            )

        self.db.studyhub_module_contents.delete_one({"_id": ObjectId(content_id)})
        return True

    # ==================== FILE CONTENT ====================

    async def link_existing_file_to_module(
        self,
        module_id: str,
        file_id: str,
        title: str,
        is_required: bool = False,
        is_preview: bool = False,
    ) -> dict:
        """
        Link existing file to module

        Args:
            module_id: Module ID
            file_id: File ID from library_files
            title: Content title
            is_required: Required for completion
            is_preview: Free preview content

        Returns:
            Created content document
        """
        # Check permission
        await self.permissions.check_module_owner(self.user_id, module_id)

        # Verify file exists and user uploaded it
        # Library files use file_id (string like 'lib_xxx') and user_id
        file_doc = self.db.library_files.find_one(
            {
                "file_id": file_id,
                "user_id": self.user_id,
                "deleted": {"$ne": True},
            }
        )

        if not file_doc:
            raise HTTPException(
                status_code=404,
                detail="File not found or you don't have permission",
            )

        # Check if file already linked to this module
        existing = self.db.studyhub_module_contents.find_one(
            {
                "module_id": ObjectId(module_id),
                "content_type": "file",
                "data.file_id": file_id,
            }
        )

        if existing:
            raise HTTPException(
                status_code=409, detail="File already linked to this module"
            )

        # Get module to get subject_id
        module = self.db.studyhub_modules.find_one({"_id": ObjectId(module_id)})

        # Get next order_index
        last_content = self.db.studyhub_module_contents.find_one(
            {"module_id": ObjectId(module_id)}, sort=[("order_index", -1)]
        )
        order_index = (last_content["order_index"] + 1) if last_content else 1

        # Create content record
        content_doc = {
            "module_id": ObjectId(module_id),
            "content_type": "file",
            "title": title,
            "data": {
                "file_id": file_id,
                "file_url": file_doc.get("file_url"),
                "file_name": file_doc.get("file_name"),
                "file_type": file_doc.get("file_type"),
                "file_size": file_doc.get("file_size"),
            },
            "is_required": is_required,
            "is_preview": is_preview,
            "order_index": order_index,
            "created_at": datetime.now(timezone.utc),
        }

        result = self.db.studyhub_module_contents.insert_one(content_doc)
        content_doc["_id"] = result.inserted_id

        # Update studyhub_context in file
        await self.permissions.update_content_studyhub_context(
            collection_name="library_files",
            content_id=file_id,
            subject_id=str(module["subject_id"]),
            module_id=module_id,
            enabled=True,
            is_preview=is_preview,
        )

        return content_doc

    async def get_module_files(self, module_id: str) -> List[dict]:
        """
        Get all files in module

        Args:
            module_id: Module ID

        Returns:
            List of file contents with details
        """
        # Check permission (owner or enrolled)
        await self.permissions.check_content_access(self.user_id, module_id)

        # Get all file contents
        contents = list(
            self.db.studyhub_module_contents.find(
                {"module_id": ObjectId(module_id), "content_type": "file"}
            ).sort("order_index", 1)
        )

        # Enrich with file details
        for content in contents:
            file_id = content["data"].get("file_id")
            if file_id:
                file_doc = self.db.library_files.find_one({"file_id": file_id})
                if file_doc:
                    content["file_details"] = {
                        "uploaded_at": file_doc.get("uploaded_at"),
                        "uploaded_by": file_doc.get("user_id"),
                        "download_count": file_doc.get("download_count", 0),
                        "duration": file_doc.get("duration"),  # for videos
                        "thumbnail_url": file_doc.get("thumbnail_url"),
                    }

        return contents

    async def remove_file_from_module(self, content_id: str) -> bool:
        """Remove file from module (soft delete)"""
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id), "content_type": "file"}
        )

        if not content:
            raise HTTPException(status_code=404, detail="File content not found")

        await self.permissions.check_module_owner(
            self.user_id, str(content["module_id"])
        )

        file_id = content["data"].get("file_id")
        if file_id:
            # Update studyhub_context
            await self.permissions.update_content_studyhub_context(
                collection_name="library_files",
                content_id=file_id,
                subject_id="",
                module_id="",
                enabled=False,
            )

            # Mark file as deleted (soft delete)
            self.db.library_files.update_one(
                {"file_id": file_id},
                {
                    "$set": {
                        "deleted": True,
                        "deleted_at": datetime.now(timezone.utc),
                    }
                },
            )

        self.db.studyhub_module_contents.delete_one({"_id": ObjectId(content_id)})
        return True
