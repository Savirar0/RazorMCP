# Phase 2 Implementation: Product Catalog & Safety Guardrails

## Overview
This document summarizes the implementation of **Phase 2** of the Razorpay Agentic Seller Gateway project. Phase 2 establishes the product catalog with semantic search and the deterministic safety guardrail validation system.

---

## Files Created

### 1. `app/services/catalog.py`
**Purpose**: Product inventory management with keyword-based semantic search and margin tracking.

#### Data Model: `Product`
| Field | Type | Description |
|-------|------|-------------|
| `sku` | str | Unique stock keeping unit |
| `name` | str | Display name |
| `category` | str | Product category (Keyboards, Accessories, Mice) |
| `price_inr` | float | List price in INR |
| `margin_percentage` | float | Profit margin % (used for discount calculations) |
| `stock_quantity` | int | Available inventory |
| `description` | str | Semantic search corpus |

#### Mock Catalog (4 SKUs)
| SKU | Name | Category | Price | Margin | Stock |
|-----|------|----------|-------|--------|-------|
| SKU-KBD-01 | Tactile Silent Mechanical Keyboard V2 | Keyboards | ₹4,499 | 45% | 15 |
| SKU-WST-01 | Ergonomic Memory Foam Wrist Rest | Accessories | ₹599 | 60% | 40 |
| SKU-MAT-01 | Waterproof Desk Mat (900x400mm) | Accessories | ₹899 | 55% | 25 |
| SKU-MSE-01 | Precision Wireless Ergonomic Mouse | Mice | ₹2,999 | 40% | 8 |

#### `CatalogService` Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_by_sku()` | `(sku: str) -> Optional[Product]` | Direct SKU lookup (case-insensitive) |
| `search_catalog()` | `(query: str, max_price: float) -> List[Product]` | Keyword match on name+category+description with price filter |

**Search Logic**:
- Splits query into lowercase terms
- Matches against `name + category + description`
- Filters by `max_price` if provided
- Returns full `Product` objects for margin-aware negotiation

---

### 2. `app/core/guardrails.py`
**Purpose**: Deterministic validation engine that wraps every quote before Razorpay order creation.

#### Data Models

**`QuoteItem`**
```python
sku: str
quantity: int = Field(gt=0)
unit_price_inr: float = Field(gt=0)
```

**`ProposedQuote`**
```python
buyer_agent_id: str
items: List[QuoteItem]
original_total_inr: float
final_discounted_total_inr: float
applied_discount_percentage: float
buyer_max_budget_inr: float
upsell_applied: bool = False
reasoning: str
```

**`GuardrailValidationResult`**
```python
is_approved: bool
rejection_code: Optional[str] = None
rejection_reason: Optional[str] = None
validated_quote: Optional[ProposedQuote] = None
```

#### `SafetyGuardrailEngine.validate_quote()` — 4 Hard Rules

| Rule | Check | Rejection Code | Config Source |
|------|-------|----------------|---------------|
| 1 | `final_discounted_total_inr <= MAX_TRANSACTION_LIMIT_INR` | `EXCEEDED_GLOBAL_TRANSACTION_LIMIT` | `settings.MAX_TRANSACTION_LIMIT_INR` |
| 2 | `final_discounted_total_inr <= buyer_max_budget_inr` | `EXCEEDED_BUYER_BUDGET` | Quote field |
| 3 | `applied_discount_percentage <= MAX_DISCOUNT_PERCENTAGE` | `EXCEEDED_MAX_DISCOUNT_CAP` | `settings.MAX_DISCOUNT_PERCENTAGE` |
| 4 | SKU exists AND `stock_quantity >= quantity` | `INVALID_SKU` / `INSUFFICIENT_STOCK` | `catalog_service` |

**Execution Order**: Rules run sequentially — first failure returns immediately.

---

### 3. `test_phase2.py` (Project Root)
**Purpose**: Verification script for catalog search and guardrail validation.

**Test Cases**:
1. **Catalog Search** — "keyboard" under ₹5,000 → returns Keyboard + Wrist Rest
2. **Valid Quote** — Bundle with 5.88% discount, under budget → **APPROVED**
3. **Discount Violation** — Same quote with 30% discount → **REJECTED** (`EXCEEDED_MAX_DISCOUNT_CAP`)

---

## Running the Test

```bash
cd /home/xenzi/AISeller/Backend
./venv/bin/python test_phase2.py
```

**Expected Output**:
```
--- 1. Testing Catalog Search ---
Found 2 matching products:
 - SKU-KBD-01: Tactile Silent Mechanical Keyboard V2 @ ₹4499.0
 - SKU-WST-01: Ergonomic Memory Foam Wrist Rest @ ₹599.0

--- 2. Testing Valid Quote Approval ---
Approved: True

--- 3. Testing Discount Cap Violation ---
Approved: False | Code: EXCEEDED_MAX_DISCOUNT_CAP
```

---

## Architecture Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Mock inventory with margins | ✅ | `MOCK_CATALOG` dict with `margin_percentage` |
| Semantic keyword search | ✅ | `search_catalog()` on name+category+description |
| Price filter support | ✅ | `max_price` parameter |
| Pydantic validation schemas | ✅ | `QuoteItem`, `ProposedQuote`, `GuardrailValidationResult` |
| Global transaction limit | ✅ | Rule 1 uses `settings.MAX_TRANSACTION_LIMIT_INR` |
| Buyer budget enforcement | ✅ | Rule 2 uses quote's `buyer_max_budget_inr` |
| Discount cap enforcement | ✅ | Rule 3 uses `settings.MAX_DISCOUNT_PERCENTAGE` |
| Inventory verification | ✅ | Rule 4 checks `catalog_service.get_by_sku()` |
| Structured rejection codes | ✅ | `rejection_code` + `rejection_reason` |
| No unhandled exceptions | ✅ | All paths return `GuardrailValidationResult` |

---

## Integration Points

| Component | Consumes | Produces |
|-----------|----------|----------|
| `seller_agent.py` (Phase 3) | `catalog_service.search_catalog()` | `ProposedQuote` for validation |
| `seller_agent.py` (Phase 3) | `guardrail_engine.validate_quote()` | `GuardrailValidationResult` |
| `razorpay_client.py` (Phase 1) | Validated quote's `final_discounted_total_inr` | Razorpay Order in paise |

---

## Next Steps (Phase 3)

1. **`app/services/seller_agent.py`** — LLM-powered negotiation engine using Instructor + OpenAI
   - Parse buyer intent → search catalog → calculate bundle discounts → produce `ProposedQuote`
   - Margin-aware cross-sell logic (suggest accessories within budget)
   - Structured output via Instructor → Pydantic validation → Guardrails

---

## Dependencies Used

From `requirements.txt`:
- `pydantic>=2.6.0` — Data models & validation
- `pydantic-settings>=2.2.0` — Config access in guardrails

---

*Generated as part of Razorpay Buildathon — Track 01 (AI Growth & Agentic Commerce)*
