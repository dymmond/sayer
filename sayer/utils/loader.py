import importlib
import pkgutil
from types import ModuleType


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
