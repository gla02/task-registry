"""Exceptions raised by task-registry."""

from __future__ import annotations


class TaskRegistryError(Exception):
    """Base exception for registry errors."""


class TaskAlreadyRegisteredError(TaskRegistryError):
    """Raised when a task name is registered more than once."""


class TaskNotFoundError(TaskRegistryError):
    """Raised when a requested task is not registered."""


class TaskValidationError(TaskRegistryError):
    """Raised when supplied task arguments cannot be prepared safely."""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))
