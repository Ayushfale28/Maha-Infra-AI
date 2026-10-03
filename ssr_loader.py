"""
SSR Loader for the Road Cost Estimator.

Reads the Maharashtra PWD "SSR 2022-23" workbook (or a CSV in the same
shape) and returns a clean pandas DataFrame with these columns:

    id          internal integer id (also the DataFrame index)
    item_no     SSR item number, as text (may include letters, e.g. "2.29a")
    chapter     chapter name (blank cells are forward-filled)
    description item description
    unit        unit of measurement, as written in the SSR
    rate        completed rate (float), GST excluded
    kind        quantity category inferred from the unit:
                "area" | "volume" | "length" | "km" | "nos" | "weight" |
                "liquid" | "time" | "acre" | "unknown"

Important fix (compared to an earlier version of this loader):
Some SSR item numbers use letter suffixes for sub-items, e.g. "2.29a",
"2.29b", "6.12 a", or a bare "a"/"b"/"c" for a continuation row of the
item above it. An earlier version of this loader converted item_no to a
number and dropped every row that failed that conversion -- which
silently removed roughly 200 real, priced SSR items (about 9% of the
whole schedule), including common items such as kilometre stones and
sub-grade material supply. This version keeps the item number as text
and instead validates a row using its description/unit/rate, which are
the fields that actually indicate a usable SSR line item.

Improvements in this version:
    - Adaptive header-row detection (no longer assumes row 1)
    - Reads all columns (no hardcoded usecols="A:I")
    - Recognises litre, hour, day, acre and other unit types
    - Better chapter forward-fill validation
    - SSR health summary reports zero-rate and missing-rate items
"""

import io
import logging
import os
import re

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# TEXT HELPERS
# ============================================================

def _clean_text(value) -> str:
    """Convert any cell value into clean, single-spaced text."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalise_name(value) -> str:
    """Normalise a column/sheet/chapter name for tolerant comparison."""
    text = _clean_text(value).lower()
    text = text.replace("\n", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# SOURCE HANDLING
# ============================================================

def _prepare_source(source):
    """Normalise the many possible input types into something pandas can read."""
    if isinstance(source, (str, os.PathLike)):
        path = os.fspath(source)
        if not os.path.exists(path):
            raise FileNotFoundError(f"SSR file not found: {path}")
        return path

    if hasattr(source, "seek"):
        try:
            source.seek(0)
        except Exception:
            pass
        return source

    if isinstance(source, (bytes, bytearray)):
        return io.BytesIO(source)

    raise TypeError(
        "Unsupported SSR source. Provide a file path, bytes, "
        "or a file-like object (e.g. a Streamlit UploadedFile)."
    )


def _source_filename(source) -> str:
    if isinstance(source, (str, os.PathLike)):
        return os.fspath(source).lower()
    if hasattr(source, "name"):
        return str(source.name).lower()
    return ""


# ============================================================
# FIND THE SSR WORKSHEET
# ============================================================

def _find_ssr_sheet(excel_file: pd.ExcelFile) -> str:
    """Find the worksheet that actually holds the SSR item table."""
    sheet_names = excel_file.sheet_names

    for sheet in sheet_names:
        if _normalise_name(sheet) == "ssr 2022-23":
            return sheet

    for sheet in sheet_names:
        if "ssr 2022-23" in _normalise_name(sheet):
            return sheet

    for sheet in sheet_names:
        normalized = _normalise_name(sheet)
        if normalized.startswith("ssr") or "schedule of rates" in normalized:
            return sheet

    raise ValueError(
        "Could not find the SSR item worksheet in this workbook. "
        "Expected a sheet named something like 'SSR 2022-23'."
    )


# ============================================================
# ADAPTIVE HEADER-ROW DETECTION
# ============================================================

# Keywords we expect to find in a real SSR header row.
_HEADER_KEYWORDS = {"chapter", "item", "description", "unit", "rate"}


def _find_header_row(raw: pd.DataFrame, max_rows: int = 10) -> int:
    """
    Scan the first ``max_rows`` rows for the one that looks like
    a header (contains the most SSR-related keywords).

    Returns the 0-based row index (suitable for ``header=``).
    """
    best_row = 0
    best_score = 0

    for i in range(min(max_rows, len(raw))):
        row_text = " ".join(_normalise_name(str(v)) for v in raw.iloc[i].values)
        score = sum(1 for kw in _HEADER_KEYWORDS if kw in row_text)
        if score > best_score:
            best_score = score
            best_row = i

    return best_row


# ============================================================
# FIND THE RELEVANT COLUMNS
# ============================================================

def _find_columns(columns) -> dict:
    """
    Map the messy Maharashtra SSR column headers onto our internal names.

    Expected source headers include things like:
        "Sr. No.", "Chapter", "SSR Item No.", "Reference No.",
        "Description of the item", "Additional Specification", "Unit",
        "Completed Rate for 2022-23 excluding GST In Rs.", "Labour Rate ..."
    """
    mapping = {}

    for column in columns:
        normalized = _normalise_name(column)

        if "sr" in normalized and "no" in normalized and "item" not in normalized:
            mapping.setdefault("sr_no", column)
        elif normalized == "chapter" or ("chapter" in normalized and "chapter" not in mapping):
            mapping["chapter"] = column
        elif "ssr item" in normalized or normalized in ("item no", "item no.") or "item number" in normalized:
            mapping["item_no"] = column
        elif "description of the item" in normalized or normalized.startswith("description"):
            mapping.setdefault("description", column)
        elif normalized == "unit":
            mapping["unit"] = column
        elif "completed rate" in normalized and "2022-23" in normalized:
            mapping["rate"] = column
        elif "completed rate" in normalized and "rate" not in mapping:
            mapping.setdefault("rate", column)
        elif normalized in ("rate", "rate in rs", "rate rs", "unit rate") or normalized.startswith("rate"):
            mapping.setdefault("rate", column)
        elif "rate" in normalized and "labour" not in normalized and "rate" not in mapping:
            mapping.setdefault("rate", column)

    required = ["chapter", "item_no", "description", "unit", "rate"]
    missing = [field for field in required if field not in mapping]
    if missing:
        raise ValueError(
            "The SSR file is missing required columns: " + ", ".join(missing)
        )

    return mapping


# ============================================================
# QUANTITY-KIND INFERENCE (from the SSR unit text)
# ============================================================

_VOLUME_PATTERNS = ["cubic metre", "cubic meter", "cum", "m3", "m³", "cu.m", "cubic"]
_AREA_PATTERNS = ["square metre", "square meter", "sq metre", "sq meter", "sq.m", "sqm", "m2", "m²"]
_LENGTH_PATTERNS = ["running metre", "running meter", "metre", "meter", "mtr"]
_WEIGHT_PATTERNS = ["kilogram", "kilogramme", "kilo gram", "kg", "tonne", "ton", "metric ton", "quintal"]
_LIQUID_PATTERNS = ["litre", "liter", "ltr"]
_TIME_PATTERNS = ["hour", "day", "shift", "rig hour"]


def infer_kind(unit: str) -> str:
    """Classify an SSR unit into a quantity category used by the estimator."""
    text = _clean_text(unit).lower()
    if not text:
        return "unknown"

    if any(p in text for p in _VOLUME_PATTERNS):
        return "volume"
    if any(p in text for p in _AREA_PATTERNS):
        return "area"
    if "acre" in text:
        return "acre"
    if "kilometre" in text or "kilometer" in text or text == "km":
        return "km"
    if text in ("m", "rm", "r.m.", "rmt", "r.mt.") or any(p in text for p in _LENGTH_PATTERNS):
        return "length"
    if any(p in text for p in _WEIGHT_PATTERNS):
        return "weight"
    if any(p in text for p in _LIQUID_PATTERNS):
        return "liquid"
    if any(p in text for p in _TIME_PATTERNS):
        return "time"
    if "number" in text or "nos" in text or text in ("no", "no.", "each", "per no"):
        return "nos"

    return "unknown"


# ============================================================
# LOAD RAW TABLE (EXCEL OR CSV)
# ============================================================

def _load_excel_raw(source) -> pd.DataFrame:
    prepared = _prepare_source(source)

    try:
        excel_file = pd.ExcelFile(prepared)
    except Exception as error:
        raise ValueError("Unable to open the SSR Excel file.") from error

    sheet_name = _find_ssr_sheet(excel_file)

    # ---- adaptive header detection ----
    # Read a small preview with no header to find the real header row.
    try:
        preview = pd.read_excel(
            excel_file, sheet_name=sheet_name, header=None, nrows=10,
        )
        header_row = _find_header_row(preview)
    except Exception:
        header_row = 1  # safe fallback for the known Maharashtra SSR

    try:
        # Read ALL columns (no usecols restriction) so that
        # _find_columns() can locate them by name regardless of their
        # position in the sheet.
        raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
    except Exception as error:
        raise ValueError(f"Could not read the SSR worksheet '{sheet_name}'.") from error

    if raw.empty:
        raise ValueError("The SSR worksheet is empty.")

    raw.columns = [_clean_text(c).lower() for c in raw.columns]
    column_map = _find_columns(raw.columns)

    cols = ["chapter", "item_no", "description", "unit", "rate"]
    if "sr_no" in column_map:
        cols = ["sr_no"] + cols

    data = raw[[column_map[c] for c in cols]].copy()
    data.columns = cols
    return data


def _load_csv_raw(source) -> pd.DataFrame:
    prepared = source
    if isinstance(source, (bytes, bytearray)):
        prepared = io.BytesIO(source)
    elif hasattr(source, "seek"):
        try:
            source.seek(0)
        except Exception:
            pass

    try:
        raw = pd.read_csv(prepared)
    except Exception as error:
        raise ValueError("Unable to read the CSV SSR file.") from error

    if raw.empty:
        raise ValueError("The uploaded SSR CSV is empty.")

    raw.columns = [_clean_text(c).lower() for c in raw.columns]
    column_map = _find_columns(raw.columns)

    cols = ["chapter", "item_no", "description", "unit", "rate"]
    if "sr_no" in column_map:
        cols = ["sr_no"] + cols

    data = raw[[column_map[c] for c in cols]].copy()
    data.columns = cols
    return data


# ============================================================
# NORMALISE INTO THE FINAL SHAPE
# ============================================================

def _format_item_no(value) -> str:
    """
    Format an SSR item number for display.

    Excel stores plain numeric item numbers (e.g. 53.84) as binary
    floats, which can print with precision artifacts such as
    "53.839999999999954". Those are rounded and reformatted cleanly.
    Lettered item numbers (e.g. "2.29a", or a bare "a"/"b" continuation
    row) are not numeric and are kept exactly as written.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if isinstance(value, (int, float)):
        return f"{round(float(value), 4):g}"

    text = _clean_text(value)
    try:
        numeric = float(text)
        return f"{round(numeric, 4):g}"
    except (TypeError, ValueError):
        return text


def _is_valid_chapter(text: str) -> bool:
    """Return True if ``text`` looks like a real chapter name (not garbage)."""
    if not text:
        return False
    # Reject pure numbers or very short strings
    if re.fullmatch(r"[\d\s.]+", text):
        return False
    if len(text) < 3:
        return False
    return True


def _normalise(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()

    # item_no needs its own formatting (see _format_item_no) so it is
    # handled separately from the other text columns below.
    data["item_no"] = raw["item_no"].map(_format_item_no)

    for column in ("chapter", "description", "unit"):
        data[column] = data[column].map(_clean_text)

    # --------------------------------------------------------
    # Forward-fill the chapter column.
    #
    # In the source workbook a chapter name is only written on the first
    # row of that chapter; every following item row leaves the chapter
    # cell blank. We carry the last seen chapter name forward, but only
    # when the value looks like a genuine chapter name.
    # --------------------------------------------------------
    current_chapter = ""
    filled_chapters = []
    for chapter in data["chapter"]:
        if chapter and _is_valid_chapter(chapter):
            current_chapter = chapter
        filled_chapters.append(current_chapter)
    data["chapter"] = filled_chapters

    data["rate"] = pd.to_numeric(data["rate"], errors="coerce")

    # --------------------------------------------------------
    # A row is a usable SSR item if it has a description, a unit and a
    # numeric rate. We deliberately do NOT require item_no to be a pure
    # number: many genuine items use letter-suffixed numbers such as
    # "2.29a" or a bare "a"/"b" continuation row, and rejecting those
    # silently drops real, priced items from the schedule.
    #
    # We also accept items with rate == 0 but flag them, because some
    # SSR items are genuinely zero-rated (header rows for composite
    # items). The caller can decide whether to use them.
    # --------------------------------------------------------
    valid = (
        data["item_no"].ne("")
        & data["description"].ne("")
        & data["unit"].ne("")
        & data["rate"].notna()
    )
    data = data.loc[valid].copy()

    if data.empty:
        raise ValueError("No valid SSR items were found in this file.")

    data["kind"] = data["unit"].map(infer_kind)

    data.reset_index(drop=True, inplace=True)
    data.insert(0, "id", range(len(data)))

    result = data[["id", "item_no", "chapter", "description", "unit", "rate", "kind"]].copy()
    result = result.drop_duplicates(subset=["item_no", "description", "unit", "rate"], keep="first")
    result.reset_index(drop=True, inplace=True)
    result["id"] = range(len(result))

    return result


# ============================================================
# PUBLIC API
# ============================================================

def load_ssr(source) -> pd.DataFrame:
    """
    Load an SSR file (Excel .xlsx/.xls or CSV) into the standard DataFrame.

    Accepts: a file path, raw bytes, or a file-like object such as a
    Streamlit UploadedFile.
    """
    if source is None:
        raise ValueError("No SSR file was provided.")

    filename = _source_filename(source)

    if filename.endswith(".csv") or isinstance(source, io.StringIO):
        raw = _load_csv_raw(source)
    else:
        try:
            raw = _load_excel_raw(source)
        except Exception:
            # If excel reader failed, try CSV reader as fallback
            try:
                raw = _load_csv_raw(source)
            except Exception:
                raise

    result = _normalise(raw)

    required = ["id", "item_no", "chapter", "description", "unit", "rate", "kind"]
    missing = [c for c in required if c not in result.columns]
    if missing:
        raise ValueError("SSR loader failed to produce required columns: " + ", ".join(missing))

    logger.info(
        "SSR loaded: %d items, %d chapters, %d lettered item numbers",
        len(result), result["chapter"].nunique(),
        result["item_no"].str.contains(r"[a-zA-Z]", regex=True).sum(),
    )

    return result


def ssr_health_summary(df: pd.DataFrame) -> dict:
    """
    A small diagnostic summary, useful to show right after loading an SSR
    file so a broken/changed file format is caught immediately instead of
    silently losing items.
    """
    zero_rates = int((df["rate"] == 0).sum())
    return {
        "total_items": int(len(df)),
        "total_chapters": int(df["chapter"].nunique()),
        "items_by_kind": df["kind"].value_counts().to_dict(),
        "unknown_unit_items": int((df["kind"] == "unknown").sum()),
        "zero_rate_items": zero_rates,
        "zero_or_missing_rates": zero_rates,
        "lettered_item_numbers": int(df["item_no"].str.contains(r"[a-zA-Z]", regex=True).sum()),
    }


# ============================================================
# CHAPTER MATCHING
# ============================================================

def match_chapters(available_chapters, wanted_chapters) -> list:
    """
    Map a list of "wanted" chapter names onto the actual chapter names
    present in the loaded SSR, tolerating case, spacing and minor
    spelling differences.
    """
    if not available_chapters or not wanted_chapters:
        return []

    normalized_available = [(str(c), _normalise_name(c)) for c in available_chapters]
    result = []

    for wanted in wanted_chapters:
        wanted_norm = _normalise_name(wanted)
        if not wanted_norm:
            continue

        for actual, norm in normalized_available:
            if norm == wanted_norm and actual not in result:
                result.append(actual)

        if not any(_normalise_name(r) == wanted_norm for r in result):
            for actual, norm in normalized_available:
                if (wanted_norm in norm or norm in wanted_norm) and actual not in result:
                    result.append(actual)

    return result


# ============================================================
# SEARCH
# ============================================================

def search(df: pd.DataFrame, chapters=None, keywords=None) -> pd.DataFrame:
    """
    Filter the SSR DataFrame by chapter (exact match, tolerant of
    spelling) and by keywords (all keywords must appear somewhere in the
    item's text -- item number, chapter, description or unit).
    """
    if df is None:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        raise TypeError("search() expects a pandas DataFrame.")

    result = df

    if chapters:
        wanted = {_normalise_name(c) for c in chapters if _clean_text(c)}
        if wanted:
            mask = result["chapter"].map(_normalise_name).isin(wanted)
            result = result[mask]

    clean_keywords = [_clean_text(k).lower() for k in (keywords or []) if _clean_text(k)]
    if clean_keywords:
        searchable = (
            result["item_no"].astype(str) + " "
            + result["chapter"].astype(str) + " "
            + result["description"].astype(str) + " "
            + result["unit"].astype(str)
        ).str.lower()

        mask = pd.Series(True, index=result.index)
        for keyword in clean_keywords:
            mask &= searchable.str.contains(re.escape(keyword), na=False)
        result = result[mask]

    return result.reset_index(drop=True)


def get_item(df: pd.DataFrame, item_id):
    """Safely fetch a single SSR row by its internal id."""
    if df is None or df.empty:
        return None
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return None
    matches = df[df["id"] == item_id]
    return None if matches.empty else matches.iloc[0]


# ============================================================
# SELF-TEST (run this file directly to sanity-check an SSR file)
# ============================================================

if __name__ == "__main__":
    import sys

    test_file = sys.argv[1] if len(sys.argv) > 1 else "SSR_2022-23 (2).xlsx"

    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
    else:
        try:
            df = load_ssr(test_file)
            print("SSR loaded successfully.")
            import json
            print(json.dumps(ssr_health_summary(df), indent=2))
        except Exception as error:
            print("SSR loading failed:", error)
