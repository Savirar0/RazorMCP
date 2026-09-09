# Phase 1 Implementation: Configuration & Razorpay Core

## Overview
This document summarizes the implementation of **Phase 1** of the Razorpay Agentic Seller Gateway project. Phase 1 establishes environment variable management and Razorpay API integration.

---

## Files Created/Modified

### 1. `.env` (Project Root)
**Purpose**: Environment variable configuration for sensitive credentials and application settings.

```env
RAZORPAY_KEY_ID="rzp_test_YOUR_KEY_HERE"
RAZORPAY_KEY_SECRET="YOUR_SECRET_HERE"
MAX_DISCOUNT_PERCENTAGE=20.0
MAX_TRANSACTION_LIMIT_INR=10000.00
ENVIRONMENT="development"
```

**Variables**:
| Variable | Description | Default |
|----------|-------------|---------|
| `RAZORPAY_KEY_ID` | Razorpay Test Mode Key ID (from Dashboard) | placeholder |
| `RAZORPAY_KEY_SECRET` | Razorpay Test Mode Key Secret | placeholder |
| `MAX_DISCOUNT_PERCENTAGE` | Maximum allowed discount percentage for guardrails | 20.0 |
| `MAX_TRANSACTION_LIMIT_INR` | Maximum transaction amount in INR | 10000.00 |
| `ENVIRONMENT` | Application environment | development |

> ⚠️ **Action Required**: Replace placeholder values with actual Razorpay Test credentials from [Razorpay Dashboard](https://dashboard.razorpay.com/app/keys)

---

### 2. `app/config.py`
**Purpose**: Pydantic Settings configuration manager for type-safe environment variable loading.

**Key Features**:
- Uses `pydantic-settings` v2 with `BaseSettings`
- Automatic `.env` file loading with UTF-8 encoding
- Type validation and default values
- `extra="ignore"` to prevent unknown config errors

**Code**:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    MAX_DISCOUNT_PERCENTAGE: float = 20.0
    MAX_TRANSACTION_LIMIT_INR: float = 10000.0
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
```

**Usage**:
```python
from app.config import settings

print(settings.RAZORPAY_KEY_ID)
print(settings.MAX_TRANSACTION_LIMIT_INR)
```

---

### 3. `app/core/razorpay_client.py`
**Purpose**: Razorpay SDK wrapper handling INR↔Paise conversion and Test Mode API calls.

**Class: `RazorpayService`**

#### Methods:

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `create_order()` | Creates a Razorpay Order | `amount_inr: float`, `receipt: str`, `notes: dict` | Order dict with `id`, `amount` (paise), `status` |
| `create_payment_link()` | Generates time-locked payment link | `amount_inr: float`, `description: str`, `customer_info: dict`, `notes: dict` | Payment link dict |
| `verify_payment_signature()` | Validates HMAC signature | `params: dict` | `bool` |

**Key Implementation Details**:
- **Paise Conversion**: `int(round(amount_inr * 100))` — ensures integer paise for Razorpay API
- **Currency**: Hardcoded to `INR`
- **Payment Links**: Configured for agent transactions (`accept_partial=False`, notifications disabled)
- **Error Handling**: Signature verification catches `razorpay.errors.SignatureVerificationError`

**Code**:
```python
import razorpay
from typing import Dict, Any, Optional
from app.config import settings


class RazorpayService:
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def create_order(self, amount_inr: float, receipt: str, notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        amount_in_paise = int(round(amount_inr * 100))
        payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes or {}
        }
        return self.client.order.create(data=payload)

    def create_payment_link(self, amount_inr: float, description: str, customer_info: Dict[str, Any], notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        amount_in_paise = int(round(amount_inr * 100))
        payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "customer": customer_info,
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": notes or {}
        }
        return self.client.payment_link.create(data=payload)

    def verify_payment_signature(self, params: Dict[str, str]) -> bool:
        try:
            self.client.utility.verify_payment_signature(params)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False


razorpay_service = RazorpayService()
```

---

### 4. `test_razorpay.py` (Project Root)
**Purpose**: Verification script to test Razorpay integration.

**Code**:
```python
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
```

**Expected Output** (with valid credentials):
```
Success! Razorpay Order Created:
Order ID: order_XXXXXXXXXXXXXX
Amount (Paise): 149900
Status: created
```

---

## Running the Test

```bash
cd /home/xenzi/AISeller/Backend
./venv/bin/python test_razorpay.py
```

---

## Architecture Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Pydantic Settings for config | ✅ | `app/config.py` |
| Razorpay credentials from `.env` | ✅ | `BaseSettings` with `env_file` |
| INR → Paise conversion | ✅ | `int(round(amount_inr * 100))` |
| Order creation with metadata | ✅ | `notes` parameter in `create_order()` |
| Payment link for agent transactions | ✅ | `create_payment_link()` with `accept_partial=False` |
| Signature verification | ✅ | `verify_payment_signature()` |
| Async-ready (sync wrapper) | ✅ | Ready for async FastAPI routes |

---

## Next Steps (Phase 2)

1. **`app/services/catalog.py`** — Product catalog with mock inventory, semantic search
2. **`app/core/guardrails.py`** — Pydantic validation schemas for spend limits, discount caps

---

## Dependencies Used

From `requirements.txt`:
- `pydantic>=2.6.0`
- `pydantic-settings>=2.2.0`
- `razorpay>=1.4.1`
- `python-dotenv>=1.0.1`

---

*Generated as part of Razorpay Buildathon — Track 01 (AI Growth & Agentic Commerce)*
