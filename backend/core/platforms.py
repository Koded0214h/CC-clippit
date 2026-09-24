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


#: PRD V1.0 locked set. Threads remains in the enum/adapters for already-
#: built code paths, but product surfaces that gate "supported platforms"
#: should use this frozenset rather than every Platform member.
V1_PLATFORMS: frozenset[Platform] = frozenset(
    {
        Platform.instagram,
        Platform.tiktok,
        Platform.facebook,
        Platform.x,
        Platform.youtube,
    }
)


def is_v1_platform(platform: Platform | str) -> bool:
    value = platform if isinstance(platform, Platform) else Platform(platform)
    return value in V1_PLATFORMS
