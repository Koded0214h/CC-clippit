"""Failures this module raises, as opposed to the ones adapters raise.

Adapter errors (`RateLimited`, `ContentUnavailable`, …) describe what a
*platform* did. These describe what went wrong on our side of the line:
a URL we can't route, a creator who never connected an account, an
internal service we couldn't reach. Callers catch both families.
"""


class IntelligenceError(RuntimeError):
    """Base class for every ingestion/intelligence failure."""


class UrlNotRecognized(IntelligenceError):
    """No adapter could turn the submitted URL into a content ID. Usually a
    creator pasting a profile link, a wrong platform, or a typo — so this
    should surface to the product, not be retried."""


class MissingCreatorToken(IntelligenceError):
    """The creator has no usable token for this platform: never connected,
    disconnected, or expired past refresh. Not retryable — the creator has
    to reconnect the account before this submission can be read."""


class TokenLookupFailed(IntelligenceError):
    """We couldn't ask the auth module at all (network, wrong internal
    secret, unexpected status). This is our infrastructure misbehaving
    rather than a creator problem, and is worth retrying."""


class IneligibleContent(IntelligenceError):
    """The URL resolved, but the post isn't a campaign-submittable type
    (X reposts and replies). Not retryable — the creator has to submit
    an original or a quote."""
