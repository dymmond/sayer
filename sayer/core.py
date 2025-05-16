import inspect
from typing import Annotated, Any, Callable, get_args, get_origin

import click

from sayer.middleware import run_after, run_before
from sayer.params import Param
from sayer.ui import RichGroup

COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}


def _extract_command_help(signature: inspect.Signature, func: Callable) -> str:
    cmd_help = func.__doc__ or ""
    if not cmd_help:
        # look for first Param description
        for param in signature.parameters.values():
            default = param.default
            if isinstance(default, Param) and default.description:
                cmd_help = default.description
                break
            anno = param.annotation
            if get_origin(anno) is Annotated:
                for a in get_args(anno)[1:]:
                    if isinstance(a, Param) and a.description:
                        cmd_help = a.description
                        break
                if cmd_help:
                    break
    return cmd_help


def command(func: Callable) -> click.Command:
    """Register a Sayer command from a typed function with Param/Annotated support."""
    name = func.__name__.replace("_", "-")
    sig = inspect.signature(func)

    # 0️⃣ Command-level help
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

    # 1️⃣ Apply parameters via type inference and Param()/Annotated
    for param in sig.parameters.values():
        pname = param.name
        raw_anno = param.annotation if param.annotation != inspect._empty else str
        ptype = raw_anno
        meta: Param | None = None
        help_text = ""

        # Handle Annotated[T, Param(...), 'doc']
        if get_origin(raw_anno) is Annotated:
            args = get_args(raw_anno)
            ptype = args[0]
            for a in args[1:]:
                if isinstance(a, Param):
                    meta = a
                elif isinstance(a, str):
                    help_text = a

        # Fallback if default is Param
        if not meta and isinstance(param.default, Param):
            meta = param.default

        # Determine default, required, description
        if meta:
            has_def = meta.default is not ...
            default = meta.default if has_def else None
            required = meta.explicit_required if meta.explicit_required is not None else not has_def
            if meta.description:
                help_text = meta.description
        else:
            has_def = param.default != inspect._empty
            default = param.default if has_def else None
            required = not has_def

        is_flag = ptype is bool

        if required:
            # positional argument
            wrapper = click.argument(pname, type=ptype)(wrapper)
            if help_text:
                for p in wrapper.params:
                    if p.name == pname:
                        p.description = help_text
        else:
            # ➡️ Distinguish between:
            #    * optional flag/option (for None or bool)
            #    * optional positional (for literal defaults)
            if default is None or is_flag:
                # option/flag form
                wrapper = click.option(
                    f"--{pname.replace('_','-')}",
                    type=None if is_flag else ptype,
                    is_flag=is_flag,
                    default=default,
                    required=False,
                    show_default=True,
                    help=help_text,
                )(wrapper)
            else:
                # optional positional with literal default
                wrapper = click.argument(
                    pname,
                    type=ptype,
                    required=False,
                    default=default,
                )(wrapper)
                # ⚙️ Patch the Argument so Click accepts two positionals
                for p in wrapper.params:
                    if p.name == pname:
                        p.required = False
                        p.default = default
                        if help_text:
                            p.description = help_text
                        break

    COMMANDS[name] = wrapper
    if hasattr(func, "__sayer_group__"):
        func.__sayer_group__.add_command(wrapper)
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


def bind_command(group: click.Group, func: Callable) -> click.Command:
    func.__sayer_group__ = group
    return command(func)


click.Group.command = bind_command


def _convert(value: Any, to_type: type) -> Any:
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return to_type(value)
