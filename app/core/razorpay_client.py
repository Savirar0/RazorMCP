import razorpay
from typing import Dict, Any, Optional
from app.config import settings


class RazorpayService:
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def create_order(
        self,
        amount_inr: float,
        receipt: str,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates a Razorpay Order object.
        Converts INR float input to integer paise (1 INR = 100 Paise).
        """
        amount_in_paise = int(round(amount_inr * 100))
        payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes or {}
        }
        return self.client.order.create(data=payload)

    def create_payment_link(
        self,
        amount_inr: float,
        description: str,
        customer_info: Dict[str, Any],
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates a time-locked Razorpay Payment Link for delegated agent transactions.
        """
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
        """
        Validates HMAC signature of incoming payment confirmation payloads.
        """
        try:
            self.client.utility.verify_payment_signature(params)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False


razorpay_service = RazorpayService()
