"""Minimal task-registry example."""

from task_registry import TaskRegistry

registry = TaskRegistry()


@registry.register(category="text", tags=["demo"])
def repeat(text: str, count: int = 1, uppercase: bool = False) -> str:
    """Repeat text a configurable number of times."""

    output = text.upper() if uppercase else text
    return " ".join([output] * count)


if __name__ == "__main__":
    print(registry.to_dict())
    result = registry.run("repeat", text="hello", count="3", uppercase="true")
    print(result.to_dict())
