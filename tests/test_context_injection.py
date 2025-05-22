import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import command, get_commands


# --- Test commands with Context injection ---
@command
def show_ctx_verbose(ctx: click.Context, msg: str):
    # Command should receive the context and the message
    click.echo(f"CTX:{ctx.command_path}")
    click.echo(f"MSG:{msg}")


@command
def count_ctx_usage_verbose(ctx: click.Context, repeat: int = 1):
    # Use ctx to determine how many times to echo
    for _ in range(repeat):
        click.echo(ctx.info_name)


@pytest.fixture
def runner():
    return CliRunner()


def test_show_ctx_injection(runner):
    cmd = get_commands()["show-ctx-verbose"]
    result = runner.invoke(cmd, ["hello"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()

    # First line should show the command path
    assert lines[0] == "CTX:show-ctx-verbose"
    # Second line should show the message
    assert lines[1] == "MSG:hello"


def test_count_ctx_usage_default(runner):
    cmd = get_commands()["count-ctx-usage-verbose"]
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    # Default repeat is 1, so one line with command name
    assert result.output.strip() == "count-ctx-usage-verbose"


def test_count_ctx_usage_repeat(runner):
    cmd = get_commands()["count-ctx-usage-verbose"]
    result = runner.invoke(cmd, ["--repeat", "3"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["count-ctx-usage-verbose"] * 3
