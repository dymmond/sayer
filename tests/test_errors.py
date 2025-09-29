from typing import Annotated

import click
import pytest

from sayer import Argument, command
from sayer.app import Sayer
from sayer.testing import SayerTestClient


def test_raise_value_error_on_default_with_nargs():
    """
    Test that a ValueError is raised when a command with nargs is defined with a default value.
    """
    with pytest.raises(ValueError):

        @command
        def foo(arg: Annotated[str, Argument(nargs=-1, default="default")]): ...


def test_invalid_option_renders_custom_error(capsys):
    app = Sayer(name="myapp")

    @app.command()
    def hello():
        """Simple hello command"""
        click.echo("hello")

    client = SayerTestClient(app)
    result = client.invoke(["hello", "--not-an-option"])

    # It should fail
    assert result.exit_code != 0

    # Capture Rich-rendered error output
    out = result.output

    # Check that our Rich "Error:" line is present
    assert "Error:" in out
    assert "Usage:" in out
    assert "--not-an-option" in out


def test_missing_argument_renders_custom_error():
    app = Sayer(name="myapp")

    @app.command()
    @click.argument("name")
    def greet(name):
        click.echo(f"hello {name}")

    client = SayerTestClient(app)
    result = client.invoke(["greet"])  # missing required argument

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Usage:" in result.output
    assert "Missing argument 'NAME'" in result.output
