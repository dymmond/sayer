import sys
from inspect import isawaitable
from pathlib import Path
from pkgutil import ModuleInfo
from typing import Annotated, Any

import click

from sayer.core.engine import command
from sayer.params import Argument
from sayer.utils.loader import find_directives_from
from sayer.utils.ui import echo, error


def extractor(path: Path, module: ModuleInfo) -> tuple[str, Any]:
    app_name = getattr(module, "app_name", path.parent.parent.parent.name)
    return app_name, module.Directive


@command(
    context_settings={
        "allow_interspersed_args": False
    },
)
async def directive(
    directive: Annotated[
        str,
        Argument("", required=False, help="The name of the directive to execute. Leave empty to list directives."),
    ],
    directive_args: Annotated[
        list[str],
        Argument(
            nargs=-1,
            type=click.UNPROCESSED,
            help="The arguments needed to be passed to the custom directive",
            required=False,
        ),
    ],
) -> None:
    custom_directives = find_directives_from(path=Path.cwd(), pattern="**/directives/operations/", extractor=extractor)
    directives_by_name = {}
    directives_by_app_and_name = {}
    for directive_tuple in custom_directives.values():
        if directive_tuple is not None:
            name = directive_tuple[0].stem
            app_name = directive_tuple[1]
            if (app_name, name) in directives_by_app_and_name:
                directives_by_app_and_name[(app_name, name)] = None
            if name in directives_by_name:
                directives_by_name[name] = None
                continue
            directives_by_app_and_name[(app_name, name)] = directive_tuple[2]
            directives_by_name[name] = directive_tuple[2]

    if not directive:
        echo(
            "\n".join(
                [
                    "",
                    "Type '<directive> <subcommand> --help' for help on a specific subcommand.",
                    "",
                    "Available directives:",
                ]
            )
        )
        last_app = None
        for app, name in sorted(directives_by_app_and_name.keys()):
            if last_app != app:
                echo("\n")
                echo(f"[bold green]\\[{app}]\n")
            echo(f"    [bold blue]{name}\n")
            last_app = app
    else:
        if "." in directive:
            tup = tuple(directive.split(".", 1))
            if tup not in directives_by_app_and_name:
                error(f"Fully specified directive: {directive} not found.")
                sys.exit(1)
            retrieved = directives_by_app_and_name[tup]
            if retrieved is None:
                error(f"Directive: `{directive}` could not be uniquely resolved.")
                sys.exit(1)
            result = retrieved(*directive_args)
        else:
            if directive not in directives_by_name:
                error(f"Directive: `{directive}` not found.")
                sys.exit(1)
            retrieved = directives_by_name[directive]
            if retrieved is None:
                error(f"Directive: `{directive}` could not be uniquely resolved.")
                sys.exit(1)
            result = retrieved(*directive_args)
        if isawaitable(result):
            result = await result
