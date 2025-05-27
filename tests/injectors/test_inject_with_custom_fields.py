import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

import click

from sayer import Sayer, command
from sayer.core.groups import SayerGroup
from sayer.testing import SayerTestClient

T = typing.TypeVar("T")


@dataclass
class EnvTest:
    name: str = "test"


@dataclass
class NameTest:
    name: str = "Sayer"


class TestGroup(SayerGroup):
    def add_command(self, cmd: click.Command, name: str | None = None) -> None:
        if cmd.callback:
            cmd.callback = self.wrap_args(cmd.callback)
        return super().add_command(cmd, name)

    def wrap_args(self, func: Callable[..., T]) -> Callable[..., T]:
        original = inspect.unwrap(func)
        params = inspect.signature(original).parameters

        @wraps(func)
        def wrapped(ctx: click.Context, /, *args: typing.Any, **kwargs: typing.Any) -> T:
            scaffold = ctx.ensure_object(EnvTest)
            if "env" in params:
                kwargs["env"] = scaffold
            return func(*args, **kwargs)

        # click.pass_context makes sure that 'ctx' is the first argument
        return click.pass_context(wrapped)


def test_inject_custom():
    @command(
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        },
    )
    def custom_command(env: EnvTest):
        click.echo(f"Injected env: {env.name}")

    app = Sayer(name="test", help="Test group", group_class=TestGroup)
    app.add_command(custom_command)

    runner = SayerTestClient(app)

    result = runner.invoke(["custom-command"])

    assert result.exit_code == 0
    assert result.output.strip() == "Injected env: test"


class NewGroup(SayerGroup):
    def add_command(self, cmd: click.Command, name: str | None = None) -> None:
        if cmd.callback:
            cmd.callback = self.wrap_args(cmd.callback)
        return super().add_command(cmd, name)

    def wrap_args(self, func: Callable[..., T]) -> Callable[..., T]:
        original = inspect.unwrap(func)
        params = inspect.signature(original).parameters

        @wraps(func)
        def wrapped(ctx: click.Context, /, *args: typing.Any, **kwargs: typing.Any) -> T:
            scaffold = ctx.ensure_object(NameTest)
            env = ctx.ensure_object(EnvTest)
            if "name" in params:
                kwargs["name"] = scaffold
            if "env" in params:
                kwargs["env"] = env
            return func(*args, **kwargs)

        # click.pass_context makes sure that 'ctx' is the first argument
        return click.pass_context(wrapped)


def test_inject_custom_multiple():
    @command(
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        },
    )
    def another(name: NameTest, env: EnvTest) -> T:
        click.echo(f"Injected name: {name.name} and env: {env.name}")

    app = Sayer(name="test", help="Test group", group_class=NewGroup)
    app.add_command(another)

    runner = SayerTestClient(app)

    result = runner.invoke(["another"])

    assert result.exit_code == 0
    assert result.output.strip() == "Injected name: Sayer and env: test"
