import click
from rich import print as rprint
from rich.console import Console  # Keep import
from rich.panel import Panel
from rich.text import Text

from sayer.help import render_help_for_command


class RichGroup(click.Group):
    def command(self, *args, **kwargs):
        from sayer.engine import command

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
            Console().print(panel)
            ctx.exit(e.exit_code)

    def get_help(self, ctx):
        help_text = super().get_help(ctx)
        panel = Panel.fit(
            Text(help_text), title=f"[bold cyan]{ctx.command.name}", border_style="cyan"
        )
        Console().print(panel)
        ctx.exit()

    def main(self, *args, **kwargs):
        try:
            return super().main(*args, **kwargs)
        except TypeError:
            # This seems like an unusual way to handle TypeError,
            # but keeping it as per your original code.
            # If the goal is to make the group callable directly
            # without 'main', you might reconsider this.
            return self

    def format_help(self, ctx, formatter=None):
        # If no explicit help, infer from first subcommand's help
        return render_help_for_command(ctx)


def echo(*args, **kwargs):
    # rprint should ideally use the current sys.stdout,
    # which CliRunner redirects. This might work without changes.
    rprint(*args, **kwargs)


def error(message: str):
    # Create Console locally
    Console().print(f"[bold red]✖ {message}[/]", highlight=False)


def success(message: str):
    # Create Console locally
    Console().print(f"[bold green]✔ {message}[/]", highlight=False)


def warn(message: str):
    # Create Console locally
    Console().print(f"[bold yellow]⚠ {message}[/]", highlight=False)


def info(message: str):
    # Create Console locally
    Console().print(f"[bold blue]ℹ {message}[/]", highlight=False)
