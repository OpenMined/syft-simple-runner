#!/bin/bash
set -e

# SyftBox app entry point for syft-simple-runner  
# This script is called periodically by SyftBox to process the code execution queue

echo "🚀 Syft Simple Runner - Processing jobs..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -e .

# Run the queue processor
echo "🔄 Processing queue..."
python -m syft_simple_runner.app

echo "✅ Queue processing complete." 