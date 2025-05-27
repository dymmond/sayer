# tests/test_capture_extra_args.py
from typing import Annotated

import click
import pytest

from sayer import Sayer, command
from sayer.params import Argument, Option
from sayer.testing import SayerTestClient

# 1) Create your Sayer app
app = Sayer(name="test-app")


# 2) Define & register the `run` command, enabling both settings
@command(
    name="run",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
def cmd_no_extra(
    directive: Annotated[str, Option(required=True, help="The name of the directive to run.")],
    directive_args: Annotated[
        str,
        Argument(
            nargs=-1,
            type=click.UNPROCESSED,
            help="Extra flags/args to pass through.",
        ),
    ],
) -> None:
    """Echo back what was passed in."""
    click.echo(f"{directive} → {directive_args}")


app.add_command(cmd_no_extra)


@pytest.fixture
def client():
    return SayerTestClient(app)


def test_unknown_flags_are_captured(client):
    # "-n Esmerald" is unknown, so with both settings it ends up in directive_args
    result = client.invoke(["run", "--directive", "create", "-n", "Esmerald"])
    assert result.exit_code == 0
    assert "create → ('-n', 'Esmerald')" in result.output


def test_explicit_separator_still_works(client):
    # Everything after "--" should go into directive_args, even if they look like flags
    result = client.invoke(["run", "--directive", "create", "--", "foo", "bar", "--baz"])
    assert result.exit_code == 0
    assert "create → ('foo', 'bar', '--baz')" in result.output


def test_missing_directive_fails(client):
    # Omitting the required --directive should still error out
    result = client.invoke(["run", "-n", "Esmerald"])
    assert result.exit_code != 0
    assert "Missing option '--directive'" in result.output
