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
from time import sleep
from typing import Optional

from .syft_queue import Job, JobStatus, Queue, q

try:
    from syft_core import Client as SyftBoxClient
except ImportError:
    logger.warning("syft_core not available - using mock client")
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

from .runner import run_job


class SimpleRunnerApp:
    """Simple app that polls for and executes code jobs."""
    
    def __init__(self, queue_name: str = "code-queue"):
        """Initialize the app."""
        try:
            self.syftbox_client = SyftBoxClient.load()
            email = self.syftbox_client.email
            self.queue = q(queue_name, owner_email=email)

            logger.info(f"Initialized Simple Runner App for {email}")
        except Exception as e:
            logger.warning(f"Could not initialize Simple Runner: {e}")
            # Set up in demo mode
            self.syftbox_client = SyftBoxClient()
            email = self.syftbox_client.email
            self.queue = q(queue_name, owner_email=email)
    
    @property
    def email(self) -> str:
        """Get the current user's email."""
        return self.syftbox_client.email
    
    def run(self, poll_interval: int = 1):
        """
        Start continuous job polling and execution.

        Args:
            poll_interval: Seconds between polling cycles
        """
        logger.info(f"🔄 Starting continuous job polling (every {poll_interval} second)...")
        
        cycle = 0
        while True:
            try:
                # Process one cycle
                self._process_cycle()
                cycle += 1
                
                # Sleep until next cycle
                sleep(poll_interval)
            
            except KeyboardInterrupt:
                logger.info("👋 Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in processing cycle {cycle}: {e}")
                # Continue running despite errors
                sleep(poll_interval)
    
    def _process_cycle(self):
        """Process one polling cycle."""
        # Check for timed out jobs
        self._check_timeouts()
        
        # Log pending jobs
        self._log_pending_jobs()

        # Execute approved jobs
        self._execute_approved_jobs()
    
    def _check_timeouts(self):
        """Check for jobs that have timed out waiting for approval or running too long."""
        current_time = datetime.now()
        
        # Check inbox jobs for approval timeout
        inbox_jobs = self.queue.list_jobs(status=JobStatus.inbox)
        for job in inbox_jobs:
            if job.created_at and job.timeout_seconds:
                elapsed = (current_time - job.created_at).total_seconds()
                if elapsed > job.timeout_seconds:
                    logger.warning(f"Job {job.name} ({job.uid}) has timed out waiting for approval after {elapsed:.0f} seconds")
                    job.error_message = f"Timed out waiting for approval after {job.timeout_seconds} seconds"
                    self.queue.move_job(job, JobStatus.timedout)
        
        # Check running jobs for execution timeout
        running_jobs = self.queue.list_jobs(status=JobStatus.running)
        for job in running_jobs:
            if job.started_at and job.timeout_seconds:
                elapsed = (current_time - job.started_at).total_seconds()
                if elapsed > job.timeout_seconds:
                    logger.warning(f"Running job {job.name} ({job.uid}) has exceeded timeout of {job.timeout_seconds} seconds")
                    job.error_message = f"Execution timed out after {job.timeout_seconds} seconds"
                    self.queue.move_job(job, JobStatus.timedout)
    
    def _log_pending_jobs(self):
        """Log information about pending jobs."""
        # Get pending jobs for this user
        pending_jobs = self.queue.list_jobs(status=JobStatus.inbox, target_email=self.email)
        
        if pending_jobs:
            logger.info(f"📋 {len(pending_jobs)} job(s) pending approval:")
            for job in pending_jobs:
                logger.info(f"   • {job.name} from {job.requester_email}")
        # Don't log when no jobs - too verbose for continuous polling
    
    def _execute_approved_jobs(self):
        """Execute all approved jobs."""
        # Get approved jobs for this user
        approved_jobs = self.queue.list_jobs(status=JobStatus.approved, target_email=self.email)
        
        if not approved_jobs:
            # Don't log when no jobs - too verbose for continuous polling
            return
        
        logger.info(f"🚀 Executing {len(approved_jobs)} approved job(s)")
        
        for job in approved_jobs:
            self._execute_single_job(job)
    
    def _execute_single_job(self, job: Job):
        """Execute a single job."""
        logger.info(f"Starting execution of job: {job.name}")
        
        try:
            # Update status to running and move to running directory
            self.queue.move_job(job, JobStatus.running)
            
            # Get the job directory
            job_dir = job.object_path
            code_dir = job_dir / "code"
            run_script = code_dir / "run.sh"

            # Validate script
            if not self._validate_script(run_script):
                self.queue.move_job(job, JobStatus.rejected)
                job.error_message = "Script contains potentially dangerous commands"
                return

            # Create output directory
            output_dir = job_dir / "output"
            output_dir.mkdir(exist_ok=True)
            job.output_folder = output_dir

            # Execute the script
            success, logs = run_job(job, code_dir, output_dir)
            
            # Save logs
            job.logs = logs
            
            # Update job status and move to appropriate directory
            if success:
                self.queue.move_job(job, JobStatus.completed)
            else:
                job.error_message = "Execution failed"
                self.queue.move_job(job, JobStatus.failed)
            
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")
            job.error_message = str(e)
            job.logs = str(e)
            self.queue.move_job(job, JobStatus.failed)
    
    def _validate_script(self, script_path: Path) -> bool:
        """Validate that a script is safe to execute."""
        try:
            # Basic validation - check that script exists and is readable
            if not script_path.exists():
                logger.error(f"Script does not exist: {script_path}")
                return False

            # Read script content
            script_content = script_path.read_text()

            # Check for potentially dangerous commands
            dangerous_commands = [
                "rm -rf",
                "sudo",
                "> /dev/null",
                "2>&1",
                "wget",
                "curl",
                "nc",
                "netcat",
            ]
        
            for cmd in dangerous_commands:
                if cmd in script_content:
                    logger.warning(f"Script contains dangerous command: {cmd}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Failed to validate script: {e}")
            return False


def main():
    """Main entry point for the SyftBox app."""
    try:
        app = SimpleRunnerApp()
        app.run()
    except Exception as e:
        logger.error(f"App failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
