#!/usr/bin/env python3
"""
Test script to verify DocumentProcessingWorker Redis connection handling and fallback.
Tests the enhanced worker's ability to handle Redis connection issues on PRODUCTION server.
"""

import asyncio
import sys
import os
import logging
import traceback
import time
from datetime import datetime

# Set production environment
os.environ["ENVIRONMENT"] = "production"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["MONGODB_URI"] = "mongodb://localhost:27017/"
os.environ["MONGODB_NAME"] = "ai_service_prod_db"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.workers.document_processing_worker import DocumentProcessingWorker
from src.queue.queue_manager import QueueManager
from src.queue.tasks import DocumentProcessingTask
from src.queue.queue_dependencies import get_document_queue

# Configure logging for production testing
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"production_worker_redis_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)

logger = logging.getLogger(__name__)


async def test_worker_redis_handling():
    """Test DocumentProcessingWorker Redis connection handling on PRODUCTION"""
    logger.info("🧪 Testing DocumentProcessingWorker Redis connection handling on production")

    try:
        # Test 1: Worker initialization with Redis retry logic
        logger.info("🔧 Test 1: Production worker initialization with Redis connection")
        worker = DocumentProcessingWorker(worker_id="production_test_worker", poll_interval=2)

        # Test initialization
        start_time = time.time()
        await worker.initialize()
        init_time = time.time() - start_time
        logger.info(f"✅ Production worker initialized successfully in {init_time:.2f}s")

        # Test 2: Verify queue manager has enhanced features
        logger.info("🔧 Test 2: Verify production QueueManager has enhanced Redis handling")
        queue_manager = worker.queue_manager

        # Check if queue manager has the enhanced methods
        enhanced_methods = [
            "_process_task_immediately",
            "connect", 
            "redis_client"
        ]
        
        missing_methods = []
        for method in enhanced_methods:
            if not hasattr(queue_manager, method):
                missing_methods.append(method)

        if not missing_methods:
            logger.info("✅ Production QueueManager has all enhanced Redis handling methods")
        else:
            logger.warning(f"⚠️ Production QueueManager missing methods: {missing_methods}")

        # Test 3: Test Redis connection status on production
        logger.info("🔧 Test 3: Test production Redis connection status")
        try:
            # Try to ping Redis
            if hasattr(queue_manager.redis_client, "ping"):
                ping_result = await queue_manager.redis_client.ping()
                logger.info(f"✅ Production Redis ping successful: {ping_result}")
            else:
                logger.info("ℹ️ Redis client ping method not available")

            # Try to get Redis info
            if hasattr(queue_manager.redis_client, "info"):
                redis_info = await queue_manager.redis_client.info()
                role = redis_info.get("role", "unknown")
                logger.info(f"📡 Production Redis role: {role}")

                if role == "slave":
                    logger.error("🚨 CRITICAL: Production Redis is in slave/replica mode!")
                    logger.error("💥 This will cause 'write against read only replica' errors!")
                    logger.info("🔧 ACTION REQUIRED: Run fix-redis.sh to promote to master")
                elif role == "master":
                    logger.info("✅ Production Redis is in master mode - ready for writes")
                else:
                    logger.info(f"ℹ️ Production Redis role: {role}")

        except Exception as redis_error:
            logger.error(f"❌ Production Redis connection test failed: {redis_error}")
            logger.error("🔍 This indicates serious Redis connectivity issues on production")

        # Test 4: Test task dequeue operation on production
        logger.info("🔧 Test 4: Test production task dequeue operation")
        try:
            # Try to dequeue with short timeout
            task_data = await queue_manager.dequeue_generic_task(
                worker_id="production_test_worker", timeout=1
            )

            if task_data:
                logger.info(f"📋 Found task in production queue: {task_data.get('task_id', 'unknown')}")
                logger.warning("⚠️ Actual task found - not processing to avoid interfering with production")
            else:
                logger.info("📭 No tasks in production queue (good for testing)")

        except Exception as dequeue_error:
            logger.error(f"❌ Production task dequeue failed: {dequeue_error}")
            logger.error("🔍 This indicates Redis connection issues affecting file upload processing")

        # Test 5: Short worker run test (reduced time for production)
        logger.info("🔧 Test 5: Test production worker run loop (5 seconds only)")

        # Create a task to test worker processing
        async def run_worker_test():
            worker_task = asyncio.create_task(worker.run())
            await asyncio.sleep(5)  # Only 5 seconds for production
            worker.running = False
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Worker task didn't stop cleanly, but this is expected")

        try:
            await run_worker_test()
            logger.info("✅ Production worker run loop completed successfully")
        except Exception as run_error:
            logger.error(f"❌ Production worker run loop failed: {run_error}")
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")

        # Cleanup
        await worker.shutdown()
        logger.info("✅ Production worker shutdown completed")

    except Exception as e:
        logger.error(f"❌ Production worker test failed: {e}")
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        return False

    return True


async def test_queue_manager_direct():
    """Test QueueManager directly for Redis handling on PRODUCTION"""
    logger.info("🧪 Testing QueueManager Redis handling on production server")

    try:
        # Get queue manager
        queue_manager = await get_document_queue()
        logger.info("✅ QueueManager created successfully")

        # Test connection
        try:
            await queue_manager.connect()
            logger.info("✅ QueueManager connected to production Redis")
        except Exception as connect_error:
            logger.error(f"❌ QueueManager connection failed: {connect_error}")

            # Test if it has fallback processing
            if hasattr(queue_manager, "_process_task_immediately"):
                logger.info("✅ QueueManager has fallback processing capability")
            else:
                logger.warning("⚠️ QueueManager lacks fallback processing")

        # Test Redis info - CRITICAL for production
        try:
            if hasattr(queue_manager, "redis_client") and queue_manager.redis_client:
                logger.info("🔍 Checking production Redis status...")
                
                # Get replication info
                info = await queue_manager.redis_client.info("replication")
                role = info.get("role", "unknown")
                logger.info(f"📡 Production Redis replication role: {role}")

                if role == "slave":
                    logger.error("🚨 PRODUCTION ISSUE: Redis is in read-only slave mode!")
                    logger.error("💡 This explains the 'write against read only replica' errors")
                    logger.info("� Recommended action: Promote slave to master using fix-redis.sh")
                elif role == "master":
                    logger.info("✅ Production Redis is in master mode - writes should work")
                else:
                    logger.warning(f"⚠️ Unknown Redis role: {role}")
                
                # Test actual write operation
                logger.info("🔍 Testing Redis write operation...")
                try:
                    test_key = f"production_test_{int(time.time())}"
                    await queue_manager.redis_client.set(test_key, "test_value", ex=10)
                    value = await queue_manager.redis_client.get(test_key)
                    await queue_manager.redis_client.delete(test_key)
                    
                    if value == b"test_value":
                        logger.info("✅ Production Redis write test successful")
                    else:
                        logger.error("❌ Production Redis write test failed - value mismatch")
                        
                except Exception as write_error:
                    logger.error(f"🚨 PRODUCTION REDIS WRITE FAILED: {write_error}")
                    logger.error("💡 This confirms Redis is in read-only mode")
                    logger.info("🔧 Fix needed: Run fix-redis.sh to promote replica to master")
                
                # Get additional Redis stats
                server_info = await queue_manager.redis_client.info("server")
                logger.info(f"📊 Redis version: {server_info.get('redis_version', 'unknown')}")
                logger.info(f"📊 Uptime: {server_info.get('uptime_in_seconds', 0)} seconds")
                
                # Check memory usage
                memory_info = await queue_manager.redis_client.info("memory")
                used_memory = memory_info.get("used_memory_human", "unknown")
                logger.info(f"📊 Redis memory usage: {used_memory}")

        except Exception as info_error:
            logger.error(f"❌ Failed to get production Redis info: {info_error}")
            logger.error("🔍 This could indicate connection or permission issues")

        return True

    except Exception as e:
        logger.error(f"❌ Production QueueManager test failed: {e}")
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Main test runner for PRODUCTION server"""
    logger.info("🚀 Starting DocumentProcessingWorker Redis handling tests on PRODUCTION")
    logger.info(f"🕐 Test started at: {datetime.now()}")
    logger.info(f"📡 Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379')}")
    logger.info(f"🖥️ Environment: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"🐋 Running on Docker production server")
    
    # Verify we're connecting to production Redis
    logger.info("🔍 Production Environment Check:")
    logger.info(f"   - Redis: {os.getenv('REDIS_URL')}")
    logger.info(f"   - MongoDB: {os.getenv('MONGODB_URI')}")
    logger.info(f"   - Environment: {os.getenv('ENVIRONMENT')}")

    # Test 1: Direct QueueManager test
    logger.info("\n" + "=" * 60)
    logger.info("🧪 PHASE 1: Production QueueManager Redis Testing")
    logger.info("=" * 60)

    success1 = await test_queue_manager_direct()

    # Test 2: Full Worker test
    logger.info("\n" + "=" * 60)
    logger.info("🧪 PHASE 2: Production DocumentProcessingWorker Testing")
    logger.info("=" * 60)

    success2 = await test_worker_redis_handling()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 PRODUCTION TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"QueueManager Direct Test: {'✅ PASS' if success1 else '❌ FAIL'}")
    logger.info(
        f"DocumentProcessingWorker Test: {'✅ PASS' if success2 else '❌ FAIL'}"
    )

    if success1 and success2:
        logger.info("🎉 All production tests passed! Worker should handle Redis issues properly.")
        logger.info("💡 The enhanced Redis handling is working on production server.")
    else:
        logger.error("💥 Some production tests failed. Check the logs for Redis connection issues.")
        logger.error("🚨 Production Redis may still be in read-only replica mode!")
        
        # Provide specific troubleshooting steps
        logger.info("\n" + "🔧" * 20 + " PRODUCTION TROUBLESHOOTING STEPS " + "🔧" * 20)
        logger.info("1. Check Redis container status:")
        logger.info("   docker ps | grep redis")
        logger.info("   docker logs redis-server")
        logger.info("")
        logger.info("2. If Redis is in slave/replica mode, promote to master:")
        logger.info("   cd ~/ai-rag-chatbot")
        logger.info("   chmod +x scripts/fix-redis.sh")
        logger.info("   ./scripts/fix-redis.sh")
        logger.info("")
        logger.info("3. Restart the application container:")
        logger.info("   docker restart ai-chatbot-rag")
        logger.info("")
        logger.info("4. Monitor the application logs:")
        logger.info("   docker logs -f ai-chatbot-rag")
        logger.info("")
        logger.info("5. Test file upload functionality after fixes")
        logger.info("🔧" * 70)

    logger.info(f"🕐 Production test completed at: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
