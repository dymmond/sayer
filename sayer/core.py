import inspect
from collections import defaultdict
from typing import Any, Callable, Dict

import click

from sayer.middleware import run_after, run_before

COMMANDS: Dict[str, click.Command] = {}
_GROUPS: Dict[str, click.Group] = {}
_ARG_OVERRIDES = defaultdict(dict)


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

    overrides = _ARG_OVERRIDES.get(func, {})

    for param in reversed(sig.parameters.values()):
        param_name = param.name
        param_type = param.annotation if param.annotation != inspect._empty else str
        has_default = param.default != inspect._empty
        default = param.default if has_default else None

        # Manual override
        if param_name in overrides:
            mode, extra = overrides[param_name]
            if mode == "arg":
                wrapper = click.argument(param_name, type=param_type, **extra)(wrapper)
            elif mode == "opt":
                wrapper = click.option(
                    f"--{param_name.replace('_', '-')}",
                    type=param_type,
                    default=default,
                    show_default=has_default,
                    **extra,
                )(wrapper)
            continue

        # Auto mode
        if has_default:
            wrapper = click.option(
                f"--{param_name.replace('_', '-')}",
                default=default,
                required=False,
                show_default=True,
                type=param_type,
            )(wrapper)
        else:
            wrapper = click.argument(param_name, type=param_type)(wrapper)

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


def argument(param_name: str, **kwargs):
    def wrapper(func):
        _ARG_OVERRIDES[func][param_name] = ("arg", kwargs)
        return func

    return wrapper


def option(param_name: str, **kwargs):
    def wrapper(func):
        _ARG_OVERRIDES[func][param_name] = ("opt", kwargs)
        return func

    return wrapper


def get_groups() -> Dict[str, click.Group]:
    return _GROUPS


def bind_command(group: click.Group, func: Callable) -> Callable:
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command
