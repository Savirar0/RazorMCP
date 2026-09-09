import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from app.config import settings
from app.services.catalog import catalog_service, Product
from app.core.guardrails import guardrail_engine, ProposedQuote, QuoteItem, GuardrailValidationResult
from app.core.razorpay_client import razorpay_service


class BuyerIntentRequest(BaseModel):
    buyer_agent_id: str
    query: str
    max_budget_inr: float


class AgenticTransactionResult(BaseModel):
    status: str  # "SUCCESS", "GUARDRAIL_REJECTED", "ERROR"
    buyer_agent_id: str
    razorpay_order_id: Optional[str] = None
    amount_paid_inr: Optional[float] = None
    applied_quote: Optional[ProposedQuote] = None
    validation_details: GuardrailValidationResult
    audit_trail: List[Dict[str, Any]]


class SellerAgentService:
    def __init__(self):
        self._client = None  # Lazily initialized to avoid import-time credential errors

    @property
    def llm_client(self):
        """Lazily initializes the Instructor-patched client pointed at Groq (OpenAI-compatible API)."""
        if self._client is None:
            groq_client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
            # Mode.JSON is the most reliable structured-output mode for
            # third-party OpenAI-compatible providers like Groq.
            self._client = instructor.from_openai(groq_client, mode=instructor.Mode.JSON)
        return self._client

    def process_buyer_request(self, request: BuyerIntentRequest) -> AgenticTransactionResult:
        audit_trail: List[Dict[str, Any]] = []
        audit_trail.append({"step": "INTENT_RECEIVED", "buyer_id": request.buyer_agent_id, "query": request.query, "budget": request.max_budget_inr})

        # 1. Search catalog for candidate items matching query
        candidate_products: List[Product] = catalog_service.search_catalog(
            query=request.query,
            max_price=request.max_budget_inr
        )

        # If no items found within budget, include all accessories for possible matching
        if not candidate_products:
            candidate_products = list(catalog_service.search_catalog("").values())

        catalog_context = [
            f"SKU: {p.sku} | Name: {p.name} | Price: ₹{p.price_inr} | Margin: {p.margin_percentage}% | Stock: {p.stock_quantity}"
            for p in candidate_products
        ]
        audit_trail.append({"step": "CATALOG_SEARCH", "matches_found": len(candidate_products)})

        # 2. Construct LLM system prompt for Instructor
        system_prompt = f"""You are an autonomous AI Seller representing a merchant store. Your goal is to fulfill the AI Buyer's request while maximizing order value (AOV) through relevant cross-sells or bundles, without exceeding their budget.

MERCHANT RULES:
- Maximum allowed discount percentage: {settings.MAX_DISCOUNT_PERCENTAGE}%
- Buyer Maximum Budget: ₹{request.max_budget_inr}

AVAILABLE CATALOG ITEMS:
{chr(10).join(catalog_context)}

INSTRUCTIONS:
1. Select the primary product matching the buyer's query.
2. If budget allows, add a complementary high-margin accessory (upsell).
3. Apply a modest bundle discount (under {settings.MAX_DISCOUNT_PERCENTAGE}%) to keep the total within budget.
4. Calculate 'original_total_inr' (sum of list prices) and 'final_discounted_total_inr'.
5. Set 'applied_discount_percentage' accurately."""

        # 3. Call OpenAI using Instructor for structured Pydantic output
        try:
            proposed_quote: ProposedQuote = self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                response_model=ProposedQuote,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Buyer Request: '{request.query}'. Maximum Budget: ₹{request.max_budget_inr}"}
                ]
            )
        except Exception as e:
            audit_trail.append({"step": "LLM_ERROR", "error": str(e)})
            return AgenticTransactionResult(
                status="ERROR",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="LLM_NEGOTIATION_ERROR",
                    rejection_reason=str(e)
                ),
                audit_trail=audit_trail
            )
        audit_trail.append({"step": "QUOTE_GENERATED", "quote": proposed_quote.model_dump()})

        # 4. Pass generated quote through Safety Guardrail Engine
        validation_result: GuardrailValidationResult = guardrail_engine.validate_quote(proposed_quote)
        audit_trail.append({"step": "GUARDRAIL_EVALUATION", "approved": validation_result.is_approved, "code": validation_result.rejection_code})

        if not validation_result.is_approved:
            return AgenticTransactionResult(
                status="GUARDRAIL_REJECTED",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=validation_result,
                audit_trail=audit_trail
            )

        # 5. Execute Razorpay Order creation for approved quote
        try:
            rzp_order = razorpay_service.create_order(
                amount_inr=proposed_quote.final_discounted_total_inr,
                receipt=f"receipt_{request.buyer_agent_id[:8]}",
                notes={
                    "buyer_agent_id": request.buyer_agent_id,
                    "upsell_applied": str(proposed_quote.upsell_applied),
                    "applied_discount_pct": str(proposed_quote.applied_discount_percentage)
                }
            )
            audit_trail.append({"step": "RAZORPAY_ORDER_CREATED", "order_id": rzp_order["id"], "amount_paise": rzp_order["amount"]})

            return AgenticTransactionResult(
                status="SUCCESS",
                buyer_agent_id=request.buyer_agent_id,
                razorpay_order_id=rzp_order["id"],
                amount_paid_inr=proposed_quote.final_discounted_total_inr,
                applied_quote=proposed_quote,
                validation_details=validation_result,
                audit_trail=audit_trail
            )
        except Exception as e:
            audit_trail.append({"step": "RAZORPAY_ERROR", "error": str(e)})
            return AgenticTransactionResult(
                status="ERROR",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="RAZORPAY_API_ERROR",
                    rejection_reason=str(e)
                ),
                audit_trail=audit_trail
            )


seller_agent_service = SellerAgentService()
