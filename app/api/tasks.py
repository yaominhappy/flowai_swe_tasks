"""Task CRUD API routes.

All endpoints are mounted under ``/api/v1/tasks``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.task import Priority, Status
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.task_service import TaskNotFoundError, TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def get_task_service(
    session: AsyncSession = Depends(get_session),
) -> TaskService:
    """Provide a ``TaskService`` wired to the current request's DB session."""
    repo = TaskRepository(session)
    return TaskService(repo)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
async def create_task(
    body: TaskCreate,
    svc: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Create a task and return it with generated id and timestamps."""
    return await svc.create(body)


@router.get(
    "",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks with optional filters and pagination",
)
async def list_tasks(
    status_filter: Status | None = Query(
        default=None,
        alias="status",
        description="Filter by task status",
    ),
    priority_filter: Priority | None = Query(
        default=None,
        alias="priority",
        description="Filter by task priority",
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Records to skip"),
    svc: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """List tasks, newest first, with optional status/priority filters."""
    items, total = await svc.list_all(
        status=status_filter,
        priority=priority_filter,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single task by ID",
)
async def get_task(
    task_id: uuid.UUID,
    svc: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Return the task with the given UUID, or 404."""
    try:
        return await svc.get_by_id(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a task (partial update)",
)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    svc: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Apply a partial update.  Only supplied (non-None) fields are changed."""
    try:
        return await svc.update(task_id, body)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: uuid.UUID,
    svc: TaskService = Depends(get_task_service),
) -> None:
    """Delete the task with the given UUID, or 404."""
    try:
        await svc.delete(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc
