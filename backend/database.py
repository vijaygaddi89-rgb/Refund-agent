"""
database.py
-----------
Loads crm.json into memory at startup.
Exposes two lookup functions used by the agent tools:
  - get_customer_by_id(customer_id)
  - get_customer_by_email(email)
  - get_order_by_id(order_id)
"""

import json
from pathlib import Path
from typing import Optional

# ── Load once at import time ──────────────────────────────────────────────────
_DATA_PATH = Path(__file__).parent / "data" / "crm.json"

with open(_DATA_PATH, "r") as f:
    _raw = json.load(f)

# Build two indexes for fast O(1) lookup
_customers_by_id: dict = {}
_customers_by_email: dict = {}
_orders_by_id: dict = {}

for customer in _raw["customers"]:
    cid = customer["customer_id"]
    email = customer["email"].lower()

    _customers_by_id[cid] = customer
    _customers_by_email[email] = customer

    # Also index each order so we can look up by order_id directly
    for order in customer.get("orders", []):
        _orders_by_id[order["order_id"]] = {
            "order": order,
            "customer": customer,  # attach parent customer so tools have full context
        }


# ── Public API ────────────────────────────────────────────────────────────────

def get_customer_by_id(customer_id: str) -> Optional[dict]:
    """Return full customer dict or None if not found."""
    return _customers_by_id.get(customer_id.upper())


def get_customer_by_email(email: str) -> Optional[dict]:
    """Case-insensitive email lookup. Returns full customer dict or None."""
    return _customers_by_email.get(email.lower())


def get_order_by_id(order_id: str) -> Optional[dict]:
    """
    Returns dict with keys 'order' and 'customer', or None.
    Example:
        {
            "order": { order fields ... },
            "customer": { customer fields ... }
        }
    """
    return _orders_by_id.get(order_id.upper())


def list_all_customers() -> list:
    """Returns all customers. Used for admin/debug purposes."""
    return list(_customers_by_id.values())


def get_policy_text() -> str:
    """
    Reads and returns the full refund policy markdown as a string.
    Called once per agent run so the LLM always has the latest policy.
    """
    policy_path = Path(__file__).parent / "data" / "policy.md"
    return policy_path.read_text(encoding="utf-8")
