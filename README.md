# Financial Agent

Client-server autonomous financial advisor agent built for the backend engineering challenge in AgentAssignment/. This system uses a deterministic analytics core combined with a graph-shaped reasoning engine to explain portfolio movements based on market news and trends.

## Why This Is Different

Most financial dashboards report what happened.

This agent explains why it happened by constructing causal chains:

**Macro News -> Sector Movement -> Stock Impact -> Portfolio Outcome**

It also:
- Quantifies the contribution of each factor
- Simulates counterfactual scenarios
- Filters irrelevant signals automatically

## Core Features

### Intelligent Reasoning
- **Multi-Level Causal Linking**: Maps news events through sectors and specific stocks down to portfolio impact (News -> Sector -> Stock -> Portfolio).
- **Explicit Causal Graph**: Returns a structured JSON graph showing the logical chain of events for every analysis.

  #### Example Causal Graph
  ```json
  [
    {
      "event": "RBI Hawkish Policy",
      "sector": "Banking",
      "stock": "HDFC Bank",
      "portfolio_impact": -2.61
    }
  ]
  ```

- **Counterfactual Attribution**: Calculates what the portfolio performance would have been if a specific driver were removed.
- **Conflict Detection**: Automatically identifies and explains discrepancies between news sentiment and actual market price action.

### Portfolio Analytics
- **Mutual Fund Look-Through**: Transparently calculates sector and stock exposure even when held through mutual fund schemes.
- **Risk Analysis**: Detects concentration risks, sector-level sensitivities (e.g., interest rate sensitivity), and single-stock dominance.
- **Asset Allocation**: Provides a detailed breakdown of holdings across direct stocks and mutual funds.

### Observability and Evaluation
- **Intermediate Step Tracing**: Full transparency into the reasoning process with traces for filtered_news, linked_signals, drivers, and final_summary.
- **Self-Evaluation Layer**: Every briefing is scored on Causality, Relevance, and Specificity (1.0 - 5.0).
- **Langfuse Integration**: Optional production-grade tracing for debugging and performance monitoring.

---

## Requirements Mapping (Rubric Compliance)

| Requirement | Status | Implementation Detail |
| :--- | :---: | :--- |
| **Reasoning Quality (35%)** | OK | Implements explicit causal linking and counterfactual analysis. |
| **Explicit Causal Graph** | OK | Provided in the causal_graph field of the /analyze response. |
| **Code Design (20%)** | OK | Modular, service-oriented architecture with strict type hints and Pydantic schemas. |
| **Observability (15%)** | OK | Integrated Langfuse tracing for all intermediate reasoning phases. |
| **Edge Case Handling (15%)** | OK | Handles conflicts and provides a professional fallback for "No Relevant News" scenarios. |
| **Evaluation Layer (15%)** | OK | Provides a structured evaluation_breakdown for every briefing. |

### Completed Features
- Multi-phase reasoning pipeline (LangGraph-inspired nodes).
- News -> Sector -> Stock -> Portfolio attribution.
- Look-through exposure analysis for Mutual Funds.
- Conflict detection (Positive news vs Negative price).
- Professional fallback for "No Relevant News".
- Langfuse/Tracing support.

### Future Scope
- **Real-time Data**: Currently uses the provided mock JSON datasets (standard for this challenge).
- **Temporal Trends**: Deeper historical trend analysis (beyond current sentiment indicators).
- **Database Persistence**: Currently relies on external tracing (Langfuse) or in-memory logging.

---

## Architecture

The system follows a modular pipeline that separates data processing from reasoning:

```text
Client Request
    -> FastAPI API Layer
    -> Data Loading Layer (DataLoader)
    -> Phase 1: Market Intelligence (Sentiment & Sector Trends)
    -> Phase 2: Portfolio Analytics (Exposure & P&L)
    -> Phase 3: Reasoning Engine (Filtering -> Linking -> Ranking)
    -> Phase 4: Explanation Generation (Template or LLM)
    -> Phase 5: Evaluation & Tracing
    -> Response to Client
```

## How the Agent Thinks

1. **Filters** irrelevant news
2. **Links** relevant signals to sectors and stocks
3. **Computes** impact contribution
4. **Ranks** top drivers
5. **Generates** explanation
6. **Evaluates** reasoning quality

---

## Performance Optimizations

- **Minimal LLM usage** (only for explanation/evaluation)
- **Deterministic analytics pipeline** (precise math, no hallucinations)
- **Signal filtering** reduces computation and token usage
- **Batched reasoning** avoids redundant analysis

---

## Setup and Execution

### 1. Environment Setup
The project requires Python 3.10+.
```bash
# Recommended: use the existing virtual environment
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Server
```bash
# Terminal 1: Start Backend
sh scripts/start_backend.sh
```

### 3. Run the Frontend (Streamlit)
```bash
# Terminal 2: Start Dashboard
sh scripts/start_frontend.sh
```

### 4. Running Tests
```bash
# Run baseline API tests
PYTHONPATH=. .venv/bin/pytest tests/test_api.py

# Run rubric-specific enhancement tests
PYTHONPATH=. .venv/bin/pytest tests/test_enhancements.py
```

---

## Hosting and Deployment

### 1. Docker (Recommended for Production)
The project includes a multi-stage Dockerfile and docker-compose.yml for quick containerized deployment.

```bash
# Build and run the containers
docker-compose up --build
```

### 2. Cloud Hosting (Render / Railway)
Since this is a standard FastAPI app, you can host it easily on any PaaS. Please refer to DEPLOYMENT.md for detailed instructions on both Docker and Native Python setups.

---

## API Reference

### POST /analyze
Analyzes a portfolio and returns a detailed financial briefing.

**Request:**
```json
{
  "portfolio_id": "sector_heavy"
}
```

**Response Highlights:**
- summary: Human-readable 4-line briefing.
- causal_graph: List of nodes linking events to portfolio impact.
- drivers: Detailed impact attribution for top factors.
- evaluation_breakdown: Scores for causality, relevance, and specificity.
- counterfactuals: "What-if" analysis for the top drivers (up to 2).
- confidence: An overall confidence score derived from signal alignment, data completeness, and conflict penalties.

---

## Configuration
Use environment variables or a .env file to customize the agent:
- FINANCIAL_AGENT_EXPLANATION_MODE: template (default) or groq.
- GROQ_API_KEY: Required for Groq explanations.
- LANGFUSE_PUBLIC_KEY / SECRET_KEY: Enable production tracing.
