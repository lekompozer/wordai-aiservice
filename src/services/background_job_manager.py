"""
Background Job Manager - Track long-running AI processing tasks
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status states"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundJob:
    """Single background job"""

    def __init__(self, job_id: str, job_type: str, user_id: str, params: Dict):
        self.job_id = job_id
        self.job_type = job_type
        self.user_id = user_id
        self.params = params
        self.status = JobStatus.PENDING
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.task = None

    def to_dict(self) -> Dict:
        """Convert to dict for API response"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "elapsed_seconds": (
                (
                    (self.completed_at or datetime.now()) - self.created_at
                ).total_seconds()
                if self.created_at
                else 0
            ),
        }


class BackgroundJobManager:
    """Manage background jobs in memory"""

    def __init__(self):
        self.jobs: Dict[str, BackgroundJob] = {}
        logger.info("🔧 Background Job Manager initialized")

    def create_job(
        self, job_id: str, job_type: str, user_id: str, params: Dict
    ) -> BackgroundJob:
        """Create a new job"""
        job = BackgroundJob(job_id, job_type, user_id, params)
        self.jobs[job_id] = job
        logger.info(f"📋 Created job {job_id} (type: {job_type})")
        return job

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def update_progress(self, job_id: str, progress: int, status: JobStatus = None):
        """Update job progress"""
        job = self.jobs.get(job_id)
        if job:
            job.progress = progress
            if status:
                job.status = status
            logger.info(f"📊 Job {job_id}: {progress}% ({status or job.status})")

    def complete_job(self, job_id: str, result: Dict):
        """Mark job as completed"""
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.result = result
            job.completed_at = datetime.now()
            logger.info(
                f"✅ Job {job_id} completed in {job.to_dict()['elapsed_seconds']:.2f}s"
            )

    def fail_job(self, job_id: str, error: str):
        """Mark job as failed"""
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = error
            job.completed_at = datetime.now()
            logger.error(f"❌ Job {job_id} failed: {error}")

    async def run_job(self, job_id: str, task_func: Callable, *args, **kwargs):
        """Run a job in background"""
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()
            logger.info(f"🚀 Starting job {job_id}")

            # Run the actual task
            result = await task_func(*args, **kwargs)

            # Mark as completed
            self.complete_job(job_id, result)

        except Exception as e:
            logger.error(f"Error in job {job_id}: {str(e)}", exc_info=True)
            self.fail_job(job_id, str(e))

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        now = datetime.now()
        to_remove = []

        for job_id, job in self.jobs.items():
            if job.completed_at:
                age_hours = (now - job.completed_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(job_id)

        for job_id in to_remove:
            del self.jobs[job_id]
            logger.info(f"🗑️  Cleaned up old job {job_id}")


# Global singleton instance
_job_manager = None


def get_job_manager() -> BackgroundJobManager:
    """Get singleton instance"""
    global _job_manager
    if _job_manager is None:
        _job_manager = BackgroundJobManager()
    return _job_manager
