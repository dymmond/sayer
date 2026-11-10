from pathlib import Path

from click.testing import CliRunner

from sayer import Sayer
from sayer.cli.new import new


def make_app():
    app = Sayer(name="test-new", help="Test app")
    app.add_command(new)
    return app


def test_new_creates_project():
    runner = CliRunner()
    result = runner.invoke(make_app().cli, ["new", "demo-proj"])
    assert result.exit_code == 0
    assert Path("demo-proj/main.py").is_file()
    assert Path("demo-proj/commands/hello.py").is_file()


def test_new_existing_directory_fails():
    runner = CliRunner()
    Path("demo-existing").mkdir()
    result = runner.invoke(make_app().cli, ["new", "demo-existing"])
    assert result.exit_code == 1
    # the pre-existing directory is left untouched
    assert Path("demo-existing").is_dir()
    assert not Path("demo-existing/main.py").exists()
