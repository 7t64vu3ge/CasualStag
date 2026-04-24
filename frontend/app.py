import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_chat import message
import os

# Configuration
BACKEND_URL = os.getenv("FINANCIAL_AGENT_API_URL", "https://financial-agent-api-zw0e.onrender.com")

st.set_page_config(
    page_title="Financial Agent Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
    }
    .stMetric {
        background-color: #1e293b;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #334155;
    }
    .stAlert {
        background-color: #1e293b;
        color: #f8fafc;
        border: 1px solid #334155;
    }
    </style>
""", unsafe_allow_html=True)

# Helper Functions
def fetch_portfolios():
    try:
        response = requests.get(f"{BACKEND_URL}/portfolios")
        return response.json()
    except Exception as e:
        st.error(f"Failed to connect to backend: {e}")
        return []

def run_analysis(portfolio_id):
    try:
        response = requests.post(
            f"{BACKEND_URL}/analyze", 
            json={"portfolio_id": portfolio_id}
        )
        return response.json()
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        return None

def send_chat(portfolio_id, user_msg, history):
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={
                "portfolio_id": portfolio_id,
                "message": user_msg,
                "history": history
            }
        )
        return response.json()
    except Exception as e:
        return {"answer": f"Error: {e}", "context_used": []}

# Sidebar
st.sidebar.title("Control Panel")
portfolios = fetch_portfolios()
if portfolios:
    portfolio_options = {f"{p['user_name']} ({p['portfolio_id']})": p['portfolio_id'] for p in portfolios}
    selected_label = st.sidebar.selectbox("Select Portfolio", list(portfolio_options.keys()))
    selected_id = portfolio_options[selected_label]
    
    if st.sidebar.button("Run Analysis", use_container_width=True):
        with st.spinner("Analyzing market drivers..."):
            result = run_analysis(selected_id)
            st.session_state.last_result = result
            st.session_state.chat_history = []
else:
    st.sidebar.warning("No portfolios found. Is the backend running?")

# Main Content
st.title("Financial Advisor Agent")

if "last_result" in st.session_state and st.session_state.last_result:
    res = st.session_state.last_result
    
    # Row 1: Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Reasoning Score", f"{res['score']}/5.0")
    col2.metric("Confidence", f"{res['confidence']*100:.0f}%")
    col3.metric("Data Quality", f"{res['confidence_factors']['data_completeness']*100:.0f}%")
    col4.metric("Signals Aligned", f"{res['confidence_factors']['signal_alignment']*100:.0f}%")
    
    st.divider()
    
    # Row 2: Left Content & Right Content
    left_col, right_col = st.columns([1, 1])
    
    with left_col:
        # Section A: Executive Summary
        st.subheader("Executive Summary")
        st.info(res['summary'])
        
        with st.expander("Dominance Insight"):
            st.write(res.get('insight', "No dominance insight available."))
            
        with st.expander("Counterfactuals (What if?)"):
            for cf in res.get('counterfactuals', []):
                st.write(f"**Without {cf['without']}:** {cf['insight']}")

        st.divider()

        # Section B: Causal Reasoning Graph (Now below Executive Summary)
        st.subheader("Causal Reasoning Graph")
        if res.get('causal_graph'):
            df_graph = pd.DataFrame(res['causal_graph'])
            # The backend schema uses 'event' as the primary identifier for causal nodes
            chart_y = 'event' if 'event' in df_graph.columns else df_graph.columns[0]
            
            fig = px.bar(
                df_graph, 
                x='portfolio_impact', 
                y=chart_y, 
                orientation='h',
                title="Portfolio Impact by Source",
                color='portfolio_impact',
                color_continuous_scale='RdYlGn',
                text=chart_y
            )
            fig.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No causal links isolated.")

    with right_col:
        st.subheader("AI Chat Advisor")
        chat_container = st.container(height=600)
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        # Display chat history
        with chat_container:
            for i, chat in enumerate(st.session_state.chat_history):
                message(chat["content"], is_user=(chat["role"] == "user"), key=f"chat_msg_{i}_{selected_id}")
        
        # Chat input
        if prompt := st.chat_input("Ask about HDFC Bank, market trends, or risks...", key=f"chat_input_{selected_id}"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.spinner("Thinking..."):
                # Prepare history for API
                api_history = [{"role": c["role"], "content": c["content"]} for c in st.session_state.chat_history[:-1]]
                ans = send_chat(selected_id, prompt, api_history)
                st.session_state.chat_history.append({"role": "assistant", "content": ans["answer"]})
            st.rerun()

    # Row 3: Drivers
    st.divider()
    st.subheader("Market Drivers")
    d1, d2 = st.columns(2)
    
    with d1:
        for driver in res['drivers']:
            with st.expander(f"Factor: {driver['factor']} ({driver['impact']:+.2f} pp)"):
                st.write(f"**Causal Chain:** {driver.get('causal_chain', 'N/A')}")
                if driver.get('impact_details'):
                    st.json(driver['impact_details'])
    
    with d2:
        st.subheader("Risks & Conflicts")
        for risk in res['risks']:
            st.warning(risk)
        for conflict in res['conflicts']:
            st.error(f"Conflict: {conflict['signal']}\n\n{conflict['explanation']}")

else:
    st.info("👈 Select a portfolio and click 'Run Analysis' to begin.")
    
    # Placeholder Visual for "Empty State"
    st.subheader("Sample Analytics View")
    sample_data = pd.DataFrame({
        "Sector": ["Banking", "IT", "Auto", "Energy"],
        "Impact": [-1.2, 0.4, -0.3, 0.8]
    })
    fig = px.bar(sample_data, x="Sector", y="Impact", color="Impact", color_continuous_scale="RdYlGn")
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
