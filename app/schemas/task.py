"""Pydantic v2 schemas for Task API request / response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import Priority, Status


class TaskCreate(BaseModel):
    """Schema for ``POST /api/v1/tasks`` request body."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None)
    priority: Priority = Field(default=Priority.MEDIUM)
    status: Status = Field(default=Status.PENDING)


class TaskUpdate(BaseModel):
    """Schema for ``PUT /api/v1/tasks/{task_id}`` request body.

    All fields are optional -- only supplied values are applied.
    ``description`` may be explicitly set to ``null`` to clear it.
    ``title``, ``priority``, and ``status`` reject explicit ``null`` values.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None)
    priority: Priority | None = Field(default=None)
    status: Status | None = Field(default=None)

    model_config = ConfigDict(extra="ignore")

    @field_validator("title")
    @classmethod
    def _reject_null_title(cls, v: str | None) -> str | None:
        """Reject explicit ``null`` for title — pass through if unset or a string."""
        if v is None:
            # ``None`` is the default when the field is NOT provided.
            # If the client explicitly sends ``"title": null``, it also
            # lands here.  We distinguish by checking ``model_dump`` context.
            # Pydantic v2 does not distinguish "unset" inside validators,
            # so we reject null here and rely on ``exclude_unset`` in the
            # service layer to skip truly absent fields.
            raise ValueError("title must not be null — provide a non-empty string or omit the field")
        return v

    @field_validator("priority")
    @classmethod
    def _reject_null_priority(cls, v: Priority | None) -> Priority | None:
        if v is None:
            raise ValueError("priority must not be null — provide a valid Priority value or omit the field")
        return v

    @field_validator("status")
    @classmethod
    def _reject_null_status(cls, v: Status | None) -> Status | None:
        if v is None:
            raise ValueError("status must not be null — provide a valid Status value or omit the field")
        return v


class TaskResponse(BaseModel):
    """Schema for individual task responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated list response schema."""

    items: list[TaskResponse]
    total: int
    offset: int
    limit: int
