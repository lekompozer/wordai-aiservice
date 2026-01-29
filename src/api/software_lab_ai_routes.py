"""
Software Lab AI Routes
10 endpoints for AI Code Assistant features using Redis Worker Pattern
"""

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import uuid
import json

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.services.points_service import get_points_service
from src.models.software_lab_ai_models import (
    GenerateCodeRequest,
    GenerateCodeResponse,
    ExplainCodeRequest,
    ExplainCodeResponse,
    TransformCodeRequest,
    TransformCodeResponse,
    AnalyzeArchitectureRequest,
    AnalyzeArchitectureResponse,
    ScaffoldProjectRequest,
    ScaffoldProjectResponse,
    JobStatusResponse,
)
from src.queue.queue_manager import QueueManager, set_job_status, get_job_status

router = APIRouter(prefix="/software-lab/ai", tags=["Software Lab AI"])

# Points cost for all AI features
POINTS_COST_AI_CODE = 2

# ========================================
# FEATURE 1: GENERATE CODE
# ========================================


@router.post("/generate", response_model=GenerateCodeResponse)
async def start_generate_code(
    request: GenerateCodeRequest, user: dict = Depends(get_current_user)
):
    """
    Start AI code generation job.
    Returns job_id for status polling.
    Cost: 2 points
    """
    user_id = user["uid"]
    points_service = get_points_service()

    # Check and deduct points using points_service
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AI_CODE,
            service="ai_code_generate",
            description=f"Generate code: {request.query[:50]}...",
        )
    except Exception as e:
        # Check if insufficient points error
        if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient points. Required: {POINTS_COST_AI_CODE}, Available: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create job
    job_id = f"gen_{uuid.uuid4().hex[:12]}"

    # Enqueue to Redis
    queue = QueueManager(queue_name="software_lab_generate_code")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "project_id": request.project_id,
        "user_query": request.user_query,
        "target_file_id": request.target_file_id,
        "target_path": request.target_path,
        "insert_at_line": request.insert_at_line,
        "context_file_ids": request.context_file_ids,
        "include_all_files": request.include_all_files,
    }

    # Set initial status in Redis
    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    # Push to queue
    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))

    await queue.disconnect()

    return GenerateCodeResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=2,
        new_balance=balance,
    )


@router.get("/generate/{job_id}/status", response_model=GenerateCodeResponse)
async def get_generate_code_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll status of code generation job"""
    queue = QueueManager(queue_name="software_lab_generate_code")
    await queue.connect()

    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return GenerateCodeResponse(
        success=True,
        job_id=job_id,
        status=job.get("status"),
        generated_code=job.get("generated_code"),
        explanation=job.get("explanation"),
        suggested_file=job.get("suggested_file"),
        tokens=job.get("tokens"),
        points_deducted=2,
        error=job.get("error"),
        message=job.get("message"),
    )


# ========================================
# FEATURE 2: EXPLAIN CODE
# ========================================


@router.post("/explain", response_model=ExplainCodeResponse)
async def start_explain_code(
    request: ExplainCodeRequest, user: dict = Depends(get_current_user)
):
    """
    Start AI code explanation job.
    Returns annotated code with inline comments.
    Cost: 2 points
    """
    user_id = user["uid"]
    points_service = get_points_service()

    # Check and deduct points using points_service
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AI_CODE,
            service="ai_code_explain",
            description=f"Explain code: file {request.file_id}",
        )
    except Exception as e:
        if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient points. Required: {POINTS_COST_AI_CODE}, Available: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create job
    job_id = f"exp_{uuid.uuid4().hex[:12]}"

    # Enqueue to Redis
    queue = QueueManager(queue_name="software_lab_explain_code")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "project_id": request.project_id,
        "file_id": request.file_id,
        "selection": request.selection,
        "question": request.question,
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return ExplainCodeResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=2,
        new_balance=transaction.balance_after,
    )


@router.get("/explain/{job_id}/status", response_model=ExplainCodeResponse)
async def get_explain_code_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll status of code explanation job"""
    queue = QueueManager(queue_name="software_lab_explain_code")
    await queue.connect()

    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return ExplainCodeResponse(
        success=True,
        job_id=job_id,
        status=job.get("status"),
        file_path=job.get("file_path"),
        annotated_code=job.get("annotated_code"),
        explanation=job.get("explanation"),
        key_concepts=job.get("key_concepts"),
        code_snippets=job.get("code_snippets"),
        tokens=job.get("tokens"),
        points_deducted=2,
        error=job.get("error"),
        message=job.get("message"),
    )


# ========================================
# FEATURE 3: TRANSFORM CODE
# ========================================


@router.post("/transform", response_model=TransformCodeResponse)
async def start_transform_code(
    request: TransformCodeRequest, user: dict = Depends(get_current_user)
):
    """
    Start AI code transformation job.
    Refactor, optimize, convert, fix, or add features.
    Cost: 2 points
    """
    user_id = user["uid"]
    points_service = get_points_service()

    # Check and deduct points using points_service
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AI_CODE,
            service="ai_code_transform",
            description=f"Transform code: {request.transformation_type}",
        )
    except Exception as e:
        if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient points. Required: {POINTS_COST_AI_CODE}, Available: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create job
    job_id = f"trf_{uuid.uuid4().hex[:12]}"

    # Enqueue to Redis
    queue = QueueManager(queue_name="software_lab_transform_code")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "project_id": request.project_id,
        "file_id": request.file_id,
        "transformation": request.transformation,
        "instruction": request.instruction,
        "selection": request.selection,
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return TransformCodeResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=2,
        new_balance=transaction.balance_after,
    )


@router.get("/transform/{job_id}/status", response_model=TransformCodeResponse)
async def get_transform_code_status(
    job_id: str, user: dict = Depends(get_current_user)
):
    """Poll status of code transformation job"""
    queue = QueueManager(queue_name="software_lab_transform_code")
    await queue.connect()

    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return TransformCodeResponse(
        success=True,
        job_id=job_id,
        status=job.get("status"),
        transformed_code=job.get("transformed_code"),
        changes_summary=job.get("changes_summary"),
        diff=job.get("diff"),
        tokens=job.get("tokens"),
        points_deducted=2,
        error=job.get("error"),
        message=job.get("message"),
    )


# ========================================
# FEATURE 4: ANALYZE ARCHITECTURE
# ========================================


@router.post("/analyze-architecture", response_model=AnalyzeArchitectureResponse)
async def start_analyze_architecture(
    request: AnalyzeArchitectureRequest, user: dict = Depends(get_current_user)
):
    """
    Start AI architecture analysis job.
    Generates complete system architecture from requirements.
    Cost: 2 points
    """
    user_id = user["uid"]
    points_service = get_points_service()

    # Check and deduct points using points_service
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AI_CODE,
            service="ai_architecture_analyze",
            description=f"Analyze architecture: {request.requirements[:50]}...",
        )
    except Exception as e:
        if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient points. Required: {POINTS_COST_AI_CODE}, Available: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create job
    job_id = f"arch_{uuid.uuid4().hex[:12]}"

    # Enqueue to Redis
    queue = QueueManager(queue_name="software_lab_analyze_architecture")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "project_id": request.project_id,
        "requirements": request.requirements,
        "tech_stack": request.tech_stack.dict() if request.tech_stack else {},
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return AnalyzeArchitectureResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=2,
        new_balance=transaction.balance_after,
    )


@router.get(
    "/analyze-architecture/{job_id}/status", response_model=AnalyzeArchitectureResponse
)
async def get_analyze_architecture_status(
    job_id: str, user: dict = Depends(get_current_user)
):
    """Poll status of architecture analysis job"""
    queue = QueueManager(queue_name="software_lab_analyze_architecture")
    await queue.connect()

    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return AnalyzeArchitectureResponse(
        success=True,
        job_id=job_id,
        status=job.get("status"),
        architecture_id=job.get("architecture_id"),
        architecture=job.get("architecture"),
        tokens=job.get("tokens"),
        points_deducted=2,
        error=job.get("error"),
        message=job.get("message"),
    )


# ========================================
# FEATURE 5: SCAFFOLD PROJECT
# ========================================


@router.post("/scaffold-project", response_model=ScaffoldProjectResponse)
async def start_scaffold_project(
    request: ScaffoldProjectRequest, user: dict = Depends(get_current_user)
):
    """
    Start project scaffolding job.
    Generates complete project structure from architecture.
    Cost: 2 points
    """
    user_id = user["uid"]
    points_service = get_points_service()

    # Check and deduct points using points_service
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AI_CODE,
            service="ai_scaffold_project",
            description=f"Scaffold project: architecture {request.architecture_id}",
        )
    except Exception as e:
        if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient points. Required: {POINTS_COST_AI_CODE}, Available: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(e))

    # Create job
    job_id = f"scf_{uuid.uuid4().hex[:12]}"

    # Enqueue to Redis
    queue = QueueManager(queue_name="software_lab_scaffold_project")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "project_id": request.project_id,
        "architecture_id": request.architecture_id,
        "include_comments": request.include_comments,
        "file_types": request.file_types,
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return ScaffoldProjectResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=2,
        new_balance=transaction.balance_after,
    )


@router.get("/scaffold-project/{job_id}/status", response_model=ScaffoldProjectResponse)
async def get_scaffold_project_status(
    job_id: str, user: dict = Depends(get_current_user)
):
    """Poll status of project scaffolding job"""
    queue = QueueManager(queue_name="software_lab_scaffold_project")
    await queue.connect()

    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return ScaffoldProjectResponse(
        success=True,
        job_id=job_id,
        status=job.get("status"),
        files_created=job.get("files_created"),
        folders_created=job.get("folders_created"),
        summary=job.get("summary"),
        tokens=job.get("tokens"),
        points_deducted=2,
        error=job.get("error"),
        message=job.get("message"),
    )
