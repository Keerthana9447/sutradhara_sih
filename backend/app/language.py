"""
Input-language detection + fallback query normalization.

This is the missing piece in the pipeline: previously `language` on
AnalyzeRequest only controlled *output* translation. The query text itself
was passed straight into classify()/route_areas()/retrieve(), all of which
only understand English keywords/tokens. For a Telugu query that meant a
guaranteed zero-relevance retrieval (see retrieval.py docstring for the
mechanism), regardless of how good the underlying corpus match actually was.

detect_language() looks at the query text itself (Unicode script), not a
UI toggle or browser locale, per the "use the actual query text" requirement.

fallback_normalize() is a small, explicit second line of defense: if the real
translator (translate.translate_to_english) is unavailable or fails, we still
want *some* English signal for retrieval rather than silently returning
nothing. It is intentionally tiny and is never used to author legal claims —
only to help the TF-IDF retriever match on domain terms.
"""
import re

_TELUGU_RANGE = re.compile(r"[\u0C00-\u0C7F]")
_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")
_TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
_MALAYALAM_RANGE = re.compile(r"[\u0D00-\u0D7F]")

# Sanskrit and Hindi both use the Devanagari script, so script alone cannot
# distinguish them -- there is no Unicode range unique to Sanskrit. Rather
# than silently mislabel one as the other, we look for a short list of
# grammatical markers (verb forms, particles) that are common in Sanskrit
# prose but rare-to-absent in everyday Hindi, and bias toward "sa" only when
# at least one appears. This is a heuristic, not a real language-ID model:
# a short or ambiguous Devanagari query with no such marker defaults to
# "hi", since that is the far more common real-world case for this app's
# audience. Document this rather than claim false precision.
_SANSKRIT_MARKERS = re.compile(
    r"(अस्ति|भवति|इति|कुरुत|करोति|अस्मि|वयम्|एतत्|तत्र|यत्र|कस्मात्|भवन्तः|प्राप्तुं|शक्नोमि|शक्नोति)"
)


def detect_language(text: str) -> str:
    """Detect input language from the query text itself.

    Telugu, Tamil, Malayalam, Hindi, Sanskrit, and English are distinguished
    by Unicode script (Hindi/Sanskrit additionally by a marker-word
    heuristic, see _SANSKRIT_MARKERS above). This is a targeted detector,
    not a general language-ID model.
    """
    if text and _TELUGU_RANGE.search(text):
        return "te"
    if text and _TAMIL_RANGE.search(text):
        return "ta"
    if text and _MALAYALAM_RANGE.search(text):
        return "ml"
    if text and _DEVANAGARI_RANGE.search(text):
        return "sa" if _SANSKRIT_MARKERS.search(text) else "hi"
    return "en"


# Small, explicit term glossary — used ONLY as a fallback normalization
# strategy when live translation is unavailable (see main.py). NOT a
# replacement for real translation, and NOT applied to the corpus or to
# anything shown to the user.
TELUGU_TERM_MAP = {
    "పేటెంట్": "patent",
    "సాంప్రదాయ జ్ఞానం": "traditional knowledge",
    "ఆయుర్వేదం": "Ayurveda",
    "ఆయుర్వేద": "Ayurvedic",
    "శాస్త్రీయ": "classical",
    "ఫార్ములేషన్": "formulation",
    "జీవ వనరులు": "biological resources",
    "ప్రయోజన భాగస్వామ్యం": "access and benefit sharing",
    "గ్రంథం": "text",
    "సంప్రదాయ": "traditional",
}

HINDI_TERM_MAP = {
    "पेटेंट": "patent",
    "पारंपरिक ज्ञान": "traditional knowledge",
    "आयुर्वेदिक": "Ayurvedic",
    "आयुर्वेद": "Ayurveda",
    "शास्त्रीय": "classical",
    "फॉर्मूलेशन": "formulation",
    "जैविक संसाधन": "biological resources",
    "लाभ साझा करना": "access and benefit sharing",
    "ग्रंथ": "text",
    "पारंपरिक": "traditional",
}

TAMIL_TERM_MAP = {
    "காப்புரிமை": "patent",
    "பாரம்பரிய அறிவு": "traditional knowledge",
    "ஆயுர்வேத": "Ayurvedic",
    "ஆயுர்வேதம்": "Ayurveda",
    "பாரம்பரிய": "classical",
    "சூத்திரமாக்கம்": "formulation",
    "உயிரியல் வளங்கள்": "biological resources",
    "பயன் பகிர்வு": "access and benefit sharing",
    "நூல்": "text",
    "மரபு": "traditional",
}

MALAYALAM_TERM_MAP = {
    "പേറ്റന്റ്": "patent",
    "പരമ്പരാഗത അറിവ്": "traditional knowledge",
    "ആയുർവേദ": "Ayurvedic",
    "ആയുർവേദം": "Ayurveda",
    "ക്ലാസിക്കൽ": "classical",
    "ഫോർമുലേഷൻ": "formulation",
    "ജൈവ വിഭവങ്ങൾ": "biological resources",
    "പ്രയോജന പങ്കിടൽ": "access and benefit sharing",
    "ഗ്രന്ഥം": "text",
    "പരമ്പരാഗതം": "traditional",
}

# Sanskrit's modern administrative/technical vocabulary is not standardized
# the way Hindi's is (there is no single widely-used Sanskrit legal-tech
# register), so several entries below are Sanskritized loanwords/calques of
# the kind used in All India Radio's Sanskrit bulletins and Sanskrit
# Wikipedia, not attested classical terms. This map exists only to help the
# offline retrieval fallback match on domain concepts -- it is never shown
# to the user as an authoritative translation.
SANSKRIT_TERM_MAP = {
    "पेटेण्ट्": "patent",
    "परम्परागतं ज्ञानम्": "traditional knowledge",
    "आयुर्वेदीयम्": "Ayurvedic",
    "आयुर्वेदः": "Ayurveda",
    "शास्त्रीयम्": "classical",
    "सूत्रीकरणम्": "formulation",
    "जैविकं संसाधनम्": "biological resources",
    "लाभ-साझाकरणम्": "access and benefit sharing",
    "ग्रन्थः": "text",
    "परम्परागतम्": "traditional",
}


def fallback_normalize(text: str) -> str:
    """Best-effort English gloss built by substring term substitution.

    Used only when the real translator call fails/is offline. Strips any
    remaining non-Latin characters afterward so leftover Telugu text can't
    silently zero out the TF-IDF tokenizer again.
    """
    out = text
    for term_map in (TELUGU_TERM_MAP, HINDI_TERM_MAP, TAMIL_TERM_MAP, MALAYALAM_TERM_MAP, SANSKRIT_TERM_MAP):
        for source_term, en_term in term_map.items():
            out = out.replace(source_term, f" {en_term} ")
    out = re.sub(r"[^\x00-\x7F]+", " ", out)
    return re.sub(r"\s+", " ", out).strip()
