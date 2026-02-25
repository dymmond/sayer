"""Performance benchmarks for the sayer CLI framework."""

import json
from dataclasses import dataclass
from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import command, get_commands, group
from sayer.encoders import (
    apply_structure,
    json_encode_default,
)
from sayer.params import JsonParam, Option

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Encoder benchmarks
# ---------------------------------------------------------------------------


@dataclass
class Point:
    x: int
    y: int


@pytest.mark.benchmark
def test_bench_json_encode_dataclass():
    """Benchmark serializing a dataclass through json_encode_default."""
    obj = Point(x=10, y=20)
    json.dumps(obj, default=json_encode_default)


@pytest.mark.benchmark
def test_bench_apply_structure_dataclass():
    """Benchmark molding a dict into a dataclass via apply_structure."""
    apply_structure(Point, {"x": 1, "y": 2})


@pytest.mark.benchmark
def test_bench_json_encode_list():
    """Benchmark serializing a set through json_encode_default."""
    json.dumps({1, 2, 3}, default=json_encode_default)


@pytest.mark.benchmark
def test_bench_apply_structure_list():
    """Benchmark molding a list through apply_structure."""
    apply_structure(list, [1, 2, 3])


# ---------------------------------------------------------------------------
# Command registration benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_command_registration():
    """Benchmark registering a simple command."""

    @command
    def bench_hello(name: str):
        click.echo(f"Hello {name}")


@pytest.mark.benchmark
def test_bench_command_registration_with_options():
    """Benchmark registering a command with multiple typed options."""

    @command
    def bench_greet(
        name: str,
        count: int = Option(default=1, help="Repeat count"),
        loud: bool = False,
    ):
        for _ in range(count):
            msg = f"Hello {name}"
            click.echo(msg.upper() if loud else msg)


# ---------------------------------------------------------------------------
# Command invocation benchmarks
# ---------------------------------------------------------------------------


@command
def invoke_simple(name: str):
    click.echo(f"Hi {name}")


@command
def invoke_options(
    name: str,
    count: int = Option(default=1, help="Repeat count"),
    loud: bool = False,
):
    for _ in range(count):
        msg = f"Hello {name}"
        click.echo(msg.upper() if loud else msg)


@command
def invoke_json(obj: Annotated[Point, JsonParam()]):
    click.echo(f"{obj.x},{obj.y}")


@pytest.mark.benchmark
def test_bench_invoke_simple_command(runner):
    """Benchmark invoking a simple command with a positional argument."""
    cmd = get_commands()["invoke-simple"]
    runner.invoke(cmd, ["World"])


@pytest.mark.benchmark
def test_bench_invoke_command_with_options(runner):
    """Benchmark invoking a command with options."""
    cmd = get_commands()["invoke-options"]
    runner.invoke(cmd, ["Alice", "--count", "3", "--loud"])


@pytest.mark.benchmark
def test_bench_invoke_json_command(runner):
    """Benchmark invoking a command that deserializes JSON input."""
    cmd = get_commands()["invoke-json"]
    runner.invoke(cmd, ["--obj", json.dumps({"x": 42, "y": 99})])


# ---------------------------------------------------------------------------
# Group benchmarks
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_bench_group_creation_and_command():
    """Benchmark creating a group and attaching a command."""
    grp = group("bench-grp")

    @grp.command()
    def bench_ping():
        click.echo("pong")
