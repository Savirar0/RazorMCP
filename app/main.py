from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

from app.config import settings
from app.services.catalog import catalog_service, Product
from app.core.guardrails import guardrail_engine, GuardrailValidationResult
from app.services.seller_agent import seller_agent_service, BuyerIntentRequest, AgenticTransactionResult

# ------------------------------------------------------------------------------
# 1. Initialize FastAPI Application
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Razorpay Agentic Seller Gateway",
    description="Machine-to-Machine AI Seller Gateway powering agentic commerce with Razorpay Test Mode APIs and FastMCP.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend judge dashboards or browser-based AI buyers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# 2. Initialize FastMCP Server (Model Context Protocol)
# ------------------------------------------------------------------------------
mcp = FastMCP(
    name="Razorpay AI Seller Agent",
    instructions="Autonomous merchant seller tools for product discovery, margin-aware negotiation, and Razorpay payment execution."
)


@mcp.tool(name="search_catalog", description="Search product catalog by keyword query and maximum price cap in INR.")
def mcp_search_catalog(query: str, max_price: Optional[float] = None) -> List[Dict[str, Any]]:
    products = catalog_service.search_catalog(query=query, max_price=max_price)
    return [p.model_dump() for p in products]


@mcp.tool(name="process_agentic_purchase", description="Negotiate quote, evaluate guardrails, and generate Razorpay test order in one atomic step.")
def mcp_process_purchase(buyer_agent_id: str, query: str, max_budget_inr: float) -> Dict[str, Any]:
    request = BuyerIntentRequest(
        buyer_agent_id=buyer_agent_id,
        query=query,
        max_budget_inr=max_budget_inr
    )
    result = seller_agent_service.process_buyer_request(request)
    return result.model_dump()


# ------------------------------------------------------------------------------
# 3. REST API Routes
# ------------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "max_discount_cap_pct": settings.MAX_DISCOUNT_PERCENTAGE,
        "max_transaction_limit_inr": settings.MAX_TRANSACTION_LIMIT_INR
    }


@app.get("/api/v1/catalog/search", response_model=List[Product], tags=["Catalog"])
async def search_catalog_endpoint(
    query: str = Query(..., description="Search keyword for product discovery"),
    max_price: Optional[float] = Query(None, description="Optional price filter in INR")
):
    """
    Exposes catalog discovery endpoint for AI Buyer agents reading REST schemas.
    """
    return catalog_service.search_catalog(query=query, max_price=max_price)


@app.post("/api/v1/agent/process-intent", response_model=AgenticTransactionResult, tags=["Agent Commerce"])
async def process_intent_endpoint(request: BuyerIntentRequest):
    """
    Core entry point for AI Buyer Agents to execute end-to-end negotiated transactions.
    """
    try:
        result = seller_agent_service.process_buyer_request(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


# Mount FastMCP server endpoints on FastAPI app (over SSE)
app.mount("/mcp", mcp.http_app(path="/"))
