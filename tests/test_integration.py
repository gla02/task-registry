from pathlib import Path

from task_registry import TaskRegistry, TaskStatus


def test_end_to_end_registry_flow(tmp_path: Path):
    registry = TaskRegistry()

    @registry.register(category="files", tags=["filesystem"])
    def count_lines(path: str, ignore_empty: bool = False) -> int:
        """Count lines in a UTF-8 text file."""
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        if ignore_empty:
            lines = [line for line in lines if line.strip()]
        return len(lines)

    sample = tmp_path / "sample.txt"
    sample.write_text("alpha\n\nbeta\ngamma\n", encoding="utf-8")

    result = registry.run(
        "count_lines",
        path=str(sample),
        ignore_empty="true",
    )

    assert result.status is TaskStatus.SUCCESS
    assert result.output == 3
    assert result.params["ignore_empty"] is True
    assert [task.name for task in registry.filter(category="files")] == ["count_lines"]
    assert "count_lines" in registry.to_dict()["tasks"]
