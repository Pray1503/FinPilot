from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

# ADDED: Support for hyphens and slashes in text-based dates
DATE_PATTERNS = [

    r"(?:date)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

    r"(?:date)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",

    r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",

    r"\b(\d{1,2}[ \-\/]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[ \-\/]+\d{2,4})\b",

    r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[ \-\/]+\d{1,2},?[ \-\/]+\d{2,4})\b",

]
AMOUNT_PATTERN = r"(?:rs\.?|inr|₹|\$|usd)?\s*(?<![a-zA-Z0-9\-])([0-9]{1,3}(?:[, ]?[0-9]{3})*(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)(?![a-zA-Z0-9\-])"
TOTAL_KEYWORDS = [

    "grand total",

    "net amount",

    "amount due",

    "amount payable",

    "invoice total",

    "total amount",

    "balance due",

    "total",

    "subtotal",

]
TAX_KEYWORDS = ["gst", "tax", "cgst", "sgst", "igst", "vat"]

# ADDED: A floating ID catcher that handles spaces if Tesseract misreads hyphens
INVOICE_PATTERNS = [

    r"(?:invoice|inv|bill|receipt|order)\s*(?:no|number|#|id)?\s*[:\-]?\s*([A-Z0-9\-\/]*\d[A-Z0-9\-\/]*)",

    r"(?:^|\s)(?:no|#)\s*[:\-]?\s*([A-Z0-9\-\/]*\d[A-Z0-9\-\/]{2,})\b",

    r"bill\s*no\.?\s*[:\-]?\s*([A-Z0-9\-]+)",

    r"\b([A-Z]{2,5}[ \-\/]+\d{4}[ \-\/]+\d{3,8})\b",

]

# ---------------------------------------------------------------------------
# Payment method extraction — strict, context-aware regex patterns.
# Each pattern requires the keyword to appear in an explicit payment context
# (e.g., "Payment : Cash", "Paid By Card", "Mode : UPI") rather than as
# part of an unrelated phrase ("Cashier", "Cash Memo", "Card Number").
# ---------------------------------------------------------------------------

# Patterns that indicate an explicit payment context.
# Group 1 is always the raw payment token to classify.
_PAYMENT_CONTEXT_PATTERNS: list[str] = [
    # Labelled fields:  "Payment : Cash", "Mode : UPI", "Tender : Cash"
    r"(?:payment\s*(?:mode|method|type|by|via)?|mode\s*of\s*pay(?:ment)?|pay\s*mode|tender|paid\s*(?:by|via|through|using))\s*[:\-]?\s*([\w\s]+)",
]

# Standalone tokens that alone (on their own line or after a label) signal
# a payment method when NOT preceded by a false-positive context.
_PAYMENT_STANDALONE_TOKENS: dict[str, list[str]] = {
    "Cash":        ["cash"],
    "Credit Card": ["credit card", "credit"],
    "Debit Card":  ["debit card", "debit"],
    "Card":        ["card"],   # generic card — normalised later
    "Visa":        ["visa"],
    "Mastercard":  ["mastercard"],
    "Rupay":       ["rupay"],
    "UPI":         ["upi"],
    "Google Pay":  ["google pay", "gpay"],
    "PhonePe":     ["phonepe", "phone pe"],
    "Paytm":       ["paytm"],
    "BHIM":        ["bhim"],
    "Net Banking": ["net banking", "netbanking", "neft", "imps"],
}

# Substrings that — if present anywhere in the line — disqualify it from
# being treated as a payment method declaration.
_PAYMENT_FALSE_POSITIVE_FRAGMENTS: frozenset[str] = frozenset({
    "cashier",
    "cash memo",
    "cash discount",
    "cash back",
    "cashback",
    "card holder",
    "cardholder",
    "card number",
    "card no",
    "card type",   # e.g. "card type: visa" would expose via context pattern — OK
    "card expiry",
    "card name",
})

# Canonical mapping from raw token to normalised payment method label.
_PAYMENT_NORMALISE: dict[str, str] = {
    "cash":         "Cash",
    "credit card":  "Credit Card",
    "credit":       "Credit Card",
    "debit card":   "Debit Card",
    "debit":        "Debit Card",
    "card":         "Card",
    "visa":         "Visa",
    "mastercard":   "Mastercard",
    "rupay":        "Rupay",
    "upi":          "UPI",
    "google pay":   "Google Pay",
    "gpay":         "Google Pay",
    "phonepe":      "PhonePe",
    "phone pe":     "PhonePe",
    "paytm":        "Paytm",
    "bhim":         "BHIM",
    "net banking":  "Net Banking",
    "netbanking":   "Net Banking",
    "neft":         "Net Banking",
    "imps":         "Net Banking",
}

VENDOR_STOPWORDS = {
    "tax invoice", "invoice", "receipt", "bill", "cash memo", "duplicate", "customer copy", "original", "gst invoice", "retail invoice"
}

@dataclass
class ExtractedBill:
    vendor: str = "Unknown"
    amount: float = 0.0
    tax: float = 0.0
    date: str | None = None
    invoice_number: str | None = None
    payment_method: str | None = None
    validation_warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text or "").strip()

def _parse_amount(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace(",", "").replace(" ", "")
    try:
        amount = float(normalized)
        return amount if amount >= 0 else None
    except ValueError:
        return None

def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%Y-%m-%d",
        "%d/%m/%y", "%d-%m-%y", "%m/%d/%y", "%m-%d-%y", "%d %b %Y", "%d %B %Y",
        "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y",
        "%d-%b-%Y", "%d-%B-%Y" # Added hyphenated formats
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value.title().replace(",", ""), fmt.replace(",", "")).date().isoformat()
        except ValueError:
            continue
    return None

DOCUMENT_HEADERS = {
    "invoice",
    "tax invoice",
    "bill",
    "bill of supply",
    "receipt",
    "cash memo",
    "original",
    "duplicate",
    "customer copy",
    "retail invoice",
    "gst invoice",
}


_VENDOR_POSITIVE_WORDS = frozenset({
    "store", "mart", "supermarket", "hypermarket", "retail",
    "cafe", "coffee", "tea", "bakery", "bakers", "sweets",
    "restaurant", "eatery", "kitchen", "diner", "bistro", "grill",
    "pizza", "burger", "hotel", "lodge", "inn", "resort",
    "pharmacy", "chemist", "medical", "clinic", "hospital",
    "electronics", "digital", "tech", "solutions",
    "fashion", "apparel", "garments", "clothing", "boutique", "wear",
    "sports", "fitness", "gym",
    "fresh", "foods", "organic", "dairy",
    "hardware", "tools", "auto", "motors", "garage",
    "salon", "spa", "beauty",
    "jewellers", "jewels", "gold", "diamonds",
    "books", "stationery", "prints",
    "optical", "vision",
    "petrol", "fuel",
    "pvt", "ltd", "llp", "inc", "corp", "co", "company", "enterprises",
    "agencies", "traders", "trading", "associates", "brothers", "sons"
})

_VENDOR_NEGATIVE_WORDS = frozenset({
    "dine in", "take away", "delivery", "parcel", "counter", "table",
    "guest", "token", "cashier", "bill to", "customer", "order type",
    "room", "hall", "order no", "kot no", "biller", "served by", "waiter",
    "staff", "operator", "terminal", "pos", "shift",
    "road", "rd", "street", "st", "avenue", "ave", "marg", "nagar", "floor",
    "building", "bldg", "shop no", "plot", "opp", "near", "sector", "phase",
    "block", "plaza", "mall", "market", "arcade", "complex", "estate",
    "highway", "bypass", "junction", "circle",
    "gst", "gstin", "fssai", "pan", "tin", "cin",
    "invoice", "bill no", "receipt no", "date", "time", "phone", "ph", "mob", "mobile",
    "email", "address", "add", "qty", "price", "amount", "total", "subtotal", "tax", "cgst", "sgst", "igst",
    "discount", "change", "cash", "card", "upi", "paid", "balance"
})

def extract_vendor(lines: list[str]) -> str:
    """
    Returns the most likely vendor/store name using generalized candidate scoring.
    """
    candidates = []

    # Consider up to the first 15 lines since headers can be pushed down by logo/whitespace
    for idx, line in enumerate(lines[:15]):
        # Clean: keep letters, numbers, spaces, and basic punctuation common in names
        clean = re.sub(r"[^A-Za-z0-9 &'.-]", "", line).strip()
        
        if not clean:
            continue
            
        lowered = clean.lower()
        
        # Hard rejections
        if lowered in DOCUMENT_HEADERS:
            continue
            
        # Reject if heavily numeric (e.g., pure dates, phone numbers, GST numbers)
        alpha = sum(c.isalpha() for c in clean)
        digit = sum(c.isdigit() for c in clean)
        if alpha < 3 or alpha < digit:
            continue
            
        words = clean.split()
        if not words:
            continue
            
        # --- Scoring ---
        score = 0.0
        
        # 1. Position bonus (max 3.0)
        score += max(0, 10 - idx) * 0.3
        
        # 2. Length & word count bonus
        word_count = len(words)
        if 2 <= word_count <= 5:
            score += 3.0
        elif word_count == 1:
            score += 1.0
            
        # 3. Capitalization bonus
        if clean.upper() == clean:
            score += 2.0
        elif clean.istitle():
            score += 1.0
            
        # 4. Positive Signals
        positive_hits = sum(1 for w in lowered.split() if w in _VENDOR_POSITIVE_WORDS)
        score += positive_hits * 4.0
        
        # 5. Negative Signals
        alpha_only = "".join(c for c in lowered if c.isalpha() or c.isspace()).strip()
        if alpha_only in _VENDOR_NEGATIVE_WORDS:
            continue
            
        negative_hits = sum(1 for neg in _VENDOR_NEGATIVE_WORDS if neg in lowered)
        if negative_hits > 0:
            score -= (negative_hits * 8.0)
            
        # 6. Specific structure penalties
        if clean[0].isdigit():
            score -= 4.0
            
        candidates.append((score, clean))

    if not candidates:
        return "Unknown"

    candidates.sort(reverse=True, key=lambda x: x[0])
    
    # Return the top candidate if its score is positive
    best_score, best_clean = candidates[0]
    if best_score <= 0:
        return "Unknown"
        
    return best_clean[:80]

def extract_date(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if any(k in line.lower() for k in ["date", "dt"]):
            lookahead_block = " ".join(lines[i:i+3])
            for pattern in DATE_PATTERNS:
                match = re.search(pattern, lookahead_block, flags=re.IGNORECASE)
                if match:
                    parsed = _parse_date(match.group(1))
                    if parsed: return parsed

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            parsed = _parse_date(match.group(1))
            if parsed: return parsed
    return None

def extract_amount_by_keywords(text: str, keywords: list[str]) -> float | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[float] = []
    for i, line in enumerate(lines):
        lowered = line.lower()
        if "tax invoice" in lowered: continue
        if any(keyword in lowered for keyword in keywords):
            combined_context = " ".join(lines[i:i+3])
            matches = re.findall(AMOUNT_PATTERN, combined_context, flags=re.IGNORECASE)
            for match in matches:
                amount = _parse_amount(match)
                if amount is not None: candidates.append(amount)
    return max(candidates) if candidates else None

def extract_total_amount(text: str) -> float:
    total = extract_amount_by_keywords(text, TOTAL_KEYWORDS)
    if total is not None: return total
    amounts = [_parse_amount(match) for match in re.findall(AMOUNT_PATTERN, text, flags=re.IGNORECASE)]
    numeric = [amount for amount in amounts if amount is not None and amount > 0]
    return max(numeric) if numeric else 0.0

def extract_tax_amount(text: str, amount: float) -> float:
    # UPGRADE: Add together all distinct taxes found (like CGST + SGST)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    taxes = []
    for i, line in enumerate(lines):
        lowered = line.lower()
        if "tax invoice" in lowered: continue
        if any(keyword in lowered for keyword in TAX_KEYWORDS):
            matches = re.findall(AMOUNT_PATTERN, line, flags=re.IGNORECASE)
            for match in matches:
                val = _parse_amount(match)
                # Avoid adding the grand total if it happens to be on the same line
                if (val and val < amount and val < amount * 0.5): 
                    taxes.append(val)
    
    # If we found multiple taxes (e.g. CGST 4473 and SGST 4473), sum them
    total_tax = sum(taxes) if taxes else 0.0
    return total_tax if total_tax <= amount else 0.0

def extract_invoice_number(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if any(k in line.lower() for k in ["invoice", "inv", "bill", "receipt", "order", "#"]):
            combined_context = " ".join(lines[i:i+3])
            for pattern in INVOICE_PATTERNS:
                match = re.search(pattern, combined_context, flags=re.IGNORECASE)
                if match: return match.group(1).strip()[:40]
    
    for pattern in INVOICE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match: return match.group(1).strip()[:40]
    return None

def extract_payment_method(text: str) -> str | None:
    """
    Return the payment method ONLY when it is explicitly stated in the OCR text.

    Detection strategy:
    1. Walk each line of the receipt.
    2. Skip lines that contain false-positive fragments (e.g. "cashier").
    3. Try each labelled-context pattern ("Payment : Cash", "Mode : UPI", …).
    4. If no labelled pattern matches on a line, try standalone token matching
       but ONLY when the line itself looks like a payment declaration
       (i.e. the line is short or begins with a known payment label word).
    5. Return the first canonical match; None if nothing is found.

    Never guesses or infers — if absent, returns None.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        lowered_line = line.lower()

        # --- Reject lines that are clearly not payment declarations ---
        if any(fp in lowered_line for fp in _PAYMENT_FALSE_POSITIVE_FRAGMENTS):
            continue

        # --- 1. Labelled-context patterns (highest confidence) ---
        for pattern in _PAYMENT_CONTEXT_PATTERNS:
            m = re.search(pattern, lowered_line, flags=re.IGNORECASE)
            if m:
                raw_token = m.group(1).strip().lower()
                # Take only the first meaningful word(s) (up to 3 words)
                raw_token = " ".join(raw_token.split()[:3])
                # Try exact normalisation first
                if raw_token in _PAYMENT_NORMALISE:
                    return _PAYMENT_NORMALISE[raw_token]
                # Try prefix matching (e.g. "cash " from "cash change")
                for key, canonical in _PAYMENT_NORMALISE.items():
                    if raw_token.startswith(key):
                        return canonical

        # --- 2. Standalone token matching (lower confidence) ---
        # Only attempt on short lines (≤60 chars) or lines that contain a
        # payment trigger word, to avoid matching in the middle of item names.
        line_word_count = len(line.split())
        has_payment_label = any(
            trigger in lowered_line
            for trigger in (
                "payment", "paid", "tender", "mode", "method",
                "cash", "card", "upi", "gpay", "google pay",
                "phonepe", "phone pe", "paytm", "bhim",
                "visa", "mastercard", "rupay",
                "net banking", "netbanking", "neft", "imps",
            )
        )
        if not has_payment_label:
            continue
        if len(line) > 80 and line_word_count > 10:
            # Long descriptive lines — skip standalone matching
            continue

        # Check standalone tokens in order of specificity (longest first)
        for canonical_label, tokens in sorted(
            _PAYMENT_STANDALONE_TOKENS.items(),
            key=lambda kv: max(len(t) for t in kv[1]),
            reverse=True,
        ):
            for token in tokens:
                # Must appear as a whole phrase (word-boundary aware)
                pattern_str = r"(?<![a-z])" + re.escape(token) + r"(?![a-z])"
                if re.search(pattern_str, lowered_line):
                    # One final false-positive check: reject if the match is
                    # inside a disqualifying fragment
                    if any(fp in lowered_line for fp in _PAYMENT_FALSE_POSITIVE_FRAGMENTS):
                        break
                    # Normalise and return
                    return _PAYMENT_NORMALISE.get(token, canonical_label)

    return None

def extract_bill_data(raw_text: str) -> ExtractedBill:
    clean_text = _clean_text(raw_text)
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    amount = extract_total_amount(clean_text)
    tax = extract_tax_amount(clean_text, amount)
    
    extracted = ExtractedBill(
        vendor=extract_vendor(lines),
        amount=round(amount, 2),
        tax=round(tax, 2),
        date=extract_date(clean_text),
        invoice_number=extract_invoice_number(clean_text),
        payment_method=extract_payment_method(clean_text),
        validation_warnings=[],
    )
    return extracted

def validate_extraction(data: ExtractedBill) -> list[str]:
    warnings = []
    if data.vendor == "Unknown": warnings.append("Vendor could not be identified.")
    if data.amount <= 0: warnings.append("Total amount could not be detected.")
    if data.tax and data.tax > data.amount: warnings.append("Tax amount is higher than total amount.")
    if not data.date: warnings.append("Bill date is missing or invalid.")
    if not data.invoice_number: warnings.append("Invoice number was not found.")
    return warnings