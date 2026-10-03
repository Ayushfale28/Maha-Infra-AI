"""
SSR item candidate search, scoring, and selection.

Design (the "hybrid" approach):
    1. Python keyword & category scoring -> broad list of candidates across all road works
    2. Deduplication & relevance ranking -> prevents duplicate item numbers or redundant rows
    3. AI review (optional)              -> picks the most relevant subset from those candidates only
    4. Validation against loaded SSR     -> ensures every selected item exists in the active DataFrame
    5. User review in the UI             -> engineer has the final say

The AI is never allowed to invent an item or rate; it can only choose IDs from
the candidate list it was given. If the AI step is unavailable, the top-ranked
candidates are used directly.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _norm(text: Any) -> str:
    """Normalize text for consistent keyword matching."""
    text = "" if text is None else str(text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# KEYWORD DICTIONARIES
# ============================================================

CC_KEYWORDS = [
    "concrete", "cement concrete", "rigid pavement", "cc pavement", "pcc",
    "expansion joint", "contraction joint", "longitudinal joint", "dowell", "tie bar",
    "dlc", "dry lean concrete", "m10", "m15", "m20", "m30", "m40", "m35",
]

BT_KEYWORDS = [
    "bitumen", "bituminous", "dambar", "asphalt", "surface dressing", "tack coat",
    "prime coat", "premix", "dbm", "dense bituminous macadam", "bc ", "bituminous concrete",
    "seal coat", "mastic asphalt", "penetration macadam",
]

NEW_ROAD_KEYWORDS = [
    "excavat", "earthwork", "sub grade", "subgrade", "sub base", "subbase", "base course",
    "clearing", "cleaning", "grubbing", "formation", "embankment", "gsb", "wbm", "wmm",
    "wet mix", "granular", "roller", "compaction",
]

REPAIR_KEYWORDS = [
    "maintenance", "repair", "pothole", "pot hole", "patch", "crack", "ravel",
    "edge break", "reinstatement", "filling", "resurfacing", "profile corrective",
]

CATEGORY_KEYWORDS = {
    "site_preparation": ["clearing", "cleaning", "grubbing", "tree cutting", "removal of stump"],
    "excavation": ["excavat", "earthwork", "cutting", "embankment", "formation"],
    "subgrade": ["sub grade", "subgrade", "compacting ground"],
    "subbase": ["sub base", "subbase", "gsb", "granular sub base"],
    "base_course": ["base course", "wbm", "wmm", "wet mix macadam", "water bound macadam"],
    "concrete_pavement": ["rigid pavement", "cement concrete", "concrete pavement", "pcc", "dlc"],
    "expansion_joint": ["expansion joint", "contraction joint", "joint filler", "sealant"],
    "prime_coat": ["prime coat"],
    "tack_coat": ["tack coat"],
    "bituminous_surface": ["bitumen", "bituminous", "asphalt", "surface dressing", "premix", "dbm", "bc "],
    "pothole_repair": ["pothole", "pot hole", "patch repair", "patching"],
    "crack_repair": ["crack", "slurry seal", "crack seal", "fog seal"],
    "maintenance": ["maintenance", "reinstatement", "dressing"],
    "drainage": ["drain", "culvert", "pipe", "catchpit", "gutter", "cross drainage"],
    "road_furniture": ["km stone", "kilometre stone", "sign board", "signboard", "road marking",
                        "guard stone", "boundary stone", "painting"],
    "road_safety": ["road safety", "crash barrier", "reflector", "delineator", "speed breaker", "rumble"],
}


def _keyword_score(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def categorise_text(text: str) -> str:
    """Assign an item to a functional roadwork category for diversity."""
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "other"


# ============================================================
# ITEM SCORING
# ============================================================

def score_item(
    row: dict | pd.Series,
    mode: str,
    road_kind: str | None,
    ai_analysis: dict | None = None,
) -> tuple[int, list[str]]:
    """
    Score one SSR row against the project requirements.
    Returns (score, matched_reasons).
    """
    description = _norm(row.get("description", ""))
    chapter = _norm(row.get("chapter", ""))
    text = f"{description} {chapter}"

    score = 0
    reasons: list[str] = []

    # Basic road relevance
    if mode == "New Road Construction":
        hits = _keyword_score(text, NEW_ROAD_KEYWORDS)
        if hits:
            score += 10 * min(hits, 3)
            reasons.append("matches new-road construction")

        if road_kind == "Concrete (CC)":
            cc_hits = _keyword_score(text, CC_KEYWORDS)
            if cc_hits:
                score += 15 + (5 * min(cc_hits, 3))
                reasons.append("matches concrete/CC pavement")
        elif road_kind == "Bitumen / Dambar":
            bt_hits = _keyword_score(text, BT_KEYWORDS)
            if bt_hits:
                score += 15 + (5 * min(bt_hits, 3))
                reasons.append("matches bituminous/BT surfacing")

    elif mode == "Repair (Existing Road)":
        hits = _keyword_score(text, REPAIR_KEYWORDS)
        if hits:
            score += 12 * min(hits, 3)
            reasons.append("matches road repair & maintenance")

    # Match AI analysis observations if available
    if ai_analysis and isinstance(ai_analysis, dict):
        defects = ai_analysis.get("defects") or []
        for defect in defects:
            if isinstance(defect, dict):
                dtype = _norm(defect.get("type", "")).replace("_", " ")
                if dtype and dtype in text:
                    score += 10
                    reasons.append(f"AI defect: {dtype}")

        suggested_works = ai_analysis.get("suggested_works") or []
        for work in suggested_works:
            if not isinstance(work, dict):
                continue
            for kw in work.get("search_keywords", []) or []:
                kw_norm = _norm(kw)
                if kw_norm and kw_norm in text:
                    score += 8
                    reasons.append(f"AI work keyword: {kw_norm}")

    # Prioritize items with valid non-zero rates
    rate = row.get("rate")
    try:
        if rate is not None and float(rate) > 0:
            score += 2
    except (ValueError, TypeError):
        pass

    return score, reasons


# ============================================================
# CANDIDATE SEARCH & DEDUPLICATION
# ============================================================

def find_candidates(
    df: pd.DataFrame,
    mode: str,
    road_kind: str | None = None,
    ai_analysis: dict | None = None,
    allowed_chapters: list[str] | None = None,
    max_per_category: int = 3,
    max_total: int = 40,
) -> pd.DataFrame:
    """
    Search and score SSR rows, returning ranked candidates spread across
    work categories to prevent near-duplicate items while covering all needed tasks.

    - De-duplicates identical item numbers and identical descriptions.
    - Ensures categories like excavation, subgrade, base, surface, and safety are represented.
    - Gracefully handles empty or missing inputs.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    pool = df
    if allowed_chapters:
        allowed_norm = {_norm(c) for c in allowed_chapters if c}
        if allowed_norm:
            pool = df[df["chapter"].map(_norm).isin(allowed_norm)]
            if pool.empty:
                pool = df

    scored_candidates = []
    seen_item_nos: set[str] = set()

    for _, row in pool.iterrows():
        score, reasons = score_item(row, mode, road_kind, ai_analysis)
        if score <= 0:
            continue

        item_id = int(row["id"])
        item_no = str(row.get("item_no", "")).strip().lower()
        desc = _norm(row.get("description", ""))
        text = f"{desc} {_norm(row.get('chapter', ''))}"
        cat = categorise_text(text)

        scored_candidates.append({
            "id": item_id,
            "item_no_norm": item_no,
            "score": score,
            "reasons": reasons,
            "category": cat,
            "desc_snippet": desc[:60],
        })

    if not scored_candidates:
        return pd.DataFrame()

    # Sort descending by score
    scored_candidates.sort(key=lambda r: r["score"], reverse=True)

    # De-duplicate: avoid duplicate item numbers and limit items per category
    kept = []
    category_counts: dict[str, int] = {}
    seen_snippets: set[str] = set()

    for candidate in scored_candidates:
        item_no = candidate["item_no_norm"]
        if item_no and item_no in seen_item_nos:
            continue

        # Prevent exact identical description duplicates
        snippet = candidate["desc_snippet"]
        if snippet and snippet in seen_snippets:
            continue

        cat = candidate["category"]
        count = category_counts.get(cat, 0)
        if count >= max_per_category and cat != "other":
            continue

        seen_item_nos.add(item_no)
        seen_snippets.add(snippet)
        category_counts[cat] = count + 1
        kept.append(candidate)

        if len(kept) >= max_total:
            break

    if not kept:
        return pd.DataFrame()

    kept_ids = [c["id"] for c in kept]
    result = pool[pool["id"].isin(kept_ids)].copy()

    # Map scoring metadata directly by ID to avoid index vs column ambiguity
    meta_dict = {c["id"]: c for c in kept}
    result["score"] = [meta_dict[int(i)]["score"] for i in result["id"]]
    result["reasons"] = [meta_dict[int(i)]["reasons"] for i in result["id"]]
    result["category"] = [meta_dict[int(i)]["category"] for i in result["id"]]
    return result.sort_values("score", ascending=False).reset_index(drop=True)


# ============================================================
# VALIDATION & RANKING HELPERS
# ============================================================

def validate_selected_items(df: pd.DataFrame, selected_ids: list[Any]) -> list[int]:
    """
    Validate that item IDs exist in the active SSR DataFrame.
    Filters out missing, corrupted, or non-numeric IDs gracefully.
    Preserves input order.
    """
    if df is None or df.empty or not selected_ids:
        return []

    available_ids = set(df.index if df.index.name == "id" else df["id"])
    valid: list[int] = []
    seen: set[int] = set()

    for raw_id in selected_ids:
        try:
            item_id = int(raw_id)
        except (ValueError, TypeError):
            continue

        if item_id in available_ids and item_id not in seen:
            valid.append(item_id)
            seen.add(item_id)

    return valid


def rank_items_by_relevance(
    df: pd.DataFrame,
    item_ids: list[int],
    mode: str,
    road_kind: str | None = None,
    ai_analysis: dict | None = None,
) -> list[int]:
    """
    Rank a given list of SSR item IDs by relevance score against the project.
    """
    valid_ids = validate_selected_items(df, item_ids)
    if not valid_ids:
        return []

    ranked = []
    for item_id in valid_ids:
        row = df.loc[item_id] if item_id in df.index else df[df["id"] == item_id].iloc[0]
        score, _ = score_item(row, mode, road_kind, ai_analysis)
        ranked.append((item_id, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [item_id for item_id, _ in ranked]


def candidates_to_ai_payload(candidates: pd.DataFrame) -> list[dict]:
    """Trim candidate rows down to essential fields for AI selection."""
    if candidates is None or candidates.empty:
        return []

    return [
        {
            "id": int(row["id"]),
            "chapter": str(row["chapter"]),
            "description": str(row["description"])[:200],
            "unit": str(row["unit"]),
        }
        for _, row in candidates.iterrows()
    ]
