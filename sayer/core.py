import inspect
import os
from typing import Annotated, Any, Callable, get_args, get_origin, TypeVar

import click

from sayer.middleware import run_after, run_before
from sayer.params import Argument, Env, Option, Param
from sayer.ui import RichGroup

# Define a type variable for the function being wrapped
F = TypeVar("F", bound=Callable[..., Any])

# Global dictionaries to store registered commands and groups
COMMANDS: dict[str, click.Command] = {}
_GROUPS: dict[str, click.Group] = {}


def _convert(value: Any, to_type: type) -> Any:
    """
    Converts a value, typically from a CLI input string, to the specified Python type.

    Handles boolean conversion specifically for common string representations.

    Args:
        value: The input value to convert.
        to_type: The target Python type for conversion.

    Returns:
        The converted value.
    """
    if to_type is bool:
        # Handle boolean conversion from various string/numeric inputs
        if isinstance(value, bool):
            return value
        # Case-insensitive check for common true/false representations
        return str(value).lower() in ("true", "1", "yes", "on")
    # Attempt direct type conversion for other types
    return to_type(value)


def _should_use_option(meta: Param, default: Any) -> bool:
    """
    Determines if a parameter with generic `Param` metadata should be treated as a Click option.

    This is based on whether the metadata includes option-specific features like envvar,
    prompts, callbacks, or a non-default value explicitly set in the metadata.

    Args:
        meta: The `Param` metadata instance.
        default: The parameter's default value from the function signature.

    Returns:
        True if the parameter should be an option, False otherwise.
    """
    return (
        meta.envvar is not None
        or meta.prompt # Use original truthiness check
        or meta.confirmation_prompt # Use original truthiness check
        or meta.hide_input
        or meta.callback is not None
        # Check if a default is explicitly set in the metadata, ignoring the Param(...) sentinel
        or (meta.default is not ... and meta.default is not None)
    )


def _extract_command_help(signature: inspect.Signature, func: Callable) -> str:
    """
    Extracts the help text for a command.

    It first looks for the function's docstring. If not found, it iterates through
    parameters looking for help text provided in `Param` metadata.

    Args:
        signature: The inspect.Signature object for the function.
        func: The command function.

    Returns:
        The extracted help text string, or an empty string if none is found.
    """
    # Prioritize the function's docstring
    cmd_help = inspect.getdoc(func) or ""

    if not cmd_help:
        # If no docstring, look for help in parameter metadata
        for param in signature.parameters.values():
            # Check if the default value is a Param instance with help text
            if isinstance(param.default, Param) and param.default.help:
                return param.default.help

            # Check Annotated metadata for Param instances with help text
            anno = param.annotation
            if get_origin(anno) is Annotated:
                for arg in get_args(anno)[1:]:
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
) -> Callable:
    """
    Builds and attaches a Click parameter (option or argument) to a Click command wrapper.

    This function analyzes the parameter's signature, annotation, and associated `sayer`
    metadata to determine the appropriate Click parameter type and configuration.

    Args:
        param: The inspect.Parameter object for the function parameter.
        raw_anno: The raw annotation of the parameter (before processing Annotated).
        ptype: The determined Python type for the parameter after processing Annotated.
        meta: The extracted `sayer` metadata instance (Option, Argument, Env, Param), or None.
        help_text: The extracted help text for the parameter.
        wrapper: The current Click command wrapper function.

    Returns:
        The wrapper function with the Click parameter attached.
    """
    pname = param.name
    # Determine if the parameter is a boolean flag
    is_flag = ptype is bool
    # Check if the function signature provides a default value
    has_func_default = param.default != inspect._empty
    # Get the default value from the function signature if it exists
    param_default = param.default if has_func_default else None

    # If generic Param metadata is used with Annotated, decide if it should be an Option
    if isinstance(meta, Param) and get_origin(raw_anno) is Annotated:
        if _should_use_option(meta, param_default): # Used param_default instead of param.default, which is equivalent
            # Convert generic Param to Option metadata if it meets the criteria
            meta = meta.as_option()

    # Determine the final default value, prioritizing metadata default, then function default
    has_meta_default = getattr(meta, "default", ...) is not ...
    default = getattr(meta, "default", param_default)

    # Determine if the parameter is required. It's required if there's no function default
    # and no metadata default, unless explicitly set in metadata.
    required = getattr(meta, "required", not (has_func_default or has_meta_default))

    # Determine the final help text, prioritizing metadata help/description
    help_text = getattr(meta, "help", help_text) or getattr(meta, "description", help_text)

    # --- Apply Click Decorators based on Metadata Type ---

    if isinstance(meta, Argument):
        # Parameter is explicitly defined as a Click argument
        wrapper = click.argument(
            pname,
            type=ptype,
            required=required,
            default=default
        )(wrapper)

    elif isinstance(meta, Env):
        # Parameter gets its value primarily from an environment variable
        env_default = os.getenv(meta.envvar, meta.default)
        wrapper = click.option(
            f"--{pname.replace('_','-')}", # Use hyphenated option name
            type=ptype,
            default=env_default,
            show_default=True, # Always show the default value (from env or metadata)
            required=meta.required, # Use required status from Env metadata
            help=f"[env:{meta.envvar}] {help_text}", # Prepend env var info to help
        )(wrapper)

    elif isinstance(meta, Option):
        # Parameter is explicitly defined as a Click option
        wrapper = click.option(
            f"--{pname.replace('_','-')}", # Use hyphenated option name
            type=None if is_flag else ptype, # Type is None for flags
            is_flag=is_flag, # Set is_flag for boolean types
            default=default,
            required=required, # Use required status from Option metadata
            show_default=True, # Always show the default value
            help=help_text,
            prompt=meta.prompt,
            hide_input=meta.hide_input,
            callback=meta.callback,
            envvar=meta.envvar, # Link to environment variable if specified
        )(wrapper)

    else:
        # --- Handle parameters without explicit Option/Argument/Env metadata ---
        # Determine if it should be an argument or an option based on function default

        if not has_func_default:
            # No function default -> it's a required argument by default
            wrapper = click.argument(pname, type=ptype, required=True)(wrapper)
        elif is_flag and isinstance(param.default, bool):
            # Boolean parameter with a boolean default -> it's a flag option
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                is_flag=True,
                default=param.default,
                required=False, # Flags are typically not required
                help=help_text,
            )(wrapper)
        elif isinstance(param.default, Param):
            # Parameter uses a Param instance as its default -> it's an optional argument
            # with the default value from the Param instance
            wrapper = click.argument(
                pname,
                type=ptype,
                required=False,
                default=param.default.default,
            )(wrapper)
        elif param.default is None:
             # Parameter has a default of None -> it's an optional option
             # This allows explicitly passing --param None
            wrapper = click.option(
                f"--{pname.replace('_','-')}",
                type=ptype,
                default=None,
                required=False,
                show_default=True,
                help=help_text,
            )(wrapper)
        else:
            # Parameter has a standard default value -> it's an optional argument
            wrapper = click.argument(
                pname,
                type=ptype,
                default=param.default,
                required=False # Arguments with defaults are optional
            )(wrapper)

            # Ensure the argument is marked as optional explicitly in Click's params
            # This is a bit of a workaround to ensure Click treats it as optional
            # when added as an argument with a default.
            for p in wrapper.params:
                if p.name == pname:
                    p.required = False
                    # The default is already set by the decorator, but this ensures consistency
                    p.default = param.default
                    break

    # Ensure help text is attached to the Click parameter object for tools like Rich
    # to display it correctly.
    for p in wrapper.params:
        if p.name == pname and not getattr(p, "help", None):
            p.help = help_text

    return wrapper


def command(func: F) -> click.Command:
    """
    Registers a function as a CLI command using Click, respecting `sayer` parameter metadata.

    This decorator wraps the original function, processes its signature and annotations
    to build corresponding Click options and arguments, and registers it globally.
    It also integrates `sayer` middleware (`run_before`, `run_after`).

    Args:
        func: The function to register as a command.

    Returns:
        A Click.Command instance representing the wrapped function.
    """
    # Generate the command name from the function name (replace underscores with hyphens)
    name = func.__name__.replace("_", "-")
    # Get the function's signature for parameter inspection
    sig = inspect.signature(func)
    # Extract help text for the command
    cmd_help = _extract_command_help(sig, func)

    # Create the Click command wrapper
    @click.command(name=name, help=cmd_help)
    @click.pass_context # Inject Click context
    def wrapper(ctx: click.Context, **kwargs: Any):
        """
        Internal wrapper function executed by Click when the command is invoked.

        It handles parameter type conversion and middleware execution.
        """
        # Prepare arguments for the original function by converting types
        bound_args = {}
        for p in sig.parameters.values():
            # Get the value provided by Click (from CLI args, options, defaults, etc.)
            val = kwargs.get(p.name)
            # Convert the value to the expected type if an annotation is present
            if p.annotation != inspect._empty:
                val = _convert(val, p.annotation)
            bound_args[p.name] = val

        # Execute 'before' middleware
        run_before(name, bound_args)

        # Call the original function with the prepared arguments
        result = func(**bound_args)

        # Handle async functions
        if inspect.iscoroutine(result):
            import asyncio
            result = asyncio.run(result) # Run the async function to completion

        # Execute 'after' middleware
        run_after(name, bound_args, result)

        # Return the result of the original function
        return result

    # Store a reference to the original function on the wrapper for introspection if needed
    wrapper._original_func = func # type: ignore

    # Process each parameter in the original function's signature
    current_wrapper = wrapper
    for param in sig.parameters.values():
        # Determine the raw annotation and the effective parameter type
        raw_anno = param.annotation if param.annotation != inspect._empty else str # Default to str if no annotation
        ptype: type = raw_anno

        meta: Param | Option | Argument | Env | None = None
        help_text: str = ""

        # Process Annotated annotations
        if get_origin(raw_anno) is Annotated:
            args = get_args(raw_anno)
            ptype = args[0] # The first argument is the type
            # Iterate through subsequent arguments to find metadata and help text
            for arg in args[1:]:
                if isinstance(arg, (Option, Argument, Env, Param)):
                    meta = arg # Found metadata instance
                elif isinstance(arg, str):
                    help_text = arg # Found help text string

        # If no metadata found in Annotated, check if the default value is a Param instance
        if isinstance(param.default, Param) and not meta:
            meta = param.default

        # Build and attach the Click parameter to the wrapper
        current_wrapper = _build_click_parameter(
            param, raw_anno, ptype, meta, help_text, current_wrapper
        )

    # Register the command globally
    COMMANDS[name] = current_wrapper

    # If the original function was bound to a group, add the Click command to it
    if hasattr(func, "__sayer_group__"):
        func.__sayer_group__.add_command(current_wrapper)

    # Return the final Click command object
    return current_wrapper


def group(name: str, group_cls: type[click.Group] | None = None) -> click.Group:
    """
    Registers a Click group or returns an existing one by name.

    This function ensures that group instances are reused if a group with the
    same name is requested multiple times.

    Args:
        name: The name of the group.
        group_cls: An optional custom Click Group class to use. Defaults to RichGroup.

    Returns:
        The Click.Group instance.
    """
    if name not in _GROUPS:
        # Create a new group if it doesn't exist
        cls = group_cls or RichGroup
        _GROUPS[name] = cls(name=name)
    # Return the existing or newly created group
    return _GROUPS[name]


def get_commands() -> dict[str, click.Command]:
    """
    Returns a dictionary of all registered Click commands.

    Returns:
        A dictionary where keys are command names and values are Click.Command objects.
    """
    return COMMANDS


def get_groups() -> dict[str, click.Group]:
    """
    Returns a dictionary of all registered Click groups.

    Returns:
        A dictionary where keys are group names and values are Click.Group objects.
    """
    return _GROUPS


def bind_command(group: click.Group, func: F) -> click.Command:
    """
    Binds a command function to a specific Click group.

    This function is intended to be used as a method on a Click Group instance
    (e.g., `my_group.command(my_func)`). It marks the function for later
    addition to the group during the `command` decorator execution.

    Args:
        group: The Click.Group instance to bind the command to.
        func: The function to register as a command and bind to the group.

    Returns:
        The result of calling the `command` decorator on the function.
    """
    # Attach the target group to the function object. This is picked up by the `command` decorator.
    func.__sayer_group__ = group # type: ignore
    # Register the function as a command
    return command(func)

# Monkey patch Click's Group class to add the bind_command method.
# This allows using group_instance.command(func) syntax.
click.Group.command = bind_command # type: ignore
