"""
Regulatory pathway checklist.

The classifier tells the user WHAT category their product falls into and
jurisdiction.route_areas() tells them WHICH IP/regulatory areas apply. Neither
tells them WHAT TO ACTUALLY DO NEXT. This module closes that gap: given a
(category, jurisdiction) pair, it returns an ordered list of concrete,
well-known administrative next-steps.

Honesty constraints, matching the rest of the pipeline:
  - Every step describes a real, generally-known administrative pathway
    (e.g. Form 1 is the actual patent application form under the Indian
    Patents Act; the GI Registry is genuinely seated at Chennai). Nothing
    here is invented.
  - Steps are deliberately phrased as an *indicative* sequence ("typically",
    "generally") rather than definitive legal instructions, and each
    checklist carries the same disclaimer used elsewhere in the app — this
    is signposting, not legal advice, and doesn't guarantee any outcome.
  - This is static, rule-based content (like classifier.py), not generated
    by retrieval or an LLM, so it is exactly as auditable as the rest of the
    deterministic pipeline: no risk of a hallucinated authority name.
"""
from typing import List

PATHWAY_DISCLAIMER = (
    "Indicative administrative sequence only, based on the applicable category and "
    "jurisdiction — not legal advice and not a guarantee of any outcome. Confirm current "
    "forms, fees, and timelines with the named authority before acting."
)

# (category, jurisdiction) -> ordered list of next-step strings.
_PATHWAYS = {
    ("Classical / Generic Medicine", "India"): [
        "Check the formulation against the Traditional Knowledge Digital Library (TKDL) reference workflow before any filing — classical formulations are generally barred from patenting under Section 3(p) of the Patents Act, 1970.",
        "If a genuine, non-obvious improvement exists over the classical formulation, consider whether that improvement alone (not the base formulation) could support a separate patent application.",
        "For manufacture and sale, apply for an Ayurvedic drug manufacturing licence from the State Licensing Authority under the Drugs and Cosmetics Act, 1940 (Schedule T for GMP compliance).",
        "If a biological resource (herb, plant, extract) was accessed, check Access-and-Benefit-Sharing obligations with the National Biodiversity Authority (NBA) under the Biological Diversity Act, 2002.",
    ],
    ("Classical / Generic Medicine", "International"): [
        "Confirm the formulation's presence in TKDL, which several foreign patent offices (EPO, USPTO) consult as prior art during examination.",
        "A classical formulation itself is unlikely to be patentable abroad either, for the same prior-art reasons — evaluate only a genuine improvement for filing.",
        "For export, check the herbal/traditional-medicine market-access regime of the destination country (e.g. EU traditional herbal medicinal product registration) separately from any IP filing.",
    ],
    ("Patent / Proprietary Medicine", "India"): [
        "File a patent application using Form 1 with the Indian Patent Office (IPO), supported by a complete specification describing the proprietary formulation.",
        "Register the product's brand name as a trademark with the Trade Marks Registry to protect market identity independent of the patent.",
        "Apply for a proprietary Ayurvedic medicine manufacturing licence from the State Licensing Authority under the Drugs and Cosmetics Act, 1940.",
    ],
    ("Patent / Proprietary Medicine", "International"): [
        "Consider a Patent Cooperation Treaty (PCT) international application to preserve filing dates across multiple countries before national-phase entry.",
        "Register the trademark internationally via the Madrid Protocol if export markets are planned.",
        "Check each target country's drug/health-product import and registration requirements separately from the IP filings.",
    ],
    ("New / Non-Classical Drug", "India"): [
        "File a patent application (Form 1) with the IPO — a genuinely new, non-classical formulation is the strongest category for patentability, subject to novelty and inventive-step examination.",
        "Generate safety and efficacy evidence; new/non-classical Ayurvedic drugs generally require more substantive proof than classical ones under the Drugs and Cosmetics Act, 1940 and Rules, 1945.",
        "Apply for a manufacturing licence from the State Licensing Authority, referencing the new-drug approval pathway rather than the classical-drug pathway.",
    ],
    ("New / Non-Classical Drug", "International"): [
        "File via the PCT international phase to preserve rights across multiple jurisdictions while evidence generation continues.",
        "Plan clinical/safety data generation aligned to each target market's regulatory expectations for a novel herbal drug, which vary by country.",
    ],
    ("Phytopharmaceutical", "India"): [
        "Pursue phytopharmaceutical drug approval, a distinct pathway under the Drugs and Cosmetics Rules for standardized botanical extracts.",
        "File a patent application (Form 1) for the standardized-extract process or formulation if it is genuinely novel over known extracts.",
        "If sourced from a biological resource, check ABS obligations with the NBA under the Biological Diversity Act, 2002.",
    ],
    ("Phytopharmaceutical", "International"): [
        "Check the botanical/herbal drug registration pathway of each target market (these differ significantly by country and are not unified).",
        "Consider a PCT filing for any genuinely novel extraction or standardization process.",
    ],
    ("Ayurveda-Aahar / Nutraceutical", "India"): [
        "Register the product and obtain a licence under the FSSAI Ayurveda-Aahar / health-supplement regulations before sale.",
        "Ensure label claims comply with the Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954 and FSSAI labelling rules.",
        "Register the brand name as a trademark separately from the FSSAI licence.",
    ],
    ("Ayurveda-Aahar / Nutraceutical", "International"): [
        "Check the food-supplement/nutraceutical registration regime of each target export market — these are generally separate from drug-approval regimes.",
        "Register the trademark internationally via the Madrid Protocol if export is planned.",
    ],
    ("Cosmetic", "India"): [
        "Register the product under the cosmetic provisions of the Drugs and Cosmetics Act, 1940 before manufacture or import.",
        "Register the brand name and any distinctive packaging/design (Designs Act, 2000) as applicable.",
    ],
    ("Cosmetic", "International"): [
        "Check the cosmetic-product registration regime of each target market (ingredient restrictions and labelling rules vary widely by country).",
        "Register the trademark internationally via the Madrid Protocol and any distinctive design via the Hague Agreement, if export is planned.",
    ],
}


def get_pathway(category: str, jurisdiction: str) -> List[str]:
    """Return the ordered next-step list for this category+jurisdiction, or
    an empty list if no pathway is defined (never fabricate one)."""
    return list(_PATHWAYS.get((category, jurisdiction), []))
