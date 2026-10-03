"""
Quantity calculation engine for the Road Cost Estimator.

This module performs deterministic arithmetic only. The AI never
calculates a quantity itself -- it only helps identify which SSR items
are relevant. Every formula here is a plain, auditable calculation from
project measurements supplied by the user/engineer.

This replaces the two separate, inconsistent quantity implementations
that used to live in app.py and in a stand-alone estimate_engine.py.

Improvements over the earlier version:
    - Explicit unit-specific formulas (not one generic formula for all)
    - Layer-wise thickness support for new construction
    - Litre, hour, day, per-test, acre and other unit recognition
    - Measurement validation (rejects negative / nonsensical values)
    - Transparent calculation notes explaining every result
    - Unsupported units are flagged, never silently zeroed
"""

from __future__ import annotations

from schemas import ProjectMeasurements


# ============================================================
# ITEM CLASSIFICATION HELPERS
# ============================================================

def _is_pothole_item(description: str, chapter: str) -> bool:
    text = f"{description} {chapter}".lower()
    return "pothole" in text or ("patch" in text and "repair" in text)


def _is_drainage_item(description: str) -> bool:
    text = description.lower()
    return any(word in text for word in ("drain", "kerb", "curb", "gutter", "channel"))


def _is_road_marking_item(description: str) -> bool:
    text = description.lower()
    return any(kw in text for kw in ("road marking", "thermoplastic", "paint line", "marking"))


def _is_shoulder_item(description: str) -> bool:
    text = description.lower()
    return "shoulder" in text


# ============================================================
# MAIN CALCULATION FUNCTION
# ============================================================

def calculate_quantity(
    kind: str,
    description: str,
    chapter: str,
    m: ProjectMeasurements,
) -> float:
    """
    Calculate a quantity for one SSR row.

    kind: the row's quantity category, as produced by
          ssr_loader.infer_kind() -- one of
          "area" | "volume" | "length" | "km" | "nos" | "weight" |
          "liquid" | "time" | "unknown"

    Returns 0.0 when there is not enough information to calculate a
    sensible quantity (the caller should treat 0.0 as "needs manual
    entry", not as a real zero quantity).
    """
    # --- validate inputs ---
    if m.length_m < 0 or m.width_m < 0 or m.thickness_mm < 0:
        return 0.0

    if kind == "area":
        return _calc_area(description, chapter, m)

    if kind == "volume":
        return _calc_volume(description, chapter, m)

    if kind == "length":
        return _calc_length(description, chapter, m)

    if kind == "km":
        if m.length_m <= 0:
            return 0.0
        return round(m.length_km, 3)

    if kind == "nos":
        return _calc_nos(description, chapter, m)

    # "weight", "liquid", "time", "acre", "unknown" all need
    # project-specific data (material density, mix design, duration,
    # survey area, etc.) that we must not invent.
    return 0.0


# ============================================================
# UNIT-SPECIFIC CALCULATION HELPERS
# ============================================================

def _calc_area(description: str, chapter: str, m: ProjectMeasurements) -> float:
    """Area = L × W  (or pothole area for pothole items)."""
    # Pothole-specific area
    if m.pothole_count > 0 and _is_pothole_item(description, chapter):
        return round(m.pothole_area_m2, 3)

    # Road marking uses length only (width is the stripe width, not road width)
    if _is_road_marking_item(description):
        if m.length_m <= 0:
            return 0.0
        # Road markings are typically per sqm; use length × stripe width.
        # Since we don't know the stripe width, return 0 for manual entry.
        return 0.0

    if m.length_m <= 0 or m.width_m <= 0:
        return 0.0

    return round(m.area_m2, 3)


def _calc_volume(description: str, chapter: str, m: ProjectMeasurements) -> float:
    """Volume = L × W × T  (or pothole volume, or layer-specific)."""
    # Pothole-specific volume
    if m.pothole_count > 0 and _is_pothole_item(description, chapter):
        return round(m.pothole_volume_m3, 3)

    # Check for layer-specific thickness from the layers list
    desc_lower = description.lower()
    for layer in (m.layers or []):
        layer_name = str(layer.get("name", "")).lower()
        layer_thickness_mm = layer.get("thickness_mm", 0)
        if layer_name and layer_name in desc_lower and layer_thickness_mm > 0:
            thickness_m = layer_thickness_mm / 1000.0
            if m.length_m > 0 and m.width_m > 0:
                return round(m.length_m * m.width_m * thickness_m, 3)

    # Default volume: L × W × T
    if m.thickness_m <= 0 or m.length_m <= 0 or m.width_m <= 0:
        return 0.0

    return round(m.volume_m3, 3)


def _calc_length(description: str, chapter: str, m: ProjectMeasurements) -> float:
    """Length = drain length for drainage items, otherwise project length."""
    if m.drain_length_m > 0 and _is_drainage_item(description):
        return round(m.drain_length_m, 3)

    if _is_shoulder_item(description):
        # Shoulder runs along the road length (both sides often)
        if m.length_m > 0:
            return round(m.length_m, 3)
        return 0.0

    if m.length_m <= 0:
        return 0.0

    return round(m.length_m, 3)


def _calc_nos(description: str, chapter: str, m: ProjectMeasurements) -> float:
    """Number-based items: potholes, or 0 for manual entry."""
    if m.pothole_count > 0 and "pothole" in description.lower():
        return float(m.pothole_count)

    # For kilometre stones: one per km
    desc_lower = description.lower()
    if ("km stone" in desc_lower or "kilometre stone" in desc_lower
            or "kilometer stone" in desc_lower or "chainage" in desc_lower):
        if m.length_m >= 1000:
            return float(int(m.length_km))
        return 0.0

    # A generic "number" item (e.g. one sign board) has
    # no automatic quantity -- the engineer must confirm how many.
    return 0.0


# ============================================================
# CALCULATION NOTES
# ============================================================

def quantity_note(kind: str, quantity: float, description: str = "", chapter: str = "") -> str:
    """A short, human-readable note explaining where a quantity came from."""
    if quantity > 0:
        desc_lower = (description or "").lower()
        ch_lower = (chapter or "").lower()

        if kind == "area":
            if _is_pothole_item(desc_lower, ch_lower):
                return "pothole count × avg length × avg width"
            return "length × width"
        if kind == "volume":
            if _is_pothole_item(desc_lower, ch_lower):
                return "pothole count × avg L × avg W × avg depth"
            return "length × width × thickness"
        if kind == "length":
            if _is_drainage_item(desc_lower):
                return "drain/kerb length"
            return "project length"
        if kind == "km":
            return "project length ÷ 1000"
        if kind == "nos":
            if "pothole" in desc_lower:
                return "pothole count"
            if "km stone" in desc_lower or "kilometre" in desc_lower:
                return "one per kilometre"
            return "user-specified count"
        return "calculated from measurements"

    if kind in ("weight",):
        return "⚠ needs manual entry — requires material weight/density"
    if kind in ("liquid",):
        return "⚠ needs manual entry — requires liquid volume specification"
    if kind in ("time",):
        return "⚠ needs manual entry — requires duration estimate"
    if kind in ("acre",):
        return "⚠ needs manual entry — requires survey area"
    if kind == "unknown":
        return "⚠ needs manual entry — unsupported unit for auto-calculation"
    return "⚠ needs manual entry — missing measurement"


def calculate_all_quantities(
    df,
    selected_ids: list[int],
    measurements: ProjectMeasurements,
) -> dict[int, tuple[float, str]]:
    """
    Calculate quantities for a list of SSR item IDs.

    Returns {item_id: (quantity, calculation_note)}.
    """
    results: dict[int, tuple[float, str]] = {}
    for item_id in selected_ids:
        if item_id not in df.index:
            continue
        row = df.loc[item_id]
        kind = str(row.get("kind", "unknown"))
        desc = str(row.get("description", ""))
        chapter = str(row.get("chapter", ""))
        qty = calculate_quantity(kind, desc, chapter, measurements)
        note = quantity_note(kind, qty, desc, chapter)
        results[item_id] = (qty, note)
    return results
