"""
Cost calculation engine for the Road Cost Estimator.

Takes a list of selected SSR items, their quantities and their verified
SSR rates, and produces a traceable cost estimate.

Rules:
    - Amount = Quantity × Rate  (never negative)
    - Items with missing rates are flagged, not silently zeroed
    - Items with zero quantity are flagged as needing manual entry
    - GST is applied to the subtotal at the user-configured percentage
    - No taxes or charges are invented beyond what the user configures
    - All arithmetic is deterministic Python — the AI is never involved
"""

from __future__ import annotations

import pandas as pd

from schemas import CostEstimate, EstimateLineItem


def build_estimate(
    df: pd.DataFrame,
    selected: dict[int, float],
    gst_percent: float = 18.0,
    calculation_notes: dict[int, str] | None = None,
) -> CostEstimate:
    """
    Build a complete cost estimate from the SSR DataFrame, a dict of
    {item_id: quantity}, and the GST percentage.

    ``calculation_notes`` is an optional dict of {item_id: note_string}
    from the quantity engine explaining how each quantity was derived.

    Returns a ``CostEstimate`` with all amounts, subtotal, GST and
    total already computed.
    """
    notes = calculation_notes or {}
    items: list[EstimateLineItem] = []

    for item_id, qty in selected.items():
        if item_id not in df.index:
            continue
        row = df.loc[item_id]
        rate = _safe_float(row.get("rate"))
        has_valid_rate = rate > 0
        has_valid_qty = qty > 0

        line = EstimateLineItem(
            id=int(item_id),
            item_no=str(row.get("item_no", "")),
            chapter=str(row.get("chapter", "")),
            description=str(row.get("description", "")),
            unit=str(row.get("unit", "")),
            kind=str(row.get("kind", "unknown")),
            rate=rate,
            quantity=max(0.0, _safe_float(qty)),
            has_valid_rate=has_valid_rate,
            has_valid_quantity=has_valid_qty,
            calculation_note=notes.get(item_id, ""),
        )
        line.compute_amount()
        items.append(line)

    estimate = CostEstimate(
        items=items,
        gst_percent=max(0.0, gst_percent),
    )
    estimate.recalculate()
    return estimate


def update_estimate_quantities(
    estimate: CostEstimate,
    updated_quantities: dict[int, float],
) -> CostEstimate:
    """
    Update quantities for specific items and recalculate.

    Does NOT add or remove items — only changes quantities.
    """
    for item in estimate.items:
        if item.id in updated_quantities:
            item.quantity = max(0.0, _safe_float(updated_quantities[item.id]))
    estimate.recalculate()
    return estimate


def remove_items(estimate: CostEstimate, item_ids: set[int]) -> CostEstimate:
    """Remove items by their IDs and recalculate."""
    estimate.items = [i for i in estimate.items if i.id not in item_ids]
    estimate.recalculate()
    return estimate


def estimate_to_dataframe(estimate: CostEstimate) -> pd.DataFrame:
    """Convert the estimate items into a pandas DataFrame for display / export."""
    if not estimate.items:
        return pd.DataFrame()

    rows = []
    for item in estimate.items:
        rows.append({
            "Item No": item.item_no,
            "Chapter": item.chapter,
            "Description": item.description,
            "Unit": item.unit,
            "Rate": item.rate,
            "Quantity": item.quantity,
            "Amount": item.amount,
            "Note": item.calculation_note,
        })

    return pd.DataFrame(rows)


def estimate_to_download_dataframe(
    estimate: CostEstimate,
) -> pd.DataFrame:
    """
    Produce a download-ready DataFrame that includes per-item GST.
    """
    base = estimate_to_dataframe(estimate)
    if base.empty:
        return base

    base["GST %"] = estimate.gst_percent
    base["GST Amount"] = round(base["Amount"] * estimate.gst_percent / 100.0, 2)
    base["Amount Including GST"] = round(base["Amount"] + base["GST Amount"], 2)
    return base


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, float) and pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
