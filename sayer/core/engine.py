import inspect
import json
import os
import sys
import types
from datetime import date, datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import (
    IO,
    Annotated,
    Any,
    Callable,
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


def _convert_cli_value_to_type(value: Any, to_type: type, func: Any = None, param_name: str = None) -> Any:
    """
    Converts a command-line interface (CLI) input value into the desired Python type.

    This helper function handles specific type conversions:
    - `Enum`: Leaves `Enum` values as strings to be validated by `Click.Choice`.
    - `date`: Converts `datetime` objects to `date` objects if the target type is `date`.
    - `bool`: Parses common string representations of booleans (`"true"`, `"1"`,
      `"yes"`, `"on"`) into actual boolean values.
    - Falls back to direct type casting for other types if the value is not
      already of the target type.

    Args:
        value: The input value received from the CLI.
        to_type: The target Python type to convert the value to.

    Returns:
        The converted value, or the original value if no conversion is necessary
        or possible.
    """
    # Resolve postponed annotations if to_type is a string
    if isinstance(to_type, str) and func and param_name:
        # Use get_type_hints to resolve actual type
        type_hints = get_type_hints(func, globalns=sys.modules[func.__module__].__dict__)
        to_type = type_hints.get(param_name, to_type)

    # --- container types support ---
    origin = get_origin(to_type)
    # list[T]
    if origin is list and isinstance(value, (list, tuple)):
        inner = get_args(to_type)[0]
        return [_convert_cli_value_to_type(item, inner, func, param_name) for item in value]
    # tuple[T, ...] or Tuple[T1, T2, ...]
    if origin is tuple and isinstance(value, (list, tuple)):
        args = get_args(to_type)
        # homogeneous: Tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            inner = args[0]
            return tuple(_convert_cli_value_to_type(item, inner, func, param_name) for item in value)
        # heterogeneous: Tuple[T1, T2, ...]
        return tuple(
            _convert_cli_value_to_type(item, arg_type, func, param_name)
            for item, arg_type in zip(value, args, strict=False)
        )
    # set[T]
    if origin is set and isinstance(value, (list, tuple)):
        inner = get_args(to_type)[0]
        return {_convert_cli_value_to_type(item, inner, func, param_name) for item in value}
    # dict[K, V] from ["key=val", ...]
    if origin is dict and isinstance(value, (list, tuple)):
        key_t, val_t = get_args(to_type)
        d: dict[Any, Any] = {}
        for item in value:
            if isinstance(item, str) and "=" in item:
                k_str, v_str = item.split("=", 1)
                k = _convert_cli_value_to_type(k_str, key_t, func, param_name)
                v = _convert_cli_value_to_type(v_str, val_t, func, param_name)
                d[k] = v
            else:
                raise ValueError(f"Cannot parse dict item {item!r} for {param_name!r}")
        return d

    # frozenset[T]
    if origin is frozenset and isinstance(value, (list, tuple)):
        inner = get_args(to_type)[0]
        return frozenset(_convert_cli_value_to_type(item, inner, func, param_name) for item in value)

    if isinstance(to_type, type) and issubclass(to_type, Enum):
        return value
    if to_type is date and isinstance(value, datetime):
        return value.date()
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if isinstance(value, to_type):
        return value
    return to_type(value)  # type: ignore


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
    Dynamically attaches a Click argument or option decorator to a command
    wrapper function based on the Python function's parameter definition.

    This function supports a wide range of parameter configurations, including:
    - Primitive types (`str`, `int`, `float`, `bool`).
    - Specific types like `Path`, `UUID`, `date`, `datetime`, and `file-like` objects (`IO`).
    - `Enum` types, which are handled as `Click.Choice` options.
    - Collection types like `list` and `Sequence`, mapped to Click's `multiple` options.
    - Implicit JSON injection for dataclasses, Pydantic models, or `msgspec` types
      if a relevant `MoldingProtocol` encoder is registered.
    - Explicit parameter metadata (`Argument`, `Env`, `Option`, `Param`, `JsonParam`)
      to control Click's behavior (e.g., prompts, hidden input, environment variables).
    - Boolean flags, and automatic fallback from positional arguments to options
      if a default value is present.
    - Context-aware default behavior for specific scenarios.

    The order of checks is significant, with more specific metadata or type
    handlers taking precedence.

    Args:
        parameter: The `inspect.Parameter` object for the current function parameter.
        raw_type_annotation: The raw type annotation of the parameter, including
                        any `Annotated` wrappers.
        parameter_base_type: The resolved base type of the parameter (e.g., `str`, `int`,
                    `MyDataclass`).
        parameter_metadata: Optional metadata object (`Param`, `Option`, `Argument`, `Env`,
              `JsonParam`) providing specific Click configuration.
        param_help_text: The extracted help text for the parameter.
        click_wrapper_function: The Click command wrapper function to which the parameter
                 decorator will be applied.
        is_context_injected: A boolean indicating if `click.Context` is injected into
                      the command, which can influence default parameter behavior.

    Returns:
        The `click_wrapper_function`, now decorated with the appropriate Click
        argument or option.
    """
    parameter_name = parameter.name
    origin = get_origin(parameter_base_type)
    if origin in (Union, types.UnionType):
        args = get_args(parameter_base_type)
        non_none = [t for t in args if t is not type(None)]
        if len(non_none) == 1:
            # If the parameter is a Union with only one non-None type, use that type.
            parameter_base_type = non_none[0]

    is_boolean_flag = parameter_base_type is bool
    has_default_value = parameter.default not in [inspect._empty, Ellipsis]
    resolved_default_value = parameter.default if has_default_value else None

    # Param(...) annotated as generic → Option if criteria met
    # If a generic `Param` metadata is provided via `Annotated` and
    # `_should_parameter_use_option_style` evaluates to True, it's re-cast as an `Option`.
    if (
        isinstance(parameter_metadata, Param)
        and get_origin(raw_type_annotation) is Annotated
        and _should_parameter_use_option_style(parameter_metadata, resolved_default_value)
    ):
        parameter_metadata = parameter_metadata.as_option()

    type_origin = get_origin(raw_type_annotation)

    # 1) list[T] or Sequence[T] → --name multiple
    if type_origin in (list, Sequence):
        # For list or Sequence types, extract the inner type (e.g., `int` from `list[int]`).
        inner_type = get_args(raw_type_annotation)[0]
        # Map the inner type to a Click primitive type, defaulting to STRING.
        click_inner_type = _PRIMITIVE_TYPE_MAP.get(inner_type, click.STRING)
        # Set default for sequences to an empty tuple if no default is provided.
        default_for_sequence = () if not has_default_value else parameter.default
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=click_inner_type if not is_overriden_type else parameter_base_type,
            multiple=True,
            default=default_for_sequence,
            show_default=True,
            help=param_help_text,
        )(click_wrapper_function)

    # 2) Enum → --name Choice([...])
    if isinstance(parameter_base_type, type) and issubclass(parameter_base_type, Enum):
        # For Enum types, create Click.Choice from enum member values.
        enum_choices = [e.value for e in parameter_base_type]
        enum_default_value = None
        if has_default_value:
            # Resolve the default value for Enums, handling both enum member or raw value.
            enum_default_value = parameter.default.value if isinstance(parameter.default, Enum) else parameter.default
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=click.Choice(enum_choices) if not is_overriden_type else parameter_base_type,
            default=enum_default_value,
            show_default=True,
            help=param_help_text,
        )(click_wrapper_function)

    # 2.4) Implicit JSON injection for any type your encoders can mold!
    #      If no Param/Option/Argument/Env given, and the bare Python class
    #      is moldable by one of our MoldingProtocol encoders, inject JsonParam.
    simple_types = (str, bool, int, float, Enum, Path, UUID, date, datetime)
    skip_implicit_json = isinstance(parameter_base_type, type) and issubclass(parameter_base_type, simple_types)
    if (
        parameter_metadata is None
        and not skip_implicit_json
        and inspect.isclass(parameter_base_type)
        and any(
            isinstance(encoder, MoldingProtocol) and encoder.is_type_structure(parameter_base_type)
            for encoder in get_encoders()
        )
    ):
        parameter_metadata = JsonParam()

    # 2.5) Explicit JsonParam → JSON string option
    if isinstance(parameter_metadata, JsonParam):
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=click.STRING if not is_overriden_type else parameter_base_type,
            default=parameter_metadata.default,
            required=parameter_metadata.required,
            show_default=False,
            help=f"{param_help_text} (JSON)",
        )(click_wrapper_function)

    # 3) Path support
    if parameter_base_type is Path:
        parameter_base_type = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)

    # 4) UUID support
    if parameter_base_type is UUID:
        parameter_base_type = click.UUID

    # 5) date support
    if parameter_base_type is date:
        parameter_base_type = click.DateTime(formats=["%Y-%m-%d"])

    # 6) datetime support
    if parameter_base_type is datetime:
        parameter_base_type = click.DateTime()

    # 7) File IO support
    if raw_type_annotation is IO or raw_type_annotation is click.File:
        parameter_base_type = click.File("r")

    # Compute final default & required
    has_metadata_default = getattr(parameter_metadata, "default", ...) not in [..., Ellipsis]
    final_default_value = getattr(parameter_metadata, "default", resolved_default_value)

    if final_default_value is Ellipsis:
        final_default_value = None

    if isinstance(final_default_value, Enum):
        final_default_value = final_default_value.value
    if isinstance(final_default_value, (date, datetime)):
        final_default_value = final_default_value.isoformat()

    # Determine if the parameter is required based on default presence and metadata.
    is_required = getattr(parameter_metadata, "required", not (has_default_value or has_metadata_default))
    # Combine metadata help with general help text.
    effective_help_text = getattr(parameter_metadata, "help", param_help_text) or param_help_text

    # --- Explicit metadata cases ---
    # Apply specific Click decorators based on the explicit metadata type.
    if isinstance(parameter_metadata, Argument):
        if "nargs" in parameter_metadata.options:
            # If nargs is -1, it means this is a variadic argument (accepts multiple values).
            # Click will handle this as a tuple.
            if final_default_value and final_default_value not in (inspect._empty, ...):
                raise ValueError("Variadic arguments (nargs) cannot have a default value.")
        else:
            parameter_metadata.options["default"] = final_default_value

        wrapped = click.argument(
            parameter_name,
            type=parameter_base_type,
            required=is_required,
            **parameter_metadata.options,
        )(click_wrapper_function)

        # Now inject our help text into the click.Argument instance
        help_text = getattr(parameter_metadata, "help", "")
        if hasattr(wrapped, "params"):
            for param_obj in wrapped.params:
                if isinstance(param_obj, click.Argument) and param_obj.name == parameter_name:
                    param_obj.help = help_text
        return wrapped

    if isinstance(parameter_metadata, Env):
        # For Env parameters, retrieve value from environment or use metadata default.
        env_resolved_value = os.getenv(parameter_metadata.envvar, parameter_metadata.default)
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=parameter_base_type,
            # If default_factory exists, default is None for Click to handle factory.
            default=(None if getattr(parameter_metadata, "default_factory", None) else env_resolved_value),
            show_default=True,
            required=parameter_metadata.required,
            help=f"[env:{parameter_metadata.envvar}] {effective_help_text}",
            **parameter_metadata.options,
        )(click_wrapper_function)

    if isinstance(parameter_metadata, Option):
        # figure out default
        option_default = None if getattr(parameter_metadata, "default_factory", None) else final_default_value
        # if it's not required and default is None, we want Click to skip parsing
        # entirely and just hand us None, so we *don't* accidentally interpret
        # the option name as its own value.
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            *parameter_metadata.param_decls,
            type=None if is_boolean_flag else parameter_base_type,
            is_flag=is_boolean_flag,
            default=option_default,
            required=is_required,
            show_default=parameter_metadata.show_default,
            help=effective_help_text,
            prompt=parameter_metadata.prompt,
            hide_input=parameter_metadata.hide_input,
            callback=parameter_metadata.callback,
            envvar=parameter_metadata.envvar,
            **parameter_metadata.options,
        )(click_wrapper_function)

    # --- General fallback logic ---
    # These are default behaviors if no explicit metadata is provided.
    if not has_default_value:
        # If no default, it's a required positional argument.
        return click.argument(parameter_name, type=parameter_base_type, required=True)(click_wrapper_function)

    if is_context_injected and not is_boolean_flag:
        # If context is injected and it's not a boolean flag, it's an option.
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=parameter_base_type,
            default=final_default_value,
            required=is_required,
            show_default=True,
            help=effective_help_text,
        )(click_wrapper_function)

    if is_boolean_flag and isinstance(parameter.default, bool):
        # Boolean flags with a default boolean value.
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            is_flag=True,
            default=parameter.default,
            show_default=True,
            help=effective_help_text,
        )(click_wrapper_function)

    if isinstance(parameter.default, Param):
        # `Param` as a default value means it's an optional argument with a default.
        return click.argument(
            parameter_name,
            type=parameter_base_type,
            required=False,
            default=parameter.default.default,
        )(click_wrapper_function)

    if parameter.default is None:
        # Parameters with a `None` default become optional options.
        return click.option(
            f"--{parameter_name.replace('_', '-')}",
            type=parameter_base_type,
            default=None,
            show_default=True,
            help=effective_help_text,
        )(click_wrapper_function)

    # Final fallback: optional positional with default
    # If none of the above conditions are met, it defaults to an optional
    # positional argument with its default value.
    final_wrapped_function = click.argument(
        parameter_name, type=parameter_base_type, default=final_default_value, required=False
    )(click_wrapper_function)

    # Ensure the Click parameter reflects the optional nature and default.
    for param_in_wrapper in final_wrapped_function.params:
        if param_in_wrapper.name == parameter_name:
            param_in_wrapper.required = False
            param_in_wrapper.default = final_default_value
    return final_wrapped_function


@overload
def command(func: F) -> click.Command: ...


@overload
def command(
    func: F | None = None,
    *args: Any,
    middleware: Sequence[str | Callable[..., Any]] | None = None,
    **attrs: Any,
) -> click.Command | Callable[[F], click.Command]: ...


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
                if get_origin(raw_type_for_conversion) not in (list, Sequence):
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

            return execution_result

        click_command_wrapper._original_func = function_to_decorate
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

    Returns:
        A `click.Group` instance, either newly created or retrieved from the
        internal registry.
    """
    # Check if the group already exists to avoid re-creating it.
    if name not in _GROUPS:
        # Determine the group class to use; default to `SayerGroup`.
        group_class_to_use = group_cls or SayerGroup
        # Create the Click group instance.
        new_group_instance = group_class_to_use(name=name, help=help)

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
                return cast(click.Command, command(func_to_bind, **opts))

            def inner_decorator(function_to_decorate_for_group: F) -> click.Command:
                # If used as `@group.command(...)`, return a decorator that
                # first marks the function with the group, then applies `sayer.command`.
                function_to_decorate_for_group.__sayer_group__ = new_group_instance  # type: ignore
                return cast(click.Command, command(function_to_decorate_for_group, **opts))

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
        return cast(click.Command, command(fn, *args, **attrs))

    if function_to_bind and callable(function_to_bind) and not args and not attrs:
        return decorator(function_to_bind)
    return cast(click.Command, decorator)


# Monkey-patch Click so that all groups use Sayer’s binding logic:
# This crucial line ensures that any `click.Group` created (even outside
# `sayer.group`) will use `sayer`'s `bind_command_to_group` when its `.command`
# method is called. This globally enables `sayer`'s enhanced command
# features for all Click groups in the application.
click.Group.command = bind_command_to_group  # type: ignore
