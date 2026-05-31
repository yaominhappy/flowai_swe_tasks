"""Unit tests for Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.task import Priority, Status
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
TEST_UUID = uuid.uuid4()


def _response_kwargs(**overrides):
    defaults = {
        "id": TEST_UUID,
        "title": "test",
        "description": None,
        "priority": Priority.MEDIUM,
        "status": Status.PENDING,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# TaskCreate
# ===========================================================================


class TestTaskCreate:
    def test_valid_minimal(self) -> None:
        dto = TaskCreate(title="My task")
        assert dto.title == "My task"
        assert dto.description is None
        assert dto.priority == Priority.MEDIUM
        assert dto.status == Status.PENDING

    def test_valid_all_fields(self) -> None:
        dto = TaskCreate(
            title="Full task",
            description="A description",
            priority=Priority.HIGH,
            status=Status.IN_PROGRESS,
        )
        assert dto.title == "Full task"
        assert dto.description == "A description"
        assert dto.priority == Priority.HIGH
        assert dto.status == Status.IN_PROGRESS

    def test_title_missing_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate()

    def test_title_empty_string_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(title="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_title_too_long_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(title="x" * 201)

    def test_invalid_priority_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(title="x", priority="urgent")  # type: ignore[arg-type]

    def test_invalid_status_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(title="x", status="unknown")  # type: ignore[arg-type]

    def test_ignores_extra_fields(self) -> None:
        dto = TaskCreate.model_validate(
            {"title": "x", "extra_field": "should be ignored"}
        )
        assert dto.title == "x"
        assert not hasattr(dto, "extra_field")


# ===========================================================================
# TaskUpdate
# ===========================================================================


class TestTaskUpdate:
    def test_empty_update_allowed(self) -> None:
        dto = TaskUpdate()
        assert dto.title is None
        assert dto.description is None
        assert dto.priority is None
        assert dto.status is None

    def test_partial_update(self) -> None:
        dto = TaskUpdate(title="New title")
        assert dto.title == "New title"
        assert dto.description is None
        assert dto.priority is None
        assert dto.status is None

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskUpdate(priority="critical")  # type: ignore[arg-type]

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskUpdate(status="archived")  # type: ignore[arg-type]

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskUpdate(title="")


# ===========================================================================
# TaskResponse
# ===========================================================================


class TestTaskResponse:
    def test_from_attributes(self) -> None:
        resp = TaskResponse.model_validate(
            _response_kwargs(title="Hello")
        )
        assert resp.id == TEST_UUID
        assert resp.title == "Hello"
        assert resp.priority == Priority.MEDIUM
        assert resp.status == Status.PENDING

    def test_serializes_uuid_as_string(self) -> None:
        resp = TaskResponse.model_validate(_response_kwargs())
        serialized = resp.model_dump(mode="json")
        assert isinstance(serialized["id"], str)
        assert serialized["id"] == str(TEST_UUID)

    def test_serializes_datetime_as_iso_string(self) -> None:
        resp = TaskResponse.model_validate(_response_kwargs())
        serialized = resp.model_dump(mode="json")
        assert isinstance(serialized["created_at"], str)
        assert isinstance(serialized["updated_at"], str)


# ===========================================================================
# TaskListResponse
# ===========================================================================


class TestTaskListResponse:
    def test_empty_list(self) -> None:
        lst = TaskListResponse(items=[], total=0, offset=0, limit=50)
        assert lst.items == []
        assert lst.total == 0
        assert lst.offset == 0
        assert lst.limit == 50

    def test_with_items(self) -> None:
        items = [
            TaskResponse.model_validate(_response_kwargs(title=f"t{i}"))
            for i in range(3)
        ]
        lst = TaskListResponse(items=items, total=3, offset=0, limit=50)
        assert len(lst.items) == 3
        assert lst.total == 3
