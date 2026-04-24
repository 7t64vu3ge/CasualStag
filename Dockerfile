FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Set environment variables
ENV FINANCIAL_AGENT_HOST=0.0.0.0
ENV FINANCIAL_AGENT_PORT=8000

# Run the application
CMD ["uvicorn", "financial_agent.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
