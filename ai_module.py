"""
AI backend module for the Road Cost Estimator.

Uses OpenRouter (https://openrouter.ai) over plain HTTP -- no extra heavy SDK
dependency required.

Privacy / security:
    - The end user is NEVER asked for an API key.
    - The key is read only from Streamlit secrets or an environment variable.
    - Model and provider names are never surfaced in user-facing error messages.

Key capabilities:
    - Single and multi-photo analysis with automatic downscaling/compression (Pillow)
    - Schema validation for AI outputs using schemas.py (AnalysisResult)
    - Fallback strategies across free vision & text models
    - Strict candidate-only SSR selection (AI never invents items or rates)
"""

from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from schemas import (
    AnalysisResult,
    DefectObservation,
    SuggestedParameter,
    SuggestedWork,
    StructuralConcept,
)

BASE_DIR = Path(__file__).resolve().parent
PHOTO_PROMPT_PATH = BASE_DIR / "road_photo_prompt.xml"
CHAT_PROMPT_PATH = BASE_DIR / "chat_prompt.xml"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_VISION_MODELS = [
    "dots-studio/dots-3-note-preview:free",
    "openrouter/free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3.8-27b:free",
]

DEFAULT_TEXT_MODELS = [
    "dots-studio/dots-3-note-preview:free",
    "qwen/qwen3.8-27b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
]

_env_models = os.getenv("OPENROUTER_MODELS", "").strip()
VISION_MODELS = [m.strip() for m in _env_models.split(",") if m.strip()] or DEFAULT_VISION_MODELS

SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Road Cost Estimator")


# ============================================================
# API KEY MANAGEMENT
# ============================================================

def get_api_key() -> str:
    """Retrieve API key securely from Streamlit session state, secrets, environment, or direct local config files."""
    # 1. Check Streamlit session state (user UI input)
    try:
        import streamlit as st
        if "api_key" in st.session_state and st.session_state["api_key"]:
            return str(st.session_state["api_key"]).strip()
        if "OPENROUTER_API_KEY" in st.session_state and st.session_state["OPENROUTER_API_KEY"]:
            return str(st.session_state["OPENROUTER_API_KEY"]).strip()
    except Exception:
        pass

    # 2. Check Streamlit secrets
    try:
        import streamlit as st
        key = st.secrets.get("OPENROUTER_API_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        pass

    # 3. Check environment variable
    env_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key

    # 4. Check workspace .streamlit/secrets.toml directly (independent of current working directory)
    try:
        secrets_file = BASE_DIR / ".streamlit" / "secrets.toml"
        if secrets_file.exists():
            content = secrets_file.read_text(encoding="utf-8")
            import re
            m = re.search(r'OPENROUTER_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
            if m and m.group(1).strip():
                return m.group(1).strip()
    except Exception:
        pass

    # 5. Check workspace .env directly
    try:
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            import re
            m = re.search(r'OPENROUTER_API_KEY\s*=\s*["\']?([^"\'\r\n]+)["\']?', content)
            if m and m.group(1).strip():
                return m.group(1).strip()
    except Exception:
        pass

    # 6. Check user home .streamlit/secrets.toml
    try:
        home_secrets = Path.home() / ".streamlit" / "secrets.toml"
        if home_secrets.exists():
            content = home_secrets.read_text(encoding="utf-8")
            import re
            m = re.search(r'OPENROUTER_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
            if m and m.group(1).strip():
                return m.group(1).strip()
    except Exception:
        pass

    return ""


def ai_is_configured() -> bool:
    """Check if an API key is available for AI features."""
    return bool(get_api_key())


# ============================================================
# PROMPT LOADING
# ============================================================

def load_prompt(path: Path) -> str:
    """Load prompt file text safely."""
    if not path.exists():
        raise FileNotFoundError(f"Required AI prompt file is missing: {path.name}")
    return path.read_text(encoding="utf-8")


# ============================================================
# IMAGE PREPROCESSING & RESIZING
# ============================================================

def resize_image_if_needed(
    image_bytes: bytes,
    max_dimension: int = 1600,
    quality: int = 85,
) -> tuple[bytes, str]:
    """
    Downscale and compress high-resolution photos before sending over HTTP.
    Reduces latency, token usage, and avoids payload limit rejections.
    Returns (processed_bytes, mime_type).
    """
    if not image_bytes:
        return image_bytes, "image/jpeg"

    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / float(max(w, h))
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            if img.mode in ("RGBA", "P"):
                img.save(output, format="PNG", optimize=True)
                return output.getvalue(), "image/png"
            else:
                img = img.convert("RGB")
                img.save(output, format="JPEG", quality=quality, optimize=True)
                return output.getvalue(), "image/jpeg"
    except Exception:
        # Graceful fallback: return original bytes
        return image_bytes, "image/jpeg"


def _image_to_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Resize image and encode to base64 Data URL."""
    if not image_bytes:
        raise ValueError("No image data was provided.")

    processed_bytes, safe_mime = resize_image_if_needed(image_bytes)
    encoded = base64.b64encode(processed_bytes).decode("utf-8")
    return f"data:{safe_mime};base64,{encoded}"


# ============================================================
# JSON CLEANING & PARSING
# ============================================================

def clean_json_response(text: str) -> str:
    """Strip markdown markers and find outermost JSON braces."""
    text = (text or "").strip()
    if not text:
        return ""

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    first_brace = text.find("{")
    if first_brace >= 0:
        last_brace = text.rfind("}")
        if last_brace > first_brace:
            text = text[first_brace : last_brace + 1]

    return text.strip()


def parse_json_response(text: str) -> dict:
    """Parse JSON string safely."""
    cleaned = clean_json_response(text)
    if not cleaned:
        raise RuntimeError("AI analysis returned no valid response text.")

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(cleaned)
        except Exception as error:
            raise RuntimeError("AI analysis returned an invalid JSON response.") from error

    if not isinstance(result, dict):
        raise RuntimeError("AI analysis returned an unexpected response format.")

    return result


# ============================================================
# LOW-LEVEL HTTP CALLS WITH FALLBACK
# ============================================================

def _call_model(
    model: str,
    messages: list[dict],
    system_prompt: str,
    temperature: float,
    json_mode: bool,
) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("AI service is not configured.")

    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload: dict[str, Any] = {
        "model": model,
        "messages": payload_messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if SITE_URL:
        headers["HTTP-Referer"] = SITE_URL
    if SITE_NAME:
        headers["X-Title"] = SITE_NAME

    request = urllib.request.Request(OPENROUTER_URL, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        try:
            err_msg = error.read().decode("utf-8", errors="replace")
        except Exception:
            err_msg = ""
        raise RuntimeError(f"OpenRouter HTTP error ({model}): {error.code} {err_msg[:400]}") from error
    except Exception as error:
        raise RuntimeError(f"OpenRouter connection error ({model}): {repr(error)}") from error

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenRouter returned invalid JSON structure.") from error

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("OpenRouter response lacked expected message content.") from error

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            elif isinstance(part, str):
                parts.append(part)
        content = "\n".join(parts)

    return str(content).strip()


def _request_with_fallback(
    messages: list[dict],
    system_prompt: str,
    temperature: float = 0.2,
    json_mode: bool = True,
    models: list[str] | None = None,
) -> str:
    """
    Try models in order with graceful fallbacks.
    Tries with json_mode first, then retries without json_mode for models that reject the parameter.
    """
    models = models or VISION_MODELS
    last_error: Exception | None = None

    for model in models:
        attempts = [json_mode, False] if json_mode else [False]
        for attempt_json_mode in dict.fromkeys(attempts):
            try:
                return _call_model(model, messages, system_prompt, temperature, attempt_json_mode)
            except Exception as error:
                last_error = error
                continue

    if last_error:
        raise last_error
    raise RuntimeError("AI request failed across all available models.")


# ============================================================
# PHOTO ANALYSIS WITH SCHEMA VALIDATION
# ============================================================

def unavailable_result(reason: str = "Automatic photo analysis was unavailable.") -> dict:
    """Produce a standard, guaranteed-valid AnalysisResult dict on error."""
    res = AnalysisResult(
        photo_quality="poor",
        photo_quality_reason="analysis unavailable",
        site_type="unclear",
        site_type_confidence="low",
        recommended_mode="unclear",
        recommended_mode_confidence="low",
        recommended_mode_reason=reason,
        road_type="unclear",
        road_type_confidence="low",
        surface_condition="Automatic analysis was unavailable.",
        limitations="Automatic photo analysis could not be completed. Manual site review is required.",
    )
    return res.to_dict()


def analyze_photo(image_bytes: bytes, mime_type: str = "image/jpeg", note: str = "") -> dict:
    """
    Analyze one road/site photograph and validate the result with schemas.py.
    Returns a standardized dictionary conforming to AnalysisResult schema.
    """
    if not image_bytes:
        raise ValueError("No image data was provided.")

    system_prompt = load_prompt(PHOTO_PROMPT_PATH)
    user_text = (
        "Analyse this road/site photograph according to the instructions provided. "
        "Return ONLY the required JSON object."
    )
    if note and note.strip():
        user_text += f"\n\nEngineer's additional note: {note.strip()}"

    image_url = _image_to_data_url(image_bytes, mime_type)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    }]

    raw_text = _request_with_fallback(messages, system_prompt, temperature=0.2, json_mode=True)
    raw_dict = parse_json_response(raw_text)

    # Validate and standardize against AnalysisResult schema
    validated = AnalysisResult.from_dict(raw_dict)
    return validated.to_dict()


def analyze_photos(photos: list[dict], note: str = "") -> list[dict]:
    """
    Analyze multiple photos individually.
    Each item in photos: {"name": str, "bytes": bytes, "mime": str}.
    Returns [{"name": str, "result": dict}, ...] with guaranteed schema.
    """
    results: list[dict] = []
    for photo in photos:
        name = photo.get("name", "Photo")
        b = photo.get("bytes")
        mime = photo.get("mime", "image/jpeg")

        try:
            if not b:
                raise ValueError("Empty image data")
            res_dict = analyze_photo(b, mime, note)
        except Exception as error:
            res_dict = unavailable_result(f"Analysis failed for {name}: {str(error)}")

        results.append({"name": name, "result": res_dict})
    return results


# ============================================================
# CHAT ASSISTANT
# ============================================================

def chat_reply(
    history: list[dict],
    analysis: dict | None = None,
    photos: list[dict] | None = None,
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
    project_context: dict | None = None,
) -> str:
    """
    Generate an authoritative civil engineering response from conversation history,
    optional site photos, and live active project context (measurements, estimate, BOQ).
    """
    try:
        system_prompt = load_prompt(CHAT_PROMPT_PATH)
        if analysis:
            system_prompt += "\n\n<photo_analysis>\n" + json.dumps(analysis, ensure_ascii=False, indent=2) + "\n</photo_analysis>"

        if project_context:
            system_prompt += "\n\n<active_project_context>\n" + json.dumps(project_context, ensure_ascii=False, indent=2) + "\n</active_project_context>"
            system_prompt += "\n\nUse the active project context above to provide highly specific, accurate answers regarding dimensions, costs, quantities, and SSR items whenever relevant."

        messages: list[dict] = []
        for index, message in enumerate(history or []):
            role = "assistant" if message.get("role") == "assistant" else "user"
            content = message.get("content") or "Please continue."

            # Attach photos to the first user message if available
            if index == 0 and role == "user":
                content_parts: list[dict] = [{"type": "text", "text": content}]

                # Handle multi-photo list if provided
                if photos:
                    for p in photos[:4]:  # limit to max 4 photos for context window
                        pb = p.get("bytes")
                        pm = p.get("mime", "image/jpeg")
                        if pb:
                            url = _image_to_data_url(pb, pm)
                            content_parts.append({"type": "image_url", "image_url": {"url": url}})
                elif image_bytes:
                    url = _image_to_data_url(image_bytes, mime_type)
                    content_parts.append({"type": "image_url", "image_url": {"url": url}})

                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": role, "content": content})

        if not messages:
            messages = [{"role": "user", "content": "Help me plan this road project."}]

        answer = _request_with_fallback(
            messages,
            system_prompt,
            temperature=0.4,
            json_mode=False,
            models=DEFAULT_TEXT_MODELS,
        )
        return answer or "I could not generate a response. Please try again."

    except Exception as error:
        if not get_api_key():
            return "AI service is not configured. Please ensure OPENROUTER_API_KEY is configured in your settings."
        err_msg = str(error)
        return f"Civil AI Assistant encountered a temporary connectivity delay ({err_msg[:120]}). Please send your question again."


# ============================================================
# PROJECT SPECIFICATION GENERATOR
# ============================================================

_SPEC_SYSTEM_PROMPT = """You are an AI road estimation planning assistant.

Your job is to understand a road construction or repair project and
identify the types of work that may be required.

RULES:
1. Never invent SSR item numbers.
2. Never invent SSR rates.
3. Never invent quantities.
4. Do not provide a final cost.
5. Measurements supplied by the user must be preserved exactly, never changed.
6. Only recommend work categories reasonably supported by the given information.
7. Return ONLY valid JSON, matching the schema you are given.
"""


def generate_project_specification(
    mode: str,
    road_type: str | None,
    length_m: float,
    width_m: float,
    thickness_mm: float,
    soil_condition: str = "",
    traffic_type: str = "",
    drainage_required: str = "",
    lead_distance_km: float = 0.0,
    additional_prompt: str = "",
    photo_analysis: dict | None = None,
) -> dict:
    """Derive functional work categories from project parameters and site analysis."""
    project_info: dict[str, Any] = {
        "mode": mode,
        "road_type": road_type or "unspecified",
        "length_m": length_m,
        "width_m": width_m,
        "thickness_mm": thickness_mm,
        "soil_condition": soil_condition,
        "traffic_type": traffic_type,
        "drainage_required": drainage_required,
        "lead_distance_km": lead_distance_km,
        "additional_prompt": additional_prompt,
    }
    if photo_analysis:
        project_info["photo_analysis"] = photo_analysis

    user_prompt = f"""Analyse this road project and identify relevant work categories
(for example: site preparation, excavation, subgrade, sub-base, base
course, concrete pavement, bituminous pavement, joints, drainage, road
furniture, road safety, maintenance, pothole repair). Only recommend
categories reasonably supported by the information below.

PROJECT INFORMATION:
{json.dumps(project_info, ensure_ascii=False, indent=2)}

Return exactly this JSON shape:
{{
  "project_type": "",
  "road_type": "",
  "work_categories": [
    {{"category": "", "reason": "", "search_keywords": []}}
  ],
  "additional_requirements": [],
  "missing_information": []
}}"""

    text = _request_with_fallback(
        [{"role": "user", "content": user_prompt}],
        system_prompt=_SPEC_SYSTEM_PROMPT,
        temperature=0.1,
        json_mode=True,
    )
    return parse_json_response(text)


# ============================================================
# SSR ITEM SELECTION (AI REFERS ONLY TO RETRIEVED CANDIDATES)
# ============================================================

_SELECTOR_SYSTEM_PROMPT = """You are an SSR item selection assistant for a road estimation application.

You will receive a project specification and a list of SSR items that
were already retrieved from the application's real SSR database.

STRICT RULES:
- You may ONLY select IDs from the supplied candidate list.
- Never invent an item, an item number, a rate, or a description.
- Do not calculate quantities or costs.
- Select only items reasonably required for this project; if uncertain
  about an item, leave it out.
- Return ONLY valid JSON, matching the schema you are given.
"""


def select_ssr_items(project_specification: dict, candidate_items: list[dict]) -> dict:
    """
    Select relevant items strictly from candidate_items.
    Returns {"selected_ids": [...], "reasons": {id: reason}}.
    """
    if not candidate_items:
        return {"selected_ids": [], "reasons": {}}

    user_prompt = f"""PROJECT SPECIFICATION:
{json.dumps(project_specification, ensure_ascii=False, indent=2)}

CANDIDATE SSR ITEMS (only these may be selected):
{json.dumps(candidate_items, ensure_ascii=False, indent=2)}

Return exactly this JSON shape:
{{
  "selected_items": [
    {{"id": 0, "reason": "", "confidence": "low | medium | high"}}
  ]
}}"""

    text = _request_with_fallback(
        [{"role": "user", "content": user_prompt}],
        system_prompt=_SELECTOR_SYSTEM_PROMPT,
        temperature=0.1,
        json_mode=True,
    )
    result = parse_json_response(text)

    valid_ids = {c["id"] for c in candidate_items}
    selected_ids = []
    reasons = {}

    for item in result.get("selected_items", []) or []:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if item_id in valid_ids:
            selected_ids.append(item_id)
            reasons[item_id] = str(item.get("reason", ""))

    return {"selected_ids": selected_ids, "reasons": reasons}


# ============================================================
# AI STRUCTURAL CONCEPT & CAPEX PLANNER
# ============================================================

def generate_structural_concept(
    project_title: str,
    building_type: str,
    built_up_area_sqft: float,
    floors: int = 2,
    soil_type: str = "Medium Hard Murum / Clay",
    special_requirements: str = "",
) -> StructuralConcept:
    """
    Generate preliminary structural dimensions, material consumption,
    and capex expenditure based on IS 456:2000 / NBC guidelines and AI insights.
    """
    safe_sqft = max(100.0, float(built_up_area_sqft))
    safe_floors = max(1, int(floors))
    area_sqm = round(safe_sqft / 10.7639, 2)
    floors_text = f"Ground + {safe_floors - 1} Floors (Total {safe_floors} storeys)" if safe_floors > 1 else "Ground Floor Structure"

    # IS 456 Preliminary Sizing Rules
    if safe_floors <= 2:
        col_size = "230 mm × 380 mm (9\" × 15\") with 4-#16 + 2-#12 TMT bars"
        beam_size = "230 mm × 380 mm (9\" × 15\") with #16 & #12 longitudinal bars"
        slab_thick = "125 mm (5\") Two-Way Slab with #8 @ 150mm c/c"
        grid_spacing = "3.5 m × 4.2 m (11.5 ft × 13.8 ft regular column grid)"
        foundation = "Isolated Trapezoidal Pad Footing (1.8m × 1.8m × 0.45m depth at -1.5m GL)"
        concrete_grade = "M-25 (Characteristic strength 25 N/mm²)"
        steel_grade = "Fe 500D TMT High Ductility Rebar"
        steel_ratio = 82.0  # kg per m3 of concrete
        cost_per_sqft = 1750.0
    elif safe_floors <= 4:
        col_size = "230 mm × 450 mm (9\" × 18\") with 6-#16 + 2-#20 TMT bars"
        beam_size = "230 mm × 450 mm (9\" × 18\") with #20 & #16 longitudinal bars"
        slab_thick = "135 mm (5.3\") Slab with #10 @ 150mm c/c"
        grid_spacing = "3.8 m × 4.5 m (12.5 ft × 14.8 ft regular column grid)"
        foundation = "Raft Foundation or Combined Footing with strap beams at -2.0m GL"
        concrete_grade = "M-25 / M-30"
        steel_grade = "Fe 500D TMT Rebar"
        steel_ratio = 92.0
        cost_per_sqft = 1950.0
    else:
        col_size = "300 mm × 600 mm (12\" × 24\") with 8-#20 + 4-#25 TMT bars"
        beam_size = "300 mm × 500 mm (12\" × 20\") heavy structural frame"
        slab_thick = "150 mm (6\") Two-Way Slab panel"
        grid_spacing = "4.2 m × 5.0 m (13.8 ft × 16.4 ft structural grid)"
        foundation = "Bored Cast-in-Situ Pile Foundation / Thick Raft on firm strata"
        concrete_grade = "M-30 (Characteristic strength 30 N/mm²)"
        steel_grade = "Fe 500D / Fe 550D TMT Rebar"
        steel_ratio = 105.0
        cost_per_sqft = 2250.0

    # Adjust for soil condition
    soil_l = soil_type.lower()
    if "black cotton" in soil_l or "soft" in soil_l:
        foundation = "Under-reamed Pile Foundation or Deep Raft (to prevent swelling/shrinkage settlement)"

    # Deterministic Material Consumption
    concrete_m3 = round(area_sqm * 0.039, 2)
    steel_tonnes = round((concrete_m3 * steel_ratio) / 1000.0, 2)
    # Cement: ~7.8 bags per m3 concrete + ~1.6 bags per m2 finishing/masonry
    cement_bags = int(round(concrete_m3 * 7.8 + area_sqm * 1.5))
    # Sand: ~0.45 m3 per m3 concrete / 2.83 (brass)
    sand_brass = round((concrete_m3 * 0.45 + area_sqm * 0.04) / 2.83, 1)
    # Aggregate: ~0.85 m3 per m3 concrete / 2.83
    agg_brass = round((concrete_m3 * 0.85) / 2.83, 1)

    # Capex Breakdown (Maharashtra PWD benchmark ratios)
    total_cost = round(safe_sqft * cost_per_sqft, 2)
    substructure_cost = round(total_cost * 0.14, 2)
    superstructure_cost = round(total_cost * 0.33, 2)
    masonry_plaster_cost = round(total_cost * 0.18, 2)
    finishing_cost = round(total_cost * 0.19, 2)
    mep_cost = round(total_cost * 0.16, 2)

    # Baseline engineering guidelines
    guidelines = [
        f"Concrete grade {concrete_grade} recommended with maximum water-cement ratio 0.45 for durability (IS 456:2000 Cl 8.2).",
        f"Fe 500D rebar provides superior elongation (>16%) critical for seismic resistance in Zone III/IV.",
        f"Minimum clear cover: Footings 50mm, Columns 40mm, Beams 25mm, Slabs 20mm.",
        f"Ensure plinth level is maintained at minimum +600 mm (+2.0 ft) above adjacent natural ground level / road crown.",
        f"Anti-termite treatment with Chlorpyrifos 20% EC recommended along foundation trenches and plinth backfill.",
    ]
    if "black cotton" in soil_l:
        guidelines.append("Black cotton soil requires CNS (Cohesive Non-Swelling) cushion of 1.0m thickness below footing bed.")

    summary = (
        f"Preliminary structural scheme for a {building_type} ({floors_text}) with {safe_sqft:,.0f} sq.ft "
        f"built-up area. Framed RCC system with {col_size.split(' with')[0]} columns and {beam_size.split(' with')[0]} "
        f"beams. Estimated primary civil capital expenditure: ₹{total_cost / 1e5:.2f} Lakhs (₹{total_cost / 1e7:.2f} Cr)."
    )

    # If AI API key is configured, query LLM for richer contextual advisories
    if ai_is_configured():
        prompt = f"""Act as a Chief Structural Engineer under Maharashtra PWD.
Provide structural engineering recommendations for:
Project: {project_title or 'Proposed Civil Structure'}
Type: {building_type}
Built-up Area: {safe_sqft} sq.ft ({area_sqm} m²)
Floors: {floors_text}
Soil: {soil_type}
Special Notes: {special_requirements or 'None'}

Return a JSON with:
{{
  "engineering_guidelines": ["point 1", "point 2", "point 3", "point 4"],
  "structural_concept_notes": "2-3 concise sentences on structural layout and load path"
}}"""
        try:
            raw_text = _request_with_fallback(
                [{"role": "user", "content": prompt}],
                system_prompt="You are a senior PWD civil structural engineering expert. Output valid JSON only.",
                temperature=0.2,
                json_mode=True,
            )
            parsed = parse_json_response(raw_text)
            if isinstance(parsed, dict):
                ai_points = parsed.get("engineering_guidelines")
                if isinstance(ai_points, list) and len(ai_points) >= 2:
                    guidelines = [str(p) for p in ai_points[:6]]
                ai_notes = parsed.get("structural_concept_notes")
                if ai_notes and isinstance(ai_notes, str):
                    summary = f"{summary} {ai_notes.strip()}"
        except Exception:
            pass  # Safe fallback to deterministic rules

    return StructuralConcept(
        project_title=project_title or f"Structural Concept ({building_type})",
        building_type=building_type,
        built_up_area_sqft=safe_sqft,
        built_up_area_sqm=area_sqm,
        floors_text=floors_text,
        foundation_concept=foundation,
        column_grid_spacing=grid_spacing,
        column_size=col_size,
        beam_size=beam_size,
        slab_thickness=slab_thick,
        concrete_grade=concrete_grade,
        steel_grade=steel_grade,
        estimated_concrete_m3=concrete_m3,
        estimated_steel_tonnes=steel_tonnes,
        estimated_cement_bags=cement_bags,
        estimated_sand_brass=sand_brass,
        estimated_aggregate_brass=agg_brass,
        cost_substructure=substructure_cost,
        cost_superstructure_rcc=superstructure_cost,
        cost_masonry_plaster=masonry_plaster_cost,
        cost_finishing_flooring_doors=finishing_cost,
        cost_plumbing_electrical=mep_cost,
        cost_total_estimated=total_cost,
        engineering_guidelines=guidelines,
        raw_idea_summary=summary,
    )

