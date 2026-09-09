from app.services.seller_agent import seller_agent_service, BuyerIntentRequest


def test_seller_agent_pipeline():
    print("--- Testing Phase 3: AI Seller Agent Pipeline ---")

    request = BuyerIntentRequest(
        buyer_agent_id="buyer_bot_991",
        query="I need a silent mechanical keyboard with a wrist rest under 5000 INR",
        max_budget_inr=5000.00
    )

    result = seller_agent_service.process_buyer_request(request)

    print(f"\nFinal Transaction Status: {result.status}")
    print(f"Razorpay Order ID: {result.razorpay_order_id}")
    print(f"Total Amount Charged: ₹{result.amount_paid_inr}")

    print("\nAudit Trail Logs:")
    for log in result.audit_trail:
        print(f"  [{log['step']}] -> {log}")


if __name__ == "__main__":
    test_seller_agent_pipeline()
