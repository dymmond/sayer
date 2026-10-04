import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from inspect import isawaitable, isroutine
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, Sequence, TypeVar

from sayer.utils.directives import directive_function_or_help, find_directives_from_files, transpose_directives, find_directives_from_module

F = TypeVar("F", bound=Callable[..., Any])

success = object()


class BaseDirective(ABC):
    __is_custom_directive__: ClassVar[bool] = True
    __display_in_cli__: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def run(*args) -> None:
        pass


def extractor_directive(module: ModuleType, relative):
    found: Callable | None = None
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "__is_custom_directive__", False):
            if isroutine(obj):
                new_found = obj
            elif obj.__name__ == "Directive":
                new_found = obj.run
            else:
                continue
            if found is not None:
                raise RuntimeError(f"Detected multiple directives in the same file: `{module.__file__}`.")
            found = new_found
    return found


def extractor_help(tup: Any) -> str | None:
    if not getattr(tup.func, "__display_in_cli__", False):
        return None
    return tup.func.__doc__ or ""


def find_directive(path: os.PathLike, directive: str | None):
    directives = find_directives_from_files(
        path, patterns=["**/directives/operations/[!_]*.py", "**/directives/operations/*/__init__.py"], extractor_directive=extractor_directive
    )
    transposed = transpose_directives(directives, extractor_help=extractor_help)
    return directive_function_or_help(transposed, directive=directive)


def find_directive_system(directive: str | None, patterns: any):
    from ..testdirectives_module import valid3
    directives = find_directives_from_module(
        valid3, patterns=patterns, extractor_directive=extractor_directive
    )
    transposed = transpose_directives(directives, extractor_help=extractor_help, extractor_app_name=lambda x: valid3.__name__.rsplit(".", 1)[-1])
    return directive_function_or_help(transposed, directive=directive)

def execute_directive(
    path: os.PathLike, directive: str | None, args: Sequence[Any] = (), kwargs: dict[str, Any] | None = None
):
    retrieved = find_directive(path, directive)
    if retrieved is not None:
        kwargs = {} if kwargs is None else kwargs
        retrieved = retrieved(*args, **kwargs)
        assert retrieved is success


def directive(
    func: F | None = None,
    *,
    display_in_cli: bool = False,
) -> Callable[[F], F]:
    """
    Marks a function-based Sayer CLI command as a custom Lilya directive.

    This decorator factory allows optional configuration via parameters, such as `show_on_cli`.

    Example usage:

        @directive(display_in_cli=True)
        @command(name="create")
        async def create(name: Annotated[str, Option(help="Your name")]):
            ...

    Parameters:
        display_in_cli (bool): Whether the directive should be visible in the CLI help output.

    Returns:
        Callable: A decorator that marks the function as a custom directive.
    """

    def wrapper(f: F) -> F:
        f.__is_custom_directive__ = True  # type: ignore[attr-defined]
        f.__display_in_cli__ = display_in_cli  # type: ignore[attr-defined]
        return f

    if func is not None:
        return wrapper(func)

    return wrapper
