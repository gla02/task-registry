# Task Registry

A lightweight Python registry for turning ordinary functions into discoverable, validated, runnable tasks.

Task Registry sits between your application logic and the interfaces that need to discover or execute it. Register normal Python functions once, then inspect their metadata, filter them by category or tags, validate inputs, run them consistently, and expose their schemas to a CLI, API, UI, internal tool, or agent.

## Why this project?

Applications often accumulate operations that can be triggered from more than one place: maintenance jobs, admin actions, data utilities, reports, import/export commands, developer tools, and similar functions. Without a shared abstraction, each interface tends to duplicate names, parameter definitions, validation, and execution handling.

Task Registry provides a small framework-neutral layer for those operations without becoming a scheduler, job queue, or workflow engine.

## Example

```python
from task_registry import TaskRegistry

registry = TaskRegistry()

@registry.register(category="files", tags=["filesystem"])
def count_lines(path: str, ignore_empty: bool = False) -> int:
    """Count lines in a text file."""
    with open(path, encoding="utf-8") as file:
        lines = file.readlines()
    if ignore_empty:
        lines = [line for line in lines if line.strip()]
    return len(lines)
```

The function signature is inspected automatically:

```python
print(registry["count_lines"].to_dict())
```

producing structured metadata such as:

```python
{
    "name": "count_lines",
    "description": "Count lines in a text file.",
    "category": "files",
    "params": [
        {
            "name": "path",
            "type": "str",
            "required": True,
            "description": "",
            "choices": None,
        },
        {
            "name": "ignore_empty",
            "type": "bool",
            "required": False,
            "default": False,
            "description": "",
            "choices": None,
        },
    ],
    "tags": ["filesystem"],
    "metadata": {},
    "hidden": False,
}
```

Execute the same task through the registry:

```python
result = registry.run(
    "count_lines",
    path="notes.txt",
    ignore_empty="true",
)

if result.success:
    print(result.output)
else:
    print(result.error)
```

Simple primitive values can be normalized from interface-friendly strings before execution. In v0.1, automatic coercion is intentionally limited to `str`, `int`, `float`, `bool`, and their optional forms; richer annotations are preserved as metadata rather than treated as a validation framework.

## Features

- Decorator or direct function registration
- Automatic parameter discovery from Python signatures
- Required/default parameter handling, including real `None` defaults
- Simple input normalization for strings, integers, floats, and booleans
- Explicit choices for parameters when needed
- Category, tag, and text-based discovery
- Duplicate registration protection with explicit replacement
- Structured execution results with timing and captured errors
- Machine-readable task metadata for external interfaces
- No runtime dependencies

## Explicit parameter metadata

Signature inference handles the common case. Explicit `TaskParam` definitions are available when an interface needs extra constraints such as choices:

```python
from task_registry import TaskParam, TaskRegistry

registry = TaskRegistry()


def export_report(format: str = "json") -> str:
    return format


registry.register_function(
    export_report,
    params=[
        TaskParam(
            "format",
            str,
            default="json",
            choices=("json", "csv"),
        )
    ],
)
```

## Discovery

```python
registry.list_names()
registry.filter(category="files")
registry.filter(tags=["filesystem"])
registry.filter(search="line")
```

Application-specific hints can live in metadata without becoming assumptions of the library:

```python
@registry.register(
    category="maintenance",
    metadata={"requires_admin": True, "long_running": True},
)
def rebuild_index():
    ...
```

Task Registry preserves and serializes that metadata but does not interpret it.

`hidden=True` removes a task from normal discovery and default serialization, but it is not an authorization mechanism. Hidden tasks can still be addressed directly by name.

## Design boundaries

Task Registry intentionally handles only task description, discovery, input preparation, synchronous execution, and structured results.

It does **not** provide background workers, scheduling, retries, persistence, dependency injection, progress tracking, web endpoints, or workflow graphs. Those concerns can be layered on top by the application that needs them.

Registered functions must have a finite keyword-callable signature. Positional-only arguments, `*args`, and `**kwargs` are rejected during automatic signature inspection because they cannot be represented cleanly as a finite task schema. Async callables are also rejected because v0.1 executes tasks synchronously.

When `params` is supplied explicitly, it replaces inferred parameter metadata. The caller is responsible for keeping that schema compatible with the callable.

## Package-level convenience registry

Explicit registry instances are recommended for most applications, but tiny projects can use the shared convenience registry:

```python
from task_registry import task, tasks

@task(category="maintenance")
def cleanup() -> None:
    ...

result = tasks.run("cleanup")
```

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

MIT
