"""Unit tests for app/service.py.

The repository is mocked so these tests remain pure and fast — no database I/O.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import ShortURL
from app.service import (
    MAX_SLUG_RETRIES,
    SlugCollisionError,
    SlugNotFoundError,
    UrlShortenerService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_mapping(
    slug: str = "abc123",
    original_url: str = "https://example.com",
    click_count: int = 0,
    tenant_id: str = "default",
) -> MagicMock:
    m = MagicMock(spec=ShortURL)
    m.slug = slug
    m.original_url = original_url
    m.click_count = click_count
    m.tenant_id = tenant_id
    return m


def _make_service(repo: AsyncMock) -> UrlShortenerService:
    return UrlShortenerService(
        repository=repo,
        base_url="https://short.ly",
        tenant_id="default",
    )


# ---------------------------------------------------------------------------
# shorten – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shorten_returns_result_on_first_attempt() -> None:
    """shorten() returns a ShortenResult when the slug is unique on the first try."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_make_mock_mapping("xyz789"))

    service = _make_service(repo)
    result = await service.shorten("https://example.com/very/long/path")

    assert result.slug == "xyz789"
    assert result.original_url == "https://example.com"
    assert result.short_url == "https://short.ly/xyz789"
    repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_shorten_constructs_short_url_with_base() -> None:
    """shorten() builds the full short URL by prepending base_url."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_make_mock_mapping("slug01"))

    service = UrlShortenerService(repo, base_url="https://my.domain", tenant_id="t1")
    result = await service.shorten("https://long.example.com")

    assert result.short_url == "https://my.domain/slug01"


@pytest.mark.asyncio
async def test_shorten_strips_trailing_slash_from_base_url() -> None:
    """Trailing slash on base_url is stripped to avoid double slashes."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_make_mock_mapping("slug02"))

    service = UrlShortenerService(repo, base_url="https://my.domain/", tenant_id="t1")
    result = await service.shorten("https://long.example.com")

    assert result.short_url == "https://my.domain/slug02"


# ---------------------------------------------------------------------------
# shorten – collision retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shorten_retries_on_collision() -> None:
    """shorten() retries and succeeds when the first slug collides."""
    repo = AsyncMock()
    success_mapping = _make_mock_mapping("newslug")
    # First call raises, second call succeeds.
    repo.create = AsyncMock(
        side_effect=[IntegrityError("duplicate", None, Exception()), success_mapping]
    )

    service = _make_service(repo)
    result = await service.shorten("https://example.com")

    assert result.slug == "newslug"
    assert repo.create.call_count == 2


@pytest.mark.asyncio
async def test_shorten_retries_up_to_max_retries() -> None:
    """shorten() retries MAX_SLUG_RETRIES times before raising SlugCollisionError."""
    repo = AsyncMock()
    repo.create = AsyncMock(
        side_effect=IntegrityError("duplicate", None, Exception())
    )

    service = _make_service(repo)
    with pytest.raises(SlugCollisionError) as exc_info:
        await service.shorten("https://example.com")

    assert exc_info.value.attempts == MAX_SLUG_RETRIES
    assert repo.create.call_count == MAX_SLUG_RETRIES


@pytest.mark.asyncio
async def test_shorten_succeeds_on_last_retry() -> None:
    """shorten() succeeds if the final allowed attempt produces a unique slug."""
    repo = AsyncMock()
    success_mapping = _make_mock_mapping("lastslg")
    collisions = [
        IntegrityError("dup", None, Exception()) for _ in range(MAX_SLUG_RETRIES - 1)
    ]
    repo.create = AsyncMock(side_effect=[*collisions, success_mapping])

    service = _make_service(repo)
    result = await service.shorten("https://example.com")

    assert result.slug == "lastslg"
    assert repo.create.call_count == MAX_SLUG_RETRIES


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stats_returns_result_for_known_slug() -> None:
    """get_stats() returns a StatsResult for a known slug."""
    repo = AsyncMock()
    repo.get_by_slug = AsyncMock(
        return_value=_make_mock_mapping("abc123", click_count=7)
    )

    service = _make_service(repo)
    result = await service.get_stats("abc123")

    assert result.slug == "abc123"
    assert result.click_count == 7
    repo.get_by_slug.assert_called_once_with("abc123", "default")


@pytest.mark.asyncio
async def test_get_stats_raises_for_unknown_slug() -> None:
    """get_stats() raises SlugNotFoundError when the slug does not exist."""
    repo = AsyncMock()
    repo.get_by_slug = AsyncMock(return_value=None)

    service = _make_service(repo)
    with pytest.raises(SlugNotFoundError) as exc_info:
        await service.get_stats("missing")

    assert exc_info.value.slug == "missing"


# ---------------------------------------------------------------------------
# redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redirect_returns_original_url() -> None:
    """redirect() returns the original URL after incrementing clicks."""
    repo = AsyncMock()
    repo.increment_clicks = AsyncMock(
        return_value=_make_mock_mapping("abc123", original_url="https://target.com")
    )

    service = _make_service(repo)
    url = await service.redirect("abc123")

    assert url == "https://target.com"
    repo.increment_clicks.assert_called_once_with("abc123", "default")


@pytest.mark.asyncio
async def test_redirect_raises_for_unknown_slug() -> None:
    """redirect() raises SlugNotFoundError when the slug does not exist."""
    repo = AsyncMock()
    repo.increment_clicks = AsyncMock(return_value=None)

    service = _make_service(repo)
    with pytest.raises(SlugNotFoundError):
        await service.redirect("nope")


# ---------------------------------------------------------------------------
# slug generation internals
# ---------------------------------------------------------------------------


def test_generate_slug_length() -> None:
    """Generated slugs are exactly SLUG_LENGTH characters."""
    from app.service import SLUG_LENGTH, _generate_slug

    for _ in range(20):
        s = _generate_slug()
        assert len(s) == SLUG_LENGTH


def test_generate_slug_url_safe_characters() -> None:
    """Generated slugs contain only URL-safe base64 characters."""
    import re
    from app.service import _generate_slug

    pattern = re.compile(r"^[A-Za-z0-9_\-]+$")
    for _ in range(20):
        s = _generate_slug()
        assert pattern.match(s), f"Slug {s!r} contains invalid characters"
