"""Core data models for task-registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class _MissingType:
    """Sentinel used to distinguish a missing default from ``None``."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _MissingType()


class TaskStatus(str, Enum):
    """Final status of a synchronous task execution."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(slots=True)
class TaskParam:
    """Machine-readable metadata for one task parameter."""

    name: str
    param_type: Any | None = None
    default: Any = MISSING
    description: str = ""
    choices: tuple[Any, ...] | None = None

    @property
    def required(self) -> bool:
        """Whether callers must provide a value for this parameter."""

        return self.default is MISSING

    def to_dict(self) -> dict[str, Any]:
        """Serialize parameter metadata for APIs, CLIs, or UIs."""

        data: dict[str, Any] = {
            "name": self.name,
            "type": _annotation_name(self.param_type),
            "required": self.required,
            "description": self.description,
            "choices": list(self.choices) if self.choices is not None else None,
        }
        if not self.required:
            data["default"] = self.default
        return data


@dataclass(slots=True)
class TaskSpec:
    """Description of a registered Python callable."""

    name: str
    fn: Callable[..., Any]
    description: str = ""
    category: str | None = None
    params: list[TaskParam] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    hidden: bool = False

    def __post_init__(self) -> None:
        if not self.description and self.fn.__doc__:
            self.description = self.fn.__doc__.strip().splitlines()[0]

    def to_dict(self) -> dict[str, Any]:
        """Serialize task metadata without serializing the callable itself."""

        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "params": [param.to_dict() for param in self.params],
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "hidden": self.hidden,
        }


@dataclass(slots=True)
class TaskResult:
    """Structured result from one synchronous task execution."""

    task_name: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    traceback: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def success(self) -> bool:
        """Whether execution completed successfully."""

        return self.status is TaskStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution result."""

        return {
            "task_name": self.task_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "traceback": self.traceback,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
            "params": dict(self.params),
        }


def _annotation_name(annotation: Any | None) -> str | None:
    if annotation is None:
        return None
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")
