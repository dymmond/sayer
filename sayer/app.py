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
    ) -> None:
        self._initial_obj = context
        self._context_class = context_class

        # where we store ALL callbacks in registration order
        self._callbacks: list[Callable[..., Any]] = []

        # build kwargs for our Group
        attrs: dict[str, Any] = {}
        if help is not None:
            attrs["help"] = help
        if epilog is not None:
            attrs["epilog"] = epilog

        ctx_settings = context_settings.copy() if context_settings else {}
        if context is not None:
            ctx_settings["obj"] = context
        attrs["context_settings"] = ctx_settings

        # respect init-time flags (can override per-callback too)
        attrs["invoke_without_command"] = invoke_without_command
        attrs["no_args_is_help"] = no_args_is_help
        attrs.update(group_attrs)

        # instantiate the Group
        group = group_class(name=name, **attrs)
        group.context_class = context_class
        group.command_class = command_class

        # add version option if requested
        if add_version_option:
            if not version:
                raise ValueError("`version` must be provided with `add_version_option=True`")
            group = click.version_option(version, "--version", "-V")(group)

        # wrap the Group.invoke so we can fire callbacks first
        original_invoke = group.invoke

        def invoke_with_callbacks(ctx: click.Context) -> Any:
            # 1) if there's a subcommand AND invoke_without_command=False, skip ALL callbacks
            if not group.invoke_without_command and not group.invoke_without_command:
                return original_invoke(ctx)

            # 2) enforce any required callback options up front
            for cb in self._callbacks:
                for param_obj in getattr(cb, "__click_params__", []):
                    if isinstance(param_obj, click.Option) and param_obj.required:
                        if ctx.params.get(param_obj.name) is None:
                            raise click.MissingParameter(param_obj, ctx)  # type: ignore

            # 3) run each callback in registration order
            for cb in self._callbacks:
                sig = inspect.signature(cb)
                hints = get_type_hints(cb, include_extras=True)
                bound: dict[str, Any] = {}
                for name, param in sig.parameters.items():
                    ann = hints.get(name, param.annotation)
                    if ann is click.Context:
                        bound[name] = ctx
                    else:
                        val = ctx.params.get(name)
                        # JSON parse if JsonParam
                        if (
                            get_origin(ann) is Annotated and any(isinstance(m, JsonParam) for m in get_args(ann)[1:])
                        ) or isinstance(param.default, JsonParam):
                            if isinstance(val, str):
                                val = json.loads(val)
                        bound[name] = val
                cb(**bound)

            # 4) proceed with normal click dispatch
            return original_invoke(ctx)

        group.invoke = invoke_with_callbacks  # type: ignore
        self._group = group

    def _apply_param_logic(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """
        Stamp a function (command *or* callback) with ALL Annotated[…]
        metadata by invoking the same _build_click_parameter logic
        that @app.command uses.
        """
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)
        wrapped = fn
        ctx_injected = any(hints.get(p.name, p.annotation) is click.Context for p in sig.parameters.values())

        # apply in reverse so decorators nest properly
        for param in reversed(sig.parameters.values()):
            ann = hints.get(param.name, param.annotation)
            if ann is click.Context or (isinstance(ann, type) and issubclass(ann, State)):
                continue

            raw = ann if ann is not inspect._empty else str
            param_type = get_args(raw)[0] if get_origin(raw) is Annotated else raw

            meta: Param | Option | Argument | Env | JsonParam | None = None
            help_txt = ""
            if get_origin(raw) is Annotated:
                for m in get_args(raw)[1:]:
                    if isinstance(m, (Option, Argument, Env, Param, JsonParam)):
                        meta = m
                    elif isinstance(m, str):
                        help_txt = m

            # fallback to default-based metadata
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
        Register a root-level callback with full Sayer-style params
        (Option/Argument/JsonParam) and optional flags
        `invoke_without_command`/`no_args_is_help`.
        """
        invoke = kwargs.pop("invoke_without_command", None)
        no_args = kwargs.pop("no_args_is_help", None)

        def decorator(fn: T) -> T:
            # 1) stamp it with Annotated[…Option/Argument/JsonParam]
            stamped = self._apply_param_logic(fn)

            # 2) apply any per-callback flags
            if invoke is not None:
                self._group.invoke_without_command = invoke
            if no_args is not None:
                self._group.no_args_is_help = no_args

            # 3) copy all click-Params onto the group up front
            for p in getattr(stamped, "__click_params__", []):
                if isinstance(p, click.Option) and p.default is ...:
                    p.default = None
                self._group.params.insert(0, p)

            # 4) remember it for our invoke hook
            self._callbacks.append(stamped)
            return fn

        if args and callable(args[0]) and not kwargs:
            return decorator(args[0])
        return decorator

    @overload
    def command(self, f: T) -> T: ...

    @overload
    def command(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """
        Decorator to register a function as a subcommand
        (using SayerCommand underneath).
        """
        return self._group.command(*args, **kwargs)

    def add_app(self, alias: str, app: "Sayer") -> None:
        """Alias for add_sayer()."""
        self.add_sayer(alias, app)

    def add_sayer(self, alias: str, app: "Sayer") -> None:
        """
        Mount another Sayer under this one, re-wrapping all of its
        commands/groups through SayerGroup/SayerCommand.
        """

        def rewrap_group(orig: click.Group) -> click.Group:
            Wrapped = type(self._group)
            new = Wrapped(
                name=orig.name,
                help=orig.help,
                epilog=getattr(orig, "epilog", None),
                context_settings=self._group.context_settings.copy(),
            )
            new.context_class = self._group.context_class
            new.command_class = self._group.command_class

            for nm, cmd in list(orig.commands.items()):
                if isinstance(cmd, click.Group):
                    sub = rewrap_group(cmd)
                    new.add_command(sub, name=nm)
                else:
                    wrapped_cmd = SayerCommand(
                        name=cmd.name,
                        callback=cmd.callback,
                        params=cmd.params,
                        help=cmd.help,
                    )
                    new.add_command(wrapped_cmd, name=nm)

            return new

        wrapped = rewrap_group(app._group)
        self._group.add_command(wrapped, name=alias)

    def run(self, args: list[str] | None = None) -> Any:
        """Invoke the CLI."""
        self._group(prog_name=self._group.name, args=args)

    def __call__(self, args: list[str] | None = None) -> Any:
        return self.run(args)

    @property
    def cli(self) -> click.Group:
        """Access the underlying SayerGroup."""
        return self._group
