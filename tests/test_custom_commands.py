import click

from sayer.app import Sayer
from sayer.testing import SayerTestClient


def test_custom_command_runs_and_outputs():
    app = Sayer(name="myapp")

    @click.command()
    def shout():
        """Custom shout command"""
        click.echo("HELLO!")

    app.add_custom_command("shout", shout)

    client = SayerTestClient(app)
    result = client.invoke(["shout"])

    assert result.exit_code == 0
    assert "HELLO!" in result.output


def test_help_lists_custom_commands():
    app = Sayer(name="myapp")

    @click.command()
    def shout():
        """Custom shout command"""
        click.echo("HELLO!")

    app.add_custom_command("shout", shout)

    client = SayerTestClient(app)
    result = client.invoke(["--help"])

    assert result.exit_code == 0

    output = result.output

    assert "Custom" in output
    assert "shout" in output
    assert "Custom shout command" in output
