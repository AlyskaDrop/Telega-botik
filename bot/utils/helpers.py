"""Shared utility functions."""

from __future__ import annotations

import math


def format_isk(amount: int) -> str:
    """Format ISK with M/B/T suffixes. e.g. 1_500_000 → '1.5M ISK'"""
    if amount >= 1_000_000_000_000:
        return f"{amount / 1_000_000_000_000:.2f}T ISK"
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f}B ISK"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M ISK"
    return f"{amount:,} ISK"


def paginate(items: list, page: int, per_page: int = 10) -> tuple[list, int]:
    """Return (page_items, total_pages)."""
    total = math.ceil(len(items) / per_page) if items else 1
    page = max(1, min(page, total))
    start = (page - 1) * per_page
    return items[start : start + per_page], total
