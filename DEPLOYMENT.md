# Deployment Guide: Financial Advisor Agent

This project is designed to be highly portable and can be deployed easily using Docker.

## 1. Local Deployment (Recommended)
The easiest way to run the project is using **Docker Compose**. This will automatically build and link the FastAPI backend and the Streamlit frontend.

```bash
# Clone the repository
git clone <your-repo-url>
cd financial-agent

# Ensure your .env file is configured
cp .env.example .env  # If not already present

# Build and start the containers
docker-compose up --build
```

- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Frontend Dashboard**: [http://localhost:8501](http://localhost:8501)

---

## 2. Cloud Deployment (Render / Railway / AWS)
Since the project is containerized, you can deploy it to any cloud provider that supports Docker.

### Render (Recommended Path)
I have configured a unified **Multi-Stage Dockerfile** to work seamlessly with Render.

1. **Connect your GitHub Repository** to Render.
2. **Create a New Web Service** for the **Backend**:
   - **Environment**: Docker
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Target**: `backend`
   - **Environment Variables**: Add all keys from your `.env`.
3. **Create a New Web Service** for the **Frontend**:
   - **Environment**: Docker
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Target**: `frontend`
   - **Environment Variables**: Add `FINANCIAL_AGENT_API_URL` pointing to your Backend URL.

---

## 3. Environment Variables (Critical)
Ensure the following variables are set in your production environment:

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | Your Groq API key for the LLM reasoning. |
| `LANGFUSE_PUBLIC_KEY` | Public key for observability. |
| `LANGFUSE_SECRET_KEY` | Secret key for observability. |
| `FINANCIAL_AGENT_HOST` | Set to `0.0.0.0` for Docker/Cloud. |
| `FINANCIAL_AGENT_EXPLANATION_MODE` | Set to `groq`. |

---

## 4. CI/CD (Optional)
You can use GitHub Actions to automate your deployment. Here is a basic workflow skeleton:
1. **Lint & Test**: Run `flake8` and `pytest`.
2. **Build Image**: Build the Docker image.
3. **Deploy**: Push to your cloud provider (e.g., Render Deploy Hook).
