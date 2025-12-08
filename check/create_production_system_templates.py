#!/usr/bin/env python3
"""
Production System Template Creator
Tạo system templates cho production deployment
"""

import asyncio
import os
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load production environment
load_dotenv(".env")


async def create_production_system_templates():
    """Tạo system templates cho production"""

    # Get MongoDB connection details from .env
    mongo_uri = os.getenv("MONGODB_URI_AUTH")

    # Debug: Always check Docker environment and override if needed
    print(
        f"🔍 Debug: MONGODB_URI_AUTH = {mongo_uri[:50] if mongo_uri else 'NOT SET'}..."
    )
    print(f"🔍 Debug: Docker environment check: {os.path.exists('/.dockerenv')}")

    if not mongo_uri:
        print("📋 Building MongoDB URI from components...")
        # Fallback: build authenticated URI from components
        mongo_user = os.getenv("MONGODB_APP_USERNAME")
        mongo_pass = os.getenv("MONGODB_APP_PASSWORD")

        # Check if running in Docker container (production deployment)
        if os.path.exists("/.dockerenv"):
            # In Docker container - use container name 'mongodb'
            mongo_host = "mongodb:27017"
            print("🐳 Running in Docker container - using container name: mongodb")
        else:
            # Local development - use host.docker.internal or localhost
            mongo_host = (
                os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
                .replace("mongodb://", "")
                .rstrip("/")
            )
            print(f"🏠 Running locally - using host: {mongo_host}")

        db_name = os.getenv("MONGODB_NAME", "ai_service_db")

        if mongo_user and mongo_pass:
            mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
        else:
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    else:
        print("📋 Using existing MONGODB_URI_AUTH...")
        # Check if we're in Docker and need to replace host
        if os.path.exists("/.dockerenv") and "host.docker.internal" in mongo_uri:
            print(
                "🐳 Docker detected: Replacing host.docker.internal with mongodb container name"
            )
            mongo_uri = mongo_uri.replace("host.docker.internal:27017", "mongodb:27017")
            print(f"🔄 Updated URI: {mongo_uri[:50]}...")

    db_name = os.getenv("MONGODB_NAME", "ai_service_db")

    print(f"🔗 Connecting to production database: {db_name}")
    print(f"📡 Using URI: {mongo_uri[:50]}...")

    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        # Test connection
        await client.admin.command("ping")
        print("✅ Connected to production MongoDB")

        # Check if system template already exists
        existing = await db.document_templates.find_one({"_id": "template_quote_001"})
        if existing:
            print(
                f"⚠️  System template already exists: {existing.get('name', 'Unknown')}"
            )

            # Auto-overwrite in Docker environment (production deployment)
            if os.path.exists("/.dockerenv"):
                print(
                    "🐳 Docker environment detected - auto-overwriting existing template"
                )
                # Delete existing template
                await db.document_templates.delete_one({"_id": "template_quote_001"})
                print("🗑️  Deleted existing template")
            else:
                # Ask for confirmation in local environment
                response = input("Do you want to overwrite? (y/N): ").strip().lower()
                if response != "y":
                    print("❌ Aborted by user")
                    return

                # Delete existing template
                await db.document_templates.delete_one({"_id": "template_quote_001"})
                print("🗑️  Deleted existing template")

        # Production system template data with REAL file URLs
        system_template = {
            "_id": "template_quote_001",
            "user_id": "system",
            "name": "Mẫu báo giá chuẩn",
            "description": "Template chuẩn cho báo giá dịch vụ phần mềm và website",
            "category": "software_development",
            "type": "quote",
            "subtype": "business",
            "is_system_template": True,
            "is_public": True,
            # Production file URLs (Cloudflare R2)
            "files": {
                "docx_url": "https://static.agent8x.io.vn/templates/system/template_quote_001/template.docx",
                "pdf_url": None,
                "thumbnail_urls": [],
            },
            # AI Analysis data
            "ai_analysis": {
                "confidence_score": 0.95,
                "analysis_version": "1.0",
                "placeholders": {
                    "{{company_name}}": {
                        "type": "text",
                        "description": "Tên công ty",
                        "default_value": "",
                        "validation_rules": ["required", "min_length:2"],
                        "section": "header",
                        "auto_populate": False,
                    },
                    "{{company_address}}": {
                        "type": "text",
                        "description": "Địa chỉ công ty",
                        "default_value": "",
                        "section": "header",
                    },
                    "{{quote_date}}": {
                        "type": "date",
                        "description": "Ngày báo giá",
                        "auto_populate": True,
                        "section": "header",
                    },
                    "{{total_amount}}": {
                        "type": "currency",
                        "description": "Tổng tiền",
                        "auto_populate": True,
                        "calculation_formula": "sum(item_amounts)",
                        "section": "summary",
                    },
                },
                "sections": [
                    {
                        "name": "company_info",
                        "description": "Thông tin công ty",
                        "placeholders": ["{{company_name}}", "{{company_address}}"],
                        "order": 1,
                        "required": True,
                    },
                    {
                        "name": "quote_items",
                        "description": "Danh sách sản phẩm/dịch vụ",
                        "is_repeatable": True,
                        "order": 2,
                    },
                    {
                        "name": "summary",
                        "description": "Tổng kết báo giá",
                        "placeholders": ["{{total_amount}}"],
                        "order": 3,
                        "required": True,
                    },
                ],
                "document_structure": {
                    "total_pages": 2,
                    "has_tables": True,
                    "table_locations": ["quote_items"],
                    "header_content": "Company logo and info",
                    "footer_content": "Terms and signature",
                },
            },
            "validation": {"is_valid": True, "errors": [], "warnings": []},
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": "system",
            "version": "1.0",
        }

        # Insert system template
        result = await db.document_templates.insert_one(system_template)

        if result.inserted_id:
            print("✅ Production system template created successfully!")
            print(f"   ID: {system_template['_id']}")
            print(f"   Name: {system_template['name']}")
            print(f"   DOCX: {system_template['files']['docx_url']}")
            print(f"   Database: {db_name}")
        else:
            print("❌ Failed to create system template")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        client.close()


async def main():
    """Main function"""
    print("🚀 Production System Template Creator")
    print("=" * 50)

    # Check if .env exists
    if not os.path.exists(".env"):
        print("❌ .env file not found!")
        print("   Make sure you have production .env file")
        sys.exit(1)

    await create_production_system_templates()


if __name__ == "__main__":
    asyncio.run(main())
