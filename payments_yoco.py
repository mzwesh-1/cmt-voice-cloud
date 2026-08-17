"""
payments_yoco.py — Yoco payment integration.

Yoco's Online Payments API flow:
    1. create_checkout()  -> returns a redirectUrl. Send the user there to pay.
    2. User pays on Yoco's hosted checkout page.
    3. Yoco redirects back to your successUrl with ?checkoutId=xxx in the URL.
    4. check_checkout_status(checkout_id) -> confirm it's actually "completed"
       before activating the subscription (never trust the redirect alone).

Get your Yoco Secret Key (test or live) at: https://portal.yoco.com/
Set it as an environment variable:
    setx CMT_YOCO_SECRET_KEY "sk_test_xxxxxxxx"   (Windows)
"""

import os
import requests

YOCO_API_BASE = "https://payments.yoco.com/api"

PRO_PLAN_PRICE_ZAR = 99.00   # R99/month — adjust as you like
PRO_PLAN_DAYS = 30


def _get_secret_key() -> str:
    key = os.environ.get("CMT_YOCO_SECRET_KEY")
    if not key:
        raise EnvironmentError(
            "\n\nNo Yoco secret key found!\n"
            "Get one at https://portal.yoco.com/ (use the TEST key while developing)\n"
            "Then set it: setx CMT_YOCO_SECRET_KEY \"sk_test_xxxxxxxx\"\n"
        )
    return key


def create_checkout(email: str, success_url: str, cancel_url: str, failure_url: str = None) -> dict:
    """
    Create a Yoco hosted checkout session for the Pro plan.

    Returns a dict with 'id' (checkout id) and 'redirectUrl' — send the
    user to redirectUrl to complete payment.
    """
    key = _get_secret_key()

    amount_cents = int(PRO_PLAN_PRICE_ZAR * 100)  # Yoco expects cents

    payload = {
        "amount": amount_cents,
        "currency": "ZAR",
        "successUrl": success_url,
        "cancelUrl": cancel_url,
        "failureUrl": failure_url or cancel_url,
        "metadata": {"email": email, "plan": "Pro"},
    }

    resp = requests.post(
        f"{YOCO_API_BASE}/checkouts",
        json=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Yoco checkout creation failed: {resp.status_code} {resp.text}")

    return resp.json()


def check_checkout_status(checkout_id: str) -> str:
    """
    Confirm the real status of a checkout from Yoco's servers.
    Returns one of: 'created', 'processing', 'completed', 'failed', 'cancelled'.

    ALWAYS call this before activating a subscription — never trust the
    browser redirect alone, since URLs can be faked or replayed.
    """
    key = _get_secret_key()

    resp = requests.get(
        f"{YOCO_API_BASE}/checkouts/{checkout_id}",
        headers={"Authorization": f"Bearer {key}"},
        timeout=15,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Could not check Yoco status: {resp.status_code} {resp.text}")

    data = resp.json()
    return data.get("status", "unknown")
