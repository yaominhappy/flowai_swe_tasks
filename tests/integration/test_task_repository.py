"""Integration tests for TaskRepository against a real SQLite database."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Priority, Status, Task
from app.repositories.task_repository import TaskRepository


@pytest.fixture
def repo(test_session: AsyncSession) -> TaskRepository:
    return TaskRepository(test_session)


def _make_task(
    title: str = "Test task",
    priority: Priority = Priority.MEDIUM,
    status: Status = Status.PENDING,
) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=uuid.uuid4(),
        title=title,
        description="A test task",
        priority=priority,
        status=status,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_persists_and_returns_task(
        self, repo: TaskRepository, test_session: AsyncSession
    ) -> None:
        task = _make_task()
        created = await repo.create(task)
        assert created.id == task.id
        assert created.title == task.title
        # Verify it is actually in the DB
        fetched = await test_session.get(Task, task.id)
        assert fetched is not None
        assert fetched.title == task.title

    async def test_create_task_defaults(
        self, repo: TaskRepository, test_session: AsyncSession
    ) -> None:
        task = _make_task(title="minimal")
        created = await repo.create(task)
        assert created.priority == Priority.MEDIUM
        assert created.status == Status.PENDING


# ---------------------------------------------------------------------------
# Read -- get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_get_by_id_found(self, repo: TaskRepository) -> None:
        task = await repo.create(_make_task())
        fetched = await repo.get_by_id(task.id)
        assert fetched is not None
        assert fetched.title == task.title

    async def test_get_by_id_not_found(self, repo: TaskRepository) -> None:
        fake_id = uuid.uuid4()
        fetched = await repo.get_by_id(fake_id)
        assert fetched is None


# ---------------------------------------------------------------------------
# Read -- list_all
# ---------------------------------------------------------------------------


class TestListAll:
    async def test_list_all_empty(self, repo: TaskRepository) -> None:
        items, total = await repo.list_all()
        assert items == []
        assert total == 0

    async def test_list_all_returns_all_tasks_ordered_desc(
        self, repo: TaskRepository
    ) -> None:
        t1 = await repo.create(
            _make_task(title="first", status=Status.PENDING)
        )
        t2 = await repo.create(
            _make_task(title="second", status=Status.COMPLETED)
        )
        items, total = await repo.list_all()
        assert total == 2
        assert len(items) == 2
        # newest first
        assert items[0].title == "second"
        assert items[1].title == "first"

    async def test_list_all_filter_by_status(
        self, repo: TaskRepository
    ) -> None:
        await repo.create(_make_task(title="p1", status=Status.PENDING))
        await repo.create(_make_task(title="c1", status=Status.COMPLETED))
        await repo.create(_make_task(title="ip1", status=Status.IN_PROGRESS))
        items, total = await repo.list_all(status=Status.COMPLETED)
        assert total == 1
        assert len(items) == 1
        assert items[0].title == "c1"

    async def test_list_all_filter_by_priority(
        self, repo: TaskRepository
    ) -> None:
        await repo.create(_make_task(title="low1", priority=Priority.LOW))
        await repo.create(_make_task(title="high1", priority=Priority.HIGH))
        items, total = await repo.list_all(priority=Priority.HIGH)
        assert total == 1
        assert items[0].title == "high1"

    async def test_list_all_combined_filters(
        self, repo: TaskRepository
    ) -> None:
        await repo.create(
            _make_task(
                title="target",
                status=Status.PENDING,
                priority=Priority.HIGH,
            )
        )
        await repo.create(
            _make_task(
                title="wrong_status",
                status=Status.COMPLETED,
                priority=Priority.HIGH,
            )
        )
        items, total = await repo.list_all(
            status=Status.PENDING, priority=Priority.HIGH
        )
        assert total == 1
        assert items[0].title == "target"

    async def test_list_all_pagination(self, repo: TaskRepository) -> None:
        for i in range(5):
            await repo.create(_make_task(title=f"task-{i}"))
        items, total = await repo.list_all(limit=2, offset=1)
        assert total == 5
        assert len(items) == 2  # page of 2

    async def test_list_all_limit_clamped(self, repo: TaskRepository) -> None:
        for i in range(10):
            await repo.create(_make_task(title=f"task-{i}"))
        items, total = await repo.list_all(limit=3)
        assert total == 10
        assert len(items) == 3


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_update_changes_fields(
        self, repo: TaskRepository
    ) -> None:
        task = await repo.create(_make_task(title="original"))
        task.title = "changed"
        updated = await repo.update(task)
        assert updated.title == "changed"
        # Verify from fresh session
        fetched = await repo.get_by_id(task.id)
        assert fetched is not None
        assert fetched.title == "changed"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_removes_task(
        self, repo: TaskRepository
    ) -> None:
        task = await repo.create(_make_task())
        await repo.delete(task)
        fetched = await repo.get_by_id(task.id)
        assert fetched is None
