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
    max_budget_inr: float = Field(gt=0)


class AgenticTransactionResult(BaseModel):
    status: str
    buyer_agent_id: str
    razorpay_order_id: Optional[str] = None
    amount_paid_inr: Optional[float] = None
    applied_quote: Optional[ProposedQuote] = None
    validation_details: GuardrailValidationResult
    audit_trail: List[Dict[str, Any]]


class SellerAgentService:
    def __init__(self):
        self._client = None

    @property
    def llm_client(self):
        """Lazily build the Instructor client for Groq's OpenAI-compatible API."""
        if self._client is None:
            groq_client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.LLM_BASE_URL)
            self._client = instructor.from_openai(groq_client, mode=instructor.Mode.JSON)
        return self._client

    def process_buyer_request(self, request: BuyerIntentRequest) -> AgenticTransactionResult:
        audit_trail: List[Dict[str, Any]] = [
            {"step": "INTENT_RECEIVED", "buyer_id": request.buyer_agent_id, "query": request.query, "budget": request.max_budget_inr}
        ]
        candidate_products: List[Product] = catalog_service.search_catalog(request.query, request.max_budget_inr)
        if not candidate_products:
            candidate_products = list(catalog_service.search_catalog("").values())
        audit_trail.append({"step": "CATALOG_SEARCH", "matches_found": len(candidate_products)})

        # A public portfolio must not expose paid LLM capacity or payment
        # credentials to anonymous visitors.
        if settings.DEMO_MODE:
            return self._process_demo_request(request, candidate_products, audit_trail)

        catalog_context = [
            f"SKU: {product.sku} | Name: {product.name} | Price: ₹{product.price_inr} | Margin: {product.margin_percentage}% | Stock: {product.stock_quantity}"
            for product in candidate_products
        ]
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

        try:
            proposed_quote: ProposedQuote = self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                response_model=ProposedQuote,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Buyer Request: '{request.query}'. Maximum Budget: ₹{request.max_budget_inr}"},
                ],
            )
        except Exception as error:
            audit_trail.append({"step": "LLM_ERROR", "error": str(error)})
            return AgenticTransactionResult(
                status="ERROR",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="LLM_NEGOTIATION_ERROR",
                    rejection_reason=str(error),
                ),
                audit_trail=audit_trail,
            )

        audit_trail.append({"step": "QUOTE_GENERATED", "quote": proposed_quote.model_dump()})
        validation_result = guardrail_engine.validate_quote(proposed_quote)
        audit_trail.append({"step": "GUARDRAIL_EVALUATION", "approved": validation_result.is_approved, "code": validation_result.rejection_code})
        if not validation_result.is_approved:
            return AgenticTransactionResult(
                status="GUARDRAIL_REJECTED",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=validation_result,
                audit_trail=audit_trail,
            )

        try:
            razorpay_order = razorpay_service.create_order(
                amount_inr=proposed_quote.final_discounted_total_inr,
                receipt=f"receipt_{request.buyer_agent_id[:8]}",
                notes={
                    "buyer_agent_id": request.buyer_agent_id,
                    "upsell_applied": str(proposed_quote.upsell_applied),
                    "applied_discount_pct": str(proposed_quote.applied_discount_percentage),
                },
            )
            audit_trail.append({"step": "RAZORPAY_ORDER_CREATED", "order_id": razorpay_order["id"], "amount_paise": razorpay_order["amount"]})
            return AgenticTransactionResult(
                status="SUCCESS",
                buyer_agent_id=request.buyer_agent_id,
                razorpay_order_id=razorpay_order["id"],
                amount_paid_inr=proposed_quote.final_discounted_total_inr,
                applied_quote=proposed_quote,
                validation_details=validation_result,
                audit_trail=audit_trail,
            )
        except Exception as error:
            audit_trail.append({"step": "RAZORPAY_ERROR", "error": str(error)})
            return AgenticTransactionResult(
                status="ERROR",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="RAZORPAY_API_ERROR",
                    rejection_reason=str(error),
                ),
                audit_trail=audit_trail,
            )

    @staticmethod
    def _process_demo_request(
        request: BuyerIntentRequest,
        candidate_products: List[Product],
        audit_trail: List[Dict[str, Any]],
    ) -> AgenticTransactionResult:
        """Return a deterministic, guardrail-checked simulated purchase."""
        spend_limit = min(request.max_budget_inr, settings.MAX_TRANSACTION_LIMIT_INR)
        eligible_products = [product for product in candidate_products if product.price_inr <= spend_limit]
        if not eligible_products:
            reason = "No catalog item can be offered within the supplied budget and merchant transaction limit."
            audit_trail.append({"step": "DEMO_QUOTE_UNAVAILABLE", "reason": reason})
            return AgenticTransactionResult(
                status="ERROR",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="NO_ELIGIBLE_PRODUCT",
                    rejection_reason=reason,
                ),
                audit_trail=audit_trail,
            )

        selected_products = [eligible_products[0]]
        for product in eligible_products[1:]:
            proposed_total = sum(item.price_inr for item in selected_products) + product.price_inr
            required_discount = max(0.0, (1 - (spend_limit / proposed_total)) * 100)
            if required_discount <= settings.MAX_DISCOUNT_PERCENTAGE:
                selected_products.append(product)
                break

        original_total = sum(product.price_inr for product in selected_products)
        final_total = min(original_total, spend_limit)
        discount_percentage = round(((original_total - final_total) / original_total) * 100, 2)
        proposed_quote = ProposedQuote(
            buyer_agent_id=request.buyer_agent_id,
            items=[QuoteItem(sku=product.sku, quantity=1, unit_price_inr=product.price_inr) for product in selected_products],
            original_total_inr=original_total,
            final_discounted_total_inr=final_total,
            applied_discount_percentage=discount_percentage,
            buyer_max_budget_inr=request.max_budget_inr,
            upsell_applied=len(selected_products) > 1,
            reasoning="Portfolio demo quote generated locally; no external model or payment provider was called.",
        )
        audit_trail.append({"step": "QUOTE_GENERATED", "source": "DEMO_MODE", "quote": proposed_quote.model_dump()})
        validation_result = guardrail_engine.validate_quote(proposed_quote)
        audit_trail.append({"step": "GUARDRAIL_EVALUATION", "approved": validation_result.is_approved, "code": validation_result.rejection_code})
        if not validation_result.is_approved:
            return AgenticTransactionResult(
                status="GUARDRAIL_REJECTED",
                buyer_agent_id=request.buyer_agent_id,
                validation_details=validation_result,
                audit_trail=audit_trail,
            )

        simulated_order_id = f"demo_order_{request.buyer_agent_id[:12]}"
        audit_trail.append({"step": "DEMO_ORDER_SIMULATED", "order_id": simulated_order_id, "amount_paise": int(round(final_total * 100))})
        return AgenticTransactionResult(
            status="SUCCESS",
            buyer_agent_id=request.buyer_agent_id,
            razorpay_order_id=simulated_order_id,
            amount_paid_inr=final_total,
            applied_quote=proposed_quote,
            validation_details=validation_result,
            audit_trail=audit_trail,
        )


seller_agent_service = SellerAgentService()
