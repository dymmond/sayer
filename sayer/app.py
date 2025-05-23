import inspect
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

from sayer.core.commands import SayerCommand
from sayer.core.engine import _build_click_parameter
from sayer.core.groups import SayerGroup
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State

T = TypeVar("T", bound=Callable[..., Any])


class Sayer:
    """
    A Sayer application object that wraps a SayerGroup and ensures all
    commands use SayerCommand for help rendering.
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
        **group_attrs: Any,
    ) -> None:
        self._initial_obj = context
        self._context_class = context_class

        # build up the kwargs for our group
        attrs: dict[str, Any] = {}
        if help is not None:
            attrs["help"] = help
        if epilog is not None:
            attrs["epilog"] = epilog

        # click expects a dict called "context_settings"
        ctx_settings = context_settings.copy() if context_settings else {}
        if context is not None:
            ctx_settings["obj"] = context

        # tell Click which Context *class* to instantiate
        attrs["context_settings"] = ctx_settings

        # any other group attrs (like invoke_without_command, etc.)
        attrs.update(group_attrs)

        # now build our RichGroup and wire up our RichCommand class
        group = group_class(name=name, **attrs)
        group.context_class = context_class
        group.command_class = command_class

        # version flag if you asked for it
        if add_version_option:
            if not version:
                raise ValueError("`version` must be provided with `add_version_option=True`")
            group = click.version_option(version, "--version", "-V")(group)

        self._group = group

    def _apply_param_logic(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """
        Apply Sayer’s full Option/Argument/Env/Param/JsonParam logic to `fn`
        by resolving any forward‐ref/string annotations and then wrapping it
        in Click parameter decorators exactly as @app.command does.
        """
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)

        decorated_fn = fn
        ctx_injected = any(hints.get(p.name, p.annotation) is click.Context for p in sig.parameters.values())

        # Iterate in reverse so parameters nest correctly
        for param in reversed(sig.parameters.values()):
            # Pull the resolved annotation (or fall back to the raw one)
            ann = hints.get(param.name, param.annotation)

            # Skip click.Context and State injections
            if ann is click.Context or (isinstance(ann, type) and issubclass(ann, State)):
                continue

            # 1) Figure out the “raw” annotation (or default to str)
            raw_annotation = ann if ann is not inspect._empty else str

            # 2) Unwrap Annotated[T, …] → T
            if get_origin(raw_annotation) is Annotated:
                param_type = get_args(raw_annotation)[0]
            else:
                param_type = raw_annotation

            # 3) Extract any Option/Argument/etc metadata + help text
            meta = None
            help_text = ""
            if get_origin(raw_annotation) is Annotated:
                for m in get_args(raw_annotation)[1:]:
                    if isinstance(m, (Option, Argument, Env, Param, JsonParam)):
                        meta = m
                    elif isinstance(m, str):
                        help_text = m

            # 4) Fall back to default-based metadata, e.g. fn(x=Option(...))
            if meta is None and isinstance(param.default, (Option, Argument, Env, Param, JsonParam)):
                meta = param.default

            # 5) Call the engine’s builder with the **exact** signature it expects
            decorated_fn = _build_click_parameter(
                param,
                raw_annotation,
                param_type,
                meta,
                help_text,
                decorated_fn,
                ctx_injected,
            )

        return decorated_fn

    @overload
    def callback(self, f: T) -> T: ...

    @overload
    def callback(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """
        Register a root‐level callback with full Sayer-style params
        (Option/Argument/Param) *and* allow Click’s invoke_without_command,
        no_args_is_help, replace flags.

        Usage:

            @app.callback(invoke_without_command=True, no_args_is_help=True)
            @click.option("--foo", help="…")
            @click.pass_context
            def main(ctx, foo: str):
                …
        """
        # Extract Click‐specific group flags
        invoke = kwargs.pop("invoke_without_command", None)
        no_args_help = kwargs.pop("no_args_is_help", None)
        replace = kwargs.pop("replace", False)

        def decorator(fn: T) -> T:
            # 1) apply Sayer’s parameter logic
            stamped = self._apply_param_logic(fn)

            # 2) remember this for when we run
            self._callback_fn = stamped

            # 3) configure the group’s behavior
            if invoke is not None:
                self._group.invoke_without_command = invoke
            if no_args_help is not None:
                self._group.no_args_is_help = no_args_help

            # 4) register as the group’s result_callback
            self._group.result_callback(replace=replace)(stamped)

            # 5) return the original function (so help/introspection still sees it)
            return fn

        # allow both @app.callback and @app.callback(...)
        if args and callable(args[0]) and not kwargs:
            return decorator(args[0])
        return decorator

    @overload
    def command(self, f: T) -> T: ...

    @overload
    def command(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """
        A decorator to register a function as a subcommand.
        Uses the underlying SayerGroup.command(), so SayerCommand is applied.
        """
        return self._group.command(*args, **kwargs)

    def add_app(self, alias: str, app: "Sayer") -> None:
        """
        Nest another Sayer app under this as a sub-group. This is just an alias
        to add_sayer() for clarity.
        """
        self.add_sayer(alias, app)

    def add_sayer(self, alias: str, app: "Sayer") -> None:
        """
        Mount another Sayer under this one, automatically rewrapping
        *all* of its commands (and nested groups) through RichCommand
        + our main Group class so help always renders with Rich.
        """

        def rewrap_group(orig_group: click.Group) -> click.Group:
            # 1) force it to use *our* Group class
            WrappedGroup = type(self._group)  # e.g. RichGroup or DirectiveGroup
            new_grp = WrappedGroup(
                name=orig_group.name,
                help=orig_group.help,
                epilog=getattr(orig_group, "epilog", None),
                context_settings=self._group.context_settings.copy(),
            )
            # carry over the same ctx.class + command_class
            new_grp.context_class = self._group.context_class
            new_grp.command_class = self._group.command_class

            # 2) rip out every original sub‐entry
            items = list(orig_group.commands.items())
            for name, cmd in items:
                # if it’s a subgroup, recurse
                if isinstance(cmd, click.Group):
                    # rewrap its entire subtree
                    wrapped_sub = rewrap_group(cmd)
                    new_grp.add_command(wrapped_sub, name=name)
                else:
                    # rebuild this command as a RichCommand
                    wrapped_cmd = SayerCommand(
                        name=cmd.name,
                        callback=cmd.callback,
                        params=cmd.params,
                        help=cmd.help,
                        # you can pass epilog=cmd.epilog if you have it
                    )
                    new_grp.add_command(wrapped_cmd, name=name)

            return new_grp

        # now mount:
        wrapped = rewrap_group(app._group)
        self._group.add_command(wrapped, name=alias)

    def run(self, args: list[str] | None = None) -> Any:  # click.Group returns Any
        """
        Invoke the CLI application.
        """
        self._group(prog_name=self._group.name, args=args)

    def __call__(self, args: list[str] | None = None) -> Any:
        return self.run(args)

    @property
    def cli(self) -> click.Group:
        """
        Access the underlying SayerGroup instance.
        """
        return self._group
