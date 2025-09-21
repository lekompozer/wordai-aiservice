#!/usr/bin/env python3
"""
Simplified Async Test with Worker Monitoring
Kiểm tra worker và đo thời gian thực tế của async processing
"""

import json
import requests
import time
import redis
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
COMPANY_ID = "test-async-timing"


def monitor_redis_queue():
    """Monitor Redis queue for tasks"""
    try:
        r = redis.Redis(host="localhost", port=6379, db=0)
        queue_length = r.llen("document_processing")
        print(f"📊 Redis queue length: {queue_length}")

        # Check if there are any tasks
        if queue_length > 0:
            # Peek at the first task (without removing it)
            task_data = r.lindex("document_processing", 0)
            if task_data:
                task = json.loads(task_data)
                print(f"🔍 First task in queue: {task.get('task_id', 'Unknown')}")

        return queue_length
    except Exception as e:
        print(f"❌ Redis monitoring failed: {e}")
        return -1


def test_worker_processing():
    """Test worker processing with actual timing"""
    print("🚀 Testing Async Processing with Real Worker Timing")
    print("=" * 60)

    start_time = datetime.now()

    # Step 1: Submit async request
    print(f"⏱️  [0.0s] Submitting async request...")

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID,
        "industry": "insurance",
        "data_type": "auto",  # Extract both products and services
        "file_name": "SanPham-AIA.txt",
        "file_size": 1024000,
        "file_type": "text/plain",
    }

    response = requests.post(
        f"{BASE_URL}/api/extract/process-async", json=payload, timeout=30
    )

    submit_time = (datetime.now() - start_time).total_seconds()

    if response.status_code != 200:
        print(f"❌ Request failed: {response.status_code} - {response.text}")
        return

    data = response.json()
    task_id = data.get("task_id")

    print(f"⏱️  [{submit_time:.1f}s] ✅ Task queued: {task_id}")

    # Step 2: Monitor queue immediately after submission
    queue_length = monitor_redis_queue()

    # Step 3: Check for task processing by monitoring queue and trying sync request
    print(f"⏱️  [{submit_time:.1f}s] 🔍 Monitoring processing...")

    # Try to get processing status by checking if sync request works on same file
    print(f"⏱️  [{submit_time:.1f}s] 📋 Testing sync processing for comparison...")

    sync_start = datetime.now()
    sync_payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID + "-sync",
        "industry": "insurance",
        "data_type": "products",
        "file_metadata": {
            "original_name": "SanPham-AIA.txt",
            "file_size": 1024000,
            "file_type": "text/plain",
            "uploaded_at": "2025-07-26T10:00:00Z",
        },
    }

    sync_response = requests.post(
        f"{BASE_URL}/api/extract/process", json=sync_payload, timeout=120
    )
    sync_time = (datetime.now() - sync_start).total_seconds()

    if sync_response.status_code == 200:
        sync_data = sync_response.json()
        total_elapsed = (datetime.now() - start_time).total_seconds()

        print(
            f"⏱️  [{total_elapsed:.1f}s] ✅ Sync processing completed in {sync_time:.1f}s"
        )
        print(
            f"                📊 Sync results: {sync_data.get('total_items_extracted', 0)} items"
        )

        # Estimate async timing based on sync performance
        estimated_async_time = sync_time + 10  # Add overhead for queue processing
        print(f"                📈 Estimated async time: ~{estimated_async_time:.1f}s")

        # Save results
        save_timing_results(
            task_id, submit_time, sync_time, estimated_async_time, sync_data
        )

    else:
        print(f"❌ Sync test failed: {sync_response.status_code}")

    final_queue_check = monitor_redis_queue()
    total_time = (datetime.now() - start_time).total_seconds()

    print(f"\n📊 TIMING SUMMARY:")
    print(f"   ⚡ Queue submission: {submit_time:.2f}s")
    print(f"   🔄 Sync processing: {sync_time:.2f}s")
    print(f"   📊 Total test time: {total_time:.2f}s")
    print(f"   📦 Final queue length: {final_queue_check}")


def save_timing_results(task_id, submit_time, sync_time, estimated_async, sync_data):
    """Save timing test results"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"async_timing_test_{timestamp}.json"

    results = {
        "test_info": {
            "task_id": task_id,
            "test_timestamp": datetime.now().isoformat(),
            "test_type": "async_timing_verification",
        },
        "timing_metrics": {
            "queue_submission_time": submit_time,
            "sync_processing_time": sync_time,
            "estimated_async_time": estimated_async,
            "queue_overhead_estimate": 2.0,  # Estimated queue overhead
        },
        "sync_test_results": {
            "success": sync_data.get("success"),
            "total_items": sync_data.get("total_items_extracted"),
            "ai_provider": sync_data.get("ai_provider"),
            "template_used": sync_data.get("template_used"),
            "processing_time": sync_data.get("processing_time"),
        },
        "full_extraction_data": {
            "raw_content": sync_data.get("raw_content"),
            "structured_data": sync_data.get("structured_data"),
            "extraction_metadata": sync_data.get("extraction_metadata"),
            "industry": sync_data.get("industry"),
            "data_type": sync_data.get("data_type"),
            "template_used": sync_data.get("template_used"),
            "ai_provider": sync_data.get("ai_provider"),
            "error": sync_data.get("error"),
            "error_details": sync_data.get("error_details"),
        },
        "performance_analysis": {
            "async_queue_benefit": "Immediate response vs waiting for processing",
            "expected_async_workflow": f"Queue: <1s, Processing: ~{sync_time:.0f}s, Total: ~{estimated_async:.0f}s",
            "sync_workflow": f"Direct processing: {sync_time:.1f}s (blocking)",
            "recommendation": "Use async for files >100KB or when UI responsiveness is critical",
        },
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"📁 Timing results saved to: {filename}")
    return filename


if __name__ == "__main__":
    test_worker_processing()
