from typing import Any, Callable, Dict, List

_before_middlewares: List[Callable[[str, Dict[str, Any]], None]] = []
_after_middlewares: List[Callable[[str, Dict[str, Any], Any], None]] = []


def before_command(func: Callable[[str, Dict[str, Any]], None]) -> Callable:
    """
    Decorator to register a function as a 'before command' middleware.

    Registered functions will be executed before a command runs.
    They should accept the command name (str) and arguments (Dict[str, Any]).

    Args:
        func: The function to register as middleware.

    Returns:
        The registered function.
    """
    _before_middlewares.append(func)
    return func


def after_command(func: Callable[[str, Dict[str, Any], Any], None]) -> Callable:
    """
    Decorator to register a function as an 'after command' middleware.

    Registered functions will be executed after a command runs.
    They should accept the command name (str), arguments (Dict[str, Any]),
    and the command's result (Any).

    Args:
        func: The function to register as middleware.

    Returns:
        The registered function.
    """
    _after_middlewares.append(func)
    return func


def run_before(name: str, args: Dict[str, Any]) -> None:
    """
    Executes all registered 'before command' middlewares.

    Each registered middleware function is called with the given command
    name and arguments.

    Args:
        name: The name of the command being executed.
        args: A dictionary of the command's arguments.
    """
    for middleware in _before_middlewares:
        middleware(name, args)


def run_after(name: str, args: Dict[str, Any], result: Any) -> None:
    """
    Executes all registered 'after command' middlewares.

    Each registered middleware function is called with the given command
    name, arguments, and the command's result.

    Args:
        name: The name of the command that was executed.
        args: A dictionary of the command's arguments.
        result: The result returned by the command.
    """
    for middleware in _after_middlewares:
        middleware(name, args, result)
