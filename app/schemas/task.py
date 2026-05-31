"""Pydantic v2 schemas for Task API request / response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None)
    priority: Priority | None = Field(default=None)
    status: Status | None = Field(default=None)

    model_config = ConfigDict(extra="ignore")


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
