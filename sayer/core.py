import inspect
from collections import defaultdict
from typing import Annotated, Any, Callable, get_args, get_origin

import click

from sayer.middleware import run_after, run_before
from sayer.params import Param
from sayer.ui import RichGroup

COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}
_ARG_OVERRIDES = defaultdict(dict)


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

    overrides = _ARG_OVERRIDES.get(func, {})

    for param in reversed(sig.parameters.values()):
        param_name = param.name
        raw_annotation = param.annotation if param.annotation != inspect._empty else str

        param_type = raw_annotation
        meta: Param | None = None
        description = ""

        # Handle Annotated[T, ...] with Param(...) and string description
        if get_origin(raw_annotation) is Annotated:
            args = get_args(raw_annotation)
            param_type = args[0]
            for arg in args[1:]:
                if isinstance(arg, Param):
                    meta = arg
                elif isinstance(arg, str):
                    description = arg

        # Fallback: use Param(...) as default
        if not meta:
            is_param_wrapper = isinstance(param.default, Param)
            meta = param.default if is_param_wrapper else None

        # Extract metadata
        if meta:
            has_default = meta.default is not ...
            default = meta.default if has_default else None
            required = meta.explicit_required if meta.explicit_required is not None else not has_default
            description = meta.description or description
        else:
            has_default = param.default != inspect._empty
            default = param.default if has_default else None
            required = not has_default
            description = description or ""

        # Manual override (argument/option decorators)
        if param_name in overrides:
            mode, extra = overrides[param_name]
            if mode == "arg":
                wrapper = click.argument(param_name, type=param_type, **extra)(wrapper)
            elif mode == "opt":
                wrapper = click.option(
                    f"--{param_name.replace('_', '-')}",
                    type=param_type,
                    default=default,
                    required=required,
                    show_default=has_default,
                    help=description,
                    **extra,
                )(wrapper)
            continue

        # Auto wrapping: argument or option
        if required:
            wrapper = click.argument(param_name, type=param_type)(wrapper)
            for p in wrapper.params:
                if p.name == param_name:
                    if description:
                        p.description = description
                    if default is not None:
                        p.default = default
        else:
            wrapper = click.option(
                f"--{param_name.replace('_', '-')}",
                default=default,
                required=False,
                show_default=True,
                type=param_type,
                help=description,
            )(wrapper)
            for p in wrapper.params:
                if p.name == param_name:
                    p.default = default

    COMMANDS[name] = wrapper

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


def get_commands() -> dict[str, click.Command]:
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    return _GROUPS


def group(name: str, group_cls: type[click.Group] | None = None) -> click.Group:
    if name not in _GROUPS:
        cls = group_cls or RichGroup
        _GROUPS[name] = cls(name=name)
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


def bind_command(group: click.Group, func: Callable) -> Callable:
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command
