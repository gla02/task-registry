"""Signature inspection and argument preparation."""

from __future__ import annotations

import inspect
import types
from collections.abc import Mapping
from typing import Any, Union, get_args, get_origin, get_type_hints

from .exceptions import TaskValidationError
from .models import MISSING, TaskParam, TaskSpec

_SUPPORTED_KINDS = {
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.KEYWORD_ONLY,
}


def inspect_params(fn: Any) -> list[TaskParam]:
    """Build :class:`TaskParam` metadata from a callable signature.

    Positional-only parameters, ``*args``, and ``**kwargs`` are intentionally
    rejected because registered tasks are executed with keyword arguments and
    exposed as a finite machine-readable schema.
    """

    signature = inspect.signature(fn)
    try:
        type_hints = get_type_hints(fn)
    except (NameError, TypeError):
        type_hints = {}

    params: list[TaskParam] = []
    unsupported: list[str] = []

    for parameter in signature.parameters.values():
        if parameter.kind not in _SUPPORTED_KINDS:
            unsupported.append(parameter.name)
            continue

        annotation = type_hints.get(parameter.name, parameter.annotation)
        if annotation is inspect.Signature.empty:
            annotation = None

        default = (
            MISSING
            if parameter.default is inspect.Signature.empty
            else parameter.default
        )
        params.append(
            TaskParam(
                name=parameter.name,
                param_type=annotation,
                default=default,
            )
        )

    if unsupported:
        names = ", ".join(unsupported)
        raise TaskValidationError(
            [
                "Unsupported callable signature. Registered tasks must use "
                f"keyword-callable parameters only; unsupported: {names}"
            ]
        )

    return params


def prepare_args(
    spec: TaskSpec,
    supplied: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a normalized argument dictionary for ``spec``.

    The input mapping is never mutated. Missing required values, unexpected
    arguments, failed coercions, and invalid choices are reported together in a
    :class:`TaskValidationError`.
    """

    params_by_name = {param.name: param for param in spec.params}
    errors: list[str] = []

    unexpected = sorted(set(supplied) - set(params_by_name))
    if unexpected:
        errors.append(f"Unexpected parameter(s): {', '.join(unexpected)}")

    prepared: dict[str, Any] = {}

    for param in spec.params:
        if param.name in supplied:
            raw_value = supplied[param.name]
            try:
                value = _coerce_value(raw_value, param.param_type)
            except (TypeError, ValueError) as exc:
                errors.append(f"Parameter '{param.name}': {exc}")
                continue
        elif param.required:
            errors.append(f"Missing required parameter: {param.name}")
            continue
        else:
            value = param.default

        if param.choices is not None and value not in param.choices:
            errors.append(
                f"Parameter '{param.name}' must be one of {list(param.choices)!r}, "
                f"got {value!r}"
            )
            continue

        prepared[param.name] = value

    if errors:
        raise TaskValidationError(errors)

    return prepared


def _coerce_value(value: Any, annotation: Any | None) -> Any:
    if annotation is None or annotation is Any:
        return value

    target, allows_none = _simple_target(annotation)
    if value is None:
        if allows_none:
            return None
        raise TypeError(f"must be {_type_label(annotation)}, got None")

    if target is None:
        # The annotation is useful as metadata but outside v1's coercion scope.
        return value

    if isinstance(value, target):
        return value

    try:
        if target is bool:
            return _coerce_bool(value)
        if target is str:
            return str(value)
        if target is int:
            if isinstance(value, float) and not value.is_integer():
                raise ValueError("must be an integer")
            return int(value)
        if target is float:
            return float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"must be {_type_label(annotation)}, got {type(value).__name__}"
        ) from exc

    return value


def _simple_target(annotation: Any) -> tuple[type[Any] | None, bool]:
    if annotation in {str, int, float, bool}:
        return annotation, False

    origin = get_origin(annotation)
    if origin in {Union, types.UnionType}:
        args = get_args(annotation)
        allows_none = type(None) in args
        concrete = [arg for arg in args if arg is not type(None)]
        if len(concrete) == 1 and concrete[0] in {str, int, float, bool}:
            return concrete[0], allows_none
        return None, allows_none

    return None, False


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("must be a boolean value")


def _type_label(annotation: Any) -> str:
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")
