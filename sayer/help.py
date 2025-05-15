from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
import click

console = Console()

def render_help_for_command(ctx: click.Context):
    cmd = ctx.command
    usage = f"[bold cyan]Usage:[/]\n  {ctx.command_path} {cmd.signature}"
    desc = f"[bold white]{cmd.help or 'No description provided.'}[/]"

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Option")
    table.add_column("Type")
    table.add_column("Required")

    for param in cmd.params:
        if isinstance(param, click.Option):
            typestr = str(param.type).replace(" ", "")
            required = "Yes" if param.required else "No"
            table.add_row(f"--{param.name}", typestr, required)

    console.print(Panel.fit(Markdown(desc), title=f"[bold magenta]{ctx.command.name}", border_style="magenta"))
    console.print(Panel.fit(usage, border_style="cyan"))
    if table.rows:
        console.print(Panel.fit(table, title="Options", border_style="green"))

    ctx.exit()
