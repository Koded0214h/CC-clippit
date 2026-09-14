"""The canonical list of platforms Clippit can ingest from.

This is deliberately in `core/` rather than inside any one module: auth
connects accounts on these platforms, the intelligence pipeline reads
content from them, and campaigns target them. One list, imported by all
three, so a new platform is added in exactly one place.

`modules/auth/models.py` currently declares its own `Platform` DB enum
with an overlapping-but-shorter set of values. Reconciling the two needs
a migration on Koded's table — tracked as decision D5 in
`architecture/intelligence-contracts.md`. Until then the values here must
stay spelled exactly as they are there.
"""

import enum


class Platform(str, enum.Enum):
    tiktok = "tiktok"
    instagram = "instagram"
    facebook = "facebook"
    threads = "threads"
    x = "x"
    youtube = "youtube"
