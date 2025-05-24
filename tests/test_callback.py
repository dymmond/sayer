from typing import Annotated

from click import Context

from sayer.app import Sayer
from sayer.params import Argument, JsonParam, Option
from sayer.testing import SayerTestClient


def test_default_no_invoke_skips_callback_on_subcommand():
    calls = []
    app = Sayer(help="TestApp", add_version_option=False)

    @app.callback()
    def root(ctx: Context):
        calls.append("root")

    @app.command()
    def cmd():
        calls.append("cmd")

    client = SayerTestClient(app)
    result = client.invoke(["cmd"])
    assert result.exit_code == 0
    # With invoke_without_command=False, callbacks should NOT run for subcommands
    assert calls == ["cmd"]


def test_invoke_without_command_runs_callback_only():
    calls = []
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(ctx: Context):
        calls.append("root")

    @app.command()
    def cmd():
        calls.append("cmd")

    client = SayerTestClient(app)
    result = client.invoke([])
    assert result.exit_code == 0
    assert calls == ["root"]


def test_invoke_runs_callback_then_subcommand():
    calls = []
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(ctx: Context):
        calls.append("root")

    @app.command()
    def cmd():
        calls.append("cmd")

    client = SayerTestClient(app)
    result = client.invoke(["cmd"])
    assert result.exit_code == 0
    assert calls == ["root", "cmd"]


def test_callback_receives_required_option():
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(path: Annotated[str, Option("--path", required=True)]):
        received["path"] = path

    client = SayerTestClient(app)
    result = client.invoke(["--path", "/tmp"])
    assert result.exit_code == 0
    assert received["path"] == "/tmp"


def test_missing_required_option_errors():
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(name: Annotated[str, Option("--name", required=True)]):
        pass

    client = SayerTestClient(app)
    result = client.invoke([])
    assert result.exit_code != 0
    assert "Missing option '--name'" in result.output


def test_callback_optional_option_defaults_to_none():
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(count: Annotated[int, Option("--count", required=False)]):
        received["count"] = count

    client = SayerTestClient(app)
    result = client.invoke([])
    assert result.exit_code == 0
    assert received["count"] is None


def test_callback_option_type_conversion():
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(num: Annotated[int, Option("--num", required=True)]):
        received["num"] = num
        assert isinstance(num, int)

    client = SayerTestClient(app)
    result = client.invoke(["--num", "42"])
    assert result.exit_code == 0
    assert received["num"] == 42


def test_callback_uses_envvar_default(monkeypatch):
    monkeypatch.setenv("MYVAL", "hello")
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(greeting: Annotated[str, Option("--greet", envvar="MYVAL", required=False)]):
        received["greeting"] = greeting

    client = SayerTestClient(app)
    result = client.invoke([])
    assert result.exit_code == 0
    assert received["greeting"] == "hello"


def test_callback_positional_argument():
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(filename: Annotated[str, Argument()]):
        received["filename"] = filename

    client = SayerTestClient(app)
    result = client.invoke(["myfile.txt"])
    assert result.exit_code == 0
    assert received["filename"] == "myfile.txt"


def test_callback_jsonparam_parsing():
    received = {}
    app = Sayer(help="TestApp", add_version_option=False, invoke_without_command=True)

    @app.callback()
    def root(config: Annotated[dict, JsonParam()]):
        received["config"] = config

    client = SayerTestClient(app)
    json_str = '{"a": 1, "b": 2}'
    result = client.invoke(["--config", json_str])
    assert result.exit_code == 0
    assert received["config"] == {"a": 1, "b": 2}
