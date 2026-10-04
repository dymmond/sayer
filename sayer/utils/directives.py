import importlib
import importlib.util
import os
import pkgutil
import sys
from collections.abc import Callable, Collection, Container
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

from rich.padding import Padding

from sayer.utils.ui import echo, error


class _DirectiveTuple(NamedTuple):
    module: ModuleType
    relative: Path
    func: Callable

def find_directives_from_module(
    module: str | ModuleType,
    *,
    patterns: Collection[str] | None  = None,
    extractor_directive: Callable[[ModuleType, Path], Callable | None],
    seen: Container[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], _DirectiveTuple | None]:
    directives: dict[tuple[str, str], _DirectiveTuple | None] = {}
    seen = seen if seen is not None else set()
    if isinstance(module, str):
        module = importlib.import_module(module)
    root = Path(module.__file__).parent
    for submodule_name in dir(module):
        if not submodule_name.startswith("_"):
            submodule = getattr(module, submodule_name)
            if not isinstance(submodule, ModuleType):
                continue
            full_name_str = submodule.__file__
            relative = Path(full_name_str).relative_to(root)
            id_tup = (str(root), full_name_str)
            if id_tup in directives or id_tup in seen:
                continue
            if patterns is not None and not any(relative.full_match(pattern) for pattern in patterns):
                continue
            fn = extractor_directive(submodule, relative)
            if fn is not None:
                directives[id_tup] = _DirectiveTuple(submodule, relative, fn)
    return directives

def find_directives_from_files(
    path: os.PathLike,
    *,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, Path], Callable | None],
    seen: Container[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], _DirectiveTuple | None]:
    directives: dict[tuple[str, str], _DirectiveTuple | None] = {}
    seen = seen if seen is not None else set()
    root = Path(path)
    paths = [
        p
        for p, _, _ in root.walk()
        if all(not x.startswith("_") and x.isidentifier() for x in p.relative_to(root).parts)
    ]
    for finder, name, ispkg in  pkgutil.iter_modules(paths):
        if not name.startswith("_"):
            full_name_str = (
                f"{finder.path}{os.sep}{name}{os.sep}__init__.py" if ispkg else f"{finder.path}{os.sep}{name}.py"
            )
            relative = Path(full_name_str).relative_to(root)
            id_tup = (str(root), full_name_str)
            if id_tup in directives or id_tup in seen:
                continue
            if not any(relative.full_match(pattern) for pattern in patterns):
                continue
            spec = finder.find_spec(name, None)
            module = importlib.util.module_from_spec(spec)
            if spec.loader is not None:
                spec.loader.exec_module(module)
            fn = extractor_directive(module, relative)
            if fn is not None:
                directives[id_tup] = _DirectiveTuple(module, relative, fn)
    return directives


def transpose_directives(
    directives: dict[tuple[str, str], _DirectiveTuple | None],
    *,
    extractor_help: Callable[[_DirectiveTuple], None | str] = lambda tup: tup.func.__doc__ or "",
    extractor_app_name: Callable[[_DirectiveTuple], str] = lambda tup: getattr(
        tup.module, "app_name", tup.relative.parts[0]
    ),
) -> dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None]:
    """

    Transpose directives into dictionaries referenced by name and app_name.

    Args:
        directives: Raw directives dictionary.

    Kwargs:
        extractor_help (Callable[[ModuleType, Path, Callable], None | str]):
            Extract the help text or `None` to not show up in help. Defaults to the doc string.
        extractor_app_name (Callable[[ModuleType, Path, Callable], str]):
            Extract the app_name. Defaults to the `app_name` module attribute or root folder defining the directive.
    """
    directives_by_app_and_name: dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None] = {}
    for directive_tuple in directives.values():
        if directive_tuple is not None:
            name = directive_tuple[1].parent.name if directive_tuple[1].name == "__init__.py" else directive_tuple[1].stem
            app_name = extractor_app_name(directive_tuple)
            name_tup = (name,)
            app_name_tup = (app_name, name)
            if app_name_tup in directives_by_app_and_name:
                # collision
                directives_by_app_and_name[app_name_tup] = None
            if name_tup in directives_by_app_and_name:
                directives_by_app_and_name[name_tup] = None
                continue
            extracted_help = extractor_help(directive_tuple)
            final_tup = (extracted_help, directive_tuple[2])
            directives_by_app_and_name.setdefault(app_name_tup, final_tup)
            directives_by_app_and_name.setdefault(name_tup, final_tup)
    return directives_by_app_and_name


def directive_function_or_help(
    transposed: dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None],
    /,
    *,
    directive: str | None,
    help_text_preamble: str = "",
) -> Callable | None:
    """Helper for executing the directive."""
    collisions = tuple(k for k, v in transposed.items() if len(k) == 2 and v is None)
    if collisions:
        error("Following directive have collisions:\n")
        for collision in collisions:
            echo(f"  [red]{collision[0]}.{collision[1]}[/]\n")
        sys.exit(1)
    if not directive:
        echo(f"{help_text_preamble}Available directives:\n")
        last_app = None
        for key_tup, [help_text, _] in sorted(transposed.items(), key=lambda k, v: k):
            if help_text is None or len(key_tup) == 1:
                continue
            app_name, name = key_tup
            if last_app != app_name:
                echo(f"\n[bold green]\\[{app_name}][/]\n")
            echo(f"  [bold blue]{name}[/]:\n")
            if help_text:
                echo(Padding(help_text, (0, 0, 0, 4), expand=False))
            last_app = app_name
        return None
    else:
        search_tuple = tuple(directive.rsplit(".", 1))
        if search_tuple not in transposed:
            error(f"Specified directive: {directive} not found.")
            sys.exit(1)
        retrieved = transposed[search_tuple]
        if retrieved is None:
            error(
                f"Specified directive: {directive} could not be uniquely identified. Please provide also the `app_name`."
            )
            sys.exit(1)
        return retrieved[1]
