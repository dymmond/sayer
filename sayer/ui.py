from rich import print as rprint
from rich.console import Console

console = Console()


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
