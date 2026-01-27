"""
Learning System API Routes
Endpoints for categories, topics, knowledge articles, and community features
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.models.learning_system_models import (
    LearningCategoryCreate,
    LearningCategoryUpdate,
    LearningCategoryResponse,
    LearningTopicCreate,
    LearningTopicUpdate,
    LearningTopicResponse,
    KnowledgeArticleCreate,
    KnowledgeArticleUpdate,
    KnowledgeArticleResponse,
    KnowledgeArticleListItem,
    TemplateCreate,
    TemplateUpdate,
    ExerciseCreate,
    ExerciseUpdate,
    ExerciseSubmitRequest,
    ExerciseSubmissionResponse,
    LikeRequest,
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    ContentSourceType,
    TopicLevel,
    GradeLevel,
    ContentDifficulty,
    ContentType,
    GradingType,
    ModerationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Learning System"])

# WordAI Team admin email
WORDAI_TEAM_EMAIL = "tienhoi.lh@gmail.com"


def is_wordai_team(user: dict) -> bool:
    """Check if user is WordAI Team member"""
    return user.get("email") == WORDAI_TEAM_EMAIL


# ==================== CATEGORY MANAGEMENT ====================


@router.get("/categories", response_model=dict)
async def list_categories():
    """
    Get all learning categories (public endpoint)

    Returns list of categories with topic counts
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get all active categories
        categories = list(
            db.learning_categories.find({"is_active": True}, {"_id": 0}).sort(
                "order", 1
            )
        )

        # Get topic counts for each category
        for category in categories:
            topic_count = db.learning_topics.count_documents(
                {"category_id": category["id"], "is_published": True}
            )
            category["topic_count"] = topic_count

        return {"success": True, "categories": categories}

    except Exception as e:
        logger.error(f"❌ Error listing categories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categories", response_model=dict)
async def create_category(
    request: LearningCategoryCreate, current_user: dict = Depends(get_current_user)
):
    """
    Create new learning category (WordAI Team only)

    - **id**: Category ID (slug, e.g., 'python')
    - **name**: Display name (e.g., 'Python')
    - **description**: Category description
    - **icon**: Emoji icon
    - **order**: Display order
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can create categories"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if category ID already exists
        existing = db.learning_categories.find_one({"id": request.id})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Category with ID '{request.id}' already exists",
            )

        # Create category
        now = datetime.utcnow()
        category = {
            "id": request.id,
            "name": request.name,
            "description": request.description,
            "icon": request.icon,
            "order": request.order,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        db.learning_categories.insert_one(category)

        category["topic_count"] = 0
        del category["_id"]

        logger.info(f"✅ Created category: {request.id}")

        return {"success": True, "category": category}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating category: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/categories/{category_id}", response_model=dict)
async def update_category(
    category_id: str,
    request: LearningCategoryUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update learning category (WordAI Team only)
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can update categories"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if category exists
        category = db.learning_categories.find_one({"id": category_id})
        if not category:
            raise HTTPException(
                status_code=404, detail=f"Category '{category_id}' not found"
            )

        # Build update data
        update_data = {k: v for k, v in request.dict(exclude_unset=True).items()}
        if update_data:
            update_data["updated_at"] = datetime.utcnow()

            db.learning_categories.update_one(
                {"id": category_id}, {"$set": update_data}
            )

        # Get updated category
        updated = db.learning_categories.find_one({"id": category_id}, {"_id": 0})
        if not updated:
            raise HTTPException(
                status_code=404, detail="Category not found after update"
            )

        # Add topic count
        topic_count = db.learning_topics.count_documents(
            {"category_id": category_id, "is_active": True}
        )
        updated["topic_count"] = topic_count

        logger.info(f"✅ Updated category: {category_id}")

        return {"success": True, "category": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating category: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}", response_model=dict)
async def delete_category(
    category_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete learning category (WordAI Team only)

    This will also deactivate all topics under this category
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can delete categories"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if category exists
        category = db.learning_categories.find_one({"id": category_id})
        if not category:
            raise HTTPException(
                status_code=404, detail=f"Category '{category_id}' not found"
            )

        # Soft delete: mark as inactive
        db.learning_categories.update_one(
            {"id": category_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        # Also deactivate all topics in this category
        db.learning_topics.update_many(
            {"category_id": category_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        logger.info(f"✅ Deleted category: {category_id}")

        return {
            "success": True,
            "message": f"Category '{category_id}' deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting category: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TOPIC MANAGEMENT ====================


@router.get("/categories/{category_id}/topics", response_model=dict)
async def list_topics(
    category_id: str,
    level: Optional[TopicLevel] = Query(None, description="Filter by level"),
    grade: Optional[GradeLevel] = Query(None, description="Filter by grade"),
):
    """
    Get topics in a category (public endpoint)

    - **level**: Filter by student/professional
    - **grade**: Filter by grade (10, 11, 12)
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Build query
        query = {"category_id": category_id, "is_published": True}
        if level:
            query["level"] = level.value
        if grade:
            query["grade"] = grade.value

        # Get topics
        topics = list(db.learning_topics.find(query, {"_id": 0}).sort("order", 1))

        # Add content counts
        for topic in topics:
            topic["knowledge_count"] = db.knowledge_articles.count_documents(
                {"topic_id": topic["id"], "is_published": True}
            )
            topic["template_count"] = db.code_templates.count_documents(
                {"topic_id": topic["id"], "is_published": True}
            )
            topic["exercise_count"] = db.code_exercises.count_documents(
                {"topic_id": topic["id"], "is_published": True}
            )

        return {"success": True, "topics": topics}

    except Exception as e:
        logger.error(f"❌ Error listing topics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/topics", response_model=dict)
async def create_topic(
    request: LearningTopicCreate, current_user: dict = Depends(get_current_user)
):
    """
    Create new learning topic (WordAI Team only)

    - **id**: Topic ID (slug)
    - **category_id**: Parent category
    - **name**: Topic name
    - **level**: student/professional
    - **grade**: Grade level (for student topics)
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can create topics"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if category exists
        category = db.learning_categories.find_one({"id": request.category_id})
        if not category:
            raise HTTPException(
                status_code=404, detail=f"Category '{request.category_id}' not found"
            )

        # Check if topic ID already exists
        existing = db.learning_topics.find_one({"id": request.id})
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Topic with ID '{request.id}' already exists"
            )

        # Create topic
        now = datetime.utcnow()
        topic = {
            "id": request.id,
            "category_id": request.category_id,
            "name": request.name,
            "description": request.description,
            "level": request.level.value,
            "grade": request.grade.value if request.grade else None,
            "order": request.order,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        db.learning_topics.insert_one(topic)

        topic["knowledge_count"] = 0
        topic["template_count"] = 0
        topic["exercise_count"] = 0
        del topic["_id"]

        logger.info(f"✅ Created topic: {request.id}")

        return {"success": True, "topic": topic}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating topic: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/topics/{topic_id}", response_model=dict)
async def update_topic(
    topic_id: str,
    request: LearningTopicUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update learning topic (WordAI Team only)
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can update topics"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if topic exists
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # Build update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, TopicLevel) or isinstance(value, GradeLevel):
                    update_data[field] = value.value
                else:
                    update_data[field] = value

        if update_data:
            update_data["updated_at"] = datetime.utcnow()

            db.learning_topics.update_one({"id": topic_id}, {"$set": update_data})

        # Get updated topic
        updated = db.learning_topics.find_one({"id": topic_id}, {"_id": 0})
        if not updated:
            raise HTTPException(status_code=404, detail="Topic not found after update")

        # Add content counts
        updated["knowledge_count"] = db.knowledge_articles.count_documents(
            {"topic_id": topic_id, "is_published": True}
        )
        updated["template_count"] = db.code_templates.count_documents(
            {"topic_id": topic_id, "is_published": True}
        )
        updated["exercise_count"] = db.code_exercises.count_documents(
            {"topic_id": topic_id, "is_published": True}
        )

        logger.info(f"✅ Updated topic: {topic_id}")

        return {"success": True, "topic": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating topic: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/topics/{topic_id}", response_model=dict)
async def delete_topic(topic_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete learning topic (WordAI Team only)

    This will deactivate the topic but keep the content
    """
    if not is_wordai_team(current_user):
        raise HTTPException(
            status_code=403, detail="Only WordAI Team can delete topics"
        )

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if topic exists
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # Soft delete: mark as inactive
        db.learning_topics.update_one(
            {"id": topic_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        logger.info(f"✅ Deleted topic: {topic_id}")

        return {"success": True, "message": f"Topic '{topic_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting topic: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== KNOWLEDGE ARTICLES ====================


@router.get("/topics/{topic_id}/knowledge", response_model=dict)
async def list_knowledge_articles(
    topic_id: str,
    language: str = Query("vi", description="Language code (vi/en/ja)"),
    source_type: Optional[ContentSourceType] = Query(
        None, description="Filter by source"
    ),
    difficulty: Optional[ContentDifficulty] = Query(
        None, description="Filter by difficulty"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get knowledge articles in a topic (public endpoint)

    - **language**: Content language (vi/en/ja)
    - **source_type**: Filter by wordai_team/community
    - **difficulty**: Filter by beginner/intermediate/advanced
    - **page**: Page number
    - **limit**: Items per page
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Build query
        query = {"topic_id": topic_id, "is_published": True}
        if source_type:
            query["source_type"] = source_type.value
        if difficulty:
            query["difficulty"] = difficulty.value

        # Get total count
        total = db.knowledge_articles.count_documents(query)

        # Get articles (list format without full content)
        skip = (page - 1) * limit
        articles = list(
            db.knowledge_articles.find(
                query,
                {
                    "_id": 0,
                    "content": 0,
                    "content_multilang": 0,
                },  # Exclude full content in list view
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        # Extract language-specific fields and add comment counts
        for article in articles:
            # Extract title in requested language (fallback to 'vi' or first available)
            title_multilang = article.get("title_multilang", {})
            if title_multilang:
                article["title"] = (
                    title_multilang.get(language)
                    or title_multilang.get("vi")
                    or next(iter(title_multilang.values()), article.get("title", ""))
                )
                article["available_languages"] = list(title_multilang.keys())
            else:
                article["available_languages"] = ["vi"]  # Legacy articles

            # Extract excerpt in requested language
            excerpt_multilang = article.get("excerpt_multilang", {})
            if excerpt_multilang:
                article["excerpt"] = (
                    excerpt_multilang.get(language)
                    or excerpt_multilang.get("vi")
                    or next(
                        iter(excerpt_multilang.values()), article.get("excerpt", "")
                    )
                )

            # Add comment count
            article["comment_count"] = db.learning_comments.count_documents(
                {"content_type": "knowledge", "content_id": article["id"]}
            )

        return {
            "success": True,
            "articles": articles,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error listing knowledge articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{article_id}", response_model=dict)
async def get_knowledge_article(
    article_id: str,
    language: str = Query("vi", description="Language code (vi/en/ja)"),
):
    """
    Get knowledge article details (public endpoint)

    Includes full content in requested language and increments view count
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get article
        article = db.knowledge_articles.find_one(
            {"id": article_id, "is_published": True}, {"_id": 0}
        )

        if not article:
            raise HTTPException(
                status_code=404, detail=f"Article '{article_id}' not found"
            )

        # Extract language-specific content
        title_multilang = article.get("title_multilang", {})
        content_multilang = article.get("content_multilang", {})
        excerpt_multilang = article.get("excerpt_multilang", {})

        if title_multilang:
            article["title"] = (
                title_multilang.get(language)
                or title_multilang.get("vi")
                or next(iter(title_multilang.values()), article.get("title", ""))
            )
            article["available_languages"] = list(title_multilang.keys())
        else:
            article["available_languages"] = ["vi"]  # Legacy articles

        if content_multilang:
            article["content"] = (
                content_multilang.get(language)
                or content_multilang.get("vi")
                or next(iter(content_multilang.values()), article.get("content", ""))
            )

        if excerpt_multilang:
            article["excerpt"] = (
                excerpt_multilang.get(language)
                or excerpt_multilang.get("vi")
                or next(iter(excerpt_multilang.values()), article.get("excerpt", ""))
            )

        # Increment view count
        db.knowledge_articles.update_one(
            {"id": article_id}, {"$inc": {"view_count": 1}}
        )
        article["view_count"] = article.get("view_count", 0) + 1

        # Add comment count
        article["comment_count"] = db.learning_comments.count_documents(
            {"content_type": "knowledge", "content_id": article_id}
        )

        return {"success": True, "article": article}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting knowledge article: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/topics/{topic_id}/knowledge", response_model=dict)
async def create_knowledge_article(
    topic_id: str,
    request: KnowledgeArticleCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create knowledge article

    - WordAI Team: Always allowed
    - Community users: Allowed (auto-published)
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if topic exists
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # Determine source type
        user_email = current_user.get("email", "")
        source_type = (
            ContentSourceType.WORDAI_TEAM
            if user_email == WORDAI_TEAM_EMAIL
            else ContentSourceType.COMMUNITY
        )

        # Generate article ID
        import uuid

        article_id = str(uuid.uuid4())

        # Get language from request (default to 'vi')
        language = getattr(request, "language", "vi")

        # Prepare multilang dictionaries
        title_multilang = {language: request.title}
        content_multilang = {language: request.content}
        excerpt_multilang = {language: request.excerpt or request.content[:200]}

        # Create article
        now = datetime.utcnow()
        article = {
            "id": article_id,
            "topic_id": topic_id,
            "category_id": topic["category_id"],
            "title": request.title,  # Default language title for backward compatibility
            "content": request.content,  # Default language content for backward compatibility
            "excerpt": request.excerpt or request.content[:200],
            "title_multilang": title_multilang,
            "content_multilang": content_multilang,
            "excerpt_multilang": excerpt_multilang,
            "available_languages": [language],
            "source_type": source_type.value,
            "created_by": current_user["uid"],
            "author_name": current_user.get(
                "name", current_user.get("email", "Unknown")
            ),
            "difficulty": (
                request.difficulty.value
                if request.difficulty
                else ContentDifficulty.BEGINNER.value
            ),
            "tags": request.tags,
            "view_count": 0,
            "like_count": 0,
            "is_published": request.is_published,
            "is_featured": False,
            "created_at": now,
            "updated_at": now,
            "published_at": now if request.is_published else None,
        }

        db.knowledge_articles.insert_one(article)

        article["comment_count"] = 0
        del article["_id"]

        logger.info(
            f"✅ Created knowledge article: {article_id} by {source_type.value}"
        )

        return {"success": True, "article": article}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating knowledge article: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/knowledge/{article_id}", response_model=dict)
async def update_knowledge_article(
    article_id: str,
    request: KnowledgeArticleUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update knowledge article

    - WordAI Team: Can edit ANY article
    - Community users: Can only edit OWN articles
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get article
        article = db.knowledge_articles.find_one({"id": article_id})
        if not article:
            raise HTTPException(
                status_code=404, detail=f"Article '{article_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = article["created_by"] == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only edit your own articles"
            )

        # Build update data
        update_data = {}
        language_update = None

        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                if field == "language":
                    language_update = value
                elif field in ["title", "content", "excerpt"]:
                    # Will handle multilang updates separately
                    continue
                elif isinstance(value, ContentDifficulty):
                    update_data[field] = value.value
                else:
                    update_data[field] = value

        # Handle multilingual updates
        if language_update:
            # Get current multilang fields
            title_multilang = article.get("title_multilang", {})
            content_multilang = article.get("content_multilang", {})
            excerpt_multilang = article.get("excerpt_multilang", {})

            # Update specific language
            if request.title:
                title_multilang[language_update] = request.title
                update_data["title_multilang"] = title_multilang
                update_data["title"] = (
                    request.title
                )  # Update default for backward compatibility

            if request.content:
                content_multilang[language_update] = request.content
                update_data["content_multilang"] = content_multilang
                update_data["content"] = (
                    request.content
                )  # Update default for backward compatibility

            if request.excerpt:
                excerpt_multilang[language_update] = request.excerpt
                update_data["excerpt_multilang"] = excerpt_multilang
                update_data["excerpt"] = (
                    request.excerpt
                )  # Update default for backward compatibility

            # Update available languages
            available_languages = list(set(title_multilang.keys()))
            update_data["available_languages"] = available_languages
        else:
            # Legacy update without language specified - update default language (vi)
            if request.title:
                title_multilang = article.get("title_multilang", {})
                title_multilang["vi"] = request.title
                update_data["title"] = request.title
                update_data["title_multilang"] = title_multilang

            if request.content:
                content_multilang = article.get("content_multilang", {})
                content_multilang["vi"] = request.content
                update_data["content"] = request.content
                update_data["content_multilang"] = content_multilang

            if request.excerpt:
                excerpt_multilang = article.get("excerpt_multilang", {})
                excerpt_multilang["vi"] = request.excerpt
                update_data["excerpt"] = request.excerpt
                update_data["excerpt_multilang"] = excerpt_multilang

        if update_data:
            update_data["updated_at"] = datetime.utcnow()

            db.knowledge_articles.update_one({"id": article_id}, {"$set": update_data})

        # Get updated article
        updated = db.knowledge_articles.find_one({"id": article_id}, {"_id": 0})
        if updated:
            updated["comment_count"] = db.learning_comments.count_documents(
                {"content_type": "knowledge", "content_id": article_id}
            )

        logger.info(f"✅ Updated knowledge article: {article_id}")

        return {"success": True, "article": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating knowledge article: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge/{article_id}", response_model=dict)
async def delete_knowledge_article(
    article_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete knowledge article

    - WordAI Team: Can delete ANY article
    - Community users: Can only delete OWN articles
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get article
        article = db.knowledge_articles.find_one({"id": article_id})
        if not article:
            raise HTTPException(
                status_code=404, detail=f"Article '{article_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = article["created_by"] == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only delete your own articles"
            )

        # Hard delete (admin can clean up spam)
        db.knowledge_articles.delete_one({"id": article_id})

        # Also delete associated comments
        db.learning_comments.delete_many(
            {"content_type": "knowledge", "content_id": article_id}
        )

        logger.info(f"✅ Deleted knowledge article: {article_id}")

        return {
            "success": True,
            "message": f"Article '{article_id}' deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting knowledge article: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CODE TEMPLATES (Updated for Learning System) ====================


@router.get("/topics/{topic_id}/templates", response_model=dict)
async def list_topic_templates(
    topic_id: str,
    source_type: Optional[ContentSourceType] = Query(
        None, description="Filter by source"
    ),
    difficulty: Optional[ContentDifficulty] = Query(
        None, description="Filter by difficulty"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get code templates in a topic (public endpoint)

    - **source_type**: Filter by wordai_team/community
    - **difficulty**: Filter by beginner/intermediate/advanced
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Build query
        query = {"topic_id": topic_id, "is_published": True}
        if source_type:
            query["source_type"] = source_type.value
        if difficulty:
            query["difficulty"] = difficulty.value

        # Get total count
        total = db.code_templates.count_documents(query)

        # Get templates
        skip = (page - 1) * limit
        templates = list(
            db.code_templates.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        # Add comment counts
        for template in templates:
            template["comment_count"] = db.learning_comments.count_documents(
                {
                    "content_type": "template",
                    "content_id": template.get("id", str(template.get("_id"))),
                }
            )

        return {
            "success": True,
            "templates": templates,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/topics/{topic_id}/templates", response_model=dict)
async def create_template(
    topic_id: str,
    request: TemplateCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create code template

    - WordAI Team: Always allowed
    - Community users: Allowed (auto-published)
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if topic exists
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # Determine source type
        user_email = current_user.get("email", "")
        source_type = (
            ContentSourceType.WORDAI_TEAM
            if user_email == WORDAI_TEAM_EMAIL
            else ContentSourceType.COMMUNITY
        )

        # Generate template ID
        import uuid

        template_id = str(uuid.uuid4())

        # Create template
        now = datetime.utcnow()
        template = {
            "id": template_id,
            "topic_id": topic_id,
            "category_id": topic["category_id"],
            "title": request.title,
            "programming_language": request.programming_language,
            "code": request.code,
            "description": request.description,
            "difficulty": (
                request.difficulty.value
                if request.difficulty
                else ContentDifficulty.BEGINNER.value
            ),
            "tags": request.tags,
            "source_type": source_type.value,
            "created_by": current_user["uid"],
            "author_name": current_user.get(
                "name", current_user.get("email", "Unknown")
            ),
            "metadata": {
                "author": current_user.get("name", "Community"),
                "version": "1.0",
                "usage_count": 0,
                "view_count": 0,
                "dependencies": [],
            },
            "like_count": 0,
            "is_published": request.is_published,
            "is_featured": False,
            "created_at": now,
            "updated_at": now,
        }

        db.code_templates.insert_one(template)

        template["comment_count"] = 0
        del template["_id"]

        logger.info(f"✅ Created template: {template_id} by {source_type.value}")

        return {"success": True, "template": template}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}", response_model=dict)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update code template

    - WordAI Team: Can edit ANY template
    - Community users: Can only edit OWN templates
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get template
        template = db.code_templates.find_one({"id": template_id})
        if not template:
            raise HTTPException(
                status_code=404, detail=f"Template '{template_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = template.get("created_by") == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only edit your own templates"
            )

        # Build update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, ContentDifficulty):
                    update_data[field] = value.value
                else:
                    update_data[field] = value

        if update_data:
            update_data["updated_at"] = datetime.utcnow()

            db.code_templates.update_one({"id": template_id}, {"$set": update_data})

        # Get updated template
        updated = db.code_templates.find_one({"id": template_id}, {"_id": 0})
        if updated:
            updated["comment_count"] = db.learning_comments.count_documents(
                {"content_type": "template", "content_id": template_id}
            )

        logger.info(f"✅ Updated template: {template_id}")

        return {"success": True, "template": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}", response_model=dict)
async def delete_template(
    template_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete code template

    - WordAI Team: Can delete ANY template
    - Community users: Can only delete OWN templates
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get template
        template = db.code_templates.find_one({"id": template_id})
        if not template:
            raise HTTPException(
                status_code=404, detail=f"Template '{template_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = template.get("created_by") == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only delete your own templates"
            )

        # Hard delete
        db.code_templates.delete_one({"id": template_id})

        # Also delete associated comments
        db.learning_comments.delete_many(
            {"content_type": "template", "content_id": template_id}
        )

        logger.info(f"✅ Deleted template: {template_id}")

        return {
            "success": True,
            "message": f"Template '{template_id}' deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CODE EXERCISES (Updated for Learning System) ====================


@router.get("/topics/{topic_id}/exercises", response_model=dict)
async def list_topic_exercises(
    topic_id: str,
    source_type: Optional[ContentSourceType] = Query(
        None, description="Filter by source"
    ),
    difficulty: Optional[ContentDifficulty] = Query(
        None, description="Filter by difficulty"
    ),
    grading_type: Optional[str] = Query(None, description="Filter by grading type"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get code exercises in a topic (public endpoint)

    - **source_type**: Filter by wordai_team/community
    - **difficulty**: Filter by beginner/intermediate/advanced
    - **grading_type**: Filter by test_cases/ai_grading/manual
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Build query
        query = {"topic_id": topic_id, "is_published": True}
        if source_type:
            query["source_type"] = source_type.value
        if difficulty:
            query["difficulty"] = difficulty.value
        if grading_type:
            query["grading_type"] = grading_type

        # Get total count
        total = db.code_exercises.count_documents(query)

        # Get exercises (without sample_solution)
        skip = (page - 1) * limit
        exercises = list(
            db.code_exercises.find(
                query, {"_id": 0, "sample_solution": 0}  # Don't expose sample solution
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        # Add comment counts and metadata
        for exercise in exercises:
            exercise["comment_count"] = db.learning_comments.count_documents(
                {
                    "content_type": "exercise",
                    "content_id": exercise.get("id", str(exercise.get("_id"))),
                }
            )

            # Show only public test cases
            if "test_cases" in exercise:
                exercise["test_cases"] = [
                    tc
                    for tc in exercise["test_cases"]
                    if not tc.get("is_hidden", False)
                ]

        return {
            "success": True,
            "exercises": exercises,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error listing exercises: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/topics/{topic_id}/exercises", response_model=dict)
async def create_exercise(
    topic_id: str,
    request: ExerciseCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create code exercise

    - WordAI Team: Always allowed
    - Community users: Allowed (auto-published)
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Check if topic exists
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

        # Determine source type
        user_email = current_user.get("email", "")
        source_type = (
            ContentSourceType.WORDAI_TEAM
            if user_email == WORDAI_TEAM_EMAIL
            else ContentSourceType.COMMUNITY
        )

        # Generate exercise ID
        import uuid

        exercise_id = str(uuid.uuid4())

        # Create exercise
        now = datetime.utcnow()
        exercise = {
            "id": exercise_id,
            "topic_id": topic_id,
            "category_id": topic["category_id"],
            "title": request.title,
            "description": request.description,
            "programming_language": request.programming_language,
            "difficulty": request.difficulty.value,
            "points": request.points,
            "grading_type": request.grading_type.value,
            "sample_solution": request.sample_solution,  # For AI grading
            "test_cases": request.test_cases or [],
            "starter_code": request.starter_code,
            "hints": request.hints,
            "tags": request.tags,
            "source_type": source_type.value,
            "created_by": current_user["uid"],
            "author_name": current_user.get(
                "name", current_user.get("email", "Unknown")
            ),
            "metadata": {
                "submission_count": 0,
                "completion_rate": 0.0,
                "average_score": 0.0,
                "view_count": 0,
            },
            "like_count": 0,
            "is_published": request.is_published,
            "is_featured": False,
            "created_at": now,
            "updated_at": now,
        }

        db.code_exercises.insert_one(exercise)

        # Remove sensitive data from response
        response_exercise = {**exercise}
        del response_exercise["_id"]
        if "sample_solution" in response_exercise:
            del response_exercise["sample_solution"]
        response_exercise["comment_count"] = 0

        logger.info(f"✅ Created exercise: {exercise_id} by {source_type.value}")

        return {"success": True, "exercise": response_exercise}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating exercise: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/exercises/{exercise_id}", response_model=dict)
async def update_exercise(
    exercise_id: str,
    request: ExerciseUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update code exercise

    - WordAI Team: Can edit ANY exercise
    - Community users: Can only edit OWN exercises
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get exercise
        exercise = db.code_exercises.find_one({"id": exercise_id})
        if not exercise:
            raise HTTPException(
                status_code=404, detail=f"Exercise '{exercise_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = exercise.get("created_by") == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only edit your own exercises"
            )

        # Build update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, (ContentDifficulty, GradingType)):
                    update_data[field] = value.value
                else:
                    update_data[field] = value

        if update_data:
            update_data["updated_at"] = datetime.utcnow()

            db.code_exercises.update_one({"id": exercise_id}, {"$set": update_data})

        # Get updated exercise (without sample_solution for non-admin)
        projection = {"_id": 0}
        if not is_admin:
            projection["sample_solution"] = 0

        updated = db.code_exercises.find_one({"id": exercise_id}, projection)
        if updated:
            updated["comment_count"] = db.learning_comments.count_documents(
                {"content_type": "exercise", "content_id": exercise_id}
            )

        logger.info(f"✅ Updated exercise: {exercise_id}")

        return {"success": True, "exercise": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating exercise: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/exercises/{exercise_id}", response_model=dict)
async def delete_exercise(
    exercise_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete code exercise

    - WordAI Team: Can delete ANY exercise
    - Community users: Can only delete OWN exercises
    """
    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get exercise
        exercise = db.code_exercises.find_one({"id": exercise_id})
        if not exercise:
            raise HTTPException(
                status_code=404, detail=f"Exercise '{exercise_id}' not found"
            )

        # Check permissions
        user_email = current_user.get("email", "")
        is_admin = user_email == WORDAI_TEAM_EMAIL
        is_owner = exercise.get("created_by") == current_user["uid"]

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=403, detail="You can only delete your own exercises"
            )

        # Hard delete
        db.code_exercises.delete_one({"id": exercise_id})

        # Also delete associated comments and submissions
        db.learning_comments.delete_many(
            {"content_type": "exercise", "content_id": exercise_id}
        )
        db.code_submissions.delete_many({"exercise_id": exercise_id})

        logger.info(f"✅ Deleted exercise: {exercise_id}")

        return {
            "success": True,
            "message": f"Exercise '{exercise_id}' deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting exercise: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
