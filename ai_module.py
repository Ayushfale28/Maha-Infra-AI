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

from schemas import AnalysisResult, DefectObservation, SuggestedParameter, SuggestedWork

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
    """Retrieve API key securely from Streamlit secrets, session state, or environment."""
    try:
        import streamlit as st
        # Check session state (sidebar input if provided)
        if "api_key" in st.session_state and st.session_state["api_key"]:
            return str(st.session_state["api_key"]).strip()
        key = st.secrets.get("OPENROUTER_API_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        pass

    return os.getenv("OPENROUTER_API_KEY", "").strip()


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
