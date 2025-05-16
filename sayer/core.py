import inspect
from collections import defaultdict
from typing import Annotated, Any, Callable, get_args, get_origin

import click

from sayer.middleware import run_after, run_before
from sayer.params import Param
from sayer.ui import RichGroup

COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}
_ARG_OVERRIDES: dict[Callable, dict[str, tuple[str, dict]]] = defaultdict(dict)
_APPLIED_PARAMS: dict[Callable, set[str]] = defaultdict(set)


def command(func: Callable) -> click.Command:
    """Register a Sayer command from a typed function."""
    name = func.__name__.replace("_", "-")
    sig = inspect.signature(func)

    overrides = _ARG_OVERRIDES.get(func, {})
    applied = _APPLIED_PARAMS.get(func, set())

    param_decorators: list[tuple[str, str, Callable[..., click.Command], str]] = []

    for param in reversed(sig.parameters.values()):
        param_name = param.name

        # skip if user already applied @argument/@option
        if param_name in applied or param_name in overrides:
            continue

        # infer annotation and metadata
        raw_anno = param.annotation if param.annotation != inspect._empty else str
        param_type = raw_anno
        meta: Param | None = None
        description = ""

        # support Annotated[T, Param(...), "doc"]
        if get_origin(raw_anno) is Annotated:
            args = get_args(raw_anno)
            param_type = args[0]
            for a in args[1:]:
                if isinstance(a, Param):
                    meta = a
                elif isinstance(a, str):
                    description = a

        # fallback Param(...) as default
        if not meta and isinstance(param.default, Param):
            meta = param.default

        # extract Param metadata or fallback
        if meta:
            has_def = meta.default is not ...
            default = meta.default if has_def else None
            required = meta.explicit_required if meta.explicit_required is not None else not has_def
            if meta.description:
                description = meta.description
        else:
            has_def = param.default != inspect._empty
            default = param.default if has_def else None
            required = not has_def

        is_flag = param_type is bool

        # choose decorator
        if required:
            decorator = click.argument(param_name, type=param_type)
            mode = "arg"
        else:
            decorator = click.option(
                f"--{param_name.replace('_', '-')}",
                type=None if is_flag else param_type,
                is_flag=is_flag,
                default=default,
                required=False,
                show_default=True,
                help=description,
            )
            mode = "opt"

        param_decorators.append((param_name, mode, decorator, description))

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

    wrapper._original_func = func

    # Apply explicit overrides first, and mark them so the inference loop skips them
    for pname, (mode, extra) in overrides.items():
        if mode == "arg":
            wrapper = click.argument(pname, **extra)(wrapper)
        else:
            raw = sig.parameters[pname].annotation
            is_flag = raw is bool
            wrapper = click.option(
                f"--{pname.replace('_', '-')}",
                type=None if is_flag else raw,
                is_flag=is_flag,
                default=(sig.parameters[pname].default if sig.parameters[pname].default != inspect._empty else None),
                required=False,
                show_default=True,
                **extra,
            )(wrapper)

    # Now clear overrides so the loop won’t see them again
    overrides.clear()

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
