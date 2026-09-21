import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str | None
    read: bool = False
    created_at: datetime

    @classmethod
    def from_model(cls, note) -> "NotificationOut":
        return cls(
            id=note.id,
            kind=note.kind,
            title=note.title,
            body=note.body,
            link=note.link,
            read=note.read_at is not None,
            created_at=note.created_at,
        )


class NotificationList(BaseModel):
    unread_count: int
    items: list[NotificationOut]
