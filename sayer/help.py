import inspect

import click
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sayer.params import Argument, Env, Option, Param

console = Console()


def render_help_for_command(ctx):
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
    param_table.add_column("Default", justify="center")
    param_table.add_column("Description")

    for param in cmd.params:
        typestr = str(param.type).replace(" ", "")
        default = getattr(param, "default", inspect._empty)
        description = getattr(param, "help", "") or ""

        required = "Yes"
        default_str = ""

        if isinstance(default, (Option, Argument, Env, Param)):
            # Extract from explicit .required or fallback to default sentinel
            if default.required is not None:
                required = "Yes" if default.required else "No"
            else:
                required = "No" if default.default not in (inspect._empty, None, ...) else "Yes"
            real_default = default.default
        else:
            # Fallback Click default handling
            required = "No" if default not in (None, inspect._empty, ...) else "Yes"
            real_default = default

        if real_default not in (None, inspect._empty, ...):
            default_str = str(real_default).lower() if isinstance(real_default, bool) else str(real_default)

        label = f"--{param.name}" if isinstance(param, click.Option) else f"<{param.name}>"
        param_table.add_row(label, typestr, required, default_str, description)

    # Compose rich output
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


def _generate_signature(cmd):
    parts = []
    for p in cmd.params:
        if isinstance(p, click.Argument):
            parts.append(f"<{p.name}>")
        elif isinstance(p, click.Option):
            if p.is_flag:
                parts.append(f"[--{p.name}]")
            else:
                parts.append(f"[--{p.name} <{p.name}>]")
    return " ".join(parts)
