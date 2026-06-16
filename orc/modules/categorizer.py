from __future__ import annotations

import re
from collections import Counter

import pandas as pd


CATEGORIES = ["Food", "Transportation", "Shopping", "Education", "Healthcare", "Entertainment", "Utilities", "Other"]

CATEGORY_KEYWORDS = {
    "Food": [
        "restaurant",
        "cafe",
        "coffee",
        "pizza",
        "burger",
        "swiggy",
        "zomato",
        "grocery",
        "supermarket",
        "meal",
        "bakery",
        "food",
        "kitchen",
    ],
    "Transportation": [
        "uber",
        "ola",
        "metro",
        "railway",
        "bus",
        "fuel",
        "petrol",
        "diesel",
        "parking",
        "taxi",
        "travel",
        "transport",
    ],
    "Shopping": [
        "amazon",
        "flipkart",
        "mall",
        "store",
        "retail",
        "fashion",
        "clothing",
        "apparel",
        "electronics",
        "market",
    ],
    "Education": [
        "college",
        "school",
        "university",
        "course",
        "book",
        "tuition",
        "library",
        "stationery",
        "exam",
        "education",
    ],
    "Healthcare": [
        "hospital",
        "clinic",
        "pharmacy",
        "medical",
        "medicine",
        "doctor",
        "health",
        "diagnostic",
        "lab",
    ],
    "Entertainment": [
        "movie",
        "cinema",
        "netflix",
        "spotify",
        "game",
        "concert",
        "event",
        "ticket",
        "entertainment",
    ],
    "Utilities": [
        "electricity",
        "water",
        "internet",
        "wifi",
        "mobile",
        "phone",
        "gas",
        "utility",
        "broadband",
        "recharge",
    ],
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def categorize_expense(vendor: str, raw_text: str, history: pd.DataFrame | None = None) -> tuple[str, dict[str, int]]:
    text = f"{vendor or ''} {raw_text or ''}".lower()
    tokens = _tokenize(text)
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text:
                score += 3
            score += tokens.count(keyword)
        scores[category] = score

    if history is not None and not history.empty and vendor:
        vendor_rows = history[history["vendor"].str.lower() == vendor.lower()]
        if not vendor_rows.empty:
            learned = Counter(vendor_rows["category"]).most_common(1)[0][0]
            scores[learned] = scores.get(learned, 0) + 5

    best_category = max(scores, key=scores.get) if scores else "Other"
    return (best_category if scores.get(best_category, 0) > 0 else "Other", scores)


def most_common_category(history: pd.DataFrame) -> str:
    if history.empty or "category" not in history:
        return "Other"
    return str(history["category"].mode().iloc[0]) if not history["category"].mode().empty else "Other"

