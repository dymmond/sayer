from typing import Annotated

import click
from click.testing import CliRunner

from sayer.core import command, get_commands, group
from sayer.params import Param


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


def test_command_option_defaults():
    @command
    def run(verbose: bool = Param(default=True)):
        click.echo(str(verbose))

    cmd = get_commands()["run"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "True" in result.output


def test_group_registration_and_binding():
    grp = group("test")

    @grp.command()
    def ping():
        click.echo("pong")

    assert "ping" in grp.commands
    assert isinstance(grp.commands["ping"], click.Command)


def test_annotated_param_with_description():
    @command
    def echo(msg: Annotated[str, Param(description="The message to print")]):
        click.echo(msg)

    cmd = get_commands()["echo"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["Hi"])

    assert result.exit_code == 0
    assert "Hi" in result.output


def test_param_default_via_Param():
    @command
    def add(x: int, y: int = Param(default=2)):
        click.echo(str(x + y))

    cmd = get_commands()["add"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["3"])

    assert result.exit_code == 0
    assert "5" in result.output


def test_optional_string_becomes_option():
    @command
    def greet(name: str = None):
        click.echo(f"Name: {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()

    # calling without args should show default None
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "Name: None" in result.output

    # calling with option
    result2 = runner.invoke(cmd, ["--name", "Alice"])

    assert result2.exit_code == 0
    assert "Name: Alice" in result2.output


def test_boolean_flag_inference():
    @command
    def toggle(force: bool = False):
        click.echo(str(force))

    cmd = get_commands()["toggle"]
    runner = CliRunner()

    # default
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "False" in result.output

    # flag
    result2 = runner.invoke(cmd, ["--force"])

    assert result2.exit_code == 0
    assert "True" in result2.output


def test_multiple_params_inference():
    @command
    def concat(a: str, b: str = "B"):
        click.echo(a + b)

    cmd = get_commands()["concat"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["A"])  # b defaults to "B"

    assert result.exit_code == 0
    assert result.output.strip() == "AB"

    result2 = runner.invoke(cmd, ["A", "C"])

    assert result2.exit_code == 0
    assert result2.output.strip() == "AC"


def test_multiple_params_inference_with_param():
    @command
    def concat(a: str, b: str = Param(default="B")):
        click.echo(a + b)

    cmd = get_commands()["concat"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["A"])  # b defaults to "B"

    assert result.exit_code == 0
    assert result.output.strip() == "AB"

    result2 = runner.invoke(cmd, ["A", "C"])

    assert result2.exit_code == 0
    assert result2.output.strip() == "AC"


def test_help_includes_description():
    @command
    def show(msg: Annotated[str, Param(description="test message")]):
        click.echo(msg)

    cmd = get_commands()["show"]
    help_text = cmd.get_help(click.Context(cmd))
    assert "test message" in help_text
