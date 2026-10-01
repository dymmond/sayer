import importlib
import importlib.util
import os
import pkgutil
import sys
from collections.abc import Callable
from inspect import isawaitable
from pathlib import Path
from types import ModuleType
from typing import Any

from sayer.utils.ui import echo, error


def find_directives_from(*, path: os.PathLike, pattern: str, extractor: Callable[[Path, ModuleType], tuple[str, Any]], initial_directives: dict[str, tuple[Path, str, Any] | None] | None = None) -> dict[str, tuple[Path, str, Any] | None]:
    root = Path(path)
    directives: dict[str, Any] = initial_directives if initial_directives is not None else {}
    for directive_dir in root.glob(pattern):
        relative = directive_dir.relative_to(root)
        if not all(part.isidentifier() and not part.startswith("_") for part in relative.parts):
            continue

        for _, name, _ in pkgutil.iter_modules([directive_dir]):
            if not name.startswith("_"):
                full_path = relative / f"{name}.py"
                full_path_str = str(full_path)
                if full_path_str in directives:
                    continue
                if full_path.exists():
                    spec = importlib.util.spec_from_file_location(name, full_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    app_name, imported = extractor(full_path, module)
                    directives[full_path_str] = (full_path, app_name, imported)
                else:
                    directives[full_path_str] = None
    return directives


def transpose_directives(directives: dict[str, tuple[Path, str, Any] | None]) -> tuple[dict[tuple[str, str], Any], dict[str, Any]]:
    """Transpose directives into app.name, name dictionaries."""

    directives_by_app_and_name: dict[tuple[str, str], Any] = {}
    directives_by_name: dict[str, Any] = {}
    for directive_tuple in directives.values():
        if directive_tuple is not None:
            name = directive_tuple[0].stem
            app_name = directive_tuple[1]
            if (app_name, name) in directives_by_app_and_name:
                directives_by_app_and_name[(app_name, name)] = None
            if name in directives_by_name:
                directives_by_name[name] = None
                continue
            directives_by_app_and_name[(app_name, name)] = directive_tuple[2]
            directives_by_name[name] = directive_tuple[2]
    return directives_by_app_and_name, directives_by_name


async def execute_directive(directives_or_transposed: tuple[dict[str, Any], dict[str, Any]] | dict[str, Any], /, directive: str | None, *args: str, help_text_preamble: str = "") -> Any:
    """Helper for executing the directive."""
    if not isinstance(directives_or_transposed, tuple):
        directives_by_app_and_name, directives_by_name = transpose_directives(directives_or_transposed)
    else:
        # already transposed
        directives_by_app_and_name, directives_by_name = directives_or_transposed
    if not directive:
        echo(f"{help_text_preamble}Available directives:\n")
        last_app = None
        for app, name in sorted(directives_by_app_and_name.keys()):
            if last_app != app:
                echo("\n")
                echo(f"[bold green]\\[{app}]\n")
            echo(f"    [bold blue]{name}\n")
            last_app = app
        return None
    else:
        if "." in directive:
            tup = tuple(directive.split(".", 1))
            if tup not in directives_by_app_and_name:
                error(f"Fully specified directive: {directive} not found.")
                sys.exit(1)
            retrieved = directives_by_app_and_name[tup]
            if retrieved is None:
                error(f"Directive: `{directive}` could not be uniquely resolved.")
                sys.exit(1)
            result = retrieved(*args)
        else:
            if directive not in directives_by_name:
                error(f"Directive: `{directive}` not found.")
                sys.exit(1)
            retrieved = directives_by_name[directive]
            if retrieved is None:
                error(f"Directive: `{directive}` could not be uniquely resolved.")
                sys.exit(1)
            result = retrieved(*args)
        if isawaitable(result):
            result = await result
        return result
