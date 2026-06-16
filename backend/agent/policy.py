"""Loads and serves the refund policy document."""
from pathlib import Path
from functools import lru_cache
from typing import Optional

POLICY_FILE = Path(__file__).parent.parent / "data" / "policy.md"

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "electronics": ["electronics", "electronic", "laptop", "phone", "camera", "headphone",
                    "speaker", "tablet", "tv", "television", "smartwatch"],
    "clothing":    ["clothing", "apparel", "shirt", "shoes", "jacket", "dress", "fashion"],
    "digital":     ["digital", "software", "download", "license", "ebook", "key"],
    "subscription":["subscription", "plan", "membership", "monthly", "annual"],
    "appliances":  ["appliance", "kitchen", "mixer", "blender", "washer", "dryer"],
    "sports":      ["sports", "fitness", "yoga", "gym", "exercise"],
}




@lru_cache(maxsize=1)
def load_full_policy() -> str:
    """Return the full policy document (cached)."""
    if not POLICY_FILE.exists():
        return "Policy document not found."
    return POLICY_FILE.read_text(encoding="utf-8")


def load_policy_section(category: Optional[str] = None) -> str:
    """Return full policy or the most relevant section for a given category."""
    full = load_full_policy()
    if not category:
        return full

    cat = category.lower()
    # Find which group this category belongs to
    matched_group: Optional[str] = None
    for group, keywords in CATEGORY_KEYWORDS.items():
        if cat in keywords or any(kw in cat for kw in keywords):
            matched_group = group
            break

    if not matched_group:
        return full

    # Extract relevant sections by heading keywords
    relevant: list[str] = []
    for section in full.split("\n## "):
        section_lower = section.lower()
        if any(kw in section_lower for kw in CATEGORY_KEYWORDS.get(matched_group, [])):
            relevant.append("## " + section if not section.startswith("#") else section)
        # Always include sections 1-4 (core rules)
        elif any(f"## {n}." in ("## " + section) for n in ("1", "2", "3", "4")):
            relevant.append("## " + section if not section.startswith("#") else section)

    return "\n".join(relevant) if relevant else full


# Module-level constant — imported by agent_runner.py into the system prompt.
# Defined after load_full_policy() so the function exists when this is evaluated.
REFUND_POLICY: str = load_full_policy()