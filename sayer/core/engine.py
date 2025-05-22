import inspect
import os
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import IO, Annotated, Any, Callable, Sequence, TypeVar, get_args, get_origin, overload
from uuid import UUID

import anyio
import click

from sayer.middleware import resolve as resolve_middleware, run_after, run_before
from sayer.params import Argument, Env, Option, Param
from sayer.state import State, get_state_classes
from sayer.utils.ui import RichGroup

F = TypeVar("F", bound=Callable[..., Any])  # Type variable for CLI command functions.


class _CommandRegistry(dict):
    """
    A specialized dictionary for storing Click commands.

    This registry prevents accidental clearing of registered commands by overriding
    the `clear` method to be a no-operation. This ensures that commands, once
    registered, remain accessible throughout the application's lifecycle.
    """

    def clear(self) -> None:
        """
        Overrides the default `clear` method to do nothing.

        This ensures that commands registered in the COMMANDS dictionary cannot be
        unintentionally removed by calling `clear()`.
        """
        return


COMMANDS: _CommandRegistry[str, click.Command] = _CommandRegistry()  # Global registry for Click commands.
_GROUPS: dict[str, click.Group] = {}  # Global dictionary to store registered Click groups.

# Maps Python primitive types to their corresponding Click parameter types.
# This mapping facilitates automatic type conversion for command-line arguments.
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
    Converts a value, typically originating from CLI input, to the specified Python type.

    This function handles various type conversion scenarios, including:
    - **Enum values**: Returns the raw string for Enums, allowing Click's `ParamType`
      to handle the final validation against defined choices.
    - **Datetime to Date**: Converts `datetime` objects to `date` objects if the
      target type is `date`.
    - **Boolean conversion**: Interprets common string representations (e.g., "true", "1",
      "yes", "on") as `True` for boolean types.
    - **Direct casting**: Attempts a direct type cast if the value is not already of
      the target type and no special handling is required.

    Args:
        value: The input value to be converted.
        to_type: The target Python type for the conversion.

    Returns:
        The converted value, or the original value if no conversion is needed or possible
        under the defined rules.
    """
    # If the target type is an Enum, return the value as is. Click's ParamType will validate it.
    if isinstance(to_type, type) and issubclass(to_type, Enum):
        return value
    # If target is date and value is datetime, convert datetime to date.
    if to_type is date and isinstance(value, datetime):
        return value.date()
    # Handle boolean conversion from various string representations.
    if to_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    # If the value is already of the target type, no conversion is needed.
    if isinstance(value, to_type):
        return value
    # Attempt a direct type conversion as a fallback.
    return to_type(value)


def _should_use_option(meta: Param, default: Any) -> bool:
    """
    Determines whether a parameter, based on its `Param` metadata, should be configured
    as a Click option rather than a positional argument.

    A parameter is considered an option if it has associated environment variables,
    requires prompts, hides input, defines a callback, or has an explicit default
    value that is not the `...` ellipsis (indicating no default).

    Args:
        meta: An instance of `sayer.params.Param` containing metadata for the parameter.
        default: The default value of the parameter as defined in the function signature.

    Returns:
        `True` if the parameter should be an option, `False` otherwise.
    """
    return (
        meta.envvar is not None  # Has an associated environment variable.
        or meta.prompt  # Requires a user prompt for input.
        or meta.confirmation_prompt  # Requires a confirmation prompt.
        or meta.hide_input  # Hides input during prompting (e.g., for passwords).
        or meta.callback is not None  # Defines a custom callback function.
        or (meta.default is not ... and meta.default is not None)  # Has a defined non-None default.
    )


def _extract_command_help(signature: inspect.Signature, func: Callable) -> str:
    """
    Extracts the detailed help text for a command function.

    This function prioritizes finding help text in the following order:
    1. The function's docstring.
    2. The `help` attribute of a `sayer.params.Param` instance used as a default value
       for any parameter in the function signature.
    3. A string help text provided within an `Annotated` type hint for any parameter.

    Args:
        signature: The `inspect.Signature` object of the command function.
        func: The command function itself.

    Returns:
        The extracted help text as a string, or an empty string if no help text is found.
    """
    # Attempt to get help text from the function's docstring.
    cmd_help = inspect.getdoc(func) or ""
    if not cmd_help:
        # If no docstring, iterate through parameters to find help in Param defaults or Annotated.
        for param in signature.parameters.values():
            # Check if the parameter's default is a Param instance with help text.
            if isinstance(param.default, Param) and param.default.help:
                return param.default.help
            anno = param.annotation
            # Check if the parameter's annotation uses Annotated and contains help text.
            if get_origin(anno) is Annotated:
                for arg in get_args(anno)[1:]:  # Iterate through metadata arguments.
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
    ctx_injected: bool = False,
) -> Callable:
    """
    Constructs and attaches a Click parameter (either an option or an argument) to
    a given Click command wrapper.

    This function dynamically determines the appropriate Click parameter type and
    configuration based on the Python function parameter's type hints, default values,
    and `sayer.params` metadata. It supports a wide range of types including sequences,
    enums, file paths, UUIDs, dates, datetimes, and file I/O streams.

    Args:
        param: The `inspect.Parameter` object representing the function parameter.
        raw_anno: The raw type annotation of the parameter, potentially including `Annotated`.
        ptype: The resolved base Python type of the parameter (e.g., `str`, `int`, `list[str]`).
        meta: An instance of `Param`, `Option`, `Argument`, or `Env` providing
              specific metadata for parameter configuration, or `None` if no custom
              metadata is provided.
        help_text: The help string for the parameter, potentially extracted from annotations
                   or docstrings.
        wrapper: The current Click command function that this parameter decorator will wrap.
        ctx_injected: A boolean indicating if `click.Context` is being injected into the
                      command function. This influences default parameter behavior.

    Returns:
        The `wrapper` function, now decorated with the newly built Click parameter.
    """
    pname = param.name  # The name of the function parameter.
    is_flag = ptype is bool  # True if the parameter's type is boolean, indicating a potential flag.
    has_default = param.default is not inspect._empty  # True if the parameter has a default value.
    default_val = param.default if has_default else None  # The default value from the function signature.

    # If generic `Param` metadata is provided and conditions for an option are met,
    # convert it to an `Option` instance.
    if isinstance(meta, Param) and get_origin(raw_anno) is Annotated and _should_use_option(meta, default_val):
        meta = meta.as_option()

    origin = get_origin(raw_anno)  # Get the origin type for generic annotations (e.g., `list` from `list[str]`).

    # --- Type-specific parameter building ---

    # 1) **Sequence Support**: Handles parameters annotated as `list` or `Sequence`.
    # These are always created as Click options that can be specified multiple times.
    if origin in (list, Sequence):
        inner = get_args(raw_anno)[0]  # Get the type of elements within the sequence.
        click_inner = _PRIMITIVE_MAP.get(inner, click.STRING)  # Map inner type to Click's type.
        seq_default = [] if not has_default else param.default  # Default for sequence is an empty list.
        return click.option(
            f"--{pname.replace('_','-')}",  # Option name: snake_case to kebab-case.
            type=click_inner,  # Type of individual elements.
            multiple=True,  # Allows multiple occurrences of the option.
            default=seq_default,  # Default sequence value.
            show_default=True,  # Display default in help text.
            help=help_text,
        )(wrapper)

    # 2) **Enum Support**: Handles parameters annotated with `Enum` types.
    # These are always created as Click options with choices constrained by Enum members.
    if isinstance(ptype, type) and issubclass(ptype, Enum):
        choices = [e.value for e in ptype]  # Extract values from Enum members for Click choices.
        enum_default = None
        if has_default:
            # If default is an Enum member, use its value; otherwise, use the raw default.
            enum_default = param.default.value if isinstance(param.default, Enum) else param.default
        return click.option(
            f"--{pname.replace('_','-')}",
            type=click.Choice(choices),  # Restrict input to defined Enum choices.
            default=enum_default,
            show_default=True,
            help=help_text,
        )(wrapper)

    # 3) **Path Support**: Transforms `pathlib.Path` annotations into `click.Path`.
    if ptype is Path:
        ptype = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)

    # 4) **UUID Support**: Transforms `uuid.UUID` annotations into `click.UUID`.
    if ptype is UUID:
        ptype = click.UUID

    # 5) **Date Support**: Transforms `datetime.date` annotations into `click.DateTime`
    # with a specific date format.
    if ptype is date:
        ptype = click.DateTime(formats=["%Y-%m-%d"])

    # 6) **Datetime Support**: Transforms `datetime.datetime` annotations into `click.DateTime`.
    if ptype is datetime:
        ptype = click.DateTime()

    # 7) **File IO Support**: Handles `typing.IO` or `click.File` annotations for file streams.
    if raw_anno is IO or raw_anno is click.File:
        ptype = click.File("r")  # Default to read mode for file handling.

    # --- Fallback and Metadata-driven Parameter Building ---

    # Determine the effective default value for the parameter.
    has_meta = getattr(meta, "default", ...) is not ...  # Check if metadata explicitly provides a default.
    default_final = getattr(meta, "default", default_val)  # Prioritize meta default, then function default.
    # Convert Enum default values to their raw Python values for Click.
    if isinstance(default_final, Enum):
        default_final = default_final.value
    # Convert date/datetime defaults to ISO format for Click's default display.
    if isinstance(default_final, (date, datetime)):
        default_final = default_final.isoformat()

    # Determine if the parameter is required. It's required if no default is provided
    # either by the function signature or by metadata.
    required = getattr(meta, "required", not (has_default or has_meta))
    help_text = getattr(meta, "help", help_text) or help_text  # Resolve the final help text.

    # **Explicit Argument**: If metadata specifies `Argument`.
    if isinstance(meta, Argument):
        wrapper = click.argument(pname, type=ptype, required=required, default=default_final)(wrapper)
    # **Environment Variable**: If metadata specifies `Env`.
    elif isinstance(meta, Env):
        env_val = os.getenv(meta.envvar, meta.default)  # Get default from environment variable.
        wrapper = click.option(
            f"--{pname.replace('_','-')}",
            type=ptype,
            default=env_val,
            show_default=True,
            required=meta.required,
            help=f"[env:{meta.envvar}] {help_text}",  # Add environment variable info to help.
        )(wrapper)
    # **Explicit Option**: If metadata specifies `Option`.
    elif isinstance(meta, Option):
        wrapper = click.option(
            f"--{pname.replace('_','-')}",
            type=(None if is_flag else ptype),  # Type is `None` for flags as Click handles them implicitly.
            is_flag=is_flag,
            default=default_final,
            required=required,
            show_default=True,
            help=help_text,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar,
        )(wrapper)
    # **General Fallback Logic**: For parameters without explicit `sayer.params` metadata.
    else:
        # 1) If no default is provided, it's a required positional argument.
        if not has_default:
            wrapper = click.argument(pname, type=ptype, required=True)(wrapper)

        # 2) If `click.Context` is injected, any defaulted non-flag parameter
        #    without explicit `Param` metadata becomes an option. This prevents
        #    positional arguments from interfering with context injection.
        elif ctx_injected and not is_flag and has_default:
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                type=ptype,
                default=default_final,
                required=required,
                show_default=True,
                help=help_text,
            )(wrapper)

        # 3) If it's a boolean with a default, it's an optional flag option.
        elif is_flag and isinstance(param.default, bool):
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                is_flag=True,
                default=param.default,
                show_default=True,
                help=help_text,
            )(wrapper)

        # 4) If the default is a `Param` instance, treat it as an optional argument with its default.
        elif isinstance(param.default, Param):
            wrapper = click.argument(
                pname,
                type=ptype,
                required=False,
                default=param.default.default,
            )(wrapper)

        # 5) If the default is `None`, treat it as an optional option.
        elif param.default is None:
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                type=ptype,
                default=None,
                show_default=True,
                help=help_text,
            )(wrapper)

        # 6) Final fallback: If it has a default and none of the above apply, treat it as an optional argument.
        else:
            wrapper = click.argument(
                pname,
                type=ptype,
                default=default_final,
                required=False,
            )(wrapper)
            # Ensure the Click parameter correctly reflects its optional nature and default.
            for p in wrapper.params:
                if p.name == pname:
                    p.required = False
                    p.default = default_final
                    break

    # Ensure the help text is attached to the Click parameter if it's still missing.
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
    A decorator that transforms a standard Python function into a Click command,
    seamlessly integrating `sayer`'s advanced parameter handling, middleware system,
    and **State dependency injection**.

    This decorator automates the process of converting Python function parameters
    into Click options and arguments, applies necessary type conversions, extracts
    comprehensive help text, and wraps the command's execution with configurable
    "before" and "after" middleware hooks. It also supports:
    - **Click Context Injection**: Automatically injects the `click.Context` object
      if a parameter is type-hinted as `click.Context`.
    - **State Injection**: Automatically injects instances of `sayer.state.State`
      subclasses. These state objects are typically singletons, initialized once
      per command invocation and cached for reuse.

    It supports two primary modes of use:
    1. **Direct decoration**: `@command` above a function, without parentheses, if
       no additional arguments are needed.
    2. **Configured decoration**: `@command(middleware=["my_middleware"])` when
       specifying middleware or other options.

    Args:
        func: The function to be transformed into a Click command. This argument is
              `None` when the decorator is used with keyword arguments (e.g.,
              `@command(middleware=...)`), in which case it returns another callable
              that expects the function.
        middleware: An optional `Sequence` of middleware to apply. Each element can be
                    a string representing a registered middleware name or a callable
                    function that acts as a middleware. These middlewares run
                    before and after the command's execution.

    Returns:
        If `func` is provided (direct decoration), returns a `click.Command` object.
        If `func` is `None` (configured decoration), returns a callable that takes a
        function and returns a `click.Command` object, allowing for decorator chaining.
    """

    def decorator(fn: F) -> click.Command:
        # Generate the command name by converting the function name from snake_case to kebab-case.
        cmd_name = fn.__name__.replace("_", "-")
        sig = inspect.signature(fn)  # Get the introspection signature of the decorated function.
        cmd_help = _extract_command_help(sig, fn)  # Extract the comprehensive help text for the command.

        # Detect if the function signature includes a `click.Context` parameter for injection.
        ctx_injected = any(p.annotation is click.Context for p in sig.parameters.values())

        # Resolve the specified middleware into separate 'before' and 'after' hook lists.
        before_hooks, after_hooks = resolve_middleware(middleware)

        @click.command(name=cmd_name, help=cmd_help)
        @click.pass_context
        def wrapper(ctx: click.Context, **kwargs: Any):
            # Instantiate all `State` subclasses once per command invocation.
            # The state cache is stored on the Click context for efficiency and lifecycle management.
            if not hasattr(ctx, "_sayer_state_cache"):
                cache: dict[type[State], State] = {}
                try:
                    for state_cls in get_state_classes():
                        # Initialize each state class. If `__init__` takes arguments,
                        # this simple call might fail unless a custom `build` method
                        # is used (not implemented here, but implied by `State`'s doc).
                        cache[state_cls] = state_cls()
                except Exception as e:
                    # If state construction fails, raise a ClickException to gracefully
                    # exit and inform the user.
                    raise click.ClickException(f"Failed to initialize state: {e}") from e
                ctx._sayer_state_cache = cache  # type: ignore[attr-defined] # Cache the initialized states.

            bound_args: dict[str, Any] = {}  # Dictionary to store the arguments bound to the function.
            for p in sig.parameters.values():
                # 1) **Context Injection**: If a parameter is type-hinted as `click.Context`,
                # inject the Click context directly.
                if p.annotation is click.Context:
                    bound_args[p.name] = ctx
                    continue  # Skip further processing for the context parameter.

                # 2) **State Injection**: If a parameter is type-hinted as a `State` subclass,
                # inject the cached instance of that state.
                if isinstance(p.annotation, type) and issubclass(p.annotation, State):
                    # Retrieve the state instance from the cache. This assumes all required
                    # state classes have been instantiated and cached.
                    bound_args[p.name] = ctx._sayer_state_cache[p.annotation]  # type: ignore[attr-defined]
                    continue  # Skip further processing for state parameters.

                # 3) **Regular Parameters**: For all other parameters (CLI options/arguments).
                # Get the raw value provided by Click from `kwargs`.
                raw_anno = p.annotation if p.annotation is not inspect._empty else str
                # Resolve the effective Python type, handling `Annotated` types.
                ptype = get_args(raw_anno)[0] if get_origin(raw_anno) is Annotated else raw_anno
                val = kwargs.get(p.name)

                # Apply type conversion, but skip conversion for sequence types, as Click
                # already handles their parsing into lists based on `multiple=True`.
                if get_origin(raw_anno) not in (list, Sequence):
                    val = _convert(val, ptype)
                bound_args[p.name] = val

            # Execute global "before" middleware hooks.
            run_before(cmd_name, bound_args)
            # Execute command-specific "before" middleware hooks.
            for hook in before_hooks:
                hook(cmd_name, bound_args)

            # Call the original decorated function with the processed arguments.
            result = fn(**bound_args)
            # If the original function is an asynchronous coroutine, run it using `anyio`.
            if inspect.iscoroutine(result):
                result = anyio.run(lambda: result)

            # Execute global "after" middleware hooks.
            run_after(cmd_name, bound_args, result)
            # Execute command-specific "after" middleware hooks.
            for hook in after_hooks:
                hook(cmd_name, bound_args, result)

            return result

        wrapper._original_func = fn  # type: ignore[attr-defined] # Store a reference to the original function for introspection.
        current_wrapper = wrapper  # Initialize the current wrapper with the base Click command.

        # Iterate through each parameter of the original function's signature
        # to build and attach corresponding Click parameters.
        for param in sig.parameters.values():
            # Skip `click.Context` and `State` parameters as they are handled via injection,
            # not as explicit Click options/arguments.
            if param.annotation is click.Context:
                continue
            if isinstance(param.annotation, type) and issubclass(param.annotation, State):
                continue

            # Determine the raw annotation, defaulting to `str` if not explicitly typed.
            raw_anno = param.annotation if param.annotation is not inspect._empty else str
            # Resolve the concrete Python type, unwrapping `Annotated` if present.
            ptype = get_args(raw_anno)[0] if get_origin(raw_anno) is Annotated else raw_anno

            param_meta: Param | Option | Argument | Env | None = None  # Initialize parameter metadata.
            param_help_txt = ""  # Initialize parameter help text.

            # If the annotation uses `Annotated`, extract metadata and help text from it.
            if get_origin(raw_anno) is Annotated:
                for meta_arg in get_args(raw_anno)[1:]:
                    if isinstance(meta_arg, (Option, Argument, Env, Param)):
                        param_meta = meta_arg
                    elif isinstance(meta_arg, str):
                        param_help_txt = meta_arg
            # If no metadata was found in `Annotated`, check if the default value is a `Param` instance.
            if isinstance(param.default, Param) and not param_meta:
                param_meta = param.default

            # **New Logic**: If `click.Context` is being injected into the command, and a parameter
            # has a literal default (not a `Param` instance), force it to be an `Option`.
            # This is a critical adjustment to prevent unintended positional arguments
            # when context injection shifts argument parsing.
            if (
                ctx_injected
                and param_meta is None
                and param.default is not inspect._empty
                and not isinstance(param.default, Param)
            ):
                param_meta = Option(default=param.default)

            # Build and attach the Click parameter (option or argument) to the current wrapper.
            current_wrapper = _build_click_parameter(
                param, raw_anno, ptype, param_meta, param_help_txt, current_wrapper, ctx_injected
            )

        # If the original function was marked as belonging to a specific Click group,
        # add the newly created command to that group.
        if hasattr(fn, "__sayer_group__"):
            fn.__sayer_group__.add_command(current_wrapper)
        else:
            # Otherwise, register the command globally in the `COMMANDS` registry.
            COMMANDS[cmd_name] = current_wrapper

        return current_wrapper

    # If `func` is `None`, return the `decorator` function itself, allowing it to be
    # called later with the function to decorate (e.g., `@command(middleware=[...])`).
    # Otherwise, apply the decorator directly to the provided `func`.
    return decorator if func is None else decorator(func)


def group(name: str, group_cls: type[click.Group] | None = None, help: str | None = None) -> click.Group:
    """
    Registers or retrieves a Click group, ensuring its `.command` API is
    compatible with `sayer`'s command binding logic.

    If a Click group with the specified `name` already exists in the internal registry,
    that existing instance is returned. Otherwise, a new Click group (or a custom
    `group_cls` if provided) is created, registered, and then returned. This prevents
    duplicate group definitions and allows commands to be added to existing groups.

    Crucially, this function **monkey-patches** the `.command` method of the created
    or retrieved group. This override ensures that when `@my_group.command` is used,
    `sayer`'s `command` decorator is invoked internally, correctly binding the command
    to its parent group and applying `sayer`'s advanced parameter and middleware handling.

    Args:
        name: The unique name for the Click group. This name will be used on the
              command line to invoke commands within this group.
        group_cls: An optional custom `click.Group` subclass to use when creating a
                   new group. If `None`, `sayer.utils.ui.RichGroup` is used by default,
                   providing enhanced display capabilities.
        help: An optional string providing a brief description or help text for the group.
              This text will be displayed in the CLI help messages.

    Returns:
        The `click.Group` instance corresponding to the given name.
    """
    if name not in _GROUPS:
        cls = group_cls or RichGroup  # Use `RichGroup` by default.
        grp = cls(name=name, help=help)  # Create the new group.

        # Override this group's .command method to seamlessly integrate with `sayer.command`.
        def _grp_command(fn: F | None = None, **cmd_kwargs: Any) -> click.Command | Callable[[F], click.Command]:
            # This inner function handles both `@grp.command` (no parentheses)
            # and `@grp.command(...)` (with parentheses).

            # Case 1: `@grp.command` (no parentheses) - `fn` is the decorated function.
            if fn is not None and callable(fn):
                fn.__sayer_group__ = grp  # type: ignore[attr-defined] # Mark the function for this group.
                return command(fn, **cmd_kwargs)  # Process with `sayer.command`.

            # Case 2: `@grp.command(...)` (with parentheses) - returns a decorator.
            def decorator(f: F) -> click.Command:
                f.__sayer_group__ = grp  # type: ignore[attr-defined] # Mark the function for this group.
                return command(f, **cmd_kwargs)  # Process with `sayer.command`.

            return decorator

        grp.command = _grp_command  # Assign the custom command method to the group.
        _GROUPS[name] = grp  # Store the new group in the registry.

    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    """
    Retrieves a dictionary of all globally registered Click commands.

    This function provides access to the `COMMANDS` registry, which stores all
    commands that have been defined using the `@command` decorator and are not
    explicitly bound to a specific Click group.

    Returns:
        A `dict` where keys are the command names (strings) and values are the
        corresponding `click.Command` objects.
    """
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    """
    Retrieves a dictionary of all registered Click groups.

    This function provides access to the `_GROUPS` registry, which stores all
    Click group instances that have been created using the `group()` function.

    Returns:
        A `dict` where keys are the group names (strings) and values are the
        corresponding `click.Group` objects.
    """
    return _GROUPS


def bind_command(grp: click.Group, fn: F) -> click.Command:
    """
    Binds a decorated command function to a specific Click group.

    This utility function is designed to be used by Click's monkey-patched `Group.command`
    method (see the global monkey-patching below). When a function is decorated with
    `@group_instance.command`, this function intercepts the call, attaches a special
    `__sayer_group__` attribute to the function indicating its intended group, and
    then processes the function using the main `sayer.command` decorator. This ensures
    that the command is correctly added to its parent group instead of being registered
    globally.

    Args:
        grp: The `click.Group` instance to which the command should be bound.
        fn: The function that is being decorated as a command.

    Returns:
        The `click.Command` object resulting from processing the function with
        the `sayer.command` decorator, now implicitly bound to the specified group.
    """
    fn.__sayer_group__ = grp  # type: ignore[attr-defined] # Attach the target group to the function.
    return command(fn)  # Process the function with the main `command` decorator.


# Monkey-patch Click's `Group.command` method globally as a safety net.
# This ensures that if any `click.Group` instance's `.command` method is called
# directly (e.g., from a Click extension or another library), it still routes
# through `sayer`'s binding mechanism, allowing `sayer`'s parameter handling and
# middleware to apply. This is an important integration point.
click.Group.command = bind_command  # type: ignore[method-assign]
