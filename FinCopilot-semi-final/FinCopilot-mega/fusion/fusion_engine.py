"""
fusion/fusion_engine.py
────────────────────────
Deterministic fusion layer that merges Regex-based and LLM-based
receipt extraction results into a single, higher-quality output.

The returned dictionary is fully compatible with the existing API
response schema — no keys are added or removed from the public
contract.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Tax keywords whose presence in raw text means the regex tax is trustworthy
_SPECIFIC_TAX_KEYWORDS: list[str] = ["cgst", "sgst", "igst", "vat"]

# Regex confidence baseline when a field was successfully extracted
_REGEX_BASE_CONFIDENCE: float = 0.80
_REGEX_NULL_CONFIDENCE: float = 0.0

# Amount tolerance for "both agree"
_AMOUNT_TOLERANCE: float = 0.01

# Margin by which LLM vendor score must exceed regex to override it
_VENDOR_PREFERENCE_MARGIN: float = 0.20

# ── Vendor scoring heuristics ────────────────────────────────────────────────

# Words that positively suggest a business/merchant name.
# NOTE: "market", "mall", "shop", "mobile" removed — they appear in addresses too.
# NOTE: legal suffixes (pvt, ltd, …) removed — handled by _SUFFIX_ONLY_TOKENS guard.
_BUSINESS_POSITIVE_WORDS: frozenset[str] = frozenset({
    "store", "mart", "supermarket", "hypermarket",
    "cafe", "coffee", "tea", "bakery", "bakers",
    "restaurant", "eatery", "kitchen", "diner", "bistro", "grill",
    "pizza", "burger", "hotel", "lodge", "inn", "resort",
    "pharmacy", "chemist", "medical", "clinic", "hospital", "health",
    "electronics", "digital", "tech", "solutions",
    "fashion", "apparel", "garments", "clothing", "boutique", "wear",
    "sports", "fitness", "gym",
    "fresh", "foods", "organic", "dairy",
    "hardware", "tools", "auto", "motors", "garage",
    "salon", "spa", "beauty",
    "travels", "tours", "cargo", "logistics",
    "jewellers", "jewels", "gold", "diamonds",
    "books", "stationery", "prints", "publishing",
    "optical", "vision",
    "petrol", "fuel",
})

# Address/location indicator substrings checked with `in lowered`.
# Broader than before: includes directional words, plaza/mall/shop,
# floor references, junction, gate, circle, estate, office, unit etc.
_ADDRESS_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "road", "rd", "street", "st", "lane", "ln",
    "avenue", "ave", "boulevard", "blvd", "highway", "hwy",
    "society", "colony", "nagar", "layout", "extension",
    "floor", "fl", "complex", "compound",
    "apartment", "apt", "flat", "plot",
    "block", "building", "bldg", "tower",
    "shop no", "shop#", "opp", "near",
    "sector", "phase", "area", "locality",
    "taluka", "district", "tehsil",
    "pin", "pincode", "zip", "postal",
    "city", "town", "village",
    "state", "country",
    "gst", "gstin", "gst no", "cin",
    "phone", "mobile", "tel", "fax", "email",
    "invoice", "bill no", "bill#", "receipt",
    "date", "time",
    "counter", "table", "dine", "take",
})

# Compiled pattern: detects patterns clearly not in a business name
_RE_PHONE = re.compile(r"\b\d[\d\s\-]{7,}\d\b")           # phone-like digit runs
_RE_PIN   = re.compile(r"\b\d{6}\b")                       # 6-digit PIN codes
_RE_GST   = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1,2}\d[Z][A-Z\d]\b")  # GST format
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# Exact strings that are definitely NOT merchant names
_VENDOR_EXACT_REJECT: frozenset[str] = frozenset({
    "unknown", "n/a", "na", "none", "null",
    "tax invoice", "invoice", "receipt", "bill", "bill of supply",
    "cash memo", "duplicate", "original", "customer copy",
    "gst invoice", "retail invoice", "credit note", "debit note",
})

# Suffix-only tokens that are not stand-alone vendor names
_SUFFIX_ONLY_TOKENS: frozenset[str] = frozenset({
    "pvt", "ltd", "llp", "inc", "corp", "co", "llc",
})


def _score_vendor_string(candidate: str | None) -> float:
    """
    Evaluate how likely *candidate* is to be a merchant/business name.

    Returns a float in [0.0, 1.0]:
        0.0  →  definitely not a vendor (empty, address, GST number, …)
        1.0  →  highly likely to be a merchant name

    The score is built from generalised heuristics — no merchant names
    or receipt-format specifics are hardcoded.
    """
    if not candidate or not candidate.strip():
        return 0.0

    text = candidate.strip()
    lowered = text.lower()

    # ── Exact-match hard reject ───────────────────────────────────────────
    if lowered in _VENDOR_EXACT_REJECT:
        return 0.0

    # ── Pattern-based hard disqualifiers ─────────────────────────────────
    if _RE_GST.search(text):
        return 0.0
    if _RE_EMAIL.search(text):
        return 0.0

    # Strings that are mostly digits (phone numbers, GST IDs, PIN codes)
    digit_count = sum(c.isdigit() for c in text)
    alpha_count = sum(c.isalpha() for c in text)
    total_nonws = max(len(text.replace(" ", "")), 1)

    if digit_count / total_nonws > 0.55:
        return 0.0

    # 6-digit PIN or long phone-like run = address fragment, near-zero
    if _RE_PIN.search(text) or _RE_PHONE.search(text):
        return 0.05

    # ── Pre-compute address evidence count ────────────────────────────────
    # Count address/location indicator hits once; used by multiple signals.
    address_hits = sum(
        1 for neg in _ADDRESS_NEGATIVE_WORDS if neg in lowered
    )

    # Document-header words are also very strong negative indicators
    doc_word_hits = sum(
        1 for kw in ("invoice", "bill", "receipt", "memo") if kw in lowered
    )
    total_negative_hits = address_hits + doc_word_hits

    # ── Leading-digit flag ────────────────────────────────────────────────
    # House/shop/building numbers at the start are a strong address signal.
    # e.g. "12B MG Road", "Shop 4, Ground Floor"
    leading_digit = bool(re.match(r"^\d", text))

    # ── Start accumulating score ──────────────────────────────────────────
    score: float = 0.5  # neutral baseline

    # ── Leading-digit penalty ─────────────────────────────────────────────
    if leading_digit:
        score -= 0.30

    # ── Length signal ─────────────────────────────────────────────────────
    length = len(text)
    if length < 2:                      # single char
        score -= 0.45
    elif length < 4:                    # very short
        score -= 0.30
    elif 4 <= length <= 50:             # ideal business-name range
        score += 0.10
    elif length > 80:                   # suspiciously long = address block
        score -= 0.25

    # ── Alpha ratio signal ────────────────────────────────────────────────
    alpha_ratio = alpha_count / total_nonws
    if alpha_ratio >= 0.80:
        score += 0.15
    elif alpha_ratio >= 0.60:
        score += 0.05
    elif alpha_ratio < 0.40:
        score -= 0.20

    # ── Case signal — suppressed when address evidence is present ─────────
    # Addresses are often printed in title/upper case too ("Near Bus Stand"),
    # so the bonus only fires when there is NO address evidence at all.
    words = text.split()
    if words and total_negative_hits == 0:
        upper_words = sum(1 for w in words if w.isupper() and len(w) > 1)
        title_words = sum(1 for w in words if w.istitle())
        dominant_case = (upper_words + title_words) / len(words)
        if dominant_case >= 0.70:
            score += 0.10

    # ── Suffix-only guard ─────────────────────────────────────────────────
    # Strings made entirely of legal suffixes ("Pvt Ltd") with no company
    # body are not reliable vendor names on their own.
    tokens = re.findall(r"[a-z]+", lowered)
    non_suffix_tokens = [t for t in tokens if t not in _SUFFIX_ONLY_TOKENS]
    if tokens and not non_suffix_tokens:
        score -= 0.30

    # ── Positive business-word signal ─────────────────────────────────────
    business_hits = sum(1 for t in tokens if t in _BUSINESS_POSITIVE_WORDS)
    if business_hits >= 2:
        score += 0.20
    elif business_hits == 1:
        score += 0.12

    # ── Comma / multiple-line fragments (address proxy) ───────────────────
    comma_count = text.count(",")
    if comma_count >= 2:
        score -= 0.20
    elif comma_count == 1:
        score -= 0.08

    # ── Cumulative address penalty (quadratic scaling) ────────────────────
    # Each additional address/document indicator compounds the penalty so
    # strings with many hits (e.g. "Shop 4, 2nd Floor, MG Road, Near Stand")
    # are pushed firmly toward zero.
    # Formula: n*(n+1)/2 * 0.12  →  1 hit: 0.12 | 2: 0.36 | 3: 0.72 | 4+: capped
    if total_negative_hits > 0:
        cumulative_penalty = min(
            (total_negative_hits * (total_negative_hits + 1) / 2) * 0.12,
            0.80,   # hard cap so score always clamps cleanly to 0.0
        )
        score -= cumulative_penalty

    # ── Genuine business name reward ──────────────────────────────────────
    # A real merchant name typically has 2–5 alphabetic words, no leading
    # digit, and no address or document-header keywords.
    alpha_word_count = sum(1 for w in words if w.isalpha())
    if (
        2 <= alpha_word_count <= 5
        and not leading_digit
        and total_negative_hits == 0
    ):
        score += 0.15

    # ── Word count: very long strings are typically addresses ──────────────
    word_count = len(words)
    if word_count > 8:
        score -= 0.20
    elif word_count > 5:
        score -= 0.08

    return round(max(0.0, min(1.0, score)), 3)


# ── Remaining shared helpers ─────────────────────────────────────────────────

def _has_specific_tax_keywords(raw_text: str) -> bool:
    """Return True if the raw OCR text contains CGST/SGST/IGST/VAT."""
    lowered = raw_text.lower()
    return any(kw in lowered for kw in _SPECIFIC_TAX_KEYWORDS)


def _is_valid_iso_date(date_str: str | None) -> bool:
    """Return True if the string looks like a valid ISO date (YYYY-MM-DD)."""
    if not date_str:
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str.strip()))


def _regex_field_confidence(value: Any, *, is_numeric: bool = False) -> float:
    """Derive a heuristic confidence for a regex-extracted field."""
    if value is None:
        return _REGEX_NULL_CONFIDENCE
    if is_numeric:
        # Regex found a number — 0.0 means it fell through to the fallback
        return _REGEX_BASE_CONFIDENCE if float(value) > 0 else _REGEX_NULL_CONFIDENCE
    # Non-numeric: any truthy string counts
    if isinstance(value, str) and not value.strip():
        return _REGEX_NULL_CONFIDENCE
    return _REGEX_BASE_CONFIDENCE


def _llm_field_confidence(llm_result: dict[str, Any], field: str) -> float:
    """Read a per-field confidence from the LLM result, defaulting to 0.0."""
    conf = llm_result.get("confidence")
    if not isinstance(conf, dict):
        return 0.0
    val = conf.get(field)
    if val is None:
        return 0.0
    try:
        return max(0.0, min(1.0, float(val)))
    except (ValueError, TypeError):
        return 0.0


# ── Main Fusion Function ────────────────────────────────────────────────────

def merge_extractions(
    regex_result: dict[str, Any],
    llm_result: dict[str, Any],
    raw_text: str = "",
) -> dict[str, Any]:
    """
    Merge the Regex extraction and the Groq LLM extraction into one
    fused result using deterministic decision rules.

    Args:
        regex_result: Dictionary from ``ExtractedBill.to_dict()``.
        llm_result:   Dictionary from ``extract_receipt_with_llm()``.
        raw_text:     The original OCR text (used for tax-keyword check).

    Returns:
        A dictionary with keys:
            vendor, amount, tax, date, invoice_number, payment_method,
            category, confidence (per-field dict), source (per-field dict),
            ocr_confidence (single float 0–100).
    """
    print("\n" + "=" * 80)
    print("REGEX RESULT")
    print("=" * 80)
    print(regex_result)

    print()

    print("LLM RESULT")
    print("=" * 80)
    print(llm_result)
    print("=" * 80 + "\n")

    confidence: dict[str, float] = {}
    source: dict[str, str] = {}

    # ── Vendor ───────────────────────────────────────────────────────────
    regex_vendor = regex_result.get("vendor")
    llm_vendor   = llm_result.get("vendor")

    # Score each candidate purely on string quality — no names hardcoded
    regex_vendor_score = _score_vendor_string(regex_vendor)
    llm_vendor_score   = _score_vendor_string(llm_vendor)

    # Also weight by the LLM's own stated confidence
    llm_vendor_conf = _llm_field_confidence(llm_result, "vendor")
    # Blend: 70% string-quality score, 30% LLM self-confidence
    blended_llm_score = round(0.70 * llm_vendor_score + 0.30 * llm_vendor_conf, 3)

    logger.info(
        "Vendor scores — regex: %.3f | llm (blended): %.3f | margin needed: %.2f",
        regex_vendor_score,
        blended_llm_score,
        _VENDOR_PREFERENCE_MARGIN,
    )
    print(f"Regex Vendor Score: {regex_vendor_score:.2f}")
    print(f"LLM Vendor Score:   {blended_llm_score:.2f}")

    # Decision: use LLM when its blended score exceeds regex by the margin,
    # and the LLM actually returned a non-empty vendor string.
    if (
        llm_vendor
        and llm_vendor.strip()
        and blended_llm_score > regex_vendor_score + _VENDOR_PREFERENCE_MARGIN
    ):
        vendor = llm_vendor.strip()
        confidence["vendor"] = blended_llm_score
        source["vendor"] = "llm"
    else:
        vendor = regex_vendor or "Unknown"
        confidence["vendor"] = regex_vendor_score if regex_vendor_score > 0 else _REGEX_NULL_CONFIDENCE
        source["vendor"] = "regex"

    print(f"Selected Vendor Source: {source['vendor']}")

    # ── Date ─────────────────────────────────────────────────────────────
    regex_date = regex_result.get("date")
    llm_date   = llm_result.get("date")

    if _is_valid_iso_date(regex_date):
        date = regex_date
        confidence["date"] = _REGEX_BASE_CONFIDENCE
        source["date"] = "regex"
    elif _is_valid_iso_date(llm_date):
        date = llm_date
        confidence["date"] = _llm_field_confidence(llm_result, "date")
        source["date"] = "llm"
    else:
        # Neither produced a valid ISO date — keep whatever regex had
        date = regex_date
        confidence["date"] = _REGEX_NULL_CONFIDENCE
        source["date"] = "regex"

    # ── Invoice Number ───────────────────────────────────────────────────
    regex_inv = regex_result.get("invoice_number")
    llm_inv   = llm_result.get("invoice_number")

    if regex_inv:
        invoice_number = regex_inv
        confidence["invoice_number"] = _REGEX_BASE_CONFIDENCE
        source["invoice_number"] = "regex"
    elif llm_inv:
        invoice_number = llm_inv
        confidence["invoice_number"] = _llm_field_confidence(llm_result, "invoice_number")
        source["invoice_number"] = "llm"
    else:
        invoice_number = None
        confidence["invoice_number"] = _REGEX_NULL_CONFIDENCE
        source["invoice_number"] = "regex"

    # ── Amount ───────────────────────────────────────────────────────────
    regex_amount  = regex_result.get("amount") or 0.0
    llm_amount    = llm_result.get("amount")
    regex_amt_conf = _regex_field_confidence(regex_amount, is_numeric=True)
    llm_amt_conf   = _llm_field_confidence(llm_result, "amount")

    if llm_amount is None:
        # LLM returned nothing — keep regex
        amount = float(regex_amount)
        confidence["amount"] = regex_amt_conf
        source["amount"] = "regex"
    elif abs(float(regex_amount) - float(llm_amount)) <= _AMOUNT_TOLERANCE:
        # Both agree — keep regex
        amount = float(regex_amount)
        confidence["amount"] = max(regex_amt_conf, llm_amt_conf)
        source["amount"] = "regex"
    elif regex_amt_conf >= llm_amt_conf:
        amount = float(regex_amount)
        confidence["amount"] = regex_amt_conf
        source["amount"] = "regex"
    else:
        amount = float(llm_amount)
        confidence["amount"] = llm_amt_conf
        source["amount"] = "llm"

    # ── Tax ──────────────────────────────────────────────────────────────
    regex_tax = float(regex_result.get("tax") or 0.0)
    llm_tax = llm_result.get("tax")
    llm_tax = float(llm_tax) if llm_tax is not None else None

    regex_tax_conf = _regex_field_confidence(regex_tax, is_numeric=True)
    llm_tax_conf = _llm_field_confidence(llm_result, "tax")

    if llm_tax is None:
        tax = regex_tax
        confidence["tax"] = regex_tax_conf
        source["tax"] = "regex"

    elif regex_tax <= 0:
        tax = llm_tax
        confidence["tax"] = llm_tax_conf
        source["tax"] = "llm"

    # If both agree, keep regex
    elif abs(regex_tax - llm_tax) <= 0.01:
        tax = regex_tax
        confidence["tax"] = max(regex_tax_conf, llm_tax_conf)
        source["tax"] = "regex"

    # Large disagreement → prefer the LLM
    elif abs(regex_tax - llm_tax) > 5.0:
        tax = llm_tax
        confidence["tax"] = llm_tax_conf
        source["tax"] = "llm"

    # Small disagreement → keep regex
    else:
        tax = regex_tax
        confidence["tax"] = regex_tax_conf
        source["tax"] = "regex"

    # ── Payment Method ───────────────────────────────────────────────────
    regex_pm = regex_result.get("payment_method")
    llm_pm   = llm_result.get("payment_method")

    if regex_pm:
        payment_method = regex_pm
        confidence["payment_method"] = _REGEX_BASE_CONFIDENCE
        source["payment_method"] = "regex"
    elif llm_pm:
        payment_method = llm_pm
        confidence["payment_method"] = _llm_field_confidence(llm_result, "payment_method")
        source["payment_method"] = "llm"
    else:
        payment_method = None
        confidence["payment_method"] = _REGEX_NULL_CONFIDENCE
        source["payment_method"] = "regex"

    # ── Category ─────────────────────────────────────────────────────────
    # Always prefer LLM category (caller will fallback to keyword-based
    # categorize_expense if this is None).
    llm_cat = llm_result.get("category")
    if llm_cat:
        category = llm_cat
        confidence["category"] = _llm_field_confidence(llm_result, "category")
        source["category"] = "llm"
    else:
        category = None
        confidence["category"] = _REGEX_NULL_CONFIDENCE
        source["category"] = "llm"

    # ── Compute overall OCR confidence (0–100) ───────────────────────────
    field_confidences = list(confidence.values())
    avg_confidence = (
        sum(field_confidences) / len(field_confidences)
        if field_confidences
        else 0.0
    )
    ocr_confidence = round(max(0.0, min(100.0, avg_confidence * 100)), 1)

    logger.info(
        "Fusion complete — sources: %s | ocr_confidence: %.1f",
        source,
        ocr_confidence,
    )

    final_result = {
        "vendor": vendor,
        "amount": round(amount, 2),
        "tax": round(tax, 2),
        "date": date,
        "invoice_number": invoice_number,
        "payment_method": payment_method,
        "category": category,
        "confidence": confidence,
        "source": source,
        "ocr_confidence": ocr_confidence,
    }

    print("\n" + "=" * 80)
    print("FUSION RESULT")
    print("=" * 80)
    print(final_result)
    print("=" * 80 + "\n")

    return final_result
