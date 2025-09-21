#!/usr/bin/env python3
"""
Queue Management CLI Tool

This tool provides commands to manage and monitor the document ingestion queue.

Usage:
    python queue_cli.py stats                    # Show queue statistics
    python queue_cli.py status TASK_ID          # Show task status
    python queue_cli.py retry TASK_ID           # Retry a failed task
    python queue_cli.py cleanup [--hours HOURS] # Clean up old tasks
    python queue_cli.py flush                    # Clear all queues (dangerous!)

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379)
"""

import os
import sys
import argparse
import asyncio
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.queue.queue_manager import QueueManager

async def show_stats(queue_manager: QueueManager):
    """Show queue statistics"""
    stats = await queue_manager.get_queue_stats()
    
    print("📊 Queue Statistics:")
    print("=" * 50)
    print(f"Pending Tasks:     {stats.get('pending_tasks', 0)}")
    print(f"Processing Tasks:  {stats.get('processing_tasks', 0)}")
    print(f"Dead Letter Tasks: {stats.get('dead_letter_tasks', 0)}")
    print()
    print(f"Total Queued:      {stats.get('total_queued', 0)}")
    print(f"Total Completed:   {stats.get('total_completed', 0)}")
    print(f"Total Failed:      {stats.get('total_failed', 0)}")
    print(f"Total Retried:     {stats.get('total_retried', 0)}")

async def show_task_status(queue_manager: QueueManager, task_id: str):
    """Show status of a specific task"""
    status = await queue_manager.get_task_status(task_id)
    
    if not status:
        print(f"❌ Task {task_id} not found")
        return
    
    print(f"📋 Task Status: {task_id}")
    print("=" * 50)
    print(f"Status:       {status.status}")
    print(f"User ID:      {status.user_id}")
    print(f"Document ID:  {status.document_id}")
    print(f"Created:      {status.created_at}")
    
    if status.started_at:
        print(f"Started:      {status.started_at}")
    if status.completed_at:
        print(f"Completed:    {status.completed_at}")
    if status.worker_id:
        print(f"Worker ID:    {status.worker_id}")
    if status.retry_count > 0:
        print(f"Retries:      {status.retry_count}")
    if status.error_message:
        print(f"Error:        {status.error_message}")

async def retry_task(queue_manager: QueueManager, task_id: str):
    """Retry a failed task"""
    success = await queue_manager.retry_task(task_id)
    
    if success:
        print(f"✅ Task {task_id} has been re-queued for processing")
    else:
        print(f"❌ Failed to retry task {task_id}")

async def cleanup_tasks(queue_manager: QueueManager, hours: int):
    """Clean up old task status records"""
    await queue_manager.cleanup_old_tasks(hours)
    print(f"✅ Cleaned up task status records older than {hours} hours")

async def flush_queues(queue_manager: QueueManager):
    """Clear all queues (dangerous!)"""
    print("⚠️  WARNING: This will delete ALL tasks and status records!")
    response = input("Type 'yes' to confirm: ")
    
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    await queue_manager.connect()
    
    # Clear all Redis keys related to the queue
    keys_to_delete = []
    
    # Scan for all queue-related keys
    patterns = [
        f"queue:{queue_manager.queue_name}*",
        f"status:{queue_manager.queue_name}*",
        f"processing:{queue_manager.queue_name}*",
        f"dead_letter:{queue_manager.queue_name}*",
        f"stats:{queue_manager.queue_name}*"
    ]
    
    for pattern in patterns:
        async for key in queue_manager.redis_client.scan_iter(match=pattern):
            keys_to_delete.append(key)
    
    if keys_to_delete:
        await queue_manager.redis_client.delete(*keys_to_delete)
        print(f"🗑️  Deleted {len(keys_to_delete)} queue-related keys")
    else:
        print("📭 No queue data found to delete")

def main():
    parser = argparse.ArgumentParser(description='Queue Management CLI')
    parser.add_argument('command', choices=['stats', 'status', 'retry', 'cleanup', 'flush'])
    parser.add_argument('task_id', nargs='?', help='Task ID (for status/retry commands)')
    parser.add_argument('--hours', type=int, default=72, help='Hours for cleanup command')
    parser.add_argument('--redis-url', help='Redis connection URL')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.command in ['status', 'retry'] and not args.task_id:
        print(f"❌ Task ID required for {args.command} command")
        sys.exit(1)
    
    # Create queue manager
    redis_url = args.redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
    queue_manager = QueueManager(redis_url=redis_url)
    
    # Execute command
    try:
        if args.command == 'stats':
            asyncio.run(show_stats(queue_manager))
        elif args.command == 'status':
            asyncio.run(show_task_status(queue_manager, args.task_id))
        elif args.command == 'retry':
            asyncio.run(retry_task(queue_manager, args.task_id))
        elif args.command == 'cleanup':
            asyncio.run(cleanup_tasks(queue_manager, args.hours))
        elif args.command == 'flush':
            asyncio.run(flush_queues(queue_manager))
    
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        try:
            asyncio.run(queue_manager.disconnect())
        except:
            pass

if __name__ == "__main__":
    main()
