import click

from sayer.core.groups.base import BaseSayerGroup


class SayerGroup(BaseSayerGroup):
    """
    A custom `click.Group` subclass that enhances command registration and
    error handling with Rich-based formatting.

    This class ensures that all subcommands registered through its `command`
    decorator use `sayer.core.engine.command` for enhanced Sayer-specific
    command behavior and provides custom help and error rendering.
    """

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter | None = None) -> None:
        """
        Formats and renders the help message for the command or group using
        Sayer's custom Rich help renderer.

        This method overrides Click's default help formatting. It delegates
        the rendering process to `sayer.core.loader.render_help`,
        which is responsible for generating a richly formatted help output.

        Args:
            ctx: The Click context object.
            formatter: An optional Click `HelpFormatter` instance (though ignored
                       as Sayer uses its own rendering).
        """
        from sayer.core.console.loader import (
            render_help,
        )

        # Delegate the help rendering to Sayer's custom help function.
        render_help(ctx, self.display_full_help, self.display_help_length)
