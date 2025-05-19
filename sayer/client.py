import sayer.docs as docs  # noqa
from sayer.app import RichCommand, Sayer
from sayer.core import get_commands, get_groups

app = Sayer(
    name="sayer",
    help="Sayer CLI Application",
    add_version_option=True,
    version="1.2.3",
)

# Bulk register all commands using RichCommand
for cmd in get_commands().values():
    cmd_cls = RichCommand(
        name=cmd.name,
        callback=cmd.callback,
        params=cmd.params,
        help=cmd.help,
    )
    app.cli.add_command(cmd_cls)

# Register all groups, including 'docs'
for alias, group_cmd in get_groups().items():
    group_cmd.cls = app.cli.__class__  # enforce RichGroup
    app.cli.add_command(group_cmd, name=alias)


def run() -> None:
    """
    Entry point for the Sayer CLI application.
    """
    app()
