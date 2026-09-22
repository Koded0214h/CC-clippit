from pydantic import BaseModel

from core.platforms import Platform


class PlatformConfig(BaseModel):
    platform: Platform
    #: Clippit can start a connection for this platform today.
    connectable: bool


class CampaignLimits(BaseModel):
    min_duration_days: int
    max_duration_days: int
    max_rules: int


class UploadLimits(BaseModel):
    max_image_bytes: int
    max_video_bytes: int
    max_evidence_bytes: int


class LegalVersion(BaseModel):
    slug: str
    version: str
    effective_date: str


class ProductConfigOut(BaseModel):
    country_code: str = "NG"
    currency: str = "NGN"
    hold_days: int
    min_withdrawal_naira: int
    funding_fee_rate: float
    platforms: list[PlatformConfig]
    campaign_limits: CampaignLimits
    upload_limits: UploadLimits
    legal: list[LegalVersion]


class HandleAvailabilityOut(BaseModel):
    handle: str
    available: bool
    #: Present only when `available` is false: "taken" or "invalid".
    reason: str | None = None
