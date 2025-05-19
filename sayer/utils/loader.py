import importlib
import pkgutil


def load_commands_from(module_path: str):
    """
    Recursively imports all modules under the given package/module path.
    Any module with @command or @group.command will auto-register.
    """
    module = importlib.import_module(module_path)

    if hasattr(module, "__path__"):  # it's a package
        for _, name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
            importlib.import_module(name)
    else:
        importlib.reload(module)
