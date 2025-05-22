import time
import uuid
from datetime import datetime

import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import command, get_commands
from sayer.params import Option


@pytest.fixture
def runner():
    return CliRunner()


# 1) datetime.utcnow factory
@command
def now(ts: datetime = Option(default_factory=datetime.utcnow)):
    click.echo(ts.isoformat())


def test_now_dynamic_default_unique(runner):
    cmd = get_commands()["now"]
    r1 = runner.invoke(cmd, [])
    time.sleep(0.01)
    r2 = runner.invoke(cmd, [])

    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert r1.output != r2.output


def test_now_override_with_explicit(runner):
    cmd = get_commands()["now"]
    iso = "2025-05-20T15:30:00"
    result = runner.invoke(cmd, ["--ts", iso])

    assert result.exit_code == 0
    assert result.output.strip() == iso


# 2) incremental integer factory
counter = {"n": 0}


def make_counter():
    counter["n"] += 1

    return counter["n"]


@command
def count(n: int = Option(default_factory=make_counter)):
    click.echo(str(n))


def test_count_factory_increments(runner):
    cmd = get_commands()["count"]
    # first invocation → "1"
    r1 = runner.invoke(cmd, [])

    assert r1.exit_code == 0 and r1.output.strip() == "1"
    # second → "2"

    r2 = runner.invoke(cmd, [])

    assert r2.exit_code == 0 and r2.output.strip() == "2"


def test_count_override(runner):
    cmd = get_commands()["count"]
    result = runner.invoke(cmd, ["--n", "42"])

    assert result.exit_code == 0
    assert result.output.strip() == "42"


# 3) string factory
def make_greeting():
    return "hello-" + uuid.uuid4().hex[:6]


@command
def greetings(name: str = Option(default_factory=make_greeting)):
    click.echo(name)


def test_greet_dynamic(runner):
    cmd = get_commands()["greetings"]
    r1 = runner.invoke(cmd, [])
    time.sleep(0.001)
    r2 = runner.invoke(cmd, [])

    assert r1.exit_code == 0 and r2.exit_code == 0

    # both non-empty and different
    assert r1.output.strip() != r2.output.strip()
    assert r1.output.strip().startswith("hello-")


def test_greet_override(runner):
    cmd = get_commands()["greetings"]
    result = runner.invoke(cmd, ["--name", "Alice"])

    assert result.exit_code == 0
    assert result.output.strip() == "Alice"


# 4) UUID factory
@command
def ident(u: uuid.UUID = Option(default_factory=uuid.uuid4)):
    click.echo(str(u))


def test_ident_factory_uuid(runner):
    cmd = get_commands()["ident"]
    r1 = runner.invoke(cmd, [])
    r2 = runner.invoke(cmd, [])
    assert r1.exit_code == 0 and r2.exit_code == 0

    # both valid UUIDs
    uuid.UUID(r1.output.strip())
    uuid.UUID(r2.output.strip())

    # but different
    assert r1.output != r2.output


def test_ident_override(runner):
    cmd = get_commands()["ident"]
    uid = uuid.uuid4()
    result = runner.invoke(cmd, ["--u", str(uid)])

    assert result.exit_code == 0
    assert result.output.strip() == str(uid)


# 5) Mixed with context injection
@command
def show_time(ctx: click.Context, ts: datetime = Option(default_factory=datetime.utcnow)):
    click.echo(f"{ctx.info_name}:{ts.isoformat()}")


def test_show_time_dynamic(runner):
    cmd = get_commands()["show-time"]
    r1 = runner.invoke(cmd, [])
    time.sleep(0.01)
    r2 = runner.invoke(cmd, [])

    assert r1.exit_code == 0 and r2.exit_code == 0
    # prefix is command name
    assert r1.output.startswith("show-time:")
    assert r2.output.startswith("show-time:")
    # timestamps differ
    assert r1.output != r2.output


def test_show_time_override(runner):
    cmd = get_commands()["show-time"]
    iso = "2025-01-01T00:00:00"
    result = runner.invoke(cmd, ["--ts", iso])

    assert result.exit_code == 0
    assert result.output.strip() == f"show-time:{iso}"


# 6) Combined multiple default_factory parameters
@command
def combo(
    a: int = Option(default_factory=lambda: 10), b: str = Option(default_factory=lambda: "X")
):
    click.echo(f"{a}-{b}")


def test_combo_defaults(runner):
    cmd = get_commands()["combo"]
    res = runner.invoke(cmd, [])

    assert res.exit_code == 0
    a, b = res.output.strip().split("-")

    assert int(a) == 10
    assert b == "X"


def test_combo_override_partial(runner):
    cmd = get_commands()["combo"]
    res = runner.invoke(cmd, ["--a", "7"])

    assert res.exit_code == 0
    assert res.output.strip().startswith("7-")
