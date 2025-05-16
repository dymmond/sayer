import click
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class RichGroup(click.Group):
    def command(self, *args, **kwargs):
        from sayer.core import command

        def decorator(func):
            func.__sayer_group__ = self
            return command(func)

        return decorator

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as e:
            usage = self.get_usage(ctx)
            body = f"[bold red]Error:[/] {e.format_message()}\n\n[bold cyan]Usage:[/]\n  {usage.strip()}"
            panel = Panel.fit(Text.from_markup(body), title="Error", border_style="red")
            console.print(panel)
            ctx.exit(e.exit_code)

    def get_help(self, ctx):
        help_text = super().get_help(ctx)
        panel = Panel.fit(Text(help_text), title=f"[bold cyan]{ctx.command.name}", border_style="cyan")
        Console().print(panel)
        ctx.exit()

    def main(self, *args, **kwargs):
        super().main(*args, **kwargs)


def echo(*args, **kwargs):
    rprint(*args, **kwargs)


def error(message: str):
    console.print(f"[bold red]✖ {message}[/]", highlight=False)


def success(message: str):
    console.print(f"[bold green]✔ {message}[/]", highlight=False)


def warn(message: str):
    console.print(f"[bold yellow]⚠ {message}[/]", highlight=False)


def info(message: str):
    console.print(f"[bold blue]ℹ {message}[/]", highlight=False)
