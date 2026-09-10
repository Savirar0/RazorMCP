import streamlit as st
import requests
import json
import os
BASE_DIR = Path(__file__).resolve().parent.parent
FAVICON_PATH = os.path.join(BASE_DIR, "media", "image.png")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(page_title="Razorpay Agentic Seller Dashboard", layout="wide", page_icon=FAVICON_PATH)

st.title("🤖 Razorpay Agentic Seller — Live Transaction Inspector")
st.caption("Track 01: Machine-to-Machine AI Seller Gateway with Pydantic Guardrails & Audit Trail")
st.caption(f"Backend: {BACKEND_URL}")

# Sidebar - Settings & Guardrail Rules
st.sidebar.header("🛡️ Active Guardrail Config")
st.sidebar.metric("Max Discount Cap", "20.0%")
st.sidebar.metric("Max Transaction Limit", "₹10,000")
st.sidebar.info("All transactions are strictly bounded by Pydantic schema validation prior to Razorpay Order creation.")

# Main Layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. AI Buyer Request Simulation")
    buyer_id = st.text_input("Buyer Agent ID", value="agent_buyer_demo_01")
    prompt = st.text_area("Buyer Prompt / Search Intent", value="I need a silent mechanical keyboard with a wrist rest under 5000 INR")
    budget = st.number_input("Max Authorized Budget (INR)", value=5000.0, step=500.0)

    trigger_buy = st.button("🚀 Execute Machine-to-Machine Checkout", type="primary")

if trigger_buy:
    with col2:
        st.subheader("2. Real-Time Transaction Execution")

        with st.spinner("Connecting to Seller Agent & Processing Guardrails..."):
            try:
                res = requests.post(
                    f"{BACKEND_URL}/api/v1/agent/process-intent",
                    json={
                        "buyer_agent_id": buyer_id,
                        "query": prompt,
                        "max_budget_inr": budget
                    },
                    timeout=60
                )
                data = res.json()

                status = data.get("status")
                if status == "SUCCESS":
                    is_demo_transaction = any(step.get("step") == "DEMO_ORDER_SIMULATED" for step in data.get("audit_trail", []))
                    if is_demo_transaction:
                        st.success("Demo transaction completed — no live payment order was created.")
                    else:
                        st.success("Transaction successful — Razorpay Test Mode order created.")
                    st.metric("Razorpay Order ID", data.get("razorpay_order_id"))
                    st.metric("Total Charged", f"₹{data.get('amount_paid_inr')}")
                elif status == "GUARDRAIL_REJECTED":
                    st.error(f"Transaction Blocked by Guardrail: {data['validation_details']['rejection_code']}")
                    st.warning(data['validation_details']['rejection_reason'])
                else:
                    st.error(f"Execution Error: {data['validation_details']['rejection_reason']}")

                st.subheader("3. Immutable Decision Audit Trail")
                for step in data.get("audit_trail", []):
                    with st.expander(f"Step: {step['step']}"):
                        st.json(step)

            except Exception as e:
                st.error(f"Failed to connect to backend: {e}")
