import pytest

from task_registry import TaskParam, TaskRegistry, TaskValidationError
from task_registry.params import inspect_params, prepare_args


def test_required_default_and_none_default_are_distinct():
    def example(required: str, optional: str | None = None):
        pass

    params = inspect_params(example)
    assert params[0].required is True
    assert params[1].required is False
    assert params[1].default is None


def test_keyword_only_parameters_are_supported():
    def example(value: int, *, verbose: bool = False):
        pass

    params = inspect_params(example)
    assert [p.name for p in params] == ["value", "verbose"]


def test_positional_only_and_varargs_are_rejected():
    def positional(value, /):
        pass

    with pytest.raises(TaskValidationError):
        inspect_params(positional)

    def varargs(*values):
        pass

    with pytest.raises(TaskValidationError):
        inspect_params(varargs)


def test_prepare_args_coerces_primitives_and_bool_strings():
    registry = TaskRegistry()

    def example(count: int, ratio: float, enabled: bool, label: str):
        pass

    registry.register_function(example)
    spec = registry["example"]
    result = prepare_args(
        spec,
        {"count": "3", "ratio": "1.5", "enabled": "false", "label": 8},
    )
    assert result == {"count": 3, "ratio": 1.5, "enabled": False, "label": "8"}


def test_prepare_args_rejects_missing_and_unexpected_parameters():
    registry = TaskRegistry()

    def example(value: int):
        pass

    registry.register_function(example)
    spec = registry["example"]

    with pytest.raises(TaskValidationError) as exc_info:
        prepare_args(spec, {"typo": 3})

    message = str(exc_info.value)
    assert "Unexpected parameter" in message
    assert "Missing required parameter" in message


def test_choices_are_checked_after_coercion():
    registry = TaskRegistry()

    def example(level: int):
        pass

    registry.register_function(
        example,
        params=[TaskParam("level", int, choices=(1, 2, 3))],
    )
    spec = registry["example"]

    assert prepare_args(spec, {"level": "2"}) == {"level": 2}

    with pytest.raises(TaskValidationError):
        prepare_args(spec, {"level": "9"})


def test_optional_primitive_is_coerced_and_none_is_preserved():
    registry = TaskRegistry()

    def example(value: int | None = None):
        return value

    registry.register_function(example)
    spec = registry["example"]

    assert prepare_args(spec, {"value": "3"}) == {"value": 3}
    assert prepare_args(spec, {"value": None}) == {"value": None}

