# Tool Execution Report 4

- Command: `python3 -m pytest --collect-only -q`
- Status: `completed`
- Exit code: `0`
- Log path: `/Users/minyao/.flowai/sandboxes/1574a745-bfb5-4cbd-9ba7-647f54b7e888/d08c7212-9d83-4237-b743-9effc5568ecb/_run_shared/_run_shared/logs/tool_4.log`

## Stdout
tests/e2e/test_tasks_api.py::test_healthz_returns_ok
tests/e2e/test_tasks_api.py::TestCreateTaskSuccess::test_minimal_payload
tests/e2e/test_tasks_api.py::TestCreateTaskSuccess::test_minimal_payload_refined
tests/e2e/test_tasks_api.py::TestCreateTaskSuccess::test_full_payload
tests/e2e/test_tasks_api.py::TestCreateTaskSuccess::test_response_includes_request_id_header
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_missing_title
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_empty_title
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_invalid_status
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_invalid_priority
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_unknown_fields_ignored
tests/e2e/test_tasks_api.py::TestCreateTaskInvalidInput::test_422_standard_error_shape
tests/e2e/test_tasks_api.py::TestGetTask::test_get_existing
tests/e2e/test_tasks_api.py::TestGetTask::test_get_nonexistent
tests/e2e/test_tasks_api.py::TestGetTask::test_get_invalid_uuid
tests/e2e/test_tasks_api.py::TestUpdateTask::test_update_title
tests/e2e/test_tasks_api.py::TestUpdateTask::test_update_status
tests/e2e/test_tasks_api.py::TestUpdateTask::test_update_nonexistent
tests/e2e/test_tasks_api.py::TestUpdateTask::test_update_invalid_status
tests/e2e/test_tasks_api.py::TestDeleteTask::test_delete_existing
tests/e2e/test_tasks_api.py::TestDeleteTask::test_delete_nonexistent
tests/e2e/test_tasks_api.py::TestListTasks::test_list_empty
tests/e2e/test_tasks_api.py::TestListTasks::test_list_returns_all_ordered_by_created_desc
tests/e2e/test_tasks_api.py::TestListTasks::test_filter_by_status
tests/e2e/test_tasks_api.py::TestListTasks::test_filter_by_priority
tests/e2e/test_tasks_api.py::TestListTasks::test_combined_filters
tests/e2e/test_tasks_api.py::TestListTasks::test_pagination_limit
tests/e2e/test_tasks_api.py::TestListTasks::test_pagination_offset
tests/e2e/test_tasks_api.py::TestListTasks::test_invalid_status_query
tests/e2e...[truncated]

## Stderr
/opt/homebrew/lib/python3.12/site-packages/pytest_asyncio/plugin.py:217: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
