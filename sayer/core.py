import inspect
from collections import defaultdict
from typing import Annotated, Any, Callable, dict, get_args, get_origin

import click

from sayer.middleware import run_after, run_before
from sayer.params import Param  # ✅ new

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

        # ✅ Handle Annotated[T, ...] with multiple metadata entries
        if get_origin(raw_annotation) is Annotated:
            args = get_args(raw_annotation)
            param_type = args[0]
            for arg in args[1:]:
                if isinstance(arg, Param):
                    meta = arg
                    break

        # ✅ Or fall back to Param() passed as default
        if not meta:
            is_param_wrapper = isinstance(param.default, Param)
            meta = param.default if is_param_wrapper else None

        # ✅ Resolve metadata fields
        if meta:
            has_default = meta.default is not ...
            default = meta.default if has_default else None
            required = meta.explicit_required if meta.explicit_required is not None else not has_default
            description = meta.description
        else:
            has_default = param.default != inspect._empty
            default = param.default if has_default else None
            required = not has_default
            description = ""

        # ✅ Manual override takes precedence
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

        # ✅ Auto wrapping: arguments vs options
        if required:
            arg = click.argument(param_name, type=param_type)
            wrapper = arg(wrapper)

            # Inject description manually (Click doesn't support help= on argument)
            if description:
                for p in wrapper.params:
                    if p.name == param_name:
                        p.description = description
        else:
            wrapper = click.option(
                f"--{param_name.replace('_', '-')}",
                default=default,
                required=False,
                show_default=True,
                type=param_type,
                help=description,
            )(wrapper)

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

def group(name: str) -> click.Group:
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

def bind_command(group: click.Group, func: Callable) -> Callable:
    func.__sayer_group__ = group
    return command(func)

click.Group.command = bind_command
