#!/bin/bash
# Install dependencies if needed
pip install -r requirements.txt

# Start the FastAPI server
# Use $PORT provided by Render, default to 8000
PORT=${PORT:-8000}
uvicorn financial_agent.api.routes:app --host 0.0.0.0 --port $PORT
