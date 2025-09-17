import functools
import inspect
from typing import Any


def is_async_callable(obj: Any) -> bool:
    """
    Validates if a given object is an async callable or not.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return inspect.iscoroutinefunction(obj) or (callable(obj) and inspect.iscoroutinefunction(obj.__call__))
