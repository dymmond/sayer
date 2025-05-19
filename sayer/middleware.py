import inspect
from typing import Callable, Any, Sequence

# Global registry for named middleware sets
_MIDDLEWARE_REGISTRY: dict[str, dict[str, list[Callable]]] = {}

# Global lists for always-run middleware hooks
_GLOBAL_BEFORE: list[Callable[[str, dict[str, Any]], Any]] = []
_GLOBAL_AFTER: list[Callable[[str, dict[str, Any], Any], Any]] = []


def register(
    name: str,
    *,
    before: Sequence[Callable[[str, dict[str, Any]], Any]] = (),
    after: Sequence[Callable[[str, dict[str, Any], Any], Any]] = (),
) -> None:
    """
    Register a named middleware set.

    Args:
        name: The key under which to register this set.
        before: A sequence of callables to run before the command.
        after: A sequence of callables to run after the command.
    """
    _MIDDLEWARE_REGISTRY[name] = {"before": list(before), "after": list(after)}


def resolve(
    middleware: Sequence[str | Callable[..., Any]],
) -> tuple[
    list[Callable[[str, dict[str, Any]], Any]], list[Callable[[str, dict[str, Any], Any], Any]]
]:
    """
    Resolve a list of middleware identifiers (names or callables) into two lists:
    (before_hooks, after_hooks).

    Strings are looked up in the named registry; callables are classified by signature.

    Args:
        middleware: A sequence of middleware names or callables.

    Returns:
        A tuple of (before_hooks, after_hooks).
    """
    before_hooks: list[Callable[[str, dict[str, Any]], Any]] = []
    after_hooks: list[Callable[[str, dict[str, Any], Any], Any]] = []

    for item in middleware:
        if isinstance(item, str):
            hooks = _MIDDLEWARE_REGISTRY.get(item)
            if hooks:
                before_hooks.extend(hooks.get("before", []))
                after_hooks.extend(hooks.get("after", []))
        elif callable(item):
            # Classify callables: 2 args => before, 3 args => after
            sig = inspect.signature(item)
            param_count = len(sig.parameters)
            if param_count == 2:
                before_hooks.append(item)
            elif param_count == 3:
                after_hooks.append(item)
            else:
                raise ValueError(
                    f"Middleware callable '{item.__name__}' must accept 2 (before) or 3 (after) parameters, got {param_count}"
                )

    return before_hooks, after_hooks


def add_before_global(hook: Callable[[str, dict[str, Any]], Any]) -> None:
    """
    Add a global 'before' middleware hook that runs on every command.
    """
    _GLOBAL_BEFORE.append(hook)


def add_after_global(hook: Callable[[str, dict[str, Any], Any], Any]) -> None:
    """
    Add a global 'after' middleware hook that runs on every command.
    """
    _GLOBAL_AFTER.append(hook)


def run_before(cmd_name: str, args: dict[str, Any]) -> None:
    """
    Execute all registered global 'before' middleware hooks.

    Args:
        cmd_name: Name of the command being executed.
        args: Dictionary of bound arguments for the command.
    """
    for hook in _GLOBAL_BEFORE:
        hook(cmd_name, args)


def run_after(cmd_name: str, args: dict[str, Any], result: Any) -> None:
    """
    Execute all registered global 'after' middleware hooks.

    Args:
        cmd_name: Name of the command that was executed.
        args: Dictionary of bound arguments for the command.
        result: The result returned by the command function.
    """
    for hook in _GLOBAL_AFTER:
        hook(cmd_name, args, result)
