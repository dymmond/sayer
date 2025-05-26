import click
import pytest

from sayer.app import Sayer
from sayer.testing import SayerTestClient


@pytest.fixture
def main_app():
    # Main application, with a version flag
    return Sayer(
        name="main",
        help="Main application",
        add_version_option=True,
        version="9.9.9",
    )


@pytest.fixture
def sub_app():
    # Sub-application to be mounted
    return Sayer(name="sub", help="Sub-application commands")


def test_mount_and_invoke_subapp_command(main_app: Sayer, sub_app: Sayer):
    # Define a root command on the main app
    @main_app.command()
    def hello():
        """Say hello from main."""
        click.echo("hello from main")

    # Define a command on the sub-app
    @sub_app.command()
    def ping():
        """Ping from sub."""
        click.echo("pong")

    # Mount the sub-app under prefix 'sub'
    main_app.add_sayer("sub", sub_app)

    # Use SayerTestClient against the main_app
    client = SayerTestClient(main_app)

    # --help on root should list 'sub' and 'hello'
    res = client.invoke(["--help"])
    assert res.exit_code == 0

    assert "hello" in res.output
    assert "sub" in res.output

    # Invoking the root command
    res = client.invoke(["hello"])

    assert res.exit_code == 0
    assert "hello from main" in res.output

    # --help on the sub-group
    res = client.invoke(["sub", "--help"])

    assert res.exit_code == 0
    # help text of the sub-app itself
    assert "Sub-application commands" in res.output
    # should list its 'ping' subcommand
    assert "ping" in res.output

    # Invoking the ping command on sub-app
    res = client.invoke(["sub", "ping"])
    assert res.exit_code == 0
    assert "pong" in res.output


def test_nested_subapp_under_subapp(main_app: Sayer, sub_app: Sayer):
    # Create a second-level sub-app
    nested = Sayer(name="nested", help="Nested commands")

    @nested.command()
    def foo():
        click.echo("foo!")

    # mount nested under 'sub'
    sub_app.add_sayer("nested", nested)
    # mount sub under main
    main_app.add_sayer("sub", sub_app)

    client = SayerTestClient(main_app)

    # Ensure three-level invocation works: main sub nested foo
    res = client.invoke(["sub", "nested", "--help"])

    assert res.exit_code == 0
    assert "foo" in res.output

    res = client.invoke(["sub", "nested", "foo"])

    assert res.exit_code == 0
    assert "foo!" in res.output


def test_version_flag_across_subapps(main_app: Sayer, sub_app: Sayer):
    # The --version flag should still work at root
    client = SayerTestClient(main_app)
    res = client.invoke(["--version"])

    assert res.exit_code == 0
    assert "9.9.9" in res.output

    # And not leak into sub-app invocation—`sub` must be a separate group
    main_app.add_sayer("sub", sub_app)
    res = client.invoke(["sub", "--help"])

    assert res.exit_code == 0
    # sub-app help should not show the root version option
    assert "--version" not in res.output
