import inspect
from typing import Any, Callable, Sequence

# Global registry for named middleware sets.
# Stores middleware functions categorized into 'before' and 'after' lists
# for easy retrieval by a given name.
_MIDDLEWARE_REGISTRY: dict[str, dict[str, list[Callable[..., Any]]]] = {}

# Global lists for always-run middleware hooks.
# These hooks are executed for every command, regardless of specific middleware settings.
_GLOBAL_BEFORE: list[Callable[[str, dict[str, Any]], Any]] = []
_GLOBAL_AFTER: list[Callable[[str, dict[str, Any], Any], Any]] = []


def register(
    name: str,
    *,
    before: Sequence[Callable[[str, dict[str, Any]], Any]] = (),
    after: Sequence[Callable[[str, dict[str, Any], Any], Any]] = (),
) -> None:
    """
    Registers a named set of middleware functions.

    This function allows you to group 'before' and 'after' middleware functions
    under a specific `name`. These named sets can then be referenced easily
    when defining commands or command groups.

    Args:
        name: The unique identifier for this middleware set.
        before: An optional sequence of callable functions to be executed
                *before* a command runs. Each function must accept the command name
                (str) and a dictionary of bound arguments (dict[str, Any]).
        after: An optional sequence of callable functions to be executed
               *after* a command runs. Each function must accept the command name
               (str), a dictionary of bound arguments (dict[str, Any]), and the
               result of the command execution (Any).
    """
    _MIDDLEWARE_REGISTRY[name] = {"before": list(before), "after": list(after)}


def resolve(
    middleware: Sequence[str | Callable[..., Any]],
) -> tuple[list[Callable[[str, dict[str, Any]], Any]], list[Callable[[str, dict[str, Any], Any], Any]]]:
    """
    Resolves a sequence of middleware identifiers into separate 'before' and 'after' hook lists.

    This function processes a mix of middleware names (strings) and direct callable
    middleware functions. It looks up named middleware sets in the global registry
    and classifies direct callables based on their parameter count (2 parameters for
    'before' hooks, 3 for 'after' hooks).

    Args:
        middleware: A sequence containing either strings (representing registered
                    middleware names) or callable functions to be used as middleware.

    Returns:
        A tuple containing two lists:
        - The first list (`before_hooks`) contains all resolved 'before' middleware callables.
        - The second list (`after_hooks`) contains all resolved 'after' middleware callables.

    Raises:
        ValueError: If a callable middleware function does not accept 2 or 3 parameters,
                    which are the required signatures for 'before' and 'after' hooks, respectively.
    """
    before_hooks: list[Callable[[str, dict[str, Any]], Any]] = []
    after_hooks: list[Callable[[str, dict[str, Any], Any], Any]] = []

    # Iterate through each item provided in the middleware sequence.
    for item in middleware:
        if isinstance(item, str):
            # If the item is a string, look it up in the global registry.
            hooks = _MIDDLEWARE_REGISTRY.get(item)
            if hooks:
                # Extend the 'before' and 'after' hook lists with functions from the named set.
                before_hooks.extend(hooks.get("before", []))
                after_hooks.extend(hooks.get("after", []))
        elif callable(item):
            # If the item is a callable, inspect its signature to determine if it's a 'before' or 'after' hook.
            sig = inspect.signature(item)
            param_count = len(sig.parameters)
            if param_count == 2:
                # A callable with 2 parameters is treated as a 'before' hook.
                before_hooks.append(item)
            elif param_count == 3:
                # A callable with 3 parameters is treated as an 'after' hook.
                after_hooks.append(item)
            else:
                # Raise an error if the callable has an unsupported number of parameters.
                raise ValueError(
                    f"Middleware callable '{item.__name__}' must accept 2 (before) or 3 (after) "
                    f"parameters, got {param_count}"
                )

    return before_hooks, after_hooks


def add_before_global(hook: Callable[[str, dict[str, Any]], Any]) -> None:
    """
    Adds a middleware hook to the global 'before' list.

    Functions added via this method will be executed *before* every command runs,
    regardless of whether specific middleware is assigned to that command.

    Args:
        hook: The callable function to add. It must accept the command name (str)
              and a dictionary of bound arguments (dict[str, Any]).
    """
    _GLOBAL_BEFORE.append(hook)


def add_after_global(hook: Callable[[str, dict[str, Any], Any], Any]) -> None:
    """
    Adds a middleware hook to the global 'after' list.

    Functions added via this method will be executed *after* every command runs,
    regardless of whether specific middleware is assigned to that command.

    Args:
        hook: The callable function to add. It must accept the command name (str),
              a dictionary of bound arguments (dict[str, Any]), and the result
              of the command execution (Any).
    """
    _GLOBAL_AFTER.append(hook)


def run_before(cmd_name: str, args: dict[str, Any]) -> None:
    """
    Executes all registered global 'before' middleware hooks.

    This function iterates through the `_GLOBAL_BEFORE` list and calls each
    hook with the provided command name and arguments.

    Args:
        cmd_name: The name of the command that is about to be executed.
        args: A dictionary containing the arguments bound to the command's
              parameters.
    """
    for hook in _GLOBAL_BEFORE:
        hook(cmd_name, args)


def run_after(cmd_name: str, args: dict[str, Any], result: Any) -> None:
    """
    Executes all registered global 'after' middleware hooks.

    This function iterates through the `_GLOBAL_AFTER` list and calls each
    hook with the command name, arguments, and the result of the command's
    execution.

    Args:
        cmd_name: The name of the command that has just been executed.
        args: A dictionary containing the arguments that were bound to the
              command's parameters.
        result: The value returned by the command function after its execution.
    """
    for hook in _GLOBAL_AFTER:
        hook(cmd_name, args, result)
