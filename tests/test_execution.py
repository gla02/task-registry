from task_registry import TaskRegistry, TaskStatus


def test_successful_execution_returns_structured_result():
    registry = TaskRegistry()

    @registry.register()
    def add(a: int, b: int = 1) -> int:
        return a + b

    result = registry.run("add", a="2", b="3")
    assert result.status is TaskStatus.SUCCESS
    assert result.success is True
    assert result.output == 5
    assert result.params == {"a": 2, "b": 3}
    assert result.duration_seconds >= 0
    assert result.timestamp.endswith("+00:00")


def test_validation_failure_is_returned_not_raised():
    registry = TaskRegistry()

    @registry.register()
    def add(a: int) -> int:
        return a + 1

    result = registry.run("add", typo=3)
    assert result.status is TaskStatus.FAILED
    assert "Unexpected parameter" in result.error
    assert "Missing required parameter" in result.error


def test_unknown_task_is_failed_result():
    registry = TaskRegistry()
    result = registry.run("missing", value=1)
    assert result.status is TaskStatus.FAILED
    assert "not registered" in result.error


def test_task_exception_is_captured_with_traceback():
    registry = TaskRegistry()

    @registry.register()
    def explode():
        raise RuntimeError("boom")

    result = registry.run("explode")
    assert result.status is TaskStatus.FAILED
    assert result.error == "boom"
    assert "RuntimeError: boom" in result.traceback


def test_run_many_stops_after_failure():
    registry = TaskRegistry()

    @registry.register()
    def first():
        return 1

    @registry.register()
    def second():
        raise RuntimeError("stop")

    @registry.register()
    def third():
        return 3

    results = registry.run_many(
        ["first", "second", "third"],
        stop_on_failure=True,
    )

    assert [r.task_name for r in results] == ["first", "second"]
