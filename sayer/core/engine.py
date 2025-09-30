import inspect
import json
import os
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from types import UnionType
from typing import (
    IO,
    Annotated,
    Any,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)
from uuid import UUID

import anyio
import click

from sayer.core.commands.sayer import SayerCommand
from sayer.core.groups.sayer import SayerGroup
from sayer.encoders import MoldingProtocol, apply_structure, get_encoders
from sayer.middleware import resolve as resolve_middleware, run_after, run_before
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State, get_state_classes

F = TypeVar("F", bound=Callable[..., Any])

T = TypeVar("T")
V = TypeVar("V")

SUPPORTS_HIDDEN = "hidden" in inspect.signature(click.Option).parameters


class CommandRegistry(dict[T, V]):
    """
    A specialized dictionary for storing Click commands.

    This registry prevents commands from being cleared once they are
    registered, ensuring that command definitions persist throughout the
    application's lifecycle.
    """

    def clear(self) -> None:
        """
        Overrides the default `clear` method to prevent clearing registered
        commands.

        This ensures that commands, once added to the registry, remain
        accessible and are not inadvertently removed.
        """
        # Never clear commands once registered
        ...


COMMANDS: CommandRegistry[str, click.Command] = CommandRegistry()
_GROUPS: dict[str, click.Group] = {}

# Primitive ↔ Click ParamType map
_PRIMITIVE_TYPE_MAP = {
    str: click.STRING,
    int: click.INT,
    float: click.FLOAT,
    bool: click.BOOL,
    UUID: click.UUID,
    date: click.DateTime(formats=["%Y-%m-%d"]),
    datetime: click.DateTime(),
}


@dataclass
class ParameterContext:
    parameter: inspect.Parameter
    raw_type_annotation: Any
    base_type: type
    metadata: Param | Option | Argument | Env | JsonParam | None
    help_text: str
    wrapper: Callable
    is_context_injected: bool
    is_overriden_type: bool

    expose: bool = field(init=False)
    hidden: bool = field(init=False)
    has_default: bool = field(init=False)
    default: Any = field(init=False)
    resolved_default: Any = field(init=False)
    is_required: bool = field(init=False)

    def __post_init__(self):
        self.expose = getattr(self.metadata, "expose_value", True)
        self.hidden = not self.expose

        # restore compatibility
        self.has_default = self.parameter.default not in (inspect._empty, Ellipsis)
        self.default = self.parameter.default if self.has_default else None

        self.resolved_default = self._resolve_default()
        self.is_required = self._resolve_required()

    def _resolve_default(self) -> Any:
        if self.metadata is not None:
            if getattr(self.metadata, "default_factory", None):
                return None
            if getattr(self.metadata, "default", Ellipsis) not in (Ellipsis, inspect._empty):
                val = self.metadata.default
                if val is Ellipsis:
                    return None
                if isinstance(val, (Option, Argument, Param, Env, JsonParam)):
                    return None
                return val

        if self.has_default:
            return self.default
        return None

    def _resolve_required(self) -> bool:
        if isinstance(self.metadata, (Param, Option, Argument, Env)):
            if getattr(self.metadata, "required", None) is True:
                return True
            if getattr(self.metadata, "required", None) is False:
                return False  # <-- explicit False must be respected

            has_metadata_default = getattr(self.metadata, "default", Ellipsis) not in (
                Ellipsis,
                inspect._empty,
                Ellipsis,
            )
            if not (self.has_default or has_metadata_default):
                return True
            return False

        if self.resolved_default is not None:
            return False
        if self.has_default:
            return False

        return True

    def normalize_type(self) -> None:
        origin = get_origin(self.base_type)
        if origin in (Union, types.UnionType):
            args = get_args(self.base_type)
            non_none = [t for t in args if t is not type(None)]
            if len(non_none) == 1:
                self.base_type = non_none[0]

        if (
            isinstance(self.metadata, Param)
            and get_origin(self.raw_type_annotation) is Annotated
            and _should_parameter_use_option_style(self.metadata, self.default)
        ):
            self.metadata = self.metadata.as_option()


def _safe_get_type_hints(func: Any, *, include_extras: bool = True) -> Mapping[str, Any]:
    """
    Robust type-hint resolver that tolerates dynamically loaded modules and missing sys.modules entries.
    """
    # Prefer the module inspect finds. Fall back to the function's globals
    mod = inspect.getmodule(func)
    globalns = getattr(mod, "__dict__", None) or getattr(func, "__globals__", {})
    try:
        return get_type_hints(func, globalns=globalns, localns=globalns, include_extras=include_extras)
    except Exception:
        # Try with sys.modules if available
        module = sys.modules.get(getattr(func, "__module__", None))
        if module is not None:
            try:
                return get_type_hints(
                    func,
                    globalns=module.__dict__,
                    localns=module.__dict__,
                    include_extras=include_extras,
                )
            except Exception:
                ...

        # Last resort: unresolved annotations dict
        return getattr(func, "__annotations__", {}) or {}


def _normalize_annotation_to_runtime_type(ann: Any) -> Any:
    """
    Reduce typing annotations to a runtime-checkable/conversion-friendly base.
    - Annotated[T, ...] -> T
    - Optional[T] (Union[T, None]) -> T
    - Union[A, B, ...] -> base of first non-None arg (best-effort)
    - Literal["x", ...] -> type of first literal (str/int/bool/...)
    - list[int] -> list, dict[str, int] -> dict, etc.
    - Callable[..., ...] -> collections.abc.Callable
    - Leave Enums alone (the engine may want to treat them specially)
    """
    if ann is None:
        return type(None)

    origin = get_origin(ann)

    # Annotated[T, ...]
    if origin is Annotated:
        args = get_args(ann)
        return _normalize_annotation_to_runtime_type(args[0]) if args else Any

    # Optional[T] or general Union
    if origin is Union:
        args = [a for a in get_args(ann) if a is not type(None)]
        if not args:
            return type(None)
        # Heuristic: take the first non-None argument as base
        return _normalize_annotation_to_runtime_type(args[0])

    # Literal["x", 1, True] -> type of first literal
    if origin is Literal:
        lits = get_args(ann)
        return type(lits[0]) if lits else Any

    # Subscripted generics -> map to their origin
    if origin is not None:
        # Callable[...] -> collections.abc.Callable
        if origin in (Callable,):
            return Callable
        return origin

    # If it's already a concrete type (incl. Enum subclasses), return as-is
    return ann


def _convert_cli_value_to_type(value: Any, to_type: type, func: Any = None, param_name: str = None) -> Any:
    """
    Converts a command-line interface (CLI) input value into the desired Python type.

    Handles:
      - Union / Optional: tries inner types in order (prefers non-None)
      - Containers: list[T], tuple[T...], set[T], frozenset[T], dict[K, V] (from ["k=v", ...])
      - Enum: leaves as string (Click.Choice validates)
      - date: downcasts datetime -> date
      - bool: parses "true/1/yes/on" and "false/0/no/off" (case-insensitive)
      - Scalars: casts when target is a real class
    """

    # Resolve postponed annotations if to_type is a string
    if isinstance(to_type, str) and func and param_name:
        type_hints = _safe_get_type_hints(func, include_extras=True)
        to_type = type_hints.get(param_name, to_type)

    # --- unwrap Annotated[T, ...] only for inspection (keep generics intact) ---
    inspect_ann = to_type
    if get_origin(inspect_ann) is Annotated:
        inspect_ann = get_args(inspect_ann)[0]

    # --- Union / Optional: handle early, trying inner types in order ---
    origin = get_origin(inspect_ann)
    if origin in (Union, UnionType):
        inner_types = list(get_args(inspect_ann))
        non_none = [t for t in inner_types if t is not type(None)]
        none_in_union = len(non_none) != len(inner_types)

        # try each non-None inner type in declared order
        for inner in non_none:
            try:
                coerced = _convert_cli_value_to_type(value, inner, func, param_name)
                # success heuristics:
                # 1) coerced is instance of the inner class/type
                if isinstance(inner, type) and isinstance(coerced, inner):
                    return coerced
                # 2) value changed (e.g., "42" -> 42)
                if coerced != value:
                    return coerced
            except Exception:
                continue

        # if None allowed and value is an empty/none sentinel, return None
        if none_in_union and (
            value is None or (isinstance(value, str) and value.strip().lower() in {"", "none", "null"})
        ):
            return None

        # nothing matched: leave as-is (or raise if you prefer strictness)
        return value

    # --- Container types (use inspect_ann so generic args are preserved) ---
    origin = get_origin(inspect_ann)

    # list[T]
    if origin is list:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return [_convert_cli_value_to_type(item, inner, func, param_name) for item in value]
        if isinstance(value, str):
            # CSV support; otherwise treat as a single item list
            if "," in value:
                return [_convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")]
            return [_convert_cli_value_to_type(value, inner, func, param_name)]
        # fallback: wrap scalar-ish input
        return [_convert_cli_value_to_type(value, inner, func, param_name)]

    # tuple[T, ...] or tuple[T1, T2, ...]
    if origin is tuple and isinstance(value, (list, tuple)):
        args = get_args(inspect_ann)
        # homogeneous: tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            inner = args[0]
            return tuple(_convert_cli_value_to_type(item, inner, func, param_name) for item in value)
        # heterogeneous: tuple[T1, T2, ...]
        return tuple(
            _convert_cli_value_to_type(item, arg_type, func, param_name)
            for item, arg_type in zip(value, args, strict=False)
        )

    # set[T]
    if origin is set:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return {_convert_cli_value_to_type(item, inner, func, param_name) for item in value}
        if isinstance(value, str):
            if "," in value:
                return {_convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")}
            return {_convert_cli_value_to_type(value, inner, func, param_name)}
        return {_convert_cli_value_to_type(value, inner, func, param_name)}

    # dict[K, V] from ["key=val", ...]
    if origin is dict and isinstance(value, (list, tuple)):
        args = get_args(inspect_ann)
        if len(args) >= 2:
            key_t, val_t = args[0], args[1]
        else:
            key_t, val_t = (str, Any)
        out: dict[Any, Any] = {}
        for item in value:
            if isinstance(item, str) and "=" in item:
                k_str, v_str = item.split("=", 1)
                k = _convert_cli_value_to_type(k_str, key_t, func, param_name)
                v = _convert_cli_value_to_type(v_str, val_t, func, param_name)
                out[k] = v
            else:
                raise ValueError(f"Cannot parse dict item {item!r} for {param_name!r}")
        return out

    # frozenset[T]
    if origin is frozenset:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return frozenset(_convert_cli_value_to_type(item, inner, func, param_name) for item in value)
        if isinstance(value, str):
            if "," in value:
                return frozenset(
                    _convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")
                )
            return frozenset((_convert_cli_value_to_type(value, inner, func, param_name),))
        return frozenset((_convert_cli_value_to_type(value, inner, func, param_name),))

    # --- Scalars: now normalize to a runtime base and convert ---
    to_type = _normalize_annotation_to_runtime_type(to_type)

    if isinstance(to_type, type) and issubclass(to_type, Enum):
        # Policy: leave Enum strings as-is for Click.Choice validation
        return value

    if to_type is date and isinstance(value, datetime):
        return value.date()

    if to_type is bool:
        if isinstance(value, bool):
            return value
        v = str(value).strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
        # fallthrough: let casting try or return original

    # Only perform isinstance/cast when target is a real class
    if isinstance(to_type, type):
        # Prevent coercing None into string
        if value is None:
            return None

        if isinstance(value, to_type):
            return value
        try:
            return to_type(value)
        except Exception:
            return value

    if isinstance(value, str) and value.strip().lower() in {"none", "null", ""}:  # type: ignore
        return None
    return value


def _should_parameter_use_option_style(meta_param: Param, default_value: Any) -> str | bool:  #
    """
    Determines if a generic `Param` metadata suggests that a command-line
    parameter should be exposed as a **Click option** (`--param`) rather than
    a positional **argument**.

    This is decided based on the presence of certain metadata attributes that
    are typically associated with options:
    - `envvar`: If an environment variable is specified.
    - `prompt`: If the user should be prompted for input.
    - `confirmation_prompt`: If a confirmation prompt is required.
    - `hide_input`: If the input should be hidden (e.g., for passwords).
    - `callback`: If a custom callback function is associated.
    - `default`: If a non-empty or non-`None` default value is provided.

    Args:
        meta_param: The `Param` metadata object associated with the parameter.
        default_value: The default value of the parameter as defined in the
                       function signature.

    Returns:
        True if the parameter should be an option; False otherwise.
    """
    return (
        meta_param.envvar is not None
        or meta_param.prompt
        or meta_param.confirmation_prompt
        or meta_param.hide_input
        or meta_param.callback is not None
        or (meta_param.default is not ... and meta_param.default is not None)
    )


def _extract_command_help_text(signature: inspect.Signature, func: Callable, attrs: Any) -> str:  #
    """
    Extracts the comprehensive help text for a Click command from various
    sources, prioritized as follows:
    1. The function's docstring.
    2. The `help` attribute of a `Param` object used as a default value.
    3. The `help` attribute of a `Param` object within an `Annotated` type
       annotation.

    Args:
        signature: The `inspect.Signature` object of the command function.
        func: The Python function decorated as a command.

    Returns:
        The extracted help text string, or an empty string if no help text
        is found.
    """
    attrs_help = attrs.pop("help", None)
    command_help_text = attrs_help or inspect.getdoc(func) or ""
    if command_help_text:
        return command_help_text

    for parameter in signature.parameters.values():
        if isinstance(parameter.default, Param) and parameter.default.help:
            return parameter.default.help

        annotation = parameter.annotation
        if get_origin(annotation) is Annotated:
            for metadata_item in get_args(annotation)[1:]:
                if isinstance(metadata_item, Param) and metadata_item.help:
                    return metadata_item.help
    return ""


def _handle_variadic_args(ctx: ParameterContext) -> Optional[Callable]:
    base_origin = get_origin(ctx.base_type)
    if ctx.metadata is None and base_origin in (list, tuple) and ctx.parameter.name in {"args", "argv"}:
        inner_args = get_args(ctx.base_type)
        inner_type = inner_args[0] if inner_args else str
        click_inner_type = _PRIMITIVE_TYPE_MAP.get(inner_type, click.STRING)
        return click.argument(
            ctx.parameter.name,
            nargs=-1,
            type=click_inner_type,
            required=False,
            expose_value=ctx.expose,
        )(ctx.wrapper)
    return None


def _handle_sequence(ctx: ParameterContext) -> Optional[Callable]:
    base_origin = get_origin(ctx.base_type)
    if base_origin not in (list, Sequence):
        return None

    inner_args = get_args(ctx.base_type)
    inner_type = inner_args[0] if inner_args else str
    click_inner_type = _PRIMITIVE_TYPE_MAP.get(inner_type, click.STRING)

    if isinstance(ctx.metadata, Argument):
        variadic_nargs = ctx.metadata.options.get("nargs", -1)
        is_variadic = variadic_nargs == -1 or (isinstance(variadic_nargs, int) and variadic_nargs != 1)
        is_required_local = False if is_variadic else getattr(ctx.metadata, "required", False)
        arg_options = dict(ctx.metadata.options)

        arg_type = click_inner_type if not ctx.is_overriden_type else ctx.base_type
        return click.argument(
            ctx.parameter.name,
            type=arg_type,
            required=is_required_local,
            expose_value=ctx.metadata.expose_value,
            **arg_options,
        )(ctx.wrapper)

    default_for_sequence = ctx.resolved_default if ctx.resolved_default is not None else ()
    kwargs = {
        "type": click_inner_type if not ctx.is_overriden_type else ctx.base_type,
        "multiple": True,
        "default": default_for_sequence,
        "show_default": True,
        "help": ctx.help_text,
        "expose_value": ctx.expose,
    }
    if SUPPORTS_HIDDEN:
        kwargs["hidden"] = ctx.hidden

    return click.option(f"--{ctx.parameter.name.replace('_', '-')}", **kwargs)(ctx.wrapper)


def _handle_enum(ctx: ParameterContext) -> Optional[Callable]:
    if not (isinstance(ctx.base_type, type) and issubclass(ctx.base_type, Enum)):
        return None

    enum_choices = [e.value for e in ctx.base_type]

    default_val = ctx.resolved_default
    if isinstance(default_val, Enum):
        default_val = default_val.value

    kwargs = {
        "type": click.Choice(enum_choices) if not ctx.is_overriden_type else ctx.base_type,
        "default": default_val,
        "show_default": True,
        "help": ctx.help_text,
        "expose_value": ctx.expose,
    }
    if SUPPORTS_HIDDEN:
        kwargs["hidden"] = ctx.hidden

    return click.option(f"--{ctx.parameter.name.replace('_', '-')}", **kwargs)(ctx.wrapper)


def _handle_json(ctx: ParameterContext) -> Optional[Callable]:
    simple_types = (str, bool, int, float, Enum, Path, UUID, date, datetime)
    skip_implicit_json = isinstance(ctx.base_type, type) and issubclass(ctx.base_type, simple_types)
    if (
        ctx.metadata is None
        and not skip_implicit_json
        and inspect.isclass(ctx.base_type)
        and any(
            isinstance(encoder, MoldingProtocol) and encoder.is_type_structure(ctx.base_type)
            for encoder in get_encoders()
        )
    ):
        ctx.metadata = JsonParam()

    if isinstance(ctx.metadata, JsonParam):
        kwargs = {
            "type": click.STRING if not ctx.is_overriden_type else ctx.base_type,
            "default": ctx.metadata.default,
            "required": ctx.metadata.required,
            "show_default": False,
            "expose_value": ctx.expose,
            "help": f"{ctx.help_text} (JSON)",
        }
        if SUPPORTS_HIDDEN:
            kwargs["hidden"] = ctx.hidden

        return click.option(f"--{ctx.parameter.name.replace('_', '-')}", **kwargs)(ctx.wrapper)
    return None


def _handle_special_types(ctx: ParameterContext) -> None:
    """Adjust special known types in-place."""
    if ctx.base_type is Path:
        ctx.base_type = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)
    if ctx.base_type is UUID:
        ctx.base_type = click.UUID
    if ctx.base_type is date:
        ctx.base_type = click.DateTime(formats=["%Y-%m-%d"])
    if ctx.base_type is datetime:
        ctx.base_type = click.DateTime()
    if ctx.raw_type_annotation is IO or ctx.raw_type_annotation is click.File:
        ctx.base_type = click.File("r")
    return None


def _handle_argument(ctx: ParameterContext) -> Optional[Callable]:
    if not isinstance(ctx.metadata, Argument):
        return None

    final_default = ctx.resolved_default
    if isinstance(final_default, (Option, Argument, Param, Env, JsonParam)):
        final_default = None

    if "nargs" in ctx.metadata.options and final_default is not None:
        raise ValueError("Variadic arguments (nargs) cannot have a default value.")
    if final_default is not None:
        ctx.metadata.options["default"] = final_default

    arg_kwargs = dict(ctx.metadata.options)
    arg_kwargs.update(
        {
            "type": ctx.base_type,
            "required": getattr(ctx.metadata, "required", not ctx.has_default),
            "expose_value": getattr(ctx.metadata, "expose_value", True),
        }
    )
    wrapped = click.argument(ctx.parameter.name, **arg_kwargs)(ctx.wrapper)

    help_text = getattr(ctx.metadata, "help", "")
    if hasattr(wrapped, "params"):
        for param_obj in wrapped.params:
            if isinstance(param_obj, click.Argument) and param_obj.name == ctx.parameter.name:
                param_obj.help = help_text
    return wrapped


def _handle_env(ctx: ParameterContext) -> Optional[Callable]:
    if not isinstance(ctx.metadata, Env):
        return None

    env_val = os.getenv(ctx.metadata.envvar, ctx.metadata.default)

    kwargs = {
        "type": ctx.base_type,
        "default": None if getattr(ctx.metadata, "default_factory", None) else env_val,
        "show_default": True,
        "required": ctx.metadata.required,
        "help": f"[env:{ctx.metadata.envvar}] {ctx.help_text}",
        "expose_value": ctx.expose,
        **ctx.metadata.options,
    }
    if SUPPORTS_HIDDEN:
        kwargs["hidden"] = ctx.hidden

    return click.option(
        f"--{ctx.parameter.name.replace('_', '-')}",
        **kwargs,
    )(ctx.wrapper)


def _handle_option(ctx: ParameterContext) -> Optional[Callable]:
    if not isinstance(ctx.metadata, Option):
        return None

    raw_for_option = ctx.raw_type_annotation
    if get_origin(raw_for_option) is Annotated:
        ann_args = get_args(raw_for_option)
        if ann_args:
            raw_for_option = ann_args[0]

    # Handle Optional[T]
    if get_origin(raw_for_option) in (Union, types.UnionType):
        union_args = get_args(raw_for_option)
        if type(None) in union_args:
            non_none = [a for a in union_args if a is not type(None)]
            if len(non_none) == 1:
                ctx.base_type = non_none[0]

    # Default resolution
    if getattr(ctx.metadata, "default_factory", None):
        option_default = None
    else:
        option_default = ctx.resolved_default

    if isinstance(option_default, Option):
        option_default = None

    default_kwarg: dict[str, Any] = {}
    if option_default is not None:
        default_kwarg["default"] = option_default

    if ctx.metadata.is_flag and option_default is True:
        default_kwarg["default"] = None  # let Click handle

    kwargs = {
        "type": None if ctx.base_type is bool else ctx.base_type,
        "is_flag": ctx.base_type is bool,
        "required": ctx.is_required,
        "show_default": ctx.metadata.show_default,
        "help": ctx.help_text,
        "prompt": ctx.metadata.prompt,
        "hide_input": ctx.metadata.hide_input,
        "callback": ctx.metadata.callback,
        "envvar": ctx.metadata.envvar,
        "expose_value": ctx.expose,
        **ctx.metadata.options,
        **default_kwarg,
    }
    if SUPPORTS_HIDDEN:
        kwargs["hidden"] = ctx.hidden

    return click.option(
        f"--{ctx.parameter.name.replace('_', '-')}",
        *ctx.metadata.param_decls,
        **kwargs,
    )(ctx.wrapper)


def _handle_boolean_flag(ctx: ParameterContext) -> Optional[Callable]:
    """
    Handler for pure boolean flags, ensures defaults are actual booleans.
    """
    if ctx.base_type is not bool:
        return None

    kwargs = {
        "is_flag": True,
        "default": bool(ctx.resolved_default) if ctx.resolved_default is not None else False,
        "show_default": True,
        "help": ctx.help_text,
        "expose_value": ctx.expose,
    }
    if SUPPORTS_HIDDEN:
        kwargs["hidden"] = ctx.hidden

    return click.option(
        f"--{ctx.parameter.name.replace('_', '-')}",
        **kwargs,
    )(ctx.wrapper)


def _handle_defaults(ctx: ParameterContext) -> Optional[Callable]:
    """
    Fallback handler when no explicit metadata matches.
    Decides between click.argument and click.option depending on context.
    """
    # No metadata, no default → required positional
    if ctx.is_required and ctx.resolved_default is None:
        return click.argument(
            ctx.parameter.name,
            type=ctx.base_type,
            required=True,
        )(ctx.wrapper)

    final_default = ctx.resolved_default

    # Context-injected → prefer option style
    if ctx.is_context_injected and ctx.base_type is not bool:
        kwargs = {
            "type": ctx.base_type,
            "default": final_default,
            "required": ctx.is_required,
            "show_default": True,
            "help": ctx.help_text,
            "expose_value": ctx.expose,
        }
        if SUPPORTS_HIDDEN:
            kwargs["hidden"] = ctx.hidden
        return click.option(
            f"--{ctx.parameter.name.replace('_', '-')}",
            **kwargs,
        )(ctx.wrapper)

    # Explicit None default → treat as optional option
    if final_default is None and not ctx.is_required:
        kwargs = {
            "type": ctx.base_type,
            "show_default": True,
            "help": ctx.help_text,
            "expose_value": ctx.expose,
        }
        if SUPPORTS_HIDDEN:
            kwargs["hidden"] = ctx.hidden
        return click.option(
            f"--{ctx.parameter.name.replace('_', '-')}",
            **kwargs,
        )(ctx.wrapper)

    # Boolean flags with bool defaults
    if ctx.base_type is bool and isinstance(ctx.parameter.default, bool):
        kwargs = {
            "is_flag": True,
            "default": ctx.parameter.default,
            "show_default": True,
            "help": ctx.help_text,
            "expose_value": ctx.expose,
        }
        if SUPPORTS_HIDDEN:
            kwargs["hidden"] = ctx.hidden
        return click.option(
            f"--{ctx.parameter.name.replace('_', '-')}",
            **kwargs,
        )(ctx.wrapper)

    # Fallback: positional with default
    wrapped = click.argument(
        ctx.parameter.name,
        type=ctx.base_type,
        default=final_default,
        required=False,
    )(ctx.wrapper)

    for param in wrapped.params:
        if param.name == ctx.parameter.name:
            param.required = False
            param.default = final_default
    return wrapped


def _build_click_parameter(
    parameter: inspect.Parameter,
    raw_type_annotation: Any,
    parameter_base_type: type,
    parameter_metadata: Param | Option | Argument | Env | JsonParam | None,
    param_help_text: str,
    click_wrapper_function: Callable,
    is_context_injected: bool,
    is_overriden_type: bool,
) -> Callable:
    """
    Entry point: builds a Click argument/option decorator for a function parameter.
    Delegates logic to smaller helpers based on type/metadata.
    """
    ctx = ParameterContext(
        parameter=parameter,
        raw_type_annotation=raw_type_annotation,
        base_type=parameter_base_type,
        metadata=parameter_metadata,
        help_text=param_help_text,
        wrapper=click_wrapper_function,
        is_context_injected=is_context_injected,
        is_overriden_type=is_overriden_type,
    )

    ctx.normalize_type()
    _handle_special_types(ctx)  # adjusts in-place

    for handler in (
        _handle_variadic_args,
        _handle_sequence,
        _handle_enum,
        _handle_json,
        _handle_argument,
        _handle_env,
        _handle_option,
        _handle_boolean_flag,
        _handle_defaults,
    ):
        result = handler(ctx)
        if result is not None:
            return result

    raise RuntimeError(f"Unsupported parameter configuration: {ctx.parameter}")


@overload
def command(func: F) -> click.Command: ...


@overload
def command(
    func: None = None,
    *args: Any,
    middleware: Sequence[str | Callable[..., Any]] | None = None,
    **attrs: Any,
) -> Callable[[F], click.Command]: ...


def command(
    func: F | None = None,
    *args: Any,
    middleware: Sequence[str | Callable[..., Any]] | None = None,
    **attrs: Any,
) -> click.Command | Callable[[F], click.Command]:
    """
    A powerful decorator that transforms a Python function into a Click command,
    enhancing it with `sayer`'s advanced capabilities.

    This decorator provides comprehensive support for:
    - **Diverse Type Handling**: Automatically maps common Python types (primitives,
      `Path`, `UUID`, `date`, `datetime`, `IO`) to appropriate Click parameter types.
    - **Enum Integration**: Converts `Enum` parameters into `Click.Choice` options.
    - **JSON Parameter Injection**: Facilitates implicit or explicit deserialization
      of JSON strings from the CLI into complex Python objects (e.g., `dataclasses`,
      Pydantic models) using `sayer`'s `MoldingProtocol` encoders.
    - **Rich Parameter Metadata**: Allows defining detailed CLI behavior (e.g.,
      prompts, hidden input, environment variables, default values) using `Param`,
      `Option`, `Argument`, `Env`, and `JsonParam` metadata objects.
    - **Context and State Injection**: Automatically injects `click.Context` and
      `sayer.State` instances into command functions, simplifying access to
      application state.
    - **Dynamic Default Factories**: Supports parameters whose default values are
      generated by a callable, enabling dynamic defaults at runtime.
    - **Middleware Hooks**: Integrates `before` and `after` hooks, allowing custom
      logic to be executed before and after command execution.
    - **Asynchronous Command Support**: Automatically runs asynchronous command
      functions using `anyio.run()`.

    The decorator can be used directly (`@command`) or with keyword arguments
    (`@command(middleware=[...])`).

    Args:
        func: The Python function to be transformed into a Click command.
              This is typically provided when using the decorator without
              parentheses.
        middleware: An optional sequence of middleware names (strings) or
                    callable hooks to be applied to the command. Middleware
                    functions can modify arguments before execution or process
                    results after execution.

    Returns:
        If `func` is provided, returns a `click.Command` object.
        If `func` is `None` (i.e., used with parentheses), returns a callable
        that takes the function as an argument and returns a `click.Command`.
    """
    if middleware is None:
        middleware = ()

    name_from_pos: str | None = None
    if args and isinstance(args[0], str):
        name_from_pos, args = args[0], args[1:]

    def command_decorator(function_to_decorate: F) -> click.Command:
        # Convert function name to a kebab-case command name (e.g., "my_command" -> "my-command").
        default_name = function_to_decorate.__name__.replace("_", "-")
        command_name = attrs.pop("name", name_from_pos) or default_name
        # Inspect the function's signature to get parameter information.
        function_signature = inspect.signature(function_to_decorate)
        # Get type hints for the function parameters, resolving any `Annotated` types.
        type_hints = get_type_hints(function_to_decorate, include_extras=True)
        # Extract help text for the command from various sources.
        command_help_text = _extract_command_help_text(function_signature, function_to_decorate, attrs)
        # Resolve before and after middleware hooks.
        before_execution_hooks, after_execution_hooks = resolve_middleware(middleware)
        # Check if `click.Context` is explicitly injected into the function's parameters.
        is_context_param_injected = any(p.annotation is click.Context for p in function_signature.parameters.values())
        # Checks if should be a custom group to added

        click_cmd_kwargs = {
            "name": command_name,
            "help": command_help_text,
            **attrs,
        }

        # Start with the original function as the Click wrapper function.
        # This function will be progressively wrapped with Click decorators.
        # This will allow to naturally call a command as a normal function
        click_cmd_kwargs.setdefault("cls", SayerCommand)

        @click.command(**click_cmd_kwargs)  # type: ignore
        @click.pass_context
        @wraps(function_to_decorate)
        def click_command_wrapper(ctx: click.Context, **kwargs: Any) -> Any:
            """
            The inner Click command wrapper function.

            This function is the actual entry point for the Click command.
            It handles:
            - State injection.
            - Dynamic default factory resolution.
            - Argument binding and type conversion.
            - Execution of `before` and `after` middleware hooks.
            - Execution of the original Python function (`fn`),
              including handling of asynchronous functions.
            """
            for param in ctx.command.params:
                if isinstance(param, click.Option) and param.required:
                    # click stores missing params as None (or sometimes Ellipsis in Sayer),
                    # so treat both as “not provided.”
                    val = kwargs.get(param.name, None)
                    if val is None or val is inspect._empty or val in [Ellipsis, "Ellipsis"]:
                        ctx.fail(f"Missing option '{param.opts[0]}'")

            # --- State injection ---
            # If the context doesn't already have sayer state, initialize it.
            if not hasattr(ctx, "_sayer_state"):
                try:
                    # Instantiate all registered State classes.
                    state_cache = {cls: cls() for cls in get_state_classes()}
                except Exception as e:
                    # Handle potential errors during state initialization.
                    click.echo(str(e))
                    ctx.exit(1)
                ctx._sayer_state = state_cache  # type: ignore

            # --- Dynamic default_factory injection ---
            for param_sig in function_signature.parameters.values():
                # Skip `click.Context` and `State` parameters as they are handled separately.
                if param_sig.annotation is click.Context:
                    continue
                if isinstance(param_sig.annotation, type) and issubclass(param_sig.annotation, State):
                    continue

                param_metadata_for_factory = None
                # Resolve the raw type, handling `Annotated` parameters.
                raw_annotation_for_factory = param_sig.annotation if param_sig.annotation is not inspect._empty else str
                if get_origin(raw_annotation_for_factory) is Annotated:
                    # Look for metadata (Option, Env) within Annotated arguments.
                    for meta_item in get_args(raw_annotation_for_factory)[1:]:
                        if isinstance(meta_item, (Option, Env)):
                            param_metadata_for_factory = meta_item
                            break
                # If no metadata found in Annotated, check if the default value is metadata.
                if param_metadata_for_factory is None and isinstance(param_sig.default, (Option, Env)):
                    param_metadata_for_factory = param_sig.default

                # If metadata with a `default_factory` is found and no value was provided
                # via the CLI, call the factory to get the default.
                if isinstance(param_metadata_for_factory, (Option, Env)) and getattr(
                    param_metadata_for_factory, "default_factory", None
                ):
                    if not kwargs.get(param_sig.name):
                        kwargs[param_sig.name] = param_metadata_for_factory.default_factory()

            # --- Bind & convert arguments ---
            bound_arguments: dict[str, Any] = {}
            for param_sig in function_signature.parameters.values():
                # Inject `click.Context` if requested.
                if param_sig.annotation is click.Context:
                    bound_arguments[param_sig.name] = ctx
                    continue
                # Inject `sayer.State` instances if requested.
                if isinstance(param_sig.annotation, type) and issubclass(param_sig.annotation, State):
                    bound_arguments[param_sig.name] = ctx._sayer_state[param_sig.annotation]  # type: ignore
                    continue

                # Determine the target type for conversion, handling `Annotated` and default `str`.
                raw_type_for_conversion = param_sig.annotation if param_sig.annotation is not inspect._empty else str
                target_type_for_conversion = (
                    get_args(raw_type_for_conversion)[0]
                    if get_origin(raw_type_for_conversion) is Annotated
                    else raw_type_for_conversion
                )
                parameter_value = kwargs.get(param_sig.name)

                # Special handling for explicit `JsonParam` or `Annotated` with `JsonParam`.
                is_json_param_by_default = isinstance(param_sig.default, JsonParam)
                is_json_param_by_annotation = get_origin(param_sig.annotation) is Annotated and any(
                    isinstance(meta, JsonParam) for meta in get_args(param_sig.annotation)[1:]
                )
                if is_json_param_by_default or is_json_param_by_annotation:
                    if isinstance(parameter_value, str):
                        try:
                            # Attempt to load JSON string and then apply structure.
                            json_data = json.loads(parameter_value)
                        except json.JSONDecodeError as e:
                            # Raise a Click `BadParameter` error on JSON decoding failure.
                            raise click.BadParameter(f"Invalid JSON for '{param_sig.name}': {e}") from e
                        parameter_value = apply_structure(target_type_for_conversion, json_data)

                # Convert non-list/Sequence types using the `_convert_cli_value_to_type` helper.
                if get_origin(raw_type_for_conversion) in (list, Sequence):
                    inner = get_args(raw_type_for_conversion)[0] if get_args(raw_type_for_conversion) else Any
                    parameter_value = [
                        _convert_cli_value_to_type(item, inner, function_to_decorate, param_sig.name)
                        for item in (parameter_value or [])
                    ]
                else:
                    parameter_value = _convert_cli_value_to_type(
                        parameter_value,
                        target_type_for_conversion,
                        function_to_decorate,
                        param_sig.name,
                    )

                bound_arguments[param_sig.name] = parameter_value

            # --- Before hooks ---
            for hook_func in before_execution_hooks:
                hook_func(command_name, bound_arguments)
            # Run global and command-specific `before` middleware.
            run_before(command_name, bound_arguments)

            # Checks if this comes from a natural call (i.e. not from Click)
            is_natural_call = kwargs.pop("_sayer_natural_call", False)

            # --- Execute command ---
            execution_result = function_to_decorate(**bound_arguments)
            # If the function is a coroutine, run it using `anyio`.
            if inspect.iscoroutine(execution_result):
                # If in AnyIO context create a coroutine to run later
                if is_natural_call:

                    async def _runner() -> Any:
                        """
                        Runs the coroutine in an existing AnyIO context.
                        This is used when the command is invoked directly as a function
                        within an existing async context, avoiding nested event loops.
                        """
                        _final = await execution_result
                        for hook_func in after_execution_hooks:
                            hook_func(command_name, bound_arguments, _final)
                        run_after(command_name, bound_arguments, _final)
                        return _final

                    return _runner()

                # Not in AnyIO context → run now
                execution_result = anyio.run(lambda: execution_result)

            # --- After hooks ---
            for hook_func in after_execution_hooks:  # type: ignore
                hook_func(command_name, bound_arguments, execution_result)  # type: ignore
            # Run global and command-specific `after` middleware.
            run_after(command_name, bound_arguments, execution_result)
            ctx._sayer_return_value = execution_result
            return execution_result

        click_command_wrapper._original_func = function_to_decorate
        click_command_wrapper.standalone_mode = False
        click_command_wrapper._return_result = True
        current_wrapper = click_command_wrapper

        # Attach parameters to the Click command.
        # Iterate through the original function's parameters to build Click options/arguments.
        for param_inspect_obj in function_signature.parameters.values():
            # Skip `click.Context` and `sayer.State` parameters as they are handled internally.
            if param_inspect_obj.annotation is click.Context or (
                isinstance(param_inspect_obj.annotation, type) and issubclass(param_inspect_obj.annotation, State)
            ):
                continue

            # Determine the raw annotation and the primary parameter type.
            raw_annotation_for_param = type_hints.get(
                param_inspect_obj.name,
                (param_inspect_obj.annotation if param_inspect_obj.annotation is not inspect._empty else str),
            )
            param_base_type = (
                get_args(raw_annotation_for_param)[0]
                if get_origin(raw_annotation_for_param) is Annotated
                else raw_annotation_for_param
            )

            param_metadata_for_build = None
            param_help_for_build = ""
            # Extract parameter metadata and help text from `Annotated` types.
            if get_origin(raw_annotation_for_param) is Annotated:
                for meta_item in get_args(raw_annotation_for_param)[1:]:
                    if isinstance(meta_item, (Option, Argument, Env, Param, JsonParam)):
                        param_metadata_for_build = meta_item
                    elif isinstance(meta_item, str):
                        param_help_for_build = meta_item
            # If no metadata found in `Annotated`, check if the default value is metadata.
            if param_metadata_for_build is None and isinstance(
                param_inspect_obj.default, (Param, Option, Argument, Env, JsonParam)
            ):
                param_metadata_for_build = param_inspect_obj.default

            # Extract the type and override it
            is_overriden_type = False
            if getattr(param_metadata_for_build, "type", None) is not None:
                param_base_type = param_metadata_for_build.type
                is_overriden_type = True

            # Build and apply the Click parameter decorator.
            current_wrapper = _build_click_parameter(
                param_inspect_obj,
                raw_annotation_for_param,
                param_base_type,
                param_metadata_for_build,
                param_help_for_build,
                current_wrapper,
                is_context_param_injected,
                is_overriden_type,
            )

        # Register the command.
        if hasattr(function_to_decorate, "__sayer_group__"):
            # If the function is part of a `sayer` group, add it to that group.
            function_to_decorate.__sayer_group__.add_command(current_wrapper)
        else:
            # Otherwise, add it to the global command registry.
            COMMANDS[command_name] = current_wrapper

        return cast(click.Command, current_wrapper)

    # If `func` is provided (i.e., `@command` without parentheses), apply the decorator immediately.
    # Otherwise, return the `command_decorator` function for later application (i.e., `@command(...)`).
    return command_decorator if func is None else command_decorator(func)


def group(
    name: str,
    group_cls: type[click.Group] | None = None,
    help: str | None = None,
    is_custom: bool = False,
    custom_command_name: str | None = None,
    **kwargs: Any,
) -> click.Group:
    """
    Creates or retrieves a Click command group, integrating it with `sayer`'s
    command registration logic.

    This function ensures that any commands defined within this group using
    `@group.command(...)` will be processed by `sayer`'s `command` decorator,
    inheriting all its advanced features (type handling, metadata, state, etc.).

    If a group with the given `name` already exists, the existing group is
    returned. Otherwise, a new group is created, defaulting to `SayerGroup` for
    enhanced formatting if no `group_cls` is specified. The `command` method
    of the created group is monkey-patched to use `sayer.command`.

    Args:
        name: The name of the Click group. This will be the name used to invoke
              the group from the command line.
        group_cls: An optional custom Click group class to use. If `None`,
                   `sayer.utils.ui.SayerGroup` is used by default.
        help: An optional help string for the group, displayed when `--help`
              is invoked on the group.
        is_custom: Whether or not the group is intended to be a custom command for display
        custom_command_name: The name of the custom command to use. If `None`, defaults to "Custom"

    Returns:
        A `click.Group` instance, either newly created or retrieved from the
        internal registry.
    """
    # Check if the group already exists to avoid re-creating it.
    if name not in _GROUPS:
        # Determine the group class to use; default to `SayerGroup`.
        group_class_to_use = group_cls or SayerGroup
        # Create the Click group instance.
        new_group_instance = group_class_to_use(name=name, help=help, **kwargs)

        # Set the group for different sections
        if is_custom:
            new_group_instance.__is_custom__ = is_custom
            new_group_instance._custom_command_config.title = custom_command_name or name.capitalize()  # noqa

        def _group_command_method_override(func_to_bind: F | None = None, **opts: Any) -> click.Command:  #
            """
            Internal helper that replaces `click.Group.command` to integrate
            `sayer`'s command decorator.

            This allows `sayer.command` to be applied automatically when
            `@group_instance.command` is used.
            """
            if func_to_bind and callable(func_to_bind):
                # If a function is provided directly, associate it with the group
                # and apply `sayer.command`.
                func_to_bind.__sayer_group__ = new_group_instance  # type: ignore
                return command(func_to_bind, **opts)

            def inner_decorator(function_to_decorate_for_group: F) -> click.Command:
                # If used as `@group.command(...)`, return a decorator that
                # first marks the function with the group, then applies `sayer.command`.
                function_to_decorate_for_group.__sayer_group__ = new_group_instance  # type: ignore
                return command(function_to_decorate_for_group, **opts)

            return cast(click.Command, inner_decorator)

        # Monkey-patch the group's `command` method.
        new_group_instance.command = _group_command_method_override  # type: ignore
        # Store the created group in the internal groups registry.
        _GROUPS[name] = new_group_instance

    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    """
    Retrieves all registered Click commands that are not part of a specific group.

    These are commands that were defined using `@command` (without a preceding
    `group` decorator) and are stored in the global `COMMANDS` registry.

    Returns:
        A dictionary where keys are command names (strings) and values are
        `click.Command` objects.
    """
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    """
    Retrieves all registered Click command groups.

    These are groups created using the `group()` function.

    Returns:
        A dictionary where keys are group names (strings) and values are
        `click.Group` objects.
    """
    return _GROUPS


def bind_command_to_group(group_instance: click.Group, function_to_bind: F, *args: Any, **attrs: Any) -> click.Command:
    """
    Binds a function to a specific Click group using `sayer`'s command decorator.

    This helper function is primarily used internally for monkey-patching
    `click.Group.command` to ensure all commands within a `sayer`-managed group
    are processed by `sayer`'s `command` decorator.

    Args:
        group_instance: The `click.Group` instance to which the command will be bound.
        function_to_bind: The Python function to be turned into a command.

    Returns:
        A `click.Command` object, decorated by `sayer.command` and associated
        with the provided group.
    """

    def decorator(fn: F) -> click.Command:
        fn.__sayer_group__ = group_instance  # type: ignore
        return command(fn, *args, **attrs)

    if function_to_bind and callable(function_to_bind) and not args and not attrs:
        return decorator(function_to_bind)
    return cast(click.Command, decorator)


# Monkey-patch Click so that all groups use Sayer's binding logic:
# This crucial line ensures that any `click.Group` created (even outside
# `sayer.group`) will use `sayer`'s `bind_command_to_group` when its `.command`
# method is called. This globally enables `sayer`'s enhanced command
# features for all Click groups in the application.
click.Group.command = bind_command_to_group  # type: ignore
