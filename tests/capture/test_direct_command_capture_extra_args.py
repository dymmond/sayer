from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer import command
from sayer.params import Argument, Option


@pytest.fixture
def runner():
    return CliRunner()

cmd_direct = command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)(lambda: None)  # placeholder to get a Command object

# Replace the placeholder function with our real handler:
@command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def cmd_direct( # noqa
    directive: Annotated[
        str,
        Option(required=True, help="The name of the directive to run.")
    ],
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


def test_direct_unknown_flags_are_captured(runner):
    # Invoke the command itself, not via Sayer
    result = runner.invoke(cmd_direct, ["--directive", "create", "-n", "Esmerald"])
    assert result.exit_code == 0
    assert "create → ('-n', 'Esmerald')" in result.output

def test_direct_explicit_separator_works(runner):
    result = runner.invoke(
        cmd_direct,
        ["--directive", "create", "--", "foo", "bar", "--baz"]
    )
    assert result.exit_code == 0
    assert "create → ('foo', 'bar', '--baz')" in result.output

def test_direct_missing_directive_fails(runner):
    result = runner.invoke(cmd_direct, ["-n", "Esmerald"])
    assert result.exit_code != 0
    assert "Missing option '--directive'" in result.output
