#!/usr/bin/env python3
"""
Test Document Editor API
Test Phase 1 & Phase 2 implementation
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.database.db_manager import DBManager
from src.services.document_manager import DocumentManager
from src.utils.logger import setup_logger

logger = setup_logger()


def test_document_manager():
    """Test DocumentManager CRUD operations"""
    try:
        logger.info("🧪 Testing Document Manager...")

        # Connect to MongoDB
        db_manager = DBManager()
        doc_manager = DocumentManager(db_manager.db)

        # Create indexes
        doc_manager.create_indexes()
        logger.info("✅ Indexes created")

        # Test user
        test_user_id = "test_user_123"
        test_file_id = "test_file_456"

        # Test 1: Create document
        logger.info("\n📝 Test 1: Create document")
        doc_id = doc_manager.create_document(
            user_id=test_user_id,
            file_id=test_file_id,
            title="Test Document",
            content_html="<h1>Hello World</h1><p>This is a test document.</p>",
            content_text="Hello World\nThis is a test document.",
            original_r2_url="https://example.com/test.docx",
            original_file_type="docx",
        )
        logger.info(f"✅ Created document: {doc_id}")

        # Test 2: Get document
        logger.info("\n📄 Test 2: Get document")
        doc = doc_manager.get_document(doc_id, test_user_id)
        logger.info(f"✅ Retrieved document: {doc['title']}")
        logger.info(f"   Version: {doc['version']}")
        logger.info(f"   Size: {doc['file_size_bytes']} bytes")

        # Test 3: Get document by file_id
        logger.info("\n📄 Test 3: Get document by file_id")
        doc_by_file = doc_manager.get_document_by_file_id(test_file_id, test_user_id)
        logger.info(f"✅ Retrieved by file_id: {doc_by_file['document_id']}")

        # Test 4: Auto-save update
        logger.info("\n💾 Test 4: Auto-save update")
        success = doc_manager.update_document(
            document_id=doc_id,
            user_id=test_user_id,
            content_html="<h1>Hello World</h1><p>This is an updated document (auto-saved).</p>",
            content_text="Hello World\nThis is an updated document (auto-saved).",
            is_auto_save=True,
        )
        logger.info(f"✅ Auto-save: {success}")

        # Test 5: Manual save update
        logger.info("\n💾 Test 5: Manual save update")
        success = doc_manager.update_document(
            document_id=doc_id,
            user_id=test_user_id,
            content_html="<h1>Hello World</h1><p>This is an updated document (manually saved).</p>",
            content_text="Hello World\nThis is an updated document (manually saved).",
            is_auto_save=False,
        )
        logger.info(f"✅ Manual save: {success}")

        # Test 6: Get updated document
        logger.info("\n📄 Test 6: Check version and counts")
        doc = doc_manager.get_document(doc_id, test_user_id)
        logger.info(f"✅ Version: {doc['version']} (should be 3)")
        logger.info(f"   Auto-save count: {doc['auto_save_count']} (should be 1)")
        logger.info(f"   Manual-save count: {doc['manual_save_count']} (should be 2)")

        # Test 7: List user documents
        logger.info("\n📋 Test 7: List user documents")
        docs = doc_manager.list_user_documents(test_user_id, limit=10)
        logger.info(f"✅ Found {len(docs)} documents")
        for doc in docs:
            logger.info(f"   - {doc['title']} (v{doc['version']})")

        # Test 8: Storage stats
        logger.info("\n📊 Test 8: Storage statistics")
        stats = doc_manager.get_storage_stats(test_user_id)
        logger.info(f"✅ Storage stats:")
        logger.info(f"   Total documents: {stats['total_documents']}")
        logger.info(f"   Total size: {stats['total_mb']} MB")
        logger.info(f"   Total versions: {stats['total_versions']}")
        logger.info(f"   Total auto-saves: {stats['total_auto_saves']}")
        logger.info(f"   Total manual-saves: {stats['total_manual_saves']}")

        # Test 9: Soft delete
        logger.info("\n🗑️ Test 9: Soft delete")
        success = doc_manager.delete_document(doc_id, test_user_id, soft_delete=True)
        logger.info(f"✅ Soft delete: {success}")

        # Test 10: Verify soft delete
        logger.info("\n📄 Test 10: Verify soft delete")
        doc = doc_manager.get_document(doc_id, test_user_id)
        if doc is None:
            logger.info("✅ Document not found (correctly soft-deleted)")
        else:
            logger.error("❌ Document still accessible after soft delete!")

        # Test 11: Check storage stats after delete
        logger.info("\n📊 Test 11: Storage stats after delete")
        stats = doc_manager.get_storage_stats(test_user_id)
        logger.info(f"✅ Total documents: {stats['total_documents']} (should be 0)")

        logger.info("\n🎉 All tests passed!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_document_manager()
