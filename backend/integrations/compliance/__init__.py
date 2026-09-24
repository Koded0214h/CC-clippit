"""Compliance integrations — retrieve posted media and ask Qwen to judge it.

PRD V1.0 locks yt-dlp for retrieval and Qwen3.8-Omni-Flash for native
video+audio brief checking. This package only fetches and calls the model;
`modules.submissions.qwen_verifier` turns the result into a Verifier Outcome.
"""

from .errors import ComplianceError, MediaRetrievalError, ModelError
from .qwen import QwenClient, QwenJudgement
from .ytdlp import RetrievedMedia, retrieve_video

__all__ = [
    "ComplianceError",
    "MediaRetrievalError",
    "ModelError",
    "QwenClient",
    "QwenJudgement",
    "RetrievedMedia",
    "retrieve_video",
]
