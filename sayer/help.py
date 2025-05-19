import inspect
from typing import Annotated, get_args, get_origin

import click
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sayer.params import Argument, Env, Option, Param

console = Console()


def render_help_for_command(ctx: click.Context) -> None:
    """
    Render help for a single command (or group) using Rich formatting.
    Includes description, usage, parameters, and if a group, lists its sub-commands recursively.
    """
    cmd = ctx.command
    # Command description (help or docstring)
    doc = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."
    signature = _generate_signature(cmd)
    # Build usage line
    if isinstance(cmd, click.Group):
        usage = f"sayer {cmd.name} [OPTIONS] COMMAND [ARGS]..."
    else:
        usage = f"sayer {cmd.name} {signature}"

    # Section: Description
    description_md = Markdown(doc)

    # Build parameters table
    param_table = Table(
        show_header=True,
        header_style="bold yellow",
        box=None,
        pad_edge=False,
        title_style="bold magenta",
    )
    param_table.add_column("Parameter", style="cyan")
    param_table.add_column("Type", style="green")
    param_table.add_column("Required", style="red", justify="center")
    param_table.add_column("Default", style="blue", justify="center")
    param_table.add_column("Description", style="white")

    # Inspect original function for annotations
    orig_fn = getattr(cmd.callback, "_original_func", None)
    orig_sig = inspect.signature(orig_fn) if orig_fn else None

    for param in cmd.params:
        # Determine human-friendly Type
        if orig_sig and param.name in orig_sig.parameters:
            anno = orig_sig.parameters[param.name].annotation
            if get_origin(anno) is Annotated:
                raw = get_args(anno)[0]
            else:
                raw = anno
            if raw is inspect._empty:
                typestr = "STRING"
            else:
                typestr = getattr(raw, "__name__", str(raw)).upper()
        else:
            pt = param.type
            typestr = pt.name.upper() if hasattr(pt, "name") else str(pt).upper()

        # Determine default & required
        default_val = getattr(param, "default", inspect._empty)
        if isinstance(default_val, (Option, Argument, Env, Param)):
            real_default = default_val.default
            required = "Yes" if default_val.required else "No"
        else:
            real_default = default_val
            required = "No" if real_default not in (inspect._empty, None, ...) else "Yes"

        # Format default
        if real_default in (inspect._empty, None, ...):
            default_str = ""
        elif isinstance(real_default, bool):
            default_str = "true" if real_default else "false"
        else:
            default_str = str(real_default)

        label = f"--{param.name}" if isinstance(param, click.Option) else f"<{param.name}>"
        help_text = getattr(param, "help", "") or ""
        param_table.add_row(label, typestr, required, default_str, help_text)

        # Compose rich header and optionally include subcommands
    if isinstance(cmd, click.Group):
        # Commands table for this group
        cmd_table = Table(
            show_header=True,
            header_style="bold green",
            box=None,
            pad_edge=False,
        )
        cmd_table.add_column("Name", style="cyan")
        cmd_table.add_column("Description", style="white")
        for name, sub in cmd.commands.items():
            cmd_table.add_row(name, sub.help or "")

        content = Group(
            Text("Description", style="bold blue"),
            Padding(description_md, (0, 0, 1, 2)),
            Text("Usage", style="bold cyan"),
            Padding(Text(f"  {usage}"), (0, 0, 1, 2)),
            Text("Parameters", style="bold cyan"),
            Padding(param_table, (0, 0, 0, 2)),
            Text("\nCommands", style="bold cyan"),
            Padding(cmd_table, (1, 0, 0, 2)),
        )
    else:
        content = Group(
            Text("Description", style="bold blue"),
            Padding(description_md, (0, 0, 1, 2)),
            Text("Usage", style="bold cyan"),
            Padding(Text(f"  {usage}"), (0, 0, 1, 2)),
            Text("Parameters", style="bold cyan"),
            Padding(param_table, (0, 0, 0, 2)),
        )

    console.print(Panel.fit(content, title=cmd.name, border_style="bold cyan"))
    ctx.exit()


def _generate_signature(cmd: click.Command) -> str:
    parts: list[str] = []
    for p in cmd.params:
        if isinstance(p, click.Argument):
            parts.append(f"<{p.name}>")
        elif isinstance(p, click.Option):
            if p.is_flag:
                parts.append(f"[--{p.name}]")
            else:
                parts.append(f"[--{p.name} <{p.name}>]")
    return " ".join(parts)
