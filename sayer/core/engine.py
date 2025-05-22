import inspect
import json
import os
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import (
    IO,
    Annotated,
    Any,
    Callable,
    Sequence,
    TypeVar,
    cast,
    get_args,
    get_origin,
    overload,
)
from uuid import UUID

import anyio
import click

from sayer.encoders import MoldingProtocol, apply_structure, get_encoders
from sayer.middleware import resolve as resolve_middleware, run_after, run_before
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State, get_state_classes
from sayer.utils.ui import RichGroup

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
    if isinstance(to_type, type) and issubclass(to_type, Enum):
        # Enum values are passed as strings for Click.Choice validation.
        return value
    if to_type is date and isinstance(value, datetime):
        # Convert datetime objects to date objects if the target is date.
        return value.date()
    if to_type is bool:
        # Handle boolean string conversions.
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    if isinstance(value, to_type):
        # If the value is already of the target type, return it as is.
        return value
    # Attempt direct type casting as a fallback.
    return to_type(value)  # type: ignore


def _should_use_option(meta: Param, default_value: Any) -> str | bool:
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
        meta: The `Param` metadata object associated with the parameter.
        default_value: The default value of the parameter as defined in the
                       function signature.

    Returns:
        True if the parameter should be an option; False otherwise.
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
    # 1. Function docstring
    txt = inspect.getdoc(func) or ""
    if txt:
        return txt
    # 2. Param(help=...) metadata from default values
    for p in signature.parameters.values():
        if isinstance(p.default, Param) and p.default.help:
            return p.default.help
        # 3. Annotated[..., Param(help=...)] metadata
        anno = p.annotation
        if get_origin(anno) is Annotated:
            for m in get_args(anno)[1:]:
                if isinstance(m, Param) and m.help:
                    return m.help
    return ""


def _build_click_parameter(
    param: inspect.Parameter,
    raw_annotation: Any,
    param_type: type,
    meta: Param | Option | Argument | Env | JsonParam | None,
    help_text: str,
    wrapper: Callable,
    ctx_injected: bool,
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
        param: The `inspect.Parameter` object for the current function parameter.
        raw_annotation: The raw type annotation of the parameter, including
                        any `Annotated` wrappers.
        param_type: The resolved base type of the parameter (e.g., `str`, `int`,
                    `MyDataclass`).
        meta: Optional metadata object (`Param`, `Option`, `Argument`, `Env`,
              `JsonParam`) providing specific Click configuration.
        help_text: The extracted help text for the parameter.
        wrapper: The Click command wrapper function to which the parameter
                 decorator will be applied.
        ctx_injected: A boolean indicating if `click.Context` is injected into
                      the command, which can influence default parameter behavior.

    Returns:
        The `wrapper` function, now decorated with the appropriate Click
        argument or option.
    """
    name = param.name
    is_flag = param_type is bool
    has_default = param.default is not inspect._empty
    default_val = param.default if has_default else None

    # Param(...) annotated as generic → Option if criteria met
    # If a generic `Param` metadata is provided via `Annotated` and
    # `_should_use_option` evaluates to True, it's re-cast as an `Option`.
    if (
        isinstance(meta, Param)
        and get_origin(raw_annotation) is Annotated
        and _should_use_option(meta, default_val)
    ):
        meta = meta.as_option()

    origin = get_origin(raw_annotation)

    # 1) list[T] or Sequence[T] → --name multiple
    if origin in (list, Sequence):
        # For list or Sequence types, extract the inner type (e.g., `int` from `list[int]`).
        inner = get_args(raw_annotation)[0]
        # Map the inner type to a Click primitive type, defaulting to STRING.
        click_inner = _PRIMITIVE_MAP.get(inner, click.STRING)
        # Set default for sequences to an empty tuple if no default is provided.
        default_seq = () if not has_default else param.default
        return click.option(
            f"--{name.replace('_','-')}",  # Option name derived from parameter name.
            type=click_inner,
            multiple=True,  # Enable multiple values for sequences.
            default=default_seq,
            show_default=True,  # Display default value in help.
            help=help_text,
        )(wrapper)

    # 2) Enum → --name Choice([...])
    if isinstance(param_type, type) and issubclass(param_type, Enum):
        # For Enum types, create Click.Choice from enum member values.
        choices = [e.value for e in param_type]
        enum_def = None
        if has_default:
            # Resolve the default value for Enums, handling both enum member or raw value.
            enum_def = param.default.value if isinstance(param.default, Enum) else param.default
        return click.option(
            f"--{name.replace('_','-')}",
            type=click.Choice(choices),  # Restrict input to defined enum choices.
            default=enum_def,
            show_default=True,
            help=help_text,
        )(wrapper)

    # 2.4) Implicit JSON injection for any type your encoders can mold!
    #      If no Param/Option/Argument/Env given, and the bare Python class
    #      is moldable by one of our MoldingProtocol encoders, inject JsonParam.
    simple = (str, bool, int, float, Enum, Path, UUID, date, datetime)
    skip_json = isinstance(param_type, type) and issubclass(param_type, simple)
    if (
        meta is None
        and not skip_json
        and inspect.isclass(param_type)
        and any(
            isinstance(enc, MoldingProtocol) and enc.is_type_structure(param_type)
            for enc in get_encoders()
        )
    ):
        meta = JsonParam()  # If moldable and no explicit meta, treat as JSON.

    # 2.5) Explicit JsonParam → JSON string option
    if isinstance(meta, JsonParam):
        return click.option(
            f"--{name.replace('_', '-')}",
            type=click.STRING,  # JSON is always passed as a string.
            default=meta.default,
            required=meta.required,
            show_default=False,  # Avoid showing potentially long JSON default in help.
            help=f"{help_text} (JSON)",
        )(wrapper)

    # 3) Path support
    if param_type is Path:
        param_type = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)

    # 4) UUID support
    if param_type is UUID:
        param_type = click.UUID

    # 5) date support
    if param_type is date:
        param_type = click.DateTime(formats=["%Y-%m-%d"])

    # 6) datetime support
    if param_type is datetime:
        param_type = click.DateTime()

    # 7) File IO support
    if raw_annotation is IO or raw_annotation is click.File:
        param_type = click.File("r")

    # Compute final default & required
    has_meta_def = getattr(meta, "default", ...) is not ...
    final_default = getattr(meta, "default", default_val)
    if isinstance(final_default, Enum):
        final_default = final_default.value  # Convert Enum default to its value.
    if isinstance(final_default, (date, datetime)):
        final_default = final_default.isoformat()  # Convert date/datetime to ISO string.

    # Determine if the parameter is required based on default presence and metadata.
    required = getattr(meta, "required", not (has_default or has_meta_def))
    # Combine metadata help with general help text.
    effective_help = getattr(meta, "help", help_text) or help_text

    # --- Explicit metadata cases ---
    # Apply specific Click decorators based on the explicit metadata type.
    if isinstance(meta, Argument):
        return click.argument(name, type=param_type, required=required, default=final_default)(
            wrapper
        )

    if isinstance(meta, Env):
        # For Env parameters, retrieve value from environment or use metadata default.
        env_val = os.getenv(meta.envvar, meta.default)
        return click.option(
            f"--{name.replace('_','-')}",
            type=param_type,
            # If default_factory exists, default is None for Click to handle factory.
            default=None if getattr(meta, "default_factory", None) else env_val,
            show_default=True,
            required=meta.required,
            help=f"[env:{meta.envvar}] {effective_help}",  # Add envvar info to help.
        )(wrapper)

    if isinstance(meta, Option):
        # For Option parameters, handle specific option attributes.
        opt_def = None if getattr(meta, "default_factory", None) else final_default
        return click.option(
            f"--{name.replace('_','-')}",
            type=None if is_flag else param_type,  # Flag options don't need a type.
            is_flag=is_flag,
            default=opt_def,
            required=required,
            show_default=meta.show_default,
            help=effective_help,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar,
        )(wrapper)

    # --- General fallback logic ---
    # These are default behaviors if no explicit metadata is provided.
    if not has_default:
        # If no default, it's a required positional argument.
        return click.argument(name, type=param_type, required=True)(wrapper)

    if ctx_injected and not is_flag:
        # If context is injected and it's not a boolean flag, it's an option.
        return click.option(
            f"--{name.replace('_','-')}",
            type=param_type,
            default=final_default,
            required=required,
            show_default=True,
            help=effective_help,
        )(wrapper)

    if is_flag and isinstance(param.default, bool):
        # Boolean flags with a default boolean value.
        return click.option(
            f"--{name.replace('_','-')}",
            is_flag=True,
            default=param.default,
            show_default=True,
            help=effective_help,
        )(wrapper)

    if isinstance(param.default, Param):
        # `Param` as a default value means it's an optional argument with a default.
        return click.argument(
            name, type=param_type, required=False, default=param.default.default
        )(wrapper)

    if param.default is None:
        # Parameters with a `None` default become optional options.
        return click.option(
            f"--{name.replace('_','-')}",
            type=param_type,
            default=None,
            show_default=True,
            help=effective_help,
        )(wrapper)

    # Final fallback: optional positional with default
    # If none of the above conditions are met, it defaults to an optional
    # positional argument with its default value.
    wrapped = click.argument(name, type=param_type, default=final_default, required=False)(wrapper)
    # Ensure the Click parameter reflects the optional nature and default.
    for p in wrapped.params:
        if p.name == name:
            p.required = False
            p.default = final_default
    return wrapped


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

    def decorator(fn: F) -> click.Command:
        # Convert function name to a kebab-case command name (e.g., "my_command" -> "my-command").
        cmd_name = fn.__name__.replace("_", "-")
        # Inspect the function's signature to get parameter information.
        sig = inspect.signature(fn)
        # Extract help text for the command from various sources.
        help_txt = _extract_command_help(sig, fn)
        # Resolve before and after middleware hooks.
        before_hooks, after_hooks = resolve_middleware(middleware)
        # Check if `click.Context` is explicitly injected into the function's parameters.
        ctx_injected = any(p.annotation is click.Context for p in sig.parameters.values())

        @click.command(name=cmd_name, help=help_txt)  # type: ignore
        @click.pass_context
        def wrapper(ctx: click.Context, **kwargs: Any) -> Any:
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
            # --- State injection ---
            # If the context doesn't already have sayer state, initialize it.
            if not hasattr(ctx, "_sayer_state"):
                try:
                    # Instantiate all registered State classes.
                    cache = {cls: cls() for cls in get_state_classes()}
                except Exception as e:
                    # Handle potential errors during state initialization.
                    click.echo(str(e))
                    ctx.exit(1)
                ctx._sayer_state = cache  # type: ignore # Store the state cache in the context.

            # --- Dynamic default_factory injection ---
            for p in sig.parameters.values():
                # Skip `click.Context` and `State` parameters as they are handled separately.
                if p.annotation is click.Context:
                    continue
                if isinstance(p.annotation, type) and issubclass(p.annotation, State):
                    continue

                param_meta = None
                # Resolve the raw type, handling `Annotated` parameters.
                raw = p.annotation if p.annotation is not inspect._empty else str
                if get_origin(raw) is Annotated:
                    # Look for metadata (Option, Env) within Annotated arguments.
                    for m in get_args(raw)[1:]:
                        if isinstance(m, (Option, Env)):
                            param_meta = m
                            break
                # If no metadata found in Annotated, check if the default value is metadata.
                if param_meta is None and isinstance(p.default, (Option, Env)):
                    param_meta = p.default

                # If metadata with a `default_factory` is found and no value was provided
                # via the CLI, call the factory to get the default.
                if isinstance(param_meta, (Option, Env)) and getattr(
                    param_meta, "default_factory", None
                ):
                    if not kwargs.get(p.name):
                        kwargs[p.name] = param_meta.default_factory()

            # --- Bind & convert arguments ---
            bound_args: dict[str, Any] = {}
            for p in sig.parameters.values():
                # Inject `click.Context` if requested.
                if p.annotation is click.Context:
                    bound_args[p.name] = ctx
                    continue
                # Inject `sayer.State` instances if requested.
                if isinstance(p.annotation, type) and issubclass(p.annotation, State):
                    bound_args[p.name] = ctx._sayer_state[p.annotation]  # type: ignore
                    continue

                # Determine the target type for conversion, handling `Annotated` and default `str`.
                raw = p.annotation if p.annotation is not inspect._empty else str
                target_type = get_args(raw)[0] if get_origin(raw) is Annotated else raw
                val = kwargs.get(p.name)

                # Special handling for explicit `JsonParam` or `Annotated` with `JsonParam`.
                if isinstance(p.default, JsonParam) or (
                    get_origin(p.annotation) is Annotated
                    and any(isinstance(m, JsonParam) for m in get_args(p.annotation)[1:])
                ):
                    if isinstance(val, str):
                        try:
                            # Attempt to load JSON string and then apply structure.
                            data = json.loads(val)
                        except json.JSONDecodeError as e:
                            # Raise a Click `BadParameter` error on JSON decoding failure.
                            raise click.BadParameter(f"Invalid JSON for '{p.name}': {e}") from e
                        val = apply_structure(target_type, data)

                # Convert non-list/Sequence types using the `_convert` helper.
                if get_origin(raw) not in (list, Sequence):
                    val = _convert(val, target_type)

                bound_args[p.name] = val

            # --- Before hooks ---
            # Run global and command-specific `before` middleware.
            run_before(cmd_name, bound_args)
            for hook in before_hooks:
                hook(cmd_name, bound_args)

            # --- Execute command ---
            result = fn(**bound_args)
            # If the function is a coroutine, run it using `anyio`.
            if inspect.iscoroutine(result):
                result = anyio.run(lambda: result)

            # --- After hooks ---
            # Run global and command-specific `after` middleware.
            run_after(cmd_name, bound_args, result)
            for hook in after_hooks:  # type: ignore
                hook(cmd_name, bound_args, result)  # type: ignore

            return result

        wrapper._original_func = fn  # type: ignore # Store a reference to the original function.
        current = wrapper

        # Attach parameters to the Click command.
        # Iterate through the original function's parameters to build Click options/arguments.
        for param in sig.parameters.values():
            # Skip `click.Context` and `sayer.State` parameters as they are handled internally.
            if param.annotation is click.Context or (
                isinstance(param.annotation, type) and issubclass(param.annotation, State)
            ):
                continue

            # Determine the raw annotation and the primary parameter type.
            raw = param.annotation if param.annotation is not inspect._empty else str
            ptype = get_args(raw)[0] if get_origin(raw) is Annotated else raw

            param_meta = None
            param_help = ""
            # Extract parameter metadata and help text from `Annotated` types.
            if get_origin(raw) is Annotated:
                for m in get_args(raw)[1:]:
                    if isinstance(m, (Option, Argument, Env, Param, JsonParam)):
                        param_meta = m
                    elif isinstance(m, str):
                        param_help = m
            # If no metadata found in `Annotated`, check if the default value is metadata.
            if param_meta is None and isinstance(
                param.default, (Param, Option, Argument, Env, JsonParam)
            ):
                param_meta = param.default

            # Build and apply the Click parameter decorator.
            current = _build_click_parameter(  # type: ignore
                param,
                raw,
                ptype,
                param_meta,
                param_help,
                current,
                ctx_injected,
            )

        # Register the command.
        if hasattr(fn, "__sayer_group__"):
            # If the function is part of a `sayer` group, add it to that group.
            fn.__sayer_group__.add_command(current)
        else:
            # Otherwise, add it to the global command registry.
            COMMANDS[cmd_name] = current

        return current

    # If `func` is provided (i.e., `@command` without parentheses), apply the decorator immediately.
    # Otherwise, return the `decorator` function for later application (i.e., `@command(...)`).
    return decorator if func is None else decorator(func)


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
    returned. Otherwise, a new group is created, defaulting to `RichGroup` for
    enhanced formatting if no `group_cls` is specified. The `command` method
    of the created group is monkey-patched to use `sayer.command`.

    Args:
        name: The name of the Click group. This will be the name used to invoke
              the group from the command line.
        group_cls: An optional custom Click group class to use. If `None`,
                   `sayer.utils.ui.RichGroup` is used by default.
        help: An optional help string for the group, displayed when `--help`
              is invoked on the group.

    Returns:
        A `click.Group` instance, either newly created or retrieved from the
        internal registry.
    """
    # Check if the group already exists to avoid re-creating it.
    if name not in _GROUPS:
        # Determine the group class to use; default to `RichGroup`.
        cls = group_cls or RichGroup
        # Create the Click group instance.
        grp = cls(name=name, help=help)

        def _grp_command(fn: F | None = None, **opts: Any) -> click.Command:
            """
            Internal helper that replaces `click.Group.command` to integrate
            `sayer`'s command decorator.

            This allows `sayer.command` to be applied automatically when
            `@group_instance.command` is used.
            """
            if fn and callable(fn):
                # If a function is provided directly, associate it with the group
                # and apply `sayer.command`.
                fn.__sayer_group__ = grp  # type: ignore # Mark the function as belonging to this group.
                return cast(click.Command, command(fn, **opts))

            def inner_decorator(f: F) -> click.Command:
                # If used as `@group.command(...)`, return a decorator that
                # first marks the function with the group, then applies `sayer.command`.
                f.__sayer_group__ = grp  # type: ignore
                return cast(click.Command, command(f, **opts))

            return cast(click.Command, inner_decorator)

        # Monkey-patch the group's `command` method.
        grp.command = _grp_command  # type: ignore
        # Store the created group in the internal groups registry.
        _GROUPS[name] = grp

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


def bind_command(grp: click.Group, fn: F) -> click.Command:
    """
    Binds a function to a specific Click group using `sayer`'s command decorator.

    This helper function is primarily used internally for monkey-patching
    `click.Group.command` to ensure all commands within a `sayer`-managed group
    are processed by `sayer`'s `command` decorator.

    Args:
        grp: The `click.Group` instance to which the command will be bound.
        fn: The Python function to be turned into a command.

    Returns:
        A `click.Command` object, decorated by `sayer.command` and associated
        with the provided group.
    """
    # Mark the function as belonging to the specified group.
    fn.__sayer_group__ = grp  # type: ignore
    # Apply the `sayer.command` decorator to the function.
    return cast(click.Command, command(fn))


# Monkey-patch Click so that all groups use Sayer’s binding logic:
# This crucial line ensures that any `click.Group` created (even outside
# `sayer.group`) will use `sayer`'s `bind_command` when its `.command`
# method is called. This globally enables `sayer`'s enhanced command
# features for all Click groups in the application.
click.Group.command = bind_command  # type: ignore
