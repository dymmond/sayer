import inspect
import os
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import (
    IO,
    Annotated,
    Any,
    Optional,
    Sequence,
    Union,
    cast,
    get_args,
    get_origin,
)
from uuid import UUID

import click

from sayer.encoders import MoldingProtocol, get_encoders
from sayer.params import Argument, Env, JsonParam, Option, Param

PRIMITIVE_TYPE_MAP = {
    str: click.STRING,
    int: click.INT,
    float: click.FLOAT,
    bool: click.BOOL,
    UUID: click.UUID,
    date: click.DateTime(formats=["%Y-%m-%d"]),
    datetime: click.DateTime(),
}

SUPPORTS_HIDDEN = "hidden" in inspect.signature(click.Option).parameters


@dataclass
class ParameterContext:
    parameter: inspect.Parameter
    """
    The original `inspect.Parameter` object from the function signature.
    """
    raw_type_annotation: Any
    """
    The raw, un-processed type hint for the parameter (e.g., `Optional[list[str]]`).
    """
    base_type: type
    """
    The underlying base type, potentially normalized (e.g., `str` from `Optional[list[str]]` or a Click `Type` object).
    """
    metadata: Param | Option | Argument | Env | JsonParam | None
    """
    Explicit metadata provided by the user via typing extensions (e.g., `Annotated[str, Option(...)]`),
    or implicitly added.
    """
    help_text: str
    """
    The help string for the parameter, usually extracted from the function's docstring.
    """
    wrapper: Callable
    """
    The wrapper function to which the resulting Click decorator will be applied.
    """
    is_context_injected: bool
    """
    True if the parameter is a Click context object (e.g., `click.Context`) or another form of dependency injection.
    """
    is_overriden_type: bool
    """
    True if the type was explicitly overridden by the user, preventing implicit type mapping (e.g., with `click.STRING`).
    """
    expose: bool = field(init=False)
    """
    Computed: True if the value should be exposed/bound to the function argument; False if it's hidden
    (derived from metadata).
    """
    hidden: bool = field(init=False)
    """
    Computed: True if the parameter should be hidden from the help message (derived from `expose`).
    """
    has_default: bool = field(init=False)
    """
    Computed: True if the parameter has a default value in the Python function signature.
    """
    default: Any = field(init=False)
    """
    Computed: The raw default value from the Python function signature, or `None` if none exists.
    """
    resolved_default: Any = field(init=False)
    """
    Computed: The final, resolved default value considering both the Python signature and explicit metadata defaults.
    """
    is_required: bool = field(init=False)
    """
    Computed: True if the parameter must be provided on the command line, based on metadata and the presence of defaults.
    """

    def __post_init__(self) -> None:
        """Initializes computed attributes after the instance is created.

        This method calculates and sets derived properties such as `expose`,
        `hidden`, `has_default`, `default`, `resolved_default`, and `is_required`
        based on the initial parameter, type, and metadata provided during
        initialization.

        It serves to establish the final state of context properties that guide
        the Click parameter construction process.
        """
        self.expose = getattr(self.metadata, "expose_value", True)
        self.hidden = not self.expose

        # restore compatibility
        self.has_default = self.parameter.default not in (inspect._empty, Ellipsis)
        self.default = self.parameter.default if self.has_default else None

        self.resolved_default = self._resolve_default()
        self.is_required = self._resolve_required()

    def _resolve_default(self) -> Any:
        """Determines the effective default value for the parameter.

        The resolution follows a priority:
        1. Explicit `default` value in the metadata (e.g., `Param(default=...)`).
           If `default_factory` is used in metadata, the default is considered `None`.
           If the metadata default value is itself a metadata object (e.g., `Option`), it's ignored.
        2. Default value provided in the Python function signature.
        3. If neither is found, the resolved default is `None`.

        Returns:
            The final default value to be used by Click, or `None`.
        """
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
        """Determines if the parameter should be considered 'required' by Click.

        The determination is based on the following precedence:
        1. **Explicit Metadata Flag**: If the metadata (Param, Option, etc.) explicitly sets
            `required=True` or `required=False`, that value is final.
        2. **Absence of Default**: If no explicit `required` flag is set, the parameter is
            considered **required** if and only if it has no default value (neither in the Python signature
            nor in the metadata).
        3. **Presence of Default**: If any form of default (Python signature or metadata) is present,
            the parameter is considered **optional** (`required=False`).

        Returns:
            True if the parameter is required, False otherwise.
        """
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

        if self.resolved_default is not None:  # type: ignore
            return False
        if self.has_default:
            return False

        return True

    def normalize_type(self) -> None:
        """Performs in-place adjustments to the parameter's type and metadata.

        Two main normalizations are performed:
        1. **Unwrap Optional**: If the `base_type` is an `Optional[T]` (i.e., `Union[T, None]`),
           it strips the `None` type and sets `self.base_type` to `T`.
        2. **Infer Option Style**: If the parameter has generic `Param` metadata and is
           annotated via `Annotated`, it checks if the parameter configuration (including defaults)
           suggests it should be treated as a Click option rather than a positional argument,
           and converts the `Param` metadata to `Option` metadata in-place if necessary.
        """
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


def _handle_variadic_args(ctx: ParameterContext) -> Optional[Callable]:
    """Handles implicit variadic positional arguments like `*args` or `argv`.

    This function specifically looks for the common pattern of a function parameter
    intended to capture an unbounded list of positional arguments, typically named
    `args` or `argv`, and typed as a sequence (like `list` or `tuple`).

    Key actions performed:
    1. **Implicit Variadic Check**:
        - Checks if no explicit metadata is present (`ctx.metadata is None`).
        - Checks if the parameter's type is a generic sequence (`list` or `tuple`).
        - Checks if the parameter's name is one of the conventional variadic names (`"args"` or `"argv"`).
    2. **Inner Type Resolution**: Extracts the inner type `T` from the sequence
       (e.g., `str` from `list[str]`) and maps it to a primitive Click type.
    3. **Decorator Creation**: If the pattern is matched, it creates a `click.argument`
       decorator with **`nargs=-1`**, which instructs Click to collect all remaining
       positional arguments into a list. The argument is set as `required=False`
       since variadic arguments are generally optional.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.argument` decorator) if the parameter
        matches the implicit variadic argument pattern, otherwise `None` to pass
        control to the next handler.
    """
    base_origin = get_origin(ctx.base_type)
    if ctx.metadata is None and base_origin in (list, tuple) and ctx.parameter.name in {"args", "argv"}:
        inner_args = get_args(ctx.base_type)
        inner_type = inner_args[0] if inner_args else str
        click_inner_type = PRIMITIVE_TYPE_MAP.get(inner_type, click.STRING)
        return click.argument(
            ctx.parameter.name,
            nargs=-1,
            type=click_inner_type,
            required=False,
            expose_value=ctx.expose,
        )(ctx.wrapper)
    return None


def _handle_sequence(ctx: ParameterContext) -> Optional[Callable]:
    """Handles parameter configuration for sequence types (e.g., `list[T]` or `Sequence[T]`).

    This function determines how to map a sequence type (like `list` or `Sequence`)
    to the appropriate Click construct, which is either a **variadic positional
    argument** or a **multi-value option** (using `multiple=True`).

    Key actions performed:
    1. **Type Check**: Verifies that the base type is a generic type whose origin is `list` or `Sequence`.
    2. **Inner Type Resolution**: Extracts the inner type `T` from the sequence (e.g., `str` from `list[str]`)
       and maps it to a primitive Click type (e.g., `click.STRING`).
    3. **Argument Handling (`Argument` metadata)**:
        - If the parameter has explicit `Argument` metadata, it's treated as a **positional argument**.
        - It checks for `nargs` in the metadata to determine if it's variadic (`-1` or $>1$).
        - The `type` is set to the inner Click type, allowing Click to collect multiple values.
    4. **Option Handling (Default)**:
        - If there is no explicit `Argument` metadata, it's treated as a **multi-value option**.
        - The `multiple=True` flag is set on `click.option`, instructing Click to
          accept the option multiple times on the command line (e.g., `--name a --name b`).
        - The default value is set to an empty tuple `()` if none is provided.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured Click decorator) if the parameter is a
        sequence type, otherwise `None` to pass control to the next handler.
    """
    base_origin = get_origin(ctx.base_type)
    if base_origin not in (list, Sequence):
        return None

    inner_args = get_args(ctx.base_type)
    inner_type = inner_args[0] if inner_args else str
    click_inner_type = PRIMITIVE_TYPE_MAP.get(inner_type, click.STRING)

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
    """Handles parameter configuration for Python `Enum` types by converting them to Click `Choice` options.

    This function is responsible for correctly mapping a Python `Enum` class
    to a `click.option` that uses a **`click.Choice`** type. This ensures that
    users can only provide one of the valid enum values (which are derived
    from the enum members' values).

    Key actions performed:
    1. **Type Check**: Verifies that the `ctx.base_type` is a class and is a
       subclass of `enum.Enum`.
    2. **Choice Creation**: Extracts the **`.value`** of every member in the enum
       to create the list of valid choices for Click.
    3. **Default Normalization**: If a Python default is present and it is an
       `Enum` instance, its `.value` is extracted to be used as the Click default.
    4. **Decorator Creation**: Constructs the `click.option` decorator, setting
       the `type` to `click.Choice(enum_choices)` (unless the type was overridden)
       and applying the normalized default and other context parameters.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.option` decorator) if the parameter
        is an `Enum` type, otherwise `None` to pass control to the next handler.
    """
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
    """Handles parameter configuration for complex types that should be passed via JSON string options.

    This function determines if a parameter should be treated as a JSON input,
    either through explicit `JsonParam` metadata or by implicitly detecting a
    complex type that can be molded (deserialized) but isn't a simple built-in
    or specialized type (like `Path` or `UUID`).

    Key actions performed:
    1. **Implicit JSON Detection**:
        - Checks if no explicit metadata is present (`ctx.metadata is None`).
        - Skips detection if the base type is a **simple type** (like `str`, `int`, `bool`, etc.).
        - If the base type is a class and an available **encoder/molder** can handle
          its structure, it implicitly assigns `JsonParam` metadata to the context.
    2. **Explicit JSON Handling**:
        - If `ctx.metadata` is `JsonParam` (either implicit or explicit), it configures
          the parameter as a `click.option`.
        - **Type Setting**: The Click type is set to **`click.STRING`** (to accept raw JSON),
          unless the type was explicitly overridden.
        - **Help Text Annotation**: Appends **`(JSON)`** to the help text to inform the user
          that the value must be provided as a JSON string.
        - **Decorator Creation**: Creates and applies the `click.option` decorator.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.option` decorator) if the parameter is
        identified as a JSON-input option, otherwise `None`.
    """
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

        return click.option(
            f"--{ctx.parameter.name.replace('_', '-')}",
            **cast(dict[str, Any], kwargs),
        )(ctx.wrapper)
    return None


def _handle_special_types(ctx: ParameterContext) -> None:
    """Adjusts the parameter's base type in-place for specific well-known Python types to their Click equivalents.

    This internal handler checks the parameter's determined base type and, if it
    matches a special type (like standard library types or common interfaces),
    it replaces the Python type with a corresponding Click type object. This is
    necessary because Click uses custom type classes (`click.Path`, `click.UUID`,
    `click.DateTime`, etc.) to perform input validation and conversion from
    command-line strings.

    The conversions performed are:
    - **`pathlib.Path`**: Converted to `click.Path(exists=False, ..., resolve_path=True)`.
    - **`uuid.UUID`**: Converted to `click.UUID`.
    - **`datetime.date`**: Converted to `click.DateTime` with the format `"%Y-%m-%d"`.
    - **`datetime.datetime`**: Converted to a generic `click.DateTime`.
    - **`typing.IO` or `click.File`**: Converted to `click.File("r")` for file reading.

    Args:
        ctx: The `ParameterContext` object, whose `base_type` attribute is modified
             in-place if a special type conversion is necessary.

    Returns:
        None: The function modifies the context object directly.
    """
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
    """Handles parameter configuration when explicit `Argument` metadata is present.

    This function processes parameters that are explicitly marked with `Argument`
    metadata, configuring them as a `click.argument`. It enforces the rules
    specific to positional arguments and incorporates metadata-provided options.

    Key actions performed:
    1. **Metadata Check**: Verifies that `ctx.metadata` is an instance of `Argument`.
    2. **Default Sanitization**: Cleans up the `final_default` value, setting it to `None`
       if it's one of the other metadata objects, as they shouldn't be used as a simple default.
    3. **Variadic Constraint**: Raises a `ValueError` if the user attempts to combine
       variadic argument configuration (`nargs` in options) with a Python default value,
       as this is unsupported by Click's argument definition.
    4. **Keyword Argument Construction**: Builds the keyword arguments for `click.argument`,
       merging options from `ctx.metadata.options` with essential Click parameters:
        - `type`: The resolved base type.
        - `required`: Determined by metadata, falling back to whether the parameter has a default in Python.
        - `expose_value`: Determined by metadata, defaulting to `True`.
    5. **Help Text Injection**: Applies the help text from the metadata to the
       resulting `click.Argument` object within the decorated function's `params` list,
       as `click.argument` itself doesn't directly take a `help` argument.
    6. **Decorator Creation**: Creates and applies the `click.argument` decorator.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.argument` decorator) if `Argument` metadata
        is found, otherwise `None` to pass control to the next handler.

    Raises:
        ValueError: If `nargs` is specified in `Argument` metadata and a default
            value is also present.
    """
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
    """Handles parameter configuration when explicit `Env` metadata is present.

    This function processes parameters that are explicitly marked with the `Env`
    metadata, indicating that the parameter's value should primarily be read
    from a specified environment variable. It configures the parameter as a
    `click.option`, merging the environment logic with standard option settings.

    Key actions performed:
    1. **Metadata Check**: Verifies that `ctx.metadata` is an instance of `Env`.
    2. **Environment Lookup**: Uses `os.getenv` to look up the value from the
       specified environment variable (`ctx.metadata.envvar`). If the environment
       variable is not set, it falls back to the default specified in the `Env` metadata.
    3. **Default Handling**: The resolved environment/metadata default value is
       set as the `default` for the `click.option`, unless a `default_factory`
       is present in the metadata (in which case `default` is set to `None` and
       the factory logic is expected to handle it elsewhere).
    4. **Help Text Annotation**: The help text is prepended with `[env:...]`
       to clearly indicate the environment variable source to the user.
    5. **Decorator Creation**: Constructs the final `click.option` decorator,
       combining the environment logic with other properties like `type`, `required`,
       `show_default`, and additional options provided in `ctx.metadata.options`.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.option` decorator) if `Env` metadata
        is found, otherwise `None` to pass control to the next handler.
    """
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
    """Handles parameter configuration when explicit `Option` metadata is present.

    This function processes parameters that are explicitly marked with `Option`
    metadata, overriding default behavior and providing detailed configuration
    for a `click.option`.

    Key actions performed:
    1. **Metadata Check**: Verifies that `ctx.metadata` is an instance of `Option`.
    2. **Type Cleanup**: Handles `Annotated[T, ...]` and `Optional[T]` (`Union[T, None]`)
       to extract the true base type `T` for use in the Click option's `type` parameter.
    3. **Default Resolution**:
        - If `default_factory` is used in metadata, the Click default is set to `None`.
        - Otherwise, it uses the resolved Python default (`ctx.resolved_default`).
        - Handles a specific edge case where `is_flag` is `True` and the default is `True`,
          setting Click's default to `None` to let Click properly handle the flag negation.
    4. **Decorator Creation**: Constructs the final `click.option` decorator,
       merging options provided in the metadata (`ctx.metadata.options`) with
       standard Click parameters like `type`, `is_flag`, `required`, `help`,
       `prompt`, and environment variable settings.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.option` decorator) if `Option` metadata
        is found, otherwise `None` to pass control to the next handler.
    """
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
    """Handles parameters explicitly typed as 'bool' by converting them to Click boolean flags.

    This handler is specifically designed for **pure boolean parameters**
    (where the resolved base type is `bool`). It configures the parameter
    as a `click.option` using `is_flag=True`, which automatically creates
    the `--name / --no-name` pair for toggling.

    Key actions performed:
    1. **Type Check**: Ensures the parameter's base type is exactly `bool`.
    2. **Default Normalization**: Converts the resolved default value (if present)
       to an actual Python boolean (`True` or `False`), falling back to `False`
       if no default is specified, to guarantee flag behavior.
    3. **Decorator Creation**: Creates a `click.option` decorator with the
       `is_flag`, `default`, and other context-derived options.

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured `click.option` decorator) if the parameter
        is a boolean, otherwise `None` to pass control to the next handler.
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
        **cast(dict[str, Any], kwargs),
    )(ctx.wrapper)


def _handle_defaults(ctx: ParameterContext) -> Optional[Callable]:
    """Handles parameter configuration based primarily on its default value and context.

    This function acts as a **fallback** handler, executing when no explicit
    metadata (like `Param`, `Option`, or `Argument`) was provided for the
    parameter. It decides whether to treat the parameter as a required
    positional argument, an optional flag, or an option with a default value.

    The decision logic is as follows:
    1. **Required Positional Argument**: If the parameter has no metadata, is
       required (no default in the signature), and is not context-injected.
    2. **Context-Injected Option**: If the parameter is context-injected (e.g., a
       dependency-injected value), it's treated as an optional option with a default.
    3. **Optional Option (Explicit None)**: If the default value is explicitly `None`,
       it's treated as an optional option.
    4. **Boolean Flag**: If the type is `bool` and a boolean default is provided,
       it's treated as a standard `--flag/--no-flag` option.
    5. **Positional Argument with Default**: The final fallback is a positional
       argument with a default value (making it technically optional).

    Args:
        ctx: The `ParameterContext` object containing all relevant parameter information.

    Returns:
        A callable (the configured Click decorator) if a mapping is found,
        otherwise `None` to allow subsequent handlers to run (though this is
        usually the last handler).
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
