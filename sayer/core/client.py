import sayer.cli.docs  # noqa
from sayer.__version__ import get_version
from sayer.app import Sayer
from sayer.core.commands.sayer import SayerCommand
from sayer.core.engine import get_commands, get_groups

help_text = """**Sayer** CLI: Your essential command-line tool for any project.

The ultimate tool for managing and running your Sayer projects and apps.

Read more in the docs: https://sayer.dymmond.com
"""

app = Sayer(
    name="sayer",
    help=help_text,
    add_version_option=True,
    version=get_version(),
)

# 1️⃣ Wrap and add all *top-level* commands
for cmd in get_commands().values():
    cmd_cls = SayerCommand(
        name=cmd.name,
        callback=cmd.callback,
        params=cmd.params,
        help=cmd.help,
        context_settings=cmd.context_settings,
        add_help_option=cmd.add_help_option,
        short_help=cmd.short_help,
        epilog=cmd.epilog,
        hidden=cmd.hidden,
        no_args_is_help=cmd.no_args_is_help,
        deprecated=cmd.deprecated,
    )
    app.add_command(cmd_cls)

# 2️⃣ For each group, rewrap *its* subcommands before adding the group itself
for alias, group_cmd in get_groups().items():
    # Ensure the group itself is using SayerGroup
    group_cmd.cls = app.cli.__class__

    # Capture existing subcommands
    original = list(group_cmd.commands.items())
    # Remove them so we can re-add wrapped versions
    for name, _ in original:
        group_cmd.commands.pop(name)

    # Re-add each as SayerCommand
    for name, cmd in original:
        wrapped = SayerCommand(
            name=cmd.name,
            callback=cmd.callback,
            params=cmd.params,
            help=cmd.help,
            context_settings=cmd.context_settings,
            add_help_option=cmd.add_help_option,
            short_help=cmd.short_help,
            epilog=cmd.epilog,
            hidden=cmd.hidden,
            no_args_is_help=cmd.no_args_is_help,
            deprecated=cmd.deprecated,
        )
        group_cmd.add_command(wrapped, name=name)

    # Finally register the group under the main CLI
    app.cli.add_command(group_cmd, name=alias)


def run() -> None:
    """Entry point for the Sayer CLI application."""
    app()
