"""Repository layer: all SQL queries for the URL shortener are here.

No business logic lives in this module — only data access operations.
Every query is scoped to the caller-supplied tenant_id to enforce isolation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClickEvent, ShortURL

logger = logging.getLogger(__name__)

_DEFAULT_TENANT = "default"


class UrlRepository:
    """Async repository that encapsulates all database operations for URL mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create(
        self,
        slug: str,
        original_url: str,
        tenant_id: str = _DEFAULT_TENANT,
    ) -> ShortURL:
        """Persist a new slug → URL mapping and return the created row.

        Raises:
            IntegrityError: if the (tenant_id, slug) pair already exists.
        """
        now = datetime.now(timezone.utc)
        mapping = ShortURL(
            id=uuid4(),
            tenant_id=tenant_id,
            slug=slug,
            original_url=original_url,
            click_count=0,
            created_at=now,
            updated_at=now,
        )
        self._session.add(mapping)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            logger.debug("Duplicate slug %r for tenant %r", slug, tenant_id)
            raise
        logger.info(
            "Created short URL",
            extra={"slug": slug, "tenant_id": tenant_id},
        )
        return mapping

    async def increment_clicks(
        self,
        slug: str,
        tenant_id: str = _DEFAULT_TENANT,
    ) -> ShortURL | None:
        """Atomically increment click_count and append a ClickEvent row.

        Returns the updated ShortURL, or None if the slug is not found.
        """
        mapping = await self.get_by_slug(slug, tenant_id)
        if mapping is None:
            return None

        now = datetime.now(timezone.utc)
        stmt = (
            update(ShortURL)
            .where(ShortURL.tenant_id == tenant_id, ShortURL.slug == slug)
            .values(click_count=ShortURL.click_count + 1, updated_at=now)
        )
        await self._session.execute(stmt)

        event = ClickEvent(
            short_url_id=mapping.id,
            tenant_id=tenant_id,
            clicked_at=now,
        )
        self._session.add(event)
        await self._session.flush()

        # Refresh to pick up the updated click_count value.
        await self._session.refresh(mapping)
        return mapping

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_slug(
        self,
        slug: str,
        tenant_id: str = _DEFAULT_TENANT,
    ) -> ShortURL | None:
        """Return the ShortURL row for the given (tenant_id, slug), or None."""
        stmt = select(ShortURL).where(
            ShortURL.tenant_id == tenant_id,
            ShortURL.slug == slug,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
