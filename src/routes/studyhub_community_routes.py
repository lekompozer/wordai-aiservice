"""
StudyHub Community Routes - API endpoints for marketplace community subjects

Endpoints:
- GET  /api/marketplace/community-subjects - List community subjects
- GET  /api/marketplace/community-subjects/{slug} - Get subject detail
- GET  /api/marketplace/community-subjects/{slug}/courses - Get courses in subject
- POST /api/subjects/{id}/publish-to-community - Publish subject to community
- POST /api/subjects/{id}/unpublish - Unpublish from community
- PUT  /api/subjects/{id}/marketplace - Update marketplace info
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from src.services.studyhub_community_manager import StudyHubCommunityManager
from src.models.studyhub_community_models import (
    CommunitySubjectsResponse,
    CommunitySubjectDetail,
    CoursesInSubjectResponse,
    PublishToCommunityRequest,
    UpdateMarketplaceInfoRequest
)
from src.auth.jwt_bearer import get_current_user

router = APIRouter()


@router.get(
    "/marketplace/community-subjects",
    response_model=CommunitySubjectsResponse,
    summary="Get Community Subjects",
    description="List all community subjects with filtering and pagination"
)
async def get_community_subjects(
    category: Optional[str] = Query(None, description="Filter by category (it, business, finance, etc.)"),
    search: Optional[str] = Query(None, description="Text search in title"),
    is_featured: Optional[bool] = Query(None, description="Filter featured subjects only"),
    sort_by: str = Query("display_order", description="Sort by: display_order, total_courses, total_students"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    **API-39: GET /marketplace/community-subjects**
    
    Get list of community subjects for marketplace browsing.
    
    **Query Parameters:**
    - `category`: Filter by category (optional)
    - `search`: Text search (optional)
    - `is_featured`: Show only featured subjects (optional)
    - `sort_by`: Sort field (default: display_order)
    - `skip`: Pagination offset (default: 0)
    - `limit`: Max results (default: 20, max: 100)
    
    **Returns:**
    ```json
    {
        "subjects": [
            {
                "id": "python-programming",
                "slug": "python-programming",
                "title": "Python Programming",
                "title_vi": "Lập trình Python",
                "category": "it",
                "icon": "🐍",
                "total_courses": 25,
                "total_students": 1500
            }
        ],
        "total": 150,
        "skip": 0,
        "limit": 20
    }
    ```
    """
    try:
        manager = StudyHubCommunityManager()
        result = await manager.get_community_subjects(
            category=category,
            search=search,
            is_featured=is_featured,
            sort_by=sort_by,
            skip=skip,
            limit=limit
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/marketplace/community-subjects/{slug}",
    response_model=CommunitySubjectDetail,
    summary="Get Community Subject Detail",
    description="Get detailed info about a community subject with top courses preview"
)
async def get_community_subject_detail(slug: str):
    """
    **API-40: GET /marketplace/community-subjects/{slug}**
    
    Get detailed information about a specific community subject.
    Includes top 3 courses preview.
    
    **Path Parameters:**
    - `slug`: Community subject slug (e.g., "python-programming")
    
    **Returns:**
    ```json
    {
        "id": "python-programming",
        "slug": "python-programming",
        "title": "Python Programming",
        "total_courses": 25,
        "top_courses": [
            {
                "id": "507f1f77bcf86cd799439011",
                "title": "Python for Beginners",
                "thumbnail_url": "https://...",
                "creator_name": "Mr. A",
                "total_students": 500,
                "average_rating": 4.5
            }
        ]
    }
    ```
    """
    try:
        manager = StudyHubCommunityManager()
        result = await manager.get_community_subject_detail(slug)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Community subject not found: {slug}")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/marketplace/community-subjects/{slug}/courses",
    response_model=CoursesInSubjectResponse,
    summary="Get Courses in Community Subject",
    description="Get all published courses under a community subject"
)
async def get_courses_in_subject(
    slug: str,
    sort_by: str = Query("popularity", description="Sort by: popularity, rating, newest"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    **API-41: GET /marketplace/community-subjects/{slug}/courses**
    
    Get all published courses (subjects) in a community subject.
    
    **Path Parameters:**
    - `slug`: Community subject slug
    
    **Query Parameters:**
    - `sort_by`: Sort by (popularity, rating, newest) - default: popularity
    - `skip`: Pagination offset
    - `limit`: Max results (max: 100)
    
    **Returns:**
    ```json
    {
        "courses": [
            {
                "id": "507f1f77bcf86cd799439011",
                "title": "Python for Beginners - by Mr. A",
                "creator_name": "Mr. A",
                "total_students": 500,
                "average_rating": 4.5,
                "price": 299000,
                "organization": "ABC Academy"
            }
        ],
        "total": 25,
        "community_subject": {
            "id": "python-programming",
            "title": "Python Programming"
        }
    }
    ```
    """
    try:
        manager = StudyHubCommunityManager()
        result = await manager.get_courses_in_subject(
            slug=slug,
            sort_by=sort_by,
            skip=skip,
            limit=limit
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/subjects/{subject_id}/publish-to-community",
    summary="Publish Subject to Community",
    description="Publish a subject (course) to community marketplace"
)
async def publish_to_community(
    subject_id: str,
    request: PublishToCommunityRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    **API-42: POST /subjects/{id}/publish-to-community**
    
    Publish a subject to the community marketplace.
    Links the subject to a community subject category.
    
    **Authentication:** Required (JWT)
    
    **Path Parameters:**
    - `subject_id`: StudyHub subject ID
    
    **Request Body:**
    ```json
    {
        "community_subject_id": "python-programming"
    }
    ```
    
    **Returns:**
    Updated subject with `marketplace_status: "published"`
    
    **Permissions:**
    - Must be the creator of the subject
    - Subject must not already be published
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        manager = StudyHubCommunityManager()
        result = await manager.publish_subject_to_community(
            subject_id=subject_id,
            community_subject_id=request.community_subject_id,
            user_id=user_id
        )
        
        return {
            "message": "Subject published to community successfully",
            "subject": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/subjects/{subject_id}/unpublish",
    summary="Unpublish Subject from Community",
    description="Remove a subject from community marketplace"
)
async def unpublish_from_community(
    subject_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    **API-43: POST /subjects/{id}/unpublish**
    
    Unpublish a subject from the community marketplace.
    Sets status back to "draft".
    
    **Authentication:** Required (JWT)
    
    **Path Parameters:**
    - `subject_id`: StudyHub subject ID
    
    **Returns:**
    Updated subject with `marketplace_status: "draft"`
    
    **Permissions:**
    - Must be the creator of the subject
    - Subject must be currently published
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        manager = StudyHubCommunityManager()
        result = await manager.unpublish_subject(
            subject_id=subject_id,
            user_id=user_id
        )
        
        return {
            "message": "Subject unpublished from community successfully",
            "subject": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/subjects/{subject_id}/marketplace",
    summary="Update Marketplace Info",
    description="Update marketplace-specific information for a subject"
)
async def update_marketplace_info(
    subject_id: str,
    request: UpdateMarketplaceInfoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    **API-44: PUT /subjects/{id}/marketplace**
    
    Update marketplace metadata for a subject.
    
    **Authentication:** Required (JWT)
    
    **Path Parameters:**
    - `subject_id`: StudyHub subject ID
    
    **Request Body:**
    ```json
    {
        "organization": "ABC Academy",
        "is_verified_organization": true
    }
    ```
    
    **Returns:**
    Updated subject document
    
    **Permissions:**
    - Must be the creator of the subject
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        manager = StudyHubCommunityManager()
        result = await manager.update_marketplace_info(
            subject_id=subject_id,
            user_id=user_id,
            organization=request.organization,
            is_verified_organization=request.is_verified_organization
        )
        
        return {
            "message": "Marketplace info updated successfully",
            "subject": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
