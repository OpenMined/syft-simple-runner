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

from syft_queue import JobStatus, Job, Queue, q, list_queues, get_queue, start, complete, fail, timeout

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
    """Simple app that polls for and executes code jobs across all queues."""
    
    def __init__(self):
        """Initialize the app."""
        try:
            self.syftbox_client = SyftBoxClient.load()
            self.email = self.syftbox_client.email
            logger.info(f"Initialized Simple Runner App for {self.email}")
        except Exception as e:
            logger.warning(f"Could not initialize Simple Runner: {e}")
            # Set up in demo mode
            self.syftbox_client = SyftBoxClient()
            self.email = self.syftbox_client.email
    
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
        """Process one polling cycle across all queues."""
        # Get all queue names
        queue_names = list_queues()
        
        if not queue_names:
            return
        
        # Process each queue
        for queue_name in queue_names:
            try:
                queue = get_queue(queue_name)
                if not queue:
                    continue
                    
                # Check for timed out jobs
                self._check_timeouts_for_queue(queue)
                
                # Log pending jobs
                self._log_pending_jobs_for_queue(queue)

                # Execute approved jobs
                self._execute_approved_jobs_for_queue(queue)
            except Exception as e:
                logger.error(f"Error processing queue {queue_name}: {e}")
                continue
    
    def _check_timeouts_for_queue(self, queue):
        """Check for jobs that have timed out in a specific queue."""
        current_time = datetime.now()
        
        # Check inbox jobs for approval timeout
        inbox_jobs = queue.list_jobs(status=JobStatus.inbox)
        for job in inbox_jobs:
            if job.created_at and job.timeout_seconds:
                elapsed = (current_time - job.created_at).total_seconds()
                if elapsed > job.timeout_seconds:
                    logger.warning(f"Job {job.name} ({job.uid}) in queue {queue.queue_name} has timed out waiting for approval after {elapsed:.0f} seconds")
                    timeout(job)
        
        # Check running jobs for execution timeout
        running_jobs = queue.list_jobs(status=JobStatus.running)
        for job in running_jobs:
            if job.started_at and job.timeout_seconds:
                elapsed = (current_time - job.started_at).total_seconds()
                if elapsed > job.timeout_seconds:
                    logger.warning(f"Running job {job.name} ({job.uid}) in queue {queue.queue_name} has exceeded timeout of {job.timeout_seconds} seconds")
                    timeout(job)
    
    def _log_pending_jobs_for_queue(self, queue):
        """Log information about pending jobs in a specific queue."""
        # Get all pending jobs and filter by target email
        all_pending_jobs = queue.list_jobs(status=JobStatus.inbox)
        pending_jobs = [job for job in all_pending_jobs if job.target_email == self.email]
        
        if pending_jobs:
            logger.info(f"📋 Queue '{queue.queue_name}': {len(pending_jobs)} job(s) pending approval:")
            for job in pending_jobs:
                logger.info(f"   • {job.name} from {job.requester_email}")
        # Don't log when no jobs - too verbose for continuous polling
    
    def _execute_approved_jobs_for_queue(self, queue):
        """Execute all approved jobs in a specific queue."""
        # Get approved jobs
        approved_jobs = queue.list_jobs(status=JobStatus.approved)
        
        if not approved_jobs:
            # Don't log when no jobs - too verbose for continuous polling
            return
        
        logger.info(f"🚀 Queue '{queue.queue_name}': Executing {len(approved_jobs)} approved job(s)")
        
        for job in approved_jobs:
            self._execute_single_job(job, queue)
    
    def _execute_single_job(self, job: Job, queue):
        """Execute a single job."""
        logger.info(f"Starting execution of job: {job.name} in queue: {queue.queue_name}")
        
        try:
            # Start the job (move from approved to running)
            start(job, runner="syft-simple-runner")
            
            # Get the job directory
            job_dir = job.object_path
            
            # Find the run.sh script
            queue_type = getattr(queue, 'queue_type', 'code')
            run_script = self._find_run_script(job_dir, queue_type)
            
            if not run_script:
                logger.error(f"No run.sh found in job {job.name}")
                fail(job, error="No run.sh script found")
                return

            # Validate script
            if not self._validate_script(run_script):
                fail(job, error="Script contains potentially dangerous commands")
                return

            # Create output directory
            output_dir = job_dir / "output"
            output_dir.mkdir(exist_ok=True)

            # Execute the script
            code_dir = run_script.parent
            success, logs = run_job(job, code_dir, output_dir)
            
            # Update job status based on execution result
            if success:
                complete(job, output_path=str(output_dir))
                logger.info(f"✅ Job {job.name} completed successfully")
            else:
                fail(job, error="Execution failed", exit_code=1)
                logger.error(f"❌ Job {job.name} failed")
            
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")
            fail(job, error=str(e))
    
    def _find_run_script(self, job_dir: Path, queue_type: str) -> Optional[Path]:
        """Find the run.sh script in a job directory."""
        # For code queues, it's typically in the code subdirectory
        if queue_type == "code":
            code_run = job_dir / "code" / "run.sh"
            if code_run.exists():
                return code_run
        
        # Check root directory
        root_run = job_dir / "run.sh"
        if root_run.exists():
            return root_run
            
        # Search for any run.sh in the job directory
        for run_script in job_dir.rglob("run.sh"):
            return run_script
            
        return None
    
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