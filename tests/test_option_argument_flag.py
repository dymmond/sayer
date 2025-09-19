import click

from sayer import Argument, Option, Sayer
from sayer.testing import SayerTestClient


def test_missing_required_option_errors():
    app = Sayer(add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(name: str = Option(required=True, help="Name is required")):
        click.echo(f"Name is {name}")

    client = SayerTestClient(app=app)
    result = client.invoke([])  # no --name provided

    assert result.exit_code != 0
    assert "Missing option '--name'" in result.output


def test_option_default_used_and_show_default():
    app = Sayer(add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(name: str = Option(default="Alice", help="Name default")):
        click.echo(f"Name is {name}")

    client = SayerTestClient(app=app)
    result = client.invoke([])

    assert result.exit_code == 0

    # Without passing --name, default should apply
    assert "Name is Alice" in result.output

    help_res = client.invoke(["--help"])

    assert "--name" in help_res.output
    assert "Alice" in help_res.output


def test_boolean_flag_default_true():
    app = Sayer(add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(verbose: bool = Option(True, "--verbose/--no-verbose", help="Be verbose")):
        if verbose:
            click.echo("Verbose ON")
        else:
            click.echo("Verbose OFF")

    client = SayerTestClient(app=app)
    res = client.invoke([])

    assert res.exit_code == 0

    assert "Verbose ON" in res.output

    res2 = client.invoke(["--no-verbose"])

    assert res2.exit_code == 0
    assert "Verbose OFF" in res2.output


def test_argument_with_default_value():
    app = Sayer(add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(name: str = Argument(default="Bob", help="Your name")):
        click.echo(f"Hello {name}")

    client = SayerTestClient(app=app)
    res = client.invoke([])

    assert res.exit_code == 0
    assert "Hello Bob" in res.output

    res2 = client.invoke(["Charlie"])
    assert res2.exit_code == 0
    assert "Hello Charlie" in res2.output


# def test_variadic_argument_no_default_ok():
#     app = Sayer(add_version_option=False, invoke_without_command=True)
#
#     @app.callback()
#     def root(
#         items: list[str] = Argument(nargs=-1)
#     ):
#         click.echo(f"Got {len(items)} items")
#
#     client = SayerTestClient(app=app)
#     res = client.invoke([])
#
#     breakpoint()
#     assert res.exit_code == 0
#     assert "Got 0 items" in res.output
#
#     res2 = client.invoke(["one", "two", "three"])
#
#     assert res2.exit_code == 0
#     assert "Got 3 items" in res2.output
#


def test_argument_to_option_group_param_behaviour():
    app = Sayer(help="GrpTest", add_version_option=False)

    @app.command()
    def cmd(extra: str = Argument(help="An extra value")):
        click.echo(f"Extra: {extra}")

    # Access group parameters: simulate the logic in your snippet that converts arguments to options
    # Then test invoking without extra: since required (default None/empty), it should error
    client = SayerTestClient(app=app)
    result = client.invoke(["cmd"])
    assert result.exit_code != 0
    assert "Missing argument 'EXTRA'" in result.output

    # If we pass --extra, should accept
    res2 = client.invoke(["cmd", "hello"])
    assert res2.exit_code == 0
    assert "Extra: hello" in res2.output
