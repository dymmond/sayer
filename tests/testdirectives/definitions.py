import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from inspect import isroutine
from types import ModuleType
from typing import Any, ClassVar, TypeVar

from sayer.utils.directives import (
    directive_function_or_help,
    find_directives_from_module,
    find_directives_from_path,
    transpose_directives,
)

F = TypeVar("F", bound=Callable[..., Any])

success = object()


class BaseDirective(ABC):
    __is_custom_directive__: ClassVar[bool] = True
    __display_in_cli__: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def run(cls, *args) -> None:
        pass


def directive(
    func: F | None = None,
    *,
    display_in_cli: bool = False,
) -> Callable[[F], F]:

    def wrapper(f: F) -> F:
        f.__is_custom_directive__ = True  # type: ignore[attr-defined]
        f.__display_in_cli__ = display_in_cli  # type: ignore[attr-defined]
        return f

    if func is not None:
        return wrapper(func)

    return wrapper


def extractor_directive(module: ModuleType, relative):
    found: Callable | None = None
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "__is_custom_directive__", False):
            if isroutine(obj):
                new_found = obj
            elif obj.__name__ == "Directive":
                new_found = obj()
            else:
                continue
            if found is not None:
                raise RuntimeError(
                    f"Detected multiple directives in the same file: `{module.__file__}`."
                )
            found = new_found
    return found


def extractor_help(tup: Any) -> str | None:
    if not getattr(tup.directive, "__display_in_cli__", False):
        return None
    return tup.directive.__doc__ or ""


def find_directive(path: os.PathLike, directive: str | None):
    directives = find_directives_from_path(
        path,
        patterns=["**/directives/operations/[!_]*.py", "**/directives/operations/*/__init__.py"],
        extractor_directive=extractor_directive,
    )
    transposed = transpose_directives(directives, extractor_help=extractor_help)
    return directive_function_or_help(transposed, directive=directive)


def find_directive_system(directive: str | None, extractor_app_name: Any = None):
    directives = find_directives_from_module(
        "tests.testdirectives.valid3",
        patterns=["**/directives/[!_]*.py", "**/directives/*/__init__.py"],
        extractor_directive=extractor_directive,
    )
    assert directives
    transposed = transpose_directives(
        directives, extractor_help=extractor_help, extractor_app_name=extractor_app_name
    )
    return directive_function_or_help(transposed, directive=directive)


def find_directive_zipapp(directive: str | None, extractor_app_name: Any = None):
    import valid4

    directives = find_directives_from_module(
        valid4,
        patterns=["**/directives/[!_]*.pyc", "**/directives/*/__init__.pyc"],
        extractor_directive=extractor_directive,
    )
    assert directives
    transposed = transpose_directives(
        directives, extractor_help=extractor_help, extractor_app_name=extractor_app_name
    )
    return directive_function_or_help(transposed, directive=directive)


def execute_directive(
    path: os.PathLike,
    directive: str | None,
    args: Sequence[Any] = (),
    kwargs: dict[str, Any] | None = None,
):
    retrieved = find_directive(path, directive)
    if retrieved is not None:
        kwargs = {} if kwargs is None else kwargs
        retrieved = (
            retrieved.run(*args, **kwargs)
            if isinstance(retrieved, BaseDirective)
            else retrieved(*args, **kwargs)
        )
        assert retrieved is success
    return retrieved
