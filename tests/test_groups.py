import click
import pytest
from click.testing import CliRunner

from sayer import Sayer, group
from sayer.testing import SayerTestClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sayer_runner():
    return SayerTestClient()


@pytest.fixture
def app() -> Sayer:
    app = Sayer(name="test", help="A test application")
    return app


example_group = group(name="nested", help="An example group")


@example_group.command(name="display", help="A command within the group")
def grouped_command():
    """Should simply echo once."""
    click.echo("hello from group")


def test_async_hello(runner, app: Sayer):
    app.add_command(example_group)

    result = runner.invoke(app.cli, ["nested", "display"])

    assert result.exit_code == 0
    assert result.output.strip() == "hello from group"


def test_async_hello_simple(app: Sayer):
    app.add_command(example_group)

    runner = SayerTestClient(app)

    result = runner.invoke(["nested", "display"])

    assert result.exit_code == 0
    assert result.output.strip() == "hello from group"
