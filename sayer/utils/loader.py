import importlib
import importlib.util
import os
import pkgutil
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any


def load_commands_from(module_path: str) -> None:
    """
    Recursively imports and reloads all Python modules within a given package
    or directly imports a single module.

    This function is designed to discover and register Sayer commands and groups.
    It leverages Python's import system to find modules. If a module is a package
    (i.e., has a `__path__` attribute), it recursively walks through all its
    submodules and imports them. If it's a regular module, it simply imports
    or reloads it. Commands and groups decorated with `@command` or `@group.command`
    are expected to self-register upon import.

    Args:
        module_path: The full dotted path to the module or package (e.g.,
                     "my_app.commands" or "my_app.commands.cli").
    """
    # Import the specified module or package.
    module: ModuleType = importlib.import_module(module_path)

    # Check if the imported module is a package (i.e., has a __path__ attribute).
    if hasattr(module, "__path__"):  # it's a package
        # If it's a package, recursively walk through all its submodules.
        for _, name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
            # Import each submodule found. This triggers the execution of
            # module-level code, which includes command registration.
            importlib.import_module(name)
    else:
        # If it's a single module, reload it. This ensures that if the module
        # was already imported (e.g., during development), its command
        # definitions are refreshed.
        importlib.reload(module)


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
