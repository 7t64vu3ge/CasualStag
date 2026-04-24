ARG TARGET_SERVICE=backend

# Use a single base for both services to optimize build time
FROM python:3.11-slim as base

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# --- Backend Stage ---
FROM base as backend
EXPOSE 8000
CMD ["uvicorn", "financial_agent.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Frontend Stage ---
FROM base as frontend
EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]

# --- Final Target (determined by build-arg) ---
# Default to backend if no arg is provided
FROM ${TARGET_SERVICE:-backend}
