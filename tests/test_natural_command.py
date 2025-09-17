from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer import Argument, Option
from sayer.core.engine import command, get_commands

pytestmark = pytest.mark.anyio


def test_command_registration():
    @command
    def hello(name: str):
        pass

    assert "hello" in get_commands()
    assert isinstance(get_commands()["hello"], click.Command)


def test_command_argument_injection():
    @command
    def greet(name: str):
        click.echo(f"Hello {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["World"])

    assert result.exit_code == 0
    assert "Hello World" in result.output


def test_command_registration_async():
    @command
    async def hello(name: str):
        pass

    assert "hello" in get_commands()
    assert isinstance(get_commands()["hello"], click.Command)


def test_command_argument_injection_async():
    @command
    async def greet(name: str):
        click.echo(f"Hello {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["World"])

    assert result.exit_code == 0
    assert "Hello World" in result.output


async def test_command_registration_natural():
    @command
    def hello(name: str):
        return name

    assert hello("World") == "World"


async def test_command_registration_natural_async():
    @command
    async def hello(name: str):
        return name

    assert await hello("World") == "World"


async def test_command_registration_natural_async_empty():
    @command
    async def hello():
        return "empty"

    assert await hello() == "empty"


async def test_command_registration_natural_empty():
    @command
    def hello():
        return "empty"

    assert hello() == "empty"


async def test_command_registration_natural_async_with_annotation_argument():
    @command
    async def hello(name: Annotated[str, Argument(..., help="Your name")]):
        return name

    assert await hello("World") == "World"


async def test_command_registration_natural_sync_with_annotation_argument():
    @command
    def hello(name: Annotated[str, Argument(..., help="Your name")]):
        return name

    assert hello("World") == "World"


async def test_command_registration_natural_async_with_annotation_option():
    @command
    async def hello(name: Annotated[str, Option(..., help="Your name")]):
        return name

    assert await hello("World") == "World"


async def test_command_registration_natural_sync_with_annotation_option():
    @command
    def hello(name: Annotated[str, Option(..., help="Your name")]):
        return name

    assert hello("World") == "World"
