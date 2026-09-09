# CompleteDocs.md
## Razorpay Agentic Seller Gateway — Complete Project Documentation

> **Razorpay Buildathon · Track 01: AI Growth & Agentic Commerce**
> A Machine-to-Machine (AI-to-AI) commerce gateway where autonomous AI Buyer Agents discover products, negotiate margin-aware bundles through an LLM seller brain, pass deterministic safety guardrails, and execute purchases on Razorpay Test Mode — with zero human clicks.

---

## Table of Contents
1. [What We Are Building & Why](#1-what-we-are-building--why)
2. [Tech Stack & Component Roles](#2-tech-stack--component-roles)
3. [System Architecture](#3-system-architecture)
4. [Phase-by-Phase: What Was Done](#4-phase-by-phase-what-was-done)
5. [How It Works — Request Lifecycle](#5-how-it-works--request-lifecycle)
6. [Worked Example — A Real Transaction](#6-worked-example--a-real-transaction)
7. [Safety & Guardrails](#7-safety--guardrails)
8. [Audit Trail](#8-audit-trail)
9. [API Reference Summary](#9-api-reference-summary)
10. [Achievements vs Track 01 Bar](#10-achievements-vs-track-01-bar)
11. [Running the System](#11-running-the-system)
12. [Future Scope](#12-future-scope)

---

## 1. What We Are Building & Why

### The Problem
Standard e-commerce assumes a **human** browses HTML/CSS pages, compares products, clicks "Add to Cart", and completes checkout forms. But the next wave of commerce is **agentic**: personal shopping assistants, automated procurement bots, and AI concierges acting on behalf of users. These agents cannot meaningfully "browse" a website — they need **machine-readable storefronts** and **machine-negotiable offers**.

### Our Solution
The **Agentic Seller Gateway** flips the storefront inside-out:

- **Machine-Readable Storefront** — Product catalog exposed as structured tools over MCP (Model Context Protocol) and OpenAPI/Swagger so *any* external AI buyer can discover and transact without custom integration.
- **Autonomous Negotiation** — An internal LLM seller (`gpt-oss-120b` via Groq) reads natural-language buyer intent, searches the catalog, picks cross-sell bundles by profit margin, and computes discounts to close the deal within budget — actively increasing Average Order Value (AOV).
- **Deterministic Safety** — No LLM output ever touches money directly. Every quote passes a hard Pydantic guardrail engine (spend caps, budget limits, discount ceilings, stock checks) before Razorpay is called.
- **Full Observability** — Every transaction emits an append-only JSON audit trail: intent → catalog search → quote → guardrail verdict → payment order. Judges can replay every decision.
- **Live Judge Visualization** — A Streamlit dashboard where judges type a buyer prompt and watch the whole machine-to-machine pipeline negotiate and settle in real time.

### Why It Matters for Track 01
This is not a chatbot bolted onto a store. It is a **protocol-level merchant**: the seller side of agentic commerce infrastructure, exactly the rails needed when buyers are agents (OpenAI Operator-style assistants, AutoGen fleets, procurement copilots).

---

## 2. Tech Stack & Component Roles

| Layer | Technology | Role in System |
|-------|-----------|----------------|
| Framework & API Engine | **FastAPI** (Python 3.12) | Async REST endpoints, CORS, auto-generated OpenAPI schema for agent discovery |
| Agent Protocol Layer | **FastMCP v3.4.7** | Mounts MCP server over FastAPI (`/mcp`) so external LLMs discover tools automatically |
| Payment Gateway | **razorpay SDK** | Test Mode orders (`/v1/orders`) with metadata; INR→paise conversion; signature verification |
| Guardrails & Schema | **Pydantic v2** | Typed request/response models; hard validation rules before any money moves |
| Seller Reasoning Brain | **Groq · `openai/gpt-oss-120b`** | Natural-language intent parsing, bundle selection, discount computation |
| Structured Output | **Instructor** | Forces the LLM's answer into validated `ProposedQuote` Pydantic objects (JSON mode) |
| Catalog | In-memory `MOCK_CATALOG` | SKUs, prices, margins, stock + keyword semantic search |
| Config & Secrets | **pydantic-settings** + `.env` | Type-safe credential/cap loading |
| Judge Dashboard | **Streamlit** | Live transaction inspector with guardrail config sidebar and expandable audit steps |

**Key design decision:** Groq serves an OpenAI-compatible API, so we keep one client code path (`instructor.from_openai(OpenAI(base_url=...))`) and swap providers/models purely via `.env`. Model ID must be namespaced: `openai/gpt-oss-120b` (bare `gpt-oss-120b` 404s).

---

## 3. System Architecture

```
                        ┌──────────────────────────────┐
                        │   External AI Buyer Agent    │
                        │  (shopping assistant / bot)  │
                        └──────────┬───────────────────┘
                                   │ MCP tools  OR  REST/OpenAPI
                                   ▼
┌───────────────────────────────────────────────────────────────────┐
│                     FastAPI app.main  (:8000)                     │
│   /health  /docs  /openapi.json  /api/v1/*        /mcp (FastMCP)  │
│                                                                   │
│  Tools: search_catalog · process_agentic_purchase                 │
└──────────────┬────────────────────────────────────────────────────┘
               ▼
     SellerAgentService.process_buyer_request()
               │
   ┌───────────┼─────────────────────────────┐
   ▼           ▼                             ▼
CatalogService   Groq gpt-oss-120b      SafetyGuardrailEngine
(search+stock)   via Instructor →       (Pydantic rules)
                 ProposedQuote                │ approved
   │                  │                       ▼
   │                  │              RazorpayService
   │                  │              create_order (paise)
   │                  ▼                       │
   └────────────► AgenticTransactionResult ◄──┘
                  { status, order_id,
                    amount, quote, audit_trail }
                              │
                              ▼
                  Streamlit Dashboard (:8501)
                  live negotiation inspector
```

---

## 4. Phase-by-Phase: What Was Done

### Phase 1 — Configuration & Razorpay Core ✅
| File | Delivered |
|------|-----------|
| `.env` | Credentials + global caps (`MAX_DISCOUNT_PERCENTAGE=20`, `MAX_TRANSACTION_LIMIT_INR=10000`) |
| `app/config.py` | pydantic-settings loader; type-safe access to keys/caps; extra-ignore tolerant |
| `app/core/razorpay_client.py` | `create_order()` (INR→paise via `int(round(x*100))`, metadata notes), `create_payment_link()`, HMAC `verify_payment_signature()` |

**Verified:** live Test Mode order creation (`order_TTE…` IDs), auth against real keys.

### Phase 2 — Catalog & Guardrails ✅
| File | Delivered |
|------|-----------|
| `app/services/catalog.py` | 4-SKU inventory (Keyboard ₹4499/45%, Wrist Rest ₹599/60%, Desk Mat ₹899/55%, Mouse ₹2999/40%) with keyword search + price filter |
| `app/core/guardrails.py` | 4-rule validation engine returning structured verdicts |

**Verified:** search returns correct SKUs; valid quote approved; 30% discount rejected as `EXCEEDED_MAX_DISCOUNT_CAP`.

### Phase 3 — LLM Seller Agent ✅
| File | Delivered |
|------|-----------|
| `app/services/seller_agent.py` | Full pipeline: intent → catalog context → Instructor/Groq → `ProposedQuote` → guardrails → Razorpay order. Lazy LLM init (server boots even without key). `LLM_ERROR` handled gracefully. Model/provider configurable via settings. |

**Verified:** end-to-end SUCCESS with real negotiation, upsell, and Razorpay order.

### Phase 4 — FastMCP Integration & REST Routes ✅
| File | Delivered |
|------|-----------|
| `app/main.py` | CORS-enabled FastAPI; `/health`; `/api/v1/catalog/search`; `/api/v1/agent/process-intent`; FastMCP mounted at `/mcp` exposing `search_catalog` + `process_agentic_purchase` tools; OpenAPI auto-docs |

*Fix applied during build:* fastmcp v3.x uses `mcp.http_app(path="/")` instead of legacy `sse_app()`.

### Bonus — Judge Visualization Dashboard ✅
| File | Delivered |
|------|-----------|
| `app/dashboard.py` | Streamlit live inspector: buyer prompt input, budget control, guardrail-config sidebar, success/rejection banners, expandable per-step JSON audit trail |

### Documentation ✅
`docs/PHASE1–4_IMPLEMENTATION.md` + this master doc.

---

## 5. How It Works — Request Lifecycle

```
1. INTENT_RECEIVED   Buyer agent sends {buyer_agent_id, query, max_budget_inr}
2. CATALOG_SEARCH    Keyword match on name/category/description within price cap;
                     falls back to full catalog if empty (upsell candidates preserved)
3. QUOTE_GENERATED   Catalog formatted into system prompt (SKU|price|margin|stock).
                     Groq gpt-oss-120b returns a ProposedQuote through Instructor:
                     items[], original_total, final_total, discount_pct, reasoning
4. GUARDRAIL_EVALUATION  Hard Pydantic rules run in sequence:
                     R1 global txn limit → R2 buyer budget → R3 discount cap
                     → R4 SKU existence + stock depth. First failure rejects
                     with a stable error code.
5a. RAZORPAY_ORDER_CREATED  Approved quote → POST /v1/orders in PAISE with
                     metadata (buyer id, upsell flag, discount %).
5b. …or structured rejection returned to the agent — never a raw 500.
```

Every step appends an immutable entry to `audit_trail[]` inside `AgenticTransactionResult`.

---

## 6. Worked Example — A Real Transaction

These are **actual outputs captured from the running system** during development.

### Request
```json
POST /api/v1/agent/process-intent
{
  "buyer_agent_id": "groq_smoke_test",
  "query": "silent mechanical keyboard with wrist rest under 5000 INR",
  "max_budget_inr": 5000.0
}
```

### What the seller brain did
1. Catalog search matched **SKU-KBD-01** (₹4,499) and **SKU-WST-01** (₹599).
2. LLM reasoned: *"Combined list price ₹5,098 exceeds ₹5,000 budget → apply modest bundle discount"*.
3. It produced (via Instructor, schema-enforced):

```json
{
  "items": [{"sku": "SKU-KBD-01", "quantity": 1}, {"sku": "SKU-WST-01", "quantity": 1}],
  "original_total_inr": 5098.0,
  "final_discounted_total_inr": 5000.0,
  "applied_discount_percentage": 1.92,
  "buyer_max_budget_inr": 5000.0,
  "upsell_applied": true,
  "reasoning": "Selected the silent mechanical keyboard as primary product. Added ergonomic
   wrist rest as high-margin accessory. Combined list ₹5,098 exceeds ₹5,000 budget, so a
   1.92% bundle discount was applied, bringing the total to exactly ₹5,000."
}
```

4. Guardrails: R1 ✓ (₹5,000 ≤ ₹10,000) · R2 ✓ (=budget) · R3 ✓ (1.92% ≤ 20%) · R4 ✓ (stock 15/40).
5. Razorpay responded:

```
status            : SUCCESS
razorpay_order_id : order_TTEIWwb4v4tSqq
amount            : 500000 paise (₹5,000.00)
audit_trail       : INTENT_RECEIVED → CATALOG_SEARCH → QUOTE_GENERATED
                    → GUARDRAIL_EVALUATION → RAZORPAY_ORDER_CREATED
```

**The AOV story:** buyer asked for a keyboard (~₹4,499 expected). Seller bundled a high-margin wrist rest and still closed within budget — **+11% order value** through pure machine negotiation.

### Second captured run (mouse)
`"wireless mouse under 3500 INR"` → SKU-MSE-01 @ 10% negotiated discount → **₹2,699.10** → `order_TTEV6dYt9fMy8L`.

### Rejection path demo (guardrail test)
Same quote forced to 30% discount:
```
status          : GUARDRAIL_REJECTED
rejection_code  : EXCEEDED_MAX_DISCOUNT_CAP
rejection_reason: "Discount 30.0% exceeds max threshold of 20.0%"
```
No Razorpay call was made. The buyer receives a clean, machine-readable reason.

---

## 7. Safety & Guardrails

| Rule | Check | Rejection Code |
|------|-------|----------------|
| 1 | `final_total ≤ MAX_TRANSACTION_LIMIT_INR (₹10k)` | `EXCEEDED_GLOBAL_TRANSACTION_LIMIT` |
| 2 | `final_total ≤ buyer_max_budget_inr` | `EXCEEDED_BUYER_BUDGET` |
| 3 | `discount% ≤ MAX_DISCOUNT_PERCENTAGE (20%)` | `EXCEEDED_MAX_DISCOUNT_CAP` |
| 4 | SKU exists ∧ `stock ≥ quantity` | `INVALID_SKU` / `INSUFFICIENT_STOCK` |

Additional invariants:
- **Money boundary discipline:** INR floats inside logic; paise integers only at the Razorpay edge (`int(round(inr*100))`).
- **Schema-forced generation:** the LLM cannot emit free text where `ProposedQuote` fields are required — Instructor guarantees parseable, typed quotes or raises into a handled `LLM_NEGOTIATION_ERROR`.
- **No unhandled failures:** LLM errors, Razorpay errors, and rejections all return HTTP 200 with structured `status` + codes; the dashboard renders each distinctly.

---

## 8. Audit Trail

Each transaction carries an append-only list like:

```json
[
  {"step": "INTENT_RECEIVED",       "buyer_id": "...", "query": "...", "budget": 5000.0},
  {"step": "CATALOG_SEARCH",        "matches_found": 2},
  {"step": "QUOTE_GENERATED",       "quote": { ...full ProposedQuote... }},
  {"step": "GUARDRAIL_EVALUATION",  "approved": true, "code": null},
  {"step": "RAZORPAY_ORDER_CREATED","order_id": "order_...", "amount_paise": 500000}
]
```

This satisfies Track 01's auditability bar: intent parsing, upsell rationale, guardrail execution, and payment state are all reconstructable per transaction.

---

## 9. API Reference Summary

| Interface | Endpoint / Tool | Purpose |
|-----------|-----------------|---------|
| REST | `GET /health` | Liveness + active guardrail config |
| REST | `GET /api/v1/catalog/search?query=&max_price=` | Product discovery |
| REST | `POST /api/v1/agent/process-intent` | End-to-end negotiated checkout |
| REST | `GET /openapi.json` · `/docs` | Machine/human-readable schemas |
| MCP | tool `search_catalog(query, max_price)` | Discovery for MCP-native agents |
| MCP | tool `process_agentic_purchase(buyer_agent_id, query, max_budget_inr)` | Atomic negotiate→guard→order |
| UI | Streamlit `:8501` | Judge-facing live inspector |

---

## 10. Achievements vs Track 01 Bar

| "The Bar" Requirement | Status |
|------------------------|--------|
| Machine-readable storefront (MCP + OpenAPI) | ✅ Both protocols live |
| Autonomous negotiation & upselling (AOV lift) | ✅ Margin-aware bundling demonstrated (+11% example) |
| Deterministic safety guardrails (no hallucinated money) | ✅ 4 hard rules, schema-gated LLM output |
| Append-only JSON reasoning log | ✅ Per-step audit trail in every response |
| Graceful failure (no unhandled 500s) | ✅ Structured codes incl. `PRICE_MISMATCH`-class paths (`GUARDRAIL_REJECTED`, `LLM_ERROR`, `RAZORPAY_API_ERROR`) |
| Razorpay Test Mode integration | ✅ Real orders created with metadata |
| Judge-friendly demo surface | ✅ Streamlit live inspector |

---

## 11. Running the System

```bash
cd ~/AISeller/Backend

# Terminal 1 — backend
./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — judge dashboard
./venv/bin/streamlit run app/dashboard.py --server.port 8501
```

| URL | What |
|-----|------|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/mcp | MCP agent endpoint |
| http://localhost:8501 | Dashboard |

Required `.env`: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `GROQ_API_KEY`, optional `LLM_MODEL` (default `openai/gpt-oss-120b`).

Test suites: `test_razorpay.py`, `test_phase2.py`, `test_phase3.py`, `test_phase4.py` (all passing).

---

## 12. Future Scope

### Commerce Depth
1. **Real vector search** — swap keyword matching for pgvector embeddings (Supabase) so "quiet typing board for small desks" matches semantically, not just lexically.
2. **Persistent inventory & orders DB** — move `MOCK_CATALOG` to Postgres; decrement stock atomically on order creation; add `PRICE_MISMATCH` reconciliation against quote age.
3. **Time-locked quotes** — attach TTL to `ProposedQuote`; expire stale quotes at checkout with structured `QUOTE_EXPIRED` responses; leverage Razorpay payment links with expiry.

### Negotiation Intelligence
4. **Multi-turn haggle protocol** — buyer counter-offers flow back into the LLM with conversation memory; concession ladder bounded by margin floors per SKU.
5. **Margin-aware dynamic pricing engine** — discount ceiling computed per-item from live margin (60%-margin accessory can flex more than 40%-margin hero product) instead of one global cap.
6. **A/B negotiation strategies** — log which prompt personas (bundle-first vs discount-first) yield higher AOV; dashboard toggle for demos.

### Protocol & Ecosystem
7. **AP2 / x402 alignment** — adopt emerging agentic-payments standards (mandates, verifiable credentials) so buyer agents carry signed spending mandates the gateway can verify cryptographically.
8. **Webhook completion loop** — Razorpay `payment.captured` webhook → signature verification → fulfillment event + audit closure, completing the order lifecycle.
9. **Agent identity & rate limiting** — per-`buyer_agent_id` API keys, spend velocity limits, anomaly flags in audit trail.

### Scale & Ops
10. **Async everything** — wrap Razorpay/Groq calls in async HTTP clients for concurrent agent load; background task queue for order settlement.
11. **Observability stack** — pipe audit trails to OTel/Langfuse; trace IDs linking LLM call ↔ guardrail ↔ order for judge forensics at scale.
12. **Multi-tenant gateways** — one deployment serving N merchants, each with own catalog, margins, and caps — turning the prototype into actual infrastructure.

---

## Final Notes

Everything documented here is implemented, tested, and running on real Razorpay Test Mode + Groq inference:

- ✅ 4 phases complete + bonus dashboard
- ✅ All 4 verification scripts passing
- ✅ Live orders minted: `order_TTEIWwb4v4tSqq`, `order_TTEJL5KYEew4xx`, `order_TTEV6dYt9fMy8L`
- ✅ Zero unhandled exceptions across failure paths

*Built for Razorpay Buildathon — Track 01: AI Growth & Agentic Commerce.*
