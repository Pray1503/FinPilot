"""
services/groq_client.py
────────────────────────
Unified Groq LLM client for all AI agents.
Renamed from gemini_client.py — the function name is kept for backwards compat.
"""

import os
import time
import random
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Search for .env in project dir, then parent dir (e:\final fintech)
_project_dir = Path(__file__).resolve().parent.parent
load_dotenv(_project_dir / ".env")
load_dotenv(_project_dir.parent / ".env")

GROQ_MODEL = "openai/gpt-oss-120b"

_api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("groq_api_key") or ""


def call_groq(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.25,
    max_tokens: int = 1024,
    max_retries: int = 3,
) -> str:
    """
    Call the Groq API with retry logic and exponential backoff.

    Returns the model's text response, or a descriptive error string.
    """
    if not _api_key:
        return (
            "⚠️ GROQ_API_KEY not found. "
            "Add GROQ_API_KEY=your-key to your .env file and restart."
        )

    client = Groq(api_key=_api_key)
    delay = 1.5
    last_error = ""

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()

        except Exception as exc:
            last_error = str(exc)
            retryable = any(
                code in last_error.lower()
                for code in ["429", "500", "503", "rate", "quota"]
            )
            if retryable and attempt < max_retries:
                time.sleep(delay + random.uniform(0, 0.5))
                delay *= 2
                continue
            break

    return f"[Groq error — attempt {attempt}]: {last_error}"


# Backwards-compatible alias
call_gemini_agent = call_groq
