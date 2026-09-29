import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class OpsHealthSample(Base):
    """One per-minute health check per service, so "30-day availability" can be
    computed across restarts instead of only since the process started."""

    __tablename__ = "ops_health_samples"
    __table_args__ = (Index("ix_ops_health_service_ts", "service", "ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
