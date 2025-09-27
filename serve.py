#!/usr/bin/env python3
"""
AI Chatbot RAG Service - Optimized Main Server
Refactored for better maintainability and modularity

Original file was 2989 lines, now split into modular components:
- src/core/config.py - Configuration management
- src/core/models.py - Pydantic models
- src/core/document_utils.py - Document processing utilities
- src/api/health_routes.py - Health check endpoints
- src/api/chat_routes.py - Chat endpoints
- src/api/real_estate_routes.py - Real estate analysis endpoints
- src/api/ocr_routes.py - OCR processing endpoints
- src/api/loan_routes.py - Loan assessment endpoints
- src/app.py - FastAPI application factory

This keeps all original functionality while improving code organization.
"""

# Core imports for FastAPI server
import uvicorn
import sys
from pathlib import Path

# Add src to Python path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# ✅ CRITICAL: Initialize Firebase BEFORE any other imports
# This ensures firebase_admin is initialized before any module can import it
try:
    import firebase_admin
    from firebase_admin import credentials
    import os
    import json

    # Check if already initialized
    if not firebase_admin._apps:
        # Try to load from environment variables first (production)
        firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
        firebase_private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").replace(
            "\\n", "\n"
        )
        firebase_client_email = os.getenv("FIREBASE_CLIENT_EMAIL")

        if firebase_project_id and firebase_private_key and firebase_client_email:
            # Initialize from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": firebase_project_id,
                "private_key": firebase_private_key,
                "client_email": firebase_client_email,
            }
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK initialized from environment variables")
        else:
            # Fallback to file (development)
            cred_path = Path(__file__).parent / "firebase-credentials.json"
            if cred_path.exists():
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin SDK initialized from credentials file")
            else:
                print(
                    "⚠️ WARNING: Firebase credentials not found, Firebase not initialized"
                )
    else:
        print("✅ Firebase Admin SDK already initialized")

except Exception as e:
    print(f"🔥 FATAL: Failed to initialize Firebase: {e}", file=sys.stderr)
    sys.exit(1)


# Import the optimized FastAPI application
from src.app import app
from src.core.config import APP_CONFIG


def main():
    """
    ✅ MAIN: Start the optimized FastAPI server
    """
    print("🚀 AI Chatbot RAG Service - Optimized Version")
    print("=" * 60)
    print("📂 Code Structure:")
    print("   ├── serve.py (this file) - Main entry point")
    print("   └── src/")
    print("       ├── core/")
    print("       │   ├── config.py - Environment & settings")
    print("       │   ├── models.py - Pydantic request/response models")
    print("       │   └── document_utils.py - File processing utilities")
    print("       ├── api/")
    print("       │   ├── health_routes.py - Health check endpoints")
    print("       │   ├── chat_routes.py - Chat functionality")
    print("       │   ├── real_estate_routes.py - Real estate analysis")
    print("       │   ├── ocr_routes.py - OCR processing")
    print("       │   └── loan_routes.py - Loan assessment")
    print("       └── app.py - FastAPI application factory")
    print("=" * 60)
    print(f"🌐 Starting server on {APP_CONFIG['host']}:{APP_CONFIG['port']}")
    print(
        f"🔧 Environment: {APP_CONFIG.get('debug', False) and 'Development' or 'Production'}"
    )
    print(f"📚 API Documentation: {APP_CONFIG['base_url']}/docs")
    print("=" * 60)

    # Start the server with uvicorn
    if APP_CONFIG["debug"]:
        # Development mode: use import string for auto-reload
        uvicorn.run(
            "src.app:app",  # Import string format
            host=APP_CONFIG["host"],
            port=APP_CONFIG["port"],
            reload=True,
            access_log=True,
            log_level="info",
        )
    else:
        # Production mode: use app instance
        uvicorn.run(
            app,
            host=APP_CONFIG["host"],
            port=APP_CONFIG["port"],
            reload=False,
            access_log=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
