from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException

from financial_agent.config import get_settings
from financial_agent.service import FinancialAdvisorService
from financial_agent.schemas import AnalyzeRequest, AnalyzeResponse, ChatRequest, ChatResponse, PortfolioDescriptor


from fastapi.responses import HTMLResponse


@lru_cache(maxsize=1)
def get_service() -> FinancialAdvisorService:
    return FinancialAdvisorService(get_settings())


app = FastAPI(
    title="Financial Agent",
    version="1.0.0",
    description="Client-server autonomous financial advisor agent built around deterministic analytics and graph-shaped reasoning.",
)


@app.get("/", response_class=HTMLResponse)
def developer_console() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Financial Agent Dev Console</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --accent: #38bdf8;
            --border: #334155;
        }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 { border-bottom: 2px solid var(--border); padding-bottom: 1rem; color: var(--accent); }
        .controls {
            background: var(--card);
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            display: flex;
            gap: 1rem;
            align-items: center;
            margin-bottom: 2rem;
        }
        select, button {
            padding: 0.5rem 1rem;
            border-radius: 4px;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text);
            font-size: 1rem;
        }
        button {
            background: var(--accent);
            color: var(--bg);
            border: none;
            font-weight: 600;
            cursor: pointer;
        }
        button:hover { opacity: 0.9; }
        .grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }
        .card {
            background: var(--card);
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        .card h2 { margin-top: 0; font-size: 1.2rem; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
        pre {
            background: #000;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.85rem;
        }
        .summary-content { white-space: pre-wrap; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--border); }
        th { color: var(--accent); }
        .loading { opacity: 0.5; pointer-events: none; }
        
        /* Chat UI Styles */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 400px;
        }
        .chat-messages {
            flex-grow: 1;
            overflow-y: auto;
            padding: 1rem;
            background: #000;
            border-radius: 4px;
            margin-bottom: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        .message {
            max-width: 80%;
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            font-size: 0.9rem;
        }
        .message.user {
            align-self: flex-end;
            background: var(--accent);
            color: var(--bg);
        }
        .message.assistant {
            align-self: flex-start;
            background: var(--border);
            color: var(--text);
            white-space: pre-wrap;
        }
        .chat-input-group {
            display: flex;
            gap: 0.5rem;
        }
        .chat-input-group input {
            flex-grow: 1;
            padding: 0.5rem;
            border-radius: 4px;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛠️ Dev Console</h1>
        
        <div class="controls" id="controls">
            <label for="portfolioSelect">Portfolio:</label>
            <select id="portfolioSelect">
                <option value="">Loading...</option>
            </select>
            <button id="analyzeBtn">Analyze</button>
        </div>

        <div class="grid">
            <div class="card">
                <h2>Briefing Summary</h2>
                <div id="summary" class="summary-content">No analysis run yet.</div>
            </div>

            <div class="card">
                <h2>Causal Graph</h2>
                <div id="graphContainer">
                    <p>No graph available.</p>
                </div>
            </div>

            <div class="card">
                <h2>Raw JSON Response</h2>
                <pre id="rawJson">{}</pre>
            </div>

            <div class="card">
                <h2>💬 Chat with Agent</h2>
                <div class="chat-container">
                    <div id="chatMessages" class="chat-messages">
                        <div class="message assistant">Ask me anything about your portfolio once analyzed!</div>
                    </div>
                    <div class="chat-input-group">
                        <input type="text" id="chatInput" placeholder="How is HDFC Bank affecting me?">
                        <button id="sendBtn">Send</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const portfolioSelect = document.getElementById('portfolioSelect');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const summaryDiv = document.getElementById('summary');
        const graphContainer = document.getElementById('graphContainer');
        const rawJsonPre = document.getElementById('rawJson');
        const controls = document.getElementById('controls');

        async function fetchPortfolios() {
            try {
                const res = await fetch('/portfolios');
                const data = await res.json();
                portfolioSelect.innerHTML = data.map(p => 
                    `<option value="${p.portfolio_id}">${p.user_name} (${p.portfolio_id})</option>`
                ).join('');
            } catch (err) {
                portfolioSelect.innerHTML = '<option value="">Error loading</option>';
            }
        }

        async function analyze() {
            const portfolioId = portfolioSelect.value;
            if (!portfolioId) return;

            controls.classList.add('loading');
            summaryDiv.innerText = 'Analyzing...';
            
            try {
                const res = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ portfolio_id: portfolioId })
                });
                const data = await res.json();
                
                rawJsonPre.innerText = JSON.stringify(data, null, 2);
                summaryDiv.innerText = data.summary;
                
                if (data.causal_graph && data.causal_graph.length > 0) {
                    let html = '<table><thead><tr><th>Event</th><th>Entity</th><th>Impact</th><th>Conf</th></tr></thead><tbody>';
                    data.causal_graph.forEach(node => {
                        html += `<tr><td>${node.event}</td><td>${node.entity}</td><td>${node.portfolio_impact.toFixed(2)}%</td><td>${(node.confidence_score * 100).toFixed(0)}%</td></tr>`;
                    });
                    html += '</tbody></table>';
                    graphContainer.innerHTML = html;
                } else {
                    graphContainer.innerHTML = '<p>No significant news-driven drivers.</p>';
                }

            } catch (err) {
                summaryDiv.innerText = 'Error: ' + err.message;
            } finally {
                controls.classList.remove('loading');
            }
        }

        analyzeBtn.onclick = analyze;
        fetchPortfolios();

        // Chat Logic
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        let chatHistory = [];

        async function sendChat() {
            const message = chatInput.value.trim();
            const portfolioId = portfolioSelect.value;
            if (!message || !portfolioId) return;

            // Add user message
            appendMessage('user', message);
            chatInput.value = '';

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        portfolio_id: portfolioId,
                        message: message,
                        history: chatHistory
                    })
                });
                const data = await res.json();
                
                appendMessage('assistant', data.answer);
                chatHistory.push({ role: 'user', content: message });
                chatHistory.push({ role: 'assistant', content: data.answer });
            } catch (err) {
                appendMessage('assistant', 'Error: ' + err.message);
            }
        }

        function appendMessage(role, text) {
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.innerText = text;
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        sendBtn.onclick = sendChat;
        chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendChat(); };
    </script>
</body>
</html>
    """


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/portfolios", response_model=list[PortfolioDescriptor])
def list_portfolios() -> list[PortfolioDescriptor]:
    return get_service().list_portfolios()


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_portfolio(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return get_service().analyze(payload.portfolio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        return get_service().chat(payload.portfolio_id, payload.message, payload.history)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

