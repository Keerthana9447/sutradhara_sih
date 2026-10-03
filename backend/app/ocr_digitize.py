"""
Manuscript OCR / Digitisation — /api/v1/ocr

Accepts a base64-encoded image of an old manuscript or document, invokes a
vision-language model to extract:
  - Identified herbs / botanicals
  - Symptoms / conditions treated
  - Formulation steps
  - Language / script detected

Returns an explicit provider error when OCR is unconfigured or the vision
provider rejects the request; it never presents an empty placeholder as OCR.
"""

import base64
import json
import os
import re
import logging
import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ip_sakti.ocr")


class OCRProviderError(RuntimeError):
    """Raised when the configured vision provider cannot return OCR output."""


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
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
        raise OCRProviderError(
            "Manuscript OCR is not configured. Set GROQ_API_KEY for the backend."
        )
    try:
        import urllib.error, urllib.request, ssl
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
        if isinstance(exc, urllib.error.HTTPError):
            try:
                provider_error = json.loads(exc.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                provider_error = {}
            details = provider_error.get("error", {}).get("message")
            if not isinstance(details, str) or not details:
                if exc.code in (401, 403):
                    details = (
                        f"HTTP {exc.code}; verify GROQ_API_KEY and vision-model access."
                    )
                else:
                    details = f"HTTP {exc.code}"
            logger.warning("OCR vision provider rejected request: %s", details)
            raise OCRProviderError(
                f"Vision provider rejected the OCR request: {details}"
            ) from exc
        logger.warning("OCR vision LLM call failed: %s", exc)
        raise OCRProviderError(
            "Manuscript OCR provider failed. Check GROQ_VISION_MODEL and backend logs."
        ) from exc


def digitise_manuscript(
    image_base64: str,
    mime_type: str = "image/jpeg",
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Main entry point. Returns extracted structured data + metadata."""
    result = _call_vision_llm(image_base64, mime_type)
    if result is None:
        raise OCRProviderError(
            "Manuscript OCR provider returned no extraction. Check backend logs."
        )
    return {
        "extracted": result,
        "digitised_at": datetime.datetime.utcnow().isoformat() + "Z",
        "filename": filename,
        "fallback_used": False,
        "disclaimer": (
            "OCR extraction is AI-assisted and may contain errors. Human expert "
            "review of the raw transcription is essential before using extracted "
            "data in any legal or scholarly context."
        ),
    }
