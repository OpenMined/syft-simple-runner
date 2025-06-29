#!/usr/bin/env python3
"""
Syft Code Queue App - SyftBox Integration

This module runs as a SyftBox app, called periodically by SyftBox to process
the code execution queue. It checks for jobs and processes them, then exits.

This replaces the long-running server approach with a more SyftBox-native
periodic processing model.
"""

import time
from pathlib import Path
from loguru import logger

try:
    from syft_core import Client as SyftBoxClient
except ImportError:
    logger.warning("syft_core not available - running in standalone mode")
    # Fallback for development/testing
    class MockSyftBoxClient:
        def __init__(self):
            self.email = "demo@example.com"
        
        def app_data(self, app_name):
            import tempfile
            return Path(tempfile.gettempdir()) / f"syftbox_demo_{app_name}"
        
        @classmethod
        def load(cls):
            return cls()
    
    SyftBoxClient = MockSyftBoxClient

from syft_code_queue.models import JobStatus, QueueConfig
from .runner import SafeCodeRunner


class RunnerApp:
    """
    SyftBox app for processing code execution queue.
    
    This runs periodically (called by SyftBox) to process pending jobs,
    execute approved jobs, and clean up completed jobs.
    """
    
    def __init__(self):
        self.syftbox_client = SyftBoxClient.load()
        self.config = QueueConfig(queue_name="code-queue")
        self.runner = SafeCodeRunner()
        
        logger.info(f"Initialized Simple Runner App for {self.syftbox_client.email}")
    
    @property
    def email(self) -> str:
        """Get current user's email."""
        return self.syftbox_client.email
    
    def run(self):
        """
        Main app entry point - processes the queue once and exits.
        
        This method:
        1. Checks for pending jobs (for logging)
        2. Executes approved jobs
        3. Cleans up old completed jobs
        4. Exits
        """
        logger.info("Starting queue processing cycle...")
        
        try:
            # Log pending jobs (data owners need to manually approve these)
            self._log_pending_jobs()
            
            # Execute approved jobs
            self._execute_approved_jobs()
            
            # Clean up old jobs
            self._cleanup_old_jobs()
            
            logger.info("Queue processing cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in queue processing: {e}")
            raise
    
    def _log_pending_jobs(self):
        """Log information about pending jobs waiting for approval."""
        pending_jobs = self._get_jobs_by_status(JobStatus.pending)
        
        # Only show jobs targeted at this datasite
        my_pending = [job for job in pending_jobs if job.target_email == self.email]
        
        if my_pending:
            logger.info(f"📋 {len(my_pending)} job(s) pending approval:")
            for job in my_pending:
                logger.info(f"   • {job.name} from {job.requester_email}")
        else:
            logger.debug("No jobs pending approval")
    
    def _execute_approved_jobs(self):
        """Execute jobs that have been manually approved."""
        approved_jobs = self._get_jobs_by_status(JobStatus.approved)
        
        # Only process jobs targeted at this datasite
        my_approved = [job for job in approved_jobs if job.target_email == self.email]
        
        if not my_approved:
            logger.debug("No approved jobs to execute")
            return
        
        # Check how many jobs are currently running
        running_jobs = self._get_jobs_by_status(JobStatus.running)
        my_running = [job for job in running_jobs if job.target_email == self.email]
        
        # Limit concurrent executions
        available_slots = self.config.max_concurrent_jobs - len(my_running)
        if available_slots <= 0:
            logger.info(f"Maximum concurrent jobs ({self.config.max_concurrent_jobs}) reached")
            return
        
        # Execute jobs up to the limit
        jobs_to_execute = my_approved[:available_slots]
        
        logger.info(f"🚀 Executing {len(jobs_to_execute)} approved job(s)")
        
        for job in jobs_to_execute:
            self._execute_single_job(job)
    
    def _execute_single_job(self, job):
        """Execute a single job."""
        try:
            logger.info(f"Starting execution of job: {job.name}")
            
            # Update status to running
            job.update_status(JobStatus.running)
            self._save_job(job)
            
            # Execute the job
            exit_code, stdout, stderr = self.runner.run_job(job)
            
            # Update job status based on result
            if exit_code == 0:
                job.update_status(JobStatus.completed)
                logger.info(f"Job {job.uid} completed successfully")
            else:
                job.update_status(JobStatus.failed, f"Exit code: {exit_code}")
                logger.warning(f"Job {job.uid} failed with exit code {exit_code}")
            
        except Exception as e:
            error_msg = f"Job execution error: {e}"
            job.update_status(JobStatus.failed, error_msg)
            logger.error(f"Job {job.uid} failed: {error_msg}")
        
        finally:
            # Always save the final job state
            self._save_job(job)
    
    def _cleanup_old_jobs(self):
        """Clean up old completed jobs."""
        cutoff_time = time.time() - self.config.cleanup_completed_after
        
        queue_dir = self._get_queue_dir()
        if not queue_dir.exists():
            return
        
        cleaned_count = 0
        for job_file in queue_dir.glob("*.json"):
            try:
                job = self._load_job_from_file(job_file)
                if job and job.is_terminal and job.completed_at:
                    if job.completed_at.timestamp() < cutoff_time:
                        logger.debug(f"Cleaning up old job: {job.uid}")
                        job_file.unlink()
                        
                        # Also remove job directory
                        job_dir = self._get_job_dir(job)
                        if job_dir.exists():
                            import shutil
                            shutil.rmtree(job_dir)
                        
                        cleaned_count += 1
                        
            except Exception as e:
                logger.warning(f"Failed to cleanup job {job_file}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} old job(s)")
    
    def _get_jobs_by_status(self, status: JobStatus):
        """Get all jobs with a specific status."""
        jobs = []
        queue_dir = self._get_queue_dir()
        
        if not queue_dir.exists():
            return jobs
        
        for job_file in queue_dir.glob("*.json"):
            job = self._load_job_from_file(job_file)
            if job and job.status == status:
                jobs.append(job)
        
        return jobs
    
    def _load_job_from_file(self, job_file: Path):
        """Load a job from a JSON file."""
        try:
            if not job_file.exists():
                return None
            
            with open(job_file, 'r') as f:
                import json
                from uuid import UUID
                from datetime import datetime
                from syft_code_queue.models import CodeJob
                
                data = json.load(f)
                
                # Convert string representations back to proper types
                if 'uid' in data and isinstance(data['uid'], str):
                    data['uid'] = UUID(data['uid'])
                
                for date_field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
                    if date_field in data and data[date_field] and isinstance(data[date_field], str):
                        data[date_field] = datetime.fromisoformat(data[date_field])
                
                return CodeJob.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load job from {job_file}: {e}")
            return None
    
    def _save_job(self, job):
        """Save job to storage."""
        job_file = self._get_queue_dir() / f"{job.uid}.json"
        job_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(job_file, 'w') as f:
            import json
            from uuid import UUID
            from datetime import datetime
            from pathlib import Path
            
            def custom_serializer(obj):
                if isinstance(obj, Path):
                    return str(obj)
                elif isinstance(obj, UUID):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            json.dump(job.model_dump(), f, indent=2, default=custom_serializer)
    
    def _get_queue_dir(self) -> Path:
        """Get the queue directory."""
        return self.syftbox_client.app_data(self.config.queue_name) / "jobs"
    
    def _get_job_dir(self, job) -> Path:
        """Get directory for a specific job."""
        return self._get_queue_dir() / str(job.uid)


def main():
    """Main entry point for the SyftBox app."""
    try:
        app = RunnerApp()
        app.run()
    except Exception as e:
        logger.error(f"App failed: {e}")
        exit(1)


if __name__ == "__main__":
    main() 