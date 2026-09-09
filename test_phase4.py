from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_pipeline():
    print("--- 1. Testing Health Check Endpoint ---")
    response = client.get("/health")
    print(f"Health Status Code: {response.status_code}")
    print(f"Health Response: {response.json()}")
    assert response.status_code == 200

    print("\n--- 2. Testing REST Catalog Search ---")
    response = client.get("/api/v1/catalog/search?query=keyboard&max_price=5000")
    print(f"Search Status Code: {response.status_code}")
    items = response.json()
    print(f"Returned Items ({len(items)}): {[item['sku'] for item in items]}")
    assert response.status_code == 200

    print("\n--- 3. Testing End-to-End Agent Process Intent API ---")
    payload = {
        "buyer_agent_id": "fastapi_test_bot_01",
        "query": "Silent mechanical keyboard under 5000",
        "max_budget_inr": 5000.00
    }
    response = client.post("/api/v1/agent/process-intent", json=payload)
    print(f"Process Intent Status Code: {response.status_code}")
    data = response.json()
    print(f"Transaction Status: {data['status']}")
    print(f"Razorpay Order ID: {data.get('razorpay_order_id')}")
    print(f"Audit Log Steps: {[step['step'] for step in data['audit_trail']]}")
    assert response.status_code == 200


if __name__ == "__main__":
    test_api_pipeline()
