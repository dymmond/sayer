import inspect

import click
from rich import box
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
    Render help in a simple layout, with:

      1. ‘Usage:’ line (yellow + white).
      2. Description as Markdown.
      3. A single ‘Options’ box with box.ROUNDED borders in gray50,
         containing columns: Flags | Required | Default | Description, with spacing.
      4. A single ‘Commands’ box with box.ROUNDED borders in gray50:
         Name | Description, with spacing.
      5. Exactly one blank line between Usage, Description, Options, and Commands.
    """
    cmd = ctx.command

    # USAGE LINE ——
    signature = generate_signature(cmd)
    if isinstance(cmd, click.Group):
        usage_line = f"{ctx.command_path} [OPTIONS] COMMAND [ARGS]..."
    else:
        usage_line = f"{ctx.command_path} {signature}".rstrip()

    usage_text = Text()
    usage_text.append("Usage: ", style="bold yellow")
    usage_text.append(usage_line, style="white")
    padded_usage_text = Padding(usage_text, (1, 0, 0, 1))  # 4 spaces on the lef

    # DESCRIPTION
    raw_help = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."
    description_renderable = Markdown(raw_help)
    padded_description_renderable = Padding(description_renderable, (0, 0, 0, 1))

    # BUILD LISTS FOR OPTIONS ——
    user_options = [
        p
        for p in cmd.params
        if isinstance(p, click.Option) and "--help" not in getattr(p, "opts", ()) and not getattr(p, "hidden", False)
    ]

    flags_req_def_desc: list[tuple[str, str, str, str]] = []
    max_flag_len = 0

    for param in user_options:
        # Build plain “flags” string: reversed so short form appears first
        flags_str = "/".join(reversed(param.opts))
        if len(flags_str) > max_flag_len:
            max_flag_len = len(flags_str)

        # Required?
        required_str = "Yes" if getattr(param, "required", False) else "No"

        # Default value (only if not None/empty)
        default_val = getattr(param, "default", inspect._empty)
        if default_val in (inspect._empty, None, ...):
            default_str = ""
        elif isinstance(default_val, bool):
            default_str = "true" if default_val else "false"
        else:
            default_str = str(default_val)

        # Help/Description text
        desc = param.help or ""
        flags_req_def_desc.append((flags_str, required_str, default_str, desc))

    # —BUILD OPTIONS PANEL ——
    options_panel = None
    if flags_req_def_desc:
        opt_table = Table(
            show_header=True,
            header_style="gray50",
            box=None,
            pad_edge=False,
            padding=(0, 2),  # two spaces padding on left/right of each cell
            expand=False,
        )
        # Four columns: flags, Required, Default, Description
        opt_table.add_column("Flags", style="bold cyan", no_wrap=True, min_width=max_flag_len)
        opt_table.add_column("Required", style="red", no_wrap=True, justify="center")
        opt_table.add_column("Default", style="blue", no_wrap=True, justify="center")
        opt_table.add_column("Description", style="gray50", ratio=1)

        for flags_str, required_str, default_str, desc in flags_req_def_desc:
            # Reconstruct a Text object for flags, coloring '--no-' in magenta
            flags_text = Text()
            for i, part in enumerate(flags_str.split("  ")):
                if i > 0:
                    flags_text.append("  ")
                if part.startswith("--no-"):
                    flags_text.append(part, style="magenta")
                else:
                    flags_text.append(part, style="bold cyan")

            opt_table.add_row(
                flags_text,
                required_str,
                default_str,
                desc,
            )

        options_panel = Panel(
            opt_table,
            title="Options",
            title_align="left",
            border_style="gray50",
            box=box.ROUNDED,
            padding=(0, 1),
        )

    # —— 5) BUILD COMMANDS PANEL ——
    commands_panel = None
    if isinstance(cmd, click.Group):
        sub_items: list[tuple[str, str]] = []
        max_cmd_len = 0

        for name, sub in cmd.commands.items():
            raw_sub_help = sub.help or ""
            if not display_full_help:
                lines = raw_sub_help.strip().splitlines()
                first_line = lines[0] if lines else ""
                remaining = " ".join(lines[1:]).strip()
                if len(remaining) > display_help_length:
                    remaining = remaining[:display_help_length] + "..."
                sub_summary = f"{first_line}\n{remaining}" if remaining else first_line
            else:
                sub_summary = raw_sub_help

            if len(name) > max_cmd_len:
                max_cmd_len = len(name)
            sub_items.append((name, sub_summary))

        cmd_table = Table(
            show_header=True,
            header_style="gray50",
            box=None,
            pad_edge=False,
            padding=(0, 2),  # two spaces padding on left/right of each cell
            expand=False,
        )
        cmd_table.add_column("Name", style="bold cyan", no_wrap=True, min_width=max_cmd_len)
        cmd_table.add_column("Description", style="gray50", ratio=1)

        for name, summary in sub_items:
            cmd_table.add_row(Text(name, style="bold cyan"), summary)

        commands_panel = Panel(
            cmd_table,
            title="Commands",
            title_align="left",
            border_style="gray50",
            box=box.ROUNDED,
            padding=(0, 1),
        )

    # —— 6) PRINT ALL SECTIONS WITH ONE BLANK LINE BETWEEN ——
    console.print(padded_usage_text)
    console.print()  # blank line

    console.print(padded_description_renderable)
    console.print()  # blank line

    if options_panel:
        console.print(options_panel)
        console.print()  # blank line before Commands

    if commands_panel:
        console.print(commands_panel)

    ctx.exit()
