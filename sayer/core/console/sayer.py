import inspect
from typing import Annotated, get_args, get_origin

import click
from rich.console import Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sayer.conf import monkay
from sayer.utils.console import console
from sayer.utils.signature import generate_signature


def render_help_for_command(
    ctx: click.Context,
    display_full_help: bool = monkay.settings.display_full_help,
    display_help_length: int = monkay.settings.display_help_length,
) -> None:
    """
    Render help for a single command (or group) using Rich formatting.
    Includes description, usage, parameters (if any), and if a group, lists its sub-commands.
    """
    cmd = ctx.command

    # Fetch the help text or fallback to docstring or a placeholder
    doc = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."
    description_md = Markdown(doc)

    # Build a signature string only once
    signature = generate_signature(cmd)
    if isinstance(cmd, click.Group):
        usage = f"{ctx.command_path} [OPTIONS] COMMAND [ARGS]..."
    else:
        usage = f"{ctx.command_path} {signature}"

    user_params = [
        p
        for p in cmd.params
        if not (isinstance(p, click.Option) and "--help" in getattr(p, "opts", ())) and not getattr(p, "hidden", False)
    ]

    param_table = None
    if user_params:
        # Create the table header (Rich Table)
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

        # If the callback was wrapped, get the original function to inspect type hints
        orig_fn = getattr(cmd.callback, "_original_func", None)
        orig_sig = inspect.signature(orig_fn) if orig_fn else None

        # Iterate once over all user-defined params
        for param in user_params:
            if orig_sig and param.name in orig_sig.parameters:
                anno = orig_sig.parameters[param.name].annotation
                if get_origin(anno) is Annotated:
                    raw = get_args(anno)[0]
                else:
                    raw = anno
                typestr = getattr(raw, "__name__", str(raw)).upper() if raw is not inspect._empty else "STRING"
            else:
                # Fall back to click's type name
                pt = param.type
                typestr = pt.name.upper() if hasattr(pt, "name") else str(pt).upper()

            real_default = getattr(param, "default", inspect._empty)
            if real_default in (inspect._empty, None, ...):
                default_str = ""
            elif isinstance(real_default, bool):
                default_str = "true" if real_default else "false"
            else:
                default_str = str(real_default)

            required = "Yes" if getattr(param, "required", False) else "No"

            if isinstance(param, click.Option):
                label = "/".join(reversed(param.opts))
            else:
                label = f"<{param.name}>"

            help_text = getattr(param, "help", "") or ""
            param_table.add_row(label, typestr, required, default_str, help_text)

    cmd_table = None
    if isinstance(cmd, click.Group):
        cmd_table = Table(
            show_header=True,
            header_style="bold green",
            box=None,
            pad_edge=False,
        )
        cmd_table.add_column("Name", style="cyan")
        cmd_table.add_column("Description", style="white")

        for name, sub in cmd.commands.items():
            help_text = sub.help or ""
            if not display_full_help:
                # Show only the first line + truncated remainder
                lines = help_text.strip().splitlines()
                first_line = lines[0] if lines else ""
                remaining = " ".join(lines[1:]).strip()
                if len(remaining) > display_help_length:
                    remaining = remaining[:display_help_length] + "..."
                sub_help = f"{first_line}\n{remaining}" if remaining else first_line
            else:
                sub_help = help_text

            cmd_table.add_row(name, sub_help or "")

    parts = [
        Text("Description", style="bold blue"),
        Padding(description_md, (0, 0, 1, 2)),
        Text("Usage", style="bold cyan"),
        Padding(Text(f"  {usage}"), (0, 0, 1, 0)),
    ]

    if param_table:
        parts.extend(
            [
                Text("Parameters", style="bold cyan"),
                Padding(param_table, (0, 0, 1, 2)),
            ]
        )

    if cmd_table:
        parts.extend(
            [
                Text("Commands", style="bold cyan"),
                Padding(cmd_table, (0, 0, 0, 2)),
            ]
        )

    panel = Panel.fit(Group(*parts), title=cmd.name, border_style="bold cyan")  # type: ignore
    console.print(panel)
    ctx.exit()
