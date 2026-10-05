"""Task registration, discovery, and synchronous execution."""

from __future__ import annotations

import inspect
import logging
import time
import traceback as traceback_module
from collections.abc import Callable, Collection
from typing import Any, ParamSpec, TypeVar

from .exceptions import TaskAlreadyRegisteredError, TaskNotFoundError, TaskValidationError
from .models import TaskParam, TaskResult, TaskSpec, TaskStatus
from .params import inspect_params, prepare_args

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class TaskRegistry:
    """Register, discover, describe, and execute ordinary Python callables."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskSpec] = {}

    def register(
        self,
        name: str | None = None,
        *,
        category: str | None = None,
        description: str = "",
        params: list[TaskParam] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        hidden: bool = False,
        replace: bool = False,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Return a decorator that registers a function as a task."""

        def decorator(fn: Callable[P, R]) -> Callable[P, R]:
            self.register_function(
                fn,
                name=name,
                category=category,
                description=description,
                params=params,
                tags=tags,
                metadata=metadata,
                hidden=hidden,
                replace=replace,
            )
            return fn

        return decorator

    def register_spec(
        self,
        spec: TaskSpec,
        *,
        replace: bool = False,
    ) -> TaskRegistry:
        """Register a pre-built :class:`TaskSpec`."""

        self._ensure_available(spec.name, replace=replace)
        self._tasks[spec.name] = spec
        logger.debug("Registered task: %s", spec.name)
        return self

    def register_function(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        *,
        category: str | None = None,
        description: str = "",
        params: list[TaskParam] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        hidden: bool = False,
        replace: bool = False,
    ) -> TaskRegistry:
        """Register a callable without decorator syntax."""

        task_name = name or fn.__name__
        self._ensure_available(task_name, replace=replace)

        if inspect.iscoroutinefunction(fn):
            raise TaskValidationError(
                ["Async callables are not supported by the synchronous task registry"]
            )

        spec = TaskSpec(
            name=task_name,
            fn=fn,
            description=description,
            category=category,
            params=list(params) if params is not None else inspect_params(fn),
            tags=list(tags or []),
            metadata=dict(metadata or {}),
            hidden=hidden,
        )
        self._tasks[task_name] = spec
        logger.debug("Registered task: %s", task_name)
        return self

    def unregister(self, name: str) -> TaskRegistry:
        """Remove a registered task."""

        if name not in self._tasks:
            raise TaskNotFoundError(f"Task '{name}' is not registered")
        del self._tasks[name]
        return self

    def get(self, name: str) -> TaskSpec | None:
        """Return a task specification, or ``None`` when absent."""

        return self._tasks.get(name)

    def __getitem__(self, name: str) -> TaskSpec:
        try:
            return self._tasks[name]
        except KeyError as exc:
            raise TaskNotFoundError(f"Task '{name}' is not registered") from exc

    def __contains__(self, name: object) -> bool:
        return name in self._tasks

    def __len__(self) -> int:
        return len(self._tasks)

    def list_names(self, *, include_hidden: bool = False) -> list[str]:
        """Return registered task names in sorted order."""

        return sorted(
            spec.name
            for spec in self._tasks.values()
            if include_hidden or not spec.hidden
        )

    def filter(
        self,
        *,
        category: str | None = None,
        tags: Collection[str] | None = None,
        search: str | None = None,
        include_hidden: bool = False,
    ) -> list[TaskSpec]:
        """Return tasks matching category, tags, and/or search text."""

        tag_set = set(tags) if tags is not None else None
        search_lower = search.lower() if search is not None else None
        matches: list[TaskSpec] = []

        for spec in self._tasks.values():
            if spec.hidden and not include_hidden:
                continue
            if category is not None and spec.category != category:
                continue
            if tag_set is not None and not tag_set.intersection(spec.tags):
                continue
            if search_lower is not None:
                haystack = f"{spec.name} {spec.description}".lower()
                if search_lower not in haystack:
                    continue
            matches.append(spec)

        return sorted(matches, key=lambda item: ((item.category or ""), item.name))

    def run(self, name: str, **kwargs: Any) -> TaskResult:
        """Execute a registered task and return a structured result."""

        spec = self.get(name)
        if spec is None:
            return TaskResult(
                task_name=name,
                status=TaskStatus.FAILED,
                error=f"Task '{name}' is not registered",
                params=dict(kwargs),
            )

        try:
            prepared = prepare_args(spec, kwargs)
        except TaskValidationError as exc:
            return TaskResult(
                task_name=name,
                status=TaskStatus.FAILED,
                error=str(exc),
                params=dict(kwargs),
            )

        logger.info("Running task: %s", name)
        start = time.perf_counter()
        try:
            output = spec.fn(**prepared)
        except Exception as exc:  # noqa: BLE001 - exceptions are intentionally captured.
            duration = time.perf_counter() - start
            logger.debug("Task %s failed", name, exc_info=True)
            return TaskResult(
                task_name=name,
                status=TaskStatus.FAILED,
                error=str(exc),
                traceback=traceback_module.format_exc(),
                duration_seconds=duration,
                params=prepared,
            )

        duration = time.perf_counter() - start
        logger.info("Task %s completed in %.3fs", name, duration)
        return TaskResult(
            task_name=name,
            status=TaskStatus.SUCCESS,
            output=output,
            duration_seconds=duration,
            params=prepared,
        )

    def run_many(
        self,
        names: Collection[str],
        *,
        stop_on_failure: bool = False,
        **shared_kwargs: Any,
    ) -> list[TaskResult]:
        """Execute multiple tasks sequentially using shared keyword arguments."""

        results: list[TaskResult] = []
        for name in names:
            result = self.run(name, **shared_kwargs)
            results.append(result)
            if stop_on_failure and not result.success:
                break
        return results

    def to_dict(self, *, include_hidden: bool = False) -> dict[str, Any]:
        """Serialize registered task metadata."""

        return {
            "tasks": {
                spec.name: spec.to_dict()
                for spec in sorted(self._tasks.values(), key=lambda item: item.name)
                if include_hidden or not spec.hidden
            }
        }

    def _ensure_available(self, name: str, *, replace: bool) -> None:
        if name in self._tasks and not replace:
            raise TaskAlreadyRegisteredError(
                f"Task '{name}' is already registered; pass replace=True to replace it"
            )


tasks = TaskRegistry()


def task(
    name: str | None = None,
    *,
    category: str | None = None,
    description: str = "",
    params: list[TaskParam] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    hidden: bool = False,
    replace: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register a function in the package-level convenience registry."""

    return tasks.register(
        name=name,
        category=category,
        description=description,
        params=params,
        tags=tags,
        metadata=metadata,
        hidden=hidden,
        replace=replace,
    )
