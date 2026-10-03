"""
Estimate Service for Road Cost AI.

Coordinates the entire estimation workflow:
    1. SSR Ingestion & Chapter Resolution (ssr_loader.py)
    2. Photo & Site Analysis (ai_module.py)
    3. Intelligent Item Candidate Search & Selection (ssr_selector.py)
    4. Deterministic Quantity Calculation (quantity_engine.py)
    5. Cost Estimation, GST & Export Generation (cost_engine.py)

Keeps all business logic out of app.py so the UI remains lean, maintainable,
and focused solely on presentation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from ai_module import (
    ai_is_configured,
    analyze_photos,
    chat_reply,
    select_ssr_items,
)
from cost_engine import (
    build_estimate,
    estimate_to_dataframe,
    estimate_to_download_dataframe,
    remove_items,
    update_estimate_quantities,
)
from quantity_engine import (
    calculate_all_quantities,
    calculate_quantity,
    quantity_note,
)
from schemas import (
    AnalysisResult,
    CostEstimate,
    EstimateLineItem,
    ProjectMeasurements,
)
from ssr_loader import (
    load_ssr,
    match_chapters,
    search,
    ssr_health_summary,
)
from ssr_selector import (
    candidates_to_ai_payload,
    find_candidates,
    rank_items_by_relevance,
    validate_selected_items,
)

import os

def resolve_default_ssr_path() -> str:
    """Check current directory and parent directory for default SSR file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "SSR_2022-23 (2).xlsx"),
        os.path.join(os.path.dirname(base_dir), "SSR_2022-23 (2).xlsx"),
        os.path.join(os.getcwd(), "SSR_2022-23 (2).xlsx"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]

# Standard road chapter groups
COMMON_NEW = [
    "Road Survey and DPR", "Excavation", "Road Sub grade",
    "Road Sub Base and Base Course", "Cross Drainage Works",
    "Road Miscellaneous items", "Road Furniture", "Road Safety", "Geosynthetic",
]
CC_EXTRA = ["Rigid Pavement", "Expansion Joint"]
BT_EXTRA = ["Road Surfacing Course"]
REPAIR = [
    "Road Maintenance", "Bitumen and concrete road Pot Hole Reparing",
    "Road Miscellaneous items", "Road Furniture", "Road Safety", "Cross Drainage Works",
]

REQUIRED_COLUMNS = ["id", "item_no", "chapter", "description", "unit", "rate", "kind"]


# ============================================================
# SSR DATA PREPARATION
# ============================================================

def prepare_ssr_dataframe(file_or_path: Any) -> pd.DataFrame:
    """
    Load and normalize an SSR DataFrame.
    Validates required columns, ensures clean numeric rates, and sets 'id' as index.
    """
    df = load_ssr(file_or_path)
    if df is None or df.empty:
        raise ValueError("The provided SSR file is empty or could not be parsed.")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("SSR is missing required columns: " + ", ".join(missing))

    df = df.copy()
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce").fillna(0.0)
    df = df.set_index("id", drop=False)
    return df


def get_project_preset_chapters(
    all_chapters: list[str],
    mode: str,
    road_kind: str | None = None,
) -> list[str]:
    """
    Determine the matching SSR chapters for a given project mode and road type.
    """
    if mode == "New Road Construction":
        wanted = COMMON_NEW + (CC_EXTRA if road_kind == "Concrete (CC)" else BT_EXTRA)
    else:
        wanted = REPAIR

    return match_chapters(all_chapters, wanted)


def get_ssr_summary(df: pd.DataFrame) -> dict:
    """Get diagnostic health summary of the active SSR."""
    return ssr_health_summary(df)


# ============================================================
# PHOTO ANALYSIS & COMBINATION
# ============================================================

def process_site_photos(photos: list[dict], note: str = "") -> list[dict]:
    """Analyze a batch of uploaded photos."""
    return analyze_photos(photos, note=note)


def combine_ai_results(results: list[dict]) -> dict | None:
    """
    Merge multiple photo analysis outputs into one unified project summary.
    Applies majority voting for mode/road type and aggregates defects/works/parameters.
    """
    valid = [r.get("result", {}) for r in results if isinstance(r.get("result"), dict)]
    if not valid:
        return None

    def _extract_val(obj):
        if isinstance(obj, dict):
            return obj.get("value", "")
        return str(obj) if obj is not None else ""

    def majority(values: list[str]) -> str:
        clean = [v for v in values if v and v != "unclear"]
        return Counter(clean).most_common(1)[0][0] if clean else "unclear"

    modes = [_extract_val(r.get("recommended_mode")) for r in valid]
    modes = [m for m in modes if m in ("repair", "new_construction")]
    road_types = [_extract_val(r.get("road_type")) for r in valid]
    site_types = [_extract_val(r.get("site_type")) for r in valid]

    def dedupe(items: list[dict], key_fn) -> list[dict]:
        seen = set()
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = key_fn(item)
            if key and key not in seen:
                seen.add(key)
                out.append(item)
        return out

    defects = dedupe(
        [d for r in valid for d in (r.get("defects") or [])],
        lambda d: str(d.get("type", "")).strip().lower(),
    )
    works = dedupe(
        [w for r in valid for w in (r.get("suggested_works") or [])],
        lambda w: str(w.get("work", "")).strip().lower(),
    )
    parameters = dedupe(
        [p for r in valid for p in (r.get("suggested_parameters") or [])],
        lambda p: str(p.get("name", "")).strip().lower(),
    )

    surface_notes = [
        str(r.get("surface_condition", "")).strip()
        for r in valid
        if r.get("surface_condition")
    ]

    return {
        "photo_quality": {"value": "combined", "reason": f"Synthesized from {len(valid)} photo(s)"},
        "site_type": {"value": majority(site_types), "confidence": "medium"},
        "recommended_mode": {
            "value": majority(modes) if modes else "unclear",
            "confidence": "medium",
            "reason": "Consensus assessment across all uploaded photographs.",
        },
        "road_type": {"value": majority(road_types), "confidence": "medium"},
        "surface_condition": " | ".join(surface_notes) if surface_notes else "Not specified.",
        "defects": defects,
        "suggested_works": works,
        "suggested_parameters": parameters,
        "limitations": "Photo analysis is visual guidance only. Site measurements and engineering parameters must be verified on-site.",
    }


# ============================================================
# AUTOMATIC & MANUAL ESTIMATION WORKFLOW
# ============================================================

def generate_estimate(
    df: pd.DataFrame,
    mode: str,
    road_kind: str | None,
    measurements: ProjectMeasurements,
    ai_analysis: dict | None = None,
    allowed_chapters: list[str] | None = None,
    gst_percent: float = 18.0,
    use_ai_selection: bool = True,
) -> CostEstimate:
    """
    Primary end-to-end estimation workflow:
        1. Find candidate items in SSR matching project scope & category balance.
        2. Optionally refine via AI (picking only valid candidate IDs).
        3. Deterministically compute quantities from ProjectMeasurements.
        4. Build and calculate CostEstimate with subtotal, GST, and totals.
    """
    if df is None or df.empty:
        return CostEstimate(gst_percent=gst_percent)

    # 1. Candidate identification
    candidates = find_candidates(
        df=df,
        mode=mode,
        road_kind=road_kind,
        ai_analysis=ai_analysis,
        allowed_chapters=allowed_chapters,
        max_per_category=3,
        max_total=40,
    )

    if candidates.empty:
        return CostEstimate(gst_percent=gst_percent, warnings=["No candidate SSR items found for the given criteria."])

    selected_ids = list(candidates["id"])

    # 2. AI Refinement (if enabled and configured)
    if use_ai_selection and ai_is_configured():
        try:
            spec = {
                "mode": mode,
                "road_type": road_kind,
                "length_m": measurements.length_m,
                "width_m": measurements.width_m,
                "thickness_mm": measurements.thickness_mm,
            }
            payload = candidates_to_ai_payload(candidates)
            ai_pick = select_ssr_items(spec, payload)
            if ai_pick and ai_pick.get("selected_ids"):
                validated_ai_ids = validate_selected_items(df, ai_pick["selected_ids"])
                if validated_ai_ids:
                    selected_ids = validated_ai_ids
        except Exception:
            # Fallback seamlessly to top candidate IDs
            pass

    # Ensure all IDs are validated against active DataFrame
    valid_ids = validate_selected_items(df, selected_ids)

    # 3. Calculate Quantities & Traceability Notes
    qty_results = calculate_all_quantities(df, valid_ids, measurements)
    selected_quantities = {item_id: res[0] for item_id, res in qty_results.items()}
    notes = {item_id: res[1] for item_id, res in qty_results.items()}

    # 4. Build deterministic CostEstimate
    return build_estimate(
        df=df,
        selected=selected_quantities,
        gst_percent=gst_percent,
        calculation_notes=notes,
    )


def add_items_to_estimate(
    df: pd.DataFrame,
    current_estimate: CostEstimate,
    new_item_ids: list[int],
    measurements: ProjectMeasurements,
) -> CostEstimate:
    """Add additional SSR items to an existing estimate."""
    valid_new_ids = validate_selected_items(df, new_item_ids)
    existing_ids = {item.id for item in current_estimate.items}

    items_to_add = [i for i in valid_new_ids if i not in existing_ids]
    if not items_to_add:
        return current_estimate

    # Compute quantities for new items
    new_qty_results = calculate_all_quantities(df, items_to_add, measurements)

    # Combine with current items
    combined_selected: dict[int, float] = {
        item.id: item.quantity for item in current_estimate.items
    }
    combined_notes: dict[int, str] = {
        item.id: item.calculation_note for item in current_estimate.items
    }

    for item_id in items_to_add:
        qty, note = new_qty_results.get(item_id, (0.0, "manually added"))
        combined_selected[item_id] = qty
        combined_notes[item_id] = note

    return build_estimate(
        df=df,
        selected=combined_selected,
        gst_percent=current_estimate.gst_percent,
        calculation_notes=combined_notes,
    )


def update_quantities_in_estimate(
    estimate: CostEstimate,
    updated_quantities: dict[int, float],
) -> CostEstimate:
    """Update quantities and recompute totals."""
    return update_estimate_quantities(estimate, updated_quantities)


def remove_items_from_estimate(
    estimate: CostEstimate,
    item_ids_to_remove: set[int],
) -> CostEstimate:
    """Remove items and recompute totals."""
    return remove_items(estimate, item_ids_to_remove)


def get_estimate_display_df(estimate: CostEstimate) -> pd.DataFrame:
    """Get clean display DataFrame."""
    return estimate_to_dataframe(estimate)


def get_estimate_export_csv(estimate: CostEstimate) -> str:
    """Get download-ready CSV string including GST details."""
    df = estimate_to_download_dataframe(estimate)
    if df.empty:
        return ""
    return df.to_csv(index=False)
