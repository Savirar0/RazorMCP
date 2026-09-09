from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from app.config import settings
from app.services.catalog import catalog_service


class QuoteItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0, description="Quantity must be greater than 0")
    unit_price_inr: float = Field(gt=0)


class ProposedQuote(BaseModel):
    buyer_agent_id: str
    items: List[QuoteItem]
    original_total_inr: float
    final_discounted_total_inr: float
    applied_discount_percentage: float
    buyer_max_budget_inr: float
    upsell_applied: bool = False
    reasoning: str


class GuardrailValidationResult(BaseModel):
    is_approved: bool
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None
    validated_quote: Optional[ProposedQuote] = None


class SafetyGuardrailEngine:
    @staticmethod
    def validate_quote(quote: ProposedQuote) -> GuardrailValidationResult:
        # Rule 1: Single Transaction Absolute Limit Check
        if quote.final_discounted_total_inr > settings.MAX_TRANSACTION_LIMIT_INR:
            return GuardrailValidationResult(
                is_approved=False,
                rejection_code="EXCEEDED_GLOBAL_TRANSACTION_LIMIT",
                rejection_reason=f"Quote total ₹{quote.final_discounted_total_inr:.2f} exceeds global spend limit of ₹{settings.MAX_TRANSACTION_LIMIT_INR:.2f}"
            )

        # Rule 2: Buyer's Expressed Budget Check
        if quote.final_discounted_total_inr > quote.buyer_max_budget_inr:
            return GuardrailValidationResult(
                is_approved=False,
                rejection_code="EXCEEDED_BUYER_BUDGET",
                rejection_reason=f"Quote total ₹{quote.final_discounted_total_inr:.2f} exceeds buyer budget cap of ₹{quote.buyer_max_budget_inr:.2f}"
            )

        # Rule 3: Maximum Discount Cap Check
        if quote.applied_discount_percentage > settings.MAX_DISCOUNT_PERCENTAGE:
            return GuardrailValidationResult(
                is_approved=False,
                rejection_code="EXCEEDED_MAX_DISCOUNT_CAP",
                rejection_reason=f"Discount {quote.applied_discount_percentage:.1f}% exceeds max threshold of {settings.MAX_DISCOUNT_PERCENTAGE:.1f}%"
            )

        # Rule 4: Inventory Stock Level Verification
        for item in quote.items:
            product = catalog_service.get_by_sku(item.sku)
            if not product:
                return GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="INVALID_SKU",
                    rejection_reason=f"SKU {item.sku} does not exist in store catalog."
                )
            if product.stock_quantity < item.quantity:
                return GuardrailValidationResult(
                    is_approved=False,
                    rejection_code="INSUFFICIENT_STOCK",
                    rejection_reason=f"Requested quantity {item.quantity} for {item.sku} exceeds available stock ({product.stock_quantity})."
                )

        return GuardrailValidationResult(
            is_approved=True,
            validated_quote=quote
        )


guardrail_engine = SafetyGuardrailEngine()
