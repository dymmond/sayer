import importlib.metadata

from sayer.utils.ui import error


def load_plugins() -> None:
    """
    Loads and registers Sayer commands from installed plugins.

    This function iterates through entry points defined under the 'sayer.commands'
    group in the installed Python packages. For each entry point, it attempts
    to load the specified function and execute it. These functions are expected
    to register commands with the Sayer application.

    If a plugin fails to load or its registration function raises an exception,
    an error message is logged with details about the failed plugin.
    """
    for entry_point in importlib.metadata.entry_points().get("sayer.commands", []):
        try:
            register_func = entry_point.load()
            register_func()
        except Exception as e:
            error(f"[Plugin Load Failed] {entry_point.name}: {e}")
