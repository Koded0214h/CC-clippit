"""One rule for every public handle/slug in the app — creator handles and
organisation slugs share this namespace-shaping (not the same uniqueness
table, but the same *look*), so `GET /handles/{handle}/availability` can
normalize either kind the same way before checking it against both.
"""

import re

HANDLE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{1,28}[a-z0-9])?$")
RESERVED = {
    "admin", "clippit", "support", "help", "api", "www", "brand", "creator",
    "dashboard", "settings", "auth", "login", "signup", "campaigns", "null", "undefined",
}


def normalize(raw: str) -> str:
    return raw.strip().lower()


def is_valid(handle: str) -> bool:
    return 3 <= len(handle) <= 30 and bool(HANDLE_RE.match(handle)) and handle not in RESERVED
