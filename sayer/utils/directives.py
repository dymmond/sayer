import importlib
import importlib.util
import os
import pkgutil
import sys
from collections.abc import Callable, Collection, Container, Generator, Mapping
from difflib import get_close_matches
from itertools import chain
from pathlib import Path
from types import ModuleType
from typing import NamedTuple, NewType, cast

from rich.markup import escape
from rich.padding import Padding

from sayer.utils.ui import echo, error

RelativePath = NewType("RelativePath", Path)
RootPath = NewType("RootPath", Path)
DirectiveType = NewType("DirectiveType", object)


class DirectiveTuple(NamedTuple):
    module: ModuleType
    root: RootPath
    relative: RelativePath
    directive: DirectiveType


if sys.version_info < (3, 13):
    # full match is only available since python 3.13, Path.match (python 3.12) can't resolve `**`
    from wcmatch.pathlib import Path as WCPath  # type: ignore
    from wcmatch.wcmatch import GLOBSTAR  # type: ignore

    def _match_path_against_glob(path: Path, glob_pattern: str) -> bool:
        """Helper for compatibility with python<3.13."""
        return WCPath(path).full_match(glob_pattern, flags=GLOBSTAR)
else:

    def _match_path_against_glob(path: Path, glob_pattern: str) -> bool:
        return path.full_match(glob_pattern)


def _generate_file_based_mod_infos(
    used_path: Path,
    root: Path,
    patterns: Collection[str],
) -> Generator[pkgutil.ModuleInfo, None, None]:
    """Helper to extract ModuleInfo from files."""
    if sys.version_info < (3, 12):
        path_generator = os.walk(used_path)
    else:
        path_generator = used_path.walk()

    # for having order
    valid_paths: dict[Path, bool] = {}
    for directory, _, files in path_generator:
        # required for < 3.12
        if sys.version_info < (3, 12):
            directory = Path(directory)
        relative_path_dir = directory.relative_to(root)
        files = (relative_path_dir / f for f in files)
        if all(
            not part.startswith("_") and part.isidentifier() for part in relative_path_dir.parts
        ):
            for relpath in chain([relative_path_dir], files):
                if any(_match_path_against_glob(relpath, pattern) for pattern in patterns):
                    for parent in reversed(relative_path_dir.parents):
                        valid_paths.setdefault(parent, False)
                    valid_paths.setdefault(relative_path_dir, True)
                    break
    for path in valid_paths:
        combined = root / path
        if combined == root:
            continue
        # we doesn't want to flatten the paths to one big module, so just use one combined
        for mod_info in pkgutil.iter_modules([combined], prefix=f"{'.'.join(path.parts)}."):
            if not mod_info.ispkg or path / mod_info.name.rsplit(".", 1)[-1] in valid_paths:
                yield mod_info


def _save_prefixes(originals: dict[str, ModuleType], prefix: str) -> None:
    """Save original ModuleTypes for restoring."""
    prefix_dot = f"{prefix}."
    for k in list(sys.modules.keys()):
        if k == prefix or k.startswith(prefix_dot):
            in_originals = k in originals
            if not in_originals:
                originals[k] = sys.modules.pop(k)


def _restore_modules(
    originals: dict[str, ModuleType], prefixes: set[str], amount_prefix_parts_plus_one: int
) -> None:
    """Undo changes below prefixes."""
    for k in list(sys.modules.keys()):
        splitted = k.split(".")
        if len(splitted) < amount_prefix_parts_plus_one:
            continue
        if ".".join(splitted[:amount_prefix_parts_plus_one]) not in prefixes:
            continue
        if k in originals:
            sys.modules[k] = originals[k]
        else:
            sys.modules.pop(k, None)


def _find_directives_from_path(
    path: os.PathLike,
    *,
    root: RootPath | None = None,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, RelativePath], Callable | None],
    ignore1: Container[str],
    ignore2: Container[str] = frozenset(),
    use_files: bool | None,
    global_prefix: str = "",
    cleanup_imports: bool,
) -> dict[str, DirectiveTuple | None]:
    """Helper to extract directives."""
    directives: dict[str, DirectiveTuple | None] = {}
    # path maybe not resolvable
    used_path = Path(path)
    # if exists, bypass loading modules and glob directly
    if use_files is not False and used_path.exists():
        # to prevent duplicates, resolve
        used_path = used_path.resolve()
        # files and co are invalid targets, links are resolved now
        if not used_path.is_dir():
            return directives
        if root is None:
            root = cast("RootPath", used_path)
        iterable = _generate_file_based_mod_infos(used_path, root, patterns)
    elif use_files:
        # empty
        return directives
    else:
        # maybe not resolvable, so just use absolute
        used_path = used_path.absolute()
        iterable = pkgutil.walk_packages([path], prefix=global_prefix)
    if root is None:
        root = cast("RootPath", used_path)

    original_modules: dict[str, ModuleType] = {}
    restore_prefixes: set[str] = set()
    amount_prefix_parts_plus_one: int | None = None
    try:
        for finder, name, ispkg in iterable:
            module = None
            # skip internal modules
            if name.rsplit(".", 1)[-1].startswith("_"):
                continue
            spec = finder.find_spec(name, None)
            full_name_str = spec.origin
            relative = cast("RelativePath", Path(full_name_str).relative_to(root))
            count_parts: int | None = None
            if amount_prefix_parts_plus_one is None:
                amount_prefix_parts_plus_one = len(relative.parts)
                if ispkg:
                    # packages have an injected /__init__.py
                    amount_prefix_parts_plus_one -= 1
                count_parts = amount_prefix_parts_plus_one
            if ispkg:
                module = importlib.util.module_from_spec(spec)
                if count_parts is None:
                    count_parts = len(relative.parts)
                    if ispkg:
                        # packages have an injected /__init__.py
                        count_parts -= 1
                if (
                    cleanup_imports
                    and count_parts == amount_prefix_parts_plus_one
                    and name not in restore_prefixes
                ):
                    restore_prefixes.add(name)
                    _save_prefixes(original_modules, name)
                sys.modules[name] = module
                if spec.loader is not None:
                    spec.loader.exec_module(module)
            absolute_path_str = str(root / relative)
            if (
                absolute_path_str in directives
                or absolute_path_str in ignore1
                or absolute_path_str in ignore2
            ):
                continue
            if not any(_match_path_against_glob(relative, pattern) for pattern in patterns):
                continue
            if module is None:
                module = importlib.util.module_from_spec(spec)
                if spec.loader is not None:
                    spec.loader.exec_module(module)
            directive_obj = extractor_directive(module, relative)
            directives[absolute_path_str] = (
                None
                if directive_obj is None
                else DirectiveTuple(module, root, relative, directive_obj)
            )
    finally:
        if cleanup_imports and amount_prefix_parts_plus_one is not None:
            _restore_modules(original_modules, restore_prefixes, amount_prefix_parts_plus_one)
    return directives


def find_directives_from_path(
    path: os.PathLike,
    *,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, RelativePath], DirectiveType | None],
    ignore: Container[str] = frozenset(),
    use_files: bool | None = None,
    cleanup_imports: bool = True,
) -> dict[str, DirectiveTuple | None]:
    """
    Extract directives from a path (which may exists virtually).

    Args:
        path (os.PathLike): Path to scan for directives.

    Kwargs:
        patterns (Collection[str]): Glob pattern to match.
        extractor_directive (Callable[[ModuleType, RelativePath], Callable | None]):
            Extractor for directives. Return Callable on success, `None` if no directive could be extracted.
        ignore (Optional[Container[str]]):
            Ignore additional full paths in string form for the extraction of directives.
            Can be any container like a not transposed directive dict.
        use_files (bool | None): Force file based retrieval/module based retrieval of directives. `None` (default) for auto-selection.
        cleanup_imports (bool):
            Cleanup imported helper packages after finishing imports. This may will prevent some lazy-loads but prevent collisions
            on colliding virtual paths. By default `True`.
    Returns:
        Dict mapping from file names to DirectiveTuple or `None` (no directive found).
    """
    return _find_directives_from_path(
        path,
        patterns=patterns,
        extractor_directive=extractor_directive,
        ignore1=ignore,
        use_files=use_files,
        cleanup_imports=cleanup_imports,
    )


def find_directives_from_module(
    module: str | ModuleType,
    *,
    patterns: Collection[str],
    extractor_directive: Callable[[ModuleType, RelativePath], DirectiveType | None],
    ignore: Container[str] = frozenset(),
) -> dict[str, DirectiveTuple | None]:
    """
    Extract directives from a module or package.

    Args:
        module (str | ModuleType): String to module or the imported module. A package is also a module.

    Kwargs:
        patterns (Collection[str]): Glob pattern to match.
        extractor_directive (Callable[[ModuleType, RelativePath], Callable | None]):
            Extractor for directives. Return Callable on success, `None` if no directive could be extracted.
        ignore (Optional[Container[str]]):
            Ignore additional full paths in string form for the extraction of directives.
            Can be any container like a not transposed directive dict.
    Returns:
        Dict mapping from file names to DirectiveTuple or `None` (no directive found).
    """
    directives: dict[str, DirectiveTuple | None] = {}
    if isinstance(module, str):
        module = importlib.import_module(module)
    root = cast(
        "RootPath",
        (
            Path(module.__spec__.origin).parent
            if module.__spec__.origin
            else Path(module.__name__.replace(".", os.sep))
        ).absolute(),
    )
    for path in module.__path__:
        directives.update(
            # here we have a different root as well as a prefix
            # a file based resolution is also not possible
            _find_directives_from_path(
                path,
                root=root,
                patterns=patterns,
                extractor_directive=extractor_directive,
                ignore1=ignore,
                ignore2=directives,
                use_files=False,
                # inject the correct prefix
                global_prefix=f"{module.__name__}.",
                # no need to do so (we can't have collisions). Will also provide some speed benefit
                cleanup_imports=False,
            )
        )
    return directives


def is_safe_key(key: tuple[str, str] | tuple[str], /) -> bool:
    """
    Safety check for `directive_function_or_help`.

    Return False, if key contains unsound characters.
    """
    return all(k.isidentifier() for k in key)


def transpose_directives(
    directives: dict[str, DirectiveTuple | None],
    *,
    extractor_help: Callable[[DirectiveTuple], None | str] = lambda tup: (
        tup.directive.__doc__ or ""
    ),
    extractor_app_name: Callable[[DirectiveTuple], str] | None = None,
) -> dict[tuple[str, str] | tuple[str], tuple[str | None, DirectiveType] | None]:
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
                return (
                    directive_tuple.relative.parts[0]
                    if len(directive_tuple.relative.parts) > 2
                    else directive_tuple.root.name
                )
            else:
                return (
                    directive_tuple.relative.parts[0]
                    if len(directive_tuple.relative.parts) > 1
                    else directive_tuple.root.name
                )

    directives_by_app_and_name: dict[
        tuple[str, str] | tuple[str], tuple[str | None, DirectiveType] | None
    ] = {}
    for directive_tuple in directives.values():
        if directive_tuple is not None:
            directive_tuple = DirectiveTuple(*directive_tuple)
            name = (
                directive_tuple.relative.parent.name
                if directive_tuple.relative.stem == "__init__"
                else directive_tuple.relative.stem
            )
            assert "." not in name, f"Name should not contain `.`: `{name}`"
            app_name = extractor_app_name(directive_tuple)
            name_tup = (name,)
            app_name_tup = (app_name, name)
            if not is_safe_key(app_name_tup):
                continue
            if app_name_tup in directives_by_app_and_name:
                # collision, no recover
                directives_by_app_and_name[app_name_tup] = None
                directives_by_app_and_name[name_tup] = None
                continue
            elif name_tup in directives_by_app_and_name:
                # recoverable
                directives_by_app_and_name[name_tup] = None
            extracted_help = extractor_help(directive_tuple)
            final_tup = (extracted_help, directive_tuple.directive)
            directives_by_app_and_name.setdefault(app_name_tup, final_tup)
            directives_by_app_and_name.setdefault(name_tup, final_tup)
    return directives_by_app_and_name


def directive_function_or_help(
    transposed: Mapping[tuple[str, str] | tuple[str], tuple[str | None, DirectiveType] | None],
    /,
    *,
    directive: str | None,
    help_text_preamble: str = "Available directives:",
) -> DirectiveType | None:
    """
    Helper for retrieving the directive, displaying a proper error or help in case of no directive or errornous command.

    Args:
        transposed (dict[tuple[str, str] | tuple[str], tuple[str | None, Callable] | None]):
            Contains the name, app_name.name mappings of the directives to help and actual callables
    Kwargs:
        directive (str | None): If empty or `None` display the found directives. Otherwise try to resolve
        help_text_preamble: (str):
            Preamble to echo when outputing help. Defaults to "Available directives:".
    Raises:
        SysExit(1): For errors (wrong or ambigous provided directive, colliding directives).
    """
    transposed = {k: v for k, v in transposed.items() if is_safe_key(k)}
    collisions = tuple(k for k, v in transposed.items() if len(k) == 2 and v is None)
    if collisions:
        error("Following directives have collisions:")
        for collision in collisions:
            echo(f"  [red]{collision[0]}.{collision[1]}[/]")
        sys.exit(1)
    if not directive:
        if help_text_preamble:
            echo(help_text_preamble)
        last_app = None
        for [app_name, name], [help_text, _] in sorted(
            (item for item in transposed.items() if len(item[0]) == 2 and item[1] is not None),
            key=lambda item: item[0],
        ):
            if help_text is None:
                continue
            if last_app != app_name:
                echo(f"\n[bold green]\\[{app_name}][/]")
            echo(f"  [bold blue]{name}[/]:")
            if help_text:
                echo(Padding(help_text, (0, 0, 0, 4), expand=False))
            last_app = app_name
        return None
    else:
        search_tuple = tuple(directive.rsplit(".", 1))
        if not is_safe_key(search_tuple):
            error(f"Specified directive: `{escape(directive)}` not valid as directive.")
            sys.exit(1)
        if search_tuple not in transposed:
            error(f"Specified directive: `{directive}` not found.")
            if len(search_tuple) == 2:
                matches = get_close_matches(
                    directive, (".".join(k) for k in transposed if len(k) == 2)
                )
            else:
                matches = get_close_matches(directive, (k[0] for k in transposed if len(k) == 1))
            if matches:
                echo(f"[red]Did you mean `{matches[0]}`[/]?")
            sys.exit(1)
        # collisions only happen if len(search_tuple) == 1
        retrieved = transposed[search_tuple]
        if retrieved is None:
            error(
                f"Specified directive: `{directive}` could not be uniquely identified. Please provide also the app_name-part.\n"
                "Possible directives:"
            )
            for collision in (k for k in transposed if len(k) == 2 and k[1] == search_tuple[0]):
                echo(f"  [red]{collision[0]}.{collision[1]}[/]")
            sys.exit(1)
        return retrieved[1]
