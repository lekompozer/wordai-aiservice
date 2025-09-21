from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
import os, sys, asyncio
from pathlib import Path
from datetime import datetime
from fastapi.responses import StreamingResponse
import json
import time 
import re
from datetime import datetime

import threading

import schedule
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from src.providers.ai_provider_manager import AIProviderManager  # THÊM MỚI
from config.config import (
    DEEPSEEK_API_KEY,
    CHATGPT_API_KEY,
    DEFAULT_AI_PROVIDER,
)  # THÊM MỚI
import fitz  # PyMuPDF
from docx import Document
import base64
from PIL import Image
import io
# Add import at the top
from src.utils.web_search_utils import search_real_estate_properties, search_real_estate_properties_with_logging  # ✅ ADD THIS
from src.utils.real_estate_analyzer import analyze_real_estate_query


# ✅ FIXED: Smart environment configuration loading
ENV = os.getenv("ENV", "production").lower()

# ✅ Load environment files based on environment
try:
    from dotenv import load_dotenv
    
    if ENV == "development":
        # Try development.env first, fallback to .env
        dev_env_file = Path(__file__).parent / "development.env"
        env_file = Path(__file__).parent / ".env"
        
        if dev_env_file.exists():
            load_dotenv(dev_env_file)
            print(f"Loaded DEVELOPMENT configuration from development.env")
        elif env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded DEVELOPMENT configuration from .env (fallback)")
        else:
            print(f"No environment file found, using system environment")
    else:
        # Production - use .env
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded PRODUCTION configuration from .env")
        else:
            print(f"No .env file found for production")
            
except ImportError:
    print("python-dotenv not installed, using environment variables only")

# ✅ Re-read ENV after loading files
ENV = os.getenv("ENV", "production").lower()

# ✅ Set configuration based on environment
if ENV == "development":
    # Development configuration
    DEBUG = True
    HOST = "localhost"
    PORT = 8000
    DOMAIN = "localhost:8000"
    BASE_URL = "http://localhost:8000"
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000"
    ]
    print(f"🔧 Development mode active")
    print(f"   Debug: {DEBUG}")
    print(f"   Host: {HOST}")
    print(f"   Port: {PORT}")
    print(f"   Domain: {DOMAIN}")
    print(f"   Base URL: {BASE_URL}")
    
else:
    # Production configuration (from .env or environment variables)
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DOMAIN = os.getenv("DOMAIN", "ai.aimoney.io.vn")
    BASE_URL = os.getenv("BASE_URL", f"https://{DOMAIN}")
    
    # CORS configuration for production
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else [
        "https://ai.aimoney.io.vn",
        "https://www.ai.aimoney.io.vn", 
        "https://aimoney.io.vn",
        "https://www.aimoney.io.vn",
        "http://localhost:3000",  # For development testing
        "http://localhost:8080"   # For development testing
    ]
    print(f"🏭 Production mode active")
    print(f"   Debug: {DEBUG}")
    print(f"   Host: {HOST}")
    print(f"   Port: {PORT}")
    print(f"   Domain: {DOMAIN}")
    print(f"   Base URL: {BASE_URL}")

# ✅ Load API keys (always needed)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY")
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "deepseek")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ✅ Database configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/" if ENV == "development" else "mongodb://host.docker.internal:27017/")
MONGODB_NAME = os.getenv("MONGODB_NAME", "ai_service_db")
# Add near other config variables
CHATGPT_VISION_REASONING_MODEL = os.getenv("CHATGPT_VISION_REASONING_MODEL", "gpt-4o")
# ✅ Data directory
DATA_DIR = os.getenv("DATA_DIR", "./data")

print(f"🔑 API Keys loaded:")
print(f"   DeepSeek: {'✅' if DEEPSEEK_API_KEY else '❌'}")
print(f"   ChatGPT: {'✅' if CHATGPT_API_KEY else '❌'}")
print(f"   SerpAPI: {'✅' if SERPAPI_KEY else '❌'}")
print(f"   Default AI: {DEFAULT_AI_PROVIDER}")
print(f"   MongoDB: {MONGODB_URI}")
print(f"   Data Dir: {DATA_DIR}")

# ✅ System optimization
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

sys.path.append(str(Path(__file__).parent))
# Ensure src is in sys.path for absolute imports
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)
try:
    import faiss
    faiss.omp_set_num_threads(1) # Thiết lập ngay sau khi import faiss
    print("✅ FAISS omp_set_num_threads(1) applied in serve.py")
except ImportError:
    print("⚠️ FAISS not found, skipping omp_set_num_threads in serve.py")
except Exception as e_faiss_setup:
    print(f"⚠️ Error setting FAISS threads in serve.py: {e_faiss_setup}")

# THÊM DÒNG NÀY
import nest_asyncio
nest_asyncio.apply()

from src.utils.logger import setup_logger
logger = setup_logger()

import json
import uuid
from datetime import datetime
import os

from src.models import (
    QuestionRequest,
    ChatWithFilesRequest,
    OCRRequest,
    CCCDImageRequest,
    CCCDOCRResponse,
    IDCardInfo,
    ExistingLoan,
    LoanApplicationRequest,
    LoanAssessmentResponse,
    validate_loan_application_minimal,
    build_assessment_context
)

# Create results directory
RESULTS_DIR = "results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)
    logger.info(f"✅ Created results directory: {RESULTS_DIR}")

def save_real_estate_analysis_log(analysis_data: dict):
    """Save comprehensive real estate analysis log"""
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = str(uuid.uuid4())[:8]
        filename = f"real_estate_analysis_{timestamp}_{session_id}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # Add metadata
        analysis_data.update({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "analysis_type": "real_estate_valuation",
            "version": "1.0"
        })
        
        # Save to file with proper formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Real estate analysis saved: {filename}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Error saving analysis log: {e}")
        return None

def save_web_search_detailed_log(search_data: dict):
    """Save detailed web search log with full content"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = str(uuid.uuid4())[:8]
        filename = f"web_search_detailed_{timestamp}_{session_id}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(search_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Web search detailed log saved: {filename}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Error saving web search log: {e}")
        return None


from src.rag.chatbot import Chatbot


# Khai báo biến chatbot ở mức global
chatbot = None
conversation_manager = None
ai_provider_manager = None  # THÊM MỚI


# Tạo context manager cho lifespan của ứng dụng
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo chatbot khi ứng dụng khởi động
    global chatbot, conversation_manager, ai_provider_manager
    try:
        print("🚀 Starting AI Service initialization...")
        
        # Initialize components
        print("📝 Initializing Chatbot...")
        chatbot = Chatbot()
        print("✅ Chatbot initialized")

        # Initialize AI Provider Manager
        print("🤖 Initializing AI Provider Manager...")
        ai_provider_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY, chatgpt_api_key=CHATGPT_API_KEY
        )
        print("✅ AI Provider Manager initialized")

        print("💬 Initializing Conversation Manager...")
        conversation_manager = chatbot.conversation_manager
        print("✅ Conversation Manager initialized")
        
        # ✅ LOAD DOCUMENTS WITH PROPER ERROR HANDLING
        print("📚 Loading documents for RAG...")
        try:
            documents_loaded = await load_documents()
            if documents_loaded > 0:
                print(f"✅ Documents loaded successfully: {documents_loaded} files")
            else:
                print("⚠️ No documents loaded - RAG will use empty context")
        except Exception as doc_error:
            print(f"❌ Failed to load documents: {doc_error}")
            print("⚠️ RAG will operate without document context")
        
        print("🎉 AI Service initialized successfully")
        yield
        
    except Exception as e:
        print(f"❌ Critical error during startup: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        # ✅ STILL YIELD TO PREVENT APP CRASH
        print("⚠️ Starting with minimal functionality...")
        yield
        
    finally:
        print("🛑 Shutting down AI Service...")
        # ✅ CLEANUP IF NEEDED
        try:
            if chatbot:
                # Cleanup operations if any
                pass
        except Exception as cleanup_error:
            print(f"⚠️ Error during cleanup: {cleanup_error}")


# Tạo FastAPI app với production config
app = FastAPI(
    title="AI Money Chatbot API",
    description="AI-powered real estate chatbot with RAG capabilities",
    version="1.0.0",
    docs_url="/docs" if DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if DEBUG else None,  # Disable redoc in production
    openapi_url="/openapi.json" if DEBUG else None,  # Disable OpenAPI schema in production
    lifespan=lifespan
)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers for production
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Add server info
    response.headers["X-Powered-By"] = "AI Money Platform"
    response.headers["X-API-Version"] = "1.0.0"
    
    return response

class QuestionRequest(BaseModel):
    question: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None


async def load_documents():
    try:
        # Sử dụng biến môi trường DATA_DIR, mặc định là './data'
        data_dir = os.getenv("DATA_DIR", "./data")
        print(f"📂 Đang đọc tài liệu từ thư mục: {data_dir}")
        
        # Kiểm tra thư mục có tồn tại không
        if not os.path.exists(data_dir):
            print(f"⚠️ Thư mục {data_dir} không tồn tại - tạo thư mục mới")
            os.makedirs(data_dir, exist_ok=True)
            print(f"📁 Tạo thư mục {data_dir} thành công")
            return 0

        # Kiểm tra có files nào trong thư mục không
        files_in_dir = [f for f in os.listdir(data_dir) 
                       if os.path.isfile(os.path.join(data_dir, f)) 
                       and not f.startswith('.')]  # Bỏ hidden files
        
        print(f"📄 Tìm thấy {len(files_in_dir)} files trong {data_dir}")
        for file in files_in_dir[:5]:  # Show first 5 files
            print(f"   - {file}")
        if len(files_in_dir) > 5:
            print(f"   ... và {len(files_in_dir) - 5} files khác")

        if len(files_in_dir) == 0:
            print(f"⚠️ Không có files nào trong thư mục {data_dir}")
            return 0

        # ✅ TRY-CATCH CHO INGEST DOCUMENTS
        try:
            # Sử dụng phương thức ingest_documents của chatbot
            # ⚠️ THÊM TIMEOUT VÀ BETTER ERROR HANDLING
            def safe_ingest():
                try:
                    return chatbot.ingest_documents(data_dir)
                except Exception as e:
                    print(f"❌ Error in ingest_documents: {e}")
                    import traceback
                    print(traceback.format_exc())
                    return 0

            files_processed = await asyncio.get_event_loop().run_in_executor(
                None, safe_ingest
            )

            print(f"✅ Đã xử lý {files_processed} file từ thư mục {data_dir}")
            
            # Kiểm tra số documents đã load vào vector store
            try:
                total_docs = len(chatbot.vector_store.documents) if chatbot.vector_store else 0
                print(f"📊 Vector store hiện có {total_docs} documents")
            except Exception as e:
                print(f"⚠️ Không thể đếm documents trong vector store: {e}")
                total_docs = 0
            
            return files_processed

        except Exception as ingest_error:
            print(f"❌ Error during document ingestion: {ingest_error}")
            import traceback
            print(traceback.format_exc())
            return 0

    except Exception as e:
        print(f"❌ Error loading documents: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return 0


# Production health check with more info
@app.get("/ping")
def ping():
    if DEBUG:
        print("Ping endpoint called!")
    
    return {
        "status": "ok",
        "environment": ENV,
        "domain": DOMAIN,
        "timestamp": str(datetime.now()),
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check for production monitoring"""
    global chatbot, ai_provider_manager
    
    health_status = {
        "status": "healthy",
        "timestamp": str(datetime.now()),
        "environment": ENV,
        "domain": DOMAIN,
        "base_url": BASE_URL,
        "services": {
            "chatbot": "initialized" if chatbot else "initializing",
            "ai_provider": "initialized" if ai_provider_manager else "initializing",
            "database": "connected",  # Add DB check if needed
        },
        "metrics": {
            "documents_loaded": len(chatbot.vector_store.documents) if chatbot and chatbot.vector_store else 0,
            "uptime": "unknown",  # Add uptime tracking if needed
        }
    }
    
    # Check AI providers availability
    if ai_provider_manager:
        health_status["ai_providers"] = {
            "deepseek": bool(DEEPSEEK_API_KEY),
            "chatgpt": bool(CHATGPT_API_KEY),
            "default": DEFAULT_AI_PROVIDER
        }
    
    return health_status

@app.get("/status")
async def status():
    global chatbot
    return {
        "status": "running",
        "documents_loaded": len(chatbot.vector_store.documents) if chatbot else 0,
        "api_status": "initialized" if chatbot else "initializing",
        "timestamp": str(datetime.now()),
    }


@app.post("/chat")
async def answer(req: QuestionRequest, request: Request):
    try:
        # Ưu tiên userId, fallback về deviceId
        user_id = req.userId if req.userId else req.deviceId

        # Nếu không có cả userId và deviceId, dùng IP + user agent
        if not user_id:
            user_id = f"{request.client.host}_{request.headers.get('user-agent', '')}"

        if not chatbot:
            return {"answer": "System is initializing, please try again in a moment"}

        # Sử dụng phương thức mới với lịch sử
        response = chatbot.generate_response_with_history(req.question, user_id)
        return {"answer": response}
    except Exception as e:
        logger.error(f"Error in /chat endpoint: {e}")
        return {"answer": "An error occurred while processing your request"}


@app.post("/chat-stream")
async def stream_answer(req: QuestionRequest, request: Request):
    if not chatbot:
        return StreamingResponse(
            iter(
                [
                    json.dumps(
                        {
                            "answer": "System is initializing, please try again in a moment"
                        }
                    )
                ]
            ),
            media_type="application/json",
        )

    # Ưu tiên userId, fallback về deviceId
    user_id = req.userId if req.userId else req.deviceId

    # Nếu không có cả userId và deviceId, dùng IP + user agent
    if not user_id:
        user_id = f"{request.client.host}_{request.headers.get('user-agent', '')}"

    def generate():
        try:
            prefix = "[Theo dữ liệu ứng dụng] "
            yield f'data: {json.dumps({"chunk": prefix})}\n\n'

            # Sử dụng phương thức streaming mới với lịch sử
            for chunk in chatbot.generate_response_streaming_with_history(
                req.question, user_id
            ):
                yield f'data: {json.dumps({"chunk": chunk})}\n\n'

            yield f'data: {json.dumps({"done": True})}\n\n'
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Error in stream_answer: {e}")
            yield f'data: {json.dumps({"error": error_msg})}\n\n'
            yield f'data: {json.dumps({"done": True})}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/clear-history")
async def clear_history(req: QuestionRequest, request: Request):
    try:
        user_id = req.userId if req.userId else req.deviceId

        if not user_id:
            user_id = f"{request.client.host}_{request.headers.get('user-agent', '')}"

        # Xóa lịch sử hội thoại của user
        deleted = chatbot.db_manager.clear_history(user_id)

        return {"success": True, "message": "Chat history cleared"}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return {"success": False, "message": "Error clearing history"}


# SỬA LẠI class ChatWithFilesRequest
class ChatWithFilesRequest(BaseModel):
    question: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = None
    context: Optional[str] = None
    ai_provider: Optional[str] = "deepseek"  # THÊM MỚI
    use_backend_ocr: Optional[bool] = True  # THÊM MỚI
    url_image: Optional[str] = None  # ← THÊM FIELD MỚI CHO URL IMAGE


# THAY THẾ endpoint /chat-with-files-stream cũ
@app.post("/chat-with-files-stream")
async def chat_with_files_stream(request: ChatWithFilesRequest):
    """
    ✅ CLEAN ROUTER: AI Provider Selection Only
    """
    def generate():
        try:
            # ✅ STEP 1: VALIDATE CHATBOT AVAILABILITY
            if not chatbot:
                yield f'data: {json.dumps({"chunk": "System is initializing, please try again in a moment"})}\n\n'
                yield f'data: {json.dumps({"done": True})}\n\n'
                return

            # ✅ STEP 2: USER ID RESOLUTION
            user_id = request.userId or request.deviceId or "anonymous"

            # ✅ STEP 3: FILE ANALYSIS FOR AI PROVIDER SELECTION
            image_files = []
            document_files = []

            if request.files:
                for file_data in request.files:
                    content_type = file_data.get("content_type", "")
                    if content_type and content_type.startswith("image/"):
                        image_files.append(file_data)
                    else:
                        document_files.append(file_data)

            # ✅ STEP 4: SMART AI PROVIDER SELECTION
            has_images = len(image_files) > 0
            has_documents = len(document_files) > 0

            if has_images and not has_documents:
                ai_provider = "chatgpt"
                processing_mode = "images_only"
                mode_msg = f"📸 Bạn đã đính kèm {len(image_files)} hình ảnh - AI đang đọc file của bạn.."
            elif has_documents and not has_images:
                ai_provider = "deepseek"
                processing_mode = "documents_only"
                mode_msg = f"📄 Bạn đã đính kèm {len(document_files)} tài liệu - AI đang đọc file của bạn.."
            elif has_images and has_documents:
                ai_provider = "chatgpt"
                processing_mode = "mixed_files"
                mode_msg = f"📎 Bạn đã đính kèm ({len(image_files)} hình ảnh và {len(document_files)} tài liệu) - AI đang đọc file của bạn.."
            else:
                ai_provider = request.ai_provider or "deepseek"
                processing_mode = "no_files"
                mode_msg = f"💬 Chỉ có câu hỏi - sử dụng {ai_provider.upper()}"

            # ✅ STEP 5: SEND PROCESSING MODE INFO
            yield f'data: {json.dumps({"chunk": mode_msg})}\n\n'
            # yield f'data: {json.dumps({"chunk": "🤖 Đang kết nối với AI..."})}\n\n'
            logger.info(f"✅ Router: {ai_provider}, Mode: {processing_mode}")

            # ✅ STEP 6: DELEGATE TO CHATBOT WITH STREAMING
            chunk_count = 0
            start_time = time.time()
            

            try:
                
                def run_chatbot_simple():
                    """Simple sync wrapper - no complex threading"""
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        async def collect_all_chunks():
                            chunks = []
                            async for chunk in chatbot.process_files_streaming(
                                query=request.question,
                                user_id=user_id,
                                files=request.files or [],
                                ai_provider=ai_provider,
                                ai_provider_manager=ai_provider_manager
                            ):
                                chunks.append(chunk)
                            return chunks
                        
                        # Get all chunks at once
                        all_chunks = loop.run_until_complete(collect_all_chunks())
                        loop.close()
                        return all_chunks
                        
                    except Exception as e:
                        logger.error(f"Chatbot simple call error: {e}")
                        return [f"⚠️ Lỗi xử lý: {str(e)}"]
                
                # ✅ GET CHUNKS - SAME PATTERN AS /chat-stream
                all_chunks = run_chatbot_simple()
                
                # ✅ STREAM CHUNKS ONE BY ONE - EXACT SAME AS /chat-stream
                for chunk in all_chunks:
                    chunk_count += 1
                    yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                
                # ✅ COMPLETION - SAME AS /chat-stream
                total_time = time.time() - start_time
                yield f'data: {json.dumps({"done": True})}\n\n'
                logger.info(f"✅ Chat with files completed: {chunk_count} chunks in {total_time:.1f}s")
                
            except Exception as e:
                # ✅ ERROR HANDLING - EXACT SAME AS /chat-stream
                error_msg = f"Error: {str(e)}"
                logger.error(f"Error in chat_with_files_stream: {e}")
                yield f'data: {json.dumps({"error": error_msg})}\n\n'
                yield f'data: {json.dumps({"done": True})}\n\n'

                # ✅ STEP 7: COMPLETION WITH METADATA
                total_time = time.time() - start_time
                completion_msg = {
                    "done": True,
                    "metadata": {
                        "provider": ai_provider,
                        "mode": processing_mode,
                        "chunks": chunk_count,
                        "duration": round(total_time, 2),
                        "files_processed": len(request.files) if request.files else 0,
                        "images": len(image_files),
                        "documents": len(document_files)
                    }
                }

                yield f'data: {json.dumps(completion_msg)}\n\n'

                logger.info(f"✅ Chat with files completed: {chunk_count} chunks in {total_time:.1f}s")

            except Exception as processing_error:
                logger.error(f"❌ Processing error: {processing_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

                error_msg = f"⚠️ Lỗi xử lý: {str(processing_error)}"
                yield f'data: {json.dumps({"chunk": error_msg})}\n\n'
                yield f'data: {json.dumps({"done": True, "error": True})}\n\n'

        except Exception as outer_error:
            logger.error(f"❌ Outer chat-with-files error: {outer_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            error_msg = f"⚠️ Lỗi hệ thống: {str(outer_error)}"
            yield f'data: {json.dumps({"chunk": error_msg})}\n\n'
            yield f'data: {json.dumps({"done": True, "error": True})}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


def cleanup_task():
    try:
        if chatbot:
            deleted_count = chatbot.cleanup_old_conversations(days=3)
            logger.info(f"Cleaned up {deleted_count} old conversations")
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")


# Sử dụng schedule để chạy task mỗi ngày lúc 3 giờ sáng
def run_scheduler():
    schedule.every().day.at("03:00").do(cleanup_task)

    while True:
        schedule.run_pending()
        time.sleep(60)


# THÊM endpoint mới
@app.get("/ai-providers")
async def get_available_providers():
    """Endpoint để FE biết providers nào có thể dùng"""
    providers = {
        "deepseek": {
            "available": bool(DEEPSEEK_API_KEY),
            "supports_multimodal": False,
            "requires_backend_ocr": True,
        },
        "chatgpt": {
            "available": bool(CHATGPT_API_KEY),
            "supports_multimodal": True,
            "requires_backend_ocr": False,
        },
    }

    return {"providers": providers, "default": DEFAULT_AI_PROVIDER}


@app.post("/real-estate/deepseek-reasoning")
async def real_estate_deepseek_reasoning(request: ChatWithFilesRequest):
    """
    ✅ COMPLETE: Real estate analysis with DeepSeek reasoning + web search + file processing
    """
    
    def generate():
        # ✅ IMPORTS AT FUNCTION START
        import time as time_module
        import asyncio
        import concurrent.futures
        import threading
        import queue
        import os
        import glob
        
        # ✅ INITIALIZE COMPREHENSIVE ANALYSIS LOG
        analysis_log = {
            "request": {
                "question": request.question,
                "files_count": len(request.files) if request.files else 0,
                "user_id": request.userId or "anonymous",
                "timestamp": datetime.now().isoformat()
            },
            "processing_steps": [],
            "web_search": {
                "search_query": None,
                "target_urls": [],
                "full_responses": {},
                "properties_found": [],
                "performance_metrics": {}
            },
            "processed_files": [],
            "ai_response": "",
            "performance_metrics": {},
            "errors": []
        }
        
        start_time = time_module.time()
        try:
            # ✅ INITIALIZE VARIABLES
            full_response = ""
            processed_files = []
            user_id = request.userId or "anonymous"
            web_search_data = None
            analysis = None

            # ✅ BƯỚC 0: QUICK ANALYSIS
            logger.info("=== STEP 0: QUICK ANALYSIS ===")
            analysis = analyze_real_estate_query(request.question)
            logger.info(f"Quick Analysis - Confidence: {analysis.confidence:.2f}")
            
            # ✅ LOG STEP 0 - DETAILED ANALYSIS
            analysis_log["processing_steps"].append({
                "step": 0,
                "name": "quick_analysis",
                "timestamp": time_module.time(),
                "result": {
                    "property_type": analysis.property_type,
                    "project_name": analysis.project_name,
                    "location": {
                        "province": analysis.location.province,
                        "district": analysis.location.district
                    },
                    "search_query": analysis.search_query,
                    "confidence": analysis.confidence,
                    "dientich": analysis.dientich,
                    "bedrooms": analysis.bedrooms
                }
            })

            # ✅ SAVE SEARCH QUERY TO LOG
            if analysis.search_query:
                analysis_log["web_search"]["search_query"] = analysis.search_query

            # ✅ BƯỚC 1: FILE PROCESSING
            if request.files and len(request.files) > 0:
                logger.info("=== STEP 1: PROCESSING FILES ===")
                
                files_msg = f'📄 Đang xử lý {len(request.files)} tài liệu...'
                yield f'data: {json.dumps({"chunk": files_msg})}\n\n'

                file_processing_start = time_module.time()

                files_result = []
                for i, file_data in enumerate(request.files):
                    filename = file_data.get("filename", f"file_{i}")
                    content_type = file_data.get("content_type", "")
                    
                    file_log = {
                        "filename": filename,
                        "content_type": content_type,
                        "file_size": len(file_data.get("content", "")),
                        "extraction_start": time_module.time()
                    }

                    extracted_text = ""
                    extraction_method = ""
                    
                    # Image processing
                    if content_type and content_type.startswith("image/"):
                        image_url = file_data.get("url", "") or file_data.get("public_url", "")
                        file_log["image_url"] = image_url
                        if image_url:
                            try:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                extracted_text = loop.run_until_complete(
                                    extract_text_with_chatgpt_vision_url(image_url, filename)
                                )
                                loop.close()
                                extraction_method = "ChatGPT Vision"
                            except Exception as e:
                                logger.error(f"Vision OCR error: {e}")
                                extracted_text = f"[Lỗi OCR: {str(e)}]"
                                extraction_method = "Failed"
                                file_log["error"] = str(e)
                        else:
                            extracted_text = f"[Không có URL hình ảnh cho {filename}]"
                            extraction_method = "Failed - No URL"
                    
                    # Document processing
                    elif content_type in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                        file_base64 = file_data.get("content", "")
                        if file_base64:
                            try:
                                if content_type == "application/pdf":
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    extracted_text = loop.run_until_complete(
                                        loop.run_in_executor(None, extract_text_from_pdf, file_base64)
                                    )
                                    loop.close()
                                    extraction_method = "PyMuPDF"
                                else:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    extracted_text = loop.run_until_complete(
                                        loop.run_in_executor(None, extract_text_from_docx, file_base64)
                                    )
                                    loop.close()
                                    extraction_method = "python-docx"
                            except Exception as e:
                                logger.error(f"Document processing error: {e}")
                                extracted_text = f"[Lỗi xử lý tài liệu: {str(e)}]"
                                extraction_method = "Failed"
                                file_log["error"] = str(e)
                    
                    # Complete file log
                    file_log.update({
                        "extracted_text": extracted_text,
                        "extraction_method": extraction_method,
                        "text_length": len(extracted_text),
                        "success": len(extracted_text.strip()) > 10,
                        "processing_time": time_module.time() - file_log["extraction_start"]
                    })
                    # Save processed file
                    files_result.append(file_log)
                    
                    if len(extracted_text.strip()) > 10:
                        success_msg = f'✅ {filename}: {len(extracted_text)} ký tự ({extraction_method})'
                        yield f'data: {json.dumps({"chunk": success_msg})}\n\n'
                
                processed_files = files_result
                file_processing_time = time_module.time() - file_processing_start

                # ✅ LOG STEP 1
                analysis_log["processing_steps"].append({
                    "step": 1,
                    "name": "file_processing",
                    "timestamp": time_module.time(),
                    "duration": file_processing_time,
                    "result": {
                        "files_processed": len(processed_files),
                        "successful_files": len([f for f in processed_files if f["success"]]),
                        "total_text_length": sum(len(f["extracted_text"]) for f in processed_files),
                        "files_details": processed_files
                    }
                })
                analysis_log["processed_files"] = processed_files

            # ✅ BƯỚC 2: WEB SEARCH WITH TIMEOUT
            if analysis.search_query and analysis.confidence > 0.5:
                search_msg = f'🔍 Tìm kiếm BĐS: {analysis.property_type or "BĐS"} tại {analysis.location.province or "địa phương"}'
                yield f'data: {json.dumps({"chunk": search_msg})}\n\n'
                
                search_start = time_module.time()
                
                try:
                    logger.info("🔍 DEBUG: Starting web search with 10s timeout...")
                    
                    def sync_web_search():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            result = loop.run_until_complete(
                                search_real_estate_properties_with_logging(
                                    search_query=analysis.search_query,
                                    analysis_log=analysis_log
                                )
                            )
                            loop.close()
                            return result
                        except Exception as e:
                            logger.error(f"Sync web search error: {e}")
                            return None
                    
                    # Run in background with timeout
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    future = executor.submit(sync_web_search)
                    
                    try:
                        web_search_data = future.result(timeout=10)
                        search_time = time_module.time() - search_start
                        logger.info(f"🔍 DEBUG: Web search completed in {search_time:.1f}s")

                        # ✅ LOG WEB SEARCH PERFORMANCE
                        analysis_log["web_search"]["performance_metrics"] = {
                            "total_time": search_time,
                            "timeout": False,
                            "success": web_search_data is not None
                        }
                        
                    except concurrent.futures.TimeoutError:
                        search_time = time_module.time() - search_start
                        logger.info(f"🔍 DEBUG: Web search timeout after {search_time:.1f}s - continuing...")
                        web_search_data = None
                        future.cancel()
                        
                        analysis_log["web_search"]["performance_metrics"] = {
                            "total_time": search_time,
                            "timeout": True,
                            "success": False
                        }
                        
                    except Exception as search_error:
                        logger.error(f"🔍 DEBUG: Web search error: {search_error}")
                        web_search_data = None
                        error_msg = f'⚠️ Lỗi tìm kiếm: {str(search_error)}'
                        yield f'data: {json.dumps({"chunk": error_msg})}\n\n'
                        
                        analysis_log["errors"].append({
                            "step": 2,
                            "error_type": "web_search_error",
                            "error_message": str(search_error),
                            "timestamp": time_module.time()
                        })
                    
                    finally:
                        executor.shutdown(wait=False)
                    
                    # Process web search results
                    if web_search_data and isinstance(web_search_data, dict):
                        all_properties = web_search_data.get('all_properties', [])
                        actual_count = len(all_properties)
                        
                        if actual_count > 0:
                            successful_sites = web_search_data.get('successful_websites', 0)
                            processing_time = web_search_data.get('processing_time', 0)
                            
                            search_result_msg = f'⚡ Tìm thấy {actual_count} BĐS từ {successful_sites}/3 website trong {processing_time:.1f}s'
                            yield f'data: {json.dumps({"chunk": search_result_msg})}\n\n'
                            
                            # Show top 3 properties
                            for i, prop in enumerate(all_properties[:3]):
                                title_short = prop.get('title', 'No title')[:50]
                                if len(prop.get('title', '')) > 50:
                                    title_short += "..."
                                
                                price = prop.get('price', '') or "Liên hệ"
                                area = prop.get('area', '') or ""
                                website = prop.get('website', 'unknown')
                                
                                prop_msg = f'  {i+1}. {title_short}'
                                if price and price != "Liên hệ":
                                    prop_msg += f' | {price}'
                                if area:
                                    prop_msg += f' | {area}'
                                prop_msg += f' | {website}'
                                
                                yield f'data: {json.dumps({"chunk": prop_msg})}\n\n'
                        else:
                            yield f'data: {json.dumps({"chunk": "⚠️ Không tìm thấy dữ liệu liên quan"})}\n\n'
                    
                    # ✅ LOG STEP 2
                    analysis_log["processing_steps"].append({
                        "step": 2,
                        "name": "web_search",
                        "timestamp": time_module.time(),
                        "duration": search_time,
                        "search_query": analysis.search_query,
                        "result": {
                            "success": web_search_data is not None,
                            "properties_found": len(web_search_data.get('all_properties', [])) if web_search_data else 0,
                            "successful_websites": web_search_data.get('successful_websites', 0) if web_search_data else 0,
                            "timeout": search_time >= 15,
                            "raw_data": web_search_data
                        }
                    })

                except Exception as outer_error:
                    logger.error(f"🔍 DEBUG: Outer web search error: {outer_error}")
                    # ✅ LOG ERROR
                    analysis_log["errors"].append({
                        "step": 2,
                        "error_type": "web_search_outer_error",
                        "error_message": str(outer_error),
                        "timestamp": time_module.time()
                    })
                    web_search_data = None
                    error_msg = f'⚠️ Lỗi hệ thống tìm kiếm: {str(outer_error)}'
                    yield f'data: {json.dumps({"chunk": error_msg})}\n\n'
            else:
                confidence_percent = round(analysis.confidence * 100)
                skip_msg = f'Dùng dữ liệu tổng quát (độ tin cậy: {confidence_percent}%)'
                yield f'data: {json.dumps({"chunk": skip_msg})}\n\n'
                web_search_data = None

                # ✅ LOG SKIPPED SEARCH
                analysis_log["processing_steps"].append({
                    "step": 2,
                    "name": "web_search_skipped",
                    "timestamp": time_module.time(),
                    "reason": "low_confidence" if analysis.confidence <= 0.5 else "no_search_query",
                    "confidence": analysis.confidence
                })

            # ✅ FALLBACK: Try to read from saved JSON
            if not web_search_data:
                logger.info("🔍 DEBUG: Attempting to read from saved JSON file...")
                try:
                    # import os
                    # import glob

                    log_files = glob.glob("web_search_log_*.json")
                    if log_files:
                        latest_file = max(log_files, key=os.path.getmtime)
                        file_age = time_module.time() - os.path.getmtime(latest_file)
                        
                        if file_age < 60:
                            logger.info(f"🔍 DEBUG: Reading from recent file: {latest_file} (age: {file_age:.1f}s)")
                            
                            with open(latest_file, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                            
                            if file_data.get('all_properties_details'):
                                properties = file_data['all_properties_details']
                                
                                web_search_data = {
                                    'total_properties': len(properties),
                                    'successful_websites': len([r for r in file_data.get('website_results_summary', []) if r.get('success')]),
                                    'all_properties': properties,
                                    'processing_time': file_data.get('total_elapsed', 0),
                                    'is_partial': True,
                                    'website_results': file_data.get('website_results_summary', []),
                                    'status': 'recovered_from_file'
                                }
                                
                                # Get website names
                                website_names = []
                                # ✅ METHOD 1: From website_results_summary (corrected key)
                                for result in file_data.get('website_results_summary', []):
                                    if result.get('success') and result.get('properties'):
                                        website_names.append(result.get('website', 'unknown'))
                                
                                # ✅ METHOD 2: From all_properties_details if method 1 fails
                                if not website_names and properties:
                                    seen_websites = set()
                                    for prop in properties:
                                        website = prop.get('website', '')
                                        if website and website not in seen_websites:
                                            website_names.append(website)
                                            seen_websites.add(website)
                                
                                # ✅ METHOD 3: Check for other possible keys
                                if not website_names:
                                    # Check website_results instead of website_results_summary
                                    for result in file_data.get('website_results', []):
                                        if result.get('success') and result.get('properties'):
                                            website_names.append(result.get('website', 'unknown'))
                                
                                # ✅ METHOD 4: Debug - log all available keys
                                logger.info(f"🔍 DEBUG: File data keys: {list(file_data.keys())}")
                                if 'website_results_summary' in file_data:
                                    logger.info(f"🔍 DEBUG: website_results_summary: {file_data['website_results_summary']}")
                                if 'website_results' in file_data:
                                    logger.info(f"🔍 DEBUG: website_results: {file_data['website_results']}")
                                
                                # ✅ FINAL WEBSITE LIST
                                if website_names:
                                    website_list = ', '.join(website_names)
                                    logger.info(f"🔍 DEBUG: Found websites: {website_list}")
                                else:
                                    website_list = 'dữ liệu cache'
                                    logger.warning(f"🔍 DEBUG: No website names found, using fallback")
                                
                                logger.info(f"🔍 DEBUG: Recovered {len(properties)} properties from file")
                                recovered_msg = f'⚡ Đã tìm thấy {len(properties)} BĐS từ {website_list}. Đang phân tích với AI về dữ liệu web tìm thấy...'
                                yield f'data: {json.dumps({"chunk": recovered_msg})}\n\n'
                            else:
                                logger.info(f"🔍 DEBUG: File exists but no properties found")
                        else:
                            logger.info(f"🔍 DEBUG: File too old ({file_age:.1f}s), skipping")
                    else:
                        logger.info(f"🔍 DEBUG: No web_search_log files found")
                        
                except Exception as file_error:
                    logger.error(f"🔍 DEBUG: Error reading from file: {file_error}")

            # ✅ BƯỚC 3: BUILD CONTEXT
            logger.info("🔍 DEBUG: ===== FORCED CONTINUATION AFTER WEB SEARCH =====")
            logger.info(f"🔍 DEBUG: web_search_data is not None: {web_search_data is not None}")
            
            web_data_context = ""
            if web_search_data and isinstance(web_search_data, dict):
                all_properties = web_search_data.get('all_properties', [])
                total_properties = len(all_properties)
                
                if total_properties > 0:
                    processing_time = web_search_data.get('processing_time', 0)
                    is_partial = web_search_data.get('is_partial', False)
                    successful_websites = web_search_data.get('successful_websites', 0)
                    
                    status_note = " (dữ liệu một phần do timeout)" if is_partial else " (dữ liệu đầy đủ)"
                    
                    web_data_context = f"\n\n=== DỮ LIỆU BẤT ĐỘNG SẢN TỪ WEB{status_note} ===\n"
                    web_data_context += f"Tìm thấy {total_properties} bất động sản từ {successful_websites}/3 website:\n"
                    
                    # Build context from all_properties
                    website_groups = {}
                    for prop in all_properties:
                        website = prop.get('website', 'unknown')
                        if website not in website_groups:
                            website_groups[website] = []
                        website_groups[website].append(prop)
                    
                    for website, props in website_groups.items():
                        property_count = len(props)
                        web_data_context += f"\n--- {website} ({property_count} BĐS) ---\n"
                        
                        for i, prop in enumerate(props[:8], 1):
                            web_data_context += f"{i}. {prop.get('title', 'Không có tiêu đề')}\n"
                            if prop.get('price'):
                                web_data_context += f"   💰 Giá: {prop['price']}\n"
                            if prop.get('area'):
                                web_data_context += f"   📐 Diện tích: {prop['area']}\n"
                            if prop.get('detail') and len(prop['detail']) > 20:
                                detail_short = prop['detail'][:100]
                                if len(prop['detail']) > 100:
                                    detail_short += "..."
                                web_data_context += f"   📝 Chi tiết: {detail_short}\n"
                            web_data_context += "\n"
                            
                    web_data_context += f"\n🕐 Dữ liệu cập nhật: {processing_time:.1f}s trước\n"
                    
                    logger.info(f"🔍 DEBUG: Built web_data_context: {len(web_data_context)} chars")
                else:
                    web_data_context = "\n⚠️ Không có dữ liệu web, sử dụng kiến thức chung để định giá\n"
            else:
                web_data_context = "\n⚠️ Không có dữ liệu web, sử dụng kiến thức chung để định giá\n"

            # Build file content
            file_content_text = ""
            if processed_files:
                file_content_text = "\n\n=== TÀI LIỆU ĐÃ XỬ LÝ ===\n"
                for file_info in processed_files:
                    file_content_text += f"\n--- {file_info['filename']} ---\n{file_info['extracted_text']}\n"

            # ✅ BƯỚC 4: BUILD SYSTEM PROMPT
            system_prompt = f"""
Bạn là CHUYÊN GIA THẨM ĐỊNH VÀ ĐỊNH GIÁ BẤT ĐỘNG SẢN hàng đầu Việt Nam với 25 năm kinh nghiệm.

🎯 NHIỆM VỤ: Phân tích định giá bất động sản với reasoning chi tiết từng bước.

📊 DỮ LIỆU PHÂN TÍCH:
- Câu hỏi: {request.question}
- Loại BĐS: {analysis.property_type or 'Chưa xác định'}
- Dự án: {analysis.project_name or 'Chưa xác định'}  
- Vị trí: {analysis.location.province or 'Chưa xác định'}, {analysis.location.district or ''}
- Diện tích: {analysis.dientich or 'Chưa xác định'}
- Phòng ngủ: {analysis.bedrooms or 'Chưa xác định'}
- Độ tin cậy truy vấn: {round(analysis.confidence * 100)}%

{web_data_context}

{file_content_text}

===== PHƯƠNG PHÁP REASONING TỪNG BƯỚC =====

🔍 BƯỚC 1: PHÂN TÍCH THÔNG TIN CƠ BẢN
- Xác định chính xác loại bất động sản, vị trí, diện tích
- Đánh giá chất lượng và độ tin cậy của thông tin

📊 BƯỚC 2: PHÂN TÍCH DỮ LIỆU THỊ TRƯỜNG  
- So sánh với các bất động sản tương tự từ dữ liệu web
- Xác định mức giá trung bình, cao nhất, thấp nhất
- Phân tích xu hướng giá theo khu vực

💎 BƯỚC 3: ĐÁNH GIÁ CÁC YẾU TỐ GIÁ TRỊ
- Vị trí: Tiện ích xung quanh, giao thông, hạ tầng
- Pháp lý: Sổ đỏ, giấy phép, quy hoạch
- Chất lượng: Độ mới, nội thất, tiện nghi
- Thị trường: Cung cầu, thanh khoản

🧮 BƯỚC 4: TÍNH TOÁN GIÁ TRỊ CHÍNH XÁC
- Giá trị thị trường hiện tại (dựa trên dữ liệu thực tế)
- Giá trị thẩm định ngân hàng (85% giá thị trường)
- Khả năng vay thế chấp tối đa

⚠️ BƯỚC 5: PHÂN TÍCH RỦI RO VÀ KHUYẾN NGHỊ
- Rủi ro pháp lý, thanh khoản, biến động giá  
- Điều kiện và lưu ý cần thiết
- Đánh giá độ tin cậy phân tích

LƯU Ý QUAN TRỌNG: 
- Sử dụng dữ liệu web mới nhất để đưa ra định giá chính xác nhất
- Reasoning phải logic, có căn cứ và số liệu cụ thể
"""

            # ✅ BƯỚC 5: GET CONVERSATION HISTORY
            history_messages = conversation_manager.get_optimized_messages(
                user_id=user_id, 
                rag_context="",
                current_query=request.question
            )

            # Create messages
            messages = [{"role": "system", "content": system_prompt}]
            if history_messages:
                messages.extend(history_messages)
            messages.append({"role": "user", "content": request.question})

            logger.info(f"Messages prepared: {len(messages)} total")

            # ✅ BƯỚC 6: AI STREAMING WITH THREADING
            try:
                logger.info("🔍 DEBUG: Starting DeepSeek real-time threading stream...")
                
                
                # ✅ SIMPLE ASYNC TO SYNC CONVERSION - SAME AS /chat-with-files-stream
                def run_ai_simple():
                    """Simple sync wrapper for DeepSeek AI"""
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        async def collect_ai_chunks():
                            chunks = []
                            async for chunk in ai_provider_manager.chat_completion_stream_with_reasoning(
                                messages, "deepseek", use_reasoning=True
                            ):
                                chunks.append(chunk)
                            return chunks
                        
                        # Get all chunks at once
                        all_chunks = loop.run_until_complete(collect_ai_chunks())
                        loop.close()
                        return all_chunks
                        
                    except Exception as e:
                        logger.error(f"AI simple call error: {e}")
                        return [f"⚠️ Lỗi AI: {str(e)}"]
                
                # ✅ GET AI CHUNKS - SAME PATTERN AS WORKING /chat-with-files-stream
                all_ai_chunks = run_ai_simple()
                
                # ✅ STREAM AI CHUNKS ONE BY ONE - EXACT SAME AS OTHER ENDPOINTS
                ai_chunk_count = 0
                for chunk in all_ai_chunks:
                    ai_chunk_count += 1
                    full_response += chunk
                    yield f'data: {json.dumps({"chunk": chunk})}\n\n'
                    
                    # Progress logging every 25 chunks
                    if ai_chunk_count % 25 == 0:
                        logger.info(f"📊 Streamed {ai_chunk_count} AI chunks")
                
                logger.info(f"✅ AI streaming completed: {ai_chunk_count} chunks, {len(full_response)} chars")
                    
            except Exception as ai_error:
                logger.error(f"❌ AI streaming error: {ai_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_chunk = f"⚠️ Lỗi AI: {str(ai_error)}"
                yield f'data: {json.dumps({"chunk": error_chunk})}\n\n'

            # ✅ BƯỚC 7: SAVE CONVERSATION HISTORY
            try:
                conversation_manager.add_message(user_id, "user", request.question)
                conversation_manager.add_message(user_id, "assistant", full_response)
            except Exception as history_error:
                logger.error(f"Error saving history: {history_error}")

            # ✅ BƯỚC 8: COMPLETION
            yield f'data: {json.dumps({"done": True})}\n\n'

        # ✅ CALCULATE FINAL PERFORMANCE METRICS
            total_time = time_module.time() - start_time
            analysis_log["performance_metrics"] = {
                "total_duration": total_time,
                "start_time": start_time,
                "end_time": time_module.time(),
                "steps_completed": len(analysis_log["processing_steps"]),
                "errors_count": len(analysis_log["errors"]),
                "success": len(analysis_log["errors"]) == 0
            }

            # ✅ SAVE COMPREHENSIVE ANALYSIS LOG
            try:
                log_filepath = save_real_estate_analysis_log(analysis_log)
                if log_filepath:
                    logger.info(f"📄 Analysis log saved: {log_filepath}")
                    
                    # ✅ SAVE DETAILED WEB SEARCH LOG SEPARATELY
                    if analysis_log["web_search"]["properties_found"]:
                        web_log_filepath = save_web_search_detailed_log(analysis_log["web_search"])
                        if web_log_filepath:
                            logger.info(f"🌐 Web search log saved: {web_log_filepath}")
                    
                    # ✅ SEND LOG INFO TO USER
                    # log_msg = f'📄 Phân tích đã được lưu: {os.path.basename(log_filepath)}'
                    # yield f'data: {json.dumps({"chunk": log_msg})}\n\n'
                    
            except Exception as log_error:
                logger.error(f"❌ Error saving analysis log: {log_error}")

            # ✅ COMPLETION
            yield f'data: {json.dumps({"done": True})}\n\n'

        except Exception as e:
            logger.error(f"Real estate reasoning error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # ✅ LOG SYSTEM ERROR
            analysis_log["errors"].append({
                "step": "system",
                "error_type": "system_error",
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": time_module.time()
            })
            
            # ✅ SAVE ERROR LOG
            try:
                save_real_estate_analysis_log(analysis_log)
            except Exception:
                pass
            
            error_msg = f"⚠️ Lỗi hệ thống: {str(e)}"
            yield f'data: {json.dumps({"chunk": error_msg})}\n\n'
            yield f'data: {json.dumps({"done": True})}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")

# Thêm model mới cho OCR request không cần question
class OCRRequest(BaseModel):
    files: Optional[List[Dict[str, Any]]] = None


# Thay đổi logger cho dễ phân biệt
logger_prefix = "[AI Service]"


def set_logger_prefix(prefix: str):
    global logger_prefix
    logger_prefix = f"[{prefix}]"


import fitz  # PyMuPDF
from docx import Document


# Thêm helper functions cho OCR
def extract_text_from_pdf(file_base64: str) -> str:
    """Extract text from PDF using PyMuPDF"""
    try:
        import base64

        pdf_data = base64.b64decode(file_base64)
        doc = fitz.open(stream=pdf_data, filetype="pdf")

        text = ""
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text += page.get_text() + "\n"

        doc.close()
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""


def extract_text_from_docx(file_base64: str) -> str:
    """Extract text from DOCX"""
    try:
        import base64
        import io

        docx_data = base64.b64decode(file_base64)
        doc = Document(io.BytesIO(docx_data))

        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"

        return text.strip()
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return ""


async def extract_text_with_chatgpt_vision_url(image_url: str, filename: str) -> str:
    """
    Extract text from image using ChatGPT Vision API with direct URL
    """
    try:
        logger.info(f"  === CHATGPT VISION OCR START ===")
        logger.info(f"  File: {filename}")
        logger.info(f"  Image URL: {image_url}")
        
        # ✅ PROPER MULTIMODAL MESSAGE FORMAT WITH URL
        messages = [
            {
                "role": "system",
                "content": "You are a professional OCR specialist for Vietnamese documents. Extract ALL text from the image, preserve formatting."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Please extract all text from this document image: {filename}. Provide ONLY the text without commentary."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                            "detail": "high"
                        }
                    }
                ]
            }
        ]

        # ✅ CALL CHATGPT VISION API
        logger.info(f"  Calling ChatGPT Vision API...")
        loop = asyncio.get_event_loop()

        def sync_chatgpt_call():
            return ai_provider_manager.chatgpt_client.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=4000,
                temperature=0.1,
            )

        response = await loop.run_in_executor(None, sync_chatgpt_call)
        extracted_text = response.choices[0].message.content.strip()

        logger.info(f"  ✅ ChatGPT Vision OCR completed")
        logger.info(f"  Extracted: {len(extracted_text)} characters")
        logger.info(f"  Raw OCR response: {extracted_text!r}")

        # ✅ CHECK FOR SAFETY REFUSAL
        refusal_patterns = [
            "i'm sorry", "i'm sorry", "can't assist", "cannot help", 
            "unable to", "i cannot", "not able to"
        ]
        text_lower = extracted_text.lower()
        
        if any(pattern in text_lower for pattern in refusal_patterns):
            logger.warning(f"  ⚠️ ChatGPT Vision safety refusal detected")
            return ""

        if extracted_text and len(extracted_text) > 20:
            logger.info(f"  ===== CHATGPT VISION EXTRACTED TEXT =====")
            chunk_size = 500
            for i in range(0, len(extracted_text), chunk_size):
                chunk = extracted_text[i:i+chunk_size]
                chunk_num = i//chunk_size + 1
                logger.info(f"  CHUNK {chunk_num}: {chunk}")
            logger.info(f"  ===== END EXTRACTED TEXT =====")

            return extracted_text.strip()
        else:
            logger.warning(f"  ⚠️ ChatGPT Vision returned short/empty result")
            return ""

    except Exception as e:
        logger.error(f"  ❌ ChatGPT Vision OCR failed: {e}")
        return ""

class CCCDImageRequest(BaseModel):
    images: List[Dict[str, Any]]  # [{"url": "...", "type": "front/back", "fileName": "..."}]
    requestId: Optional[str] = None
    userId: Optional[str] = None

class CCCDOCRResponse(BaseModel):
    success: bool
    requestId: Optional[str] = None
    extractedData: Optional[Dict[str, Any]] = None
    processingDetails: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.post("/api/ocr/cccd", response_model=CCCDOCRResponse)
async def ocr_cccd_extraction(request: CCCDImageRequest):
    """
    ✅ OCR CCCD - Trích xuất thông tin từ ảnh Căn cước công dân
    Hỗ trợ: JPG, JPEG, PNG, HEIC, HEIF, WEBP, TIFF, BMP
    """
    
    processing_start = time.time()
    request_id = request.requestId or f"cccd_{int(time.time() * 1000)}"
    
    try:
        logger.info(f"🆔 [CCCD OCR] {request_id}: Starting OCR processing")
        logger.info(f"📸 [CCCD OCR] {request_id}: {len(request.images)} images to process")
        
        # ✅ STEP 1: Validate và prepare images
        processed_images = []
        
        for i, img_data in enumerate(request.images):
            try:
                img_url = img_data.get("url", "")
                img_type = img_data.get("type", "unknown")  # front/back
                file_name = img_data.get("fileName", f"cccd_image_{i+1}")
                
                logger.info(f"📷 [CCCD OCR] {request_id}: Processing {img_type} - {file_name}")
                
                # Validate image URL
                if not img_url:
                    logger.warning(f"⚠️ [CCCD OCR] {request_id}: Empty URL for image {i+1}")
                    continue
                
                # Validate image format
                file_ext = file_name.split('.')[-1].lower() if '.' in file_name else 'jpg'
                supported_formats = ['jpg', 'jpeg', 'png', 'heic', 'heif', 'webp', 'tiff', 'bmp']
                
                if file_ext not in supported_formats:
                    logger.warning(f"⚠️ [CCCD OCR] {request_id}: Unsupported format {file_ext}")
                    continue
                
                # Test image accessibility
                try:
                    response = requests.head(img_url, timeout=10)
                    if response.status_code != 200:
                        logger.warning(f"⚠️ [CCCD OCR] {request_id}: Image not accessible - {response.status_code}")
                        continue
                except Exception as url_error:
                    logger.warning(f"⚠️ [CCCD OCR] {request_id}: URL test failed - {url_error}")
                    continue
                
                processed_images.append({
                    "url": img_url,
                    "type": img_type,
                    "fileName": file_name,
                    "fileType": f"image/{file_ext}" if file_ext != 'jpg' else "image/jpeg",
                    "index": i
                })
                
            except Exception as img_error:
                logger.error(f"❌ [CCCD OCR] {request_id}: Image {i+1} processing error - {img_error}")
                continue
        
        if not processed_images:
            return CCCDOCRResponse(
                success=False,
                requestId=request_id,
                error="No valid images found to process",
                processingDetails={
                    "totalImages": len(request.images),
                    "validImages": 0,
                    "processingTime": time.time() - processing_start
                }
            )
        
        logger.info(f"✅ [CCCD OCR] {request_id}: {len(processed_images)} valid images prepared")
        
        # ✅ STEP 2: Prepare ChatGPT Vision messages
        try:
            logger.info(f"🤖 [CCCD OCR] {request_id}: Preparing ChatGPT Vision request")
            
            # Create multimodal messages
            messages = [
                {
                    "role": "system",
                    "content": """Bạn là chuyên gia OCR cho Căn cước công dân Việt Nam. 
Nhiệm vụ: Trích xuất CHÍNH XÁC tất cả thông tin từ ảnh CCCD (cả mặt trước và mặt sau).

YÊU CẦU:
1. Đọc cẩn thận tất cả text trong ảnh
2. Trích xuất thông tin theo đúng format JSON
3. Nếu không rõ thông tin nào, để null
4. Chú ý ngày tháng theo format DD/MM/YYYY
5. Tên địa danh chính xác (tỉnh, thành phố, quận, huyện)

ĐỊNH DẠNG JSON TRẦN VỀ:
{
  "soCCCD": "số căn cước 12 số",
  "hoTen": "họ và tên đầy đủ",
  "ngaySinh": "DD/MM/YYYY",
  "gioiTinh": "Nam/Nữ",
  "queQuan": "quê quán đầy đủ",
  "diaChiThuongTru": "địa chỉ thường trú đầy đủ", 
  "ngayCap": "DD/MM/YYYY",
  "noiCap": "nơi cấp",
  "ngayHetHan": "DD/MM/YYYY hoặc 'Không thời hạn'",
  "danToc": "dân tộc (nếu có)",
  "tonGiao": "tôn giáo (nếu có)",
  "dacDiemNhanDang": "đặc điểm nhận dạng (nếu có)",
  "confidence": 0.95
}"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Hãy trích xuất thông tin từ {len(processed_images)} ảnh CCCD này. Trả về CHÍNH XÁC định dạng JSON như yêu cầu:"
                        }
                    ]
                }
            ]
            
            # Add images to message
            for img in processed_images:
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": img["url"],
                        "detail": "high"  # High detail for OCR accuracy
                    }
                })
            
            logger.info(f"📤 [CCCD OCR] {request_id}: ChatGPT payload prepared - {len(messages)} messages")
            
        except Exception as message_error:
            logger.error(f"❌ [CCCD OCR] {request_id}: Message preparation error - {message_error}")
            return CCCDOCRResponse(
                success=False,
                requestId=request_id,
                error=f"Message preparation failed: {str(message_error)}",
                processingDetails={
                    "totalImages": len(request.images),
                    "validImages": len(processed_images),
                    "processingTime": time.time() - processing_start
                }
            )
        
        # ✅ STEP 3: Call ChatGPT Vision API
        try:
            logger.info(f"🤖 [CCCD OCR] {request_id}: Calling ChatGPT Vision API")
            
            # Check if ChatGPT is available
            if not CHATGPT_API_KEY:
                raise Exception("ChatGPT API key not configured")
            
            # Initialize ChatGPT client
            from src.clients.chatgpt_client import ChatGPTClient
            chatgpt_client = ChatGPTClient()
            
            # Call ChatGPT Vision with non-streaming
            ocr_start_time = time.time()
            
            # Use vision reasoning model for better OCR accuracy
            chatgpt_response = chatgpt_client.client.chat.completions.create(
                model=CHATGPT_VISION_REASONING_MODEL,  # gpt-4o for best OCR
                messages=messages,
                max_tokens=2000,
                temperature=0.1,  # Low temperature for accuracy
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            ocr_duration = time.time() - ocr_start_time
            raw_response = chatgpt_response.choices[0].message.content
            
            logger.info(f"✅ [CCCD OCR] {request_id}: ChatGPT response received in {ocr_duration:.2f}s")
            logger.info(f"📄 [CCCD OCR] {request_id}: Response length: {len(raw_response)} chars")
            
        except Exception as api_error:
            logger.error(f"❌ [CCCD OCR] {request_id}: ChatGPT API error - {api_error}")
            return CCCDOCRResponse(
                success=False,
                requestId=request_id,
                error=f"ChatGPT API failed: {str(api_error)}",
                processingDetails={
                    "totalImages": len(request.images),
                    "validImages": len(processed_images),
                    "processingTime": time.time() - processing_start
                }
            )
        
        # ✅ STEP 4: Parse và validate JSON response
        try:
            logger.info(f"🔍 [CCCD OCR] {request_id}: Parsing ChatGPT response")
            
            # Parse JSON
            import json
            try:
                ocr_data = json.loads(raw_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if json_match:
                    ocr_data = json.loads(json_match.group())
                else:
                    raise Exception("No valid JSON found in response")
            
            # Validate essential fields
            essential_fields = ['soCCCD', 'hoTen', 'ngaySinh']
            missing_fields = [field for field in essential_fields if not ocr_data.get(field)]
            
            if missing_fields:
                logger.warning(f"⚠️ [CCCD OCR] {request_id}: Missing essential fields: {missing_fields}")
            
            # Clean and format data
            extracted_data = {
                "idNumber": ocr_data.get("soCCCD"),
                "fullName": ocr_data.get("hoTen"),
                "dateOfBirth": ocr_data.get("ngaySinh"),
                "gender": ocr_data.get("gioiTinh"),
                "nationality": "Việt Nam",
                "placeOfOrigin": ocr_data.get("queQuan"),
                "permanentAddress": ocr_data.get("diaChiThuongTru"),
                "dateOfIssue": ocr_data.get("ngayCap"),
                "placeOfIssue": ocr_data.get("noiCap"),
                "expirationDate": ocr_data.get("ngayHetHan"),
                "ethnicity": ocr_data.get("danToc"),
                "religion": ocr_data.get("tonGiao"),
                "identificationMarks": ocr_data.get("dacDiemNhanDang"),
                "ocrProcessedAt": datetime.now().isoformat(),
                "ocrConfidence": ocr_data.get("confidence", 0.85),
                "ocrRawData": ocr_data
            }
            
            # Remove null values
            extracted_data = {k: v for k, v in extracted_data.items() if v is not None}
            
            logger.info(f"✅ [CCCD OCR] {request_id}: OCR extraction successful")
            logger.info(f"👤 [CCCD OCR] {request_id}: Extracted name: {extracted_data.get('fullName', 'N/A')}")
            logger.info(f"🆔 [CCCD OCR] {request_id}: Extracted ID: {extracted_data.get('idNumber', 'N/A')}")
            
        except Exception as parse_error:
            logger.error(f"❌ [CCCD OCR] {request_id}: Response parsing error - {parse_error}")
            logger.error(f"📄 [CCCD OCR] {request_id}: Raw response: {raw_response[:500]}...")
            
            return CCCDOCRResponse(
                success=False,
                requestId=request_id,
                error=f"Response parsing failed: {str(parse_error)}",
                processingDetails={
                    "totalImages": len(request.images) if hasattr(request, 'images') else 0,
                    "validImages": len(processed_images) if hasattr(request, 'images') else 0,
                    "processingTime": time.time() - processing_start,
                    "rawResponse": raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
                }
            )
        
        # ✅ STEP 5: Return successful response
        total_time = time.time() - processing_start
        
        processing_details = {
            "totalImages": len(request.images),
            "validImages": len(processed_images),
            "processingTime": round(total_time, 2),
            "ocrDuration": round(ocr_duration, 2),
            "modelUsed": CHATGPT_VISION_REASONING_MODEL,
            "imageTypes": [img["type"] for img in processed_images],
            "extractedFields": len([k for k, v in extracted_data.items() if v is not None])
        }
        
        logger.info(f"🎉 [CCCD OCR] {request_id}: Processing completed successfully in {total_time:.2f}s")
        
        return CCCDOCRResponse(
            success=True,
            requestId=request_id,
            extractedData=extracted_data,
            processingDetails=processing_details
        )
        
    except Exception as general_error:
        logger.error(f"❌ [CCCD OCR] {request_id}: General error - {general_error}")
        import traceback
        logger.error(f"🔍 [CCCD OCR] {request_id}: Traceback - {traceback.format_exc()}")
        
        return CCCDOCRResponse(
            success=False,
            requestId=request_id,
            error=f"Processing failed: {str(general_error)}",
            processingDetails={
                "totalImages": len(request.images) if hasattr(request, 'images') else 0,
                "processingTime": time.time() - processing_start
            }
        )


@app.post("/api/loan/assessment", response_model=LoanAssessmentResponse)
async def loan_credit_assessment(request: LoanApplicationRequest):
    """
    ✅ LOAN CREDIT ASSESSMENT - Thẩm định hồ sơ vay với DeepSeek Reasoning
    """

    processing_start = time.time()
    assessment_id = f"assessment_{int(time.time() * 1000)}"

    try:
        logger.info(f"🏦 [LOAN ASSESSMENT] {assessment_id}: Starting credit assessment")
        logger.info(f"📋 [LOAN ASSESSMENT] {assessment_id}: Application ID: {request.applicationId}")
        logger.info(f"💰 [LOAN ASSESSMENT] {assessment_id}: Loan amount: {request.loanAmount:,} VNĐ")

        # ✅ SAFE APPLICANT NAME ACCESS
        applicant_name = "N/A"
        if hasattr(request, 'fullName') and request.fullName:
            applicant_name = request.fullName
        elif request.idCardInfo and hasattr(request.idCardInfo, 'fullName') and request.idCardInfo.fullName:
            applicant_name = request.idCardInfo.fullName

        logger.info(f"👤 [LOAN ASSESSMENT] {assessment_id}: Applicant: {applicant_name}")

        # ✅ STEP 1: Basic validation using utility function
        is_valid, validation_errors = validate_loan_application_minimal(request.dict())

        if not is_valid:
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId or "unknown",
                error=f"Validation failed: {', '.join(validation_errors)}"
            )

        # ✅ STEP 2: Check DeepSeek availability
        if not DEEPSEEK_API_KEY:
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error="DeepSeek API not configured",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 3: Calculate comprehensive financial metrics for loan assessment
        try:
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Starting financial metrics calculation")

            # =================================================================
            # 📥 INPUT DATA COLLECTION - Thu thập dữ liệu đầu vào an toàn
            # =================================================================

            # Thu nhập hàng tháng (VNĐ)
            monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            logger.info(f"   💰 Monthly income: {monthly_income:,} VNĐ")

            # Thu nhập khác (cho thuê, kinh doanh phụ, etc.)
            other_income_amount = getattr(request, 'otherIncomeAmount', 0) or 0
            logger.info(f"   💼 Other income: {other_income_amount:,} VNĐ")

            # Khoản nợ hiện tại phải trả hàng tháng
            monthly_debt_payment = getattr(request, 'monthlyDebtPayment', 0) or 0
            logger.info(f"   💳 Current monthly debt: {monthly_debt_payment:,} VNĐ")

            # Giá trị tài sản đảm bảo (thường là BĐS)
            collateral_value = getattr(request, 'collateralValue', 0) or 0
            logger.info(f"   🏠 Collateral value: {collateral_value:,} VNĐ")

            # Số tiền muốn vay
            loan_amount = getattr(request, 'loanAmount', 0) or 0
            logger.info(f"   💵 Loan amount: {loan_amount:,} VNĐ")

            # Lãi suất từ backend (% năm)
            backend_interest_rate = getattr(request, 'interestRate', 8.5) or 8.5
            logger.info(f"   📈 Interest rate: {backend_interest_rate}% per year")

            # Thời hạn vay
            loan_term = getattr(request, 'loanTerm', '15 năm') or '15 năm'
            logger.info(f"   ⏰ Loan term: {loan_term}")

            # =================================================================
            # 🧮 PRIMARY CALCULATIONS - Tính toán các chỉ số chính
            # =================================================================

            # 1️⃣ TỔNG THU NHẬP HÀNG THÁNG
            # Mục đích: Xác định khả năng tài chính tổng thể của khách hàng
            total_monthly_income = monthly_income + other_income_amount
            logger.info(f"   ✅ Total monthly income: {total_monthly_income:,} VNĐ")

            # 2️⃣ DTI HIỆN TẠI (Current Debt-to-Income Ratio)
            # Mục đích: Đánh giá tình trạng nợ hiện tại so với thu nhập
            # Tiêu chuẩn ngân hàng: ≤ 40% (tốt), 40-50% (cảnh báo), >50% (từ chối)
            current_debt_ratio = monthly_debt_payment / total_monthly_income if total_monthly_income > 0 else 0
            logger.info(f"   📊 Current DTI ratio: {current_debt_ratio:.2%} (Standard: ≤40% good, >50% risky)")

            # =================================================================
            # 💳 LOAN PAYMENT CALCULATION - Tính toán khoản trả góp
            # =================================================================

            # Chuyển đổi lãi suất năm sang thập phân
            estimated_rate = backend_interest_rate / 100
            logger.info(f"   🔢 Annual rate (decimal): {estimated_rate}")

            # Trích xuất số năm từ thời hạn vay
            years = 15  # Default
            try:
                if "năm" in loan_term:
                    years = int(loan_term.split()[0])
                    logger.info(f"   ⏳ Extracted loan years: {years}")
            except Exception as term_error:
                logger.warning(f"   ⚠️ Cannot parse loan term '{loan_term}', using default 15 years")
                years = 15

            # Tính toán các thông số cho công thức trả góp
            monthly_rate = estimated_rate / 12  # Lãi suất tháng
            n_payments = years * 12  # Tổng số kỳ trả

            logger.info(f"   📅 Monthly rate: {monthly_rate:.6f} ({monthly_rate*100:.4f}%)")
            logger.info(f"   🔢 Total payments: {n_payments} months")

            # 3️⃣ MONTHLY PAYMENT CALCULATION (Công thức trả góp đều)
            # Công thức: PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
            # Mục đích: Tính khoản trả hàng tháng cho khoản vay mới
            if loan_amount > 0 and monthly_rate > 0:
                # Áp dụng công thức trả góp đều (Equal Monthly Installment)
                compound_factor = (1 + monthly_rate) ** n_payments
                estimated_monthly_payment = loan_amount * (monthly_rate * compound_factor) / (compound_factor - 1)

                logger.info(f"   💰 Estimated monthly payment: {estimated_monthly_payment:,} VNĐ")
                logger.info(f"   📊 Payment calculation: Loan={loan_amount:,}, Rate={monthly_rate:.6f}, Periods={n_payments}")
            else:
                estimated_monthly_payment = 0
                logger.warning(f"   ⚠️ Cannot calculate payment: loan_amount={loan_amount}, monthly_rate={monthly_rate}")

            # =================================================================
            # 📈 RISK ASSESSMENT RATIOS - Tính toán các tỷ lệ đánh giá rủi ro
            # =================================================================

            # 4️⃣ NEW DTI RATIO (Projected Debt-to-Income after new loan)
            # Mục đích: Đánh giá khả năng trả nợ sau khi có khoản vay mới
            # Tiêu chuẩn ngân hàng VN: ≤50% (SBVN), ≤40% (conservative)
            new_debt_ratio = (monthly_debt_payment + estimated_monthly_payment) / total_monthly_income if total_monthly_income > 0 else 0
            logger.info(f"   🚨 New DTI ratio: {new_debt_ratio:.2%} (Regulatory limit: ≤50%, Bank limit: ≤40%)")

            # 5️⃣ LTV RATIO (Loan-to-Value Ratio)
            # Mục đích: Đánh giá rủi ro tài sản đảm bảo
            # Tiêu chuẩn ngân hàng: ≤70% (tốt), 70-80% (chấp nhận), >80% (từ chối)
            loan_to_value = loan_amount / collateral_value if collateral_value > 0 else 0
            logger.info(f"   🏠 LTV ratio: {loan_to_value:.2%} (Standard: ≤70% good, >80% risky)")

            # =================================================================
            # 💡 FINANCIAL CAPACITY ANALYSIS - Phân tích khả năng tài chính
            # =================================================================

            # 6️⃣ REMAINING INCOME (Thu nhập còn lại sau trả nợ)
            # Mục đích: Đánh giá khả năng chi tiêu sinh hoạt sau khi trả nợ
            remaining_income = total_monthly_income - monthly_debt_payment - estimated_monthly_payment
            logger.info(f"   💵 Remaining income: {remaining_income:,} VNĐ (for living expenses)")

            # 7️⃣ DEBT SERVICE COVERAGE (Khả năng thanh toán nợ)
            # Mục đích: Đo lường mức độ an toàn trong việc trả nợ
            total_debt_service = monthly_debt_payment + estimated_monthly_payment
            debt_coverage = total_monthly_income / total_debt_service if total_debt_service > 0 else float('inf')
            logger.info(f"   🛡️ Debt service coverage: {debt_coverage:.2f}x (>1.25x recommended)")

            # =================================================================
            # 🎯 RISK ASSESSMENT SUMMARY - Tóm tắt đánh giá rủi ro
            # =================================================================

            # Đánh giá mức độ rủi ro dựa trên các chỉ số
            risk_indicators = []

            if new_debt_ratio > 0.5:  # >50%
                risk_indicators.append(f"High DTI: {new_debt_ratio:.1%}")
            elif new_debt_ratio > 0.4:  # 40-50%
                risk_indicators.append(f"Moderate DTI: {new_debt_ratio:.1%}")

            if loan_to_value > 0.8:  # >80%
                risk_indicators.append(f"High LTV: {loan_to_value:.1%}")
            elif loan_to_value > 0.7:  # 70-80%
                risk_indicators.append(f"Moderate LTV: {loan_to_value:.1%}")

            if remaining_income < 15_000_000:  # <15M VNĐ
                risk_indicators.append(f"Low remaining income: {remaining_income/1_000_000:.1f}M")

            if debt_coverage < 1.25:
                risk_indicators.append(f"Low debt coverage: {debt_coverage:.2f}x")

            # =================================================================
            # 📊 COMPREHENSIVE LOGGING - Ghi log chi tiết
            # =================================================================

            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Financial metrics calculation completed")
            logger.info(f"   💵 Total monthly income: {total_monthly_income:,} VNĐ")
            logger.info(f"   📈 Current DTI ratio: {current_debt_ratio:.2%}")
            logger.info(f"   🚨 Projected DTI ratio: {new_debt_ratio:.2%}")
            logger.info(f"   🏠 Loan-to-Value ratio: {loan_to_value:.2%}")
            logger.info(f"   💰 Estimated monthly payment: {estimated_monthly_payment:,} VNĐ")
            logger.info(f"   💵 Remaining income: {remaining_income:,} VNĐ")
            logger.info(f"   🛡️ Debt service coverage: {debt_coverage:.2f}x")

            if risk_indicators:
                logger.warning(f"   ⚠️ Risk indicators: {', '.join(risk_indicators)}")
            else:
                logger.info(f"   ✅ All financial ratios within acceptable ranges")

            # =================================================================
            # 🎯 ASSESSMENT RECOMMENDATION - Đề xuất sơ bộ
            # =================================================================

            # Đưa ra đề xuất sơ bộ dựa trên các chỉ số tài chính
            if new_debt_ratio <= 0.4 and loan_to_value <= 0.7 and remaining_income >= 15_000_000:
                preliminary_recommendation = "STRONG_APPROVAL"
                logger.info(f"   🟢 Preliminary assessment: STRONG APPROVAL CANDIDATE")
            elif new_debt_ratio <= 0.5 and loan_to_value <= 0.8 and remaining_income >= 10_000_000:
                preliminary_recommendation = "CONDITIONAL_APPROVAL"
                logger.info(f"   🟡 Preliminary assessment: CONDITIONAL APPROVAL CANDIDATE")
            else:
                preliminary_recommendation = "NEEDS_REVIEW"
                logger.info(f"   🔴 Preliminary assessment: NEEDS DETAILED REVIEW")

            # Store all calculated metrics for later use
            financial_metrics = {
                'monthly_income': monthly_income,
                'other_income_amount': other_income_amount,
                'total_monthly_income': total_monthly_income,
                'monthly_debt_payment': monthly_debt_payment,
                'estimated_monthly_payment': estimated_monthly_payment,
                'current_debt_ratio': current_debt_ratio,
                'new_debt_ratio': new_debt_ratio,
                'loan_to_value': loan_to_value,
                'remaining_income': remaining_income,
                'debt_coverage': debt_coverage,
                'risk_indicators': risk_indicators,
                'preliminary_recommendation': preliminary_recommendation,
                'backend_interest_rate': backend_interest_rate,
                'loan_term_years': years
            }

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: All financial metrics stored successfully")

        except Exception as calc_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Financial calculation error - {calc_error}")
            import traceback
            logger.error(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Calculation traceback - {traceback.format_exc()}")

            # ✅ SAFE FALLBACK VALUES - Giá trị dự phòng an toàn
            estimated_monthly_payment = 0
            new_debt_ratio = 0
            loan_to_value = 0
            backend_interest_rate = 8.5
            total_monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            current_debt_ratio = 0
            remaining_income = 0
            debt_coverage = 0

            # Store fallback metrics
            financial_metrics = {
                'monthly_income': getattr(request, 'monthlyIncome', 0) or 0,
                'other_income_amount': 0,
                'total_monthly_income': total_monthly_income,
                'monthly_debt_payment': 0,
                'estimated_monthly_payment': 0,
                'current_debt_ratio': 0,
                'new_debt_ratio': 0,
                'loan_to_value': 0,
                'remaining_income': 0,
                'debt_coverage': 0,
                'risk_indicators': ['Calculation Error'],
                'preliminary_recommendation': 'MANUAL_REVIEW_REQUIRED',
                'backend_interest_rate': 8.5,
                'loan_term_years': 15,
                'calculation_error': str(calc_error)
            }

            logger.warning(f"🔄 [LOAN ASSESSMENT] {assessment_id}: Using fallback financial metrics due to calculation error")
        # ✅ STEP 4: Build comprehensive assessment prompt
        try:
            # ✅ CALCULATE AGE FROM BIRTH YEAR
            current_year = datetime.now().year
            birth_year = getattr(request, 'birthYear', None)
            if birth_year:
                age = current_year - birth_year
            elif request.idCardInfo and request.idCardInfo.dateOfBirth:
                age = current_year - request.idCardInfo.dateOfBirth.year
            else:
                age = "Chưa xác định"

            # ✅ GET PERSONAL INFO (Priority: personalInfo over idCardInfo) - ALL SAFE
            full_name = getattr(request, 'fullName', None) or (request.idCardInfo.fullName if request.idCardInfo else "Chưa cung cấp")
            gender = getattr(request, 'gender', None) or (request.idCardInfo.gender if request.idCardInfo else "Chưa cung cấp")
            marital_status = getattr(request, 'maritalStatus', None) or "Chưa cung cấp"
            dependents = getattr(request, 'dependents', 0) or 0
            email = getattr(request, 'email', None) or "Chưa cung cấp"

            # Phone with country code
            phone_country_code = getattr(request, 'phoneCountryCode', '+84')
            phone_number = getattr(request, 'phoneNumber', None)
            phone_display = f"{phone_country_code} {phone_number}" if phone_number else "Chưa cung cấp"

            # ID Card info (optional)
            id_number = "Chưa cung cấp"
            permanent_address = "Chưa cung cấp"
            if request.idCardInfo:
                id_number = getattr(request.idCardInfo, 'idNumber', None) or "Chưa cung cấp"
                permanent_address = getattr(request.idCardInfo, 'permanentAddress', None) or "Chưa cung cấp"

            # ✅ GET FINANCIAL INFO - ALL SAFE
            monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            primary_income_source = getattr(request, 'primaryIncomeSource', None) or "Chưa cung cấp"
            company_name = getattr(request, 'companyName', None) or "Chưa cung cấp"
            job_title = getattr(request, 'jobTitle', None) or "Chưa cung cấp"
            work_experience = getattr(request, 'workExperience', 0) or 0
            other_income = getattr(request, 'otherIncome', None) or "Không có"
            other_income_amount = getattr(request, 'otherIncomeAmount', 0) or 0

            # Banking info - SAFE
            bank_name = getattr(request, 'bankName', None) or "Chưa cung cấp"
            bank_account = getattr(request, 'bankAccount', None) or "Chưa cung cấp"

            # Assets - SAFE
            total_assets = getattr(request, 'totalAssets', 0) or 0
            liquid_assets = getattr(request, 'liquidAssets', 0) or 0

            # ✅ GET DEBT INFO - ALL SAFE
            has_existing_debt = getattr(request, 'hasExistingDebt', False) or False
            total_debt_amount = getattr(request, 'totalDebtAmount', 0) or 0
            monthly_debt_payment = getattr(request, 'monthlyDebtPayment', 0) or 0
            cic_credit_score_group = getattr(request, 'cicCreditScoreGroup', None) or "Chưa xác định"
            credit_history = getattr(request, 'creditHistory', None) or "Chưa có thông tin"

            # ✅ GET COLLATERAL INFO - ALL SAFE
            collateral_type = getattr(request, 'collateralType', 'Bất động sản')
            collateral_info = getattr(request, 'collateralInfo', 'Chưa có thông tin chi tiết')
            collateral_value = getattr(request, 'collateralValue', 0) or 0
            has_collateral_image = getattr(request, 'hasCollateralImage', False)

            # ✅ GET BACKEND INTEREST RATE - SAFE
            backend_interest_rate = getattr(request, 'interestRate', 8.5)

            # ✅ SAFE EXISTING LOANS FORMAT
            existing_loans = getattr(request, 'existingLoans', []) or []
            existing_loans_text = ""
            if existing_loans and len(existing_loans) > 0:
                for i, loan in enumerate(existing_loans, 1):
                    lender = getattr(loan, 'lender', None) or "Không rõ"
                    amount = getattr(loan, 'amount', 0) or 0
                    payment = getattr(loan, 'monthlyPayment', 0) or 0
                    term = getattr(loan, 'remainingTerm', None) or "Không rõ"
                    existing_loans_text += f"{i}. {lender}: {amount/1_000_000:.0f} triệu VNĐ (trả {payment/1_000_000:.0f} triệu/tháng, còn {term})\n"
            else:
                existing_loans_text = "Không có khoản nợ nào"

            # ✅ BUILD SAFE PROMPT WITH ALL FALLBACKS
            assessment_prompt = f"""Bạn là CHUYÊN GIA THẨM ĐỊNH TÍN DỤNG cao cấp với 15 năm kinh nghiệm tại các ngân hàng lớn ở Việt Nam (VietinBank, BIDV, Vietcombank). Hãy thẩm định hồ sơ vay vốn này một cách chi tiết và chuyên nghiệp theo tiêu chuẩn ngân hàng Việt Nam.

🎯 **NHIỆM VỤ THẨM ĐỊNH:**

1. **PHÂN TÍCH KHẢ NĂNG TÀI CHÍNH:**
   - Đánh giá tỷ lệ thu nhập/chi phí (DTI - Debt to Income)
   - Phân tích dòng tiền hàng tháng và khả năng trả nợ
   - Đánh giá độ ổn định thu nhập và nguồn thu

2. **THẨM ĐỊNH TÀI SẢN ĐẢM BẢO:**
   - Định giá lại bất động sản dựa trên mô tả chi tiết từ khách hàng
   - Đánh giá tính thanh khoản và rủi ro giá trị
   - Phân tích vị trí địa lý và tiện ích dựa trên thông tin có sẵn

3. **ĐÁNH GIÁ RỦI RO TÍN DỤNG:**
   - Phân tích lịch sử tín dụng và nhóm CIC
   - Đánh giá khả năng trả nợ dựa trên thu nhập
   - Xác định các yếu tố rủi ro tiềm ẩn

4. **KIẾN NGHỊ QUYẾT ĐỊNH:**
   - Phê duyệt/từ chối với lý do cụ thể và chi tiết
   - Đề xuất số tiền cho vay phù hợp (nếu phê duyệt)
   - Đề xuất lãi suất và điều kiện vay
   - Các yêu cầu bổ sung (nếu có)

📋 **THÔNG TIN HỒ SƠ VAY:**

**A. THÔNG TIN KHOẢN VAY:**
- Mã hồ sơ: {getattr(request, 'applicationId', 'N/A')}
- Số tiền vay: {loan_amount/1_000_000_000:.1f} tỷ VNĐ
- Loại vay: {getattr(request, 'loanType', 'Chưa xác định')}
- Thời hạn: {loan_term}
- Mục đích: {getattr(request, 'loanPurpose', 'Chưa cung cấp')}

**B. THÔNG TIN CÁ NHÂN:**
- Họ tên: {full_name}
- Tuổi: {age}
- Giới tính: {gender}
- Tình trạng hôn nhân: {marital_status}
- Số người phụ thuộc: {dependents} người
- Điện thoại: {phone_display}
- Email: {email}

**Thông tin CCCD (nếu có):**
- Số CCCD: {id_number}
- Địa chỉ thường trú: {permanent_address}

**C. THÔNG TIN TÀI CHÍNH:**
- Thu nhập chính: {monthly_income/1_000_000:.0f} triệu VNĐ/tháng
- Nguồn thu nhập: {primary_income_source}
- Công ty/Doanh nghiệp: {company_name}
- Chức vụ: {job_title}
- Kinh nghiệm làm việc: {work_experience} năm
- Thu nhập khác: {other_income_amount/1_000_000:.0f} triệu VNĐ/tháng ({other_income})

- Tổng tài sản: {total_assets/1_000_000_000:.1f} tỷ VNĐ
- Tài sản thanh khoản: {liquid_assets/1_000_000_000:.1f} tỷ VNĐ
- Ngân hàng chính: {bank_name}
- Số tài khoản: {bank_account}

**D. THÔNG TIN NỢ HIỆN TẠI:**
- Có nợ hiện tại: {'Có' if has_existing_debt else 'Không'}
- Tổng dư nợ: {total_debt_amount/1_000_000:.0f} triệu VNĐ
- Trả nợ hàng tháng: {monthly_debt_payment/1_000_000:.0f} triệu VNĐ
- Tỷ lệ nợ/thu nhập hiện tại: {current_debt_ratio:.1%}
- Nhóm tín dụng CIC: Nhóm {cic_credit_score_group}
- Lịch sử tín dụng: {credit_history}

**Chi tiết các khoản nợ hiện tại:**
{existing_loans_text}

**E. TÀI SẢN ĐẢM BẢO:**
- Loại tài sản: {collateral_type}
- Giá trị khách hàng ước tính: {collateral_value/1_000_000_000:.1f} tỷ VNĐ {"(có hình ảnh đính kèm)" if has_collateral_image else "(chưa có hình ảnh)"}
- Tỷ lệ cho vay/giá trị tài sản dự kiến: {loan_to_value:.1%}

**Mô tả chi tiết tài sản từ khách hàng:**
{collateral_info}

📊 **CHỈ SỐ TÀI CHÍNH QUAN TRỌNG:**
- Dự kiến trả nợ mới hàng tháng: {estimated_monthly_payment/1_000_000:.1f} triệu VNĐ
- Tỷ lệ nợ/thu nhập sau khi vay: {new_debt_ratio:.1%}
- Thu nhập còn lại sau trả nợ: {(total_monthly_income - monthly_debt_payment - estimated_monthly_payment)/1_000_000:.1f} triệu VNĐ


⚠️ **YÊU CẦU QUAN TRỌNG:**
1. Phân tích từng bước một cách logic và chi tiết
2. Đưa ra quyết định dựa trên tiêu chuẩn ngân hàng Việt Nam
3. Giải thích rõ ràng lý do cho mọi quyết định
4. Đề xuất các điều kiện cụ thể và khả thi
5. **Định giá tài sản đảm bảo dựa CHÍNH XÁC trên mô tả từ khách hàng**

🎯 **TRÁCH NGHIỆM THẨM ĐỊNH:**
Trả lời theo định dạng JSON chính xác (bắt buộc):

{{
  "status": "approved/rejected/needs_review",
  "confidence": 0.85,
  "creditScore": 750,
  "reasoning": "Phân tích chi tiết lý do quyết định với ít nhất 200 từ...",
  "riskFactors": ["Rủi ro cụ thể 1", "Rủi ro cụ thể 2", "Rủi ro cụ thể 3"],
  "recommendations": ["Kiến nghị cụ thể 1", "Kiến nghị cụ thể 2"],
  "approvedAmount": 
  "interestRate": {backend_interest_rate},
  "loanTerm": 
  "monthlyPayment": {int(estimated_monthly_payment) if estimated_monthly_payment > 0 else None},
  "loanToValue": 
  "debtToIncome": 
  "conditions": 
  "collateralValuation": {{
    "estimatedValue": {collateral_value if collateral_value > 0 else "cần định giá dựa trên tài sản đảm bảo"},
    "marketAnalysis": "Phân tích thị trường dựa trên mô tả tài sản từ khách hàng",
    "liquidityRisk": "low/medium/high",
    "valuationMethod": "customer_description_analysis"
  }},
  "financialAnalysis": {{
    "totalMonthlyIncome": {total_monthly_income},
    "totalMonthlyDebt": {monthly_debt_payment},
    "newLoanPayment": {int(estimated_monthly_payment) if estimated_monthly_payment > 0 else 0},
    "remainingIncome": {max(0, total_monthly_income - monthly_debt_payment - estimated_monthly_payment)},
    "emergencyFund": {liquid_assets},
    "incomeStability": "high/medium/low",
    "assetLiquidity": "high/medium/low"
  }}
}}

HÃY THẨM ĐỊNH KỸ LƯỠNG VÀ ĐƯA RA QUYẾT ĐỊNH CHÍNH XÁC THEO TIÊU CHUẨN NGÂN HÀNG VIỆT NAM."""

            logger.info(f"📝 [LOAN ASSESSMENT] {assessment_id}: Safe assessment prompt prepared")
            logger.info(f"   📄 Prompt length: {len(assessment_prompt)} characters")

        except Exception as prompt_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Prompt preparation error - {prompt_error}")
            return LoanAssessmentResponse(
                success=False,
                applicationId=getattr(request, 'applicationId', 'unknown'),
                error=f"Prompt preparation failed: {str(prompt_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 5: Call DeepSeek Reasoning API
        try:
            logger.info(f"🤖 [LOAN ASSESSMENT] {assessment_id}: Calling DeepSeek Reasoning API")

            # Prepare messages for DeepSeek
            messages = [
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia thẩm định tín dụng chuyên nghiệp. Phản hồi bằng JSON chính xác và phân tích chi tiết."
                },
                {
                    "role": "user",
                    "content": assessment_prompt
                }
            ]

            # Call DeepSeek with reasoning
            reasoning_start = time.time()

            def sync_loan_assessment_non_stream():
                """Sync wrapper for loan assessment non-streaming"""
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # ✅ USE DEDICATED LOAN ASSESSMENT NON-STREAMING METHOD
                    result = loop.run_until_complete(
                        ai_provider_manager.loan_assessment_completion_non_stream(messages, "deepseek")
                    )

                    loop.close()
                    return result

                except Exception as e:
                    logger.error(f"Sync loan assessment non-stream call error: {e}")
                    raise e

            # ✅ GET COMPLETE RESPONSE NON-STREAMING (MORE RELIABLE)
            raw_response = sync_loan_assessment_non_stream()
            reasoning_duration = time.time() - reasoning_start

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: DeepSeek response received in {reasoning_duration:.2f}s")
            logger.info(f"📄 [LOAN ASSESSMENT] {assessment_id}: Response length: {len(raw_response)} chars")

        except Exception as api_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: DeepSeek API error - {api_error}")
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error=f"DeepSeek API failed: {str(api_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 6: Parse assessment response
        try:
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Parsing DeepSeek response")

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                assessment_data = json.loads(json_match.group())
            else:
                # Try to find JSON in the response
                lines = raw_response.split('\n')
                json_lines = []
                in_json = False
                for line in lines:
                    if '{' in line:
                        in_json = True
                    if in_json:
                        json_lines.append(line)
                    if '}' in line and in_json:
                        break

                if json_lines:
                    assessment_data = json.loads(''.join(json_lines))
                else:
                    raise Exception("No valid JSON found in response")

            # Validate required fields
            required_fields = ['status', 'confidence', 'reasoning']
            missing_fields = [field for field in required_fields if field not in assessment_data]

            if missing_fields:
                logger.warning(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Missing fields: {missing_fields}")

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: Assessment parsing successful")
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Status: {assessment_data.get('status', 'unknown')}")
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Confidence: {assessment_data.get('confidence', 0)}")

        except Exception as parse_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Response parsing error - {parse_error}")
            logger.error(f"📄 [LOAN ASSESSMENT] {assessment_id}: Raw response preview: {raw_response[:500]}...")

            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error=f"Response parsing failed: {str(parse_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start,
                    "rawResponsePreview": raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
                }
            )

        # ✅ STEP 7: Save assessment log
        try:
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Starting log save process")

            # ✅ CHECK VARIABLES EXISTENCE
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Variables check:")
            logger.info(f"   - applicant_name exists: {'applicant_name' in locals()}")
            logger.info(f"   - id_number exists: {'id_number' in locals()}")
            logger.info(f"   - age exists: {'age' in locals()}")
            logger.info(f"   - financial_metrics exists: {'financial_metrics' in locals()}")
            logger.info(f"   - assessment_data exists: {'assessment_data' in locals()}")
            logger.info(f"   - reasoning_duration exists: {'reasoning_duration' in locals()}")
            logger.info(f"   - raw_response exists: {'raw_response' in locals()}")
            applicant_info = {
                "name": applicant_name,  # Already safe from earlier
                "idNumber": id_number if 'id_number' in locals() else "N/A",
                "age": age if 'age' in locals() else "N/A"
            }
            assessment_log = {
                "assessmentId": assessment_id,
                "applicationId": request.applicationId,
                "timestamp": datetime.now().isoformat(),
                "applicant": applicant_info, 
                "loanRequest": {
                    "amount": request.loanAmount,
                    "type": request.loanType,
                    "term": request.loanTerm,
                    "purpose": request.loanPurpose
                },
                "financialMetrics": {
                    "totalMonthlyIncome": total_monthly_income,
                    "currentDebtRatio": current_debt_ratio,
                    "projectedDebtRatio": new_debt_ratio,
                    "loanToValue": loan_to_value,
                    "estimatedMonthlyPayment": estimated_monthly_payment
                },
                "assessmentResult": assessment_data,
                "processingDetails": {
                    "reasoningDuration": reasoning_duration,
                    "totalProcessingTime": time.time() - processing_start,
                    "modelUsed": "deepseek-reasoning"
                },
                "rawResponse": raw_response
            }
            # ✅ CHECK DIRECTORY AND PERMISSIONS
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Directory check:")
            logger.info(f"   - RESULTS_DIR: {RESULTS_DIR}")
            logger.info(f"   - Directory exists: {os.path.exists(RESULTS_DIR)}")
            logger.info(f"   - Directory writable: {os.access(RESULTS_DIR, os.W_OK)}")
            # Save to file
            assessment_filename = f"loan_assessment_{assessment_id}_{request.applicationId}.json"
            assessment_filepath = os.path.join(RESULTS_DIR, assessment_filename)
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: File info:")
            logger.info(f"   - Filename: {assessment_filename}")
            logger.info(f"   - Full path: {assessment_filepath}")

            with open(assessment_filepath, 'w', encoding='utf-8') as f:
                json.dump(assessment_log, f, ensure_ascii=False, indent=2)

            # ✅ VERIFY FILE CREATION
            if os.path.exists(assessment_filepath):
                file_size = os.path.getsize(assessment_filepath)
                logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: Assessment log saved successfully")
                logger.info(f"📁 [LOAN ASSESSMENT] {assessment_id}: File: {assessment_filename}")
                logger.info(f"📁 [LOAN ASSESSMENT] {assessment_id}: Size: {file_size} bytes")
            else:
                logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: File was not created!")

        except Exception as log_error:
            logger.error(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Log saving error - {log_error}")
            import traceback
            logger.error(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Traceback - {traceback.format_exc()}")

        # ✅ STEP 8: Return successful response
        total_time = time.time() - processing_start

        processing_details = {
            "assessmentId": assessment_id,
            "processingTime": round(total_time, 2),
            "reasoningDuration": round(reasoning_duration, 2),
            "modelUsed": "deepseek-reasoning",
            "promptLength": len(assessment_prompt),
            "responseLength": len(raw_response),
            "financialMetrics": {
                "totalMonthlyIncome": total_monthly_income,
                "estimatedMonthlyPayment": int(estimated_monthly_payment),
                "projectedDebtRatio": round(new_debt_ratio, 3),
                "loanToValue": round(loan_to_value, 3)
            }
        }

        logger.info(f"🎉 [LOAN ASSESSMENT] {assessment_id}: Assessment completed successfully in {total_time:.2f}s")

        return LoanAssessmentResponse(
            success=True,
            applicationId=request.applicationId,
            assessmentId=assessment_id,
            status=assessment_data.get("status"),
            confidence=assessment_data.get("confidence"),
            creditScore=assessment_data.get("creditScore"),
            reasoning=assessment_data.get("reasoning"),
            riskFactors=assessment_data.get("riskFactors", []),
            recommendations=assessment_data.get("recommendations", []),
            approvedAmount=assessment_data.get("approvedAmount"),
            interestRate=assessment_data.get("interestRate"),
            monthlyPayment=assessment_data.get("monthlyPayment"),
            loanToValue=assessment_data.get("loanToValue"),
            debtToIncome=assessment_data.get("debtToIncome"),
            conditions=assessment_data.get("conditions", []),
            collateralValuation=assessment_data.get("collateralValuation"),
            financialAnalysis=assessment_data.get("financialAnalysis"),
            processingDetails=processing_details
        )

    except Exception as general_error:
        logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: General error - {general_error}")
        import traceback
        logger.error(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Traceback - {traceback.format_exc()}")

        return LoanAssessmentResponse(
            success=False,
            applicationId=request.applicationId if hasattr(request, 'applicationId') else "unknown",
            error=f"Assessment failed: {str(general_error)}",
            processingDetails={
                "processingTime": time.time() - processing_start
            }
        )


# ===== DOCUMENT INGESTION WORKFLOW =====
# Added for Backend integration workflow

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import redis
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
from datetime import datetime
import time

# Document Ingestion Models
class DocumentIngestionRequest(BaseModel):
    task_id: str
    user_id: str
    document_id: str
    r2_path: str
    file_name: str
    content_type: str
    task_type: str = "ingest_document"

class DocumentIngestionResponse(BaseModel):
    success: bool
    task_id: str
    message: str
    processing_details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class CallbackRequest(BaseModel):
    task_id: str
    user_id: str
    document_id: str
    status: str  # "COMPLETED" | "FAILED" | "PROCESSING"
    error_message: Optional[str] = None
    processing_details: Optional[Dict[str, Any]] = None

# Redis Queue Manager
class DocumentQueueManager:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        
    async def push_ingestion_task(self, task_data: Dict[str, Any]) -> bool:
        """Push task to ingestion queue"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self.redis_client.lpush, 
                "document_ingestion_queue", 
                json.dumps(task_data)
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to push task to queue: {e}")
            return False
    
    async def get_ingestion_task(self) -> Optional[Dict[str, Any]]:
        """Get task from ingestion queue"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.redis_client.brpop, 
                "document_ingestion_queue", 
                10  # timeout 10s
            )
            if result:
                return json.loads(result[1])
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get task from queue: {e}")
            return None

# R2 Document Processor
class R2DocumentProcessor:
    def __init__(self):
        # R2 Client
        try:
            import boto3
            from botocore.config import Config
            
            self.r2_client = boto3.client(
                's3',
                endpoint_url=os.getenv("R2_ENDPOINT"),
                aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )
            self.bucket_name = os.getenv("R2_BUCKET_NAME", "studynotes")
            
        except ImportError:
            logger.error("❌ boto3 not installed. Please install: pip install boto3")
            self.r2_client = None
        
        # Qdrant Client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance, PointStruct
            
            self.qdrant_client = QdrantClient(
                url=os.getenv("QDRANT_URL"),
                api_key=os.getenv("QDRANT_API_KEY")
            )
        except ImportError:
            logger.error("❌ qdrant-client not installed")
            self.qdrant_client = None
        
        # Embedding Model
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.error("❌ sentence-transformers not installed")
            self.embedder = None
    
    async def download_from_r2(self, r2_path: str) -> bytes:
        """Download file from R2"""
        if not self.r2_client:
            raise Exception("R2 client not available")
            
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.r2_client.get_object(Bucket=self.bucket_name, Key=r2_path)
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"❌ R2 download failed: {e}")
            raise
    
    def chunk_document(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Chunk document into smaller pieces"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            
            if end < len(content):
                # Find good breaking point
                last_sentence = chunk.rfind('. ')
                last_exclamation = chunk.rfind('! ')
                last_question = chunk.rfind('? ')
                last_newline = chunk.rfind('\n\n')
                
                break_points = [p for p in [last_sentence, last_exclamation, last_question, last_newline] if p > start + chunk_size // 2]
                
                if break_points:
                    break_point = max(break_points)
                    chunk = content[start:break_point + 2]
                    start = break_point + 2 - overlap
                else:
                    start = end - overlap
            else:
                start = len(content)
                
            cleaned_chunk = chunk.strip()
            if cleaned_chunk and len(cleaned_chunk) > 50:
                chunks.append(cleaned_chunk)
        
        return chunks
    
    async def store_in_qdrant(self, collection_name: str, chunks: List[str], user_id: str, document_id: str, filename: str) -> int:
        """Store chunks in Qdrant"""
        if not self.qdrant_client or not self.embedder:
            raise Exception("Qdrant client or embedder not available")
            
        try:
            from qdrant_client.models import VectorParams, Distance, PointStruct
            
            # Create collection if not exists
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                    )
                )
                logger.info(f"📚 Created collection: {collection_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"📚 Collection {collection_name} already exists")
                else:
                    raise e
            
            # Generate embeddings and points
            points = []
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.embedder.encode(chunk).tolist()
                )
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "user_id": user_id,
                        "document_id": document_id,
                        "filename": filename,
                        "chunk_index": i,
                        "content": chunk,
                        "word_count": len(chunk.split()),
                        "char_count": len(chunk),
                        "timestamp": datetime.now().isoformat(),
                        "chunk_id": f"{document_id}_chunk_{i:03d}"
                    }
                )
                points.append(point)
            
            # Upsert to Qdrant
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(collection_name=collection_name, points=points)
            )
            
            logger.info(f"💾 Stored {len(points)} chunks in Qdrant collection '{collection_name}'")
            return len(points)
            
        except Exception as e:
            logger.error(f"❌ Qdrant storage failed: {e}")
            raise

# Initialize components
queue_manager = DocumentQueueManager()
document_processor = R2DocumentProcessor()

async def send_callback_to_backend(task_id: str, user_id: str, document_id: str, status: str, 
                                 processing_details: Dict = None, error_message: str = None):
    """Send callback to backend when processing is complete"""
    try:
        backend_callback_url = os.getenv("BACKEND_CALLBACK_URL", "http://localhost:3000/api/documents/ingestion-callback")
        
        callback_data = {
            "task_id": task_id,
            "user_id": user_id,
            "document_id": document_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "processing_details": processing_details,
            "error_message": error_message
        }
        
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                backend_callback_url,
                json=callback_data
            )
            
            if response.status_code == 200:
                logger.info(f"✅ [CALLBACK] Sent to backend: {task_id}")
            else:
                logger.warning(f"⚠️ [CALLBACK] Backend returned {response.status_code}")
                
    except Exception as e:
        logger.error(f"❌ [CALLBACK] Failed to send callback: {e}")

# Document Worker
class DocumentWorker:
    def __init__(self):
        self.queue_manager = queue_manager
        self.processor = document_processor
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def start(self):
        """Start the document processing worker"""
        self.running = True
        logger.info("🔄 [WORKER] Document ingestion worker started")
        
        while self.running:
            try:
                # Get task from queue
                task_data = await self.queue_manager.get_ingestion_task()
                
                if task_data:
                    logger.info(f"📥 [WORKER] Processing task: {task_data.get('task_id')}")
                    
                    # Process the task
                    await self.process_document_task(task_data)
                else:
                    # No task available, wait a bit
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"❌ [WORKER] Error: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def process_document_task(self, task_data: Dict[str, Any]):
        """Process a single document ingestion task"""
        task_id = task_data.get('task_id')
        user_id = task_data.get('user_id')
        document_id = task_data.get('document_id')
        r2_path = task_data.get('r2_path')
        filename = task_data.get('file_name')
        content_type = task_data.get('content_type')
        
        processing_start = time.time()
        
        try:
            logger.info(f"📥 [INGESTION] {task_id}: Starting document ingestion")
            logger.info(f"👤 [INGESTION] {task_id}: User: {user_id}")
            logger.info(f"📄 [INGESTION] {task_id}: Document: {document_id}")
            logger.info(f"📁 [INGESTION] {task_id}: R2 Path: {r2_path}")
            
            # Step 1: Download file from R2
            logger.info(f"⬇️ [INGESTION] {task_id}: Downloading from R2...")
            file_content = await self.processor.download_from_r2(r2_path)
            logger.info(f"✅ [INGESTION] {task_id}: Downloaded {len(file_content)} bytes")
            
            # Step 2: Extract text based on content type
            logger.info(f"📝 [INGESTION] {task_id}: Extracting text...")
            
            if content_type == "application/pdf":
                import base64
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                extracted_text = extract_text_from_pdf(file_base64)
            elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                import base64
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                extracted_text = extract_text_from_docx(file_base64)
            elif content_type.startswith("text/"):
                extracted_text = file_content.decode('utf-8')
            else:
                raise Exception(f"Unsupported content type: {content_type}")
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                raise Exception("No text content extracted from document")
            
            logger.info(f"✅ [INGESTION] {task_id}: Extracted {len(extracted_text)} characters")
            
            # Step 3: Chunk document
            logger.info(f"🔪 [INGESTION] {task_id}: Chunking document...")
            chunks = self.processor.chunk_document(extracted_text)
            logger.info(f"✅ [INGESTION] {task_id}: Created {len(chunks)} chunks")
            
            # Step 4: Store in Qdrant
            logger.info(f"💾 [INGESTION] {task_id}: Storing in Qdrant...")
            collection_name = f"user_{user_id}_documents"
            stored_chunks = await self.processor.store_in_qdrant(
                collection_name, chunks, user_id, document_id, filename
            )
            
            # Step 5: Send success callback
            processing_time = time.time() - processing_start
            processing_details = {
                "chunks_created": len(chunks),
                "chunks_stored": stored_chunks,
                "text_length": len(extracted_text),
                "processing_time": processing_time,
                "collection_name": collection_name
            }
            
            await send_callback_to_backend(
                task_id=task_id,
                user_id=user_id,
                document_id=document_id,
                status="COMPLETED",
                processing_details=processing_details
            )
            
            logger.info(f"🎉 [INGESTION] {task_id}: Completed successfully in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ [INGESTION] {task_id}: Failed - {e}")
            
            # Send failure callback
            await send_callback_to_backend(
                task_id=task_id,
                user_id=user_id,
                document_id=document_id,
                status="FAILED",
                error_message=str(e)
            )
    
    def stop(self):
        """Stop the worker"""
        self.running = False
        logger.info("🛑 [WORKER] Document ingestion worker stopped")

# Initialize worker
document_worker = DocumentWorker()

# Start the worker in a separate thread
@app.on_event("startup")
async def startup_event():
    # Start the document worker
    loop = asyncio.get_event_loop()
    loop.create_task(document_worker.start())
    
    # Run the scheduler in the background
    loop.run_in_executor(None, run_scheduler)

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the document worker
    document_worker.stop()
    logger.info("AI Service is shutting down...")
