import importlib
import importlib.util
import os
import pkgutil
import sys
from collections.abc import Callable, Collection, Container, Mapping
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

from rich.padding import Padding

from sayer.utils.ui import echo, error


class DirectiveTuple(NamedTuple):
    module: ModuleType
    root: Path
    relative: Path
    func: Callable


def _find_directives_from_path(
    path: os.PathLike,
    *,
    root: Path | None = None,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, Path], Callable | None],
    ignore1: Container[str],
    ignore2: Container[str] = frozenset(),
    use_files: bool | None
) -> dict[str, DirectiveTuple | None]:
    directives: dict[str, DirectiveTuple | None] = {}
    used_path = Path(path).absolute()
    # if exists, bypass loading modules and glob directly
    if use_files is not False and used_path.exists():
        if root is None:
            root = used_path
        # to prevent duplicates
        used_path = used_path.resolve()
        paths = [
            p
            for p, _, _ in used_path.walk()
            if all(not x.startswith("_") and x.isidentifier() for x in p.relative_to(root).parts)
        ]
        iterable = pkgutil.iter_modules(paths)
        import_pkgs = False
    elif use_files:
        return directives
    else:
        iterable = pkgutil.walk_packages([path])
        import_pkgs = True
    if root is None:
        root = used_path

    for finder, name, ispkg in iterable:
        module = None
        if import_pkgs and ispkg:
            # skip internal modules
            if name.startswith("_"):
                continue
            spec = finder.find_spec(name, None)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module.__name__] = module
            if spec.loader is not None:
                spec.loader.exec_module(module)
        if hasattr(finder, "get_filename"):
            full_name_str = finder.get_filename(name)
        else:
            sanitized_name = name.replace(".", os.sep)
            full_name_str = (
                f"{finder.path}{os.sep}{sanitized_name}{os.sep}__init__.py" if ispkg else f"{finder.path}{os.sep}{sanitized_name}.py"
            )
        relative = Path(full_name_str).relative_to(root)
        absolute_path_str = str(root / relative)
        if absolute_path_str in directives or absolute_path_str in ignore1 or absolute_path_str in ignore2:
            continue
        if not any(relative.full_match(pattern) for pattern in patterns):
            continue
        if module is None:
            spec = finder.find_spec(name, None)
            module = importlib.util.module_from_spec(spec)
            if spec.loader is not None:
                spec.loader.exec_module(module)
        fn = extractor_directive(module, relative)
        if fn is not None:
            directives[absolute_path_str] = DirectiveTuple(module, root, relative, fn)
    return directives


def find_directives_from_path(
    path: os.PathLike,
    *,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, Path], Callable | None],
    ignore: Container[str] = frozenset(),
    use_files: bool | None = None
) -> dict[str, DirectiveTuple | None]:
    return _find_directives_from_path(path, patterns=patterns, extractor_directive=extractor_directive, ignore1=ignore, use_files=use_files)


def find_directives_from_module(
    module: str | ModuleType,
    *,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, Path], Callable | None],
    ignore: Container[str] = frozenset(),
) -> dict[str, DirectiveTuple | None]:
    """
    """
    directives: dict[str, DirectiveTuple | None] = {}
    if isinstance(module, str):
        module = importlib.import_module(module)
    root = (Path(module.__spec__.origin).parent  if module.__spec__.origin else Path(module.__name__.replace(".", os.sep))).absolute()
    for path in module.__path__:
        directives.update(
            _find_directives_from_path(
                path, root=root, patterns=patterns, extractor_directive=extractor_directive, ignore1=ignore, ignore2=directives, use_files=False
            )
        )
    return directives


def transpose_directives(
    directives: dict[str, DirectiveTuple | None],
    *,
    extractor_help: Callable[[DirectiveTuple], None | str] = lambda tup: tup.func.__doc__ or "",
    extractor_app_name: Callable[[DirectiveTuple], str] | None = None
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
    Returns:
        Dict mapping with `None` for ambigious directives. Full collisions (two tuple key resolving to None) should be treated as error.
    """
    if extractor_app_name is None:
        def extractor_app_name(directive_tuple: DirectiveTuple) -> str:
            if app_name := getattr(directive_tuple.module, "app_name", None):
                return app_name
            # is an __init__
            if Path(directive_tuple.module.__spec__.origin).stem == "__init__":
                return directive_tuple.relative.parts[0] if len(directive_tuple.relative.parts) > 2 else directive_tuple.root.name
            else:
                return directive_tuple.relative.parts[0] if len(directive_tuple.relative.parts) > 1 else directive_tuple.root.name
    directives_by_app_and_name: dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None] = {}
    for directive_tuple in directives.values():
        if directive_tuple is not None:
            directive_tuple = DirectiveTuple(*directive_tuple)
            name = (
                directive_tuple.relative.parent.name if directive_tuple.relative.stem == "__init__" else directive_tuple.relative.stem
            )
            assert "." not in name, f"Name should not contain `.`: `{name}`"
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
            final_tup = (extracted_help, directive_tuple.func)
            directives_by_app_and_name.setdefault(app_name_tup, final_tup)
            directives_by_app_and_name.setdefault(name_tup, final_tup)
    return directives_by_app_and_name


def directive_function_or_help(
    transposed: Mapping[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None],
    /,
    *,
    directive: str | None,
    help_text_preamble: str = "Available directives:\n",
) -> Callable | None:
    """
    Helper for retrieving the directive, displaying a proper error or help in case of no directive or errornous command.

    Args:
        transposed (dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None]):
            Contains the name, app_name.name mappings of the directives to help and actual callables
    Kwargs:
        directive (str | None): If empty or `None` display the found directives. Otherwise try to resolve
        help_text_preamble: (str):
            Preamble to echo when outputing help. Defaults to "Available directives:\n".
            Note: should end with newline.
    Raises:
        SysExit(1): For errors (wrong or ambigous provided directive, colliding directives).
    """
    collisions = tuple(k for k, v in transposed.items() if len(k) == 2 and v is None)
    if collisions:
        error("Following directive have collisions:\n")
        for collision in collisions:
            echo(f"  [red]{collision[0]}.{collision[1]}[/]\n")
        sys.exit(1)
    if not directive:
        if help_text_preamble:
            echo(help_text_preamble)
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
