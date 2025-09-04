#!/bin/bash

# Exit immediately on error
set -e

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Start uvicorn app
echo "Starting FastAPI app on http://127.0.0.1:8000 ..."
uvicorn main:app --reload --port 8000
