# Financial Agent

Client-server autonomous financial advisor agent built for the backend engineering challenge in `AgentAssignment/`.

## What It Does

The server accepts a portfolio identifier and runs a four-phase analysis pipeline:

1. Data loading
2. Market intelligence
3. Portfolio analytics
4. Graph-shaped reasoning, evaluation, and observability

It then returns a concise financial briefing with:

- Summary
- Top drivers
- Risks
- Conflicts
- Confidence score
- Reasoning quality score

## Architecture

The implementation follows the workflow requested in the assignment:

```text
Client Request
    ->
FastAPI API Layer
    ->
Data Loading Layer
    ->
Phase 1: Market Intelligence
    ->
Phase 2: Portfolio Analytics
    ->
Phase 3: Reasoning Engine
    ->
Phase 4: Evaluation + Observability
    ->
Response to Client
```

The reasoning engine is built as a LangGraph-style node pipeline:

```text
[Load State]
    ->
[Filter Signals]
    ->
[Link Signals]
    ->
[Impact Ranking]
    ->
[Explanation]
    ->
[Evaluation]
```

If `langgraph` is installed later, the engine can run through a real `StateGraph`. The current code works without it using the same node flow.

## Project Structure

```text
financial_agent/
  config.py
  data_loader.py
  market_intelligence.py
  portfolio_analytics.py
  reasoning_engine.py
  explanation.py
  observability.py
  service.py
  main.py
client.py
tests/test_api.py
AgentAssignment/
```

## Run The Server

Use the existing virtual environment if you already have it:

```bash
.venv/bin/python -m financial_agent
```

Or run with Uvicorn directly:

```bash
.venv/bin/uvicorn financial_agent.main:app --host 127.0.0.1 --port 8000
```

## Run The Client

With the server running:

```bash
.venv/bin/python client.py --portfolio-id sector_heavy
```

You can also analyze:

- `PORTFOLIO_001`
- `PORTFOLIO_002`
- `PORTFOLIO_003`
- `diversified`
- `sector_heavy`
- `conservative`

## API

### `GET /health`

Returns service health.

### `GET /portfolios`

Returns supported portfolio IDs and aliases.

### `POST /analyze`

Request:

```json
{
  "portfolio_id": "sector_heavy"
}
```

Response shape:

```json
{
  "summary": "Your portfolio declined ...",
  "drivers": [
    {
      "factor": "Banking move after RBI hawkish stance ...",
      "impact": -1.98
    }
  ],
  "risks": [
    "High exposure to Banking (72.09%)"
  ],
  "conflicts": [
    {
      "signal": "Bajaj Finance Asset Quality Stable, Management Guides for Strong Growth",
      "explanation": "Positive company news but stock falling due to sector-wide rate concerns"
    }
  ],
  "confidence": 0.86,
  "score": 4.1
}
```

## Optional Environment Variables

```bash
FINANCIAL_AGENT_DATA_DIR=AgentAssignment
FINANCIAL_AGENT_HOST=127.0.0.1
FINANCIAL_AGENT_PORT=8000
FINANCIAL_AGENT_EXPLANATION_MODE=template
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
OPENAI_API_KEY=
OPENAI_MODEL=
```

## Notes

- The deterministic core performs the market and portfolio math.
- The explanation layer defaults to a template-based generator to avoid unnecessary LLM calls.
- If `FINANCIAL_AGENT_EXPLANATION_MODE=openai` and OpenAI credentials are configured, explanation generation can use the configured model.
- Langfuse tracing is optional and activates only when the related environment variables are set.
