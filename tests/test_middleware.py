import pytest
from click.testing import CliRunner

from sayer.core.engine import command, get_commands
from sayer.middleware import (
    _GLOBAL_AFTER,
    _GLOBAL_BEFORE,
    _MIDDLEWARE_REGISTRY,
    add_after_global,
    add_before_global,
    register,
    resolve,
)


@pytest.fixture(autouse=True)
def clear_middleware_registry():
    """
    Clear all middleware state before each test to ensure isolation.
    """
    _MIDDLEWARE_REGISTRY.clear()
    _GLOBAL_BEFORE.clear()
    _GLOBAL_AFTER.clear()
    # Also clear commands to avoid name collisions
    get_commands().clear()
    yield
    _MIDDLEWARE_REGISTRY.clear()
    _GLOBAL_BEFORE.clear()
    _GLOBAL_AFTER.clear()
    get_commands().clear()


def test_direct_callable_before_and_after_hooks():
    events = []

    def before_hook(cmd_name, args):
        events.append(f"before:{cmd_name}")

    def after_hook(cmd_name, args, result):
        events.append(f"after:{cmd_name}")

    @command(middleware=[before_hook, after_hook])
    def foo():
        events.append("run:foo")

    runner = CliRunner()
    result = runner.invoke(get_commands()["foo"], [])

    assert result.exit_code == 0
    assert events == ["before:foo", "run:foo", "after:foo"]


def test_named_middleware_sets_and_resolution():
    events = []

    def log_start(cmd_name, args):
        events.append(f"start:{cmd_name}")

    def log_end(cmd_name, args, result):
        events.append(f"end:{cmd_name}")

    # Register a named middleware set
    register("logging", before=[log_start], after=[log_end])

    @command(middleware=["logging"])
    def bar():
        events.append("run:bar")

    runner = CliRunner()
    result = runner.invoke(get_commands()["bar"], [])

    assert result.exit_code == 0
    # Ensure before, run, after order
    assert events == ["start:bar", "run:bar", "end:bar"]


def test_combined_named_and_direct_middleware():
    events = []

    def log_start(cmd_name, args):
        events.append(f"startNamed:{cmd_name}")

    def log_end(cmd_name, args, result):
        events.append(f"endNamed:{cmd_name}")

    def direct_hook(cmd_name, args):
        events.append(f"directBefore:{cmd_name}")

    # Register named set
    register("named", before=[log_start], after=[log_end])

    @command(middleware=["named", direct_hook])
    def baz():
        events.append("run:baz")

    runner = CliRunner()
    result = runner.invoke(get_commands()["baz"], [])

    assert result.exit_code == 0
    # Order: named before, direct before, run, named after
    assert events == [
        "startNamed:baz",
        "directBefore:baz",
        "run:baz",
        "endNamed:baz",
    ]


def test_global_before_and_after_hooks():
    events = []

    def global_before(cmd_name, args):
        events.append(f"globalBefore:{cmd_name}")

    def global_after(cmd_name, args, result):
        events.append(f"globalAfter:{cmd_name}")

    # Register global hooks
    add_before_global(global_before)
    add_after_global(global_after)

    @command
    def qux():
        events.append("run:qux")

    runner = CliRunner()
    result = runner.invoke(get_commands()["qux"], [])

    assert result.exit_code == 0
    assert events == ["globalBefore:qux", "run:qux", "globalAfter:qux"]


def test_resolve_nonexistent_named_middleware():
    # resolve should ignore unknown names
    before, after = resolve(["does_not_exist"])

    assert before == []
    assert after == []


def test_middleware_registry_contents():
    # After registering, registry should contain the entries
    register("testset", before=[lambda n, a: None], after=[lambda n, a, r: None])

    assert "testset" in _MIDDLEWARE_REGISTRY
    assert isinstance(_MIDDLEWARE_REGISTRY["testset"]["before"], list)
    assert isinstance(_MIDDLEWARE_REGISTRY["testset"]["after"], list)
