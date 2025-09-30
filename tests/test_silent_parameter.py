from typing import Annotated

import pytest

from sayer.app import Sayer
from sayer.decorators import silent_param
from sayer.params import JsonParam, Option
from sayer.testing import SayerTestClient

# Minimal app
app = Sayer(name="test-app")


@app.command()
def hello(user: Annotated[str, Option()], secret: str = silent_param(Option("--secret"))):
    return f"Hello {user}"


@app.command()
def hello_json(
    user: Annotated[str, Option()],
    config: dict = silent_param(JsonParam("--config")),
):
    # secret-like config should not appear in return
    return {"user": user}


@app.command()
def multi(
    user: Annotated[str, Option()],
    secret: str = silent_param(Option("--secret")),
    token: str = silent_param(Option("--token")),
):
    return f"Hello {user}"


client = SayerTestClient(app)


@pytest.mark.parametrize(
    "args, expected",
    [
        (["hello", "--user", "Sayer", "--secret", "topsecret"], "Hello Sayer"),
        (["hello", "--user", "Alice"], "Hello Alice"),
    ],
)
def test_silent_param_hidden_from_callback(args, expected):
    result = client.invoke(args, with_return_value=True)

    assert result.exit_code == 0
    assert expected in result.return_value
    assert "topsecret" not in str(result.return_value)


def test_silent_param_not_in_help():
    result = client.invoke(["hello", "--help"])
    assert result.exit_code == 0
    assert "--user" in result.output
    assert "--secret" not in result.output  # hidden param


def test_silent_param_from_env(monkeypatch):
    monkeypatch.setenv("HELLO_SECRET", "from_env")
    result = client.invoke(["hello", "--user", "Dana"], with_return_value=True)

    assert result.exit_code == 0
    assert "Dana" in result.return_value
    assert "from_env" not in str(result.return_value)


def test_silent_json_param_hidden():
    result = client.invoke(
        ["hello-json", "--user", "Eve", "--config", '{"debug": true}'],
        with_return_value=True,
    )
    assert result.exit_code == 0
    assert result.return_value == {"user": "Eve"}  # config ignored


def test_multiple_silent_params_hidden():
    result = client.invoke(
        ["multi", "--user", "Frank", "--secret", "a", "--token", "b"],
        with_return_value=True,
    )
    assert result.exit_code == 0

    assert "--secret" not in str(result.return_value)
    assert "topsecret" not in str(result.return_value)
    assert "token123" not in str(result.return_value)
    assert "Hello Frank" == result.return_value
