import os

import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import COMMANDS, command, get_commands, get_groups, group
from sayer.state import _STATE_REGISTRY, State, get_state_classes


@pytest.fixture(autouse=True)
def clear_registry_and_commands():
    # Clear the state registry and the command registry before each test
    _STATE_REGISTRY.clear()
    COMMANDS.clear()
    get_groups().clear()
    yield
    _STATE_REGISTRY.clear()
    COMMANDS.clear()
    get_groups().clear()


def test_state_subclass_registration():
    class X(State):
        pass

    assert X in get_state_classes()


def test_no_states_registered_initially():
    # After clearing, no State subclasses remain
    assert get_state_classes() == []


def test_single_state_injection():
    class S(State):
        def __init__(self):
            self.v = 42

    @command
    def foo(s: S):
        click.echo(str(s.v))

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])
    assert result.exit_code == 0
    assert result.output.strip() == "42"


def test_multiple_state_injection():
    class A(State):
        def __init__(self):
            self.v = "a"

    class B(State):
        def __init__(self):
            self.v = "b"

    @command
    def foo(a: A, b: B):
        click.echo(f"{a.v},{b.v}")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])
    assert result.exit_code == 0
    assert result.output.strip() == "a,b"


def test_state_and_normal_args_mix():
    class S(State):
        def __init__(self):
            self.flag = True

    @command
    def foo(name: str, count: int, s: S):
        click.echo(f"{name}:{count}:{s.flag}")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], ["Alice", "3"])
    assert result.exit_code == 0
    assert result.output.strip() == "Alice:3:True"


def test_state_not_treated_as_arg_or_option():
    class S(State):
        def __init__(self):
            self.v = 1

    @command
    def foo(s: S):
        click.echo(str(s.v))

    # Passing an extra CLI argument should error (no args expected)
    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], ["unexpected"])
    assert result.exit_code != 0
    assert "Got unexpected extra argument" in result.output or "Error" in result.output


def test_state_and_context_injection():
    class S(State):
        def __init__(self):
            self.v = "ctxstate"

    @command
    def foo(ctx: click.Context, s: S):
        click.echo(f"{ctx.info_name}-{s.v}")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])
    assert result.exit_code == 0
    assert result.output.strip() == "foo-ctxstate"


def test_same_state_twice_in_signature():
    class S(State):
        def __init__(self):
            self.id = id(self)

    @command
    def foo(s1: S, s2: S):
        click.echo(str(s1.id == s2.id))

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])
    assert result.exit_code == 0
    assert result.output.strip() == "True"


def test_state_cache_one_per_invocation():
    calls = []

    class S(State):
        def __init__(self):
            calls.append("c")

    @command
    def foo(s: S):
        click.echo("ok")

    runner = CliRunner()
    runner.invoke(get_commands()["foo"], [])
    # __init__ called exactly once per invocation
    assert calls == ["c"]


def test_state_reconstructed_across_invocations():
    calls = []

    class S(State):
        def __init__(self):
            calls.append("c")

    @command
    def foo(s: S):
        click.echo("ok")

    runner = CliRunner()
    runner.invoke(get_commands()["foo"], [])
    runner.invoke(get_commands()["foo"], [])
    # Two separate invocations => two constructions
    assert calls == ["c", "c"]


def test_state_with_dataclass_defaults():
    from dataclasses import dataclass

    @dataclass
    class Cfg(State):
        debug: bool = True
        name: str = "app"

    @command
    def foo(cfg: Cfg):
        click.echo(f"{cfg.debug},{cfg.name}")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])

    assert result.exit_code == 0
    assert result.output.strip() == "True,app"


def test_state_env_dependent(monkeypatch):
    class E(State):
        def __init__(self):
            self.val = os.getenv("TEST_VAL", "none")

    monkeypatch.setenv("TEST_VAL", "hello")

    @command
    def foo(e: E):
        click.echo(e.val)

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])

    assert result.exit_code == 0
    assert result.output.strip() == "hello"


def test_state_custom_init_failure():
    class Bad(State):
        def __init__(self):
            raise RuntimeError("fail")

    @command
    def foo(b: Bad):
        click.echo("never")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])

    assert result.exit_code != 0
    assert "fail" in result.output


def test_no_state_defined_command_works():
    @command
    def foo(x: int):
        click.echo(str(x * 2))

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], ["5"])

    assert result.exit_code == 0
    assert result.output.strip() == "10"


def test_state_instantiation_order():
    order = []

    class A(State):
        def __init__(self):
            order.append("A")

    class B(State):
        def __init__(self):
            order.append("B")

    @command
    def foo(a: A, b: B):
        click.echo(",".join(order))

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])

    assert result.exit_code == 0
    assert result.output.strip() == "A,B"


def test_state_registry_is_isolated_across_tests():
    # Previously registered states should not leak here
    assert get_state_classes() == []


def test_group_command_state_injection():
    class S(State):
        def __init__(self):
            self.msg = "grouped"

    grp = group("grp")

    @grp.command
    def sub(s: S):
        click.echo(s.msg)

    runner = CliRunner()
    result = runner.invoke(grp, ["sub"])

    assert result.exit_code == 0
    assert result.output.strip() == "grouped"


def test_state_injection_ignores_unrelated_annotations():
    class S(State):
        def __init__(self):
            self.v = 1

    @command
    def foo(x: float):
        click.echo(str(x))

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], ["3.14"])

    assert result.exit_code == 0
    assert result.output.strip() == "3.14"


def test_state_registry_ordered():
    class A(State):
        pass

    class B(State):
        pass

    classes = get_state_classes()

    assert classes == [A, B]
