"""Pydantic v2 request/response schemas for the URL shortener API.

These models form the HTTP contract between clients and the service.
They are deliberately kept separate from domain DTOs and ORM models.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ShortenRequest(BaseModel):
    """Body accepted by POST /shorten."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The long URL to shorten.",
        examples=["https://example.com/very/long/path?query=value"],
    )


class ShortenResponse(BaseModel):
    """Response body returned by POST /shorten."""

    slug: str = Field(..., description="The generated short-URL slug.")
    short_url: str = Field(..., description="The fully-qualified short URL.")
    original_url: str = Field(..., description="The original long URL.")


class StatsResponse(BaseModel):
    """Response body returned by GET /stats/{slug}."""

    slug: str = Field(..., description="The short-URL slug.")
    original_url: str = Field(..., description="The original long URL.")
    click_count: int = Field(..., description="Total number of redirect hits.")
