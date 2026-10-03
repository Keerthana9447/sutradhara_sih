"""
Manuscript OCR / Digitisation — /api/v1/ocr

Accepts a base64-encoded image of an old manuscript or document, invokes a
vision-language model to extract:
  - Identified herbs / botanicals
  - Symptoms / conditions treated
  - Formulation steps
  - Language / script detected

Falls back to a structured placeholder response when no vision-LLM is
configured so the endpoint always responds.
"""

import base64
import json
import os
import re
import logging
import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ip_sakti.ocr")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
_TIMEOUT = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "25"))

_OCR_SYSTEM_PROMPT = (
    "You are a manuscript digitisation assistant specialising in ancient Indian "
    "medical texts (Ayurveda, Siddha, Unani, Yoga). Extract structured data from "
    "the provided manuscript image.\n\n"
    "Return ONLY valid JSON with exactly these keys:\n"
    "  script_detected     - e.g. 'Devanagari', 'Telugu', 'Grantha', 'Arabic' (string)\n"
    "  language_detected   - e.g. 'Sanskrit', 'Telugu', 'Arabic' (string)\n"
    "  raw_transcription   - verbatim OCR text as best as can be read (string)\n"
    "  herbs               - array of {name, local_name, part_mentioned}\n"
    "  symptoms_conditions - array of strings\n"
    "  formulation_steps   - ordered array of strings\n"
    "  confidence          - float 0-1 overall extraction confidence\n"
    "  notes               - any caveats about legibility or interpretation (string)\n\n"
    "If the image is not a manuscript or is unreadable, set confidence to 0 and "
    "explain in notes. Never fabricate herbs or conditions not visible in the image."
)


def _call_vision_llm(image_base64: str, mime_type: str = "image/jpeg") -> Optional[Dict[str, Any]]:
    if not GROQ_API_KEY:
        return None
    try:
        import urllib.request, ssl
        body = json.dumps({
            "model": GROQ_VISION_MODEL,
            "messages": [
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Please extract the herbal/medical information from this manuscript image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                ]},
            ],
            "temperature": 0.1,
            "max_tokens": 1500,
        }).encode()
        req = urllib.request.Request(
            GROQ_API_URL, data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"},
            method="POST",
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        raw = data["choices"][0]["message"]["content"]
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        return json.loads(raw)
    except Exception as exc:
        logger.warning("OCR vision LLM call failed: %s", exc)
        return None


def _placeholder_result() -> Dict[str, Any]:
    return {
        "script_detected": "Unknown (vision model unavailable)",
        "language_detected": "Unknown",
        "raw_transcription": "",
        "herbs": [],
        "symptoms_conditions": [],
        "formulation_steps": [],
        "confidence": 0.0,
        "notes": (
            "Vision-language model is not configured (GROQ_API_KEY not set or "
            "vision model unavailable). Upload is accepted but text extraction "
            "requires a configured vision LLM. Please configure GROQ_VISION_MODEL."
        ),
    }


def digitise_manuscript(
    image_base64: str,
    mime_type: str = "image/jpeg",
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Main entry point. Returns extracted structured data + metadata."""
    result = _call_vision_llm(image_base64, mime_type)
    fallback_used = result is None
    if fallback_used:
        result = _placeholder_result()
    return {
        "extracted": result,
        "digitised_at": datetime.datetime.utcnow().isoformat() + "Z",
        "filename": filename,
        "fallback_used": fallback_used,
        "disclaimer": (
            "OCR extraction is AI-assisted and may contain errors. Human expert "
            "review of the raw transcription is essential before using extracted "
            "data in any legal or scholarly context."
        ),
    }
