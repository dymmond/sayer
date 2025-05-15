import inspect
from collections import defaultdict
from typing import Any, Callable

import click

from sayer.middleware import run_after, run_before
from sayer.ui import RichGroup

COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}
_ARG_OVERRIDES: dict[Callable, dict[str, tuple[str, dict]]] = defaultdict(dict)
_APPLIED_PARAMS: dict[Callable, set[str]] = defaultdict(set)


def command(func: Callable) -> click.Command:
    """Register a Sayer command from a typed function."""
    name = func.__name__.replace("_", "-")
    sig = inspect.signature(func)

    @click.command(name=name, help=func.__doc__ or "")
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

    wrapper._original_func = func  # Used for decorators to reference
    COMMANDS[name] = wrapper

    if hasattr(func, "__sayer_group__"):
        group = func.__sayer_group__
        group.add_command(wrapper)

    return wrapper


def option(param_name: str, **kwargs):
    def wrapper(func):
        if isinstance(func, click.Command):
            original_func = getattr(func, "_original_func", None)
            if original_func:
                _ARG_OVERRIDES[original_func][param_name] = ("opt", kwargs)
                _APPLIED_PARAMS[original_func].add(param_name)

            func = click.option(f"--{param_name.replace('_', '-')}", **kwargs)(func)

            applied = getattr(func, "_sayer_applied_params", set())
            applied.add(param_name)
            func._sayer_applied_params = applied
            return func

        _ARG_OVERRIDES[func][param_name] = ("opt", kwargs)
        _APPLIED_PARAMS[func].add(param_name)
        return func
    return wrapper


def argument(param_name: str, **kwargs):
    def wrapper(func):
        if isinstance(func, click.Command):
            original_func = getattr(func, "_original_func", None)
            if original_func:
                _ARG_OVERRIDES[original_func][param_name] = ("arg", kwargs)
                _APPLIED_PARAMS[original_func].add(param_name)

            func = click.argument(param_name, **kwargs)(func)

            applied = getattr(func, "_sayer_applied_params", set())
            applied.add(param_name)
            func._sayer_applied_params = applied
            return func

        _ARG_OVERRIDES[func][param_name] = ("arg", kwargs)
        _APPLIED_PARAMS[func].add(param_name)
        return func
    return wrapper


def group(name: str, group_cls: type[click.Group] | None = None) -> click.Group:
    if name not in _GROUPS:
        cls = group_cls or RichGroup
        _GROUPS[name] = cls(name=name)
    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    return _GROUPS


def bind_command(group: click.Group, func: Callable) -> Callable:
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command


def _convert(value: Any, to_type: type) -> Any:
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return to_type(value)
