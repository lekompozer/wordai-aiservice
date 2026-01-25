"""
Service layer for StudyHub Discussions & Comments
Handles business logic for community discussions on subjects
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException


class StudyHubDiscussionManager:
    """Manager for discussion and comment operations"""

    def __init__(self, db):
        self.db = db
        self.discussions_collection = db["studyhub_discussions"]
        self.comments_collection = db["studyhub_discussion_comments"]
        self.users_collection = db["users"]

    async def get_subject_discussions(
        self,
        community_subject_id: str,
        sort_by: str = "latest",
        skip: int = 0,
        limit: int = 20,
        current_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get discussions for a community subject

        Args:
            community_subject_id: Community subject slug
            sort_by: Sort order (latest/popular/most_replies)
            skip: Pagination offset
            limit: Items per page
            current_user_id: Optional user ID to check if they liked discussions

        Returns:
            Dictionary with discussions list, total count, and pagination info
        """
        query = {"community_subject_id": community_subject_id}

        # Determine sort order
        if sort_by == "popular":
            sort = [("likes_count", -1), ("created_at", -1)]
        elif sort_by == "most_replies":
            sort = [("replies_count", -1), ("created_at", -1)]
        else:  # latest (default)
            sort = [("is_pinned", -1), ("created_at", -1)]

        # Execute query
        cursor = (
            self.discussions_collection.find(query).sort(sort).skip(skip).limit(limit)
        )
        discussions_raw = await cursor.to_list(length=limit)
        total = await self.discussions_collection.count_documents(query)

        # Enrich with author info and check if current user liked
        discussions = []
        for disc in discussions_raw:
            user = await self.users_collection.find_one({"uid": disc["author_id"]})

            is_liked = False
            if current_user_id:
                is_liked = current_user_id in disc.get("liked_by", [])

            discussions.append(
                {
                    "id": str(disc["_id"]),
                    "title": disc["title"],
                    "content": disc["content"],
                    "author": {
                        "id": disc["author_id"],
                        "name": (
                            user.get("displayName", "Unknown User")
                            if user
                            else "Unknown User"
                        ),
                        "avatar": user.get("photoURL") if user else None,
                    },
                    "replies_count": disc.get("replies_count", 0),
                    "likes_count": disc.get("likes_count", 0),
                    "is_liked": is_liked,
                    "is_pinned": disc.get("is_pinned", False),
                    "is_locked": disc.get("is_locked", False),
                    "created_at": disc["created_at"],
                    "updated_at": disc.get("updated_at", disc["created_at"]),
                }
            )

        return {
            "discussions": discussions,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    async def create_discussion(
        self, community_subject_id: str, title: str, content: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Create a new discussion

        Args:
            community_subject_id: Community subject slug
            title: Discussion title
            content: Discussion content
            user_id: Author user ID

        Returns:
            Created discussion document
        """
        # Get user info
        user = await self.users_collection.find_one({"uid": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create discussion document
        now = datetime.utcnow()
        discussion_doc = {
            "community_subject_id": community_subject_id,
            "author_id": user_id,
            "author_name": user.get("displayName", "Unknown User"),
            "author_avatar": user.get("photoURL"),
            "title": title,
            "content": content,
            "replies_count": 0,
            "likes_count": 0,
            "liked_by": [],
            "is_pinned": False,
            "is_locked": False,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.discussions_collection.insert_one(discussion_doc)
        discussion_doc["_id"] = result.inserted_id

        return {
            "id": str(discussion_doc["_id"]),
            "title": discussion_doc["title"],
            "content": discussion_doc["content"],
            "author": {
                "id": user_id,
                "name": discussion_doc["author_name"],
                "avatar": discussion_doc["author_avatar"],
            },
            "replies_count": 0,
            "likes_count": 0,
            "is_liked": False,
            "is_pinned": False,
            "is_locked": False,
            "created_at": discussion_doc["created_at"],
            "updated_at": discussion_doc["updated_at"],
        }

    async def get_discussion_comments(
        self, discussion_id: str, current_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all comments for a discussion (with nested replies)

        Args:
            discussion_id: Discussion ObjectId
            current_user_id: Optional user ID to check if they liked comments

        Returns:
            Dictionary with comments list and total count
        """
        # Verify discussion exists
        discussion = await self.discussions_collection.find_one(
            {"_id": ObjectId(discussion_id)}
        )
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")

        # Get all comments for this discussion
        cursor = self.comments_collection.find(
            {"discussion_id": ObjectId(discussion_id), "is_deleted": False}
        ).sort("created_at", 1)

        comments_raw = await cursor.to_list(length=None)
        total = len(comments_raw)

        # Build comment hierarchy (top-level comments with nested replies)
        comments_dict = {}
        top_level_comments = []

        # First pass: Create all comment objects
        for comment in comments_raw:
            user = await self.users_collection.find_one({"uid": comment["author_id"]})

            is_liked = False
            if current_user_id:
                is_liked = current_user_id in comment.get("liked_by", [])

            comment_obj = {
                "id": str(comment["_id"]),
                "content": comment["content"],
                "author": {
                    "id": comment["author_id"],
                    "name": (
                        user.get("displayName", "Unknown User")
                        if user
                        else "Unknown User"
                    ),
                    "avatar": user.get("photoURL") if user else None,
                },
                "likes_count": comment.get("likes_count", 0),
                "is_liked": is_liked,
                "parent_comment_id": (
                    str(comment["parent_comment_id"])
                    if comment.get("parent_comment_id")
                    else None
                ),
                "replies": [],
                "is_deleted": comment.get("is_deleted", False),
                "created_at": comment["created_at"],
                "updated_at": comment.get("updated_at", comment["created_at"]),
            }

            comments_dict[str(comment["_id"])] = comment_obj

            # If no parent, it's a top-level comment
            if not comment.get("parent_comment_id"):
                top_level_comments.append(comment_obj)

        # Second pass: Build reply hierarchy
        for comment in comments_raw:
            if comment.get("parent_comment_id"):
                parent_id = str(comment["parent_comment_id"])
                if parent_id in comments_dict:
                    comments_dict[parent_id]["replies"].append(
                        comments_dict[str(comment["_id"])]
                    )

        return {"comments": top_level_comments, "total": total}

    async def add_comment(
        self,
        discussion_id: str,
        content: str,
        user_id: str,
        parent_comment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a comment to a discussion

        Args:
            discussion_id: Discussion ObjectId
            content: Comment content
            user_id: Author user ID
            parent_comment_id: Optional parent comment for nested replies

        Returns:
            Created comment document
        """
        # Verify discussion exists and is not locked
        discussion = await self.discussions_collection.find_one(
            {"_id": ObjectId(discussion_id)}
        )
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")

        if discussion.get("is_locked"):
            raise HTTPException(status_code=403, detail="Discussion is locked")

        # Get user info
        user = await self.users_collection.find_one({"uid": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # If replying to a comment, verify parent exists
        if parent_comment_id:
            parent_comment = await self.comments_collection.find_one(
                {"_id": ObjectId(parent_comment_id)}
            )
            if not parent_comment:
                raise HTTPException(status_code=404, detail="Parent comment not found")

        # Create comment document
        now = datetime.utcnow()
        comment_doc = {
            "discussion_id": ObjectId(discussion_id),
            "author_id": user_id,
            "author_name": user.get("displayName", "Unknown User"),
            "author_avatar": user.get("photoURL"),
            "content": content,
            "parent_comment_id": (
                ObjectId(parent_comment_id) if parent_comment_id else None
            ),
            "likes_count": 0,
            "liked_by": [],
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.comments_collection.insert_one(comment_doc)
        comment_doc["_id"] = result.inserted_id

        # Increment replies_count on discussion
        await self.discussions_collection.update_one(
            {"_id": ObjectId(discussion_id)}, {"$inc": {"replies_count": 1}}
        )

        return {
            "id": str(comment_doc["_id"]),
            "content": comment_doc["content"],
            "author": {
                "id": user_id,
                "name": comment_doc["author_name"],
                "avatar": comment_doc["author_avatar"],
            },
            "likes_count": 0,
            "is_liked": False,
            "parent_comment_id": parent_comment_id,
            "replies": [],
            "is_deleted": False,
            "created_at": comment_doc["created_at"],
            "updated_at": comment_doc["updated_at"],
        }

    async def toggle_discussion_like(
        self, discussion_id: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Toggle like on a discussion

        Args:
            discussion_id: Discussion ObjectId
            user_id: User ID

        Returns:
            Dictionary with is_liked status and new likes_count
        """
        discussion = await self.discussions_collection.find_one(
            {"_id": ObjectId(discussion_id)}
        )
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")

        liked_by = discussion.get("liked_by", [])
        is_liked = user_id in liked_by

        if is_liked:
            # Unlike
            await self.discussions_collection.update_one(
                {"_id": ObjectId(discussion_id)},
                {"$pull": {"liked_by": user_id}, "$inc": {"likes_count": -1}},
            )
            new_is_liked = False
            new_count = discussion.get("likes_count", 0) - 1
        else:
            # Like
            await self.discussions_collection.update_one(
                {"_id": ObjectId(discussion_id)},
                {"$addToSet": {"liked_by": user_id}, "$inc": {"likes_count": 1}},
            )
            new_is_liked = True
            new_count = discussion.get("likes_count", 0) + 1

        return {
            "is_liked": new_is_liked,
            "likes_count": max(0, new_count),  # Ensure non-negative
        }

    async def toggle_comment_like(
        self, comment_id: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Toggle like on a comment

        Args:
            comment_id: Comment ObjectId
            user_id: User ID

        Returns:
            Dictionary with is_liked status and new likes_count
        """
        comment = await self.comments_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        liked_by = comment.get("liked_by", [])
        is_liked = user_id in liked_by

        if is_liked:
            # Unlike
            await self.comments_collection.update_one(
                {"_id": ObjectId(comment_id)},
                {"$pull": {"liked_by": user_id}, "$inc": {"likes_count": -1}},
            )
            new_is_liked = False
            new_count = comment.get("likes_count", 0) - 1
        else:
            # Like
            await self.comments_collection.update_one(
                {"_id": ObjectId(comment_id)},
                {"$addToSet": {"liked_by": user_id}, "$inc": {"likes_count": 1}},
            )
            new_is_liked = True
            new_count = comment.get("likes_count", 0) + 1

        return {"is_liked": new_is_liked, "likes_count": max(0, new_count)}

    async def delete_comment(
        self, comment_id: str, user_id: str, is_admin: bool = False
    ) -> Dict[str, str]:
        """
        Delete a comment (soft delete - mark as deleted)

        Args:
            comment_id: Comment ObjectId
            user_id: User ID (must be comment author or admin)
            is_admin: Whether user has admin privileges

        Returns:
            Success message
        """
        comment = await self.comments_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        # Check authorization
        if comment["author_id"] != user_id and not is_admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this comment"
            )

        # Soft delete (mark as deleted, keep data for reply hierarchy)
        await self.comments_collection.update_one(
            {"_id": ObjectId(comment_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "content": "[Comment deleted]",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Decrement replies_count on discussion
        await self.discussions_collection.update_one(
            {"_id": comment["discussion_id"]}, {"$inc": {"replies_count": -1}}
        )

        return {"message": "Comment deleted successfully"}

    async def delete_discussion(
        self, discussion_id: str, user_id: str, is_admin: bool = False
    ) -> Dict[str, str]:
        """
        Delete a discussion (hard delete - removes discussion and all comments)

        Args:
            discussion_id: Discussion ObjectId
            user_id: User ID (must be discussion author or admin)
            is_admin: Whether user has admin privileges

        Returns:
            Success message
        """
        discussion = await self.discussions_collection.find_one(
            {"_id": ObjectId(discussion_id)}
        )
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")

        # Check authorization
        if discussion["author_id"] != user_id and not is_admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this discussion"
            )

        # Delete all comments for this discussion
        await self.comments_collection.delete_many(
            {"discussion_id": ObjectId(discussion_id)}
        )

        # Delete discussion
        await self.discussions_collection.delete_one({"_id": ObjectId(discussion_id)})

        return {"message": "Discussion and all comments deleted successfully"}
