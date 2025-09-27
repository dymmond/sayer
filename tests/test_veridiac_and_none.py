from typing import Annotated

from sayer import Option, Sayer
from sayer.testing import SayerTestClient


def test_implicit_variadic_list_is_positional():
    app = Sayer(name="app")

    @app.command()
    def run(directive: str, args: list[str]):
        return {"directive": directive, "args": args}

    client = SayerTestClient(app)
    result = client.invoke(["run", "mail", "a", "b", "c"])

    assert result.exit_code == 0, result.output
    assert result.return_value == {
        "directive": "mail",
        "args": ["a", "b", "c"],
    }


def test_optional_str_option_none_not_stringified():
    app = Sayer(name="app")

    @app.command()
    def rev(message: Annotated[str | None, Option(None, "-m")]):
        return {
            "message": message,
            "is_none": message is None,
            "type": type(message).__name__,
        }

    # Not passing -m/--message should yield Python None
    client = SayerTestClient(app)

    res = client.invoke(["rev"])
    assert res.exit_code == 0, res.output
    assert res.return_value["message"] is None
    assert res.return_value["is_none"] is True
    assert res.return_value["type"] == "NoneType"

    # Passing a real value should still work
    res2 = client.invoke(["rev", "-m", "hello"])
    assert res2.exit_code == 0, res2.output
    assert res2.return_value["message"] == "hello"
