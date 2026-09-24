"""Shared spreadsheet-injection-safe CSV cell escaping, used by every
`.../report`/`.../export` route (campaigns' report, the brand ledger
export, the admin ledger/audit exports)."""


def csv_safe(value) -> str:
    """A cell that starts with = + - or @ is executed as a formula by
    Excel/Sheets. Creator- or brand-controlled text (names, URLs, notes)
    reaches these exports, so such cells are prefixed with a quote."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
