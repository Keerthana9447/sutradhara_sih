"""
Answer translation.

Phase 7 of the brief scoped multilingual support as "UI chrome first, don't
spend most of development time on languages." That's right for a v0, but a
judge asking for a Telugu answer and getting English back looks broken, not
scoped. This module adds real machine translation of the *generated answer
text* (which is template-assembled from English-language legal sources, so
translating it is safe — we are not asking a model to invent legal claims in
Telugu, only to render already-grounded English sentences in Telugu).

Deliberately NOT translated:
  - Source titles, section numbers, authority names, URLs — these are
    official document identifiers; translating them would make citations
    unverifiable and is standard practice not to translate.
  - The corpus.json content itself — corpus stays English/source-language;
    only the assembled answer is translated per-request.

PROVIDER CHAIN: the problem statement asks for multilingual delivery
"leveraging national language infrastructure such as Bhashini" — the
Government of India's public MeitY/ULCA language pipeline. The chain tries, in order:

  1. Bhashini (ULCA pipeline API) — tried first as primary, per the PS's
     explicit priority for national language infrastructure. Requires
     BHASHINI_NMT_USER_ID and BHASHINI_NMT_API_KEY (or the shared
     BHASHINI_USER_ID / BHASHINI_API_KEY).
  2. Sarvam AI (sarvam-translate:v1) — fallback provider. Authenticated
     API purpose-built for Indian languages, requires SARVAM_API_KEY.
  3. Google Translate (via deep-translator, free/no key) — used if Bhashini
     and Sarvam are both unconfigured, unreachable, or error.
  4. MyMemory (via deep-translator) — last free fallback.

Google and MyMemory are both live network calls, and both are
unofficial/rate-limited free services (Google's especially so — it's a
scrape of translate.google.com, not a paid API, and returns HTTP
429/TooManyRequests fairly readily on shared or high-traffic IPs,
independent of this app's own call volume). Falling through additional
providers makes that much less likely to take the whole feature down. If
every provider fails (offline, all rate-limited, services down), we fail
safe: return the original English text plus a flag so the frontend can show
a small "(translation unavailable — showing English)" note instead of
silently losing content or crashing the request. For the query-translation
direction specifically, main.py additionally falls back to
language.fallback_normalize() (an offline term-substitution gloss) so
retrieval still gets usable English signal even with zero network access —
see language.py.
"""
from typing import Tuple, Optional, List, Callable
from collections import OrderedDict
import hashlib
import logging
import os
import re

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    from sarvamai import SarvamAI
    _SARVAM_AVAILABLE = True
except ImportError:
    _SARVAM_AVAILABLE = False

logger = logging.getLogger("ip_sakti.translate")

# --------------------------------------------------------------------------
# Sarvam AI provider
# --------------------------------------------------------------------------
# Internal short codes -> Sarvam locale codes (en-IN, te-IN, ...). Sarvam's
# translate API wants a full locale rather than the bare ISO code Google
# uses, so this needs its own map (same reasoning as _MYMEMORY_LANG_MAP
# below for MyMemory).
_SARVAM_LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "te": "te-IN",
    "ta": "ta-IN",
    "ml": "ml-IN",
    "sa": "sa-IN",
}


def _sarvam_api_key() -> str:
    return os.getenv("SARVAM_API_KEY", "").strip()


def _sarvam_translate_one(text: str, source: str, target: str) -> Optional[str]:
    """
    One Sarvam sarvam-translate:v1 call for a single chunk of text. Returns
    None (never raises) on any failure — missing key, SDK not installed,
    network error, or an unexpected response shape — so the caller can fall
    through to the next provider unconditionally, same contract as
    _bhashini_translate_one below.
    """
    if not _SARVAM_AVAILABLE:
        return None
    api_key = _sarvam_api_key()
    if not api_key:
        return None
    src_code = _SARVAM_LANG_MAP.get(source, f"{source}-IN")
    tgt_code = _SARVAM_LANG_MAP.get(target, f"{target}-IN")
    try:
        client = SarvamAI(api_subscription_key=api_key)
        response = client.text.translate(
            input=text,
            source_language_code=src_code,
            target_language_code=tgt_code,
            model="sarvam-translate:v1",
        )
        result = getattr(response, "translated_text", None)
        if not result and isinstance(response, dict):
            # Older/alternate SDK versions may return a plain dict instead
            # of a typed response object.
            result = response.get("translated_text")
        return result or None
    except Exception as e:
        logger.info("Sarvam translation provider failed (%s->%s): %r", source, target, e)
        return None


def sarvam_translate_status() -> dict:
    """Small transparency helper for /api/health and the eval dashboard —
    reports whether the Sarvam translation provider is actually usable in
    this deployment, without leaking the credential value itself. See
    bhashini_status() below and app/asr.py's asr_status() for the sibling
    ASR (voice) credential check — SARVAM_API_KEY is shared across both."""
    configured = _SARVAM_AVAILABLE and bool(_sarvam_api_key())
    return {
        "configured": configured,
        "note": (
            "SARVAM_API_KEY set — Sarvam (sarvam-translate:v1) is available "
            "as fallback translation provider if Bhashini is unavailable."
            if configured
            else "Not configured in this environment — falling back to "
            "Google Translate / MyMemory if Bhashini is also unavailable. Set SARVAM_API_KEY "
            "to enable Sarvam as fallback translation provider."
        ),
    }


# --------------------------------------------------------------------------
# Bhashini (ULCA) provider
# --------------------------------------------------------------------------
# Public, documented ULCA pipeline endpoints (MeitY / Digital India Bhashini
# mission). The "getModelsPipeline" pipelineId below is the well-known public
# MT pipeline used by third-party integrations (e.g. published Bhashini
# sample apps); a production deployment should confirm the current pipelineId
# for its registered account against the Bhashini developer console, since
# these ids are managed server-side and can be rotated by MeitY.
_BHASHINI_PIPELINE_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
_BHASHINI_DEFAULT_NMT_PIPELINE_ID = "64392f96daac500b55c543cd"
_BHASHINI_TIMEOUT_SECONDS = 6.0


def _bhashini_credentials() -> Optional[Tuple[str, str]]:
    # NMT-specific names take priority; unprefixed names are a backward-
    # compatible fallback for a single-key setup (translation only, no ASR).
    user_id = os.getenv("BHASHINI_NMT_USER_ID") or os.getenv("BHASHINI_USER_ID")
    api_key = os.getenv("BHASHINI_NMT_API_KEY") or os.getenv("BHASHINI_API_KEY")
    if user_id and api_key:
        return user_id, api_key
    return None


def _bhashini_translate_one(text: str, source: str, target: str) -> Optional[str]:
    """
    One Bhashini/ULCA translation call for a single chunk of text.
    Returns None (never raises) on any failure — missing credentials, no
    network route, HTTP error, or an unexpected response shape — so the
    caller can fall through to the next provider unconditionally.
    """
    creds = _bhashini_credentials()
    if not creds or not _HTTPX_AVAILABLE:
        return None
    user_id, api_key = creds

    pipeline_id = os.getenv("BHASHINI_NMT_PIPELINE_ID", os.getenv("BHASHINI_PIPELINE_ID", _BHASHINI_DEFAULT_NMT_PIPELINE_ID))
    headers = {
        "Content-Type": "application/json",
        "userID": user_id,
        "ulcaApiKey": api_key,
    }
    config_payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {"language": {"sourceLanguage": source, "targetLanguage": target}},
            }
        ],
        "pipelineRequestConfig": {"pipelineId": pipeline_id},
    }

    try:
        with httpx.Client(timeout=_BHASHINI_TIMEOUT_SECONDS) as client:
            config_resp = client.post(_BHASHINI_PIPELINE_CONFIG_URL, headers=headers, json=config_payload)
            config_resp.raise_for_status()
            config = config_resp.json()

            endpoint = config["pipelineInferenceAPIEndPoint"]
            inference_url = endpoint["callbackUrl"]
            inference_api_name = endpoint["inferenceApiKey"]["name"]
            inference_api_value = endpoint["inferenceApiKey"]["value"]
            service_id = config["pipelineResponseConfig"][0]["config"][0]["serviceId"]

            inference_payload = {
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {"sourceLanguage": source, "targetLanguage": target},
                            "serviceId": service_id,
                        },
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            }
            inference_headers = {
                "Content-Type": "application/json",
                inference_api_name: inference_api_value,
            }
            inf_resp = client.post(inference_url, headers=inference_headers, json=inference_payload)
            inf_resp.raise_for_status()
            result = inf_resp.json()
            return result["pipelineResponse"][0]["output"][0]["target"]
    except Exception as e:
        logger.info("Bhashini provider failed (%s->%s): %r", source, target, e)
        return None

# The same demo queries get re-run repeatedly during rehearsal and again
# live in front of judges (Demo 4's exact script, retries after a
# transient failure, a judge asking the same question twice). All
# providers here are rate-limited or metered independent of this app's own
# logic, so memoizing identical (text, source, target) calls for the life
# of the process meaningfully cuts real request volume without changing
# any translation *behavior* -- a cache hit returns exactly what a fresh
# successful call would have returned. Bounded (simple FIFO eviction via
# OrderedDict) so a long-running demo process can't grow this unbounded.
_CACHE: "OrderedDict[str, str]" = OrderedDict()
_CACHE_MAX_ENTRIES = 256


def _cache_key(text: str, source: str, target: str) -> str:
    # Hash rather than store the raw text as the key: answer text can be
    # long (multi-paragraph), and every corpus/query combination is
    # already reproducible from (source, target, text) alone.
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{source}:{target}:{digest}"


def _cache_get(key: str) -> Optional[str]:
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    return None


def _cache_put(key: str, value: str) -> None:
    _CACHE[key] = value
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        _CACHE.popitem(last=False)

# Google's own codes ("en", "te") work fine as-is. MyMemory, however,
# requires locale-qualified codes (e.g. "en-US", "te-IN") and raises
# LanguageNotSupportedException on bare "en"/"te" -- this is NOT a network
# problem, it fails the same way with a perfect connection, so it needs its
# own mapping rather than reusing _LANG_MAP.
#
# Sanskrit ("sa") is included because Google Translate supports it as a
# source/target language even though MyMemory's Sanskrit coverage is
# unreliable in practice (sparse community-contributed translation memory).
# It's still mapped below on the chance a given phrase is covered; real
# Sanskrit reliability comes from Sarvam/Google (tried earlier) and the
# offline gloss fallback (tried last), not from MyMemory specifically. Not
# yet exercised against live Sanskrit traffic — if MyMemory rejects the
# pair outright, the existing per-provider try/except already falls
# through.
_LANG_MAP = {"te": "te", "hi": "hi", "ta": "ta", "ml": "ml", "sa": "sa", "en": "en"}
_MYMEMORY_LANG_MAP = {"te": "te-IN", "hi": "hi-IN", "ta": "ta-IN", "ml": "ml-IN", "sa": "sa-IN", "en": "en-US"}

# Each provider enforces its OWN hard per-request character limit,
# independent of rate-limiting/network issues:
#   - Sarvam: no officially documented hard cap, but chunking at a
#     conservative size keeps each request coherent and avoids timeouts on
#     long, multi-source assembled answers.
#   - Google (via deep-translator's scrape endpoint): ~5000 chars/request.
#   - MyMemory: a hard 500 chars/request (raises NotValidLength above that;
#     see deep_translator/mymemory.py -- is_input_valid(text, max_chars=500)).
# The assembled multi-source answer routinely exceeds 500 chars, so without
# chunking, MyMemory rejects it every single time regardless of connectivity.
# Limits below are set conservatively under each provider's real cap.
_PROVIDER_MAX_CHARS = {"sarvam": 900, "google": 4500, "mymemory": 480, "bhashini": 2000}


def _split_into_chunks(text: str, max_chars: int) -> List[str]:
    """
    Split text into pieces <= max_chars, preferring to break on paragraph
    boundaries ("\\n\\n"), then sentence boundaries, then a hard cut only as
    a last resort. Keeps whole paragraphs/sentences together where possible
    so each chunk translates coherently on its own.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current = ""

    def flush():
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush()
        if len(para) <= max_chars:
            current = para
            continue

        # This single paragraph alone exceeds max_chars -- split by sentence.
        sub = ""
        for sent in re.split(r"(?<=[.!?])\s+", para):
            cand = f"{sub} {sent}" if sub else sent
            if len(cand) <= max_chars:
                sub = cand
                continue
            if sub:
                chunks.append(sub)
                sub = ""
            if len(sent) <= max_chars:
                sub = sent
            else:
                # Last resort: hard-cut an unreasonably long single sentence.
                for i in range(0, len(sent), max_chars):
                    chunks.append(sent[i:i + max_chars])
        if sub:
            chunks.append(sub)

    flush()
    return chunks


def _translate_full_text(text: str, translate_one: Callable[[str], str], max_chars: int) -> Optional[str]:
    """
    Translate arbitrarily long text with a single provider by chunking to
    that provider's own limit, translating each chunk, and rejoining with
    paragraph breaks. Returns None (whole attempt fails) if any chunk fails
    -- we don't stitch together a partially-translated answer from a
    provider that broke midway; the caller moves on to the next provider.
    """
    chunks = _split_into_chunks(text, max_chars)
    translated_chunks = []
    for chunk in chunks:
        result = translate_one(chunk)
        if not result:
            return None
        translated_chunks.append(result)
    return "\n\n".join(translated_chunks)


def _translate_with_fallback_providers(text: str, source: str, target: str) -> Optional[str]:
    """
    Try each provider in order; return the first non-empty result, or None
    if all of them fail (offline, rate-limited, service down, wrong
    language code, text too long for that provider's own limit, etc.). Each
    provider's exceptions are caught and logged individually so one
    provider's failure doesn't stop us from trying the next -- but the
    reason is still visible in the logs, instead of disappearing into a
    bare `False`.
    """
    key = _cache_key(text, source, target)
    cached = _cache_get(key)
    if cached is not None:
        logger.info("translation cache hit (%s->%s, %d chars)", source, target, len(text))
        return cached

    providers: List[Tuple[str, Callable[[str], Optional[str]], int]] = []

    # Bhashini first (primary), per the problem statement's explicit preference
    # for national language infrastructure. Only added to the chain when
    # credentials are configured — otherwise _bhashini_translate_one would
    # just return None on every chunk, so skip it outright to avoid a
    # pointless network attempt per chunk.
    if _bhashini_credentials() and _HTTPX_AVAILABLE:
        providers.append((
            "bhashini",
            lambda t: _bhashini_translate_one(t, source, target),
            _PROVIDER_MAX_CHARS["bhashini"],
        ))

    # Sarvam next (fallback): authenticated Indian language translation API.
    # Only added when SARVAM_API_KEY is configured.
    if _SARVAM_AVAILABLE and _sarvam_api_key():
        providers.append((
            "sarvam",
            lambda t: _sarvam_translate_one(t, source, target),
            _PROVIDER_MAX_CHARS["sarvam"],
        ))

    if _AVAILABLE:
        providers += [
            (
                "google",
                lambda t: GoogleTranslator(source=source, target=target).translate(t),
                _PROVIDER_MAX_CHARS["google"],
            ),
            (
                "mymemory",
                lambda t: MyMemoryTranslator(
                    source=_MYMEMORY_LANG_MAP.get(source, source),
                    target=_MYMEMORY_LANG_MAP.get(target, target),
                ).translate(t),
                _PROVIDER_MAX_CHARS["mymemory"],
            ),
        ]

    if not providers:
        return None

    for name, translate_one, max_chars in providers:
        try:
            result = _translate_full_text(text, translate_one, max_chars)
            if result:
                logger.info(
                    "translation succeeded via '%s' (%s->%s, %d chars)",
                    name, source, target, len(text),
                )
                _cache_put(key, result)
                return result
        except Exception as e:
            logger.info("translation provider '%s' failed: %r", name, e)
            continue
    return None


def bhashini_status() -> dict:
    """Small transparency helper for /api/health and the eval dashboard —
    reports whether Bhashini NMT (translation) is actually configured in
    this deployment, without leaking the credential values themselves. See
    sarvam_translate_status() above and app/asr.py's asr_status() for the
    sibling credential checks."""
    configured = _bhashini_credentials() is not None and _HTTPX_AVAILABLE
    return {
        "configured": configured,
        "note": (
            "BHASHINI_NMT_USER_ID / BHASHINI_NMT_API_KEY set — Bhashini is "
            "the primary translation provider."
            if configured
            else "Not configured in this environment — falling back to "
            "Sarvam / Google Translate / MyMemory. Set "
            "BHASHINI_NMT_USER_ID and BHASHINI_NMT_API_KEY to enable the "
            "Bhashini (ULCA) NMT provider as primary."
        ),
    }


def translate_text(text: str, target_lang: str) -> Tuple[str, bool]:
    """
    Returns (text, translated_ok). If target_lang is 'en' or empty text,
    returns the original text untouched with translated_ok=True (no-op).
    """
    if not text or target_lang == "en" or target_lang not in _LANG_MAP:
        return text, True

    # Chunked per-provider inside _translate_with_fallback_providers -- long
    # multi-source answers now translate correctly instead of silently
    # failing MyMemory's 500-char limit.
    translated = _translate_with_fallback_providers(text, "en", _LANG_MAP[target_lang])
    if translated is None:
        return text, False
    return translated, True


def translate_to_english(text: str, source_lang: str) -> Tuple[str, bool]:
    """
    The other half of the pipeline: translate a non-English *query* to
    English so it can be matched against the (English) authoritative
    corpus. This is a retrieval-only step — the original query text is
    always preserved separately for display/logging; only this translated
    copy is used to build the retrieval query.

    Returns (text, translated_ok), same contract as translate_text().
    """
    if not text or source_lang == "en" or source_lang not in _LANG_MAP:
        return text, True

    translated = _translate_with_fallback_providers(text, _LANG_MAP[source_lang], "en")
    if translated is None:
        return text, False
    return translated, True
