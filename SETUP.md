# Local Setup Guide: Financial Advisor Agent

Follow these instructions to set up the Financial Advisor Agent on your local machine for development and testing.

## Prerequisites
- **Python 3.10 or higher**
- **Git**
- **Groq API Key** (Optional, but recommended for high-quality reasoning)
- **Docker & Docker Desktop** (Optional, only if using the Docker setup)

---

## 1. Clone the Repository
Open your terminal and run:
```bash
git clone <your-repository-url>
cd financial-agent
```

## 2. Environment Configuration
Create a `.env` file in the root directory. You can use the provided example as a starting point:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
- `GROQ_API_KEY`: Get one from [console.groq.com](https://console.groq.com/).
- `FINANCIAL_AGENT_EXPLANATION_MODE`: Set to `groq` to enable AI reasoning.

### Observability (Langfuse)
To track reasoning steps and LLM performance:
1. Create a project at [cloud.langfuse.com](https://cloud.langfuse.com).
2. Add these to your `.env`:
   - `LANGFUSE_PUBLIC_KEY`: Your project public key.
   - `LANGFUSE_SECRET_KEY`: Your project secret key.
   - `LANGFUSE_BASE_URL`: Defaults to `https://cloud.langfuse.com` (leave empty for cloud, or set your own URL for self-hosting).

## 3. Installation

### Method A: Using Virtual Environment (Recommended)
1. **Create the environment**:
   ```bash
   python -m venv .venv
   ```
2. **Activate it**:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Method B: Using Docker
Ensure Docker Desktop is running, then simply run:
```bash
docker-compose up --build
```
This will automatically handle all installation and start both services.

---

## 4. Running the Application (Local)
If you are using **Method A**, you need to start the services in two separate terminal windows:

### Terminal 1: Backend API
```bash
sh scripts/start_backend.sh
```
*The API will be available at http://localhost:8000*

### Terminal 2: Frontend Dashboard
```bash
sh scripts/start_frontend.sh
```
*The Dashboard will open automatically at http://localhost:8501*

---

## 5. Verification
To ensure everything is working correctly:
1. Open the Dashboard in your browser.
2. Select a portfolio (e.g., `sector_heavy`) from the sidebar.
3. Click **Run Analysis**.
4. You should see the reasoning score, causal graph, and AI summary populate.

## Troubleshooting
- **Port already in use**: If port 8000 or 8501 is taken, the app will fail to start. Close any other Python or Docker processes running on these ports.
- **Missing Data**: Ensure the `AgentAssignment/` folder is present in the root directory, as the agent relies on its JSON files.
