"""
Shared data structures for the Road Cost Estimator.

Every module in the project exchanges data using these structures,
which ensures consistent field names, data types and validation
everywhere.  Modules should import what they need from here rather
than inventing ad-hoc dicts.

All structures are plain dataclasses (no heavy dependencies) so they
can be used in tests and CLI scripts without importing Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ============================================================
# AI PHOTO ANALYSIS
# ============================================================

@dataclass
class DefectObservation:
    """One defect spotted by the AI in a photo."""
    type: str = ""
    severity: str = ""          # minor | moderate | severe
    confidence: str = "low"     # low | medium | high
    note: str = ""


@dataclass
class SuggestedWork:
    """One work category the AI thinks may be needed."""
    work: str = ""
    reason: str = ""
    suggested_chapters: list[str] = field(default_factory=list)
    search_keywords: list[str] = field(default_factory=list)
    confidence: str = "low"


@dataclass
class SuggestedParameter:
    """A measurement the engineer should provide."""
    name: str = ""
    why_needed: str = ""


@dataclass
class AnalysisResult:
    """
    The normalised output of one photo analysis.

    Every field has a safe default so that code consuming this object
    never needs to guard against ``None`` or missing keys.
    """
    photo_quality: str = "fair"
    photo_quality_reason: str = ""
    site_type: str = "unclear"
    site_type_confidence: str = "low"
    recommended_mode: str = "unclear"        # repair | new_construction | unclear
    recommended_mode_confidence: str = "low"
    recommended_mode_reason: str = ""
    road_type: str = "unclear"
    road_type_confidence: str = "low"
    surface_condition: str = ""
    defects: list[DefectObservation] = field(default_factory=list)
    suggested_works: list[SuggestedWork] = field(default_factory=list)
    suggested_parameters: list[SuggestedParameter] = field(default_factory=list)
    limitations: str = ""

    # --- serialisation helpers ---

    def to_dict(self) -> dict:
        """Convert to the dict shape the UI (and chat prompt) expect."""
        return {
            "photo_quality": {"value": self.photo_quality, "reason": self.photo_quality_reason},
            "site_type": {"value": self.site_type, "confidence": self.site_type_confidence},
            "recommended_mode": {
                "value": self.recommended_mode,
                "confidence": self.recommended_mode_confidence,
                "reason": self.recommended_mode_reason,
            },
            "road_type": {"value": self.road_type, "confidence": self.road_type_confidence},
            "surface_condition": self.surface_condition,
            "defects": [
                {"type": d.type, "severity": d.severity,
                 "confidence": d.confidence, "note": d.note}
                for d in self.defects
            ],
            "suggested_works": [
                {"work": w.work, "reason": w.reason,
                 "suggested_chapters": w.suggested_chapters,
                 "search_keywords": w.search_keywords,
                 "confidence": w.confidence}
                for w in self.suggested_works
            ],
            "suggested_parameters": [
                {"name": p.name, "why_needed": p.why_needed}
                for p in self.suggested_parameters
            ],
            "limitations": self.limitations,
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> "AnalysisResult":
        """
        Build from a raw AI-returned dict.

        Tolerates the ``{"value": ..., "confidence": ...}`` nesting the
        prompt produces, as well as plain strings.
        """
        if not raw or not isinstance(raw, dict):
            return cls(limitations="No analysis data available.")

        def _val(obj, default=""):
            if isinstance(obj, dict):
                return str(obj.get("value", default))
            return str(obj) if obj is not None else default

        def _conf(obj, default="low"):
            if isinstance(obj, dict):
                return str(obj.get("confidence", default))
            return default

        def _reason(obj, default=""):
            if isinstance(obj, dict):
                return str(obj.get("reason", default))
            return default

        defects = []
        for d in (raw.get("defects") or []):
            if isinstance(d, dict):
                defects.append(DefectObservation(
                    type=str(d.get("type", "")),
                    severity=str(d.get("severity", "")),
                    confidence=str(d.get("confidence", "low")),
                    note=str(d.get("note", "")),
                ))

        works = []
        for w in (raw.get("suggested_works") or []):
            if isinstance(w, dict):
                works.append(SuggestedWork(
                    work=str(w.get("work", "")),
                    reason=str(w.get("reason", "")),
                    suggested_chapters=list(w.get("suggested_chapters") or []),
                    search_keywords=list(w.get("search_keywords") or []),
                    confidence=str(w.get("confidence", "low")),
                ))

        params = []
        for p in (raw.get("suggested_parameters") or []):
            if isinstance(p, dict):
                params.append(SuggestedParameter(
                    name=str(p.get("name", "")),
                    why_needed=str(p.get("why_needed", "")),
                ))

        return cls(
            photo_quality=_val(raw.get("photo_quality"), "fair"),
            photo_quality_reason=_reason(raw.get("photo_quality")),
            site_type=_val(raw.get("site_type"), "unclear"),
            site_type_confidence=_conf(raw.get("site_type")),
            recommended_mode=_val(raw.get("recommended_mode"), "unclear"),
            recommended_mode_confidence=_conf(raw.get("recommended_mode")),
            recommended_mode_reason=_reason(raw.get("recommended_mode")),
            road_type=_val(raw.get("road_type"), "unclear"),
            road_type_confidence=_conf(raw.get("road_type")),
            surface_condition=str(raw.get("surface_condition", "")),
            defects=defects,
            suggested_works=works,
            suggested_parameters=params,
            limitations=str(raw.get("limitations", "")),
        )


# ============================================================
# PROJECT MEASUREMENTS (also used by quantity_engine)
# ============================================================

@dataclass
class ProjectMeasurements:
    """All measurements the user/engineer may supply for a project."""

    length_m: float = 0.0
    width_m: float = 0.0
    thickness_mm: float = 0.0

    # Repair-specific (used only for pothole/patch-type items)
    pothole_count: int = 0
    pothole_avg_length_m: float = 0.0
    pothole_avg_width_m: float = 0.0
    pothole_avg_depth_m: float = 0.0

    # Drainage / kerb
    drain_length_m: float = 0.0

    # New-construction layers  (list of {"name": str, "thickness_mm": float})
    layers: list[dict] = field(default_factory=list)

    # Informational only (not used in arithmetic, but kept so the AI /
    # reviewer can see the full picture)
    lead_distance_km: float = 0.0
    traffic_type: str = ""
    soil_condition: str = ""

    # --- computed helpers ---

    @property
    def area_m2(self) -> float:
        return self.length_m * self.width_m

    @property
    def thickness_m(self) -> float:
        return self.thickness_mm / 1000.0

    @property
    def volume_m3(self) -> float:
        t = self.thickness_m
        return self.length_m * self.width_m * t if t > 0 else 0.0

    @property
    def pothole_area_m2(self) -> float:
        return self.pothole_count * self.pothole_avg_length_m * self.pothole_avg_width_m

    @property
    def pothole_volume_m3(self) -> float:
        return (
            self.pothole_count
            * self.pothole_avg_length_m
            * self.pothole_avg_width_m
            * self.pothole_avg_depth_m
        )

    @property
    def length_km(self) -> float:
        return self.length_m / 1000.0

    def validate(self) -> list[str]:
        """Return a list of human-readable validation warnings (empty = OK)."""
        warnings: list[str] = []
        if self.length_m < 0:
            warnings.append("Length cannot be negative.")
        if self.width_m < 0:
            warnings.append("Width cannot be negative.")
        if self.thickness_mm < 0:
            warnings.append("Thickness cannot be negative.")
        if self.pothole_count < 0:
            warnings.append("Pothole count cannot be negative.")
        if self.pothole_avg_depth_m < 0:
            warnings.append("Pothole depth cannot be negative.")
        return warnings

    def to_dict(self) -> dict:
        return {
            "length_m": self.length_m,
            "width_m": self.width_m,
            "thickness_mm": self.thickness_mm,
            "pothole_count": self.pothole_count,
            "pothole_avg_length_m": self.pothole_avg_length_m,
            "pothole_avg_width_m": self.pothole_avg_width_m,
            "pothole_avg_depth_m": self.pothole_avg_depth_m,
            "drain_length_m": self.drain_length_m,
            "layers": self.layers,
            "lead_distance_km": self.lead_distance_km,
            "traffic_type": self.traffic_type,
            "soil_condition": self.soil_condition,
        }


# ============================================================
# ESTIMATE LINE ITEM
# ============================================================

@dataclass
class EstimateLineItem:
    """One row in the final cost estimate."""

    id: int = 0
    item_no: str = ""
    chapter: str = ""
    description: str = ""
    unit: str = ""
    kind: str = "unknown"
    rate: float = 0.0
    quantity: float = 0.0
    amount: float = 0.0
    calculation_note: str = ""
    has_valid_rate: bool = True
    has_valid_quantity: bool = True

    def compute_amount(self) -> float:
        """Amount = Quantity × Rate.  Never negative."""
        self.amount = max(0.0, round(self.quantity * self.rate, 2))
        return self.amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_no": self.item_no,
            "chapter": self.chapter,
            "description": self.description,
            "unit": self.unit,
            "kind": self.kind,
            "rate": self.rate,
            "quantity": self.quantity,
            "amount": self.amount,
            "calculation_note": self.calculation_note,
            "has_valid_rate": self.has_valid_rate,
            "has_valid_quantity": self.has_valid_quantity,
        }


# ============================================================
# FULL ESTIMATE
# ============================================================

@dataclass
class CostEstimate:
    """A complete cost estimate consisting of line items + totals."""

    items: list[EstimateLineItem] = field(default_factory=list)
    subtotal: float = 0.0
    gst_percent: float = 18.0
    gst_amount: float = 0.0
    total: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def recalculate(self) -> None:
        """Recompute all amounts and totals from current quantities/rates."""
        for item in self.items:
            item.compute_amount()
        self.subtotal = round(sum(i.amount for i in self.items), 2)
        self.gst_amount = round(self.subtotal * self.gst_percent / 100.0, 2)
        self.total = round(self.subtotal + self.gst_amount, 2)

        self.warnings = []
        zero_qty = [i for i in self.items if i.quantity <= 0]
        if zero_qty:
            self.warnings.append(
                f"{len(zero_qty)} item(s) have zero quantity — enter values manually."
            )
        no_rate = [i for i in self.items if not i.has_valid_rate]
        if no_rate:
            self.warnings.append(
                f"{len(no_rate)} item(s) are missing a valid SSR rate."
            )

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "subtotal": self.subtotal,
            "gst_percent": self.gst_percent,
            "gst_amount": self.gst_amount,
            "total": self.total,
            "warnings": self.warnings,
        }
