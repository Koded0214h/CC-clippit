import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    url: str
    content_type: str
    size_bytes: int
    created_at: datetime
