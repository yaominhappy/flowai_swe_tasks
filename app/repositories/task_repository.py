"""TaskRepository -- async data access for the ``tasks`` table.

Every method accepts a SQLAlchemy ``AsyncSession`` and issues parameterised
queries.  The repository never handles HTTP concerns or business rules.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Select

from app.models.task import Priority, Status, Task


class TaskRepository:
    """Async repository for Task CRUD and filtered listing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, task: Task) -> Task:
        """Persist a new Task and return it with generated values."""
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Return the Task with *task_id*, or ``None``."""
        return await self._session.get(Task, task_id)

    async def list_all(
        self,
        *,
        status: Status | None = None,
        priority: Priority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        """Return ``(items, total_count)`` matching the optional filters.

        Results are ordered by ``created_at DESC`` (newest first).
        """
        base: Select = select(Task)

        if status is not None:
            base = base.where(Task.status == status)
        if priority is not None:
            base = base.where(Task.priority == priority)

        # Total count (same WHERE clause)
        count_q = select(func.count()).select_from(base.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        # Paginated items
        items_q = base.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(items_q)
        items: list[Task] = list(result.scalars().all())

        return items, total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(self, task: Task) -> Task:
        """Persist changes to an existing task."""
        await self._session.flush()
        await self._session.refresh(task)
        return task

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, task: Task) -> None:
        """Delete *task* from the database."""
        await self._session.delete(task)
        await self._session.flush()
