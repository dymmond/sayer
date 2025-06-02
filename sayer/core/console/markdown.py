import inspect
from typing import Annotated, get_args, get_origin

import click
from rich.markdown import Markdown
from rich.panel import Panel

from sayer.conf import monkay
from sayer.utils.console import console
from sayer.utils.signature import generate_signature


def render_help_markdown(
    ctx: click.Context,
    display_full_help: bool = monkay.settings.display_full_help,
    display_help_length: int = monkay.settings.display_help_length,
) -> None:
    """
    Render help as one Markdown document, using HTML <span> tags for color.
    Trim down blank lines and panel padding so there’s no huge vertical gaps.
    """
    cmd = ctx.command

    # 1) Grab description (or docstring fallback)
    description = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."

    # 2) Build “Usage” chunk
    signature = generate_signature(cmd)
    if isinstance(cmd, click.Group):
        usage_line = f"{ctx.command_path} [OPTIONS] COMMAND [ARGS]..."
    else:
        usage_line = f"{ctx.command_path} {signature}".rstrip()

    # 3) Gather “user” params (skip --help and hidden)
    user_params = [
        p
        for p in cmd.params
        if not (isinstance(p, click.Option) and "--help" in getattr(p, "opts", ())) and not getattr(p, "hidden", False)
    ]

    # 4) Prepare lists for “Arguments” and “Options” bullet lines
    arg_lines = []
    opt_lines = []

    # To inspect type hints if the callback was wrapped
    orig_fn = getattr(cmd.callback, "_original_func", None)
    orig_sig = inspect.signature(orig_fn) if orig_fn else None

    for param in user_params:
        # Determine the “type” string (from annotations or click.Type)
        if orig_sig and param.name in orig_sig.parameters:
            anno = orig_sig.parameters[param.name].annotation
            if get_origin(anno) is Annotated:
                raw = get_args(anno)[0]
            else:
                raw = anno
            typestr = getattr(raw, "__name__", str(raw)).upper() if raw is not inspect._empty else "STRING"
        else:
            pt = param.type
            typestr = pt.name.upper() if hasattr(pt, "name") else str(pt).upper()

        # Required?
        required = "Yes" if getattr(param, "required", False) else "No"

        # Default (only for click.Option)
        default_val = getattr(param, "default", inspect._empty)
        if default_val in (inspect._empty, None, ...):
            default_str = ""
        elif isinstance(default_val, bool):
            default_str = "true" if default_val else "false"
        else:
            default_str = str(default_val)

        # Build a bullet entry, using HTML <span> for color
        if isinstance(param, click.Option):
            joined = ", ".join(param.opts)
            line = (
                f'- **<span style="color:cyan">`{joined}`</span>**  \n'
                f'    - Type: *<span style="color:magenta">{typestr}</span>*  \n'
                f'    - Required: *<span style="color:red">{required}</span>*  \n'
                + (f'    - Default: *<span style="color:blue">{default_str}</span>*  \n' if default_str else "")
                + (f"    - {param.help}" if param.help else "")
            )
            opt_lines.append(line)
        else:
            line = (
                f'- **<span style="color:cyan">`{param.name}`</span>**  \n'
                f'    - Type: *<span style="color:magenta">{typestr}</span>*  \n'
                f'    - Required: *<span style="color:red">{required}</span>*  \n'
                + (f"    - {param.help}" if param.help else "")
            )
            arg_lines.append(line)

    # 5) Gather subcommands (if this is a click.Group)
    cmd_lines = []
    if isinstance(cmd, click.Group):
        for name, sub in cmd.commands.items():
            raw_help = sub.help or ""
            if not display_full_help:
                lines = raw_help.strip().splitlines()
                first = lines[0] if lines else ""
                remaining = " ".join(lines[1:]).strip()
                if len(remaining) > display_help_length:
                    remaining = remaining[:display_help_length] + "..."
                sub_summary = f"{first}\n\n  {remaining}" if remaining else first
            else:
                sub_summary = raw_help

            cmd_lines.append(f'- **<span style="color:cyan">`{name}`</span>**: {sub_summary}')

    # 6) Assemble into one Markdown string, with only a single blank line between sections
    md_lines = []

    # — Header “H1” with command name
    md_lines.append(f"# {cmd.name}")
    md_lines.append("")  # single blank line

    # — Description
    md_lines.append("**Description**  ")
    md_lines.append(f"{description}")
    md_lines.append("")

    # — Usage
    md_lines.append("**Usage**  ")
    md_lines.append("```")
    md_lines.append(usage_line)
    md_lines.append("```")
    md_lines.append("")

    # — Arguments (if any)
    if arg_lines:
        md_lines.append("**Arguments**  ")
        md_lines.extend(arg_lines)
        md_lines.append("")

    # — Options (if any)
    if opt_lines:
        md_lines.append("**Options**  ")
        md_lines.extend(opt_lines)
        md_lines.append("")

    # — Commands (if any)
    if cmd_lines:
        md_lines.append("**Commands**  ")
        md_lines.extend(cmd_lines)
        md_lines.append("")

    # Join and strip any leading/trailing blank lines:
    final_md = "\n".join(md_lines).strip()

    # 7) Render with Rich’s Markdown, wrapped in a thin Panel (no extra top/bottom padding)
    console.print(Panel.fit(Markdown(final_md), border_style="bright_blue", padding=(0, 1)))
    ctx.exit()
