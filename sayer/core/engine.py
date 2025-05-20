import inspect
import os
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Callable, Sequence, TypeVar, get_args, get_origin, overload
from uuid import UUID

import anyio
import click

from sayer.middleware import resolve as resolve_middleware, run_after, run_before
from sayer.params import Argument, Env, Option, Param
from sayer.utils.ui import RichGroup

# Define a type variable for the function being wrapped
F = TypeVar("F", bound=Callable[..., Any])

# Global dictionaries to store registered commands and groups
COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}

# Map Python primitives and common types to Click ParamTypes
_PRIMITIVE_MAP = {
    str: click.STRING,
    int: click.INT,
    float: click.FLOAT,
    bool: click.BOOL,
    UUID: click.UUID,
    date: click.DateTime(formats=["%Y-%m-%d"]),
    datetime: click.DateTime(),
}


def _convert(value: Any, to_type: type) -> Any:
    """
    Converts a value, typically from a CLI input string, to the specified Python type.
    Handles boolean conversion specifically for common string representations.
    """
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return to_type(value)


def _should_use_option(meta: Param, default: Any) -> bool:
    """
    Determines if a parameter with generic `Param` metadata should be treated as a Click option.
    """
    return (
        meta.envvar is not None
        or meta.prompt
        or meta.confirmation_prompt
        or meta.hide_input
        or meta.callback is not None
        or (meta.default is not ... and meta.default is not None)
    )


def _extract_command_help(signature: inspect.Signature, func: Callable) -> str:
    """
    Extracts the help text for a command.
    """
    cmd_help = inspect.getdoc(func) or ""
    if not cmd_help:
        for param in signature.parameters.values():
            if isinstance(param.default, Param) and param.default.help:
                return param.default.help
            anno = param.annotation
            if get_origin(anno) is Annotated:
                for arg in get_args(anno)[1:]:
                    if isinstance(arg, Param) and arg.help:
                        return arg.help
    return cmd_help


def _build_click_parameter(
    param: inspect.Parameter,
    raw_anno: Any,
    ptype: type,
    meta: Param | Option | Argument | Env | None,
    help_text: str,
    wrapper: Callable,
) -> Callable:
    """
    Builds and attaches a Click parameter (option or argument) to a Click command wrapper.
    """
    pname = param.name

    # Determine if the parameter is a boolean flag
    is_flag = ptype is bool
    # Check if the function signature provides a default value
    has_func_default = param.default is not inspect._empty
    param_default = param.default if has_func_default else None

    # If generic Param metadata is used with Annotated, convert to Option
    if isinstance(meta, Param) and get_origin(raw_anno) is Annotated:
        if _should_use_option(meta, param_default):
            meta = meta.as_option()

    # Advanced type support: Enum and Path
    # 1) enum.Enum → click.Choice([...])
    if isinstance(ptype, type) and issubclass(ptype, Enum):
        choices = [member.value for member in ptype]
        ptype = click.Choice(choices)

    # 2) pathlib.Path → click.Path
    if ptype is Path:
        ptype = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)

    # Determine final default and required
    has_meta_default = getattr(meta, "default", ...) is not ...
    default = getattr(meta, "default", param_default)
    required = getattr(meta, "required", not (has_func_default or has_meta_default))
    help_text = getattr(meta, "help", help_text) or help_text

    if isinstance(meta, Argument):
        wrapper = click.argument(pname, type=ptype, required=required, default=default)(wrapper)

    elif isinstance(meta, Env):
        env_default = os.getenv(meta.envvar, meta.default)
        wrapper = click.option(
            f"--{pname.replace('_','-')}",
            type=ptype,
            default=env_default,
            show_default=True,
            required=meta.required,
            help=f"[env:{meta.envvar}] {help_text}",
        )(wrapper)

    elif isinstance(meta, Option):
        wrapper = click.option(
            f"--{pname.replace('_','-')}",
            type=None if is_flag else ptype,
            is_flag=is_flag,
            default=default,
            required=required,
            show_default=True,
            help=help_text,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar,
        )(wrapper)

    else:
        # Fallback for parameters without explicit metadata
        if not has_func_default:
            wrapper = click.argument(pname, type=ptype, required=True)(wrapper)
        elif is_flag and isinstance(param.default, bool):
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                is_flag=True,
                default=param.default,
                help=help_text,
            )(wrapper)
        elif isinstance(param.default, Param):
            # Parameter uses a Param instance as default
            wrapper = click.argument(
                pname,
                type=ptype,
                required=False,
                default=param.default.default,
            )(wrapper)
        elif param.default is None:
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                type=ptype,
                default=None,
                show_default=True,
                help=help_text,
            )(wrapper)
        else:
            wrapper = click.argument(
                pname,
                type=ptype,
                default=param.default,
                required=False,
            )(wrapper)
            for p in wrapper.params:
                if p.name == pname:
                    p.required = False
                    p.default = param.default
                    break

    # Ensure help text is attached
    for p in wrapper.params:
        if p.name == pname and not getattr(p, "help", None):
            p.help = help_text

    return wrapper


@overload
def command(func: F) -> click.Command: ...


@overload
def command(
    func: F | None = None, *, middleware: Sequence[str | Callable[..., Any]] = ()
) -> click.Command | Callable[[F], click.Command]: ...


def command(
    func: F | None = None, *, middleware: Sequence[str | Callable[..., Any]] = ()
) -> click.Command | Callable[[F], click.Command]:
    """
    Registers a function as a CLI command using Click, respecting `sayer` parameter metadata
    and allowing per-command middleware.
    """

    def decorator(fn: F) -> click.Command:
        name = fn.__name__.replace("_", "-")
        sig = inspect.signature(fn)
        cmd_help = _extract_command_help(sig, fn)

        # Resolve middleware hooks
        before_hooks, after_hooks = resolve_middleware(middleware)

        @click.command(name=name, help=cmd_help)
        @click.pass_context
        def wrapper(ctx: click.Context, **kwargs: Any):
            bound_args: dict[str, Any] = {}
            for p in sig.parameters.values():
                val = kwargs.get(p.name)
                if p.annotation is not inspect._empty:
                    val = _convert(val, p.annotation)
                bound_args[p.name] = val

            run_before(name, bound_args)
            for hook in before_hooks:
                hook(name, bound_args)

            result = fn(**bound_args)
            if inspect.iscoroutine(result):
                result = anyio.run(lambda: result)

            run_after(name, bound_args, result)
            for hook in after_hooks:
                hook(name, bound_args, result)

            return result

        wrapper._original_func = fn  # type: ignore

        current = wrapper
        for param in sig.parameters.values():
            raw_anno = param.annotation if param.annotation is not inspect._empty else str
            ptype = raw_anno if get_origin(raw_anno) is not Annotated else get_args(raw_anno)[0]

            meta: Param | Option | Argument | Env | None = None
            help_text = ""
            if get_origin(raw_anno) is Annotated:
                for a in get_args(raw_anno)[1:]:
                    if isinstance(a, (Option, Argument, Env, Param)):
                        meta = a
                    elif isinstance(a, str):
                        help_text = a
            if isinstance(param.default, Param) and not meta:
                meta = param.default

            current = _build_click_parameter(param, raw_anno, ptype, meta, help_text, current)

        # Register command
        if hasattr(fn, "__sayer_group__"):
            fn.__sayer_group__.add_command(current)
        else:
            COMMANDS[name] = current

        return current

    return decorator if func is None else decorator(func)


def group(name: str, group_cls: type[click.Group] | None = None, help: str | None = None) -> click.Group:
    """
    Registers or retrieves a Click group by name.
    """
    if name not in _GROUPS:
        cls = group_cls or RichGroup
        _GROUPS[name] = cls(name=name, help=help)
    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    return _GROUPS


def bind_command(group: click.Group, func: F) -> click.Command:
    func.__sayer_group__ = group  # type: ignore
    return command(func)


# Monkey-patch Click Group to support binding
click.Group.command = bind_command  # type: ignore
