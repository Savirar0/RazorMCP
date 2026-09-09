from app.services.catalog import catalog_service
from app.core.guardrails import guardrail_engine, ProposedQuote, QuoteItem


def test_catalog_and_guardrails():
    print("--- 1. Testing Catalog Search ---")
    results = catalog_service.search_catalog("keyboard", max_price=5000.0)
    print(f"Found {len(results)} matching products:")
    for item in results:
        print(f" - {item.sku}: {item.name} @ ₹{item.price_inr}")

    print("\n--- 2. Testing Valid Quote Approval ---")
    valid_quote = ProposedQuote(
        buyer_agent_id="agent_007",
        items=[
            QuoteItem(sku="SKU-KBD-01", quantity=1, unit_price_inr=4499.00),
            QuoteItem(sku="SKU-WST-01", quantity=1, unit_price_inr=599.00)
        ],
        original_total_inr=5098.00,
        final_discounted_total_inr=4798.00,  # ~5.88% discount
        applied_discount_percentage=5.88,
        buyer_max_budget_inr=5000.00,
        upsell_applied=True,
        reasoning="Bundled wrist rest with ₹300 discount within budget."
    )
    result = guardrail_engine.validate_quote(valid_quote)
    print(f"Approved: {result.is_approved}")

    print("\n--- 3. Testing Discount Cap Violation ---")
    invalid_quote = valid_quote.model_copy()
    invalid_quote.applied_discount_percentage = 30.0  # Exceeds 20% limit
    result_discount_fail = guardrail_engine.validate_quote(invalid_quote)
    print(f"Approved: {result_discount_fail.is_approved} | Code: {result_discount_fail.rejection_code}")


if __name__ == "__main__":
    test_catalog_and_guardrails()
