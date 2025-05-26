from typing import Any, Callable, TypeVar, cast, overload

import click
from rich.panel import Panel
from rich.text import Text

from sayer.utils.console import console

T = TypeVar("T", bound=Callable[..., Any])


class SayerGroup(click.Group):
    """
    A custom `click.Group` subclass that enhances command registration and
    error handling with Rich-based formatting.

    This class ensures that all subcommands registered through its `command`
    decorator use `sayer.core.engine.command` for enhanced Sayer-specific
    command behavior and provides custom help and error rendering.
    """

    @overload
    def command(self, f: T) -> T: ...

    @overload
    def command(self, *args: Any, **kwargs: Any) -> Callable[[T], T]: ...

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """
        Registers a function as a subcommand using the Sayer command engine.

        This method acts as a decorator, similar to `click.Group.command`, but
        it intercepts the command creation to ensure that the decorated function
        is processed by `sayer.core.engine.command`. It also attaches a
        reference to this `SayerGroup` instance to the function, allowing
        Sayer to associate commands with their parent groups.

        Args:
            *args: Positional arguments passed to the underlying `click.Group.command`.
            **kwargs: Keyword arguments passed to the underlying `click.Group.command`.

        Returns:
            A decorator that registers the function as a command or the decorated
            function itself if called directly without arguments.
        """
        from sayer.core.engine import command  # Lazily import to avoid circular dependencies

        def decorator(func: T) -> T:
            # If the user wrote @sayer.command("foo", help="…"),
            # then args[0] is the name and func is really the function.
            name_from_pos = args[0] if args and isinstance(args[0], str) else None

            func.__sayer_group__ = self
            # Pass along both forms of name, plus any other attrs.
            return cast(
                T,
                command(
                    func,
                    name=name_from_pos,
                    **kwargs,
                ),
            )

        return decorator

    def get_usage(self, ctx: click.Context) -> str:
        """
        Retrieves the usage string for the command or group.

        This method defers to the default Click `get_usage` method, ensuring
        standard usage formatting is maintained.

        Args:
            ctx: The Click context object.

        Returns:
            A string representing the command's usage.
        """
        return super().get_usage(ctx)

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple[str | None, click.Command]:
        """
        Resolves a command from the given arguments and handles usage errors
        with Rich-based formatting.

        This method attempts to resolve the command using Click's default
        mechanism. If a `click.UsageError` occurs (e.g., an invalid command
        or missing argument), it catches the error, formats a user-friendly
        error message and usage information using Rich panels, prints it to
        the console, and then exits the application with the appropriate code.

        Args:
            ctx: The Click context object.
            args: A list of command-line arguments.

        Returns:
            A tuple containing the command name and the resolved `click.Command` object.

        Raises:
            click.UsageError: If the command cannot be resolved and is not handled
                              by the custom error formatting.
        """
        try:
            # Attempt to resolve the command using the parent class's method.
            return super().resolve_command(ctx, args)  # type: ignore
        except click.UsageError as e:
            # Retrieve the usage string for display in the error panel.
            usage = self.get_usage(ctx)
            # Construct the error message and usage string using Rich markup.
            body = f"[bold red]Error:[/] {e.format_message()}\n\n" f"[bold cyan]Usage:[/]\n  {usage.strip()}"
            # Create a Rich Panel to visually highlight the error.
            panel = Panel.fit(Text.from_markup(body), title="Error", border_style="red")
            # Print the error panel to the console.
            console.print(panel)
            # Exit the application with the error's exit code.
            ctx.exit(e.exit_code)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter | None = None) -> None:
        """
        Formats and renders the help message for the command or group using
        Sayer's custom Rich help renderer.

        This method overrides Click's default help formatting. It delegates
        the rendering process to `sayer.core.help.render_help_for_command`,
        which is responsible for generating a richly formatted help output.

        Args:
            ctx: The Click context object.
            formatter: An optional Click `HelpFormatter` instance (though ignored
                       as Sayer uses its own rendering).
        """
        from sayer.core.help import (
            render_help_for_command,
        )

        # Delegate the help rendering to Sayer's custom help function.
        render_help_for_command(ctx)
