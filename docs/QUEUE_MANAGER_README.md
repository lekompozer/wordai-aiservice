# Queue Manager Integration - Complete Implementation

This document describes the complete Queue Manager integration for asynchronous document ingestion using Redis as the message broker.

## Overview

The Queue Manager provides a robust, scalable solution for processing document ingestion tasks asynchronously. It replaces the previous FastAPI BackgroundTasks approach with a Redis-based queue system that supports:

- ✅ **Task Queuing**: Reliable task scheduling with priority support
- ✅ **Status Tracking**: Real-time task status monitoring
- ✅ **Worker Processing**: Scalable worker-based task processing
- ✅ **Error Handling**: Retry logic and dead-letter queue for failed tasks
- ✅ **Monitoring**: Queue statistics and management tools

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Redis Queue   │    │   Worker Pool   │
│                 │    │                 │    │                 │
│  POST /process  │───▶│  Task Queue     │◄───│  Worker 1       │
│  GET /status    │    │  Status Store   │    │  Worker 2       │
│  GET /stats     │    │  Dead Letter    │    │  Worker N       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 1. QueueManager (`src/queue/queue_manager.py`)

Core component that manages the Redis-based task queue:

```python
from src.queue.queue_manager import QueueManager, IngestionTask

# Initialize queue manager
queue = QueueManager(redis_url="redis://localhost:6379")
await queue.connect()

# Enqueue a task
task = IngestionTask(
    task_id="unique_task_id",
    user_id="user123",
    document_id="doc456",
    file_path="documents/file.pdf",
    filename="file.pdf",
    file_type="application/pdf",
    file_size=1024000
)

success = await queue.enqueue_task(task)
```

#### Key Features:
- **Priority Queuing**: Tasks with priority >= 3 go to front of queue
- **Status Tracking**: Automatic status updates (pending → processing → completed/failed)
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Dead Letter Queue**: Failed tasks after max retries
- **Statistics**: Comprehensive queue metrics

### 2. Document Processing API (`src/api/document_processing_routes.py`)

Refactored API endpoints that use the Queue Manager:

#### Main Endpoints:

- **POST /api/documents/process** - Queue document for processing
- **GET /api/documents/task/{task_id}/status** - Get task status
- **GET /api/documents/queue/stats** - Get queue statistics
- **POST /api/documents/task/{task_id}/retry** - Retry failed task

#### Example Usage:

```python
# Queue a document for processing
response = await client.post("/api/documents/process", json={
    "document_id": "doc123",
    "user_id": "user456",
    "file_name": "document.pdf",
    "r2_key": "uploads/document.pdf",
    "content_type": "application/pdf",
    "file_size": 1024000,
    "callback_url": "http://backend.com/webhook"
})

# Response: {"task_id": "task_789", "status": "queued", ...}
```

### 3. Ingestion Worker (`src/workers/ingestion_worker.py`)

Worker processes that consume tasks from the queue:

```python
from src.workers.ingestion_worker import DocumentIngestionWorker

# Create and start worker
worker = DocumentIngestionWorker(worker_id="worker_1")
await worker.initialize()
await worker.run()  # Runs continuously
```

#### Worker Features:
- **Continuous Processing**: Polls queue for new tasks
- **Error Handling**: Graceful error recovery and reporting
- **Backoff Strategy**: Intelligent waiting when queue is empty
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM

### 4. Management Tools

#### Worker Startup Script (`start_worker.py`)

```bash
# Start a worker
python start_worker.py

# Start with custom settings
python start_worker.py --worker-id worker_001 --redis-url redis://localhost:6379
```

#### Queue Management CLI (`queue_cli.py`)

```bash
# Show queue statistics
python queue_cli.py stats

# Check task status
python queue_cli.py status task_123

# Retry failed task
python queue_cli.py retry task_123

# Clean up old tasks
python queue_cli.py cleanup --hours 48

# Flush all queues (dangerous!)
python queue_cli.py flush
```

## Setup and Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Redis Server

Using Docker:
```bash
docker-compose -f docker-compose.redis.yml up -d
```

Or install Redis locally:
```bash
# macOS
brew install redis
redis-server

# Ubuntu
sudo apt-get install redis-server
sudo systemctl start redis
```

### 3. Configure Environment

```bash
# .env file
REDIS_URL=redis://localhost:6379
QUEUE_NAME=document_ingestion
TASK_STATUS_EXPIRY_HOURS=24
MAX_QUEUE_SIZE=10000
```

### 4. Start the Application

```bash
# Start FastAPI app
uvicorn src.main:app --reload

# Start worker (in separate terminal)
python start_worker.py
```

## Testing

### Comprehensive Test Suite

Run the integration tests:

```bash
python test_queue_integration.py
```

This tests:
- ✅ Basic queue operations (enqueue, dequeue, status)
- ✅ Document processing with real files
- ✅ Error handling and retry logic
- ✅ Queue statistics

### Manual Testing

1. **Queue a document:**
```bash
curl -X POST "http://localhost:8000/api/documents/process" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "test_doc",
    "user_id": "test_user",
    "file_name": "test.txt",
    "r2_key": "test-documents/test.txt",
    "content_type": "text/plain",
    "callback_url": "http://localhost:3000/callback"
  }'
```

2. **Check task status:**
```bash
curl "http://localhost:8000/api/documents/task/{task_id}/status"
```

3. **Monitor queue:**
```bash
curl "http://localhost:8000/api/documents/queue/stats"
```

## Monitoring and Management

### Redis Commander UI

Access the Redis UI at http://localhost:8081 to:
- View queue contents
- Monitor Redis memory usage
- Debug task data

### Queue Statistics

Monitor these key metrics:
- `pending_tasks`: Tasks waiting to be processed
- `processing_tasks`: Tasks currently being processed
- `total_completed`: Successfully processed tasks
- `total_failed`: Failed tasks
- `dead_letter_tasks`: Tasks that exhausted retries

### Logging

The system provides comprehensive logging:

```python
# Worker logs
🚀 Worker worker_001: Processing task task_123
📥 Worker worker_001: Downloading from R2...
✅ Worker worker_001: Downloaded 1024 bytes
🔍 Worker worker_001: Extracting text content...
...
✅ Worker worker_001: Task completed successfully
```

## Production Considerations

### Scaling

- **Multiple Workers**: Start multiple worker processes for parallel processing
- **Worker Pools**: Use process managers like Supervisor or systemd
- **Redis Cluster**: Scale Redis for high availability

### Monitoring

- **Health Checks**: Monitor worker health and restart if needed
- **Metrics**: Export queue metrics to monitoring systems
- **Alerting**: Alert on queue backup or worker failures

### Security

- **Redis Auth**: Enable Redis authentication in production
- **Network Security**: Restrict Redis access to application servers
- **Data Encryption**: Consider Redis encryption for sensitive data

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Solution: Check Redis server status and connection URL
   ```

2. **Tasks Stuck in Processing**
   ```
   Solution: Check worker logs, restart workers if needed
   ```

3. **High Memory Usage**
   ```
   Solution: Run cleanup command or adjust task retention
   ```

### Debug Commands

```bash
# Check Redis connection
redis-cli ping

# View queue contents
redis-cli llen queue:document_ingestion

# Monitor Redis in real-time
redis-cli monitor

# Check worker logs
tail -f logs/worker.log
```

## Migration from BackgroundTasks

The migration from FastAPI BackgroundTasks to Queue Manager is complete:

### Before (Phase 1):
```python
@router.post("/process")
async def process_document(request, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_document_background, request)
    return {"status": "processing_started"}
```

### After (Phase 2):
```python
@router.post("/process")
async def process_document(request, queue: QueueManager = Depends(get_queue_manager)):
    task = IngestionTask(...)
    success = await queue.enqueue_task(task)
    return {"status": "queued", "task_id": task.task_id}
```

## Benefits

1. **Reliability**: Tasks survive server restarts
2. **Scalability**: Multiple workers can process tasks in parallel
3. **Monitoring**: Real-time visibility into queue status
4. **Error Handling**: Robust retry and dead-letter queue logic
5. **Flexibility**: Easy to add new task types and processing logic

## Conclusion

The Queue Manager integration provides a production-ready solution for asynchronous document processing. It replaces the previous BackgroundTasks approach with a robust, scalable, and monitorable system that can handle high-volume document ingestion workloads.

The system is fully tested and ready for production deployment with proper monitoring and scaling capabilities.
