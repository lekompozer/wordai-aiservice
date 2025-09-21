#!/usr/bin/env python3
"""
Extended Async Monitor - Check if worker actually processes the task
"""

import json
import requests
import time
import redis
from datetime import datetime

BASE_URL = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"


def monitor_extended():
    """Monitor for 30 seconds to see if worker processes task"""
    print("🔍 EXTENDED ASYNC MONITORING (30s)")
    print("=" * 50)

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": "extended-test",
        "industry": "insurance",
        "data_type": "products",
        "file_name": "SanPham-AIA.txt",
        "file_size": 1024000,
        "file_type": "text/plain",
    }

    start_time = datetime.now()

    # Submit async request
    response = requests.post(
        f"{BASE_URL}/api/extract/process-async", json=payload, timeout=30
    )
    submit_time = (datetime.now() - start_time).total_seconds()

    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        return

    data = response.json()
    task_id = data.get("task_id")
    print(f"✅ [{submit_time:.2f}s] Task queued: {task_id}")

    # Monitor for 30 seconds
    r = redis.Redis(host="localhost", port=6379, db=0)

    for i in range(30):
        current_time = (datetime.now() - start_time).total_seconds()
        queue_length = r.llen("document_processing")

        print(f"[{current_time:.1f}s] Queue: {queue_length} items")

        # Try Qdrant search every 5 seconds
        if i % 5 == 0 and i > 0:
            try:
                search_payload = {
                    "company_id": "extended-test",
                    "query": "bảo hiểm",
                    "limit": 3,
                }
                search_response = requests.post(
                    f"{BASE_URL}/api/search", json=search_payload, timeout=5
                )

                if search_response.status_code == 200:
                    search_data = search_response.json()
                    results_count = len(search_data.get("results", []))
                    if results_count > 0:
                        print(
                            f"🎯 [{current_time:.1f}s] SUCCESS! Found {results_count} results in Qdrant"
                        )

                        total_processing_time = current_time - submit_time
                        print(f"📊 TIMING RESULTS:")
                        print(f"   ⚡ Queue submission: {submit_time:.2f}s")
                        print(f"   🔄 Processing time: {total_processing_time:.1f}s")
                        print(f"   📊 Total workflow: {current_time:.1f}s")

                        # Save successful timing
                        save_result(
                            task_id,
                            submit_time,
                            total_processing_time,
                            current_time,
                            results_count,
                        )
                        return
                    else:
                        print(f"⏳ [{current_time:.1f}s] Search works but no data yet")
                else:
                    print(
                        f"❌ [{current_time:.1f}s] Search failed: {search_response.status_code}"
                    )
            except Exception as e:
                print(f"⚠️  [{current_time:.1f}s] Search error: {e}")

        time.sleep(1)

    print("⏰ 30s timeout reached - worker may be slow or not processing")


def save_result(task_id, submit_time, processing_time, total_time, results_count):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"async_workflow_complete_{timestamp}.json"

    result = {
        "success": True,
        "task_id": task_id,
        "timing": {
            "queue_submission": submit_time,
            "processing_time": processing_time,
            "total_workflow": total_time,
        },
        "qdrant_results": results_count,
        "performance": f"Async: {submit_time:.2f}s response + {processing_time:.1f}s processing = {total_time:.1f}s total",
    }

    with open(filename, "w") as f:
        json.dump(result, f, indent=2)

    print(f"📁 Results saved: {filename}")


if __name__ == "__main__":
    monitor_extended()
