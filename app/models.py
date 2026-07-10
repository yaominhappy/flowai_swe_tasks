"""SQLAlchemy ORM models for the URL shortener service.

Tables:
  - short_urls  : stores slug → original_url mappings per tenant.
  - click_events: append-only log of each redirect hit (integer PK for
                  high-write performance).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class ShortURL(Base):
    """Persisted mapping between a short slug and its original URL.

    Uniqueness is enforced per-tenant: two different tenants may share
    the same slug value without conflict.
    """

    __tablename__ = "short_urls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    click_events: Mapped[list[ClickEvent]] = relationship(
        back_populates="short_url", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_tenant_slug"),
        Index("ix_short_urls_tenant_id", "tenant_id"),
        Index("ix_short_urls_tenant_slug", "tenant_id", "slug"),
        Index("ix_short_urls_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ShortURL id={self.id} tenant={self.tenant_id!r} slug={self.slug!r}>"
        )


class ClickEvent(Base):
    """Append-only record of every redirect hit against a short URL.

    Uses an integer autoincrement PK for high-write append performance.
    """

    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_url_id: Mapped[UUID] = mapped_column(
        ForeignKey("short_urls.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    short_url: Mapped[ShortURL] = relationship(
        back_populates="click_events", lazy="select"
    )

    __table_args__ = (
        Index("ix_click_events_short_url_id", "short_url_id"),
        Index("ix_click_events_tenant_id", "tenant_id"),
        Index("ix_click_events_tenant_short", "tenant_id", "short_url_id"),
        Index("ix_click_events_clicked_at", "clicked_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ClickEvent id={self.id} short_url_id={self.short_url_id} "
            f"tenant={self.tenant_id!r}>"
        )
