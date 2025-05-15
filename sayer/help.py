import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

def _generate_signature(cmd: click.Command) -> str:
    parts = []
    for param in cmd.params:
        if isinstance(param, click.Argument):
            parts.append(f"<{param.name}>")
        elif isinstance(param, click.Option):
            opt = f"--{param.name.replace('_', '-')}"
            if param.required:
                opt += f" <{param.name}>"
            else:
                opt = f"[{opt} <{param.name}>]"
            parts.append(opt)
    return " ".join(parts)

def render_help_for_command(ctx: click.Context):
    cmd = ctx.command
    usage = f"[bold cyan]Usage:[/]\n  {ctx.command_path} {_generate_signature(cmd)}"
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
        elif isinstance(param, click.Argument):
            typestr = str(param.type).replace(" ", "")
            table.add_row(f"<{param.name}>", typestr, "Yes")

    console.print(Panel.fit(Markdown(desc), title=f"[bold magenta]{ctx.command.name}", border_style="magenta"))
    console.print(Panel.fit(usage, border_style="cyan"))
    if table.rows:
        console.print(Panel.fit(table, title="Parameters", border_style="green"))

    ctx.exit()
