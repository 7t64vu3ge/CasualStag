# Deployment Guide: Financial Advisor Agent

This project is designed to be highly portable and can be deployed using Docker or a native Python environment.

## 1. Local Deployment (Recommended)
The easiest way to run the project is using **Docker Compose**. This will automatically build and link the FastAPI backend and the Streamlit frontend.

```bash
# Clone the repository
git clone <your-repo-url>
cd financial-agent

# Build and start the containers
docker-compose up --build
```

- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Frontend Dashboard**: [http://localhost:8501](http://localhost:8501)

---

## 2. Docker Deployment (Render / Railway)
I have configured a unified **Multi-Stage Dockerfile** for standard cloud deployments.

1. **Backend Service**:
   - **Environment**: Docker
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Target**: `backend`
2. **Frontend Service**:
   - **Environment**: Docker
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Target**: `frontend`
   - **Env Var**: `FINANCIAL_AGENT_API_URL` (Point to your Backend URL)

---

## 3. Native Python Deployment (Without Docker)
Use these steps if you are deploying to a platform like Render with a Python runtime.

### Backend Setup
1. **Runtime**: `Python 3`
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `sh scripts/start_backend.sh`

### Frontend Setup
1. **Runtime**: `Python 3`
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `sh scripts/start_frontend.sh`
4. **Env Var**: `FINANCIAL_AGENT_API_URL` (Point to your Backend URL)

---

## 4. Environment Variables (Required)
Ensure the following variables are set in your production environment:

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | Your Groq API key. |
| `LANGFUSE_PUBLIC_KEY` | Public key for observability. |
| `LANGFUSE_SECRET_KEY` | Secret key for observability. |
| `FINANCIAL_AGENT_HOST` | Set to `0.0.0.0`. |
| `FINANCIAL_AGENT_EXPLANATION_MODE` | Set to `groq`. |

---

## 5. Development Mode (Local Venv)
To run without Docker locally:
1. `source .venv/bin/activate`
2. Terminal 1: `sh scripts/start_backend.sh`
3. Terminal 2: `sh scripts/start_frontend.sh`
