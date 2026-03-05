import click

from sayer.core.commands.sayer import SayerCommand, wrap_click_command


def test_wrap_click_command_returns_sayer_command_instance() -> None:
    @click.command("hello", help="Hello command")
    def hello() -> None:
        return None

    wrapped = wrap_click_command(hello)

    assert isinstance(wrapped, SayerCommand)
    assert wrapped.name == "hello"
    assert wrapped.help == "Hello command"


def test_wrap_click_command_is_idempotent_for_existing_sayer_command() -> None:
    @click.command("echo")
    def echo() -> None:
        return None

    wrapped = wrap_click_command(echo)
    wrapped_again = wrap_click_command(wrapped)

    assert wrapped_again is wrapped
