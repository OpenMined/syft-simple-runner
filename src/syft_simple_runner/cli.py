#!/usr/bin/env python3
"""
Command line interface for Syft Simple Runner.
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from . import __version__
from .app import RunnerApp


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Syft Simple Runner - Secure code execution for Syft Code Queue"
    )
    
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"syft-simple-runner {__version__}"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command (default SyftBox mode)
    run_parser = subparsers.add_parser(
        "run", 
        help="Run the job processor once (SyftBox integration mode)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    
    # Execute commands
    if args.command == "run":
        run_app()
    else:
        # Default to run mode for SyftBox compatibility
        run_app()


def run_app():
    """Run the SyftBox app mode."""
    try:
        logger.info("Starting Syft Simple Runner...")
        app = RunnerApp()
        app.run()
        logger.info("Syft Simple Runner completed successfully")
    except Exception as e:
        logger.error(f"Runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
