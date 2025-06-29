#!/usr/bin/env python3
"""
Syft Simple Runner App - SyftBox Integration

This module runs as a SyftBox app, continuously polling for approved code execution jobs.
"""

import time
from pathlib import Path
from loguru import logger
from datetime import datetime
import signal
import sys

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

from .models import JobStatus, QueueConfig, SimpleJob
from .runner import SafeCodeRunner


class RunnerApp:
    """
    SyftBox app for processing code execution queue.
    
    This runs continuously, polling for approved jobs and executing them safely.
    """
    
    def __init__(self):
        self.syftbox_client = SyftBoxClient.load()
        self.queue_config = QueueConfig(self._get_queue_dir())
        self.runner = SafeCodeRunner()
        self.max_concurrent_jobs = 3
        self._running = False
        
        logger.info(f"Initialized Simple Runner App for {self.syftbox_client.email}")
    
    @property
    def email(self) -> str:
        """Get current user's email."""
        return self.syftbox_client.email
    
    def run(self):
        """
        Main app entry point - continuously polls for jobs every second.
        """
        logger.info("🔄 Starting continuous job polling (every 1 second)...")
        
        # Set up graceful shutdown
        self._running = True
        
        def signal_handler(signum, frame):
            logger.info("🛑 Received shutdown signal, stopping gracefully...")
            self._running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        cycle_count = 0
        
        try:
            while self._running:
                cycle_count += 1
                
                try:
                    # Log pending jobs every 10 cycles (10 seconds) to avoid spam
                    if cycle_count % 10 == 1:
                        self._log_pending_jobs()
                    
                    # Execute approved jobs every cycle
                    self._execute_approved_jobs()
                    
                    # Clean up old jobs every 60 cycles (1 minute)
                    if cycle_count % 60 == 0:
                        self._cleanup_old_jobs()
                
                except Exception as e:
                    logger.error(f"Error in processing cycle {cycle_count}: {e}")
                    # Continue running despite errors
                    
                # Sleep for 1 second before next poll
                if self._running:
                    time.sleep(1.0)
                    
        except KeyboardInterrupt:
            logger.info("🛑 Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error in polling loop: {e}")
            raise
        finally:
            logger.info(f"✅ Job polling stopped - processed {cycle_count} cycles")
    
    def _log_pending_jobs(self):
        """Log information about pending jobs waiting for approval."""
        pending_jobs = self._get_jobs_by_status(JobStatus.PENDING)
        
        # Only show jobs targeted at this datasite
        my_pending = [job for job in pending_jobs if job.target_email == self.email]
        
        if my_pending:
            logger.info(f"📋 {len(my_pending)} job(s) pending approval:")
            for job in my_pending:
                logger.info(f"   • {job.name} from {job.requester_email}")
        # Don't log when no jobs - too verbose for continuous polling
    
    def _execute_approved_jobs(self):
        """Execute jobs that have been manually approved."""
        approved_jobs = self._get_jobs_by_status(JobStatus.APPROVED)
        
        # Only process jobs targeted at this datasite
        my_approved = [job for job in approved_jobs if job.target_email == self.email]
        
        if not my_approved:
            # Don't log when no jobs - too verbose for continuous polling
            return
        
        # Check how many jobs are currently running
        running_jobs = self._get_jobs_by_status(JobStatus.RUNNING)
        my_running = [job for job in running_jobs if job.target_email == self.email]
        
        # Limit concurrent executions
        available_slots = self.max_concurrent_jobs - len(my_running)
        if available_slots <= 0:
            logger.info(f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached")
            return
        
        # Execute jobs up to the limit
        jobs_to_execute = my_approved[:available_slots]
        
        logger.info(f"🚀 Executing {len(jobs_to_execute)} approved job(s)")
        
        for job in jobs_to_execute:
            self._execute_single_job(job)
    
    def _execute_single_job(self, job: SimpleJob):
        """Execute a single job."""
        try:
            logger.info(f"Starting execution of job: {job.name}")
            
            # Update status to running
            job.status = JobStatus.RUNNING
            job_file = self.queue_config.get_job_file(job.uid)
            job.save_to_file(job_file)
            
            # Execute the job
            exit_code, stdout, stderr = self.runner.run_job(job)
            
            # Update job status and logs based on result
            job.exit_code = exit_code
            job.logs = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            job.completed_at = datetime.now().isoformat()
            
            if exit_code == 0:
                job.status = JobStatus.COMPLETED
                logger.info(f"Job {job.uid} completed successfully")
            else:
                job.status = JobStatus.FAILED
                logger.warning(f"Job {job.uid} failed with exit code {exit_code}")
            
        except Exception as e:
            error_msg = f"Job execution error: {e}"
            job.status = JobStatus.FAILED
            job.logs = error_msg
            job.completed_at = datetime.now().isoformat()
            logger.error(f"Job {job.uid} failed: {error_msg}")
        
        finally:
            # Always save the final job state
            job_file = self.queue_config.get_job_file(job.uid)
            job.save_to_file(job_file)
    
    def _cleanup_old_jobs(self):
        """Clean up old completed jobs (older than 24 hours)."""
        cutoff_time = datetime.now().timestamp() - (24 * 60 * 60)  # 24 hours ago
        
        queue_dir = self._get_queue_dir()
        if not queue_dir.exists():
            return
        
        cleaned_count = 0
        for job_file in queue_dir.glob("*.json"):
            try:
                job = SimpleJob.from_file(job_file)
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED] and job.completed_at:
                    completed_time = datetime.fromisoformat(job.completed_at).timestamp()
                    if completed_time < cutoff_time:
                        logger.debug(f"Cleaning up old job: {job.uid}")
                        job_file.unlink()
                        cleaned_count += 1
                        
            except Exception as e:
                logger.warning(f"Failed to cleanup job {job_file}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} old job(s)")
    
    def _get_jobs_by_status(self, status: JobStatus):
        """Get all jobs with a specific status."""
        jobs = []
        
        for job_id in self.queue_config.list_jobs():
            try:
                job_file = self.queue_config.get_job_file(job_id)
                job = SimpleJob.from_file(job_file)
                if job.status == status:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to load job {job_id}: {e}")
        
        return jobs
    
    def _get_queue_dir(self) -> Path:
        """Get the queue directory."""
        return self.syftbox_client.app_data("code-queue")


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
