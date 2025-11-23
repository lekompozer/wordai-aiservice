import os
from pathlib import Path

# ✅ FIXED: Only load environment if not already loaded by serve.py
if not os.getenv("CONFIG_LOADED"):
    try:
        from dotenv import load_dotenv

        ENV = os.getenv("ENV", os.getenv("ENV", "production")).lower()

        if ENV == "development":
            # Try development.env first, fallback to .env
            dev_env_file = Path(__file__).parent.parent / "development.env"
            env_file = Path(__file__).parent.parent / ".env"

            if dev_env_file.exists():
                load_dotenv(dev_env_file, override=True)
                print(f"Config: Loaded DEVELOPMENT from development.env")
            elif env_file.exists():
                load_dotenv(env_file, override=True)
                print(f"Config: Loaded DEVELOPMENT from .env (fallback)")
            else:
                print(f"Config: No environment file found for development")
        else:
            # Production - use .env
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                load_dotenv(env_file, override=True)
                print(f"Config: Loaded PRODUCTION from .env")
            else:
                print(f"Config: No .env file found for production")

    except ImportError:
        print("Config: python-dotenv not installed, using environment variables only")
else:
    print("Config: Environment already loaded by serve.py, skipping .env loading")

# ✅ Get environment after loading
ENV = os.getenv("ENV", "production").lower()

# ✅ FIXED: Remove hardcoded API key, use environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ChatGPT configs
CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY")
CHATGPT_MODEL = os.getenv("CHATGPT_MODEL", "gpt-4-1106-preview")
CHATGPT_REASONING_MODEL = os.getenv("CHATGPT_REASONING_MODEL", "gpt-4o")
CHATGPT_VISION_REASONING_MODEL = os.getenv("CHATGPT_VISION_REASONING_MODEL", "gpt-4o")

# Cerebras configs
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507")

# Gemini configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash")

# Anthropic/Claude configs
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv(
    "CLAUDE_MODEL", "claude-sonnet-4-5-20250929"
)  # Sonnet 4.5 - Production model
CLAUDE_SONNET_MODEL = os.getenv(
    "CLAUDE_SONNET_MODEL", "claude-sonnet-4-5-20250929"
)  # Sonnet 4.5 - Production model

# AI Provider setting
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "deepseek")

# ✅ Environment-specific database configuration
if ENV == "development":
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    MONGODB_NAME = os.getenv("MONGODB_NAME", "ai_service_dev_db")
    DATA_DIR = os.getenv("DATA_DIR", "./data")
    # Use authenticated URI in development if available
    MONGODB_URI_AUTH = os.getenv("MONGODB_URI_AUTH", MONGODB_URI)
    print(f"Config: Development database - {MONGODB_URI}")
    print(f"Config: Development data dir - {DATA_DIR}")
else:
    # FIXED: Use Docker network container name in production
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")
    MONGODB_NAME = os.getenv("MONGODB_NAME", "ai_service_db")
    DATA_DIR = os.getenv("DATA_DIR", "/app/data")
    # Use authenticated URI in production (CRITICAL for security)
    MONGODB_URI_AUTH = os.getenv("MONGODB_URI_AUTH", MONGODB_URI)
    print(f"Config: Production database - {MONGODB_URI}")
    print(f"Config: Production authenticated URI - {MONGODB_URI_AUTH}")
    print(f"Config: Production data dir - {DATA_DIR}")

# RAG Configuration
CHUNK_SIZE = 1000
OVERLAP = 200
RAG_SETTINGS = {
    "SIMILARITY_THRESHOLD": 0.65,
    "MIN_SIMILARITY_SCORE": 0.37,
    "FALLBACK_RESPONSE": "Tôi sẽ trả lời dựa trên kiến thức tổng quan:",
    "DEFAULT_FALLBACK": "Hiện không thể tra cứu. Vui lòng liên hệ ngân hàng để biết thêm chi tiết.",
    "chunk_size": int(os.getenv("CHUNK_SIZE", "1000")),
    "overlap": int(os.getenv("OVERLAP", "200")),
    "top_k": int(os.getenv("TOP_K", "3")),
}

# ✅ ADDED: SerpAPI Key
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ✅ ADDED: R2 (Cloudflare) Configuration
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")

# ✅ ADDED: Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ✅ ADDED: Qdrant Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "multi_company_data")

# ✅ ADDED: Embedding Configuration - Unified Model
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2"
)  # Default to sentence-transformers model
VECTOR_SIZE = int(
    os.getenv("VECTOR_SIZE", "768")
)  # Default back to 768 for paraphrase-multilingual-mpnet-base-v2

# ✅ ADDED: Backend Configuration
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:3000")

# ✅ ADDED: Document Processing Configuration
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB
PROCESSING_TIMEOUT = int(os.getenv("PROCESSING_TIMEOUT", "600"))  # 10 minutes
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


# ✅ ADDED: Helper function to get R2 client
def get_r2_client():
    """
    Get configured boto3 S3 client for R2 storage

    Returns:
        boto3.client: Configured S3 client for Cloudflare R2
    """
    import boto3

    if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT]):
        raise ValueError(
            "Missing R2 credentials. Check R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT"
        )

    return boto3.client(
        "s3",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        endpoint_url=R2_ENDPOINT,
        region_name="auto",
    )


# ✅ ADDED: Helper function to get MongoDB client
def get_mongodb():
    """
    Get MongoDB database instance with authentication

    Returns:
        pymongo.database.Database: MongoDB database
    """
    from pymongo import MongoClient

    # Use authenticated URI if available (production), fallback to basic URI (development)
    mongo_uri = (
        MONGODB_URI_AUTH
        if "MONGODB_URI_AUTH" in locals() or "MONGODB_URI_AUTH" in globals()
        else MONGODB_URI
    )

    # Try to get from environment as final fallback
    mongo_uri = os.getenv("MONGODB_URI_AUTH", mongo_uri)

    client = MongoClient(mongo_uri)
    return client[MONGODB_NAME]


# ✅ ADDED: Debug logging for config verification
print(f"🔧 Config.py loaded:")
print(f"   Environment: {ENV}")
print(f"   DeepSeek API: {'✅' if DEEPSEEK_API_KEY else '❌'}")
print(f"   ChatGPT API: {'✅' if CHATGPT_API_KEY else '❌'}")
print(f"   Gemini API: {'✅' if GEMINI_API_KEY else '❌'}")
print(f"   SerpAPI: {'✅' if SERPAPI_KEY else '❌'}")
print(f"   Default AI: {DEFAULT_AI_PROVIDER}")
print(f"   MongoDB: {MONGODB_URI}")
print(f"   Data Dir: {DATA_DIR}")
print(f"   R2 Bucket: {'✅' if R2_BUCKET_NAME else '❌'}")
print(f"   Qdrant: {'✅' if QDRANT_URL else '❌'}")
print(f"   Redis: {'✅' if REDIS_URL else '❌'}")

# ✅ ADDED: Export all configuration to environment variables
# This ensures other modules get the correct config
os.environ["DEEPSEEK_API_KEY"] = DEEPSEEK_API_KEY or ""
os.environ["CHATGPT_API_KEY"] = CHATGPT_API_KEY or ""
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY or ""
os.environ["DEFAULT_AI_PROVIDER"] = DEFAULT_AI_PROVIDER
os.environ["SERPAPI_KEY"] = SERPAPI_KEY or ""
os.environ["MONGODB_URI"] = MONGODB_URI
os.environ["MONGODB_NAME"] = MONGODB_NAME
os.environ["DATA_DIR"] = DATA_DIR
os.environ["R2_ENDPOINT"] = R2_ENDPOINT or ""
os.environ["R2_ACCESS_KEY_ID"] = R2_ACCESS_KEY_ID or ""
os.environ["R2_SECRET_ACCESS_KEY"] = R2_SECRET_ACCESS_KEY or ""
os.environ["R2_BUCKET_NAME"] = R2_BUCKET_NAME or ""
os.environ["QDRANT_URL"] = QDRANT_URL or ""
os.environ["QDRANT_API_KEY"] = QDRANT_API_KEY or ""
os.environ["QDRANT_COLLECTION_NAME"] = QDRANT_COLLECTION_NAME or ""
os.environ["REDIS_URL"] = REDIS_URL or ""
