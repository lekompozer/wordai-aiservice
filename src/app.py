"""
Main FastAPI application factory and startup configuration
"""

import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from datetime import datetime
import asyncio
import os
import logging

from src.core.config import APP_CONFIG
from src.api.health_routes import router as health_router

# ✅ COMMENTED: Chat routes - Firebase auth dependency
# from src.api.chat_routes import router as chat_router
from src.api.real_estate_routes import router as real_estate_router
from src.api.ocr_routes import router as ocr_router
from src.api.loan_routes import router as loan_router

# ✅ ADDED: Document Processing API for Phase 1
from src.api.document_processing_routes import router as document_processing_router

# ✅ ADDED: Document Generation API for AI-powered document creation - KEEP (uses WordAI credentials)
from src.api.document_generation import router as document_generation_router

# ✅ ADDED: Quote Generation API with AI Gemini Pro 2.5
from src.api.quote_generation import router as quote_generation_router

# ✅ ADDED: Quote Settings API for managing user quote preferences
from src.routes.quote_settings import router as quote_settings_router

# ✅ ADDED: Enhanced Template Upload API for DOCX template processing with AI
from src.routes.enhanced_template_routes import router as enhanced_template_router

# ✅ ADDED: AI Sales Agent for loan consultation
from src.ai_sales_agent.api.routes import router as ai_sales_agent_router

# ✅ ADDED: Unified Chat System for multi-industry support
from src.api.unified_chat_routes import router as unified_chat_router

# ✅ ADDED: Conversation Analysis API for remarketing insights with Google Gemini
from src.api.conversation_analysis_routes import router as conversation_analysis_router

# ✅ ADDED: Admin API for Company Data Management - Modular Structure
from src.api.admin.company_routes import router as company_router
from src.api.admin.file_routes import router as file_router
from src.api.admin.products_services_routes import router as products_services_router
from src.api.admin.image_routes import router as image_router
from src.api.admin.task_status_routes import router as task_status_router

# ✅ ADDED: Admin Template Management for System Templates
from src.routes.admin_template_routes import router as admin_template_router

# ✅ ADDED: Company Context and User History APIs for Optimized Chat
from src.api.admin.company_context_routes import router as company_context_router
from src.api.user_history_routes import router as user_history_router

# ✅ ADDED: AI Extraction API for structured data extraction
from src.api.extraction_routes import router as extraction_router

# ✅ ADDED: Hybrid Search Strategy for enhanced callbacks, search & CRUD
from src.api.hybrid_strategy_router import main_router as hybrid_strategy_router

# ✅ ADDED: Internal CORS management for chat-plugin dynamic domains
from src.api.internal_cors_routes import router as internal_cors_router

# ✅ ADDED: Dynamic CORS middleware for chat-plugin support
from src.middleware.dynamic_cors import DynamicCORSMiddleware

# ✅ ADDED: Hybrid Search API for direct search testing
from src.api.hybrid_search.hybrid_search_routes import router as hybrid_search_router

# ✅ ADDED: Firebase Authentication API for user management
from src.api.auth_routes import router as auth_router

# Authentication API
# from src.api.auth_routes import router as auth_router

# ✅ COMMENTED: HTML to DOCX Conversion API - Firebase auth dependency
# from src.api.conversion_routes import router as conversion_router

# ✅ UNCOMMENTED: Document Settings and History APIs - needed by frontend
from src.api.document_settings_routes import router as document_settings_router
from src.api.documents_history_routes import router as documents_history_router

# ✅ ADDED: Simple File Management API for basic file upload & folder CRUD
from src.api.simple_file_routes import router as simple_file_router

# ✅ ADDED: AI Content Edit API for Tiptap editor with multiple AI providers
from src.api.ai_content_edit import router as ai_content_edit_router

# ✅ ADDED: AI Chat API for streaming chat with file context
from src.api.ai_chat import router as ai_chat_router

# ✅ ADDED: Document Editor API for document management with auto-save
from src.api.document_editor_routes import router as document_editor_router

# ✅ ADDED: Library Files API for Type 3 files (templates, guides, references, resources)
from src.api.library_routes import router as library_router

# ✅ ADDED: Document Editor API for document management with auto-save
from src.api.document_editor_routes import router as document_editor_router

# Global startup time for uptime tracking
startup_time = time.time()

# Global worker management
background_workers = {}

# ✅ Initialize Firebase Admin SDK IMMEDIATELY (before any route definitions)
print("🔥 Initializing Firebase Admin SDK globally...")
try:
    from src.config.firebase_config import FirebaseConfig

    firebase_config = FirebaseConfig()
    print("✅ Firebase Admin SDK initialized globally")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    # Don't raise error - let app continue without Firebase


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ✅ STARTUP/SHUTDOWN: Application lifecycle management
    """
    # ===== STARTUP =====
    print("🚀 Starting AI Chatbot RAG Service...")
    print(
        f"   Environment: {APP_CONFIG.get('debug', False) and 'Development' or 'Production'}"
    )
    print(f"   Host: {APP_CONFIG['host']}")
    print(f"   Port: {APP_CONFIG['port']}")
    print(f"   Base URL: {APP_CONFIG['base_url']}")

    # Initialize global components here if needed
    try:
        # Load documents or initialize services
        await load_documents()

        # ✅ Start background workers
        await start_background_workers()

        print("✅ Application startup completed")
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

    yield

    # ===== SHUTDOWN =====
    print("🛑 Shutting down AI Chatbot RAG Service...")

    # ✅ Shutdown background workers
    await shutdown_background_workers()

    print("✅ Shutdown completed")


async def load_documents():
    """
    ✅ Load documents and initialize services on startup
    """
    global documents
    documents = {}

    try:
        print("📚 Loading documents and initializing services...")

        # Firebase is now initialized in serve.py before app import
        # No need to initialize it here anymore

        # Add any other initialization logic here
        # For example: load vector store, initialize AI providers, etc.

        print("✅ Documents and services loaded successfully")

    except Exception as e:
        print(f"❌ Failed to load documents: {e}")
        raise


async def start_background_workers():
    """
    ✅ Start background workers for queue processing
    """
    try:
        print("🔧 Starting background workers...")

        # ===== START DOCUMENT PROCESSING WORKER (for /upload endpoint) =====
        print("📄 Starting DocumentProcessingWorker for /upload endpoint...")
        from src.workers.document_processing_worker import DocumentProcessingWorker

        doc_worker = DocumentProcessingWorker(
            worker_id="app_doc_worker", poll_interval=2.0  # Poll every 2 seconds
        )

        await doc_worker.initialize()

        # Start worker in background task
        doc_worker_task = asyncio.create_task(doc_worker.run())
        background_workers["document_worker"] = {
            "worker": doc_worker,
            "task": doc_worker_task,
        }

        print("✅ DocumentProcessingWorker started")

        # ===== START EXTRACTION PROCESSING WORKER (Worker 1) =====
        print(
            "🎯 Starting ExtractionProcessingWorker (Worker 1: AI extraction only)..."
        )
        from src.workers.extraction_processing_worker import ExtractionProcessingWorker

        extraction_worker = ExtractionProcessingWorker(
            worker_id="app_extraction_worker", poll_interval=1.0
        )

        await extraction_worker.initialize()

        # Start worker in background task
        extraction_worker_task = asyncio.create_task(extraction_worker.run())
        background_workers["extraction_worker"] = {
            "worker": extraction_worker,
            "task": extraction_worker_task,
        }

        print("✅ ExtractionProcessingWorker started")

        # ===== START STORAGE PROCESSING WORKER (Worker 2) =====
        print(
            "💾 Starting StorageProcessingWorker (Worker 2: Qdrant + callback only)..."
        )
        from src.workers.storage_processing_worker import StorageProcessingWorker

        storage_worker = StorageProcessingWorker(
            worker_id="app_storage_worker", poll_interval=1.0
        )

        await storage_worker.initialize()

        # Start worker in background task
        storage_worker_task = asyncio.create_task(storage_worker.run())
        background_workers["storage_worker"] = {
            "worker": storage_worker,
            "task": storage_worker_task,
        }

        print("✅ StorageProcessingWorker started")
        print("")
        print("🎉 All workers started successfully!")
        print("📋 Worker Architecture:")
        print(
            "   📄 DocumentProcessingWorker → /upload endpoint (DocumentProcessingTask only)"
        )
        print(
            "   🎯 ExtractionProcessingWorker → Worker 1: AI extraction for /process-async"
        )
        print(
            "   💾 StorageProcessingWorker → Worker 2: Qdrant storage + backend callbacks"
        )
        print("   🔄 Flow: API → Worker 1 (AI) → Worker 2 (Storage) → Backend")

    except Exception as e:
        print(f"❌ Failed to start background workers: {e}")
        raise


async def shutdown_background_workers():
    """
    ✅ Shutdown background workers gracefully
    """
    try:
        print("🛑 Shutting down background workers...")

        for worker_name, worker_info in background_workers.items():
            try:
                print(f"   🛑 Stopping {worker_name}...")

                # Shutdown worker
                await worker_info["worker"].shutdown()

                # Cancel task
                worker_info["task"].cancel()
                try:
                    await worker_info["task"]
                except asyncio.CancelledError:
                    pass

                print(f"   ✅ {worker_name} stopped")

            except Exception as worker_error:
                print(f"   ❌ Error stopping {worker_name}: {worker_error}")

        background_workers.clear()
        print("✅ All background workers stopped")

    except Exception as e:
        print(f"❌ Error shutting down workers: {e}")


def create_app() -> FastAPI:
    """
    ✅ FastAPI application factory
    """
    app = FastAPI(
        title="AI Chatbot RAG Service",
        description="Advanced AI-powered chatbot with RAG capabilities, document processing, OCR, and financial services",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if APP_CONFIG["debug"] else None,
        redoc_url="/redoc" if APP_CONFIG["debug"] else None,
    )

    # ===== VALIDATION ERROR HANDLER =====
    logger = logging.getLogger("chatbot")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Log validation errors with full details"""
        logger.error("=" * 80)
        logger.error(f"❌ FASTAPI VALIDATION ERROR (422)")
        logger.error(f"   Path: {request.url.path}")
        logger.error(f"   Method: {request.method}")
        logger.error(
            f"   Content-Type: {request.headers.get('content-type', 'NOT SET')}"
        )

        # Try to get the body - FastAPI may have cached it
        body_str = "Could not read body"
        try:
            # Try to get from exc.body first (available in newer FastAPI versions)
            if hasattr(exc, "body"):
                body_str = (
                    exc.body.decode("utf-8")
                    if isinstance(exc.body, bytes)
                    else str(exc.body)
                )
            else:
                # Fallback: try to read from request (may fail if already consumed)
                body = await request.body()
                body_str = body.decode("utf-8")
        except Exception as e:
            body_str = f"Error reading body: {e}"

        logger.error(f"   Request Body: {body_str}")
        logger.error(f"   Validation Errors ({len(exc.errors())} total):")
        for i, error in enumerate(exc.errors(), 1):
            logger.error(f"      {i}. Location: {error.get('loc', 'unknown')}")
            logger.error(f"         Message: {error.get('msg', 'unknown')}")
            logger.error(f"         Type: {error.get('type', 'unknown')}")
            if "input" in error:
                logger.error(f"         Input: {error['input']}")
        logger.error("=" * 80)

        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    # ===== CORS MIDDLEWARE REMOVED =====
    # CORS is now handled at the bottom of the file based on ENVIRONMENT variable
    # This prevents duplicate CORS middleware that was causing "true, true" headers

    # Dynamic CORS middleware for chat-plugin support (streaming routes only)
    backend_url = APP_CONFIG.get("backend_webhook_url", "http://localhost:8001")
    app.add_middleware(DynamicCORSMiddleware, backend_url=backend_url)

    # ===== SECURITY MIDDLEWARE =====
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add security headers to all responses"""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response

    # ===== DEBUG MIDDLEWARE FOR FILE UPLOADS =====
    @app.middleware("http")
    async def log_file_upload_requests(request: Request, call_next):
        """Log all requests to /api/simple-files/* endpoints"""
        if request.url.path.startswith("/api/simple-files/"):
            print("=" * 80)
            print(f"📥 INCOMING REQUEST TO FILE API")
            print(f"   Method: {request.method}")
            print(f"   Path: {request.url.path}")
            print(f"   Query: {dict(request.query_params)}")
            print(f"   Headers: {dict(request.headers)}")
            print(f"   Client: {request.client.host if request.client else 'unknown'}")
            print("=" * 80)

        response = await call_next(request)

        if request.url.path.startswith("/api/simple-files/"):
            print("=" * 80)
            print(f"📤 OUTGOING RESPONSE FROM FILE API")
            print(f"   Method: {request.method}")
            print(f"   Path: {request.url.path}")
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            print("=" * 80)

        return response

    # ===== REGISTER ROUTERS =====

    # ✅ Authentication endpoints - Firebase auth for user management
    app.include_router(auth_router, tags=["Firebase Authentication"])

    # Health and status endpoints
    app.include_router(health_router, tags=["Health"])

    # ✅ COMMENTED: Chat endpoints - Firebase auth dependency
    # app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])

    # ✅ COMMENTED: Support legacy frontend paths - Firebase auth dependency
    # app.include_router(chat_router, tags=["Chat - Legacy Paths"])

    # Unified Chat System - Multi-industry with intelligent routing
    app.include_router(unified_chat_router, tags=["Unified Chat - Multi-Industry"])

    # Conversation Analysis API - Remarketing insights with Google Gemini
    app.include_router(
        conversation_analysis_router,
        tags=["Conversation Analysis", "Remarketing", "Gemini AI"],
    )

    # Real estate analysis endpoints
    app.include_router(real_estate_router, tags=["Real Estate"])

    # OCR endpoints
    app.include_router(ocr_router, tags=["OCR"])

    # Loan assessment endpoints
    app.include_router(loan_router, tags=["Loan Assessment"])

    # Document processing endpoints
    app.include_router(document_processing_router, tags=["Document Processing"])

    # Quote generation endpoints - New workflow with AI Gemini Pro 2.5
    app.include_router(quote_generation_router, tags=["Quote Generation", "Gemini AI"])

    # Quote settings endpoints - User preferences and configuration
    app.include_router(
        quote_settings_router, tags=["Quote Settings", "User Preferences"]
    )

    # Template upload endpoints - DOCX template processing with AI
    # ✅ Enhanced Template Management API with PDF processing và metadata editing
    app.include_router(
        enhanced_template_router,
        tags=["Template Management", "AI Analysis", "PDF Processing"],
    )

    # ✅ Legacy Template Upload API (kept for backward compatibility)
    # AI Sales Agent endpoints for loan consultation
    app.include_router(
        ai_sales_agent_router,
        prefix="/api/sales-agent",
        tags=["AI Sales Agent - Loan Consultation"],
    )

    # Conversation Analysis API for remarketing insights
    app.include_router(
        conversation_analysis_router,
        prefix="/api/conversation-analysis",
        tags=["Conversation Analysis - Google Gemini"],
    )

    # Admin routers for company data management - Modular Structure
    app.include_router(
        company_router, prefix="/api/admin", tags=["Admin - Company Management"]
    )
    app.include_router(
        file_router, prefix="/api/admin", tags=["Admin - File Management"]
    )
    app.include_router(
        products_services_router,
        prefix="/api/admin",
        tags=["Admin - Products & Services"],
    )
    app.include_router(
        image_router, prefix="/api/admin", tags=["Admin - Image Processing"]
    )
    app.include_router(task_status_router)

    # ✅ ADDED: Admin Template Management for System Templates
    app.include_router(admin_template_router, tags=["Admin - System Templates"])

    # ✅ COMMENTED: HTML to DOCX Conversion API - Firebase auth dependency
    # app.include_router(conversion_router, tags=["Document Conversion"])

    # ✅ RESTORED: Document Settings and History APIs - needed by frontend
    app.include_router(document_settings_router, tags=["Document Settings"])
    app.include_router(documents_history_router, tags=["Documents History"])

    # ✅ ADDED: AI Content Edit API - HTML editing with AI
    app.include_router(ai_content_edit_router, tags=["AI Content Edit"])

    # ✅ ADDED: AI Chat API - Streaming chat with file context
    app.include_router(ai_chat_router, tags=["AI Chat"])

    # ✅ ADDED: Document Editor API - Document management with auto-save
    app.include_router(document_editor_router, tags=["Document Editor"])

    # ✅ ADDED: Company Context and User History APIs
    app.include_router(company_context_router)
    app.include_router(user_history_router)

    # ✅ ADDED: AI Extraction API
    app.include_router(extraction_router, tags=["AI Extraction - Products & Services"])

    # ✅ ADDED: Hybrid Search API for direct testing
    app.include_router(hybrid_search_router, tags=["Hybrid Search API"])

    # ✅ ADDED: Document Generation API for AI-powered document creation - KEEP
    app.include_router(document_generation_router, tags=["Document Generation"])

    # ✅ NEW: Simple File Management API with R2 integration
    app.include_router(simple_file_router, tags=["Simple File Management"])

    # ✅ NEW: Library Files API - Type 3 files (Phase 1 complete)
    app.include_router(library_router, tags=["Library Files"])

    # ✅ NEW: AI Content Edit API for Tiptap editor with AI providers
    app.include_router(ai_content_edit_router, tags=["AI Content Editing"])

    # ✅ ADDED: Internal CORS management for chat-plugin
    app.include_router(internal_cors_router, tags=["Internal CORS"])

    # ✅ Hybrid Search Strategy - Enhanced callbacks, search & CRUD operations
    app.include_router(
        hybrid_strategy_router,
        prefix="/api",
        tags=[
            "Hybrid Search Strategy",
            "Enhanced Callbacks",
            "Metadata + Vector Search",
        ],
    )

    # ✅ Admin Task Status API
    app.include_router(
        task_status_router, prefix="/api/admin", tags=["Admin - Task Status"]
    )

    print("✅ FastAPI application created with all routes")
    print("📌 AI Content Edit endpoints:")
    print("   POST /api/ai/content/edit - AI-powered content editing")
    print("   GET  /api/ai/content/health - Health check")
    print("   GET  /api/ai/content/providers - Available AI providers")
    print("   GET  /api/ai/content/operations - Supported operations")
    print("📌 Unified Chat System endpoints:")
    print("   POST /api/unified/chat-stream - Streaming version of unified chat")
    print("   POST /api/unified/detect-intent - Intent detection only")
    print("   GET  /api/unified/industries - Supported industries")
    print("   GET  /api/unified/languages - Supported languages")
    print("   GET  /api/unified/session/{id} - Session management")
    print("   DELETE /api/unified/session/{id} - Clear session")
    print("📌 AI Sales Agent endpoints:")
    print("   POST /api/sales-agent/chat - Natural conversation for loan consultation")
    print("   POST /api/sales-agent/assess - Loan assessment based on collected data")
    print(
        "   POST /api/sales-agent/check-readiness - Check if data is ready for assessment"
    )
    print(
        "   GET  /api/sales-agent/suggest-questions/{session_id} - Get smart question suggestions"
    )
    print("   DELETE /api/sales-agent/session/{session_id} - Clear session data")
    print("📌 Admin API endpoints:")
    print("   POST /api/admin/companies/register - Register new company")
    print("   GET  /api/admin/companies/{id} - Get company details")
    print("   GET  /api/admin/companies/{id}/stats - Get company data statistics")
    print(
        "   POST /api/admin/companies/{id}/context/basic-info/from-backend - Update basic info (Backend format)"
    )
    print(
        "   POST /api/admin/companies/{id}/files/upload - Upload company files (R2 URL only)"
    )
    print("   POST /api/admin/companies/{id}/extract - Extract data from files")
    print("   POST /api/admin/companies/{id}/search - Search company data")
    print(
        "   GET  /api/admin/industries/{industry}/data-types - Get supported data types"
    )
    print("   GET  /api/admin/file-types - Get supported file types")

    return app


# Create the FastAPI application instance
app = create_app()

# CORS Middleware
# IMPORTANT: Only add CORSMiddleware if NOT in production.
# In production, Nginx handles all CORS headers. Adding them here will cause duplication.
if os.getenv("ENVIRONMENT") != "production":
    print("✅ DEVELOPMENT MODE: Enabling FastAPI CORSMiddleware.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "https://aivungtau.com",
            "https://www.aivungtau.com",
        ],  # Origins for dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    print("✅ PRODUCTION MODE: Skipping FastAPI CORSMiddleware (handled by Nginx).")

# Global variable for document storage (will be moved to proper service later)
documents = {}
