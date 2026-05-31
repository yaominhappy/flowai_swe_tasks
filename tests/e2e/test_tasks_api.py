"""End-to-end tests for the Task API -- full HTTP stack with in-memory DB.

Covers every acceptance criterion from the product requirements.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


def _random_title() -> str:
    return f"task-{uuid.uuid4().hex[:8]}"


# ===========================================================================
# Health check
# ===========================================================================


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ===========================================================================
# AC-1.1: Create task -- success
# ===========================================================================


class TestCreateTaskSuccess:
    """AC-1.1: Create task with valid payload returns 201."""

    async def test_minimal_payload(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": _random_title()},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "id" in body
        uuid.UUID(body["id"])  # valid UUID
        assert body["status"] == "pending"
        assert body["priority"] == "medium"
        assert "created_at" in body
        assert "updated_at" in body

    async def test_minimal_payload_refined(
        self, client: AsyncClient
    ) -> None:
        title = _random_title()
        resp = await client.post("/api/v1/tasks", json={"title": title})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == title
        assert body["status"] == "pending"
        assert body["priority"] == "medium"
        assert body["description"] is None

    async def test_full_payload(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "title": _random_title(),
                "description": "a description",
                "priority": "high",
                "status": "in_progress",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["description"] == "a description"
        assert body["priority"] == "high"
        assert body["status"] == "in_progress"

    async def test_response_includes_request_id_header(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": _random_title()},
        )
        assert "x-request-id" in resp.headers


# ===========================================================================
# AC-1.2: Create missing title → 422
# ===========================================================================


class TestCreateTaskInvalidInput:
    """AC-1.2, AC-1.3, AC-1.4: Invalid create input returns 422."""

    async def test_missing_title(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/tasks", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body

    async def test_empty_title(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": ""},
        )
        assert resp.status_code == 422

    async def test_invalid_status(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "x", "status": "bogus"},
        )
        assert resp.status_code == 422

    async def test_invalid_priority(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "x", "priority": "urgent"},
        )
        assert resp.status_code == 422

    async def test_unknown_fields_ignored(
        self, client: AsyncClient
    ) -> None:
        """AC-3.1: extra fields are silently ignored."""
        title = _random_title()
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": title, "extra": "should-be-ignored"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "extra" not in body
        assert body["title"] == title

    async def test_422_standard_error_shape(
        self, client: AsyncClient
    ) -> None:
        """AC-3.2: 422 uses standard Pydantic error shape."""
        resp = await client.post("/api/v1/tasks", json={})
        assert resp.status_code == 422
        body = resp.json()
        detail = body["detail"]
        assert isinstance(detail, list)
        assert len(detail) > 0
        err = detail[0]
        assert "loc" in err
        assert "msg" in err
        assert "type" in err


# ===========================================================================
# AC-1.5, AC-1.6: Get single task
# ===========================================================================


class TestGetTask:
    """AC-1.5: Get existing task returns 200.
    AC-1.6: Get nonexistent task returns 404.
    """

    async def test_get_existing(self, client: AsyncClient) -> None:
        # Create first
        title = _random_title()
        create_resp = await client.post(
            "/api/v1/tasks", json={"title": title}
        )
        task_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == title

    async def test_get_nonexistent(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/tasks/{fake_id}")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Task not found"}

    async def test_get_invalid_uuid(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/tasks/not-a-uuid")
        assert resp.status_code == 422


# ===========================================================================
# AC-1.7, AC-1.8, AC-1.9: Update task
# ===========================================================================


class TestUpdateTask:
    """AC-1.7: Update existing task changes fields.
    AC-1.8: Update nonexistent returns 404.
    AC-1.9: Update with invalid status returns 422.
    """

    async def test_update_title(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/tasks",
            json={"title": _random_title(), "status": "pending"},
        )
        task_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/tasks/{task_id}",
            json={"title": "updated-title"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "updated-title"
        # updated_at should be different from created_at
        assert body["updated_at"] != body["created_at"]

    async def test_update_status(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/tasks",
            json={"title": _random_title(), "status": "pending"},
        )
        task_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/tasks/{task_id}",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    async def test_update_nonexistent(self, client: AsyncClient) -> None:
        resp = await client.put(
            f"/api/v1/tasks/{uuid.uuid4()}",
            json={"title": "x"},
        )
        assert resp.status_code == 404

    async def test_update_invalid_status(
        self, client: AsyncClient
    ) -> None:
        create_resp = await client.post(
            "/api/v1/tasks", json={"title": _random_title()}
        )
        task_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/tasks/{task_id}",
            json={"status": "bogus"},
        )
        assert resp.status_code == 422


# ===========================================================================
# AC-1.10, AC-1.11: Delete task
# ===========================================================================


class TestDeleteTask:
    """AC-1.10: Delete existing returns 204 then 404 on re-GET.
    AC-1.11: Delete nonexistent returns 404.
    """

    async def test_delete_existing(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/tasks", json={"title": _random_title()}
        )
        task_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 204
        assert resp.content == b""

        # Verify gone
        get_resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient) -> None:
        resp = await client.delete(f"/api/v1/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Task not found"}


# ===========================================================================
# AC-2.1 to AC-2.8: List tasks with filtering and pagination
# ===========================================================================


class TestListTasks:
    """FR‑2: Task list with filtering and pagination."""

    async def test_list_empty(self, client: AsyncClient) -> None:
        """AC‑2.1: empty list returns 200 with correct shape."""
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["offset"] == 0
        assert body["limit"] == 50

    async def test_list_returns_all_ordered_by_created_desc(
        self, client: AsyncClient
    ) -> None:
        """AC‑2.1: list without filters returns all, newest first."""
        t1 = await client.post(
            "/api/v1/tasks", json={"title": "first"}
        )
        t2 = await client.post(
            "/api/v1/tasks", json={"title": "second"}
        )
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        titles = [i["title"] for i in body["items"]]
        # newest first
        assert titles == ["second", "first"]

    async def test_filter_by_status(self, client: AsyncClient) -> None:
        """AC‑2.2: status filter returns only matching tasks."""
        await client.post(
            "/api/v1/tasks",
            json={"title": "p", "status": "pending"},
        )
        await client.post(
            "/api/v1/tasks",
            json={"title": "c", "status": "completed"},
        )
        resp = await client.get("/api/v1/tasks?status=completed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "c"

    async def test_filter_by_priority(self, client: AsyncClient) -> None:
        """AC‑2.3: priority filter returns only matching tasks."""
        await client.post(
            "/api/v1/tasks",
            json={"title": "low", "priority": "low"},
        )
        await client.post(
            "/api/v1/tasks",
            json={"title": "high", "priority": "high"},
        )
        resp = await client.get("/api/v1/tasks?priority=high")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "high"

    async def test_combined_filters(self, client: AsyncClient) -> None:
        """AC‑2.4: combined status+priority filter works."""
        await client.post(
            "/api/v1/tasks",
            json={
                "title": "target",
                "status": "pending",
                "priority": "high",
            },
        )
        await client.post(
            "/api/v1/tasks",
            json={
                "title": "wrong",
                "status": "completed",
                "priority": "high",
            },
        )
        resp = await client.get(
            "/api/v1/tasks?status=pending&priority=high"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "target"

    async def test_pagination_limit(self, client: AsyncClient) -> None:
        """AC‑2.5: limit restricts results."""
        for i in range(5):
            await client.post(
                "/api/v1/tasks", json={"title": f"task-{i}"}
            )
        resp = await client.get("/api/v1/tasks?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2

    async def test_pagination_offset(self, client: AsyncClient) -> None:
        """AC‑2.5: offset skips correctly."""
        for i in range(5):
            await client.post(
                "/api/v1/tasks", json={"title": f"task-{i}"}
            )
        resp = await client.get("/api/v1/tasks?limit=2&offset=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["offset"] == 2

    async def test_invalid_status_query(self, client: AsyncClient) -> None:
        """AC‑2.6: invalid status in query returns 422."""
        resp = await client.get("/api/v1/tasks?status=bogus")
        assert resp.status_code == 422

    async def test_invalid_priority_query(
        self, client: AsyncClient
    ) -> None:
        """AC‑2.7: invalid priority in query returns 422."""
        resp = await client.get("/api/v1/tasks?priority=urgent")
        assert resp.status_code == 422

    async def test_invalid_limit_query(self, client: AsyncClient) -> None:
        """AC‑2.8: invalid limit (<1 or >100) returns 422."""
        resp = await client.get("/api/v1/tasks?limit=0")
        assert resp.status_code == 422

        resp2 = await client.get("/api/v1/tasks?limit=101")
        assert resp2.status_code == 422

    async def test_default_limit_is_50(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 50

    async def test_negative_offset_rejected(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/v1/tasks?offset=-1")
        assert resp.status_code == 422
