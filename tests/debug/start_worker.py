#!/usr/bin/env python3
"""
Document Ingestion Worker Startup Script

This script starts the document ingestion worker that processes tasks from the Redis queue.
Multiple workers can be started for load balancing.

Usage:
    python start_worker.py [--worker-id WORKER_ID] [--redis-url REDIS_URL]

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379)
    WORKER_ID: Unique worker identifier (auto-generated if not provided)
"""

import os
import sys
import argparse
import asyncio
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.workers.ingestion_worker import DocumentIngestionWorker

def main():
    parser = argparse.ArgumentParser(description='Start Document Ingestion Worker')
    parser.add_argument('--worker-id', help='Unique worker identifier')
    parser.add_argument('--redis-url', help='Redis connection URL')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create worker
    worker = DocumentIngestionWorker(
        worker_id=args.worker_id,
        redis_url=args.redis_url
    )
    
    # Run worker
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
