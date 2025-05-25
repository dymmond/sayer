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
