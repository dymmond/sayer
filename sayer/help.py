import click
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
    doc = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."
    signature = _generate_signature(cmd)
    usage = f"sayer {ctx.command.name} {signature}"

    # Section: Description
    description_md = Markdown(doc)

    # Section: Usage
    usage_text = Text("\nUsage\n", style="bold cyan")
    usage_text += Text(f"  {usage}\n")

    # Section: Parameters
    param_table = Table(show_header=True, header_style="bold green", box=None, pad_edge=False)
    param_table.add_column("Parameter")
    param_table.add_column("Type")
    param_table.add_column("Required")

    for param in cmd.params:
        if isinstance(param, click.Option):
            typestr = str(param.type).replace(" ", "")
            required = "Yes" if param.required else "No"
            param_table.add_row(f"--{param.name}", typestr, required)
        elif isinstance(param, click.Argument):
            typestr = str(param.type).replace(" ", "")
            param_table.add_row(f"<{param.name}>", typestr, "Yes")

    content = Group(
        Text("Description", style="bold cyan"),
        Padding(description_md, (0, 0, 0, 2)),
        Text("\nUsage", style="bold cyan"),
        Text(f"  {usage}\n"),
        Text("Parameters", style="bold cyan"),
        Padding(param_table, (0, 0, 0, 2)),
    )

    console.print(Panel.fit(content, title=f"{ctx.command.name}", border_style="cyan"))
    ctx.exit()
