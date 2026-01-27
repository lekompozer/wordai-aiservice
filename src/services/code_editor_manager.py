"""
Code Editor Manager
Service layer for managing code files, folders, templates
"""

import logging
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from fastapi import HTTPException

from src.database.db_manager import DBManager
from src.models.code_editor_models import (
    CodeLanguage,
    FileSortBy,
    SortOrder,
    FileMetadata,
    ExerciseDifficulty,
)

logger = logging.getLogger(__name__)


class CodeEditorManager:
    """Manager for Code Editor operations"""

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

    # ==================== FILE MANAGEMENT ====================

    async def create_file(
        self,
        user_id: str,
        name: str,
        language: str,
        code: str,
        folder_id: Optional[str] = None,
        tags: List[str] = None,
        is_public: bool = False,
        description: Optional[str] = None,
    ) -> dict:
        """Create or update a code file"""
        now = datetime.now(timezone.utc)

        # Validate syntax
        await self._validate_code_syntax(code, language)

        # Calculate metadata
        size_bytes = len(code.encode("utf-8"))
        lines_of_code = len(code.split("\n"))

        # Check storage quota
        await self._check_storage_quota(user_id, size_bytes)

        # Prepare file document
        file_doc = {
            "user_id": user_id,
            "name": name,
            "language": language,
            "code": code,
            "folder_id": ObjectId(folder_id) if folder_id else None,
            "tags": tags or [],
            "is_public": is_public,
            "description": description,
            "metadata": {
                "size_bytes": size_bytes,
                "run_count": 0,
                "last_run_at": None,
                "lines_of_code": lines_of_code,
            },
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }

        result = self.db.code_files.insert_one(file_doc)
        file_doc["_id"] = result.inserted_id

        logger.info(f"✅ Created file '{name}' for user {user_id}, language={language}")

        return self._format_file_response(file_doc)

    async def get_user_files(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "updated_at",
        order: str = "desc",
    ) -> dict:
        """Get user's code files with filters"""
        # Build query
        query = {"user_id": user_id, "deleted_at": None}

        if folder_id:
            query["folder_id"] = ObjectId(folder_id) if folder_id != "root" else None

        if language:
            query["language"] = language

        if tags:
            query["tags"] = {"$in": tags}

        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Count total
        total_items = self.db.code_files.count_documents(query)

        # Pagination
        skip = (page - 1) * limit
        total_pages = (total_items + limit - 1) // limit

        # Sort
        sort_direction = 1 if order == "asc" else -1
        sort_field = sort_by

        # Fetch files
        files_cursor = (
            self.db.code_files.find(query)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        files = []
        for file_doc in files_cursor:
            files.append(self._format_file_list_item(file_doc))

        return {
            "success": True,
            "files": files,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total_items,
                "items_per_page": limit,
            },
        }

    async def get_file_by_id(self, file_id: str, user_id: str) -> dict:
        """Get file by ID"""
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "deleted_at": None}
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Check access
        if file_doc["user_id"] != user_id and not file_doc.get("is_public", False):
            raise HTTPException(
                status_code=403, detail="You don't have permission to view this file"
            )

        return {"success": True, "file": self._format_file_response(file_doc)}

    async def update_file(
        self,
        file_id: str,
        user_id: str,
        name: Optional[str] = None,
        code: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Update file"""
        # Check ownership
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "user_id": user_id, "deleted_at": None}
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Build update
        update_fields = {"updated_at": datetime.now(timezone.utc)}

        if name is not None:
            update_fields["name"] = name

        if code is not None:
            # Validate syntax
            await self._validate_code_syntax(code, file_doc["language"])

            update_fields["code"] = code
            update_fields["metadata.size_bytes"] = len(code.encode("utf-8"))
            update_fields["metadata.lines_of_code"] = len(code.split("\n"))

        if folder_id is not None:
            update_fields["folder_id"] = ObjectId(folder_id) if folder_id else None

        if tags is not None:
            update_fields["tags"] = tags

        if is_public is not None:
            update_fields["is_public"] = is_public

        if description is not None:
            update_fields["description"] = description

        # Update
        self.db.code_files.update_one(
            {"_id": ObjectId(file_id)}, {"$set": update_fields}
        )

        # Fetch updated file
        updated_file = self.db.code_files.find_one({"_id": ObjectId(file_id)})

        logger.info(f"✅ Updated file {file_id}")

        return {"success": True, "file": self._format_file_response(updated_file)}

    async def delete_file(self, file_id: str, user_id: str) -> dict:
        """Soft delete file"""
        # Check ownership
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "user_id": user_id, "deleted_at": None}
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Soft delete
        deleted_at = datetime.now(timezone.utc)
        self.db.code_files.update_one(
            {"_id": ObjectId(file_id)}, {"$set": {"deleted_at": deleted_at}}
        )

        logger.info(f"✅ Deleted file {file_id}")

        return {
            "success": True,
            "message": "File moved to trash",
            "file_id": file_id,
            "deleted_at": deleted_at,
        }

    async def increment_run_count(self, file_id: str, user_id: str) -> dict:
        """Increment file run count"""
        # Check file exists and user has access
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "deleted_at": None}
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Check access
        if file_doc["user_id"] != user_id and not file_doc.get("is_public", False):
            raise HTTPException(
                status_code=403, detail="You don't have permission to run this file"
            )

        # Increment
        now = datetime.now(timezone.utc)
        result = self.db.code_files.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$inc": {"metadata.run_count": 1},
                "$set": {"metadata.last_run_at": now},
            },
        )

        # Get updated count
        updated_file = self.db.code_files.find_one({"_id": ObjectId(file_id)})
        run_count = updated_file["metadata"]["run_count"]

        return {"success": True, "run_count": run_count}

    async def duplicate_file(self, file_id: str, user_id: str) -> dict:
        """Clone/duplicate a file"""
        # Get original file
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "deleted_at": None}
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Check access
        if file_doc["user_id"] != user_id and not file_doc.get("is_public", False):
            raise HTTPException(
                status_code=403, detail="You don't have permission to clone this file"
            )

        # Create duplicate
        new_name = f"{file_doc['name'].rsplit('.', 1)[0]}_copy.{file_doc['name'].rsplit('.', 1)[1]}"

        return await self.create_file(
            user_id=user_id,
            name=new_name,
            language=file_doc["language"],
            code=file_doc["code"],
            folder_id=str(file_doc["folder_id"]) if file_doc.get("folder_id") else None,
            tags=file_doc.get("tags", []),
            is_public=False,  # Duplicates are always private
            description=file_doc.get("description"),
        )

    # ==================== FOLDER MANAGEMENT ====================

    async def create_folder(
        self,
        user_id: str,
        name: str,
        parent_id: Optional[str] = None,
        color: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> dict:
        """Create a folder"""
        now = datetime.now(timezone.utc)

        folder_doc = {
            "user_id": user_id,
            "name": name,
            "parent_id": ObjectId(parent_id) if parent_id else None,
            "color": color,
            "language_filter": language_filter,
            "file_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        result = self.db.code_folders.insert_one(folder_doc)
        folder_doc["_id"] = result.inserted_id

        logger.info(f"✅ Created folder '{name}' for user {user_id}")

        return {"success": True, "folder": self._format_folder_response(folder_doc)}

    async def get_user_folders(self, user_id: str) -> dict:
        """Get user's folders"""
        folders_cursor = self.db.code_folders.find({"user_id": user_id}).sort(
            "created_at", -1
        )

        folders = []
        for folder_doc in folders_cursor:
            # Count files in folder
            file_count = self.db.code_files.count_documents(
                {"folder_id": folder_doc["_id"], "deleted_at": None}
            )
            folder_doc["file_count"] = file_count

            folders.append(self._format_folder_response(folder_doc))

        return {"success": True, "folders": folders}

    async def update_folder(
        self,
        folder_id: str,
        user_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> dict:
        """Update folder"""
        # Check ownership
        folder_doc = self.db.code_folders.find_one(
            {"_id": ObjectId(folder_id), "user_id": user_id}
        )

        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Build update
        update_fields = {"updated_at": datetime.now(timezone.utc)}

        if name is not None:
            update_fields["name"] = name
        if color is not None:
            update_fields["color"] = color
        if language_filter is not None:
            update_fields["language_filter"] = language_filter

        # Update
        self.db.code_folders.update_one(
            {"_id": ObjectId(folder_id)}, {"$set": update_fields}
        )

        # Fetch updated folder
        updated_folder = self.db.code_folders.find_one({"_id": ObjectId(folder_id)})

        logger.info(f"✅ Updated folder {folder_id}")

        return {"success": True, "folder": self._format_folder_response(updated_folder)}

    async def delete_folder(
        self, folder_id: str, user_id: str, delete_files: bool = False
    ) -> dict:
        """Delete folder and optionally its files"""
        # Check ownership
        folder_doc = self.db.code_folders.find_one(
            {"_id": ObjectId(folder_id), "user_id": user_id}
        )

        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        if delete_files:
            # Delete all files in folder
            now = datetime.now(timezone.utc)
            self.db.code_files.update_many(
                {"folder_id": ObjectId(folder_id)}, {"$set": {"deleted_at": now}}
            )
            files_moved = 0
        else:
            # Move files to root
            result = self.db.code_files.update_many(
                {"folder_id": ObjectId(folder_id)}, {"$set": {"folder_id": None}}
            )
            files_moved = result.modified_count

        # Delete folder
        self.db.code_folders.delete_one({"_id": ObjectId(folder_id)})

        logger.info(f"✅ Deleted folder {folder_id}, files_moved={files_moved}")

        return {
            "success": True,
            "message": "Folder deleted",
            "files_moved_to_root": files_moved,
        }

    # ==================== VALIDATION ====================

    async def _validate_code_syntax(self, code: str, language: str) -> None:
        """Validate code syntax"""
        if language == "python":
            try:
                compile(code, "<string>", "exec")
            except SyntaxError as e:
                raise HTTPException(status_code=400, detail=f"Python syntax error: {e}")
        # JavaScript, HTML, CSS validation can be added here
        # For now, just basic checks

    async def _check_storage_quota(self, user_id: str, new_file_size: int) -> None:
        """Check if user has enough storage quota"""
        # Calculate current usage
        pipeline = [
            {"$match": {"user_id": user_id, "deleted_at": None}},
            {"$group": {"_id": None, "total_size": {"$sum": "$metadata.size_bytes"}}},
        ]
        result = list(self.db.code_files.aggregate(pipeline))
        current_usage = result[0]["total_size"] if result else 0

        # Storage limit: 10MB
        storage_limit = 10 * 1024 * 1024  # 10MB

        if current_usage + new_file_size > storage_limit:
            raise HTTPException(
                status_code=413,
                detail=f"Storage quota exceeded. Current: {current_usage}, Limit: {storage_limit}",
            )

    # ==================== RESPONSE FORMATTING ====================

    def _format_file_response(self, file_doc: dict) -> dict:
        """Format file document for response"""
        return {
            "id": str(file_doc["_id"]),
            "user_id": file_doc["user_id"],
            "name": file_doc["name"],
            "language": file_doc["language"],
            "code": file_doc["code"],
            "folder_id": (
                str(file_doc["folder_id"]) if file_doc.get("folder_id") else None
            ),
            "tags": file_doc.get("tags", []),
            "is_public": file_doc.get("is_public", False),
            "description": file_doc.get("description"),
            "metadata": file_doc.get("metadata", {}),
            "created_at": file_doc["created_at"],
            "updated_at": file_doc["updated_at"],
            "share_link": None,  # TODO: Check if file has active share
        }

    def _format_file_list_item(self, file_doc: dict) -> dict:
        """Format file for list view (without code)"""
        metadata = file_doc.get("metadata", {})
        return {
            "id": str(file_doc["_id"]),
            "name": file_doc["name"],
            "language": file_doc["language"],
            "folder_id": (
                str(file_doc["folder_id"]) if file_doc.get("folder_id") else None
            ),
            "tags": file_doc.get("tags", []),
            "is_public": file_doc.get("is_public", False),
            "description": file_doc.get("description"),
            "size_bytes": metadata.get("size_bytes", 0),
            "run_count": metadata.get("run_count", 0),
            "created_at": file_doc["created_at"],
            "updated_at": file_doc["updated_at"],
        }

    def _format_folder_response(self, folder_doc: dict) -> dict:
        """Format folder document for response"""
        return {
            "id": str(folder_doc["_id"]),
            "user_id": folder_doc["user_id"],
            "name": folder_doc["name"],
            "parent_id": (
                str(folder_doc["parent_id"]) if folder_doc.get("parent_id") else None
            ),
            "color": folder_doc.get("color"),
            "language_filter": folder_doc.get("language_filter"),
            "file_count": folder_doc.get("file_count", 0),
            "created_at": folder_doc["created_at"],
            "updated_at": folder_doc["updated_at"],
        }

    # ==================== TEMPLATE LIBRARY ====================

    async def list_templates(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None,
        difficulty: Optional[str] = None,
        search: Optional[str] = None,
        featured: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict:
        """List code templates with filtering"""
        # Support both old schema (is_active) and new schema (is_published)
        query = {"$or": [{"is_active": True}, {"is_published": True}]}

        if category:
            # Support both 'category' (old) and 'topic_id' (new Learning System)
            # Append to existing $or or create new condition
            category_condition = {
                "$or": [{"category": category}, {"topic_id": category}]
            }
            if "$or" in query:
                query = {"$and": [query, category_condition]}
            else:
                query.update(category_condition)

        if language:
            query["programming_language"] = language
        if difficulty:
            query["difficulty"] = difficulty
        if featured is not None:
            query["is_featured"] = featured
        if search:
            search_condition = {
                "$or": [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}},
                    {"tags": {"$in": [search.lower()]}},
                ]
            }
            if "$and" in query:
                query["$and"].append(search_condition)
            else:
                query = {"$and": [query, search_condition]}

        total = self.db.code_templates.count_documents(query)
        templates = list(
            self.db.code_templates.find(query)
            .sort("metadata.usage_count", -1)
            .skip(skip)
            .limit(limit)
        )

        return {
            "success": True,
            "templates": [self._format_template_response(t) for t in templates],
            "pagination": {
                "total": total,
                "skip": skip,
                "limit": limit,
                "has_more": skip + len(templates) < total,
            },
        }

    async def list_categories(self, language: Optional[str] = None) -> dict:
        """List template categories"""
        query = {}
        if language:
            query["language"] = language

        categories = list(self.db.code_template_categories.find(query).sort("order", 1))

        return {
            "success": True,
            "categories": [self._format_category_response(c) for c in categories],
        }

    async def get_template(self, template_id: str) -> dict:
        """Get template details (UUID only)"""
        template = self.db.code_templates.find_one(
            {"id": template_id, "is_published": True}
        )

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "success": True,
            "template": self._format_template_response(template, include_code=True),
        }

    async def use_template(
        self,
        template_id: str,
        user_id: str,
        file_name: str,
        folder_id: Optional[str] = None,
    ) -> dict:
        """Create file from template (UUID only)"""
        template = self.db.code_templates.find_one(
            {"id": template_id, "is_published": True}
        )

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create file from template
        file_result = await self.create_file(
            user_id=user_id,
            name=file_name,
            language=template["programming_language"],
            code=template["code"],
            folder_id=folder_id,
            tags=template.get("tags", []),
            is_public=False,
            description=f"Created from template: {template['title']}",
        )

        # Increment template usage count
        self.db.code_templates.update_one(
            {"id": template_id},
            {"$inc": {"metadata.usage_count": 1}},
        )

        logger.info(
            f"✅ User {user_id} used template '{template['title']}' → file '{file_name}'"
        )

        return {
            "success": True,
            "file": file_result,
        }

    # ==================== SQL GRADING ====================

    async def grade_sql_exercise(
        self,
        exercise_id: str,
        user_id: str,
        code: str,
    ) -> dict:
        """Grade SQL exercise submission"""
        import sqlite3
        import tempfile
        import os

        if not ObjectId.is_valid(exercise_id):
            raise HTTPException(status_code=400, detail="Invalid exercise ID")

        exercise = self.db.code_exercises.find_one({"_id": ObjectId(exercise_id)})

        if not exercise:
            raise HTTPException(status_code=404, detail="Exercise not found")

        if exercise.get("language") != "sql":
            raise HTTPException(
                status_code=400, detail="Exercise is not a SQL exercise"
            )

        # Create temporary SQLite database
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".db", delete=False
        ) as temp_db:
            db_path = temp_db.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Setup test database schema and data
            setup_sql = exercise.get("setup_sql", "")
            if setup_sql:
                cursor.executescript(setup_sql)

            # Run user's SQL
            test_results = []
            total_points = 0
            earned_points = 0

            for test_case in exercise.get("test_cases", []):
                test_number = test_case.get("test_number", 1)
                expected_output = test_case.get("expected_output", "")
                points = test_case.get("points", 1)
                total_points += points

                try:
                    # Execute user code
                    cursor.execute(code)
                    actual_result = cursor.fetchall()

                    # Compare results
                    expected_result = eval(expected_output)  # Parse expected result
                    passed = actual_result == expected_result

                    if passed:
                        earned_points += points

                    test_results.append(
                        {
                            "test_number": test_number,
                            "passed": passed,
                            "expected": str(expected_result),
                            "actual": str(actual_result),
                            "points_earned": points if passed else 0,
                            "error_message": None,
                        }
                    )

                except Exception as e:
                    test_results.append(
                        {
                            "test_number": test_number,
                            "passed": False,
                            "expected": expected_output,
                            "actual": "",
                            "points_earned": 0,
                            "error_message": str(e),
                        }
                    )

            conn.close()

            # Calculate score
            score = int((earned_points / total_points) * 100) if total_points > 0 else 0
            passed = score >= 70

            # Save submission
            submission_doc = {
                "exercise_id": ObjectId(exercise_id),
                "user_id": user_id,
                "code": code,
                "language": "sql",
                "score": score,
                "points_earned": earned_points,
                "total_points": total_points,
                "passed": passed,
                "test_results": test_results,
                "submitted_at": datetime.now(timezone.utc),
            }

            self.db.code_submissions.insert_one(submission_doc)

            logger.info(
                f"✅ SQL exercise graded: exercise_id={exercise_id}, user_id={user_id}, score={score}%"
            )

            return {
                "success": True,
                "submission": {
                    "id": str(submission_doc["_id"]),
                    "score": score,
                    "passed": passed,
                    "points_earned": earned_points,
                    "total_points": total_points,
                    "test_results": test_results,
                    "submitted_at": submission_doc["submitted_at"],
                },
            }

        finally:
            # Cleanup temp database
            if os.path.exists(db_path):
                os.unlink(db_path)

    # ==================== TEMPLATE FORMATTING ====================

    def _format_template_response(
        self, template_doc: dict, include_code: bool = False
    ) -> dict:
        """Format template document for response (UUID only)"""
        response = {
            "id": template_doc["id"],  # UUID only (all templates migrated)
            "title": template_doc["title"],
            "category": template_doc.get("topic_id"),  # Use topic_id
            "programming_language": template_doc.get("programming_language", "python"),
            "difficulty": template_doc.get("difficulty", "beginner"),
            "description": template_doc.get("description", ""),
            "tags": template_doc.get("tags", []),
            "is_featured": template_doc.get("is_featured", False),
            "metadata": template_doc.get("metadata", {}),
            "created_at": template_doc.get("created_at"),
            "updated_at": template_doc.get("updated_at"),
        }

        if include_code:
            response["code"] = template_doc.get("code", "")

        return response

    def _format_category_response(self, category_doc: dict) -> dict:
        """Format category document for response"""
        return {
            "id": category_doc["id"],
            "name": category_doc["name"],
            "language": category_doc.get("language", "python"),
            "description": category_doc.get("description", ""),
            "order": category_doc.get("order", 0),
        }

    # ==================== FILE NOTES ====================

    async def create_note(
        self,
        file_id: str,
        user_id: str,
        content: str,
        color: str = "yellow",
        line_number: Optional[int] = None,
        is_pinned: bool = False,
    ) -> dict:
        """Create a note for a file"""
        now = datetime.now(timezone.utc)

        # Verify file exists and user owns it
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "user_id": user_id, "deleted_at": None}
        )
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Create note document
        note_doc = {
            "file_id": ObjectId(file_id),
            "user_id": user_id,
            "content": content,
            "color": color,
            "line_number": line_number,
            "is_pinned": is_pinned,
            "created_at": now,
            "updated_at": now,
        }

        result = self.db.code_file_notes.insert_one(note_doc)
        note_doc["_id"] = result.inserted_id

        logger.info(f"✅ Created note for file {file_id}, user {user_id}")

        return {
            "success": True,
            "note": self._format_note_response(note_doc),
        }

    async def get_file_notes(self, file_id: str, user_id: str) -> dict:
        """Get all notes for a file"""
        # Verify file exists and user owns it
        file_doc = self.db.code_files.find_one(
            {"_id": ObjectId(file_id), "user_id": user_id, "deleted_at": None}
        )
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")

        # Get notes (pinned first, then by creation date)
        notes_cursor = self.db.code_file_notes.find(
            {"file_id": ObjectId(file_id), "user_id": user_id}
        ).sort([("is_pinned", -1), ("created_at", -1)])

        notes = [self._format_note_response(note) for note in notes_cursor]

        return {
            "success": True,
            "notes": notes,
            "total": len(notes),
        }

    async def get_note(self, note_id: str, user_id: str) -> dict:
        """Get a specific note"""
        note_doc = self.db.code_file_notes.find_one(
            {"_id": ObjectId(note_id), "user_id": user_id}
        )
        if not note_doc:
            raise HTTPException(status_code=404, detail="Note not found")

        return {
            "success": True,
            "note": self._format_note_response(note_doc),
        }

    async def update_note(
        self,
        note_id: str,
        user_id: str,
        content: Optional[str] = None,
        color: Optional[str] = None,
        line_number: Optional[int] = None,
        is_pinned: Optional[bool] = None,
    ) -> dict:
        """Update a note"""
        # Verify note exists and user owns it
        note_doc = self.db.code_file_notes.find_one(
            {"_id": ObjectId(note_id), "user_id": user_id}
        )
        if not note_doc:
            raise HTTPException(status_code=404, detail="Note not found")

        # Build update dict
        update_dict = {"updated_at": datetime.now(timezone.utc)}
        if content is not None:
            update_dict["content"] = content
        if color is not None:
            update_dict["color"] = color
        if line_number is not None:
            update_dict["line_number"] = line_number
        if is_pinned is not None:
            update_dict["is_pinned"] = is_pinned

        # Update note
        self.db.code_file_notes.update_one(
            {"_id": ObjectId(note_id)}, {"$set": update_dict}
        )

        # Get updated note
        updated_note = self.db.code_file_notes.find_one({"_id": ObjectId(note_id)})

        logger.info(f"✅ Updated note {note_id}")

        return {
            "success": True,
            "note": self._format_note_response(updated_note),
        }

    async def delete_note(self, note_id: str, user_id: str) -> dict:
        """Delete a note"""
        # Verify note exists and user owns it
        note_doc = self.db.code_file_notes.find_one(
            {"_id": ObjectId(note_id), "user_id": user_id}
        )
        if not note_doc:
            raise HTTPException(status_code=404, detail="Note not found")

        # Delete note
        self.db.code_file_notes.delete_one({"_id": ObjectId(note_id)})

        logger.info(f"✅ Deleted note {note_id}")

        return {
            "success": True,
            "message": "Note deleted successfully",
            "note_id": note_id,
        }

    def _format_note_response(self, note_doc: dict) -> dict:
        """Format note document for response"""
        return {
            "id": str(note_doc["_id"]),
            "file_id": str(note_doc["file_id"]),
            "user_id": note_doc["user_id"],
            "content": note_doc["content"],
            "color": note_doc.get("color", "yellow"),
            "line_number": note_doc.get("line_number"),
            "is_pinned": note_doc.get("is_pinned", False),
            "created_at": (
                note_doc["created_at"].isoformat()
                if note_doc.get("created_at")
                else None
            ),
            "updated_at": (
                note_doc["updated_at"].isoformat()
                if note_doc.get("updated_at")
                else None
            ),
        }
