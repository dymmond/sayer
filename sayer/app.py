from typing import Any, Callable, TypeVar, overload

import click

from sayer.core.commands import SayerCommand
from sayer.core.groups import SayerGroup

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
