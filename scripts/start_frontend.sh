#!/bin/bash
# Install dependencies if needed
pip install -r requirements.txt

# Start the Streamlit dashboard
# Use $PORT provided by Render, default to 8501
PORT=${PORT:-8501}
streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0
