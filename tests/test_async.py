from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import Option, command, get_commands
from sayer.state import State


@pytest.fixture
def runner():
    return CliRunner()


@command
async def async_hello():
    """Should simply echo once, asynchronously."""
    click.echo("hello async")


def test_async_hello(runner):
    result = runner.invoke(get_commands()["async-hello"], [])

    assert result.exit_code == 0
    assert result.output.strip() == "hello async"


@command
async def async_add(a: int, b: Annotated[int, Option(default=1)]):
    """Echo a + b, asynchronously."""
    click.echo(str(a + b))


def test_async_add_default(runner):
    # b defaults to 1
    result = runner.invoke(get_commands()["async-add"], ["5"])

    assert result.exit_code == 0
    assert result.output.strip() == "6"


def test_async_add_override(runner):
    # override b on the CLI
    result = runner.invoke(get_commands()["async-add"], ["5", "--b", "4"])

    assert result.exit_code == 0
    assert result.output.strip() == "9"


@command
async def async_fail():
    """Raise a ClickException asynchronously."""
    raise click.ClickException("async failure")


def test_async_fail(runner):
    result = runner.invoke(get_commands()["async-fail"], [])

    assert result.exit_code != 0
    assert "async failure" in result.output


@command
async def async_ctx(ctx: click.Context, name: str):
    """Echo the command name and the provided name asynchronously."""
    click.echo(f"{ctx.info_name}:{name}")


def test_async_ctx(runner):
    result = runner.invoke(get_commands()["async-ctx"], ["Alice"])

    assert result.exit_code == 0
    assert result.output.strip() == "async-ctx:Alice"


class Counter(State):
    def __init__(self):
        # increment a counter each construction
        self.value = getattr(self, "value", 0) + 1


@command
async def async_state(s: Counter):
    """Echo the per-invocation Counter.value asynchronously."""
    click.echo(str(s.value))


def test_async_state_cache(runner):
    cmd = get_commands()["async-state"]
    # Each invocation should create a fresh Counter, so .value == 1 both times
    r1 = runner.invoke(cmd, [])
    r2 = runner.invoke(cmd, [])

    assert r1.exit_code == 0 and r1.output.strip() == "1"
    assert r2.exit_code == 0 and r2.output.strip() == "1"
