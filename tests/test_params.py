from typing import Annotated

import click
from click.testing import CliRunner

from sayer.core.engine import command, get_commands
from sayer.params import Argument, Env, Option


def test_option_with_prompt():
    @command
    def ask(name: Annotated[str, Option(prompt="Your name?")]):
        click.echo(name)

    cmd = get_commands()["ask"]
    runner = CliRunner()
    result = runner.invoke(cmd, input="Alice\n")

    assert result.exit_code == 0
    assert "Alice" in result.output


def test_option_with_default():
    @command
    def greet(name: Annotated[str, Option(default="World")]):
        click.echo(f"Hello {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "Hello World" in result.output


def test_argument_required():
    @command
    def shout(word: Annotated[str, Argument()]):
        click.echo(word.upper())

    cmd = get_commands()["shout"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["yo"])

    assert result.exit_code == 0
    assert result.output.strip() == "YO"


def test_argument_with_default():
    @command
    def greet(name: Annotated[str, Argument(default="Sayer")]):
        click.echo(f"Hi {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "Hi Sayer" in result.output


def test_env_parameter(monkeypatch):
    monkeypatch.setenv("GREETING", "Bonjour")

    @command
    def greet(msg: Annotated[str, Env("GREETING", default="Hello")]):
        click.echo(msg)

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "Bonjour" in result.output


def test_plain_required_argument():
    @command
    def echo(msg: str):
        click.echo(msg.upper())

    cmd = get_commands()["echo"]
    runner = CliRunner()
    result = runner.invoke(cmd, ["hello"])

    assert result.exit_code == 0
    assert result.output.strip() == "HELLO"


def test_plain_default_argument():
    @command
    def greet(name: str = "friend"):
        click.echo(f"Hi {name}")

    cmd = get_commands()["greet"]
    runner = CliRunner()
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert "Hi friend" in result.output


def test_plain_optional_flag():
    @command
    def debug(verbose: bool = False):
        click.echo(f"Verbose: {verbose}")

    cmd = get_commands()["debug"]
    runner = CliRunner()
    result1 = runner.invoke(cmd, [])
    result2 = runner.invoke(cmd, ["--verbose"])

    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert "False" in result1.output
    assert "True" in result2.output


def test_plain_optional_string():
    @command
    def hello(name: str = None):
        click.echo(f"Name: {name}")

    cmd = get_commands()["hello"]
    runner = CliRunner()
    result1 = runner.invoke(cmd, [])
    result2 = runner.invoke(cmd, ["--name", "Sayer"])

    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert "None" in result1.output
    assert "Sayer" in result2.output
