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

from schemas import (
    ProjectMeasurements,
    BuildingMeasurements,
    WaterSupplyMeasurements,
    InfraMeasurements,
)


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


# ============================================================
# BUILDING QUANTITY CALCULATIONS
# ============================================================

def calculate_building_quantity(
    kind: str,
    description: str,
    chapter: str,
    b: BuildingMeasurements,
    unit: str = "",
) -> float:
    """Calculate deterministic quantities for building construction items."""
    desc_l = description.lower()
    ch_l = chapter.lower()
    unit_l = unit.lower()

    if kind == "volume":
        if "excavat" in desc_l or "earth" in desc_l or "excavation" in ch_l:
            return b.approx_excavation_m3
        if any(kw in desc_l for kw in ("brick", "masonry", "block", "wall")) or "brick" in ch_l:
            return b.approx_brickwork_m3
        if any(kw in desc_l for kw in ("concrete", "rcc", "cement", "m-20", "m-25", "m-30")) or "concrete" in ch_l:
            return b.approx_concrete_m3
        return b.approx_concrete_m3

    if kind == "weight":
        # TMT Rebar / Steel
        if any(kw in desc_l for kw in ("steel", "tmt", "fe 500", "fe-500", "rebar", "bar", "reinforce")):
            if any(t in unit_l for t in ("tonne", "metric", "mt", "ton")) or any(t in desc_l for t in ("tonne", "metric ton", "mt")):
                return b.approx_steel_tonnes
            return round(b.approx_steel_tonnes * 1000.0, 1)  # kg
        return b.approx_steel_tonnes

    if kind == "area":
        if any(kw in desc_l for kw in ("door", "window", "shutter", "ventilator")) or "door" in ch_l:
            return round(b.total_built_up_area_m2 * 0.12, 2)
        if any(kw in desc_l for kw in ("roof", "ceiling", "waterproof", "terrace")) or "roof" in ch_l:
            return b.plinth_area_m2
        if any(kw in desc_l for kw in ("floor", "dado", "tile", "paving", "marble", "granite")) or "flooring" in ch_l:
            return b.approx_flooring_m2
        if any(kw in desc_l for kw in ("paint", "colour", "color", "distemper", "primer", "white-wash")) or "colouring" in ch_l:
            return b.approx_plaster_m2
        if any(kw in desc_l for kw in ("plaster", "pointing")) or "plaster" in ch_l:
            return b.approx_plaster_m2
        return b.total_built_up_area_m2

    if kind == "nos":
        if "door" in desc_l or "door" in ch_l:
            return float(b.floors * 4)
        if "window" in desc_l:
            return float(b.floors * 6)
        if any(kw in desc_l for kw in ("closet", "wc", "basin", "tap", "sink")):
            return float(b.floors * 2)
        return 1.0

    return 0.0


def building_quantity_note(
    kind: str,
    qty: float,
    description: str,
    chapter: str,
    b: BuildingMeasurements,
) -> str:
    """Generate human-readable engineering note for building quantity."""
    desc_l = description.lower()
    ch_l = chapter.lower()

    if qty > 0:
        if any(kw in desc_l for kw in ("door", "window", "shutter", "ventilator")) or "door" in ch_l:
            return f"Built-up area ({b.total_built_up_area_m2} m²) × 12% aperture ratio"
        if any(kw in desc_l for kw in ("roof", "ceiling", "terrace")) or "roof" in ch_l:
            return f"Roof terrace plinth area ({b.plinth_area_m2} m²)"
        if any(kw in desc_l for kw in ("floor", "tile", "paving")) or "flooring" in ch_l:
            return f"Built-up area ({b.total_built_up_area_m2} m²) × 82% usable carpet area"
        if any(kw in desc_l for kw in ("paint", "colour", "white-wash")) or "colouring" in ch_l:
            return f"Plastered surface area ({b.approx_plaster_m2} m²)"
        if "plaster" in desc_l or "plaster" in ch_l:
            return f"Built-up area ({b.total_built_up_area_m2} m²) × 2.3 m²/m² internal+external"
        if "excavat" in desc_l or "excavation" in ch_l:
            return f"Plinth ({b.plinth_area_m2} m²) × footing depth factor"
        if any(kw in desc_l for kw in ("steel", "tmt", "fe 500", "fe-500", "rebar")):
            return f"RCC concrete ({b.approx_concrete_m3} m³) × 85 kg/m³ IS 456 thumb rule"
        if any(kw in desc_l for kw in ("brick", "masonry", "block")) or "brick" in ch_l:
            return f"Built-up area ({b.total_built_up_area_m2} m²) × 0.18 m³/m² wall ratio"
        if any(kw in desc_l for kw in ("concrete", "rcc", "m-20", "m-25", "m-30")) or "concrete" in ch_l:
            return f"Built-up ({b.total_built_up_area_m2} m²) × 0.038 m³/m² framed thumb rule"
        return "Calculated from building built-up area and PWD norms"

    return "⚠ needs manual entry — specific fixture or schedule item"


# ============================================================
# WATER SUPPLY & SANITARY QUANTITY CALCULATIONS
# ============================================================

def calculate_water_supply_quantity(
    kind: str,
    description: str,
    chapter: str,
    w: WaterSupplyMeasurements,
) -> float:
    """Calculate deterministic quantities for water supply and sanitation items."""
    desc_l = description.lower()

    if kind == "length":
        if any(kw in desc_l for kw in ("drain", "sewer", "stoneware", "gully", "soil pipe", "swg")):
            return w.sewer_drain_length_m
        return w.network_length_m

    if kind == "volume":
        if any(kw in desc_l for kw in ("excavat", "trench", "earthwork")):
            return w.trench_excavation_m3
        if any(kw in desc_l for kw in ("tank", "reservoir", "sump")):
            return round(w.storage_tank_litres / 1000.0, 2)
        return w.trench_excavation_m3

    if kind == "nos":
        if any(kw in desc_l for kw in ("chamber", "inspection", "manhole")):
            return float(w.inspection_chambers_count)
        if any(kw in desc_l for kw in ("tap", "cock", "valve", "ferrule", "pillar", "bib", "shower", "joint")):
            return float(w.fixtures_count)
        if any(kw in desc_l for kw in ("tank", "reservoir")):
            return 1.0
        return float(w.fixtures_count)

    if kind in ("liquid", "volume") and "1000 litre" in description.lower():
        return round(w.storage_tank_litres / 1000.0, 2)

    return 0.0


def water_supply_quantity_note(
    kind: str,
    qty: float,
    description: str,
    chapter: str,
    w: WaterSupplyMeasurements,
) -> str:
    """Generate engineering note for water supply items."""
    desc_l = description.lower()
    if qty > 0:
        if "drain" in desc_l or "sewer" in desc_l or "stoneware" in desc_l:
            return f"Drain/sewer line length ({w.sewer_drain_length_m} m)"
        if kind == "length":
            return f"Total pipeline network running length ({w.network_length_m} m)"
        if "excavat" in desc_l or "trench" in desc_l:
            return f"Trench ({w.network_length_m}m × depth × width = {w.trench_excavation_m3} m³)"
        if "chamber" in desc_l or "inspection" in desc_l:
            return f"User specified inspection chambers ({w.inspection_chambers_count} nos)"
        if any(kw in desc_l for kw in ("tap", "cock", "valve", "ferrule", "fixture")):
            return f"Sanitary/water supply fixtures ({w.fixtures_count} nos)"
        return "Calculated from network measurements"

    return "⚠ needs manual entry — specific fitting specification"


# ============================================================
# INFRASTRUCTURE QUANTITY CALCULATIONS
# ============================================================

def calculate_infra_quantity(
    kind: str,
    description: str,
    chapter: str,
    infra: InfraMeasurements,
) -> float:
    """Calculate deterministic quantities for civil & site infrastructure items."""
    desc_l = description.lower()

    if kind == "length":
        if any(kw in desc_l for kw in ("drain", "channel", "gutter")):
            return infra.storm_drain_length_m
        if any(kw in desc_l for kw in ("wall", "fencing", "barbed", "compound")):
            return infra.compound_wall_length_m
        return infra.compound_wall_length_m

    if kind == "area":
        if any(kw in desc_l for kw in ("paver", "pavement", "block", "flooring", "walkway")):
            return infra.internal_pavement_area_m2
        if any(kw in desc_l for kw in ("wall", "plaster", "coping")):
            return infra.compound_wall_area_m2
        return infra.internal_pavement_area_m2

    if kind == "volume":
        if any(kw in desc_l for kw in ("drain", "excavat", "earthwork")):
            return infra.storm_drain_volume_m3
        return round(infra.compound_wall_length_m * 0.23 * infra.compound_wall_height_m, 2)

    if kind == "nos":
        if any(kw in desc_l for kw in ("culvert", "pipe culvert", "slab")):
            return float(infra.culverts_count)
        if any(kw in desc_l for kw in ("sign", "furniture", "bollard", "post", "light")):
            return float(infra.street_furniture_count)
        return float(infra.culverts_count)

    return 0.0


def infra_quantity_note(
    kind: str,
    qty: float,
    description: str,
    chapter: str,
    infra: InfraMeasurements,
) -> str:
    """Generate engineering note for site infrastructure items."""
    desc_l = description.lower()
    if qty > 0:
        if "paver" in desc_l or "pavement" in desc_l or "walkway" in desc_l:
            return f"Internal pavement area ({infra.internal_pavement_area_m2} m²)"
        if "drain" in desc_l:
            return f"Storm drain length ({infra.storm_drain_length_m} m)"
        if "wall" in desc_l or "fencing" in desc_l:
            return f"Compound wall length ({infra.compound_wall_length_m} m)"
        if "culvert" in desc_l:
            return f"Cross drainage culverts ({infra.culverts_count} nos)"
        return "Calculated from site infrastructure dimensions"

    return "⚠ needs manual entry — specific site item"


# ============================================================
# MASTER CALCULATE ALL QUANTITIES (POLYMORPHIC)
# ============================================================

def calculate_all_quantities(
    df,
    selected_ids: list[int],
    measurements: Any,
) -> dict[int, tuple[float, str]]:
    """
    Calculate quantities for a list of SSR item IDs for any project type.

    Returns {item_id: (quantity, calculation_note)}.
    """
    results: dict[int, tuple[float, str]] = {}
    is_b = isinstance(measurements, BuildingMeasurements)
    is_w = isinstance(measurements, WaterSupplyMeasurements)
    is_i = isinstance(measurements, InfraMeasurements)

    for item_id in selected_ids:
        if item_id not in df.index:
            continue
        row = df.loc[item_id]
        kind = str(row.get("kind", "unknown"))
        desc = str(row.get("description", ""))
        chapter = str(row.get("chapter", ""))
        unit = str(row.get("unit", ""))

        if is_b:
            qty = calculate_building_quantity(kind, desc, chapter, measurements, unit=unit)
            note = building_quantity_note(kind, qty, desc, chapter, measurements)
        elif is_w:
            qty = calculate_water_supply_quantity(kind, desc, chapter, measurements)
            note = water_supply_quantity_note(kind, qty, desc, chapter, measurements)
        elif is_i:
            qty = calculate_infra_quantity(kind, desc, chapter, measurements)
            note = infra_quantity_note(kind, qty, desc, chapter, measurements)
        else:
            qty = calculate_quantity(kind, desc, chapter, measurements)
            note = quantity_note(kind, qty, desc, chapter)

        results[item_id] = (qty, note)
    return results

