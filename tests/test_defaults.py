from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer import Sayer
from sayer.params import Option


# Helper to fetch a Click parameter by name from a wrapped command
def _get_param(cmd: click.Command, name: str) -> click.Parameter:
    for p in cmd.params:
        if p.name == name.replace("-", "_"):
            return p
    raise AssertionError(f"param {name!r} not found")


@pytest.mark.parametrize("default_arg", [pytest.param([], id="list"), pytest.param((), id="tuple")])
@pytest.mark.parametrize("extra_name", ["--store", "--somethingelse"])
def test_sequence_option_default_from_metadata(default_arg, extra_name):
    """
    store: Annotated[list[str], Option([], "--store", help="...")]
    Expect: default tuple(), multiple=True, and accepts repeated values.
    """
    app = Sayer(name="app", help="defaults")

    @app.command("meta")
    def meta(
        store: Annotated[list[str], Option(default_arg, extra_name, help="Store spec")],
    ):
        click.echo(f"{tuple(store)!r}")

    runner = CliRunner()
    # no --store provided -> default should be tuple()
    res = runner.invoke(app.cli, ["meta"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "()"

    # multiple values accumulate
    res = runner.invoke(app.cli, ["meta", "--store", "a", "--store", "b"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "('a', 'b')"

    # inspect Click param
    cmd = app.cli.get_command(None, "meta")
    prm = _get_param(cmd, "store")
    assert prm.multiple is True
    assert prm.default == ()  # tuple default for multiple=True
    assert isinstance(prm, click.Option)


def test_sequence_option_default_from_python():
    """
    store: Annotated[list[str], Option("--store", help="...")] = []
    Expect: Python default [] honored -> coerced to tuple() for click.
    """
    app = Sayer(name="app2", help="defaults")

    @app.command("pydef")
    def pydef(
        store: Annotated[list[str], Option("--store", help="Store spec")] = [],  # noqa
    ):
        click.echo(f"{tuple(store)!r}")

    runner = CliRunner()
    res = runner.invoke(app.cli, ["pydef"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "()"

    res = runner.invoke(app.cli, ["pydef", "--store", "x", "--store", "y"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "('x', 'y')"

    cmd = app.cli.get_command(None, "pydef")
    prm = _get_param(cmd, "store")
    assert prm.multiple is True
    assert prm.default == ()


def test_sequence_option_no_default_anywhere():
    """
    store: Annotated[list[str], Option("--store", help="...")]
    Expect: default becomes tuple(), not None; still multiple=True.
    """
    app = Sayer(name="app3", help="defaults")

    @app.command("nodef")
    def nodef(
        store: Annotated[list[str], Option("--store", help="Store spec")],
    ):
        click.echo(f"{tuple(store)!r}")

    runner = CliRunner()
    res = runner.invoke(app.cli, ["nodef"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "()"

    cmd = app.cli.get_command(None, "nodef")
    prm = _get_param(cmd, "store")
    assert prm.multiple is True
    assert prm.default == ()


def test_scalar_option_default_precedence_metadata_over_python():
    """
    retries: Annotated[int, Option(3, "--retries")] = 5
    Expect: metadata default (3) wins over python default (=5).
    """
    app = Sayer(name="app4", help="defaults")

    @app.command("scalar")
    def scalar(
        retries: Annotated[int, Option(3, "--retries", help="Retries")] = 5,
    ):
        click.echo(str(retries))

    cmd = app.cli.get_command(None, "scalar")
    prm = _get_param(cmd, "retries")
    assert isinstance(prm, click.Option)
    assert prm.default == 3  # metadata beats python default

    runner = CliRunner()
    res = runner.invoke(app.cli, ["scalar"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "3"

    res = runner.invoke(app.cli, ["scalar", "--retries", "9"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "9"


def test_boolean_flag_default_handling_and_toggle():
    """
    debug: Annotated[bool, Option(help="...")] = False
    Expect: flag --debug toggles to True; default shows as False.
    """
    app = Sayer(name="app5", help="defaults")

    @app.command("bools")
    def bools(
        debug: Annotated[bool, Option(help="Enable debug")] = False,
    ):
        click.echo(str(debug))

    cmd = app.cli.get_command(None, "bools")
    prm = _get_param(cmd, "debug")
    assert isinstance(prm, click.Option)
    assert prm.is_flag is True
    assert prm.default is False

    runner = CliRunner()
    res = runner.invoke(app.cli, ["bools"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "False"

    res = runner.invoke(app.cli, ["bools", "--debug"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "True"


def test_option_without_param_decls_derives_flag_name():
    """
    retries: Annotated[int, Option(help='...')] = 1
    Expect: flag derived as --retries and visible in help; no None in param decls.
    """
    app = Sayer(name="app6", help="defaults")

    @app.command("derived")
    def derived(
        retries: Annotated[int, Option(help="Number of retries")] = 1,
    ):
        click.echo(str(retries))

    runner = CliRunner()
    # Ensure help shows derived flag
    res = runner.invoke(app.cli, ["derived", "--help"])
    assert res.exit_code == 0, res.output
    assert "--retries" in res.output

    # Using the derived flag works
    res = runner.invoke(app.cli, ["derived", "--retries", "7"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "7"


def test_sequence_option_default_empty():
    app = Sayer(name="app2", help="defaults")

    @app.command("pydef")
    def pydef(store: Annotated[list[str], Option((), "--store", help="Store spec")]):
        click.echo(f"{tuple(store)!r}")

    runner = CliRunner()
    res = runner.invoke(app.cli, ["pydef"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "()"

    res = runner.invoke(app.cli, ["pydef", "--store", "x", "--store", "y"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "('x', 'y')"

    cmd = app.cli.get_command(None, "pydef")
    prm = _get_param(cmd, "store")
    assert prm.multiple is True
    assert prm.default == ()
