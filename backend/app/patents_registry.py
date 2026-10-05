"""
Public prior-art reference browser — /api/v1/patents

Public entries are illustrative and are not records from the restricted TKDL.
Private citizen claims are excluded unless an explicit publication-consent
workflow is implemented.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ip_sakti.patents_registry")

# Illustrative public references; these are not records from the restricted TKDL.
_PUBLIC_REFERENCE_ENTRIES = [
    {
        "id": "REF-PUB-001", "system": "Ayurveda", "name": "Triphala Churna",
        "description": "A classical combination of three myrobalans (Terminalia chebula, Terminalia bellirica, Emblica officinalis) used as a rasayana and for digestive health.",
        "source_text": "Charaka Samhita, Chikitsa Sthana, Chapter 1",
        "ingredients": ["Haritaki", "Bibhitaki", "Amalaki"],
        "therapeutic_use": "Digestive disorders, rasayana, ophthalmology",
        "status": "Illustrative public lead - not an official TKDL record; verify sources independently",
    },
    {
        "id": "REF-PUB-002", "system": "Ayurveda", "name": "Ashwagandha Churna",
        "description": "Powdered root of Withania somnifera used as an adaptogen and rejuvenating tonic.",
        "source_text": "Ashtanga Hridayam, Uttara Sthana",
        "ingredients": ["Withania somnifera (root)"],
        "therapeutic_use": "Stress, fatigue, reproductive health",
        "status": "Illustrative public lead - not an official TKDL record; verify sources independently",
    },
    {
        "id": "REF-PUB-003", "system": "Ayurveda", "name": "Neem Formulation for Skin",
        "description": "Publicly reported traditional uses of Azadirachta indica for skin conditions; verify exact sources independently.",
        "source_text": "Illustrative public reference; source-level verification required",
        "ingredients": ["Neem bark", "Neem leaves", "Sesame oil"],
        "therapeutic_use": "Skin diseases, wound healing, antimicrobial",
        "status": "Illustrative public traditional-knowledge lead; neem opposition was an EPO proceeding. Not an official TKDL record.",
    },
    {
        "id": "REF-PUB-004", "system": "Ayurveda", "name": "Turmeric for Wound Healing",
        "description": "Curcuma longa application on wounds. Related US Patent 5,401,504 was assigned to the University of Mississippi Medical Center and revoked after USPTO re-examination in 1997.",
        "source_text": "US Patent 5,401,504; public historical prior-art example, not an official TKDL record",
        "ingredients": ["Curcuma longa (rhizome)"],
        "therapeutic_use": "Wound healing, anti-inflammatory",
        "status": "Public prior-art example — US patent revoked after re-examination; not an official TKDL record",
    },
    {
        "id": "REF-PUB-005", "system": "Siddha", "name": "Kalpaamruthaa",
        "description": "A classical Siddha formulation for chronic conditions using multiple mineral-herbal ingredients.",
        "source_text": "Siddha Materia Medica",
        "ingredients": ["Emblica officinalis", "Piper longum", "Terminalia chebula"],
        "therapeutic_use": "Chronic diseases, immunomodulation",
        "status": "Illustrative public lead - not an official TKDL record; verify sources independently",
    },
    {
        "id": "REF-PUB-006", "system": "Unani", "name": "Arq-e-Badiyan (Fennel Water)",
        "description": "Distilled fennel water preparation in Unani Tibb for digestive ailments.",
        "source_text": "Qarabadin-e-Qadeem",
        "ingredients": ["Foeniculum vulgare"],
        "therapeutic_use": "Flatulence, digestive disorders",
        "status": "Illustrative public lead - not an official TKDL record; verify sources independently",
    },
]


def browse_registry(
    system: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return paginated illustrative public references; private claims are excluded."""
    entries = list(_PUBLIC_REFERENCE_ENTRIES)

    if system:
        entries = [e for e in entries if e["system"].lower() == system.lower()]
    if keyword:
        kw = keyword.lower()
        entries = [e for e in entries if
                   kw in e["name"].lower() or
                   kw in e["description"].lower() or
                   any(kw in ing.lower() for ing in e["ingredients"])]

    all_entries = entries

    total = len(all_entries)
    page = all_entries[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": page,
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

