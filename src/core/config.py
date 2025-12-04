"""
Core configuration and settings for the FastAPI application
"""

import os
import sys
from pathlib import Path
from typing import List


def load_environment():
    """
    ✅ SMART: Environment configuration loading
    Load environment files based on ENV variable
    """
    ENV = os.getenv("ENV", "production").lower()

    try:
        from dotenv import load_dotenv

        if ENV == "development":
            # Development: ONLY use development files, do NOT fallback to production .env
            dev_env_file = Path(__file__).parent.parent.parent / ".env.development"
            fallback_dev_env = Path(__file__).parent.parent.parent / "development.env"

            if dev_env_file.exists():
                load_dotenv(dev_env_file, override=True)
                print(f"Loaded DEVELOPMENT configuration from .env.development")
            elif fallback_dev_env.exists():
                load_dotenv(fallback_dev_env, override=True)
                print(f"Loaded DEVELOPMENT configuration from development.env")
            else:
                print(f"WARNING: No development environment file found!")
        else:
            # Production - use .env only
            env_file = Path(__file__).parent.parent.parent / ".env"
            if env_file.exists():
                load_dotenv(env_file, override=True)
                print(f"Loaded PRODUCTION configuration from .env")
            else:
                print(f"No .env file found for production")

    except ImportError:
        print("python-dotenv not installed, using environment variables only")


def get_app_config():
    """
    ✅ Get application configuration based on environment
    """
    # Re-read ENV after loading files
    ENV = os.getenv("ENV", "production").lower()

    if ENV == "development":
        # Development configuration
        config = {
            "debug": True,
            "host": "localhost",
            "port": 8000,
            "domain": "localhost:8000",
            "base_url": "http://localhost:8000",
            "cors_origins": [
                "http://localhost:3000",
                "http://localhost:8080",
                "http://localhost:8001",
                "http://127.0.0.1:3002",
                "http://127.0.0.1:8080",
                "http://127.0.0.1:8000",
                # Production domains
                "https://api.agent8x.io.vn",
                "https://agent8x.io.vn",
                "https://admin.agent8x.io.vn",
            ],
            # AI Provider keys
            "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
            "CHATGPT_API_KEY": os.getenv("CHATGPT_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
            "CEREBRAS_API_KEY": os.getenv("CEREBRAS_API_KEY", ""),
            "default_ai_provider": os.getenv("DEFAULT_AI_PROVIDER", "cerebras"),
            # Qdrant configuration
            "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
            "qdrant_host": os.getenv("QDRANT_HOST", "localhost"),
            "qdrant_port": int(os.getenv("QDRANT_PORT", 6333)),
            "qdrant_api_key": os.getenv("QDRANT_API_KEY", ""),
            # R2 Storage configuration
            "r2_account_id": os.getenv("R2_ACCOUNT_ID", ""),
            "r2_access_key_id": os.getenv("R2_ACCESS_KEY_ID", ""),
            "r2_secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", ""),
            "r2_bucket_name": os.getenv("R2_BUCKET_NAME", ""),
            "r2_endpoint": os.getenv("R2_ENDPOINT", ""),
            "r2_public_url": os.getenv("R2_PUBLIC_URL", ""),
            "r2_region": os.getenv("R2_REGION", "auto"),
            # 🆕 Webhook and CORS configuration
            "backend_webhook_url": os.getenv(
                "BACKEND_WEBHOOK_URL", "http://localhost:8001"
            ),
            "webhook_secret": os.getenv(
                "WEBHOOK_SECRET", "webhook-secret-for-signature"
            ),
            "internal_api_key": os.getenv(
                "INTERNAL_API_KEY", "agent8x-backend-secret-key-2025"
            ),
        }
        print(f"🔧 Development mode active")
        print(f"   Debug: {config['debug']}")
        print(f"   Host: {config['host']}")
        print(f"   Port: {config['port']}")
        print(f"   Domain: {config['domain']}")
        print(f"   Base URL: {config['base_url']}")

    else:
        # Production configuration (from .env or environment variables)
        config = {
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "host": os.getenv("HOST", "0.0.0.0"),
            "port": int(os.getenv("PORT", 8000)),
            "domain": os.getenv("DOMAIN", "ai.wordai.pro"),
            "base_url": os.getenv(
                "BASE_URL", f"https://{os.getenv('DOMAIN', 'ai.wordai.pro')}"
            ),
            "cors_origins": (
                list(
                    set(
                        os.getenv(
                            "CORS_ORIGINS",
                            "https://api.agent8x.io.vn,https://agent8x.io.vn,https://admin.agent8x.io.vn,https://aivungtau.com,https://www.aivungtau.com,https://api.aivungtau.com",
                        ).split(",")
                    )
                )
                if os.getenv("CORS_ORIGINS")
                else [
                    "https://api.agent8x.io.vn",
                    "https://agent8x.io.vn",
                    "https://admin.agent8x.io.vn",
                    "https://aivungtau.com",
                    "https://www.aivungtau.com",
                    "https://api.aivungtau.com",
                ]
            ),
            # AI Provider keys
            "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
            "CHATGPT_API_KEY": os.getenv("CHATGPT_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
            "CEREBRAS_API_KEY": os.getenv("CEREBRAS_API_KEY", ""),
            "default_ai_provider": os.getenv("DEFAULT_AI_PROVIDER", "cerebras"),
            # Qdrant configuration
            "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
            "qdrant_host": os.getenv("QDRANT_HOST", "localhost"),
            "qdrant_port": int(os.getenv("QDRANT_PORT", 6333)),
            "qdrant_api_key": os.getenv("QDRANT_API_KEY", ""),
            # R2 Storage configuration
            "r2_account_id": os.getenv("R2_ACCOUNT_ID", ""),
            "r2_access_key_id": os.getenv("R2_ACCESS_KEY_ID", ""),
            "r2_secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", ""),
            "r2_bucket_name": os.getenv("R2_BUCKET_NAME", ""),
            "r2_endpoint": os.getenv("R2_ENDPOINT", ""),
            "r2_public_url": os.getenv("R2_PUBLIC_URL", ""),
            "r2_region": os.getenv("R2_REGION", "auto"),
            # 🆕 Webhook and CORS configuration
            "backend_webhook_url": os.getenv(
                "BACKEND_WEBHOOK_URL", "http://localhost:8001"
            ),
            "webhook_secret": os.getenv(
                "WEBHOOK_SECRET", "webhook-secret-for-signature"
            ),
            "internal_api_key": os.getenv(
                "INTERNAL_API_KEY", "agent8x-backend-secret-key-2025"
            ),
        }

        print(f"🚀 Production mode active")
        print(f"   Debug: {config['debug']}")
        print(f"   Host: {config['host']}")
        print(f"   Port: {config['port']}")
        print(f"   Domain: {config['domain']}")

    return config


# Initialize environment on import
load_environment()
APP_CONFIG = get_app_config()
