"""
llm/receipt_extractor.py
─────────────────────────
Module for extracting receipt data using Groq LLM.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

# Configure logging
logger = logging.getLogger(__name__)

# Try importing the project's unified Groq client, fallback if executed standalone
try:
    from services.groq_client import call_groq
except ImportError:
    # Standalone fallback implementation
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    from groq import Groq

    # Locate and load the environment variables
    _project_dir = Path(__file__).resolve().parent.parent
    load_dotenv(_project_dir / ".env")
    load_dotenv(_project_dir.parent / ".env")
    _api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("groq_api_key") or ""

    def call_groq(
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.25,
        max_tokens: int = 1024,
        max_retries: int = 3,
    ) -> str:
        """Fallback Groq API caller for standalone execution."""
        if not _api_key:
            logger.warning("GROQ_API_KEY not found in environment.")
            return "⚠️ GROQ_API_KEY not found."

        client = Groq(api_key=_api_key)
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Basic retry logic
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as exc:
                logger.error(f"Groq API call attempt {attempt} failed: {exc}")
                if attempt == max_retries:
                    return f"[Groq error]: {exc}"
        return "Unknown error occurred"


# Sensible defaults/fallback result structure
DEFAULT_RESULT = {
    "vendor": "",
    "amount": None,
    "tax": None,
    "date": None,
    "invoice_number": None,
    "payment_method": None,
    "category": None,
    "confidence": {
        "vendor": 0.0,
        "amount": 0.0,
        "tax": 0.0,
        "date": 0.0,
        "invoice_number": 0.0,
        "payment_method": 0.0,
        "category": 0.0,
    },
}

SYSTEM_PROMPT = (
    "You are an expert receipt understanding system.\n"
    "Your task is to read, understand, and extract structured data from receipt OCR text.\n\n"

    "STEP 1 — UNDERSTAND THE DOCUMENT\n"
    "Before extracting any field, first identify the type of document (receipt, invoice, bill, order slip, etc.).\n"
    "Identify the overall context: what business issued it, what transaction it records, and how the totals are structured.\n\n"

    "STEP 2 — EXTRACT FIELDS\n"
    "Extract the following fields according to the rules below.\n\n"

    "=== VENDOR ===\n"
    "The vendor is the business or establishment that ISSUED this receipt.\n"
    "It is typically the name printed most prominently near the top of the document (the header/logo area).\n"
    "The vendor is NEVER any of the following — even if they appear at the top of the receipt:\n"
    "  - Customer names or 'Bill To' names\n"
    "  - Street addresses, areas, cities, or location descriptions\n"
    "  - GST numbers, FSSAI numbers, PAN numbers, or registration codes\n"
    "  - Phone numbers, mobile numbers, or email addresses\n"
    "  - Table numbers, room numbers, or counter numbers\n"
    "  - Dine-in labels, takeaway labels, delivery labels, or order type labels\n"
    "  - Cashier names, staff names, or waiter names\n"
    "  - Operational labels (e.g., 'Token', 'Shift', 'KOT', 'POS')\n"
    "  - Branch identifiers or department names\n"
    "  - Document headers (e.g., 'Tax Invoice', 'Receipt', 'Bill of Supply')\n"
    "If the vendor name cannot be determined with confidence, return \"\".\n\n"

    "=== AMOUNT ===\n"
    "Extract the final amount the customer actually paid or is required to pay.\n"
    "This is the grand total after all discounts, taxes, service charges, and adjustments.\n"
    "Do NOT return a subtotal, pre-tax total, pre-discount total, or any intermediate total.\n"
    "Look for labels like: Grand Total, Net Payable, Total Amount, Amount Due, Total Payable.\n"
    "Return as a float, or null if not determinable.\n\n"

    "=== TAX ===\n"
    "Extract the total tax amount.\n"
    "If both CGST and SGST are present, sum them together as the total tax.\n"
    "If IGST is present (instead of CGST+SGST), use the IGST value directly.\n"
    "Do not include the tax amount in the final 'amount' if it is already part of the grand total.\n"
    "Return as a float, or null if not present.\n\n"

    "=== DATE ===\n"
    "Extract the transaction date and return it in ISO 8601 format: YYYY-MM-DD.\n"
    "If the date is ambiguous, partially legible, or missing, return null.\n\n"

    "=== INVOICE NUMBER ===\n"
    "Extract the receipt, invoice, or bill number if explicitly present.\n"
    "Return as a string, or null if not present.\n\n"

    "=== PAYMENT METHOD ===\n"
    "Return the payment method ONLY if it is explicitly and literally written in the OCR text.\n"
    "Accepted values: \"Cash\", \"Credit Card\", \"Debit Card\", \"Visa\", \"Mastercard\", \"Rupay\",\n"
    "  \"UPI\", \"Google Pay\", \"PhonePe\", \"Paytm\", \"BHIM\", \"Net Banking\".\n"
    "Map any recognised variant to the closest accepted value above.\n"
    "STRICT RULES — violating any of these is a critical error:\n"
    "  - Do NOT assume Cash just because no other method is visible.\n"
    "  - Do NOT assume Card just because a number or expiry is present.\n"
    "  - Do NOT invent UPI if only a QR code is mentioned.\n"
    "  - Do NOT infer payment method from the type of establishment.\n"
    "  - Words like 'Cashier', 'Cash Memo', 'Cash Discount', 'Card Number',\n"
    "    'Card Holder' are NOT payment method declarations — ignore them.\n"
    "If the payment method is absent, ambiguous, or only implied, return null.\n\n"

    "=== CATEGORY ===\n"
    "Classify the transaction into one of the following generalized categories based on the nature of the purchase:\n"
    "  \"Food\"         — restaurants, cafes, food delivery, bakeries, dining\n"
    "  \"Grocery\"      — supermarkets, grocery stores, fresh produce, daily essentials\n"
    "  \"Shopping\"     — retail clothing, accessories, general merchandise\n"
    "  \"Medical\"      — pharmacies, clinics, hospitals, diagnostic labs\n"
    "  \"Electronics\"  — electronic devices, gadgets, accessories\n"
    "  \"Fuel\"         — petrol, diesel, CNG, electric charging\n"
    "  \"Hotel\"        — accommodation, lodging, resorts\n"
    "  \"Utility\"      — electricity, water, internet, telephone bills\n"
    "  \"Travel\"       — transport tickets, travel bookings, toll receipts\n"
    "  \"Entertainment\"— cinema, events, gaming, amusement\n"
    "  \"Other\"        — anything that does not clearly fit the above categories\n"
    "Return null only if the category truly cannot be determined.\n\n"

    "=== ANTI-HALLUCINATION RULES ===\n"
    "You MUST NOT invent, guess, or assume any value.\n"
    "If a field is missing, ambiguous, or not clearly supported by the text, return null.\n"
    "A low-confidence extraction is always preferable to a hallucinated one.\n"
    "Assign a confidence score (0.0–1.0) for each field reflecting your certainty based on evidence in the text.\n\n"

    "=== OUTPUT FORMAT ===\n"
    "Return ONLY a valid JSON object. No markdown, no code fences, no explanations, no extra text.\n"
    "The JSON must exactly match this schema:\n"
    "{\n"
    '  "vendor": string,\n'
    '  "amount": number or null,\n'
    '  "tax": number or null,\n'
    '  "date": string or null,\n'
    '  "invoice_number": string or null,\n'
    '  "payment_method": string or null,\n'
    '  "category": string or null,\n'
    '  "confidence": {\n'
    '    "vendor": number,\n'
    '    "amount": number,\n'
    '    "tax": number,\n'
    '    "date": number,\n'
    '    "invoice_number": number,\n'
    '    "payment_method": number,\n'
    '    "category": number\n'
    "  }\n"
    "}"
)


def _to_float(val: Any) -> float | None:
    """Helper to convert a value safely to float or None."""
    if val is None or isinstance(val, bool):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_str(val: Any) -> str | None:
    """Helper to convert a value safely to string or None."""
    if val is None:
        return None
    return str(val).strip()


def _to_confidence(val: Any) -> float:
    """Helper to safely convert confidence value to float bounded [0.0, 1.0]."""
    f_val = _to_float(val)
    if f_val is None:
        return 0.0
    return max(0.0, min(1.0, f_val))


def _extract_json_substring(text: str) -> str | None:
    """Extracts the first matched JSON substring (matching outer braces) from text."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def extract_receipt_with_llm(raw_text: str) -> dict[str, Any]:
    """
    Extract structured receipt data using Groq LLM.

    Args:
        raw_text: Raw OCR text from the receipt.

    Returns:
        A dictionary containing the extracted keys:
        - vendor (str)
        - amount (float | None)
        - tax (float | None)
        - date (str | None)
        - invoice_number (str | None)
        - payment_method (str | None)
        - category (str | None)
        - confidence (dict with the same keys mapped to floats)
    """
    if not raw_text or not raw_text.strip():
        logger.warning("Empty raw_text passed to extract_receipt_with_llm.")
        return DEFAULT_RESULT.copy()

    try:
        # Prompt Groq model (temperature=0.0 to ensure deterministic/factual extraction)
        # ------------------------------------------------------------------
        # Build a structured OCR prompt instead of sending a raw text blob.
        # This preserves reading order and gives the LLM document context
        # without changing the OCR engine or adding receipt-specific logic.
        # ------------------------------------------------------------------

        ocr_lines = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]

        structured_prompt = (
            "================ RECEIPT OCR ================\n\n"
            "The following OCR text preserves the original reading order.\n"
            "Earlier lines are located nearer the TOP of the receipt.\n"
            "Later lines are located nearer the BOTTOM of the receipt.\n\n"

            "General document structure (this is a guideline, not a rule):\n"
            "- Earlier lines usually contain the merchant or store information.\n"
            "- Middle lines usually contain purchased items and quantities.\n"
            "- Later lines usually contain totals, taxes and payment information.\n\n"

            "---------------- OCR START ----------------\n\n"
            + "\n".join(
                f"[{i + 1:03d}] {line}"
                for i, line in enumerate(ocr_lines)
            )
            + "\n\n---------------- OCR END ----------------\n\n"

            "Use the reading order to understand the document.\n"
            "Do not rely only on keywords.\n"
            "Reason about the role of each line within the document.\n"
            "Prefer information that is structurally consistent with receipts and invoices.\n"
            "Do not assume missing information.\n"
            "Return only values explicitly supported by the OCR text."
        )

        print("\n" + "=" * 80)
        print("PROMPT SENT TO GROQ")
        print("=" * 80)
        print(structured_prompt)
        print("=" * 80 + "\n")

        # Prompt Groq model (temperature=0.0 for deterministic extraction)
        response_text = call_groq(
            prompt=structured_prompt,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
        )
        print("\n" + "=" * 80)
        print("RAW GROQ RESPONSE")
        print("=" * 80)
        print(response_text)
        print("=" * 80 + "\n")

        if not response_text:
            logger.error("Groq returned an empty response.")
            return DEFAULT_RESULT.copy()

        # Handle API warning / error signals
        if response_text.startswith("⚠️") or response_text.startswith("[Groq error"):
            logger.error(f"Groq API call returned error: {response_text}")
            return DEFAULT_RESULT.copy()

        # Clean/extract the JSON substring in case of code block wrapping
        json_str = _extract_json_substring(response_text)
        if not json_str:
            logger.error(f"Could not find JSON object in response: {response_text}")
            return DEFAULT_RESULT.copy()

        # Parse JSON
        parsed_data = json.loads(json_str)

    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse JSON response: {exc}. Response text: {response_text}")
        return DEFAULT_RESULT.copy()
    except Exception as exc:
        logger.error(f"Unexpected error in LLM extraction pipeline: {exc}", exc_info=True)
        return DEFAULT_RESULT.copy()

    # Normalize and validate returned keys according to requirements
    try:
        vendor = _to_str(parsed_data.get("vendor"))
        # Requirement: "vendor" must be a string, defaulting to "" if uncertain/missing
        if vendor is None:
            vendor = ""

        amount = _to_float(parsed_data.get("amount"))
        tax = _to_float(parsed_data.get("tax"))
        date = _to_str(parsed_data.get("date"))
        invoice_number = _to_str(parsed_data.get("invoice_number"))

        # Normalize payment_method and category if they don't match specified values
        payment_method = _to_str(parsed_data.get("payment_method"))
        valid_payments = {
            "Cash", "Credit Card", "Debit Card", "Card",
            "Visa", "Mastercard", "Rupay",
            "UPI", "Google Pay", "PhonePe", "Paytm", "BHIM",
            "Net Banking",
        }
        if payment_method not in valid_payments:
            payment_method = None

        category = _to_str(parsed_data.get("category"))
        valid_categories = {
            "Food",
            "Grocery",
            "Shopping",
            "Medical",
            "Electronics",
            "Fuel",
            "Hotel",
            "Utility",
            "Travel",
            "Entertainment",
            "Other",
        }
        if category not in valid_categories:
            category = None

        # Build confidence sub-dictionary
        raw_conf = parsed_data.get("confidence")
        if not isinstance(raw_conf, dict):
            raw_conf = {}

        confidence = {
            "vendor": _to_confidence(raw_conf.get("vendor")),
            "amount": _to_confidence(raw_conf.get("amount")),
            "tax": _to_confidence(raw_conf.get("tax")),
            "date": _to_confidence(raw_conf.get("date")),
            "invoice_number": _to_confidence(raw_conf.get("invoice_number")),
            "payment_method": _to_confidence(raw_conf.get("payment_method")),
            "category": _to_confidence(raw_conf.get("category")),
        }

        # Build the final output dictionary matching the exact schema
        result = {
            "vendor": vendor,
            "amount": amount,
            "tax": tax,
            "date": date,
            "invoice_number": invoice_number,
            "payment_method": payment_method,
            "category": category,
            "confidence": confidence,
        }

        print("\n" + "=" * 80)
        print("LLM OUTPUT")
        print("=" * 80)
        print(json.dumps(result, indent=4))
        print("=" * 80 + "\n")

        return result
       

    except Exception as exc:
        logger.error(f"Error validating/building receipt dictionary: {exc}", exc_info=True)
        return DEFAULT_RESULT.copy()
