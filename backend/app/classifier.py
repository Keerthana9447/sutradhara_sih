"""
Deterministic two-stage query understanding.

Legal intent selects retrieval domains; product classification is inferred
separately and only requested when it is needed to answer a product-category
question. This keeps words such as "proprietary" from turning a trade-secret
or patent question into a medicine classification.
"""
import re
from typing import Optional

from .schemas import ClassificationResult

CATEGORIES = [
    "Classical / Generic Medicine",
    "Patent / Proprietary Medicine",
    "New / Non-Classical Drug",
    "Phytopharmaceutical",
    "Ayurveda-Aahar / Nutraceutical",
    "Cosmetic",
]

UNKNOWN_CATEGORY = "Unknown / Not Required"

INTENTS = [
    "Patent / Patentability",
    "Traditional Knowledge",
    "Access and Benefit Sharing",
    "Trade Secrets / Confidential Information",
    "Geographical Indications",
    "Trademarks",
    "Copyright",
    "Designs",
    "Plant Variety Protection",
    "Drug Regulation",
    "Food / Nutraceutical",
    "Cosmetic",
    "General IP / Regulatory Guidance",
    "Out of Scope",
]

_INTENT_TERMS = [
    ("Access and Benefit Sharing", (
        "access and benefit sharing", "access and benefit-sharing", "benefit sharing",
        "benefit-sharing", "biodiversity",
        "biological resource", "biological resources", "genetic resource",
        "genetic resources", "national biodiversity authority",
        "nba approval", "nagoya", "abs obligation", "abs approval",
    )),
    ("Trade Secrets / Confidential Information", (
        "trade secret", "confidential", "non-disclosure", "nondisclosure",
        "breach of confidence", "undisclosed information", "nda",
    )),
    ("Patent / Patentability", (
        "patent", "patentability", "patentable", "invention", "inventive step",
        "novelty", "pct application", "patents act",
    )),
    ("Traditional Knowledge", (
        "traditional knowledge", "classical text", "traditional text", "tkdl",
        "prior art", "traditional formulation", "gratk",
    )),
    ("Plant Variety Protection", (
        "plant variety", "plant-variety", "seed variety", "cultivar",
        "breeders right", "breeder's right", "upov",
    )),
    ("Geographical Indications", (
        "geographical indication", "geographical indications", "gi registration",
        "gi tag", "regional indication",
    )),
    ("Trademarks", (
        "trademark", "trade mark", "brand name", "logo registration",
        "madrid protocol",
    )),
    ("Copyright", (
        "copyright", "literary work", "artistic work", "berne convention",
    )),
    ("Designs", (
        "industrial design", "design registration", "product shape", "hague agreement",
    )),
    ("Food / Nutraceutical", (
        "nutraceutical", "health supplement", "food supplement", "functional food",
        "dietary supplement", "ayurveda aahar", "ayurveda-aahar", "fssai",
        "dshea", "new dietary ingredient",
    )),
    ("Cosmetic", (
        "cosmetic", "skincare", "skin care", "beauty product", "cosmetic claim",
    )),
    ("Drug Regulation", (
        "drug regulation", "drug licence", "drug license", "manufacturing licence",
        "manufacturing license", "drug approval", "drug registration", "clinical",
        "herbal medicinal product", "traditional herbal registration", "thmpd",
        "mhra", "natural health product", "marketing authorisation",
        "marketing authorization", "regulatory requirement", "regulatory pathway",
        "phytopharmaceutical",
    )),
]

_CATEGORY_TERMS = {
    "Classical / Generic Medicine": (
        "classical ayurvedic formulation", "classical formulation",
        "classical ayurvedic medicine", "classical medicine",
        "classical ayurvedic herbal tablet", "classical herbal tablet",
        "classical ayurvedic herbal medicine", "classical herbal medicine",
        "traditional ayurvedic formulation", "traditional ayurvedic medicine",
        "described in a classical text", "described in the ayurvedic formulary",
        "formulation described in", "already described in a traditional text",
        "known classical formulation",
    ),
    "Patent / Proprietary Medicine": (
        "patent/proprietary medicine", "patent or proprietary medicine",
        "patent and proprietary medicine", "proprietary ayurvedic medicine",
        "proprietary medicine",
    ),
    "New / Non-Classical Drug": (
        "new ayurvedic formulation", "new formulation", "novel formulation",
        "new non-classical drug", "new drug", "not documented in a classical",
        "not found in a classical", "not found in any classical",
        "not described in a classical", "not a classical formulation",
    ),
    "Phytopharmaceutical": (
        "phytopharmaceutical", "standardized extract", "standardised extract",
        "purified botanical extract", "botanical drug", "isolated compound",
    ),
    "Ayurveda-Aahar / Nutraceutical": (
        "nutraceutical", "health supplement", "food supplement", "functional food",
        "dietary supplement", "ayurveda aahar", "ayurveda-aahar", "food product",
    ),
    "Cosmetic": (
        "cosmetic product", "herbal cosmetic", "skincare product", "skin care product",
        "face cream", "face pack", "skin brightening", "skin whitening",
        "beauty product", "hair oil", "soap",
    ),
}

_OUT_OF_SCOPE_TERMS = ("quantum computing", "boiling point of tungsten")
_AYURVEDA_CONTEXT = (
    "ayurved", "herbal", "medicinal plant", "formulation", "medicine", "drug",
    "biological resource", "genetic resource", "traditional knowledge",
)
_CLASSIFICATION_QUESTION = re.compile(
    r"\b(what category|which category|classify|classification|is this a|"
    r"what type of (?:medicine|drug|product)|which licence|which license|"
    r"what licence|what license|what approval route|which approval route)\b"
)
_VAGUE_PRODUCT_QUESTION = re.compile(
    r"\b(tell me about|advise me about|help me with)\b.*\b(product|formulation|medicine)\b",
    re.IGNORECASE,
)
_NEW_FORMULATION_PATTERNS = (
    re.compile(r"not\s+(found|documented|described|present)\s+in\s+(any\s+|a\s+)?classical"),
    re.compile(r"not\s+in\s+any\s+classical"),
    re.compile(r"non[\s-]?classical"),
    re.compile(r"not\s+a\s+classical"),
)


def detect_intent(query: str) -> str:
    """Return one deterministic legal-domain label or ``Out of Scope``."""
    q = (query or "").lower()
    if any(term in q for term in _OUT_OF_SCOPE_TERMS):
        return "Out of Scope"
    if (
        "ip and regulatory" in q
        or "intellectual property and regulatory" in q
        or "ip/regulatory considerations" in q
    ) and not any(
        _contains_term(q, term)
        for intent, terms in _INTENT_TERMS
        if intent not in {"Traditional Knowledge", "Drug Regulation"}
        for term in terms
    ):
        return "General IP / Regulatory Guidance"

    for intent, terms in _INTENT_TERMS:
        if any(_contains_term(q, term) for term in terms):
            return intent

    if any(term in q for term in _AYURVEDA_CONTEXT):
        return "General IP / Regulatory Guidance"
    return "Out of Scope"


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def _product_category(query: str) -> Optional[str]:
    q = query.lower()
    if any(pattern.search(q) for pattern in _NEW_FORMULATION_PATTERNS):
        return "New / Non-Classical Drug"

    matched = [
        category
        for category, terms in _CATEGORY_TERMS.items()
        if any(_contains_term(q, term) for term in terms)
    ]
    if (
        "classical" in q
        and ("ayurveda" in q or "ayurvedic" in q)
        and "formulation" in q
    ):
        matched.append("Classical / Generic Medicine")
    if not matched:
        return None

    # Prefer the most specific identified product type when a query compares
    # alternatives (e.g. "cosmetic or drug") or mentions a subcategory.
    priority = {
        "New / Non-Classical Drug": 0,
        "Phytopharmaceutical": 1,
        "Ayurveda-Aahar / Nutraceutical": 2,
        "Cosmetic": 3,
        "Patent / Proprietary Medicine": 4,
        "Classical / Generic Medicine": 5,
    }
    return min(matched, key=priority.__getitem__)


def classify(query: str, confirmed_category: Optional[str] = None) -> ClassificationResult:
    intent = detect_intent(query)
    category = (
        confirmed_category
        if confirmed_category in CATEGORIES
        else _product_category(query)
    )
    if category:
        reason = (
            "Product category confirmed directly by the user."
            if confirmed_category in CATEGORIES
            else f"The query explicitly describes a {category} product/formulation."
        )
        return ClassificationResult(
            category=category,
            product_classification=category,
            intent=intent,
            intent_confidence=0.9 if intent != "Out of Scope" else 0.35,
            classification_required=True,
            confidence=0.99 if confirmed_category in CATEGORIES else 0.85,
            reason=reason,
            needs_clarification=False,
        )

    # Legal intent is enough to route a legal-information query. Do not force
    # a medicine category merely because a law or commercial term was named.
    if intent != "Out of Scope":
        needs_category = bool(
            _CLASSIFICATION_QUESTION.search(query or "")
            or _VAGUE_PRODUCT_QUESTION.search(query or "")
        )
        question = None
        if needs_category:
            question = (
                "Is the product a classical formulation from a First-Schedule "
                "authoritative text, a new/non-classical medicine, a proprietary "
                "medicine, a phytopharmaceutical, an Ayurveda-Aahar/food product, "
                "or a cosmetic?"
            )
        return ClassificationResult(
            category=UNKNOWN_CATEGORY,
            product_classification=UNKNOWN_CATEGORY,
            intent=intent,
            intent_confidence=0.8,
            classification_required=needs_category,
            confidence=0.8,
            reason="The query has a legal/regulatory intent, but does not establish a product category.",
            needs_clarification=needs_category,
            clarification_question=question,
        )

    return ClassificationResult(
        category=UNKNOWN_CATEGORY,
        product_classification=UNKNOWN_CATEGORY,
        intent=intent,
        intent_confidence=0.95,
        classification_required=True,
        confidence=0.35,
        reason="No in-scope IP, regulatory, or product-category signal was found.",
        needs_clarification=True,
        clarification_question=(
            "What Ayurvedic product or IP/regulatory issue would you like help with?"
        ),
    )
