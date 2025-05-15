import click

from sayer.core import get_commands


@click.group()
def cli():
    """Sayer CLI Application"""
    pass

def run():
    for name, cmd in get_commands().items():
        cli.add_command(cmd)
    cli()
