import inspect
import json
from typing import (
    Annotated,
    Any,
    Callable,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

import click

from sayer.conf import monkay
from sayer.core.commands.base import BaseSayerCommand
from sayer.core.commands.sayer import SayerCommand
from sayer.core.engine import _build_click_parameter
from sayer.core.groups.sayer import SayerGroup
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State

_EMPTY_PARAMETER_SENTINEL = inspect._empty
T = TypeVar("T", bound=Callable[..., Any])


class Sayer:
    """
    A Sayer application object that wraps a `SayerGroup` and ensures all
    commands use `SayerCommand` for help rendering. It supports multiple
    root-level callbacks executed before any command or subcommand.
    """

    def __init__(
        self,
        name: str | None = None,
        help: str | None = None,
        epilog: str | None = None,
        context_settings: dict | None = None,
        add_version_option: bool = False,
        version: str | None = None,
        group_class: type[click.Group] = SayerGroup,
        command_class: type[click.Command] = SayerCommand,
        context: Any = None,
        context_class: type[click.Context] = click.Context,
        invoke_without_command: bool = False,
        no_args_is_help: bool = False,
        display_full_help: bool = monkay.settings.display_full_help,
        display_help_length: int = monkay.settings.display_help_length,
        **group_attrs: Any,
    ) -> None:
        """
        Initializes the Sayer application.

        Args:
            name: The name of the command group. If `None`, Click infers it.
            help: The help text for the command group.
            epilog: An epilog text displayed at the end of the help page.
            context_settings: A dictionary of context settings passed to the Click context.
            add_version_option: If `True`, adds a `--version` option to the root command.
            version: The version string to display if `add_version_option` is `True`.
                     Required if `add_version_option` is `True`.
            group_class: The Click Group class to use for the application's root group.
                         Defaults to `SayerGroup`.
            command_class: The Click Command class to use for commands within this group.
                           Defaults to `SayerCommand`.
            context: An initial object to be stored in the Click context (`ctx.obj`).
            context_class: The Click Context class to use. Defaults to `click.Context`.
            invoke_without_command: If `True`, the command's callback is invoked even if no
                                    subcommand is specified. This is passed to the underlying
                                    Click group.
            no_args_is_help: If `True`, displays the help message when no arguments are provided.
                             This is passed to the underlying Click group.
            **group_attrs: Additional keyword arguments passed directly to the `group_class`
                           constructor.

        Raises:
            ValueError: If `add_version_option` is `True` but `version` is not provided.
        """
        self._initial_obj = context
        self._context_class = context_class
        self._callbacks: list[Callable[..., Any]] = []

        # Build up the keyword arguments for the Click group
        group_initialization_attributes: dict[str, Any] = {}
        if help is not None:
            group_initialization_attributes["help"] = help
        if epilog is not None:
            group_initialization_attributes["epilog"] = epilog

        resolved_context_settings = context_settings.copy() if context_settings else {}
        if context is not None:
            resolved_context_settings["obj"] = context
        group_initialization_attributes["context_settings"] = resolved_context_settings

        # Apply init-time flags; these can be overridden per-callback later
        self.invoke_without_command = invoke_without_command
        if invoke_without_command:
            group_initialization_attributes["invoke_without_command"] = invoke_without_command

        if no_args_is_help:
            group_initialization_attributes["no_args_is_help"] = no_args_is_help

        group_initialization_attributes.update(group_attrs)

        # Instantiate the Click group
        cli_group = group_class(name=name, **group_initialization_attributes)
        cli_group.context_class = context_class
        cli_group.command_class = command_class

        # Allows the user to override the default Sayer help rendering
        # by setting `display_full_help` and `display_help_length`
        cli_group.display_full_help = display_full_help
        cli_group.display_help_length = display_help_length

        # Add version option if requested
        if add_version_option:
            if not version:
                raise ValueError("`version` must be provided with `add_version_option=True`")
            cli_group = click.version_option(version, "--version", "-V")(cli_group)

        # Preserve the original invoke method to be called after callbacks
        original_group_invoke = cli_group.invoke

        def invoke_with_sayer_callbacks(ctx: click.Context) -> Any:
            """
            Custom invoke method that integrates Sayer's root-level callbacks
            before the standard Click command dispatch.
            """
            if ctx.resilient_parsing:
                return original_group_invoke(ctx)

            # by default (invoke_without_command=False), skip root callbacks if a subcommand is being called
            # Click<9 stores the raw tokens here; Click>=9 will populate .args instead
            tokens = getattr(ctx, "protected_args", None)
            if tokens is None:
                tokens = ctx.args

            if tokens and tokens[0] in cli_group.commands and not cli_group.invoke_without_command:
                return original_group_invoke(ctx)

            # Enforce any required callback options upfront
            # This reproduces Click's behavior for missing required options
            for callback_handler in self._callbacks:
                for parameter_object in getattr(callback_handler, "__click_params__", []):
                    # The print statements are retained to match original behavior,
                    # though they are unusual for production code.
                    if isinstance(parameter_object, click.Option) and parameter_object.required:
                        if ctx.params.get(parameter_object.name) is None:
                            # Raise the same MissingParameter Click would
                            raise click.MissingParameter(parameter_object, ctx)  # type: ignore

            # Run each callback in registration order
            for callback_handler in self._callbacks:
                function_signature = inspect.signature(callback_handler)
                type_hints = get_type_hints(callback_handler, include_extras=True)
                bound_arguments: dict[str, Any] = {}
                for param_name, param_info in function_signature.parameters.items():
                    annotation = type_hints.get(param_name, param_info.annotation)
                    if annotation is click.Context:
                        bound_arguments[param_name] = ctx
                    else:
                        parameter_value = ctx.params.get(param_name)
                        # JSON parameters get parsed here
                        is_json_param_annotated = get_origin(annotation) is Annotated and any(
                            isinstance(meta, JsonParam) for meta in get_args(annotation)[1:]
                        )
                        is_json_param_default = isinstance(param_info.default, JsonParam)

                        if (is_json_param_annotated or is_json_param_default) and isinstance(parameter_value, str):
                            parameter_value = json.loads(parameter_value)
                        bound_arguments[param_name] = parameter_value
                callback_handler(**bound_arguments)

            # Proceed with normal Click dispatch
            return original_group_invoke(ctx)

        # Install our wrapper
        cli_group.invoke = invoke_with_sayer_callbacks  # type: ignore
        self._group = cli_group
        self._command_class = command_class

    def _apply_param_logic(self, target_function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Stamps a function (whether a command or a callback) with all `Annotated`
        metadata by calling into the same `_build_click_parameter` logic that
        `@app.command` uses.

        Args:
            target_function: The function to apply parameter logic to.

        Returns:
            The function decorated with Click parameters.
        """
        function_signature = inspect.signature(target_function)
        type_hints = get_type_hints(target_function, include_extras=True)
        wrapped_function = target_function
        # Check if click.Context is injected, to pass to _build_click_parameter
        context_param_injected = any(
            type_hints.get(p.name, p.annotation) is click.Context for p in function_signature.parameters.values()
        )

        # Decorate in reverse order so the parameters nest correctly as per Click's design
        for param_obj in reversed(function_signature.parameters.values()):
            annotation = type_hints.get(param_obj.name, param_obj.annotation)
            # Skip Context or State injections as they are handled by Click/Sayer directly
            if annotation is click.Context or (isinstance(annotation, type) and issubclass(annotation, State)):
                continue

            raw_type_annotation = annotation if annotation is not _EMPTY_PARAMETER_SENTINEL else str
            # Extract the actual parameter type, unwrapping from Annotated if present
            actual_param_type = (
                get_args(raw_type_annotation)[0]
                if get_origin(raw_type_annotation) is Annotated
                else raw_type_annotation
            )

            parameter_metadata: Param | Option | Argument | Env | JsonParam | None = None
            parameter_help_text = ""
            if get_origin(raw_type_annotation) is Annotated:
                for metadata_item in get_args(raw_type_annotation)[1:]:
                    if isinstance(metadata_item, (Option, Env, Param, Argument, JsonParam)):
                        parameter_metadata = metadata_item
                    elif isinstance(metadata_item, str):
                        parameter_help_text = metadata_item

            # Fallback to default-based metadata if not explicitly provided via Annotated
            if parameter_metadata is None and isinstance(param_obj.default, (Option, Argument, Env, Param, JsonParam)):
                parameter_metadata = param_obj.default

            is_overriden_type = False
            if getattr(parameter_metadata, "type", None) is not None:
                actual_param_type = parameter_metadata.type
                is_overriden_type = True

            wrapped_function = _build_click_parameter(
                param_obj,
                raw_type_annotation,
                actual_param_type,
                parameter_metadata,
                parameter_help_text,
                wrapped_function,
                context_param_injected,
                is_overriden_type,
            )

        return wrapped_function

    @overload
    def callback(self, f: T) -> T: ...

    @overload
    def callback(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """
        Registers a root-level callback with full Sayer-style parameters
        (`Option`/`Argument`/`JsonParam`) plus optional flags
        `invoke_without_command` and `no_args_is_help`.

        Args:
            *args: If a callable is provided as the first argument, it's treated as the
                   function to decorate.
            **kwargs: Optional keyword arguments including:
                      - `invoke_without_command`: Overrides the group's `invoke_without_command`
                                                  setting for this specific callback.
                      - `no_args_is_help`: Overrides the group's `no_args_is_help` setting
                                           for this specific callback.

        Returns:
            The decorated function if called directly, or a decorator function if called
            with arguments.
        """
        # Pop specific keyword arguments to handle overrides
        invoke_override = kwargs.pop("invoke_without_command", None)
        no_args_override = kwargs.pop("no_args_is_help", None)

        def decorator(func_to_decorate: T) -> T:
            # Apply parameter logic to stamp the function with Click parameters
            stamped_function = self._apply_param_logic(func_to_decorate)

            # Apply any overrides for group behavior based on callback registration
            if invoke_override is not None:
                self._group.invoke_without_command = invoke_override
            if no_args_override is not None:
                self._group.no_args_is_help = no_args_override

            # Iterate through the Click parameters generated for the stamped function
            for param_config in getattr(stamped_function, "__click_params__", []):
                if isinstance(param_config, click.Option):
                    # If a required option has an implicit default (Ellipsis or _empty),
                    # normalize it to None to ensure Click's MissingParameter logic triggers reliably.
                    if param_config.required and (
                        param_config.default is ... or param_config.default is _EMPTY_PARAMETER_SENTINEL
                    ):
                        param_config.default = None
                    # If an optional option has an implicit default, normalize it to None
                    # so it correctly resolves to Python's None if not provided.
                    elif (not param_config.required) and (
                        param_config.default is ... or param_config.default is _EMPTY_PARAMETER_SENTINEL
                    ):
                        param_config.default = None

                    # Fallback logic for inferring 'required' if it was somehow None.
                    # This case should ideally not be hit if `_build_click_parameter`
                    # always sets `required` to `True` or `False`.
                    elif param_config.required is None:
                        # If a default value is explicitly provided (not None, Ellipsis, or _empty),
                        # it's considered optional. Otherwise, default to optional.
                        if (
                            param_config.default is not None
                            and param_config.default is not ...
                            and param_config.default is not _EMPTY_PARAMETER_SENTINEL
                        ):
                            param_config.required = False
                        else:
                            param_config.required = False  # Defaulting to optional

                if isinstance(param_config, click.Argument) and param_config.type is not click.UNPROCESSED:
                    flag_name = f"--{param_config.name.replace('_', '-')}"
                    param_config = click.Option(
                        param_decls=[flag_name],
                        type=param_config.type,
                        default=param_config.default,
                        required=False,
                        help=getattr(param_config, "help", None),
                        multiple=param_config.multiple,
                        nargs=param_config.nargs,
                        show_default=hasattr(param_config, "default"),
                    )
                # Insert the parameter at the beginning of the group's parameters list.
                # This ensures callback parameters are processed before command-specific ones.
                self._group.params.insert(0, param_config)

            self._callbacks.append(stamped_function)
            return func_to_decorate

        # Determine if the callback is being used directly as a decorator or as a decorator factory
        if args and callable(args[0]) and not kwargs:
            return decorator(args[0])
        return decorator

    @overload
    def command(self, f: T) -> T: ...

    @overload
    def command(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """
        Decorator to register a function as a subcommand for this Sayer application.
        This delegates directly to the underlying `SayerGroup.command` method,
        ensuring that help is rendered by `SayerCommand`.

        Args:
            *args: Positional arguments passed directly to `click.Group.command`.
            **kwargs: Keyword arguments passed directly to `click.Group.command`.

        Returns:
            The decorated function if called directly, or a decorator function if called
            with arguments.
        """
        return self._group.command(*args, **kwargs)

    def add_app(self, alias: str, app: "Sayer") -> None:
        """
        An alias for `add_sayer()`.

        Args:
            alias: The name under which the `app` will be mounted.
            app: The `Sayer` application instance to be mounted.
        """
        self.add_sayer(alias, app)

    def add_sayer(self, alias: str, app: "Sayer") -> None:
        """
        Mounts another `Sayer` application under this one.
        This re-wraps the mounted app's commands and groups to ensure that
        help output and behavior align with this `Sayer` instance's `SayerCommand`
        and `SayerGroup` classes.

        Args:
            alias: The name under which the `app` will be mounted as a subcommand.
            app: The `Sayer` application instance to be mounted.
        """
        self._group.add_command(app._group, name=alias)

    def run(self, args: list[str] | None = None) -> Any:
        """
        Invokes the CLI application. This is the main entry point for running the Sayer app.

        Args:
            args: An optional list of command-line arguments to pass to the CLI.
                  If `None`, `sys.argv` is used by Click.

        Returns:
            The return value of the invoked command or callback.
        """
        # Call the underlying Click group's run method
        return self._group(prog_name=self._group.name, args=args)

    def add_command(
        self,
        cmd: click.Command | Any,
        name: str | None = None,
    ) -> None:
        """
        Add a Click Command (or a whole Sayer sub-app) to this Sayer application.

        Args:
            cmd: Either a Click Command/Group, or another Sayer instance.
            name: Optional name under which to register it; if omitted,
                  uses cmd.name (or sub-app’s own name).
        """
        # If they passed in a Sayer instance, pull out its internal group:
        if isinstance(cmd, Sayer):
            cmd = cmd._group  # now cmd is a click.Group

        # If it's a Group (vanilla or SayerGroup), mount it directly so it
        # subcommands survive:
        if isinstance(cmd, click.Group):
            self._group.add_command(cmd, name=name)
            return

        if isinstance(cmd, BaseSayerCommand):
            self._group.add_command(cmd, name=name)
            return

        # Otherwise it's a leaf command: wrap it in SayerCommand
        wrapped = self._command_class(
            name=cmd.name,
            callback=cmd.callback,
            params=cmd.params,
            help=cmd.help,
            context_settings=cmd.context_settings,
            add_help_option=cmd.add_help_option,
            short_help=cmd.short_help,
            epilog=cmd.epilog,
            hidden=cmd.hidden,
            no_args_is_help=cmd.no_args_is_help,
            deprecated=cmd.deprecated,
        )
        self._group.add_command(wrapped, name=name)

    def __call__(self, args: list[str] | None = None) -> Any:
        """
        Makes the Sayer instance callable, providing a convenient shorthand for `run()`.

        Args:
            args: An optional list of command-line arguments to pass.

        Returns:
            The return value of the invoked command or callback.
        """
        return self.run(args)

    @property
    def cli(self) -> click.Group:
        """
        Provides direct access to the underlying Click group object (`SayerGroup`).
        This allows for advanced interactions with the raw Click API if needed.
        """
        return self._group
