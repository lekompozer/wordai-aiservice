"""
StudyHub Marketplace Manager
Handles marketplace discovery, browsing, search operations
Pattern: Similar to Community Books marketplace
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from bson import ObjectId
from fastapi import HTTPException

from src.database.db_manager import DBManager
from src.models.studyhub_models import (
    MarketplaceSubjectsResponse,
    MarketplaceSubjectItem,
    OwnerInfo,
    SubjectStats,
    FeaturedSubjectsResponse,
    FeaturedSubjectItem,
    TrendingSubjectsResponse,
    TrendingSubjectItem,
    FeaturedCreatorsResponse,
    FeaturedCreatorItem,
    CreatorStats,
    SubjectPreview,
    PopularTagsResponse,
    PopularTagItem,
    CategoriesResponse,
    CategoryItem,
    SubjectPublicViewResponse,
    ModulePreview,
    SubjectPricing,
    RelatedSubjectsResponse,
    CreatorProfileResponse,
)


class StudyHubMarketplaceManager:
    """Manager for marketplace operations"""

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

    # ==================== SEARCH & BROWSE ====================

    async def search_subjects(
        self,
        q: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        level: Optional[str] = None,
        sort_by: str = "updated",
        skip: int = 0,
        limit: int = 20,
    ) -> MarketplaceSubjectsResponse:
        """Search and filter marketplace subjects"""
        # Build query
        query = {
            "status": "published",
            "is_public_marketplace": True,
            "deleted_at": None,
        }

        # Search by title or owner name
        if q:
            # Text search on title and description
            query["$text"] = {"$search": q}

        # Filter by category
        if category:
            query["category"] = category

        # Filter by tags
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["tags"] = {"$in": tag_list}

        # Filter by level
        if level:
            query["level"] = level

        # Determine sort
        sort_map = {
            "updated": ("last_updated_at", -1),
            "views": ("total_views", -1),
            "rating": ("metadata.avg_rating", -1),
            "newest": ("created_at", -1),
        }
        sort_field, sort_order = sort_map.get(sort_by, ("last_updated_at", -1))

        # Execute query
        total = self.db.studyhub_subjects.count_documents(query)
        subjects_cursor = (
            self.db.studyhub_subjects.find(query)
            .sort(sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )

        subjects = []
        for subject in subjects_cursor:
            owner = await self._get_owner_info(str(subject["owner_id"]))
            subjects.append(await self._build_marketplace_item(subject, owner))

        return MarketplaceSubjectsResponse(
            subjects=subjects, total=total, skip=skip, limit=limit
        )

    async def get_latest_subjects(
        self,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> MarketplaceSubjectsResponse:
        """Get latest updated subjects"""
        query = {
            "status": "published",
            "is_public_marketplace": True,
            "deleted_at": None,
        }

        if category:
            query["category"] = category

        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["tags"] = {"$in": tag_list}

        total = self.db.studyhub_subjects.count_documents(query)
        subjects_cursor = (
            self.db.studyhub_subjects.find(query)
            .sort("last_updated_at", -1)
            .skip(skip)
            .limit(limit)
        )

        subjects = []
        for subject in subjects_cursor:
            owner = await self._get_owner_info(str(subject["owner_id"]))
            subjects.append(await self._build_marketplace_item(subject, owner))

        return MarketplaceSubjectsResponse(
            subjects=subjects, total=total, skip=skip, limit=limit
        )

    async def get_top_subjects(
        self,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 10,
    ) -> MarketplaceSubjectsResponse:
        """Get top viewed/enrolled subjects"""
        query = {
            "status": "published",
            "is_public_marketplace": True,
            "deleted_at": None,
        }

        if category:
            query["category"] = category

        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["tags"] = {"$in": tag_list}

        subjects_cursor = (
            self.db.studyhub_subjects.find(query).sort("total_views", -1).limit(limit)
        )

        subjects = []
        for subject in subjects_cursor:
            owner = await self._get_owner_info(str(subject["owner_id"]))
            subjects.append(await self._build_marketplace_item(subject, owner))

        return MarketplaceSubjectsResponse(
            subjects=subjects, total=len(subjects), skip=0, limit=limit
        )

    # ==================== FEATURED & TRENDING ====================

    async def get_featured_week(self) -> FeaturedSubjectsResponse:
        """Get 3 featured subjects of the week"""
        # Get date range (last 7 days)
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        featured = []

        # Get 2 most viewed this week
        top_viewed = list(
            self.db.studyhub_subjects.find(
                {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                    "last_updated_at": {"$gte": week_ago},
                }
            )
            .sort("views_this_week", -1)
            .limit(2)
        )

        for subject in top_viewed:
            owner = await self._get_owner_info(str(subject["owner_id"]))
            stats = await self._get_subject_stats(subject)
            featured.append(
                FeaturedSubjectItem(
                    id=str(subject["_id"]),
                    title=subject["title"],
                    cover_image_url=subject.get("cover_image_url"),
                    owner=owner,
                    stats=stats,
                    reason="most_viewed_week",
                )
            )

        # Get 1 most enrolled this week
        enrolled_pipeline = [
            {
                "$match": {
                    "enrolled_at": {"$gte": week_ago},
                    "status": {"$ne": "dropped"},
                }
            },
            {"$group": {"_id": "$subject_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1},
        ]
        top_enrolled = list(self.db.studyhub_enrollments.aggregate(enrolled_pipeline))

        if top_enrolled:
            subject = self.db.studyhub_subjects.find_one(
                {
                    "_id": top_enrolled[0]["_id"],
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            )
            if subject:
                owner = await self._get_owner_info(str(subject["owner_id"]))
                stats = await self._get_subject_stats(subject)
                featured.append(
                    FeaturedSubjectItem(
                        id=str(subject["_id"]),
                        title=subject["title"],
                        cover_image_url=subject.get("cover_image_url"),
                        owner=owner,
                        stats=stats,
                        reason="most_enrolled_week",
                    )
                )

        return FeaturedSubjectsResponse(featured_subjects=featured)

    async def get_trending_today(self) -> TrendingSubjectsResponse:
        """Get 5 trending subjects today"""
        trending = []

        subjects_cursor = (
            self.db.studyhub_subjects.find(
                {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            )
            .sort("views_today", -1)
            .limit(5)
        )

        for subject in subjects_cursor:
            owner = await self._get_owner_info(str(subject["owner_id"]))
            stats = await self._get_subject_stats(subject)
            trending.append(
                TrendingSubjectItem(
                    id=str(subject["_id"]),
                    title=subject["title"],
                    cover_image_url=subject.get("cover_image_url"),
                    owner=owner,
                    stats=stats,
                    views_today=subject.get("views_today", 0),
                )
            )

        return TrendingSubjectsResponse(trending_subjects=trending)

    async def get_featured_creators(self) -> FeaturedCreatorsResponse:
        """Get 10 featured creators"""
        featured = []
        used_creators = set()

        # 1. Top 3 by total reads (sum of all subject views)
        pipeline_reads = [
            {
                "$match": {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            },
            {
                "$group": {
                    "_id": "$owner_id",
                    "total_reads": {"$sum": "$total_views"},
                }
            },
            {"$sort": {"total_reads": -1}},
            {"$limit": 3},
        ]
        top_reads = list(self.db.studyhub_subjects.aggregate(pipeline_reads))

        for item in top_reads:
            creator_id = str(item["_id"])
            if creator_id not in used_creators:
                creator = await self._build_featured_creator(creator_id, "most_reads")
                if creator:
                    featured.append(creator)
                    used_creators.add(creator_id)

        # 2. Top 3 by best ratings
        pipeline_ratings = [
            {
                "$match": {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                    "metadata.avg_rating": {"$gte": 4.0},
                }
            },
            {
                "$group": {
                    "_id": "$owner_id",
                    "avg_rating": {"$avg": "$metadata.avg_rating"},
                }
            },
            {"$sort": {"avg_rating": -1}},
            {"$limit": 3},
        ]
        top_ratings = list(self.db.studyhub_subjects.aggregate(pipeline_ratings))

        for item in top_ratings:
            creator_id = str(item["_id"])
            if creator_id not in used_creators:
                creator = await self._build_featured_creator(creator_id, "best_reviews")
                if creator:
                    featured.append(creator)
                    used_creators.add(creator_id)

        # 3. Top 4 by highest-viewed subjects
        top_subjects = list(
            self.db.studyhub_subjects.find(
                {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            )
            .sort("total_views", -1)
            .limit(10)
        )

        for subject in top_subjects:
            creator_id = str(subject["owner_id"])
            if creator_id not in used_creators and len(featured) < 10:
                creator = await self._build_featured_creator(creator_id, "top_subject")
                if creator:
                    featured.append(creator)
                    used_creators.add(creator_id)

        return FeaturedCreatorsResponse(featured_creators=featured[:10])

    # ==================== TAGS & CATEGORIES ====================

    async def get_popular_tags(self) -> PopularTagsResponse:
        """Get 25 most popular tags"""
        pipeline = [
            {
                "$match": {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            },
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 25},
        ]

        results = list(self.db.studyhub_subjects.aggregate(pipeline))
        tags = [PopularTagItem(tag=r["_id"], count=r["count"]) for r in results]

        return PopularTagsResponse(popular_tags=tags)

    async def get_popular_categories(self) -> CategoriesResponse:
        """Get all categories with subject count"""
        pipeline = [
            {
                "$match": {
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                    "category": {"$ne": None},
                }
            },
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        results = list(self.db.studyhub_subjects.aggregate(pipeline))

        # Category icons mapping
        category_icons = {
            "Programming": "💻",
            "Business": "💼",
            "Design": "🎨",
            "Marketing": "📈",
            "Data Science": "📊",
            "Language": "🌍",
            "Music": "🎵",
            "Health": "🏥",
        }

        categories = [
            CategoryItem(
                name=r["_id"],
                count=r["count"],
                icon=category_icons.get(r["_id"], "📚"),
                description=None,
            )
            for r in results
        ]

        return CategoriesResponse(categories=categories)

    # ==================== SUBJECT VIEWS ====================

    async def get_subject_public_view(
        self, subject_id: str
    ) -> SubjectPublicViewResponse:
        """Get public subject view + track views"""
        subject = self.db.studyhub_subjects.find_one(
            {
                "_id": ObjectId(subject_id),
                "status": "published",
                "is_public_marketplace": True,
                "deleted_at": None,
            }
        )
        if not subject:
            raise HTTPException(
                status_code=404, detail="Subject not found or not public"
            )

        # Track view
        await self._track_view(subject_id)

        # Get owner
        owner = await self._get_owner_info(str(subject["owner_id"]))

        # Get modules (preview first 2 or marked as preview)
        modules = list(
            self.db.studyhub_modules.find(
                {"subject_id": ObjectId(subject_id), "deleted_at": None}
            ).sort("order_index", 1)
        )

        module_previews = []
        for idx, module in enumerate(modules):
            # Get content count
            content_count = self.db.studyhub_module_contents.count_documents(
                {"module_id": module["_id"], "deleted_at": None}
            )

            module_previews.append(
                ModulePreview(
                    id=str(module["_id"]),
                    title=module["title"],
                    description=module.get("description"),
                    order_index=module["order_index"],
                    content_count=content_count,
                    is_preview=(idx < 2),  # First 2 modules are preview
                )
            )

        # Get stats
        stats = await self._get_subject_stats(subject)

        # Pricing (for now all free)
        pricing = SubjectPricing(is_free=True, price=0.0)

        return SubjectPublicViewResponse(
            id=str(subject["_id"]),
            title=subject["title"],
            description=subject.get("description"),
            cover_image_url=subject.get("cover_image_url"),
            owner=owner,
            category=subject.get("category"),
            tags=subject.get("tags", []),
            level=subject.get("level"),
            modules=module_previews,
            stats=stats,
            pricing=pricing,
            created_at=subject["created_at"],
            last_updated_at=subject.get("last_updated_at", subject["created_at"]),
        )

    async def get_related_subjects(
        self, subject_id: str, limit: int = 5
    ) -> RelatedSubjectsResponse:
        """Get related subjects based on category/tags"""
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Build query for related subjects
        query = {
            "_id": {"$ne": ObjectId(subject_id)},
            "status": "published",
            "is_public_marketplace": True,
            "deleted_at": None,
        }

        # Match category or tags
        or_conditions = []
        if subject.get("category"):
            or_conditions.append({"category": subject["category"]})
        if subject.get("tags"):
            or_conditions.append({"tags": {"$in": subject["tags"]}})

        if or_conditions:
            query["$or"] = or_conditions

        related = list(
            self.db.studyhub_subjects.find(query).sort("total_views", -1).limit(limit)
        )

        subjects = []
        for subj in related:
            owner = await self._get_owner_info(str(subj["owner_id"]))
            subjects.append(await self._build_marketplace_item(subj, owner))

        return RelatedSubjectsResponse(related_subjects=subjects)

    # ==================== CREATOR PROFILE ====================

    async def get_creator_profile(self, creator_id: str) -> CreatorProfileResponse:
        """Get public creator profile"""
        # Get user
        user = self.db.users.find_one({"firebase_uid": creator_id})
        if not user:
            raise HTTPException(status_code=404, detail="Creator not found")

        # Get creator stats
        stats = await self._get_creator_stats(creator_id)

        # Get featured subjects (top 3 by views)
        top_subjects = list(
            self.db.studyhub_subjects.find(
                {
                    "owner_id": creator_id,
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            )
            .sort("total_views", -1)
            .limit(3)
        )

        featured = []
        for subject in top_subjects:
            subject_stats = await self._get_subject_stats(subject)
            featured.append(
                SubjectPreview(
                    id=str(subject["_id"]),
                    title=subject["title"],
                    cover_image_url=subject.get("cover_image_url"),
                    stats=subject_stats,
                )
            )

        return CreatorProfileResponse(
            user_id=creator_id,
            display_name=user.get("display_name"),
            avatar_url=user.get("avatar_url"),
            bio=user.get("bio"),
            website=user.get("website"),
            social_links=user.get("social_links"),
            stats=stats,
            featured_subjects=featured,
            joined_at=user.get("created_at"),
        )

    async def get_creator_subjects(
        self,
        creator_id: str,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "views",
    ) -> MarketplaceSubjectsResponse:
        """Get all public subjects by creator"""
        query = {
            "owner_id": creator_id,
            "status": "published",
            "is_public_marketplace": True,
            "deleted_at": None,
        }

        # Sort mapping
        sort_map = {
            "views": ("total_views", -1),
            "rating": ("metadata.avg_rating", -1),
            "newest": ("created_at", -1),
        }
        sort_field, sort_order = sort_map.get(sort_by, ("total_views", -1))

        total = self.db.studyhub_subjects.count_documents(query)
        subjects_cursor = (
            self.db.studyhub_subjects.find(query)
            .sort(sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )

        owner = await self._get_owner_info(creator_id)
        subjects = []
        for subject in subjects_cursor:
            subjects.append(await self._build_marketplace_item(subject, owner))

        return MarketplaceSubjectsResponse(
            subjects=subjects, total=total, skip=skip, limit=limit
        )

    # ==================== HELPER METHODS ====================

    async def _get_owner_info(self, user_id: str) -> OwnerInfo:
        """Get owner/creator info"""
        user = self.db.users.find_one({"firebase_uid": user_id})
        if not user:
            return OwnerInfo(user_id=user_id, display_name="Unknown", avatar_url=None)

        return OwnerInfo(
            user_id=user_id,
            display_name=user.get("display_name", "Unknown"),
            avatar_url=user.get("photo_url"),
        )

    async def _get_subject_stats(self, subject: Dict) -> SubjectStats:
        """Get subject statistics"""
        # Calculate completion rate
        total_learners = subject["metadata"].get("total_learners", 0)
        completed_learners = self.db.studyhub_enrollments.count_documents(
            {"subject_id": subject["_id"], "status": "completed"}
        )
        completion_rate = (
            completed_learners / total_learners if total_learners > 0 else 0.0
        )

        return SubjectStats(
            total_modules=subject["metadata"].get("total_modules", 0),
            total_learners=total_learners,
            total_views=subject.get("total_views", 0),
            average_rating=subject["metadata"].get("avg_rating", 0.0),
            completion_rate=completion_rate,
        )

    async def _build_marketplace_item(
        self, subject: Dict, owner: OwnerInfo
    ) -> MarketplaceSubjectItem:
        """Build marketplace subject item"""
        stats = await self._get_subject_stats(subject)

        return MarketplaceSubjectItem(
            id=str(subject["_id"]),
            title=subject["title"],
            description=subject.get("description"),
            cover_image_url=subject.get("cover_image_url"),
            owner=owner,
            category=subject.get("category"),
            tags=subject.get("tags", []),
            level=subject.get("level"),
            stats=stats,
            last_updated_at=subject.get("last_updated_at", subject["created_at"]),
            created_at=subject["created_at"],
        )

    async def _get_creator_stats(self, creator_id: str) -> CreatorStats:
        """Get creator statistics"""
        # Count subjects
        total_subjects = self.db.studyhub_subjects.count_documents(
            {
                "owner_id": creator_id,
                "status": "published",
                "is_public_marketplace": True,
                "deleted_at": None,
            }
        )

        # Get total students (sum of all subject learners)
        subjects = list(
            self.db.studyhub_subjects.find(
                {
                    "owner_id": creator_id,
                    "status": "published",
                    "is_public_marketplace": True,
                    "deleted_at": None,
                }
            )
        )

        total_students = 0
        total_reads = 0
        avg_rating_sum = 0.0
        rating_count = 0

        for subject in subjects:
            total_students += subject["metadata"].get("total_learners", 0)
            total_reads += subject.get("total_views", 0)
            if subject["metadata"].get("avg_rating", 0) > 0:
                avg_rating_sum += subject["metadata"]["avg_rating"]
                rating_count += 1

        avg_rating = avg_rating_sum / rating_count if rating_count > 0 else 0.0

        return CreatorStats(
            total_subjects=total_subjects,
            total_students=total_students,
            total_reads=total_reads,
            average_rating=avg_rating,
            total_reviews=0,  # TODO: Implement reviews system
        )

    async def _build_featured_creator(
        self, creator_id: str, reason: str
    ) -> Optional[FeaturedCreatorItem]:
        """Build featured creator item"""
        user = self.db.users.find_one({"firebase_uid": creator_id})
        if not user:
            return None

        # Get stats
        stats = await self._get_creator_stats(creator_id)

        # Get top subject
        top_subject = self.db.studyhub_subjects.find_one(
            {
                "owner_id": creator_id,
                "status": "published",
                "is_public_marketplace": True,
                "deleted_at": None,
            },
            sort=[("total_views", -1)],
        )

        top_subject_preview = None
        if top_subject:
            subject_stats = await self._get_subject_stats(top_subject)
            top_subject_preview = SubjectPreview(
                id=str(top_subject["_id"]),
                title=top_subject["title"],
                cover_image_url=top_subject.get("cover_image_url"),
                stats=subject_stats,
            )

        return FeaturedCreatorItem(
            user_id=creator_id,
            display_name=user.get("display_name"),
            avatar_url=user.get("avatar_url"),
            bio=user.get("bio"),
            stats=stats,
            top_subject=top_subject_preview,
            reason=reason,
        )

    async def _track_view(self, subject_id: str):
        """Track subject view"""
        now = datetime.now(timezone.utc)

        # Increment total views and views today
        self.db.studyhub_subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$inc": {"total_views": 1, "views_today": 1, "views_this_week": 1},
                "$set": {"last_updated_at": now},
            },
        )
