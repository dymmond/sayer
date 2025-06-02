import inspect
from pathlib import Path
from typing import Annotated, get_args, get_origin

import click

from sayer.core.engine import group
from sayer.params import Option
from sayer.utils.ui import error, success

# Create the 'docs' subgroup
docs = group(
    "docs",
    help="Generate Markdown documentation for all Sayer commands and groups.",
)


def _generate_signature(cmd: click.Command) -> str:
    """
    Generate the usage signature for a Click command.
    """
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


def render_cmd(full_name: str, cmd: click.Command) -> str:
    """
    Render a single command to Markdown.
    """
    sig = _generate_signature(cmd)
    md = []
    # Title
    md.append(f"# sayer {full_name}\n")
    # Description
    desc = cmd.help or inspect.getdoc(cmd.callback) or "No description provided."
    md.append(f"{desc.strip()}\n")
    # Usage
    md.append("## Usage\n")
    md.append(f"```bash\nsayer {full_name} {sig}\n```\n")
    # Parameters
    md.append("## Parameters\n")
    md.append("| Name | Type | Required | Default | Description |")
    md.append("|------|------|----------|---------|-------------|")

    # Attempt to inspect original function for annotation-driven types
    orig_fn = getattr(cmd.callback, "_original_func", None)
    orig_sig = inspect.signature(orig_fn) if orig_fn else None

    for p in cmd.params:
        # Name label
        label = f"--{p.name}" if isinstance(p, click.Option) else f"<{p.name}>"
        # Type
        if orig_sig and p.name in orig_sig.parameters:
            anno = orig_sig.parameters[p.name].annotation
            raw = get_args(anno)[0] if get_origin(anno) is Annotated else anno
            typestr = raw.__name__.upper() if hasattr(raw, "__name__") else str(raw).upper()
        else:
            pt = p.type
            typestr = pt.name.upper() if getattr(pt, "name", None) else str(pt).upper()
        # Required
        req = getattr(p, "required", None)
        required = "Yes" if req else "No"
        # Default
        default = p.default
        default_str = "" if default in (None, inspect._empty) else str(default)
        # Description
        help_text = getattr(p, "help", "") or ""
        md.append(f"| {label} | {typestr} | {required} | {default_str} | {help_text} |")

    return "\n".join(md)


@docs.command()
def generate(
    output: Annotated[
        Path,
        Option(
            Path("docs"),
            "-o",
            show_default=True,
            help="Output directory for generated Markdown docs",
        ),
    ],
    force: Annotated[
        bool,
        Option(
            False,
            "-f",
            show_default=True,
            help="Forces the override of an existing folder",
        ),
    ],
) -> None:
    """
    Generate Markdown documentation for all Sayer commands and groups.
    """
    from sayer.core.client import app

    # Ensure output directory
    output = output.expanduser()

    if output.exists() and not force:
        error(f"Output directory '{output}' already exists. Use `--force` to overwrite.")
        return

    commands_dir = output / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    # Write top-level index
    index_file = output / "README.md"
    with index_file.open("w", encoding="utf-8") as idx:
        idx.write("# Sayer CLI Documentation\n\n")
        idx.write("## Commands\n\n")
        for name, cmd in app.cli.commands.items():
            if isinstance(cmd, click.Group):
                continue
            idx.write(f"- [{name}](commands/{name}.md)\n")
        idx.write("\n## Subcommands\n\n")
        for name, grp in app.cli.commands.items():
            if not isinstance(grp, click.Group):
                continue
            idx.write(f"### {name}\n\n")
            for sub in grp.commands:
                idx.write(f"- [{name} {sub}](commands/{name}-{sub}.md)\n")
            idx.write("\n")

    # Generate per-command docs
    # Top-level commands
    for name, cmd in app.cli.commands.items():
        if not isinstance(cmd, click.Group):
            (commands_dir / f"{name}.md").write_text(render_cmd(name, cmd), encoding="utf-8")
    # Group subcommands
    for name, grp in app.cli.commands.items():
        if not isinstance(grp, click.Group):
            continue
        for sub, sub_cmd in grp.commands.items():
            filename = f"{name}-{sub}.md"
            (commands_dir / filename).write_text(
                render_cmd(f"{name} {sub}", sub_cmd), encoding="utf-8"
            )

    success(f"Generated docs in {output}")
