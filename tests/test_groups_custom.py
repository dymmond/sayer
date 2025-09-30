import click
import pytest
from click.testing import CliRunner

from sayer import Sayer, group
from sayer.core.engine import GROUPS
from sayer.testing import SayerTestClient


@pytest.fixture(autouse=True)
def reset_groups():
    GROUPS.clear()
    yield
    GROUPS.clear()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def app() -> Sayer:
    app = Sayer(name="test", help="A test application")
    return app


@pytest.fixture
def sayer_runner(app):
    return SayerTestClient(app)


def test_shows_custom_group(sayer_runner, app: Sayer):
    example_group = group(name="nested", help="An example group", is_custom=True, custom_command_name="Example Group 2")

    @example_group.command(name="display", help="A command within the group")
    def grouped_command():
        """Should simply echo once."""
        click.echo("hello from group")

    app.add_command(example_group)

    result = sayer_runner.invoke(["nested", "display"])

    assert result.exit_code == 0
    assert result.output.strip() == "hello from group"


def test_shows_custom_group_text(app: Sayer):
    example_group = group(name="nested", help="An example group", is_custom=True, custom_command_name="Example Group 2")

    @example_group.command(name="display", help="A command within the group")
    def grouped_command():
        """Should simply echo once."""
        click.echo("hello from group")

    app.add_command(example_group)

    runner = SayerTestClient(app)

    result = runner.invoke([])

    assert result.exit_code == 0
    assert "Example Group 2" in result.output
    assert "nested" in result.output


def test_shows_custom_groups_text(app: Sayer):
    example_group = group(name="nested", help="An example group", is_custom=True, custom_command_name="Example Group 2")

    @example_group.command(name="display", help="A command within the group")
    def grouped_command():
        """Should simply echo once."""
        click.echo("hello from group")

    another_group = group(name="trains", help="An example group", is_custom=True, custom_command_name="Another Group")

    @another_group.command(name="display", help="A command within the group")
    def grouped_another_command():
        """Should simply echo once."""
        click.echo("hello from another")

    app.add_command(example_group)
    app.add_command(another_group)

    runner = SayerTestClient(app)

    result = runner.invoke([])

    assert result.exit_code == 0
    assert "Example Group 2" in result.output
    assert "nested" in result.output
    assert "Another Group" in result.output
    assert "trains" in result.output


def test_make_calls_to_both_groups_text(app: Sayer):
    example_group = group(name="nested", help="An example group", is_custom=True, custom_command_name="Example Group 2")

    @example_group.command(name="display", help="A command within the group")
    def grouped_command():
        """Should simply echo once."""
        click.echo("hello from group")

    another_group = group(name="trains", help="An example group", is_custom=True, custom_command_name="Another Group")

    @another_group.command(name="display", help="A command within the group")
    def grouped_another_command():
        """Should simply echo once."""
        click.echo("hello from another")

    app.add_command(example_group)
    app.add_command(another_group)

    runner = SayerTestClient(app)

    result = runner.invoke(["nested", "display"])
    assert result.exit_code == 0
    assert "hello from group" in result.output

    result = runner.invoke(["trains", "display"])
    assert result.exit_code == 0
    assert "hello from another" in result.output
