"""
Syft Simple Runner - Simple and secure code execution runner for Syft Code Queue

This package provides a lightweight, secure code execution engine that watches for 
approved jobs in the Syft Code Queue and executes them safely in controlled environments.

Key Components:
- CodeRunner: Basic code execution with timeout and output limits
- SafeCodeRunner: Enhanced security with command validation
- RunnerApp: SyftBox app integration for periodic job processing

Usage:
    # As a SyftBox app (run.sh calls this)
    python -m syft_simple_runner.app
    
    # Command line interface  
    syft-simple-runner --help
    
    # Programmatic usage
    from syft_simple_runner import SafeCodeRunner
    runner = SafeCodeRunner()
    exit_code, stdout, stderr = runner.run_job(job)

Architecture:
- Separation of concerns: syft-code-queue handles job management & approval workflows
- syft-simple-runner handles only job execution in secure sandboxes
- Both components communicate via shared SyftBox job queue data
"""

from .app import RunnerApp
from .runner import CodeRunner, SafeCodeRunner

__version__ = "0.1.0"

__all__ = [
    # Main execution engine
    "CodeRunner",
    "SafeCodeRunner", 
    
    # SyftBox app integration
    "RunnerApp",
    
    # Metadata
    "__version__",
]
