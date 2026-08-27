"""Helpers for asserting deterministic pure-analysis functions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


def assert_deterministic(function: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    """Return whether two isolated calls produce the same value.

    Inputs are deep-copied for each invocation so a function that mutates its
    arguments cannot make a later call appear deterministic by accident.
    Exceptions deliberately propagate to keep test and runtime failures visible.
    """

    first = function(*deepcopy(args), **deepcopy(kwargs))
    second = function(*deepcopy(args), **deepcopy(kwargs))
    return first == second
