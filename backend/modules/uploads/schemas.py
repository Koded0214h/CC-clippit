import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    url: str
    content_type: str
    size_bytes: int
    created_at: datetime


class MultipartCreate(BaseModel):
    kind: str = Field(pattern="^(image|video|evidence)$")
    filename: str = Field(min_length=1, max_length=255)
    declared_size_bytes: int = Field(gt=0)
    content_type: str = Field(min_length=1, max_length=64)


class MultipartCreated(BaseModel):
    upload_id: uuid.UUID
    #: This local backend issues one part; a real R2 backend would return
    #: several presigned PUT URLs sized to `part_size_bytes` for parallel
    #: upload — see `core.storage.Storage`'s multipart docstring.
    part_urls: list[str]
    part_size_bytes: int
    expires_at: datetime


class MultipartComplete(BaseModel):
    part_numbers: list[int] = Field(default_factory=lambda: [1], min_length=1)


class UploadStatusOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    url: str | None
    content_type: str | None
    size_bytes: int | None
    created_at: datetime
