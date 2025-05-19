import click
from rich.panel import Panel
from rich.text import Text

from sayer.utils.console import console


class RichGroup(click.Group):
    def command(self, *args, **kwargs):
        from sayer.core.engine import command

        def decorator(func):
            func.__sayer_group__ = self
            return command(func)

        return decorator

    def get_usage(self, ctx):
        # Use default usage formatting
        return super().get_usage(ctx)

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as e:
            usage = self.get_usage(ctx)
            body = f"[bold red]Error:[/] {e.format_message()}\n\n[bold cyan]Usage:[/]\n  {usage.strip()}"
            panel = Panel.fit(Text.from_markup(body), title="Error", border_style="red")
            console.print(panel)
            ctx.exit(e.exit_code)

    def format_help(self, ctx, formatter=None):
        from sayer.core.help import render_help_for_command

        # If no explicit help, infer from first subcommand's help
        return render_help_for_command(ctx)


def echo(*args, **kwargs):
    # rprint should ideally use the current sys.stdout,
    # which CliRunner redirects. This might work without changes.
    console.print(*args, **kwargs)


def error(message: str):
    # Create Console locally
    console.print(f"[bold red]✖ {message}[/]", highlight=False)


def success(message: str):
    # Create Console locally
    console.print(f"[bold green]✔ {message}[/]", highlight=False)


def warning(message: str):
    # Create Console locally
    console.print(f"[bold yellow]⚠ {message}[/]", highlight=False)


def info(message: str):
    # Create Console locally
    console.print(f"[bold blue]ℹ {message}[/]", highlight=False)
