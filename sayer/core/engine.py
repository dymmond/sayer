import inspect
import json
from collections.abc import Callable
from functools import wraps
from typing import (
    Annotated,
    Any,
    Sequence,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

import anyio
import click

from sayer.core.commands.sayer import SayerCommand
from sayer.core.groups.sayer import SayerGroup
from sayer.core.handlers import (
    ParameterContext,
    _handle_argument,
    _handle_boolean_flag,
    _handle_defaults,
    _handle_enum,
    _handle_env,
    _handle_json,
    _handle_option,
    _handle_sequence,
    _handle_special_types,
    _handle_variadic_args,
)
from sayer.core.utils import CommandRegistry, _extract_command_help_text, convert_cli_value_to_type
from sayer.encoders import apply_structure
from sayer.middleware import resolve as resolve_middleware, run_after, run_before
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State, get_state_classes

F = TypeVar("F", bound=Callable[..., Any])

COMMANDS: CommandRegistry[str, click.Command] = CommandRegistry()
GROUPS: dict[str, click.Group] = {}


def build_click_parameter(
    parameter: inspect.Parameter,
    raw_type_annotation: Any,
    parameter_base_type: type,
    parameter_metadata: Param | Option | Argument | Env | JsonParam | None,
    param_help_text: str,
    click_wrapper_function: Callable,
    is_context_injected: bool,
    is_overriden_type: bool,
) -> Callable:
    """Builds a Click decorator (argument or option) for a function parameter.

    This function acts as the entry point, coordinating the process of
    converting a Python function parameter into a `click.Argument` or
    `click.Option` decorator, which is then applied to a wrapper function.
    It delegates the actual construction logic to a series of specialized
    handler functions based on the parameter's type, metadata, and
    other properties.

    Args:
        parameter: The `inspect.Parameter` object for the function parameter.
        raw_type_annotation: The raw type annotation of the parameter (e.g., `list[str]`).
        parameter_base_type: The underlying base type of the parameter (e.g., `str` for `list[str]`).
        parameter_metadata: A metadata object (e.g., `Param`, `Option`, `Argument`)
            if provided by the user via typing extensions.
        param_help_text: The help text extracted from the function's docstring.
        click_wrapper_function: The function (usually a wrapper) to which the
            Click decorator will be applied.
        is_context_injected: True if the parameter is a Click context object (e.g., `click.Context`).
        is_overriden_type: True if the parameter's type was explicitly overridden.

    Returns:
        A callable (the Click decorator function) that, when called with
        the wrapper function, will apply the final `click.Argument` or
        `click.Option` to it.

    Raises:
        RuntimeError: If no specialized handler can successfully process the
            parameter configuration.
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

                # Convert non-list/Sequence types using the `convert_cli_value_to_type` helper.
                if get_origin(raw_type_for_conversion) in (list, Sequence):
                    inner = get_args(raw_type_for_conversion)[0] if get_args(raw_type_for_conversion) else Any
                    parameter_value = [
                        convert_cli_value_to_type(item, inner, function_to_decorate, param_sig.name)
                        for item in (parameter_value or [])
                    ]
                else:
                    parameter_value = convert_cli_value_to_type(
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
            current_wrapper = build_click_parameter(
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
    if name not in GROUPS:
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
        GROUPS[name] = new_group_instance

    return GROUPS[name]


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
    return GROUPS


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
