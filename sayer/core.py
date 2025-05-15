import inspect
from typing import Any, Callable, Dict

import click

from sayer.middleware import run_after, run_before

COMMANDS: Dict[str, click.Command] = {}
_GROUPS: Dict[str, click.Group] = {}


def command(func: Callable) -> click.Command:
    """Register a Sayer command from a typed function."""
    name = func.__name__.replace("_", "-")
    sig = inspect.signature(func)

    @click.command(name=name)
    @click.pass_context
    def wrapper(ctx: click.Context, **kwargs):
        bound = {}
        for param in sig.parameters.values():
            val = kwargs.get(param.name)
            if param.annotation != inspect._empty:
                val = _convert(val, param.annotation)
            bound[param.name] = val

        run_before(name, bound)
        result = func(**bound)
        if inspect.iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        run_after(name, bound, result)
        return result

    for param in reversed(sig.parameters.values()):
        param_type = param.annotation if param.annotation != inspect._empty else str
        param_default = param.default if param.default != inspect._empty else None
        is_required = param.default == inspect._empty

        wrapper = click.option(
            f"--{param.name.replace('_', '-')}",
            required=is_required,
            default=None if is_required else param_default,
            type=param_type,
            show_default=not is_required,
        )(wrapper)

    # Global registration
    COMMANDS[name] = wrapper

    # Attach to group if decorated inside a group context
    if hasattr(func, "__sayer_group__"):
        group = func.__sayer_group__
        group.add_command(wrapper)

    return wrapper


def _convert(value: Any, to_type: type) -> Any:
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return to_type(value)


def get_commands() -> Dict[str, click.Command]:
    return COMMANDS


def group(name: str) -> click.Group:
    """Create or get a command group by name."""
    if name not in _GROUPS:
        _GROUPS[name] = click.Group(name=name)
    return _GROUPS[name]


def get_groups() -> Dict[str, click.Group]:
    return _GROUPS


# Allow: @group.command() to register Sayer-compatible functions
def bind_command(group: click.Group, func: Callable) -> Callable:
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command
