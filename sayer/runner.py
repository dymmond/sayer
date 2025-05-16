import click

from sayer.core import get_commands, get_groups
from sayer.help import render_help_for_command
from sayer.ui import RichGroup


class RichCommand(click.Command):
    def get_help(self, ctx):
        render_help_for_command(ctx)


@click.group(cls=RichGroup, add_help_option=True)
def cli():
    """Sayer CLI Application"""
    ...


def run():
    for _name, cmd in get_commands().items():
        cmd_cls = RichCommand(name=cmd.name, callback=cmd.callback, params=cmd.params, help=cmd.help)
        cli.add_command(cmd_cls)

    for _name, group_cmd in get_groups().items():
        group_cmd.cls = RichGroup
        cli.add_command(group_cmd)
    cli()
