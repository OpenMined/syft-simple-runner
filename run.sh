#!/bin/bash
set -e

# SyftBox app entry point for syft-simple-runner  
# This script starts the long-running job polling service

echo "🚀 Syft Simple Runner - Starting service..."

# Disable interactive prompts and shell customizations for non-interactive environments
export ZSH_DISABLE_COMPFIX=true
export NONINTERACTIVE=1

# Create virtual environment with uv (remove old one if exists)
echo "📦 Setting up virtual environment with uv..."
rm -rf .venv

# Use system Python 3.12 if available, otherwise use 3.11 or 3.10
PYTHON_VERSION="3.12"
if ! command -v python3.12 &> /dev/null; then
    if command -v python3.11 &> /dev/null; then
        PYTHON_VERSION="3.11"
    elif command -v python3.10 &> /dev/null; then
        PYTHON_VERSION="3.10"
    else
        echo "❌ No suitable Python version found (3.10, 3.11, or 3.12)"
        exit 1
    fi
fi

echo "🐍 Using Python $PYTHON_VERSION"
uv venv -p $PYTHON_VERSION

# Activate the virtual environment to ensure we use the correct Python
source .venv/bin/activate

# Install dependencies using the virtual environment's pip
echo "📦 Installing dependencies..."
python -m pip install --no-cache-dir -e .

# Run the queue processor (long-running service)
echo "🔄 Starting job polling service..."
python -m syft_simple_runner.app
