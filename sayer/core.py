import inspect
import os
from typing import Annotated, Any, Callable, get_args, get_origin

import click

from sayer.middleware import run_after, run_before
from sayer.params import Argument, Env, Option, Param
from sayer.ui import RichGroup

COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}


def _convert(value: Any, to_type: type) -> Any:
    """Convert CLI input string to the specified type."""
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return to_type(value)


def _should_use_option(meta: Param, default: Any) -> bool:
    """Determine if the parameter metadata implies this should be a Click option."""
    return (
        meta.envvar is not None
        or meta.prompt
        or meta.confirmation_prompt
        or meta.hide_input
        or meta.callback is not None
        or (meta.default is not ... and meta.default is not None)
    )


def _extract_command_help(signature: inspect.Signature, func: Callable) -> str:
    """Extract help text for a command from function docstring or parameter descriptions."""
    cmd_help = func.__doc__ or ""
    if not cmd_help:
        for param in signature.parameters.values():
            default = param.default
            if isinstance(default, Param) and default.help:
                return default.help
            anno = param.annotation
            if get_origin(anno) is Annotated:
                for a in get_args(anno)[1:]:
                    if isinstance(a, Param) and a.help:
                        return a.help
    return cmd_help


def _build_click_parameter(
    param: inspect.Parameter,
    raw_anno: Any,
    ptype: Any,
    meta: Param | Option | Argument | Env | None,
    help_text: str,
    wrapper: Callable,
) -> Callable:
    """Attach Click option/argument to wrapper based on type and metadata."""
    pname = param.name
    is_flag = ptype is bool
    has_func_default = param.default != inspect._empty
    param_default = param.default if has_func_default else None

    if isinstance(meta, Param) and get_origin(raw_anno) is Annotated:
        if _should_use_option(meta, param.default):
            meta = meta.as_option()

    has_meta_default = getattr(meta, "default", ...) is not ...
    default = getattr(meta, "default", param_default)
    required = getattr(meta, "required", not (has_func_default or has_meta_default))
    help_text = getattr(meta, "help", help_text) or getattr(meta, "description", help_text)

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
            required=False,
            show_default=True,
            help=help_text,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar,
        )(wrapper)

    else:
        if not has_func_default:
            wrapper = click.argument(pname, type=ptype)(wrapper)
        elif param.annotation is bool and isinstance(param.default, bool):
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                is_flag=True,
                default=param.default,
                required=False,
                help=help_text,
            )(wrapper)
        elif isinstance(param.default, Param):
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
                required=False,
                show_default=True,
                help=help_text,
            )(wrapper)
        else:
            wrapper = click.argument(pname, type=ptype, default=param.default, required=False)(wrapper)
            for p in wrapper.params:
                if p.name == pname:
                    p.required = False
                    p.default = param.default
                    break

    # Ensure help is present for rich rendering
    for p in wrapper.params:
        if p.name == pname and not getattr(p, "help", None):
            p.help = help_text

    return wrapper


def command(func: Callable) -> click.Command:
    """Register a function as a CLI command with Click, respecting rich parameter metadata."""
    name = func.__name__.replace("_", "-")
    sig = inspect.signature(func)
    cmd_help = _extract_command_help(sig, func)

    @click.command(name=name, help=cmd_help)
    @click.pass_context
    def wrapper(ctx: click.Context, **kwargs):
        bound = {}
        for p in sig.parameters.values():
            val = kwargs.get(p.name)
            if p.annotation != inspect._empty:
                val = _convert(val, p.annotation)
            bound[p.name] = val

        run_before(name, bound)
        result = func(**bound)
        if inspect.iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        run_after(name, bound, result)
        return result

    wrapper._original_func = func

    for param in sig.parameters.values():
        raw_anno = param.annotation if param.annotation != inspect._empty else str
        ptype = raw_anno
        meta = None
        help_text = ""

        if get_origin(raw_anno) is Annotated:
            args = get_args(raw_anno)
            ptype = args[0]
            for a in args[1:]:
                if isinstance(a, (Option, Argument, Env, Param)):
                    meta = a
                elif isinstance(a, str):
                    help_text = a

        if isinstance(param.default, Param) and not meta:
            meta = param.default

        wrapper = _build_click_parameter(param, raw_anno, ptype, meta, help_text, wrapper)

    COMMANDS[name] = wrapper
    if hasattr(func, "__sayer_group__"):
        func.__sayer_group__.add_command(wrapper)
    return wrapper


def group(name: str, group_cls: type[click.Group] | None = None) -> click.Group:
    """Register or return an existing Click group by name."""
    if name not in _GROUPS:
        cls = group_cls or RichGroup
        _GROUPS[name] = cls(name=name)
    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    """Return all registered commands."""
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    """Return all registered groups."""
    return _GROUPS


def bind_command(group: click.Group, func: Callable) -> click.Command:
    """Bind a command function to a given Click group."""
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command
