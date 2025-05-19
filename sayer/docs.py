import inspect
from pathlib import Path
from typing import Annotated

import click

from sayer.core import get_commands, group
from sayer.params import Option

docs = group("docs", help="Generate Markdown documentation for all Sayer commands and groups.")


def _generate_signature(cmd: click.Command) -> str:
    """
    Generate a CLI usage signature string for a Click command.
    """
    parts: list[str] = []
    for p in cmd.params:
        if isinstance(p, click.Argument):
            parts.append(f"<{p.name}>")
        elif isinstance(p, click.Option):
            if getattr(p, "is_flag", False):
                parts.append(f"[--{p.name}]")
            else:
                parts.append(f"[--{p.name} <{p.name}>]")
    return " ".join(parts)


@docs.command()
def generate(
    output: Annotated[
        str,
        Option(
            default=Path("docs"),
            show_default=True,
            help="Output directory for generated Markdown docs",
        ),
    ],
) -> None:
    """
    Generate Markdown documentation for all Sayer commands and groups.
    """
    # Ensure output directory exists
    output = output.expanduser()
    commands_dir = output / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    # Create index README.md
    index_file = output / "README.md"
    with index_file.open("w", encoding="utf-8") as idx:
        idx.write("# Sayer CLI Documentation\n\n")
        idx.write("## Commands\n\n")
        for name in sorted(get_commands()):
            idx.write(f"- [{name}](commands/{name}.md)\n")

    # Generate per-command docs
    for name, cmd in get_commands().items():
        md_file = commands_dir / f"{name}.md"
        with md_file.open("w", encoding="utf-8") as f:
            # Title
            f.write(f"# sayer {name}\n\n")
            # Description
            desc = cmd.help or inspect.getdoc(cmd.callback) or "No description provided."
            f.write(f"{desc.strip()}\n\n")
            # Usage
            sig = _generate_signature(cmd)
            f.write("## Usage\n\n")
            f.write(f"```sayer {name} {sig}```\n\n")
            # Parameters table
            f.write("## Parameters\n\n")
            f.write("| Name | Type | Required | Default | Description |\n")
            f.write("|------|------|----------|---------|-------------|\n")
            for p in cmd.params:
                pname = f"--{p.name}" if isinstance(p, click.Option) else f"<{p.name}>"
                typestr = getattr(p.type, "__name__", str(p.type)).upper()
                req = (
                    "Yes"
                    if getattr(p, "required", isinstance(p, click.Argument) and p.required)
                    else "No"
                )
                default = p.default
                default_str = "" if default in (None, inspect._empty) else str(default)
                help_text = getattr(p, "help", "") or ""
                f.write(f"| {pname} | {typestr} | {req} | {default_str} | {help_text} |\n")

    click.echo(f"Generated docs in {output}")
