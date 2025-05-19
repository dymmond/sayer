import inspect
from pathlib import Path
from typing import Annotated, get_args, get_origin

import click

from sayer.core import get_commands, get_groups, group
from sayer.params import Option
from sayer.ui import success

# Create the 'docs' subgroup
docs = group(
    "docs",
    help="Generate Markdown documentation for all Sayer commands and groups.",
)


def _generate_signature(cmd: click.Command) -> str:
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
        Path,
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
    output = output.expanduser()
    commands_dir = output / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    # 1️⃣ Write top-level README.md
    with (output / "README.md").open("w", encoding="utf-8") as idx:
        idx.write("# Sayer CLI Documentation\n\n")
        # Top-level commands
        idx.write("## Commands\n\n")
        for name, _ in sorted(get_commands().items()):
            idx.write(f"- [{name}](commands/{name}.md)\n")
        idx.write("\n")
        # Groups and their sub-commands
        for grp_name, grp_cmd in sorted(get_groups().items()):
            idx.write(f"### {grp_name}\n\n")
            for sub_name in sorted(grp_cmd.commands):
                file = f"{grp_name}-{sub_name}.md"
                idx.write(f"- [{grp_name} {sub_name}](commands/{file})\n")
            idx.write("\n")

    # 2️⃣ Generate Markdown per command
    def render_cmd(full_name: str, cmd: click.Command):
        sig = _generate_signature(cmd)
        md = []
        md.append(f"# sayer {full_name}\n")
        desc = cmd.help or inspect.getdoc(cmd.callback) or "No description provided."
        md.append(f"{desc.strip()}\n")
        md.append("## Usage\n")
        md.append(f"```bash\nsayer {full_name} {sig}\n```\n")
        md.append("## Parameters\n")
        md.append("| Name | Type | Required | Default | Description |")
        md.append("|------|------|----------|---------|-------------|")
        # Attempt to get original fn for annotation-based types
        orig_fn = getattr(cmd.callback, "_original_func", None)
        orig_sig = inspect.signature(orig_fn) if orig_fn else None

        for p in cmd.params:
            label = f"--{p.name}" if isinstance(p, click.Option) else f"<{p.name}>"
            # Type
            if orig_sig and p.name in orig_sig.parameters:
                ann = orig_sig.parameters[p.name].annotation
                if get_origin(ann) is Annotated:
                    raw = get_args(ann)[0]
                else:
                    raw = ann
                typestr = raw.__name__.upper() if hasattr(raw, "__name__") else str(raw).upper()
            else:
                pt = p.type
                typestr = (pt.name.upper() if hasattr(pt, "name") else str(pt)).upper()
            # Required
            req = getattr(p, "required", None)
            if req is None:
                required = "Yes" if isinstance(p, click.Argument) and p.required else "No"
            else:
                required = "Yes" if req else "No"
            # Default
            default = p.default
            default_str = "" if default in (None, inspect._empty) else str(default)
            # Help
            help_txt = getattr(p, "help", "") or ""
            md.append(f"| {label} | {typestr} | {required} | {default_str} | {help_txt} |")
        return "\n".join(md)

    # render each top-level cmd
    for name, cmd in get_commands().items():
        (commands_dir / f"{name}.md").write_text(render_cmd(name, cmd), encoding="utf-8")

    # render each subgroup cmd
    for grp_name, grp_cmd in get_groups().items():
        for sub_name, sub_cmd in grp_cmd.commands.items():
            full = f"{grp_name} {sub_name}"
            filename = f"{grp_name}-{sub_name}.md"
            (commands_dir / filename).write_text(render_cmd(full, sub_cmd), encoding="utf-8")

    success(f"Generated docs in {output}")
