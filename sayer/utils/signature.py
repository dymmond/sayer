import click


def generate_signature(cmd: click.Command) -> str:
    """
    Build a minimal signature string like "<arg> [--flag <flag>]" for usage output.
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
