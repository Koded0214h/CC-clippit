"""Typed failures for the compliance pipeline.

Callers map these to a non-rejecting product state (PRD: retrieval/model
failure must not auto-reject a submission).
"""


class ComplianceError(RuntimeError):
    """Base class for compliance failures."""

    code: str = "compliance_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class MediaRetrievalError(ComplianceError):
    code = "media_retrieval_failed"


class ModelError(ComplianceError):
    code = "model_failed"
