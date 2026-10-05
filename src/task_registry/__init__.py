"""Lightweight registry for discoverable, validated Python tasks."""

from .exceptions import (
    TaskAlreadyRegisteredError,
    TaskNotFoundError,
    TaskRegistryError,
    TaskValidationError,
)
from .models import TaskParam, TaskResult, TaskSpec, TaskStatus
from .registry import TaskRegistry, task, tasks

__all__ = [
    "TaskAlreadyRegisteredError",
    "TaskNotFoundError",
    "TaskParam",
    "TaskRegistry",
    "TaskRegistryError",
    "TaskResult",
    "TaskSpec",
    "TaskStatus",
    "TaskValidationError",
    "task",
    "tasks",
]

__version__ = "0.1.0"
