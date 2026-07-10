"""Application service layer for the URL shortener.

Business rules:
- Slugs are 6-character URL-safe strings derived from secrets.token_urlsafe.
- On a slug collision the service retries up to MAX_SLUG_RETRIES times before
  raising SlugCollisionError.
- All persistence is delegated to UrlRepository; this layer contains no SQL.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.models import ShortURL
from app.repository import UrlRepository

logger = logging.getLogger(__name__)

MAX_SLUG_RETRIES: int = 5
SLUG_LENGTH: int = 6
_DEFAULT_TENANT = "default"


# ---------------------------------------------------------------------------
# Domain DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShortenResult:
    """Return value of UrlShortenerService.shorten()."""

    slug: str
    original_url: str
    short_url: str


@dataclass(frozen=True)
class StatsResult:
    """Return value of UrlShortenerService.get_stats()."""

    slug: str
    original_url: str
    click_count: int


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SlugCollisionError(RuntimeError):
    """Raised when all retry attempts for slug generation are exhausted."""

    def __init__(self, attempts: int) -> None:
        super().__init__(
            f"Failed to generate a unique slug after {attempts} attempt(s)."
        )
        self.attempts = attempts


class SlugNotFoundError(LookupError):
    """Raised when a slug lookup returns no result."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Slug {slug!r} not found.")
        self.slug = slug


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _generate_slug() -> str:
    """Return a 6-character URL-safe random slug."""
    return secrets.token_urlsafe(9)[:SLUG_LENGTH]


class UrlShortenerService:
    """Coordinates slug generation and persistence for the URL shortener."""

    def __init__(
        self,
        repository: UrlRepository,
        base_url: str = "http://localhost:8000",
        tenant_id: str = _DEFAULT_TENANT,
    ) -> None:
        self._repo = repository
        self._base_url = base_url.rstrip("/")
        self._tenant_id = tenant_id

    async def shorten(self, original_url: str) -> ShortenResult:
        """Generate a unique short slug for original_url.

        Retries up to MAX_SLUG_RETRIES times on collision.

        Raises:
            SlugCollisionError: if a unique slug cannot be produced.
        """
        for attempt in range(1, MAX_SLUG_RETRIES + 1):
            slug = _generate_slug()
            try:
                mapping: ShortURL = await self._repo.create(
                    slug=slug,
                    original_url=original_url,
                    tenant_id=self._tenant_id,
                )
                short_url = f"{self._base_url}/{mapping.slug}"
                logger.info(
                    "Shortened URL",
                    extra={
                        "slug": slug,
                        "attempt": attempt,
                        "tenant_id": self._tenant_id,
                    },
                )
                return ShortenResult(
                    slug=mapping.slug,
                    original_url=mapping.original_url,
                    short_url=short_url,
                )
            except IntegrityError:
                logger.warning(
                    "Slug collision on attempt %d/%d: %r",
                    attempt,
                    MAX_SLUG_RETRIES,
                    slug,
                )

        raise SlugCollisionError(MAX_SLUG_RETRIES)

    async def get_stats(self, slug: str) -> StatsResult:
        """Return click statistics for slug.

        Raises:
            SlugNotFoundError: if the slug does not exist.
        """
        mapping = await self._repo.get_by_slug(slug, self._tenant_id)
        if mapping is None:
            raise SlugNotFoundError(slug)
        return StatsResult(
            slug=mapping.slug,
            original_url=mapping.original_url,
            click_count=mapping.click_count,
        )

    async def redirect(self, slug: str) -> str:
        """Increment click count and return the original URL for a redirect.

        Raises:
            SlugNotFoundError: if the slug does not exist.
        """
        mapping = await self._repo.increment_clicks(slug, self._tenant_id)
        if mapping is None:
            raise SlugNotFoundError(slug)
        return mapping.original_url
