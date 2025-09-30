from __future__ import annotations

import inspect
import sys
import types
from datetime import date, datetime
from enum import Enum
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    Mapping,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from sayer.params import Param

try:
    from types import UnionType
except ImportError:  # py<3.10
    UnionType = Union

T = TypeVar("T")
V = TypeVar("V")


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
    """Recursively reduces complex type annotations to a simple, runtime-checkable base type.

    This function unwraps nested, placeholder, and generic type annotations to extract
    the most specific concrete type suitable for runtime checks, conversions, or
    initial parameter construction (e.g., for Click type system integration).

    Args:
        ann: The type annotation (`Any`) to be processed.

    Returns:
        The simplified base type, which may be a concrete Python type (`str`, `int`),
        a generic origin type (`list`, `dict`), or a Click-compatible type.

    The normalization rules applied are:
    1.  **None**: Maps `None` (as a value) to the `type(None)` object.
    2.  **Annotated**: Extracts the base type $T$ from $\text{Annotated}[T, \\dots]$.
    3.  **Optional/Union**: Extracts the first non-`None` type $T$ from $\text{Union}[T, \text{None}]$ (i.e., $\text{Optional}[T]$) or general unions. This is a best-effort heuristic.
    4.  **Literal**: Maps $\text{Literal}[\text{"a"}, 1]$ to the type of its first value (e.g., $\text{str}$).
    5.  **Generics**: Maps subscripted generics (e.g., $\text{list}[\text{int}]$) to their origin (e.g., $\text{list}$).
    6.  **Callable**: Maps $\text{typing.Callable}[\\dots]$ to $\text{collections.abc.Callable}$ for runtime compatibility.
    7.  **Concrete Types**: Leaves simple types and `Enum` subclasses as-is.
    """
    if ann is None:
        return type(None)

    origin = get_origin(ann)

    # 1. Annotated[T, ...] -> T
    if origin is Annotated:
        args = get_args(ann)
        return _normalize_annotation_to_runtime_type(args[0]) if args else Any

    # 2. Optional[T] (Union[T, None]) or general Union
    if origin in (Union, types.UnionType):
        # Filter out type(None) to unwrap Optional[T]
        args = [a for a in get_args(ann) if a is not type(None)]
        if not args:
            return type(None)
        # Heuristic: Recursively normalize the first non-None argument as the base
        return _normalize_annotation_to_runtime_type(args[0])

    # 3. Literal["x", 1, True] -> type of first literal
    if origin is Literal:
        lits = get_args(ann)
        return type(lits[0]) if lits else Any

    # 4. Subscripted generics -> map to their origin
    if origin is not None:
        # 4a. Callable[...] -> collections.abc.Callable
        if origin in (Callable, Callable):
            return Callable
        # 4b. list[int] -> list, dict[str, int] -> dict, etc.
        return origin

    # 5. If it's already a concrete type (incl. Enum subclasses), return as-is
    return ann


def convert_cli_value_to_type(
    value: Any,
    to_type: Any,  # not just type: could be Annotated/Union/etc.
    func: Callable[..., Any] | None = None,
    param_name: str | None = None,
) -> Any:
    """
    Converts a CLI string or list value into the desired Python type.

    Handles:
      - Union / Optional
      - Containers: list, tuple, set, frozenset, dict
      - Enum (strings passed through, let Click handle Choice validation)
      - date/datetime, bool, scalars
    """

    # Resolve postponed annotations if to_type is a string
    if isinstance(to_type, str) and func and param_name:
        type_hints = _safe_get_type_hints(func, include_extras=True)
        to_type = type_hints.get(param_name, to_type)

    # unwrap Annotated[T, ...]
    inspect_ann = to_type
    if get_origin(inspect_ann) is Annotated:
        inspect_ann = get_args(inspect_ann)[0]

    # --- Union / Optional
    origin = get_origin(inspect_ann)
    if origin in (Union, UnionType):
        inner_types = list(get_args(inspect_ann))
        non_none = [t for t in inner_types if t is not type(None)]
        none_in_union = len(non_none) != len(inner_types)

        for inner in non_none:
            try:
                coerced = convert_cli_value_to_type(value, inner, func, param_name)
                if isinstance(inner, type) and isinstance(coerced, inner):
                    return coerced
                if coerced != value:
                    return coerced
            except Exception:
                continue

        if none_in_union and (
            value is None or (isinstance(value, str) and value.strip().lower() in {"", "none", "null"})
        ):
            return None

        return value

    # --- Containers ---
    origin = get_origin(inspect_ann)

    # list[T]
    if origin is list:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return [convert_cli_value_to_type(item, inner, func, param_name) for item in value]
        if isinstance(value, str):
            if "," in value:
                return (
                    [convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")],
                )
            return [convert_cli_value_to_type(value, inner, func, param_name)]
        return [convert_cli_value_to_type(value, inner, func, param_name)]

    # tuple[T,...]
    if origin is tuple and isinstance(value, (list, tuple)):
        args = get_args(inspect_ann)
        if len(args) == 2 and args[1] is Ellipsis:
            inner = args[0]
            return tuple(convert_cli_value_to_type(item, inner, func, param_name) for item in value)
        return tuple(
            convert_cli_value_to_type(item, arg, func, param_name) for item, arg in zip(value, args, strict=False)
        )

    # set[T]
    if origin is set:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return {convert_cli_value_to_type(item, inner, func, param_name) for item in value}
        if isinstance(value, str):
            if "," in value:
                return {convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")}
            return {convert_cli_value_to_type(value, inner, func, param_name)}
        return {convert_cli_value_to_type(value, inner, func, param_name)}

    # dict[K,V] from ["key=val", ...]
    if origin is dict and isinstance(value, (list, tuple)):
        args = get_args(inspect_ann)
        key_t, val_t = (args[0], args[1]) if len(args) >= 2 else (str, Any)
        out: dict[Any, Any] = {}
        for item in value:
            if isinstance(item, str) and "=" in item:
                k_str, v_str = item.split("=", 1)
                k = convert_cli_value_to_type(k_str, key_t, func, param_name)
                v = convert_cli_value_to_type(v_str, val_t, func, param_name)
                out[k] = v
            else:
                raise ValueError(f"Cannot parse dict item {item!r} for {param_name!r}")
        return out

    # frozenset[T]
    if origin is frozenset:
        (inner,) = get_args(inspect_ann) or (Any,)
        if isinstance(value, (list, tuple)):
            return frozenset(convert_cli_value_to_type(item, inner, func, param_name) for item in value)
        if isinstance(value, str):
            if "," in value:
                return frozenset(
                    convert_cli_value_to_type(item.strip(), inner, func, param_name) for item in value.split(",")
                )
            return frozenset((convert_cli_value_to_type(value, inner, func, param_name),))
        return frozenset((convert_cli_value_to_type(value, inner, func, param_name),))

    # --- Scalars ---
    to_type = _normalize_annotation_to_runtime_type(to_type)

    if isinstance(to_type, type) and issubclass(to_type, Enum):
        return cast(Any, value)

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

    if isinstance(to_type, type):
        if value is None:
            return None
        if isinstance(value, to_type):
            return value
        try:
            return to_type(value)
        except Exception:
            return value

    if isinstance(value, str) and value.strip().lower() in {"none", "null", ""}:
        return None
    return value


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
