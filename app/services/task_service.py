"""TaskService -- application-layer business logic coordination.

Receives resolved data from the API layer, applies business rules, and
coordinates repository calls.  Never touches HTTP or raw SQL.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.models.task import Priority, Status, Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    """Raised when a requested task does not exist."""


class TaskService:
    """Application service for task CRUD operations."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, dto: TaskCreate) -> TaskResponse:
        """Create a new task from the validated DTO."""
        now = datetime.now(timezone.utc)
        task = Task(
            id=uuid.uuid4(),
            title=dto.title,
            description=dto.description,
            priority=dto.priority,
            status=dto.status,
            created_at=now,
            updated_at=now,
        )
        created = await self._repo.create(task)
        return TaskResponse.model_validate(created)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, task_id: uuid.UUID) -> TaskResponse:
        """Return the task with *task_id*, or raise ``TaskNotFoundError``."""
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return TaskResponse.model_validate(task)

    async def list_all(
        self,
        *,
        status: Status | None = None,
        priority: Priority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskResponse], int]:
        """Return ``(items, total_count)``, optionally filtered."""
        items, total = await self._repo.list_all(
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
        )
        return [TaskResponse.model_validate(t) for t in items], total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self, task_id: uuid.UUID, dto: TaskUpdate
    ) -> TaskResponse:
        """Apply a partial update to *task_id*.  Only non-None fields are set."""
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")

        # ``exclude_unset=True`` ensures only fields the client supplied
        # are in the dict.  ``description=None`` is valid (clears the field);
        # ``title/priority/status=None`` is rejected by the schema validator.
        update_data = dto.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)

        task.updated_at = datetime.now(timezone.utc)
        updated = await self._repo.update(task)
        return TaskResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, task_id: uuid.UUID) -> None:
        """Delete the task with *task_id*, or raise ``TaskNotFoundError``."""
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        await self._repo.delete(task)
