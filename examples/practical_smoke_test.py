"""Practical end-to-end smoke test for task-registry.

Run from the repository root with:

    PYTHONPATH=src python examples/practical_smoke_test.py

The script intentionally exercises the public API the way a small CLI, API, UI,
or agent-facing tool layer might use it.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from task_registry import (
    TaskAlreadyRegisteredError,
    TaskParam,
    TaskRegistry,
    TaskStatus,
)


registry = TaskRegistry()


@registry.register(category="files", tags=["filesystem", "read"])
def count_lines(path: str, ignore_empty: bool = False) -> int:
    """Count lines in a UTF-8 text file."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if ignore_empty:
        lines = [line for line in lines if line.strip()]
    return len(lines)


@registry.register(
    category="text",
    tags=["transform"],
    params=[
        TaskParam("text", str),
        TaskParam("mode", str, default="upper", choices=("upper", "lower")),
    ],
)
def transform_text(text: str, mode: str = "upper") -> str:
    """Transform text using a constrained mode."""
    return text.upper() if mode == "upper" else text.lower()


@registry.register(category="math", tags=["demo"])
def multiply(value: float, factor: int = 2) -> float:
    """Multiply a numeric value by an integer factor."""
    return value * factor


@registry.register(category="internal", hidden=True)
def internal_healthcheck() -> str:
    """Return a simple health-check value."""
    return "ok"


@registry.register(category="demo")
def explode() -> None:
    """Raise an exception so structured error capture can be inspected."""
    raise RuntimeError("intentional smoke-test failure")


@registry.register(category="batch")
def first_step() -> str:
    return "first"


@registry.register(category="batch")
def second_step() -> str:
    return "second"


def main() -> None:
    print("\n1. Discovery and inferred metadata")
    print("---------------------------------")
    print("Visible tasks:", registry.list_names())
    print("All tasks:    ", registry.list_names(include_hidden=True))

    spec = registry["count_lines"]
    print(json.dumps(spec.to_dict(), indent=2))
    assert spec.description == "Count lines in a UTF-8 text file."
    assert [param.name for param in spec.params] == ["path", "ignore_empty"]
    assert spec.params[0].required is True
    assert spec.params[1].default is False
    assert "internal_healthcheck" not in registry.list_names()

    print("\n2. Real file task + boolean coercion")
    print("------------------------------------")
    with tempfile.TemporaryDirectory() as temp_dir:
        sample = Path(temp_dir) / "sample.txt"
        sample.write_text("alpha\n\nbeta\ngamma\n", encoding="utf-8")

        # Simulates values arriving from a CLI/query string.
        result = registry.run(
            "count_lines",
            path=str(sample),
            ignore_empty="true",
        )
        print(result.to_dict())
        assert result.status is TaskStatus.SUCCESS
        assert result.output == 3
        assert result.params["ignore_empty"] is True

    print("\n3. Numeric coercion")
    print("-------------------")
    result = registry.run("multiply", value="2.5", factor="4")
    print(result.to_dict())
    assert result.success
    assert result.output == 10.0
    assert result.params == {"value": 2.5, "factor": 4}

    print("\n4. Explicit choices")
    print("-------------------")
    good = registry.run("transform_text", text="Hello", mode="lower")
    bad = registry.run("transform_text", text="Hello", mode="title")
    print("Valid:  ", good.to_dict())
    print("Invalid:", bad.to_dict())
    assert good.output == "hello"
    assert bad.status is TaskStatus.FAILED
    assert "must be one of" in (bad.error or "")

    print("\n5. Missing and unexpected arguments")
    print("-----------------------------------")
    missing = registry.run("count_lines")
    unexpected = registry.run("multiply", value=2, typo=3)
    print("Missing:   ", missing.to_dict())
    print("Unexpected:", unexpected.to_dict())
    assert not missing.success
    assert "Missing required parameter" in (missing.error or "")
    assert not unexpected.success
    assert "Unexpected parameter" in (unexpected.error or "")

    print("\n6. Structured exception capture")
    print("-------------------------------")
    failed = registry.run("explode")
    print({
        "status": failed.status.value,
        "error": failed.error,
        "has_traceback": bool(failed.traceback),
    })
    assert not failed.success
    assert failed.error == "intentional smoke-test failure"
    assert "RuntimeError" in (failed.traceback or "")

    print("\n7. Filtering")
    print("------------")
    file_tasks = registry.filter(category="files")
    tagged = registry.filter(tags=["transform"])
    searched = registry.filter(search="multiply")
    print("category='files':", [task.name for task in file_tasks])
    print("tag='transform': ", [task.name for task in tagged])
    print("search='multiply':", [task.name for task in searched])
    assert [task.name for task in file_tasks] == ["count_lines"]
    assert [task.name for task in tagged] == ["transform_text"]
    assert [task.name for task in searched] == ["multiply"]

    print("\n8. Batch execution")
    print("------------------")
    batch = registry.run_many(["first_step", "second_step"])
    print([result.to_dict() for result in batch])
    assert [result.output for result in batch] == ["first", "second"]

    stopped = registry.run_many(
        ["first_step", "explode", "second_step"],
        stop_on_failure=True,
    )
    print("Stopped after:", [result.task_name for result in stopped])
    assert [result.task_name for result in stopped] == ["first_step", "explode"]

    print("\n9. Duplicate registration protection")
    print("------------------------------------")
    try:
        registry.register_function(count_lines)
    except TaskAlreadyRegisteredError as exc:
        print(type(exc).__name__ + ":", exc)
    else:
        raise AssertionError("Duplicate registration should have failed")

    print("\n10. Registry serialization")
    print("--------------------------")
    serialized = registry.to_dict(include_hidden=False)
    encoded = json.dumps(serialized, indent=2)
    print(encoded[:1200] + ("\n..." if len(encoded) > 1200 else ""))
    assert "internal_healthcheck" not in serialized["tasks"]
    assert "count_lines" in serialized["tasks"]
    assert "fn" not in serialized["tasks"]["count_lines"]

    print("\nAll practical smoke tests passed.")


if __name__ == "__main__":
    main()
