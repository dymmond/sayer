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

    This registry prevents accidental clearing of registered commands by
    overriding the `clear` method to be a no-operation. This ensures that
    commands, once registered, remain accessible throughout the application's
    lifecycle.
    """

    def clear(self) -> None:
        """
        Overrides the default `clear` method to do nothing.

        This ensures that commands registered in the COMMANDS dictionary cannot be
        unintentionally removed by calling `clear()`.
        """
        # Intentionally do nothing to prevent clearing the command registry.
        pass


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
    return to_type(value)


def _should_use_option(meta: Param, default_value: Any) -> bool:
    """
    Determines whether a parameter, based on its `Param` metadata, should be configured
    as a Click option rather than a positional argument.

    A parameter is considered an option if it has associated environment variables,
    requires prompts, hides input, defines a callback, or has an explicit default
    value that is not the `...` ellipsis (indicating no default).

    Args:
        meta: An instance of `sayer.params.Param` containing metadata for the parameter.
        default_value: The default value of the parameter as defined in the function signature.

    Returns:
        `True` if the parameter should be an option, `False` otherwise.
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
    cmd_help = inspect.getdoc(func) or ""
    if cmd_help:
        return cmd_help

    for param in signature.parameters.values():
        if isinstance(param.default, Param) and param.default.help:
            return param.default.help
        anno = param.annotation
        if get_origin(anno) is Annotated:
            for arg in get_args(anno)[1:]:
                if isinstance(arg, Param) and arg.help:
                    return arg.help
    return ""


def _build_click_parameter(
    param: inspect.Parameter,
    raw_annotation: Any,
    param_type: type,
    meta: Param | Option | Argument | Env | None,
    help_text: str,
    wrapper: Callable,
    ctx_injected: bool,
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
        raw_annotation: The raw type annotation of the parameter, potentially including `Annotated`.
        param_type: The resolved base Python type of the parameter (e.g., `str`, `int`, `list[str]`).
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
    param_name = param.name
    is_flag = param_type is bool
    has_func_default = param.default is not inspect._empty
    func_default_value = param.default if has_func_default else None

    # If generic `Param` metadata is provided and conditions for an option are met,
    # convert it to an `Option` instance.
    if (
        isinstance(meta, Param)
        and get_origin(raw_annotation) is Annotated
        and _should_use_option(meta, func_default_value)
    ):
        meta = meta.as_option()

    origin = get_origin(raw_annotation)

    # --- Type-specific parameter building ---

    # 1) Sequence Support: Handles parameters annotated as `list` or `Sequence`.
    if origin in (list, Sequence):
        inner_type = get_args(raw_annotation)[0]
        click_inner_type = _PRIMITIVE_MAP.get(inner_type, click.STRING)
        seq_default = () if not has_func_default else param.default
        return click.option(
            f"--{param_name.replace('_','-')}",
            type=click_inner_type,
            multiple=True,
            default=seq_default,
            show_default=True,
            help=help_text,
        )(wrapper)

    # 2) Enum Support: Handles parameters annotated with `Enum` types.
    if isinstance(param_type, type) and issubclass(param_type, Enum):
        choices = [e.value for e in param_type]
        enum_default = None
        if has_func_default:
            enum_default = param.default.value if isinstance(param.default, Enum) else param.default
        return click.option(
            f"--{param_name.replace('_','-')}",
            type=click.Choice(choices),
            default=enum_default,
            show_default=True,
            help=help_text,
        )(wrapper)

    # Convert common Python types to their Click equivalents.
    if param_type is Path:
        param_type = click.Path(exists=False, file_okay=True, dir_okay=True, resolve_path=True)
    elif param_type is UUID:
        param_type = click.UUID
    elif param_type is date:
        param_type = click.DateTime(formats=["%Y-%m-%d"])
    elif param_type is datetime:
        param_type = click.DateTime()
    elif raw_annotation is IO or raw_annotation is click.File:
        param_type = click.File("r")

    # --- Determine final default and required status ---
    has_meta_default = getattr(meta, "default", ...) is not ...
    final_default = getattr(meta, "default", func_default_value)
    if isinstance(final_default, Enum):
        final_default = final_default.value
    if isinstance(final_default, (date, datetime)):
        final_default = final_default.isoformat()

    required = getattr(meta, "required", not (has_func_default or has_meta_default))
    effective_help_text = getattr(meta, "help", help_text) or help_text

    # --- Explicit metadata cases ---
    if isinstance(meta, Argument):
        wrapper = click.argument(param_name, type=param_type, required=required, default=final_default)(wrapper)
    elif isinstance(meta, Env):
        env_val = os.getenv(meta.envvar, meta.default)
        # If `default_factory` is present, let the wrapper handle injection at runtime.
        option_default = None if getattr(meta, "default_factory", None) else env_val
        wrapper = click.option(
            f"--{param_name.replace('_','-')}",
            type=param_type,
            default=option_default,
            show_default=True,
            required=meta.required,
            help=f"[env:{meta.envvar}] {effective_help_text}",
        )(wrapper)
    elif isinstance(meta, Option):
        # If `default_factory` is present, do not set a static default here;
        # the wrapper will call the factory at runtime.
        option_default = None if getattr(meta, "default_factory", None) else final_default
        wrapper = click.option(
            f"--{param_name.replace('_','-')}",
            type=None if is_flag else param_type,
            is_flag=is_flag,
            default=option_default,
            required=required,
            show_default=meta.show_default,  # Use meta's show_default if provided.
            help=effective_help_text,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar,
        )(wrapper)
    # --- General Fallback Logic (no explicit metadata) ---
    else:
        # 1) Required positional argument if no default.
        if not has_func_default:
            wrapper = click.argument(param_name, type=param_type, required=True)(wrapper)
        # 2) If `click.Context` is injected, any defaulted non-flag parameter
        #    without explicit `Param` metadata becomes an option.
        elif ctx_injected and not is_flag and has_func_default:
            wrapper = click.option(
                f"--{param_name.replace('_','-')}",
                type=param_type,
                default=final_default,
                required=required,
                show_default=True,
                help=effective_help_text,
            )(wrapper)
        # 3) Boolean flag fallback.
        elif is_flag and isinstance(param.default, bool):
            wrapper = click.option(
                f"--{param_name.replace('_','-')}",
                is_flag=True,
                default=param.default,
                show_default=True,
                help=effective_help_text,
            )(wrapper)
        # 4) `Param(...)` default fallback as an optional argument.
        elif isinstance(param.default, Param):
            wrapper = click.argument(
                param_name,
                type=param_type,
                required=False,
                default=param.default.default,
            )(wrapper)
        # 5) Explicit `None` default becomes an optional option.
        elif param.default is None:
            wrapper = click.option(
                f"--{param_name.replace('_','-')}",
                type=param_type,
                default=None,
                show_default=True,
                help=effective_help_text,
            )(wrapper)
        # 6) Final fallback: Optional positional argument.
        else:
            wrapper = click.argument(param_name, type=param_type, default=final_default, required=False)(wrapper)
            # Ensure the Click parameter correctly reflects its optional nature and default.
            for p in wrapper.params:
                if p.name == param_name:
                    p.required = False
                    p.default = final_default
                    break

    # Attach missing help text if it hasn't been set by a specific decorator.
    for p in wrapper.params:
        if p.name == param_name and not getattr(p, "help", None):
            p.help = effective_help_text

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

    * **Click Context Injection**: Automatically injects the `click.Context` object
        if a parameter is type-hinted as `click.Context`.
    * **State Injection**: Automatically injects instances of `sayer.state.State`
        subclasses. These state objects are typically singletons, initialized once
        per command invocation and cached for reuse.
    * **Dynamic Defaults**: Supports `default_factory` for `Option` and `Env` to
        provide defaults computed at runtime.

    It supports two primary modes of use:
    1.  **Direct decoration**: `@command` above a function, without parentheses, if
        no additional arguments are needed.
    2.  **Configured decoration**: `@command(middleware=["my_middleware"])` when
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
        cmd_name = fn.__name__.replace("_", "-")
        sig = inspect.signature(fn)
        help_txt = _extract_command_help(sig, fn)
        before_hooks, after_hooks = resolve_middleware(middleware)

        # Detect if the function signature includes a `click.Context` parameter for injection.
        ctx_injected = any(p.annotation is click.Context for p in sig.parameters.values())

        @click.command(name=cmd_name, help=help_txt)
        @click.pass_context
        def wrapper(ctx: click.Context, **kwargs: Any):
            # --- State Caching and Injection ---
            # Instantiate all `State` subclasses once per command invocation, caching them on the Click context.
            if not hasattr(ctx, "_sayer_state_cache"):
                state_cache: dict[type[State], State] = {}
                try:
                    for state_cls in get_state_classes():
                        state_cache[state_cls] = state_cls()
                except Exception as e:
                    # If state construction fails, raise a ClickException for graceful exit.
                    raise click.ClickException(f"Failed to initialize state: {e}") from e
                ctx._sayer_state_cache = state_cache  # type: ignore[attr-defined]

            # --- Dynamic Default Factory Injection ---
            # Apply default_factory values for Option/Env if no explicit CLI value is given.
            for param in sig.parameters.values():
                # Skip `click.Context` or `State` parameters as they aren't standard CLI args.
                if param.annotation is click.Context or (
                    isinstance(param.annotation, type) and issubclass(param.annotation, State)
                ):
                    continue

                param_meta: Option | Env | None = None
                raw_anno = param.annotation if param.annotation is not inspect._empty else str

                # Check `Annotated` metadata first.
                if get_origin(raw_anno) is Annotated:
                    for m in get_args(raw_anno)[1:]:
                        if isinstance(m, (Option, Env)):
                            param_meta = m
                            break
                # Fallback to default value if it's an `Option` or `Env` instance.
                if param_meta is None and isinstance(param.default, (Option, Env)):
                    param_meta = param.default  # type: ignore[assignment]

                # If a `default_factory` is defined and no value was provided via CLI, call the factory.
                if isinstance(param_meta, (Option, Env)) and getattr(param_meta, "default_factory", None):
                    if kwargs.get(param.name) is None:
                        kwargs[param.name] = param_meta.default_factory()  # type: ignore[operator]

            # --- Bind and Convert Arguments ---
            bound_args: dict[str, Any] = {}
            for param in sig.parameters.values():
                # Handle Context injection.
                if param.annotation is click.Context:
                    bound_args[param.name] = ctx
                    continue
                # Handle State injection.
                if isinstance(param.annotation, type) and issubclass(param.annotation, State):
                    bound_args[param.name] = ctx._sayer_state_cache[param.annotation]  # type: ignore[attr-defined]
                    continue

                # Process regular parameters.
                raw_anno = param.annotation if param.annotation is not inspect._empty else str
                target_type = get_args(raw_anno)[0] if get_origin(raw_anno) is Annotated else raw_anno
                value = kwargs.get(param.name)
                # Convert value, skipping sequence types as Click handles their parsing.
                if get_origin(raw_anno) not in (list, Sequence):
                    value = _convert(value, target_type)
                bound_args[param.name] = value

            # --- Middleware Execution ---
            run_before(cmd_name, bound_args)
            for hook in before_hooks:
                hook(cmd_name, bound_args)

            # --- Command Execution ---
            result = fn(**bound_args)
            if inspect.iscoroutine(result):
                result = anyio.run(lambda: result)

            # --- Post-Execution Middleware ---
            run_after(cmd_name, bound_args, result)
            for hook in after_hooks:
                hook(cmd_name, bound_args, result)

            return result

        wrapper._original_func = fn  # type: ignore[attr-defined] # Store original function for introspection.
        current_wrapper = wrapper

        # --- Attach Click Parameters ---
        # Iterate through parameters to build and attach corresponding Click arguments/options.
        for param in sig.parameters.values():
            # Skip parameters handled by injection (`click.Context`, `State`).
            if param.annotation is click.Context or (
                isinstance(param.annotation, type) and issubclass(param.annotation, State)
            ):
                continue

            raw_anno = param.annotation if param.annotation is not inspect._empty else str
            param_type = get_args(raw_anno)[0] if get_origin(raw_anno) is Annotated else raw_anno

            param_meta: Param | Option | Argument | Env | None = None
            param_help_txt = ""
            if get_origin(raw_anno) is Annotated:
                for m in get_args(raw_anno)[1:]:
                    if isinstance(m, (Option, Argument, Env, Param)):
                        param_meta = m
                    elif isinstance(m, str):
                        param_help_txt = m
            # If no metadata from Annotated, check if the default is a Param instance.
            if param_meta is None and isinstance(param.default, (Param, Option, Argument, Env)):
                param_meta = param.default  # type: ignore[assignment]

            current_wrapper = _build_click_parameter(
                param,
                raw_anno,
                param_type,
                param_meta,
                param_help_txt,
                current_wrapper,
                ctx_injected,
            )

        # --- Register Command ---
        # If the original function was marked for a specific group, add it there; otherwise, add to global commands.
        if hasattr(fn, "__sayer_group__"):
            fn.__sayer_group__.add_command(current_wrapper)  # type: ignore[attr-defined]
        else:
            COMMANDS[cmd_name] = current_wrapper

        return current_wrapper

    # Return the decorator itself if `func` is None (for parameterized usage),
    # otherwise apply the decorator immediately to `func`.
    return decorator if func is None else decorator(func)


def group(
    name: str,
    group_cls: type[click.Group] | None = None,
    help: str | None = None,
) -> click.Group:
    """
    Creates or retrieves a Click group, ensuring its `.command` decorator
    automatically binds decorated functions into that group using `sayer`'s logic.

    If a Click group with the specified `name` already exists in the internal registry,
    that existing instance is returned. Otherwise, a new Click group (or a custom
    `group_cls` if provided) is created, registered, and then returned.

    This function monkey-patches the `.command` method of the created or retrieved group.
    This override ensures that when `@my_group.command` is used, `sayer`'s `command`
    decorator is invoked internally, correctly binding the command to its parent group
    and applying `sayer`'s advanced parameter and middleware handling.

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
        cls = group_cls or RichGroup
        grp = cls(name=name, help=help)

        def _grp_command(fn: F | None = None, **cmd_kwargs: Any) -> click.Command | Callable[[F], click.Command]:
            """
            Custom `.command` method for the group, integrating `sayer`'s command decorator.
            Handles both `@grp.command` and `@grp.command(...)` usage.
            """
            # Case 1: @grp.command (no parentheses) - `fn` is the decorated function.
            if fn is not None and callable(fn):
                fn.__sayer_group__ = grp  # type: ignore[attr-defined] # Mark function for this group.
                return command(fn, **cmd_kwargs)  # Process with `sayer.command`.

            # Case 2: @grp.command(...) (with parentheses) - returns a decorator.
            def inner_decorator(f: F) -> click.Command:
                f.__sayer_group__ = grp  # type: ignore[attr-defined] # Mark function for this group.
                return command(f, **cmd_kwargs)  # Process with `sayer.command`.

            return inner_decorator

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
    method. When a function is decorated with `@group_instance.command`, this function
    intercepts the call, attaches a special `__sayer_group__` attribute to the function
    indicating its intended group, and then processes the function using the main
    `sayer.command` decorator. This ensures that the command is correctly added to
    its parent group instead of being registered globally.

    Args:
        grp: The `click.Group` instance to which the command should be bound.
        fn: The function that is being decorated as a command.

    Returns:
        The `click.Command` object resulting from processing the function with
        the `sayer.command` decorator, now implicitly bound to the specified group.
    """
    fn.__sayer_group__ = grp  # type: ignore[attr-defined] # Attach the target group to the function.
    return command(fn)  # Process the function with the main `command` decorator.


# Monkey-patch Click's `Group.command` method globally.
# This is a crucial integration point. It ensures that any `click.Group` instance's
# `.command` method (even those not created via `sayer.group`) will route through
# `sayer`'s binding mechanism, allowing `sayer`'s parameter handling, middleware,
# and state injection to apply universally when commands are attached to groups.
click.Group.command = bind_command  # type: ignore[method-assign]
