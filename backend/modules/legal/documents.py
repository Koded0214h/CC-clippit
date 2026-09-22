"""The current version of every legal document Clippit requires consent
for. Content itself is static (it can be built/deployed with the app, or
swapped for a CMS later — see production-api-inventory.md §R); what the
backend must own is the *acceptance record*, which is what this module is
really for. Placeholder copy below is not real legal text — this needs
counsel-reviewed content before launch.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LegalDocument:
    slug: str
    version: str
    title: str
    effective_date: str  # ISO date
    body: str


REGISTRY: dict[str, LegalDocument] = {
    d.slug: d
    for d in [
        LegalDocument(
            slug="terms",
            version="1",
            title="Terms of Service",
            effective_date="2026-01-01",
            body="Placeholder — needs counsel-reviewed Terms of Service copy before launch.",
        ),
        LegalDocument(
            slug="privacy",
            version="1",
            title="Privacy Policy",
            effective_date="2026-01-01",
            body="Placeholder — needs counsel-reviewed Privacy Policy copy before launch.",
        ),
        LegalDocument(
            slug="community-rules",
            version="1",
            title="Community Rules",
            effective_date="2026-01-01",
            body="Placeholder — needs counsel-reviewed Community Rules copy before launch.",
        ),
        LegalDocument(
            slug="campaign-funding-terms",
            version="1",
            title="Campaign Funding Terms",
            effective_date="2026-01-01",
            body="Placeholder — needs counsel-reviewed campaign-funding terms before launch.",
        ),
    ]
}


def get(slug: str) -> LegalDocument | None:
    return REGISTRY.get(slug)


def current_versions() -> dict[str, str]:
    return {slug: doc.version for slug, doc in REGISTRY.items()}
