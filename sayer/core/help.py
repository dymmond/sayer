import inspect
from typing import Annotated, get_args, get_origin

import click
from rich.console import Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sayer.params import Argument, Env, Option, Param
from sayer.utils.console import console


def render_help_for_command(ctx: click.Context) -> None:
    """
    Render help for a single command (or group) using Rich formatting.
    Includes description, usage, parameters (if any), and if a group, lists its sub-commands.
    """
    cmd = ctx.command

    # 1) Description
    doc = cmd.help or (cmd.callback.__doc__ or "").strip() or "No description provided."
    description_md = Markdown(doc)

    # 2) Usage — use the actual invoked path, not “sayer …”
    signature = _generate_signature(cmd)
    if isinstance(cmd, click.Group):
        usage = f"{ctx.command_path} [OPTIONS] COMMAND [ARGS]..."
    else:
        usage = f"{ctx.command_path} {signature}"

    # 3) Parameters — filter out built-in help and any hidden params
    user_params = [
        p
        for p in cmd.params
        if not (isinstance(p, click.Option) and "--help" in getattr(p, "opts", ())) and not getattr(p, "hidden", False)
    ]

    param_table = None
    if user_params:
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

        # original function signature for type hints
        orig_fn = getattr(cmd.callback, "_original_func", None)
        orig_sig = inspect.signature(orig_fn) if orig_fn else None

        for param in user_params:
            # Type name
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

            # Default & required
            default_val = getattr(param, "default", inspect._empty)
            if isinstance(default_val, (Option, Argument, Env, Param)):
                real_default = default_val.default
                required = "Yes" if default_val.required else "No"
            else:
                real_default = default_val
                required = "No" if real_default not in (inspect._empty, None, ...) else "Yes"

            if real_default in (inspect._empty, None, ...):
                default_str = ""
            elif isinstance(real_default, bool):
                default_str = "true" if real_default else "false"
            else:
                default_str = str(real_default)

            label = f"--{param.name}" if isinstance(param, click.Option) else f"<{param.name}>"
            help_text = getattr(param, "help", "") or ""
            param_table.add_row(label, typestr, required, default_str, help_text)

    # 4) If group, build commands table
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
            cmd_table.add_row(name, sub.help or "")

    # 5) Assemble panels
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
