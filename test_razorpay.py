from app.core.razorpay_client import razorpay_service

if __name__ == "__main__":
    try:
        order = razorpay_service.create_order(
            amount_inr=1499.00,
            receipt="test_receipt_001",
            notes={"agent_id": "buyer_agent_alpha", "test_mode": "true"}
        )
        print("Success! Razorpay Order Created:")
        print(f"Order ID: {order['id']}")
        print(f"Amount (Paise): {order['amount']}")
        print(f"Status: {order['status']}")
    except Exception as e:
        print(f"Razorpay Client Test Failed: {e}")
