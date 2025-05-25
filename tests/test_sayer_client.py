from sayer.core.client import app
from sayer.testing import SayerTestClient


def test_sayer_client():
    client = SayerTestClient(app)
    result = client.invoke([])

    assert result.exit_code == 0, result.output

    out = result.output

    assert "Sayer CLI Application" in out

    # exact formatting: command name, two spaces, description
    assert "new   Create a new Sayer CLI project in *NAME* directory." in out
    assert "docs  Generate Markdown documentation for all Sayer commands and groups." in out
