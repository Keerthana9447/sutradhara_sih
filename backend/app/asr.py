"""
Speech-to-text and text-to-speech.

PROVIDER CHAIN — same shape for both directions, and deliberately kept
consistent with app/translate.py's answer-translation chain:

  1. Bhashini (ULCA pipeline API — taskType "asr" for transcribe(),
     taskType "tts" for synthesize()) — tried first as primary, per the
     problem statement's explicit priority for national language infrastructure.
     Two live HTTP calls per request: (a) getModelsPipeline to resolve
     the serviceId + inference endpoint for the requested language and
     task, (b) the inference call itself.
  2. Sarvam AI (Saaras v3 for STT, Bulbul v3 for TTS) — fallback if
     Bhashini is unconfigured or the call fails. Authenticated API
     purpose-built for Indian languages, requires SARVAM_API_KEY.

     Bhashini's ASR models are generally trained on WAV/FLAC PCM audio;
     the browser's MediaRecorder (frontend MicButton fallback, when wired
     up) typically produces WebM/Opus. Sending audio_format "webm"
     straight through is not guaranteed to work against Bhashini's ASR
     service the way it does against Sarvam's more format-tolerant Saaras
     model — if Bhashini's ASR needs actual WAV PCM, that's a
     frontend-side re-encode, not something this module can fix after the
     fact. Documented here rather than silently assumed to work; the
     function still fails safe (returns None) rather than raising if the
     format is rejected, falling back to Sarvam or failing safe. Bhashini
     TTS returns WAV audio regardless of input, so synthesize()'s output
     contract (base64 WAV) is unchanged whichever provider actually served
     the request.

  Credentials — three tiers, checked in this order, same pattern as
  translate.py's BHASHINI_NMT_USER_ID / BHASHINI_NMT_API_KEY fallback:
    - Task-specific: BHASHINI_ASR_USER_ID/BHASHINI_ASR_API_KEY for ASR,
      BHASHINI_TTS_USER_ID/BHASHINI_TTS_API_KEY for TTS.
    - Shared voice pair: BHASHINI_ASR_USER_ID/BHASHINI_ASR_API_KEY is also
      read for TTS if no TTS-specific pair is set — ASR and TTS are
      normally authorized together under one ULCA subscription, so
      whichever pair was set up first usually covers both.
    - Fully shared: unprefixed BHASHINI_USER_ID/BHASHINI_API_KEY (the same
      fallback translate.py's NMT provider reads), for a single-account
      setup covering translation, ASR and TTS all at once.

  If both providers fail for a given call (unconfigured, network error,
  unsupported format, service down), transcribe()/synthesize() fall back to
  their original behavior unchanged: transcribe() returns an explanatory
  failure string with success=False so the frontend can let the person type
  instead; synthesize() returns None so the frontend's Read Aloud button
  stays disabled rather than erroring.
"""
import base64
import logging
import os
import tempfile
from typing import Optional

try:
    from sarvamai import SarvamAI
    _SARVAM_AVAILABLE = True
except ImportError:
    SarvamAI = None
    _SARVAM_AVAILABLE = False

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

logger = logging.getLogger("ip_sakti.asr")

SUPPORTED_ASR_LANGUAGES = ("en", "hi", "te", "ta", "ml")
_LANGUAGE_CODES = {"en": "en-IN", "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN", "ml": "ml-IN", "sa": "hi-IN"}


def _sarvam_client() -> Optional[object]:
    api_key = os.getenv("SARVAM_API_KEY")
    if not _SARVAM_AVAILABLE or not api_key:
        return None
    return SarvamAI(api_subscription_key=api_key)


def asr_status() -> dict:
    """Report whether Sarvam SDK and credentials are available for fallback.
    See bhashini_asr_status() below for the primary provider's check —
    kept as a separate function (rather than folded into this one) so
    /api/health can show both independently, same pattern as
    translate.sarvam_translate_status() / translate.bhashini_status()."""
    configured = _SARVAM_AVAILABLE and bool(os.getenv("SARVAM_API_KEY"))
    return {
        "configured": configured,
        "provider": "sarvam",
        "note": (
            "Sarvam Saaras speech-to-text and Bulbul text-to-speech are configured as fallback."
            if configured
            else "Set SARVAM_API_KEY in the environment for fallback ASR/TTS."
        ),
    }


def _transcribe_via_sarvam(audio_base64: str, audio_format: str) -> Optional[str]:
    """Transcribe one browser recording with Sarvam Saaras v3."""
    client = _sarvam_client()
    if client is None:
        return None

    suffix = "." + (audio_format.lower() or "webm")
    temp_path = None
    try:
        audio_content = base64.b64decode(audio_base64, validate=True)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
            audio_file.write(audio_content)
            temp_path = audio_file.name
        with open(temp_path, "rb") as audio_file:
            response = client.speech_to_text.transcribe(
                file=audio_file, model="saaras:v3", mode="transcribe"
            )
        return response.transcript.strip() or None
    except Exception as error:
        logger.info("Sarvam ASR failed: %r", error)
        return None
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# --------------------------------------------------------------------------
# Bhashini (ULCA) ASR fallback
# --------------------------------------------------------------------------
# Same public pipeline config endpoint and default pipelineId used by
# app/translate.py's Bhashini NMT provider — one ULCA pipeline resource
# covers ASR, translation and TTS taskTypes together; only the taskType in
# the request payload changes.
_BHASHINI_PIPELINE_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
_BHASHINI_DEFAULT_ASR_PIPELINE_ID = "64392f96daac500b55c543cd"
_BHASHINI_TIMEOUT_SECONDS = 8.0


def _bhashini_asr_credentials() -> Optional[tuple[str, str]]:
    # ASR-specific names take priority; unprefixed names are the same
    # backward-compatible shared-account fallback used by translate.py's
    # _bhashini_credentials() for the NMT (translation) provider.
    user_id = os.getenv("BHASHINI_ASR_USER_ID") or os.getenv("BHASHINI_USER_ID")
    api_key = os.getenv("BHASHINI_ASR_API_KEY") or os.getenv("BHASHINI_API_KEY")
    if user_id and api_key:
        return user_id, api_key
    return None


def bhashini_asr_status() -> dict:
    """Small transparency helper for /api/health — reports whether the
    Bhashini ASR provider is actually usable in this deployment, without
    leaking the credential values themselves. See asr_status() above and
    translate.bhashini_status() for the sibling credential checks."""
    configured = _bhashini_asr_credentials() is not None and _HTTPX_AVAILABLE
    return {
        "configured": configured,
        "provider": "bhashini",
        "note": (
            "BHASHINI_ASR_USER_ID / BHASHINI_ASR_API_KEY (or the shared "
            "BHASHINI_USER_ID / BHASHINI_API_KEY) set — Bhashini ASR is "
            "the primary speech-to-text provider."
            if configured
            else "Not configured in this environment — voice input falls "
            "back to Sarvam. Set BHASHINI_ASR_USER_ID and "
            "BHASHINI_ASR_API_KEY (or the shared BHASHINI_USER_ID / "
            "BHASHINI_API_KEY) to enable Bhashini as primary ASR."
        ),
    }


def _transcribe_via_bhashini(
    audio_base64: str, source_language: str, audio_format: str, sampling_rate: int
) -> Optional[str]:
    """
    One Bhashini/ULCA ASR call for a single recording. Returns None (never
    raises) on any failure — missing credentials, no network route, HTTP
    error, an audio format/codec Bhashini's ASR model doesn't accept, or an
    unexpected response shape — so the caller can fall through / fail safe
    unconditionally, same contract as _transcribe_via_sarvam above and every
    provider function in translate.py.
    """
    creds = _bhashini_asr_credentials()
    if not creds or not _HTTPX_AVAILABLE:
        return None
    user_id, api_key = creds

    pipeline_id = os.getenv(
        "BHASHINI_ASR_PIPELINE_ID",
        os.getenv("BHASHINI_PIPELINE_ID", _BHASHINI_DEFAULT_ASR_PIPELINE_ID),
    )
    headers = {
        "Content-Type": "application/json",
        "userID": user_id,
        "ulcaApiKey": api_key,
    }
    config_payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {"language": {"sourceLanguage": source_language}},
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
                        "taskType": "asr",
                        "config": {
                            "language": {"sourceLanguage": source_language},
                            "serviceId": service_id,
                            "audioFormat": audio_format,
                            "samplingRate": sampling_rate,
                        },
                    }
                ],
                "inputData": {"audio": [{"audioContent": audio_base64}]},
            }
            inference_headers = {
                "Content-Type": "application/json",
                inference_api_name: inference_api_value,
            }
            inf_resp = client.post(inference_url, headers=inference_headers, json=inference_payload)
            inf_resp.raise_for_status()
            result = inf_resp.json()
            transcript = result["pipelineResponse"][0]["output"][0]["source"]
            return transcript.strip() or None
    except Exception as error:
        logger.info("Bhashini ASR failed (%s): %r", source_language, error)
        return None


def synthesize(text: str, language: str = "en", speaker: str = "shubh") -> Optional[str]:
    """Return base64-encoded WAV audio. Tries Bhashini TTS first as primary, then
    falls back to Sarvam Bulbul v3 if Bhashini is unconfigured or fails — see the
    module docstring for the full chain. ``speaker`` is Sarvam-specific
    (voice name, e.g. "shubh") and has no effect on the Bhashini provider,
    which instead picks a gender via _BHASHINI_TTS_GENDER."""
    if not text.strip() or len(text) > 6000:
        return None

    audio = _synthesize_via_bhashini(text, language)
    if audio:
        return audio

    return _synthesize_via_sarvam(text, language, speaker)


def _synthesize_via_sarvam(text: str, language: str, speaker: str) -> Optional[str]:
    client = _sarvam_client()
    if client is None:
        return None
    try:
        response = client.text_to_speech.convert(
            text=text.strip(), model="bulbul:v3",
            language_code=_LANGUAGE_CODES.get(language, "en-IN"), speaker=speaker,
        )
        return "".join(response.audios)
    except Exception as error:
        logger.info("Sarvam TTS failed: %r", error)
        return None


# --------------------------------------------------------------------------
# Bhashini (ULCA) TTS provider
# --------------------------------------------------------------------------
_BHASHINI_DEFAULT_TTS_PIPELINE_ID = _BHASHINI_DEFAULT_ASR_PIPELINE_ID  # same multi-task pipeline resource
_BHASHINI_TTS_GENDER = "female"  # Bhashini TTS voices are selected by gender, not a named speaker like Sarvam's
_BHASHINI_TTS_SAMPLING_RATE = 8000


def _bhashini_tts_credentials() -> Optional[tuple[str, str]]:
    # TTS-specific names take priority; the ASR pair is checked next since
    # ASR and TTS are normally authorized together under one ULCA voice
    # subscription; unprefixed names are the final fully-shared fallback
    # (same one translate.py's NMT provider and _bhashini_asr_credentials()
    # above both read).
    user_id = (
        os.getenv("BHASHINI_TTS_USER_ID")
        or os.getenv("BHASHINI_ASR_USER_ID")
        or os.getenv("BHASHINI_USER_ID")
    )
    api_key = (
        os.getenv("BHASHINI_TTS_API_KEY")
        or os.getenv("BHASHINI_ASR_API_KEY")
        or os.getenv("BHASHINI_API_KEY")
    )
    if user_id and api_key:
        return user_id, api_key
    return None


def bhashini_tts_status() -> dict:
    """Small transparency helper for /api/health — reports whether the
    Bhashini TTS provider is actually usable in this deployment, without
    leaking the credential values themselves. See bhashini_asr_status()
    above and translate.bhashini_status() for the sibling credential
    checks."""
    configured = _bhashini_tts_credentials() is not None and _HTTPX_AVAILABLE
    return {
        "configured": configured,
        "provider": "bhashini",
        "note": (
            "BHASHINI_TTS_USER_ID / BHASHINI_TTS_API_KEY (or the shared "
            "BHASHINI_ASR_* / BHASHINI_* credentials) set — Bhashini TTS is "
            "the primary text-to-speech provider."
            if configured
            else "Not configured in this environment — Read Aloud falls "
            "back to Sarvam. Set BHASHINI_TTS_USER_ID and "
            "BHASHINI_TTS_API_KEY (or reuse the BHASHINI_ASR_* / shared "
            "BHASHINI_* credentials) to enable Bhashini as primary TTS."
        ),
    }


def _synthesize_via_bhashini(text: str, language: str) -> Optional[str]:
    """
    One Bhashini/ULCA TTS call. Returns None (never raises) on any failure
    — missing credentials, no network route, HTTP error, or an unexpected
    response shape — so the caller can fail safe unconditionally, same
    contract as _transcribe_via_bhashini above and every provider function
    in translate.py.
    """
    creds = _bhashini_tts_credentials()
    if not creds or not _HTTPX_AVAILABLE:
        return None
    user_id, api_key = creds

    pipeline_id = os.getenv(
        "BHASHINI_TTS_PIPELINE_ID",
        os.getenv("BHASHINI_PIPELINE_ID", _BHASHINI_DEFAULT_TTS_PIPELINE_ID),
    )
    # Bhashini pipeline routes Sanskrit (Devanagari script) under the
    # Indo-Aryan/Devanagari model ('hi').
    bhashini_lang = "hi" if language == "sa" else language

    headers = {
        "Content-Type": "application/json",
        "userID": user_id,
        "ulcaApiKey": api_key,
    }
    config_payload = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {"language": {"sourceLanguage": bhashini_lang}},
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
                        "taskType": "tts",
                        "config": {
                            "language": {"sourceLanguage": bhashini_lang},
                            "serviceId": service_id,
                            "gender": _BHASHINI_TTS_GENDER,
                            "samplingRate": _BHASHINI_TTS_SAMPLING_RATE,
                        },
                    }
                ],
                "inputData": {"input": [{"source": text.strip()}]},
            }
            inference_headers = {
                "Content-Type": "application/json",
                inference_api_name: inference_api_value,
            }
            inf_resp = client.post(inference_url, headers=inference_headers, json=inference_payload)
            inf_resp.raise_for_status()
            result = inf_resp.json()
            audio_content = result["pipelineResponse"][0]["audio"][0]["audioContent"]
            return audio_content or None
    except Exception as error:
        logger.info("Bhashini TTS failed (%s): %r", language, error)
        return None


def transcribe(audio_base64: str, source_language: str = "en",
               audio_format: str = "wav", sampling_rate: int = 16000) -> tuple[str, bool]:
    """Return ``(transcript, success)`` without raising into the API handler.
    Tries Bhashini ASR first as primary, then falls back to Sarvam Saaras
    if Bhashini is unconfigured or fails — see the module docstring for the full chain."""
    if source_language not in SUPPORTED_ASR_LANGUAGES:
        return (
            f"Voice input isn't supported for language '{source_language}' yet.",
            False,
        )

    if not audio_base64 or not audio_base64.strip():
        return "No audio received.", False

    transcript = _transcribe_via_bhashini(audio_base64, source_language, audio_format, sampling_rate)
    if transcript:
        return transcript, True

    transcript = _transcribe_via_sarvam(audio_base64, audio_format)
    if transcript:
        return transcript, True

    return (
        "Couldn't transcribe that — Bhashini and Sarvam speech-to-text are both "
        "unavailable or unconfigured in this environment. You can type your "
        "question instead.",
        False,
    )
