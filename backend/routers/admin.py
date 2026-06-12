"""
routers/admin.py
----------------
FastAPI router for the admin dashboard.

Endpoints:
  GET /api/admin/customers   → full CRM list
  GET /api/admin/stats       → aggregate statistics
"""

from fastapi import APIRouter
from database import list_all_customers

router = APIRouter()


@router.get("/admin/customers")
async def get_customers():
    """Returns all 15 CRM profiles for the admin panel."""
    customers = list_all_customers()
    return {"customers": customers, "total": len(customers)}


@router.get("/admin/stats")
async def get_stats():
    """Returns aggregate statistics from the CRM for the dashboard."""
    customers = list_all_customers()

    tier_counts = {"standard": 0, "premium": 0, "vip": 0}
    total_orders = 0
    digital_orders = 0
    sale_orders = 0
    total_value = 0.0

    for customer in customers:
        tier = customer.get("tier", "standard")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        for order in customer.get("orders", []):
            total_orders += 1
            total_value += order.get("amount", 0)
            if order.get("is_digital"):
                digital_orders += 1
            if order.get("is_sale_item"):
                sale_orders += 1

    return {
        "total_customers": len(customers),
        "tier_breakdown": tier_counts,
        "total_orders": total_orders,
        "total_order_value": round(total_value, 2),
        "digital_orders": digital_orders,
        "sale_orders": sale_orders,
        "refundable_orders": total_orders - digital_orders - sale_orders,
    }
