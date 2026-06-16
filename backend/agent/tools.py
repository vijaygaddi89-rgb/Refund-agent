"""
Pure business-logic layer.
No LangChain imports — fully unit-testable.
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

CRM_FILE = Path(__file__).parent.parent / "data" / "crm.json"

# ── Return windows (days) ──────────────────────────────────────────────────────
RETURN_WINDOWS = {
    "electronics":  15,
    "digital":       0,
    "subscription":  7,
    "defective":    60,
    "damaged":      60,
    "default":      30,
}

# ── In-memory CRM cache (simulates live CRM) ──────────────────────────────────
_crm_cache: Optional[Dict] = None


def _load_crm() -> Dict:
    global _crm_cache
    if _crm_cache is None:
        if not CRM_FILE.exists():
            raise FileNotFoundError(f"CRM file not found: {CRM_FILE}")
        _crm_cache = json.loads(CRM_FILE.read_text(encoding="utf-8"))
    return _crm_cache


# ── Customer lookup ────────────────────────────────────────────────────────────

def find_customer(identifier: str) -> Optional[Dict]:
    """
    Find a customer by customer_id, email, or name (case-insensitive).
    Returns the customer dict or None.
    """
    crm = _load_crm()
    needle = identifier.strip().lower()
    for customer in crm["customers"]:
        if (
            customer["customer_id"].lower() == needle
            or customer["email"].lower() == needle
            or customer["name"].lower() == needle
            or needle in customer["name"].lower()
        ):
            return customer
    return None


def get_customer_orders(customer_id: str, order_id: Optional[str] = None) -> List[Dict]:
    """Return all orders for a customer, or just the one matching order_id."""
    crm = _load_crm()
    customer = next(
        (c for c in crm["customers"] if c["customer_id"] == customer_id), None
    )
    if not customer:
        return []
    orders = customer.get("orders", [])
    if order_id:
        return [o for o in orders if o["order_id"] == order_id]
    return orders


# ── Eligibility check ─────────────────────────────────────────────────────────

def check_refund_eligibility(customer_id: str, order_id: str) -> Dict[str, Any]:
    """
    Core refund eligibility engine.

    Returns:
        eligible           (bool)
        reason             (str)  — human-readable explanation
        policy_rule        (str)  — section reference
        refund_amount      (float)
        includes_shipping  (bool)
        requires_escalation(bool)
        escalation_reason  (str | None)
    """
    crm = _load_crm()
    customer = next(
        (c for c in crm["customers"] if c["customer_id"] == customer_id), None
    )

    # ── Customer not found ─────────────────────────────────────────────────────
    if not customer:
        return _deny("Customer not found in the system.", "N/A")

    # ── Suspended account → hard deny ─────────────────────────────────────────
    if customer.get("account_status") == "suspended":
        return _deny(
            "Customer account is suspended. Refunds cannot be processed for suspended accounts.",
            "Section 9: Fraud Prevention",
            escalate=True,
            escalation_reason="Suspended account",
        )

    # ── Locate order ──────────────────────────────────────────────────────────
    order = next(
        (o for o in customer.get("orders", []) if o["order_id"] == order_id), None
    )
    if not order:
        return _deny(
            f"Order {order_id} not found for this customer account.",
            "N/A",
        )

    # ── Already refunded ──────────────────────────────────────────────────────
    if order.get("refund_status") == "refunded":
        return _deny(
            f"Order {order_id} has already been refunded on {order.get('refunded_at', 'unknown date')}. "
            "Duplicate refunds are not permitted.",
            "Policy: No duplicate refunds",
        )

    if order.get("refund_status") == "processing":
        return _deny(
            f"A refund for order {order_id} is already being processed. "
            "Please allow 5–7 business days for completion.",
            "Policy: No duplicate refund requests",
        )

    # ── Final sale items ───────────────────────────────────────────────────────
    if order.get("is_sale_item", False):
        return _deny(
            f"'{order['product']}' was purchased as a sale/clearance item and is marked as "
            "final sale. Sale items are strictly non-refundable.",
            "Section 3: Non-Refundable Items — Sale/Clearance Items",
        )

    # ── Digital products ───────────────────────────────────────────────────────
    if order.get("is_digital", False):
        if order.get("was_downloaded", False):
            ts = order.get("download_timestamp", "unknown time")
            return _deny(
                f"'{order['product']}' is a digital product that was downloaded/accessed on {ts}. "
                "Digital products are non-refundable once accessed.",
                "Section 3: Non-Refundable Items — Digital Products",
            )

    # ── Calculate days since delivery ─────────────────────────────────────────
    delivery_str = order.get("delivery_date") or order.get("purchase_date")
    try:
        delivery_date = datetime.strptime(delivery_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        delivery_date = date.today()

    days_since = (date.today() - delivery_date).days

    # ── Determine return window ────────────────────────────────────────────────
    category = order.get("category", "default").lower()
    is_defective = order.get("is_defective", False)
    is_damaged = order.get("condition_reported") == "damaged_shipping"

    if is_defective or is_damaged:
        window = RETURN_WINDOWS["defective"]
        policy_rule = "Section 5: Defective/Damaged Items — 60-day return window"
        includes_shipping = True
    elif category == "electronics":
        window = RETURN_WINDOWS["electronics"]
        policy_rule = "Section 6: Electronics Policy — 15-day return window"
        includes_shipping = False
    elif category == "subscription":
        window = RETURN_WINDOWS["subscription"]
        policy_rule = "Section 7: Subscription Cancellations — 7-day window"
        includes_shipping = False
    elif category == "digital":
        # Not downloaded → still technically returnable? No — digital is always 0.
        return _deny(
            f"'{order['product']}' is a digital product. Digital products are non-refundable.",
            "Section 3: Non-Refundable Items — Digital Products",
        )
    else:
        window = RETURN_WINDOWS["default"]
        policy_rule = "Section 1: Standard Return Window — 30-day return window"
        includes_shipping = False

    # ── Window check ──────────────────────────────────────────────────────────
    if days_since > window:
        return _deny(
            f"The return window has expired. '{order['product']}' ({category}) has a "
            f"{window}-day return window. It has been {days_since} day(s) since delivery "
            f"({delivery_str}). The deadline was "
            f"{(delivery_date.replace(year=delivery_date.year) if False else delivery_date).__class__.fromordinal(delivery_date.toordinal() + window).isoformat()}.",
            policy_rule,
        )

    # ── Hygiene restriction — opened headphones/earbuds ───────────────────────
    subcategory = order.get("subcategory", "").lower()
    hygiene_items = ("headphone", "earbud", "earphone", "in-ear")
    if category == "electronics" and any(h in subcategory for h in hygiene_items):
        if order.get("condition_reported") == "used":
            return _deny(
                f"Opened/used '{order['product']}' cannot be returned due to hygiene restrictions. "
                "Headphones and earbuds are non-refundable once used.",
                "Section 6: Electronics — Hygiene restriction",
            )

    # ── Compute refund amount ─────────────────────────────────────────────────
    base_amount = float(order.get("amount", 0))
    shipping = float(order.get("shipping_cost", 0))
    refund_amount = base_amount + (shipping if includes_shipping else 0.0)

    # ── Escalation checks ─────────────────────────────────────────────────────
    requires_escalation = False
    escalation_reason: Optional[str] = None

    if refund_amount > 500:
        requires_escalation = True
        escalation_reason = f"Refund amount ${refund_amount:.2f} exceeds $500 threshold (Section 8)"

    if customer.get("account_status") == "flagged":
        requires_escalation = True
        escalation_reason = (
            f"Customer account is flagged: {customer.get('flag_reason', 'under review')} (Section 9)"
        )

    prior_refund_count = sum(
        1 for o in customer.get("orders", [])
        if o.get("refund_status") in ("refunded", "processing")
    )
    if prior_refund_count >= 3:
        requires_escalation = True
        escalation_reason = (
            f"Customer has {prior_refund_count} prior refunds — "
            "fraud prevention review required (Section 9)"
        )

    return {
        "eligible": True,
        "reason": (
            f"'{order['product']}' is eligible for a refund. "
            f"Delivered {days_since} day(s) ago ({delivery_str}), "
            f"within the {window}-day window."
        ),
        "policy_rule": policy_rule,
        "refund_amount": round(refund_amount, 2),
        "includes_shipping": includes_shipping,
        "requires_escalation": requires_escalation,
        "escalation_reason": escalation_reason,
        "product": order["product"],
        "category": category,
        "days_since_delivery": days_since,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _deny(
    reason: str,
    policy_rule: str,
    escalate: bool = False,
    escalation_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "eligible": False,
        "reason": reason,
        "policy_rule": policy_rule,
        "refund_amount": 0.0,
        "includes_shipping": False,
        "requires_escalation": escalate,
        "escalation_reason": escalation_reason,
        "product": None,
        "category": None,
        "days_since_delivery": None,
    }


def format_customer_for_agent(customer: Dict) -> str:
    """Format a customer dict into a clean string for the LLM."""
    orders = customer.get("orders", [])
    order_lines = []
    for o in orders:
        status = o.get("refund_status") or o.get("status", "delivered")
        order_lines.append(
            f"  • {o['order_id']} | {o['product']} | ${o['amount']:.2f} | "
            f"Delivered: {o.get('delivery_date', o.get('purchase_date', 'N/A'))} | "
            f"Refund status: {status or 'none'}"
        )
    orders_str = "\n".join(order_lines) if order_lines else "  (no orders)"

    return (
        f"CUSTOMER FOUND\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Name          : {customer['name']}\n"
        f"Customer ID   : {customer['customer_id']}\n"
        f"Email         : {customer['email']}\n"
        f"Account Status: {customer['account_status'].upper()}\n"
        f"Tier          : {customer.get('tier', 'standard').capitalize()}\n"
        f"Member Since  : {customer.get('member_since', 'N/A')}\n"
        f"\nOrders ({len(orders)}):\n{orders_str}"
    )


def format_eligibility_for_agent(result: Dict, order_id: str) -> str:
    """Format eligibility result into a clear decision string for the LLM."""
    if result["eligible"]:
        esc = ""
        if result["requires_escalation"]:
            esc = f"\n⚠️  ESCALATION REQUIRED: {result['escalation_reason']}"
        shipping_note = " (includes shipping)" if result["includes_shipping"] else ""
        return (
            f"ELIGIBILITY RESULT FOR {order_id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Status        : ✅ ELIGIBLE FOR REFUND\n"
            f"Product       : {result.get('product', 'N/A')}\n"
            f"Refund Amount : ${result['refund_amount']:.2f}{shipping_note}\n"
            f"Policy Rule   : {result['policy_rule']}\n"
            f"Reason        : {result['reason']}{esc}"
        )
    else:
        return (
            f"ELIGIBILITY RESULT FOR {order_id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Status        : ❌ NOT ELIGIBLE\n"
            f"Policy Rule   : {result['policy_rule']}\n"
            f"Reason        : {result['reason']}"
        )





# ── Async tool implementations ─────────────────────────────────────────────────

@tool
async def lookup_customer_and_order(
    identifier: str,
    order_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Look up a customer in the CRM system and retrieve their order details.
    Call this FIRST to verify the customer and order exist before any refund processing.
    """
    customer = find_customer(identifier)
    if not customer:
        return {
            "found": False,
            "message": f"No customer matching '{identifier}' found.",
        }
    orders = get_customer_orders(customer["customer_id"], order_id)
    return {
        "found": True,
        "customer_id": customer["customer_id"],
        "customer_name": customer["name"],
        "customer_email": customer["email"],
        "account_status": customer["account_status"],
        "tier": customer.get("tier", "standard"),
        "orders": orders,
        "formatted": format_customer_for_agent(customer),
    }


@tool
async def check_refund_history(customer_id: str) -> Dict[str, Any]:
    """Check how many refunds this customer has received this month.
    Call this after lookup_customer_and_order to detect abuse.
    """
    orders = get_customer_orders(customer_id)
    refunded = [o for o in orders if o.get("refund_status") in ("refunded", "processing")]
    return {
        "customer_id": customer_id,
        "total_orders": len(orders),
        "prior_refunds": len(refunded),
        "refunded_orders": [o["order_id"] for o in refunded],
        "high_risk": len(refunded) >= 3,
    }


@tool
async def validate_refund_policy(
    customer_id: str,
    order_id: str,
) -> Dict[str, Any]:
    """Run the deterministic policy engine to check whether the order is eligible for a refund.
    Returns eligible/denied verdict, refund amount, and policy rule.
    YOU MUST call this before approving or denying any refund.
    """
    result = check_refund_eligibility(customer_id, order_id)
    result["formatted"] = format_eligibility_for_agent(result, order_id)
    return result


@tool
async def process_refund_decision(
    customer_id: str,
    order_id: str,
    decision: str,
    refund_amount: float,
    reason: str,
    policy_rule: str,
) -> Dict[str, Any]:
    """Record the final refund decision (approved / denied / escalated).
    YOU MUST call this for every refund request — even denials.
    Never skip this step.
    """
    import uuid as _uuid
    ref_number = f"REF-{_uuid.uuid4().hex[:8].upper()}"
    return {
        "decision": decision,
        "customer_id": customer_id,
        "order_id": order_id,
        "refund_amount": refund_amount,
        "reason": reason,
        "policy_rule": policy_rule,
        "reference_number": ref_number,
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "message": (
            f"Decision recorded: {decision.upper()} — "
            f"₹{refund_amount:.2f} — ref {ref_number}"
        ),
    }


AGENT_TOOLS = [
    lookup_customer_and_order,
    check_refund_history,
    validate_refund_policy,
    process_refund_decision,
]