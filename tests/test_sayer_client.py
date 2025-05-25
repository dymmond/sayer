from sayer.core.client import app
from sayer.testing import SayerTestClient


def test_sayer_client():
    client = SayerTestClient(app)
    result = client.invoke([])

    assert result.exit_code == 0, result.output

    out = result.output

    assert "Sayer CLI Application" in out

    # exact formatting: command name, two spaces, description
    assert "new" in out
    assert "Create a new Sayer CLI project in *NAME* directory." in out

    assert "docs" in out


def test_sayer_client_help():
    client = SayerTestClient(app)
    result = client.invoke(["--help"])

    assert result.exit_code == 0, result.output

    out = result.output

    assert "Sayer CLI Application" in out

    # exact formatting: command name, two spaces, description
    assert "new" in out
    assert "docs" in out


def test_sayer_client_command_new_help():
    client = SayerTestClient(app)
    result = client.invoke(["new", "--help"])

    assert result.exit_code == 0, result.output

    out = result.output

    # test name
    assert "<name>" in out

    # test description
    assert "The name given for the new cli project" in out


def test_sayer_client_command_docs_help():
    client = SayerTestClient(app)
    result = client.invoke(["docs", "--help"])

    assert result.exit_code == 0, result.output

    out = result.output

    # test name
    assert "generate" in out

    # test description
    assert "Generate Markdown documentation for all Sayer commands and groups." in out
