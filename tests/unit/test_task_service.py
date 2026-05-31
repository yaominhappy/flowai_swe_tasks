"""Unit tests for TaskService using a mock TaskRepository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.task import Priority, Status, Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import TaskNotFoundError, TaskService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
TEST_UUID = uuid.uuid4()


def _mock_task(**overrides) -> Task:
    defaults = {
        "id": TEST_UUID,
        "title": "Test task",
        "description": "desc",
        "priority": Priority.MEDIUM,
        "status": Status.PENDING,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return MagicMock(spec=Task, **defaults)


# ---------------------------------------------------------------------------


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def svc(repo: AsyncMock) -> TaskService:
    return TaskService(repository=repo)


# ===========================================================================
# Create
# ===========================================================================


class TestCreate:
    async def test_create_returns_response(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.create.return_value = _mock_task(title="New")
        dto = TaskCreate(title="New")
        result = await svc.create(dto)
        assert result.title == "New"
        assert result.id == TEST_UUID
        repo.create.assert_awaited_once()


# ===========================================================================
# Get by ID
# ===========================================================================


class TestGetById:
    async def test_found(self, svc: TaskService, repo: AsyncMock) -> None:
        repo.get_by_id.return_value = _mock_task()
        result = await svc.get_by_id(TEST_UUID)
        assert result.id == TEST_UUID

    async def test_not_found_raises(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.get_by_id.return_value = None
        with pytest.raises(TaskNotFoundError):
            await svc.get_by_id(TEST_UUID)


# ===========================================================================
# List
# ===========================================================================


class TestListAll:
    async def test_list_returns_items_and_total(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.list_all.return_value = (
            [_mock_task(title="a"), _mock_task(title="b")],
            2,
        )
        items, total = await svc.list_all()
        assert len(items) == 2
        assert total == 2

    async def test_list_passes_filters(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.list_all.return_value = ([], 0)
        await svc.list_all(
            status=Status.COMPLETED,
            priority=Priority.HIGH,
            limit=30,
            offset=10,
        )
        repo.list_all.assert_awaited_once_with(
            status=Status.COMPLETED,
            priority=Priority.HIGH,
            limit=30,
            offset=10,
        )


# ===========================================================================
# Update
# ===========================================================================


class TestUpdate:
    async def test_update_non_existent_raises(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.get_by_id.return_value = None
        dto = TaskUpdate(title="nope")
        with pytest.raises(TaskNotFoundError):
            await svc.update(TEST_UUID, dto)

    async def test_update_modifies_title(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        task = _mock_task(title="Old")
        repo.get_by_id.return_value = task
        repo.update.return_value = task
        dto = TaskUpdate(title="New")
        result = await svc.update(TEST_UUID, dto)
        assert task.title == "New"
        repo.update.assert_awaited_once_with(task)

    async def test_update_clears_description(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        """Explicit ``description=null`` should clear the description field."""
        task = _mock_task(title="Has desc", description="some text")
        repo.get_by_id.return_value = task
        repo.update.return_value = task
        dto = TaskUpdate(description=None)
        await svc.update(TEST_UUID, dto)
        assert task.description is None
        repo.update.assert_awaited_once_with(task)

    async def test_update_preserves_updated_at(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        """On every update, ``updated_at`` is refreshed to now."""
        old_updated = NOW
        task = _mock_task(title="Old", updated_at=old_updated)
        repo.get_by_id.return_value = task
        repo.update.return_value = task
        dto = TaskUpdate(title="Changed")
        await svc.update(TEST_UUID, dto)
        # The service should have set updated_at to a more recent value
        assert task.updated_at != old_updated
        repo.update.assert_awaited_once_with(task)


# ===========================================================================
# Delete
# ===========================================================================


class TestDelete:
    async def test_delete_non_existent_raises(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        repo.get_by_id.return_value = None
        with pytest.raises(TaskNotFoundError):
            await svc.delete(TEST_UUID)

    async def test_delete_existing(
        self, svc: TaskService, repo: AsyncMock
    ) -> None:
        task = _mock_task()
        repo.get_by_id.return_value = task
        await svc.delete(TEST_UUID)
        repo.delete.assert_awaited_once_with(task)
