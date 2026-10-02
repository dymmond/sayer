import importlib
import importlib.util
import os
import pkgutil
import sys
from collections.abc import Callable, Container, Iterable
from inspect import isawaitable
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple, Sequence

from rich.padding import Padding

from sayer.utils.ui import echo, error


class DirectiveTuple(NamedTuple):
    module: ModuleType
    # relative parent
    relative: Path
    # absolute path to file
    absolute: Path
    func: Callable


def find_directives_from(
    path: os.PathLike,
    *,
    pattern: str,
    extractor_directive: Callable[[ModuleType, Path, Path], Callable],
    seen: Container[str] | None = None,
) -> dict[str, DirectiveTuple | None]:
    root = Path(path)
    directives: dict[str, DirectiveTuple | None] = {}
    seen = seen if seen is not None else set()
    for directive_dir in root.glob(pattern):
        relative = directive_dir.relative_to(root)
        directive_dir = directive_dir.resolve()
        if not all(part.isidentifier() and not part.startswith("_") for part in relative.parts):
            continue

        for _, name, ispkg in pkgutil.iter_modules([directive_dir]):
            if not name.startswith("_") and not ispkg:
                full_path = directive_dir / f"{name}.py"
                relative_path = relative / f"{name}.py"
                full_path_str = str(full_path)
                if full_path_str in directives or full_path_str in seen:
                    continue
                if full_path.exists():
                    spec = importlib.util.spec_from_file_location(name, full_path)
                    module = importlib.util.module_from_spec(spec)
                    if spec.loader is not None:
                        spec.loader.exec_module(module)
                    fn = extractor_directive(module, relative_path, full_path)
                    directives[full_path_str] = DirectiveTuple(module, relative_path, full_path, fn)
                else:
                    directives[full_path_str] = None
    return directives


def transpose_directives(
    directives: dict[str, DirectiveTuple | None],
    *,
    extractor_help: Callable[[DirectiveTuple], None | str] = lambda tup: tup.func.__doc__ or "",
    extractor_app_name: Callable[[DirectiveTuple], str] = lambda tup: getattr(
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
            name = directive_tuple[1].stem
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
            final_tup = (extracted_help, directive_tuple[3])
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
