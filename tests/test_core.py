from typing import Annotated

import click
from click.testing import CliRunner

from sayer.core import argument, command, get_commands, group, option
from sayer.params import Param


def test_command_registration():
    @command
    def hello(name: str): pass

    assert "hello" in get_commands()
    assert isinstance(get_commands()["hello"], click.Command)

def test_command_argument_injection():
    @argument("name")
    @command
    def greet(name: str):
        click.echo(f"Hello {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["World"])
    assert result.exit_code == 0
    assert "Hello World" in result.output

def test_command_option_defaults():
    @command
    def run(verbose: bool = Param(default=True)): return verbose

    cmd = get_commands()["run"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 0


def test_group_registration_and_binding():
    grp = group("test")

    @grp.command()
    def ping(): return "pong"

    assert "ping" in grp.commands
    assert isinstance(grp.commands["ping"], click.Command)

def test_annotated_param_with_description():
    @argument("msg")
    @command
    def echo(msg: Annotated[str, Param(description="The message to print")]):
        click.echo(msg)

    cmd = get_commands()["echo"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["Hi"])
    assert result.exit_code == 0
    assert "Hi" in result.output

def test_param_override_with_argument_and_option():
    @argument("x")
    @option("y", default=2)
    @command
    def add(x: int, y: int):
        click.echo(str(x + y))

    cmd = get_commands()["add"]

    runner = CliRunner()
    result = runner.invoke(cmd, ["3"])

    print(cmd.get_help(click.Context(cmd)))
    assert result.exit_code == 0
    assert "5" in result.output
