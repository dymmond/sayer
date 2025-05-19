import click

from sayer.core.help import render_help_for_command
from sayer.utils.ui import RichGroup


class RichCommand(click.Command):
    """
    A custom click.Command that renders help via Sayer's rich help renderer.
    """

    def get_help(self, ctx):
        render_help_for_command(ctx)


class Sayer:
    """
    A Sayer application object that wraps a RichGroup and ensures all
    commands use RichCommand for help rendering.
    """

    def __init__(
        self,
        name: str | None = None,
        help: str | None = None,
        epilog: str | None = None,
        context_settings: dict | None = None,
        add_version_option: bool = False,
        version: str | None = None,
        group_class: type[click.Group] = RichGroup,
        command_class: type[click.Command] = RichCommand,
        **group_attrs,
    ) -> None:
        # Prepare group attributes
        attrs: dict = {}
        if help is not None:
            attrs["help"] = help
        if epilog is not None:
            attrs["epilog"] = epilog
        if context_settings:
            attrs["context_settings"] = context_settings
        attrs.update(group_attrs)

        # Instantiate the RichGroup
        group = group_class(name=name, **attrs)
        # Ensure every subcommand uses RichCommand
        group.command_class = command_class

        # Optionally add a --version flag
        if add_version_option:
            if not version:
                raise ValueError("`version` must be provided when `add_version_option=True`.")
            group = click.version_option(version, "--version", "-V")(group)  # type: ignore

        self._group = group

    def command(self, *args, **kwargs):
        """
        A decorator to register a function as a subcommand.
        Uses the underlying RichGroup.command(), so RichCommand is applied.
        """
        return self._group.command(*args, **kwargs)

    def add_app(self, alias: str, app: "Sayer") -> None:
        """
        Nest another Sayer app under this as a sub-group.
        """
        self._group.add_command(app._group, name=alias)

    def run(self, args=None):
        """
        Invoke the CLI application.
        """
        self._group(prog_name=self._group.name, args=args)

    def __call__(self, args=None):
        return self.run(args)

    @property
    def cli(self) -> click.Group:
        """
        Access the underlying RichGroup instance.
        """
        return self._group

    def complete(self, ctx: click.Context, incomplete: str) -> list[str]:
        """
        Get shell completion suggestions.
        """
        return list(self._group.complete(ctx, incomplete))
