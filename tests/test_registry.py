import pytest

from task_registry import (
    TaskAlreadyRegisteredError,
    TaskNotFoundError,
    TaskRegistry,
    TaskSpec,
    TaskValidationError,
)


def test_decorator_registration_infers_name_description_and_params():
    registry = TaskRegistry()

    @registry.register(category="files", tags=["filesystem"])
    def count_lines(path: str, ignore_empty: bool = False) -> int:
        """Count lines in a text file."""
        return 1

    spec = registry["count_lines"]
    assert spec.description == "Count lines in a text file."
    assert spec.category == "files"
    assert spec.tags == ["filesystem"]
    assert [param.name for param in spec.params] == ["path", "ignore_empty"]
    assert spec.params[0].required is True
    assert spec.params[1].default is False


def test_direct_registration_and_unregister():
    registry = TaskRegistry()

    def ping() -> str:
        return "pong"

    registry.register_function(ping)
    assert "ping" in registry
    registry.unregister("ping")
    assert "ping" not in registry

    with pytest.raises(TaskNotFoundError):
        registry.unregister("ping")


def test_duplicate_registration_requires_replace():
    registry = TaskRegistry()

    def first():
        return 1

    def second():
        return 2

    registry.register_function(first, name="same")
    with pytest.raises(TaskAlreadyRegisteredError):
        registry.register_function(second, name="same")

    registry.register_function(second, name="same", replace=True)
    assert registry.run("same").output == 2


def test_register_spec_obeys_duplicate_rule():
    registry = TaskRegistry()

    def fn():
        return None

    spec = TaskSpec(name="job", fn=fn)
    registry.register_spec(spec)
    with pytest.raises(TaskAlreadyRegisteredError):
        registry.register_spec(spec)


def test_hidden_filtering_and_search():
    registry = TaskRegistry()

    @registry.register(category="files", tags=["filesystem"])
    def visible():
        """Visible file task."""

    @registry.register(category="admin", tags=["maintenance"], hidden=True)
    def secret():
        """Hidden maintenance task."""

    assert registry.list_names() == ["visible"]
    assert registry.list_names(include_hidden=True) == ["secret", "visible"]
    assert [s.name for s in registry.filter(category="files")] == ["visible"]
    assert [s.name for s in registry.filter(tags=["filesystem"])] == ["visible"]
    assert [s.name for s in registry.filter(search="file")] == ["visible"]
    assert registry.filter(search="maintenance") == []
    assert [s.name for s in registry.filter(search="maintenance", include_hidden=True)] == ["secret"]


def test_to_dict_serializes_public_task_metadata():
    registry = TaskRegistry()

    @registry.register(metadata={"requires_admin": True})
    def cleanup(path: str | None = None):
        """Clean a path."""

    @registry.register(hidden=True)
    def internal_task():
        """Internal task."""

    data = registry.to_dict()
    task = data["tasks"]["cleanup"]
    assert "fn" not in task
    assert task["metadata"] == {"requires_admin": True}
    assert task["params"][0]["default"] is None
    assert "internal_task" not in data["tasks"]
    assert "internal_task" in registry.to_dict(include_hidden=True)["tasks"]


def test_async_callable_is_rejected():
    registry = TaskRegistry()

    async def async_task():
        return "done"

    with pytest.raises(TaskValidationError, match="Async callables are not supported"):
        registry.register_function(async_task)
