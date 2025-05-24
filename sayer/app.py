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
from sayer.core.engine import _build_click_parameter  # noqa
from sayer.core.groups import SayerGroup
from sayer.params import Argument, Env, JsonParam, Option, Param
from sayer.state import State

T = TypeVar("T", bound=Callable[..., Any])


class Sayer:
    """
    A Sayer application object that wraps a SayerGroup and ensures all
    commands use SayerCommand for help rendering.
    Supports multiple callbacks executed before any command or subcommand.
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
        **group_attrs: Any,
    ):
        self._initial_obj = context
        self._context_class = context_class

        # ←—— where we’ll store ALL callbacks, in reg‐order
        self._callbacks: list[Callable[..., Any]] = []

        # Build up the kwargs for our Group
        attrs: dict[str, Any] = {}
        if help is not None:
            attrs["help"] = help
        if epilog is not None:
            attrs["epilog"] = epilog

        ctx_settings = context_settings.copy() if context_settings else {}
        if context is not None:
            ctx_settings["obj"] = context
        attrs["context_settings"] = ctx_settings

        # Respect init‐time flags (you can also override per‐callback)
        attrs["invoke_without_command"] = invoke_without_command
        attrs["no_args_is_help"] = no_args_is_help
        attrs.update(group_attrs)

        # Instantiate the Group
        group = group_class(name=name, **attrs)
        group.context_class = context_class
        group.command_class = command_class

        # Add version option if requested
        if add_version_option:
            if not version:
                raise ValueError("`version` must be provided with `add_version_option=True`")
            group = click.version_option(version, "--version", "-V")(group)

        # Wrap the Group.invoke so we can fire callbacks first
        original_invoke = group.invoke

        def invoke_with_callbacks(ctx: click.Context) -> Any:
            # If there's a subcommand *and* invoke_without_command=False, skip callbacks
            if not group.invoke_without_command and ctx.invoked_subcommand:
                return original_invoke(ctx)

            # Otherwise, run every callback in registration order
            for cb in self._callbacks:
                sig = inspect.signature(cb)
                hints = get_type_hints(cb, include_extras=True)
                bound: dict[str, Any] = {}
                for name, param in sig.parameters.items():
                    ann = hints.get(name, param.annotation)
                    if ann is click.Context:
                        bound[name] = ctx
                    else:
                        bound[name] = ctx.params.get(name)
                cb(**bound)

            return original_invoke(ctx)

        group.invoke = invoke_with_callbacks  # type: ignore

        self._group = group

    def _apply_param_logic(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """
        Stamp a function (command *or* callback) with ALL of your Annotated[…]
        metadata by calling into the same _build_click_parameter logic
        that @app.command uses.
        """
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)
        wrapped = fn
        ctx_injected = any(hints.get(p.name, p.annotation) is click.Context for p in sig.parameters.values())

        for param in reversed(sig.parameters.values()):
            ann = hints.get(param.name, param.annotation)
            # Skip ctx or State injections
            if ann is click.Context or (isinstance(ann, type) and issubclass(ann, State)):
                continue

            raw = ann if ann is not inspect._empty else str
            param_type = get_args(raw)[0] if get_origin(raw) is Annotated else raw

            # Pull out any Option/Argument/etc metadata + help text
            meta = None
            help_txt = ""
            if get_origin(raw) is Annotated:
                for m in get_args(raw)[1:]:
                    if isinstance(m, (Option, Argument, Env, Param, JsonParam)):
                        meta = m
                    elif isinstance(m, str):
                        help_txt = m

            # Fallback to default‐based metadata
            if meta is None and isinstance(param.default, (Option, Argument, Env, Param, JsonParam)):
                meta = param.default

            wrapped = _build_click_parameter(param, raw, param_type, meta, help_txt, wrapped, ctx_injected)

        return wrapped

    @overload
    def callback(self, f: T) -> T: ...

    @overload
    def callback(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """
        Register a root‐level callback with full Sayer‐style params,
        plus optional Click flags `invoke_without_command` and `no_args_is_help`.
        """
        invoke = kwargs.pop("invoke_without_command", None)
        no_args = kwargs.pop("no_args_is_help", None)

        def decorator(fn: T) -> T:
            # 1) Stamp it with Annotated[...Option/Argument/JsonParam] logic
            stamped = self._apply_param_logic(fn)

            # 2) Apply any per‐callback flags
            if invoke is not None:
                self._group.invoke_without_command = invoke
            if no_args is not None:
                self._group.no_args_is_help = no_args

            # 3) Copy *all* of the Click parameters we built onto the group
            for p in getattr(stamped, "__click_params__", []):
                # Insert at front so they appear before subcommands
                self._group.params.append(p)

            # 4) Remember it for the pre‐invoke hook
            self._callbacks.append(stamped)
            return fn

        # Support both @app.callback and @app.callback(...)
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
