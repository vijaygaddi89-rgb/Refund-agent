 
"""
tools.py
--------
Three tools the LangGraph agent can call:

  1. lookup_customer   → find customer + order in CRM
  2. validate_policy   → check refund eligibility against policy.md
  3. process_refund    → approve / deny / escalate and return final decision

Each tool is a plain Python function decorated with @tool from LangChain.
LangGraph will bind these to the Claude model so it can call them by name.
"""

from datetime import date, datetime
from typing import Optional
from langchain_core.tools import tool
from database import get_customer_by_id, get_customer_by_email, get_order_by_id, get_policy_text

# ── Tier → allowed return window in days ────────────────────────────────────
TIER_WINDOWS = {
    "standard": 30,
    "premium": 45,
    "vip": 60,
}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: lookup_customer
# ─────────────────────────────────────────────────────────────────────────────

@tool
def lookup_customer(
    customer_id: Optional[str] = None,
    email: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict:
    """
    Look up a customer and their order from the CRM database.

    Provide at least ONE of: customer_id, email, or order_id.
    Returns customer profile and the relevant order details.

    Args:
        customer_id: e.g. "CUST001"
        email: e.g. "james.carter@email.com"
        order_id: e.g. "ORD-2026-001"
    """
    customer = None
    order = None

    # Try order_id first — most specific
    if order_id:
        result = get_order_by_id(order_id)
        if result:
            customer = result["customer"]
            order = result["order"]

    # Fall back to customer_id
    if not customer and customer_id:
        customer = get_customer_by_id(customer_id)

    # Fall back to email
    if not customer and email:
        customer = get_customer_by_email(email)

    if not customer:
        return {
            "found": False,
            "error": "Customer not found. Please verify the customer ID, email, or order ID.",
        }

    # If we found customer but not order yet, take their first (and only) order
    if not order and customer.get("orders"):
        order = customer["orders"][0]

    return {
        "found": True,
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "email": customer["email"],
        "tier": customer["tier"],
        "phone": customer["phone"],
        "joined": customer["joined"],
        "order": order,  # full order dict or None
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: validate_policy
# ─────────────────────────────────────────────────────────────────────────────

@tool
def validate_policy(
    customer_id: str,
    order_id: str,
    refund_reason: str,
) -> dict:
    """
    Validate whether a refund request is eligible according to ShopEasy's refund policy.

    Checks (in order):
      1. Non-refundable category (digital, sale items) — hard stop
      2. Return window based on customer tier
      3. Refund reason validity

    Args:
        customer_id: The customer's ID (e.g. "CUST001")
        order_id: The order being disputed (e.g. "ORD-2026-001")
        refund_reason: The reason the customer gave for requesting a refund
    """
    # ── Fetch data ────────────────────────────────────────────────────────────
    customer = get_customer_by_id(customer_id)
    if not customer:
        return {"eligible": False, "reason": "Customer not found in CRM.", "rule_triggered": "NO_CUSTOMER"}

    order = None
    for o in customer.get("orders", []):
        if o["order_id"] == order_id:
            order = o
            break

    if not order:
        return {"eligible": False, "reason": f"Order {order_id} not found for this customer.", "rule_triggered": "NO_ORDER"}

    # ── Rule 1: Digital product check ─────────────────────────────────────────
    if order.get("is_digital"):
        return {
            "eligible": False,
            "reason": (
                f"'{order['product']}' is a digital product that has been activated. "
                "Per Section 2 of the refund policy, digital goods are strictly non-refundable once activated."
            ),
            "rule_triggered": "DIGITAL_PRODUCT",
            "days_since_purchase": None,
            "window_allowed": None,
        }

    # ── Rule 2: Sale / clearance item check ───────────────────────────────────
    if order.get("is_sale_item"):
        return {
            "eligible": False,
            "reason": (
                f"'{order['product']}' was purchased as a clearance/sale item. "
                "Per Section 2 of the refund policy, final sale items are non-refundable."
            ),
            "rule_triggered": "SALE_ITEM",
            "days_since_purchase": None,
            "window_allowed": None,
        }

    # ── Rule 3: Return window check ───────────────────────────────────────────
    tier = customer.get("tier", "standard")
    window = TIER_WINDOWS.get(tier, 30)

    purchase_date = date.fromisoformat(order["purchase_date"])
    today = date.today()
    days_since = (today - purchase_date).days

    if days_since > window:
        return {
            "eligible": False,
            "reason": (
                f"The purchase was made {days_since} days ago. "
                f"As a {tier} tier customer, the return window is {window} days. "
                "This request falls outside the eligible return period."
            ),
            "rule_triggered": "OUTSIDE_WINDOW",
            "days_since_purchase": days_since,
            "window_allowed": window,
        }

    # ── Rule 4: Refund reason check ───────────────────────────────────────────
    valid_reasons = [
        "damaged", "defective", "wrong item", "not as described",
        "never arrived", "change of mind", "not received", "broken",
        "faulty", "incorrect item", "missing", "stopped working",
    ]

    reason_lower = refund_reason.lower()
    reason_valid = any(r in reason_lower for r in valid_reasons)

    if not reason_valid:
        return {
            "eligible": False,
            "reason": (
                f"The provided reason '{refund_reason}' does not match any approved refund categories. "
                "Valid reasons include: product damaged/defective, wrong item shipped, not as described, "
                "item never arrived, or change of mind (within 7 days)."
            ),
            "rule_triggered": "INVALID_REASON",
            "days_since_purchase": days_since,
            "window_allowed": window,
        }

    # ── All checks passed ─────────────────────────────────────────────────────
    return {
        "eligible": True,
        "reason": (
            f"Refund request is valid. Customer is {tier} tier with a {window}-day window. "
            f"Purchase was {days_since} days ago. Reason '{refund_reason}' is approved."
        ),
        "rule_triggered": "APPROVED",
        "days_since_purchase": days_since,
        "window_allowed": window,
        "refund_amount": order["amount"],
        "product": order["product"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: process_refund
# ─────────────────────────────────────────────────────────────────────────────

@tool
def process_refund(
    customer_id: str,
    order_id: str,
    decision: str,
    agent_notes: str,
) -> dict:
    """
    Finalize and record the refund decision.

    Args:
        customer_id: Customer's ID
        order_id: The order being refunded or denied
        decision: One of "approved", "denied", "partial", "escalated"
        agent_notes: A brief human-readable explanation of the decision
                     that will be shown to the customer
    """
    valid_decisions = {"approved", "denied", "partial", "escalated"}
    if decision not in valid_decisions:
        return {
            "success": False,
            "error": f"Invalid decision '{decision}'. Must be one of: {valid_decisions}",
        }

    customer = get_customer_by_id(customer_id)
    order = None
    if customer:
        for o in customer.get("orders", []):
            if o["order_id"] == order_id:
                order = o
                break

    refund_amount = None
    if decision == "approved" and order:
        refund_amount = order["amount"]
    elif decision == "partial" and order:
        refund_amount = round(order["amount"] * 0.5, 2)

    timestamp = datetime.utcnow().isoformat() + "Z"

    result = {
        "success": True,
        "decision": decision,
        "customer_id": customer_id,
        "order_id": order_id,
        "refund_amount": refund_amount,
        "agent_notes": agent_notes,
        "processed_at": timestamp,
        "next_steps": _get_next_steps(decision, refund_amount),
    }

    return result


def _get_next_steps(decision: str, amount: Optional[float]) -> str:
    """Generate customer-facing next step message."""
    if decision == "approved":
        return (
            f"Your refund of ${amount:.2f} has been approved and will be credited "
            "to your original payment method within 5–7 business days."
        )
    elif decision == "partial":
        return (
            f"A partial refund of ${amount:.2f} (50%) has been approved and will be "
            "credited to your original payment method within 5–7 business days."
        )
    elif decision == "denied":
        return (
            "Your refund request has been denied per our refund policy. "
            "If you believe this is an error, please contact support@shopeasy.com."
        )
    elif decision == "escalated":
        return (
            "Your case has been escalated to a human support agent who will "
            "reach out within 1 business day."
        )
    return ""


# ── Export all tools as a list for LangGraph binding ─────────────────────────
ALL_TOOLS = [lookup_customer, validate_policy, process_refund]