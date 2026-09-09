# Phase 3 Implementation: LLM Seller Agent & Negotiation Engine

## Overview
This document summarizes the implementation of **Phase 3** of the Razorpay Agentic Seller Gateway project. Phase 3 introduces the autonomous AI Seller Agent that uses Instructor + OpenAI to parse buyer intent, search the catalog, calculate margin-aware bundle offers, enforce guardrails, and execute Razorpay orders.

---

## Files Created

### 1. `app/services/seller_agent.py`
**Purpose**: End-to-end agentic pipeline — natural language → structured quote → guardrails → Razorpay order.

#### Data Models

**`BuyerIntentRequest`**
```python
buyer_agent_id: str
query: str
max_budget_inr: float
```

**`AgenticTransactionResult`**
```python
status: str  # "SUCCESS", "GUARDRAIL_REJECTED", "ERROR"
buyer_agent_id: str
razorpay_order_id: Optional[str]
amount_paid_inr: Optional[float]
applied_quote: Optional[ProposedQuote]
validation_details: GuardrailValidationResult
audit_trail: List[Dict[str, Any]]
```

#### `SellerAgentService` Class

**`__init__()`**
- Initializes Instructor-patched OpenAI client: `instructor.from_openai(OpenAI())`
- Requires `OPENAI_API_KEY` in environment

**`process_buyer_request(request: BuyerIntentRequest) -> AgenticTransactionResult`**

| Step | Operation | Details |
|------|-----------|---------|
| 1 | **Intent Received** | Logs buyer_id, query, budget to audit trail |
| 2 | **Catalog Search** | `catalog_service.search_catalog(query, max_price=budget)` — falls back to all items if no matches |
| 3 | **LLM Prompt Construction** | System prompt includes merchant rules, catalog context (SKU, price, margin, stock), budget |
| 4 | **Structured LLM Output** | Instructor call with `response_model=ProposedQuote` → validated Pydantic object |
| 5 | **Guardrail Validation** | `guardrail_engine.validate_quote()` — 4 rules (global limit, buyer budget, discount cap, inventory) |
| 6 | **Razorpay Order** | `razorpay_service.create_order()` with metadata in `notes` |
| 7 | **Result Assembly** | Returns `AgenticTransactionResult` with full audit trail |

**Prompt Engineering Highlights**:
- Injects `settings.MAX_DISCOUNT_PERCENTAGE` and `request.max_budget_inr` dynamically
- Provides full catalog context: `SKU | Name | Price | Margin | Stock`
- Explicit instructions for upsell logic and discount calculation
- Requires accurate `original_total_inr`, `final_discounted_total_inr`, `applied_discount_percentage`

**Error Handling**:
- Guardrail rejection → `status="GUARDRAIL_REJECTED"` with `rejection_code` + `rejection_reason`
- Razorpay API error → `status="ERROR"` with `RAZORPAY_API_ERROR` code
- All paths return structured result with audit trail

---

### 2. `test_phase3.py` (Project Root)
**Purpose**: End-to-end test of the complete agentic pipeline.

**Test Case**:
```python
BuyerIntentRequest(
    buyer_agent_id="buyer_bot_991",
    query="I need a silent mechanical keyboard with a wrist rest under 5000 INR",
    max_budget_inr=5000.00
)
```

**Expected Behavior**:
1. Catalog search finds Keyboard (₹4,499) + Wrist Rest (₹599)
2. LLM proposes bundle with ~5-10% discount to stay under ₹5,000
3. Guardrails approve (discount < 20%, total < budget, stock available)
4. Razorpay order created in Test Mode
5. Returns `status="SUCCESS"` with order ID and audit trail

---

## Running the Test

**Prerequisites**:
```bash
# Add to .env
OPENAI_API_KEY="sk-your-openai-key-here"
```

```bash
cd /home/xenzi/AISeller/Backend
./venv/bin/python test_phase3.py
```

**Expected Output** (example):
```
--- Testing Phase 3: AI Seller Agent Pipeline ---

Final Transaction Status: SUCCESS
Razorpay Order ID: order_XXXXXXXXXXXXXX
Total Amount Charged: ₹4798.0

Audit Trail Logs:
  [INTENT_RECEIVED] -> {'step': 'INTENT_RECEIVED', 'buyer_id': 'buyer_bot_991', 'query': 'I need a silent mechanical keyboard with a wrist rest under 5000 INR', 'budget': 5000.0}
  [CATALOG_SEARCH] -> {'step': 'CATALOG_SEARCH', 'matches_found': 2}
  [QUOTE_GENERATED] -> {'step': 'QUOTE_GENERATED', 'quote': {...}}
  [GUARDRAIL_EVALUATION] -> {'step': 'GUARDRAIL_EVALUATION', 'approved': True, 'code': None}
  [RAZORPAY_ORDER_CREATED] -> {'step': 'RAZORPAY_ORDER_CREATED', 'order_id': 'order_XXXXXXXXXXXXXX', 'amount_paise': 479800}
```

---

## Architecture Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Instructor + OpenAI for structured output | ✅ | `instructor.from_openai(OpenAI())` with `response_model=ProposedQuote` |
| Natural language intent parsing | ✅ | LLM prompt with buyer query + catalog context |
| Semantic catalog search | ✅ | `catalog_service.search_catalog()` with price filter |
| Margin-aware upsell logic | ✅ | Prompt instructs adding high-margin accessories |
| Discount calculation accuracy | ✅ | LLM computes `original_total`, `final_total`, `discount_pct` |
| Guardrail integration | ✅ | `guardrail_engine.validate_quote()` before Razorpay |
| Razorpay order with metadata | ✅ | `notes` includes buyer_id, upsell flag, discount % |
| Audit trail (append-only JSON) | ✅ | `audit_trail` list with every step logged |
| Graceful failure handling | ✅ | Structured `AgenticTransactionResult` for all outcomes |

---

## Integration Flow

```
BuyerAgent (MCP/REST)
       │
       ▼
BuyerIntentRequest
       │
       ▼
SellerAgentService.process_buyer_request()
       │
       ├──► catalog_service.search_catalog()
       │
       ├──► Instructor + OpenAI (gpt-4o-mini)
       │       │
       │       └──► ProposedQuote (Pydantic validated)
       │
       ├──► guardrail_engine.validate_quote()
       │       │
       │       ├──► APPROVED → razorpay_service.create_order()
       │       │
       │       └──► REJECTED → GUARDRAIL_REJECTED result
       │
       └──► AgenticTransactionResult (status + audit_trail)
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Instructor for structured output | Guarantees valid `ProposedQuote` schema; no JSON parsing errors |
| `gpt-4o-mini` model | Cost-effective for high-volume agentic commerce; sufficient for structured tasks |
| Catalog fallback to all items | Handles vague queries; ensures upsell candidates always available |
| Audit trail as list of dicts | JSON-serializable; easy to persist to database/log aggregation |
| Guardrails as hard gate | Prevents LLM hallucinations from creating invalid orders |
| Metadata in Razorpay `notes` | Enables reconciliation & analytics without extra DB calls |

---

## Dependencies Used

From `requirements.txt`:
- `instructor>=1.0.0` — Structured LLM output
- `openai>=1.14.0` — OpenAI API client
- `pydantic>=2.6.0` — Data models (via `ProposedQuote`, `GuardrailValidationResult`)

---

## Next Steps (Phase 4)

1. **`app/main.py`** — FastAPI application with:
   - REST endpoints (`/search`, `/quote`, `/checkout`)
   - FastMCP tool mounting for MCP protocol
   - Audit logging middleware
   - Health check endpoint

2. **MCP Tool Definitions**:
   - `search_products(query, max_price)` → `List[Product]`
   - `get_negotiated_quote(buyer_agent_id, query, max_budget)` → `ProposedQuote`
   - `execute_checkout(quote)` → `Razorpay Order`

3. **OpenAPI/Swagger** auto-generation for AI Buyer Agent discovery

---

## Security Notes

- **Never** pass unvalidated LLM output to Razorpay — always through guardrails
- `OPENAI_API_KEY` must be kept secret (`.env`, never committed)
- Razorpay Test Mode used throughout — no real money movement
- All monetary values in INR for logic, converted to paise only at Razorpay boundary

---

*Generated as part of Razorpay Buildathon — Track 01 (AI Growth & Agentic Commerce)*
