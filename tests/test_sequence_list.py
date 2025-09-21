import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import Option, command, get_commands


@pytest.fixture
def runner():
    return CliRunner()


@command
def mail(name: list[str] = Option(required=True, help="Name is required")):
    click.echo(f"{name}")


def test_list(runner):
    result = runner.invoke(get_commands()["mail"], ["--name", "test", "--name", "another"])  # no --name provided

    assert result.exit_code == 0

    assert "test" in result.output
    assert "another" in result.output
