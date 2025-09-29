from typing import Annotated

from sayer import Option, Sayer, echo
from sayer.testing import SayerTestClient


def test_implicit_variadic_list_is_positional():
    app = Sayer(name="app")

    @app.command()
    def run(directive: str, args: list[str]):
        echo(f"directive args: {args}")

    client = SayerTestClient(app)
    result = client.invoke(["run", "mail", "a", "b", "c"])

    assert result.exit_code == 0, result.output
    assert "directive args: ['a', 'b', 'c']" in result.output


def test_optional_str_option_none_not_stringified():
    app = Sayer(name="app")

    @app.command()
    def rev(message: Annotated[str | None, Option(None, "-m")]):
        echo(f"message: {message}, is_none: {message is None}, type: {type(message).__name__}")
        return {
            "message": message,
            "is_none": message is None,
            "type": type(message).__name__,
        }

    # Not passing -m/--message should yield Python None
    client = SayerTestClient(app)

    res = client.invoke(["rev"], with_return_value=True)
    assert res.exit_code == 0, res.output
    assert "message: None, is_none: True, type: NoneType" in res.output

    assert res.return_value["message"] is None
    assert res.return_value["is_none"] is True

    # Passing a real value should still work
    res2 = client.invoke(["rev", "-m", "hello"])
    assert res2.exit_code == 0, res2.output
    assert "message: hello, is_none: False, type: str" in res2.output


def test_optional_str_option_none_not_stringified_display():
    app = Sayer(name="app")

    @app.command()
    def rev(message: Annotated[str | None, Option(None, "-m")]):
        assert message is None
        echo(f"Message: {message}")

    @app.command()
    def rev2(message: Annotated[str | None, Option(None, "-m")]):
        echo(f"Message: {message}")

    # Not passing -m/--message should yield Python None
    client = SayerTestClient(app)

    res = client.invoke(["rev"])
    assert res.exit_code == 0, res.output
    assert "Message: None" in res.output

    # Passing a real value should still work
    res2 = client.invoke(["rev2", "-m", "hello"])
    assert res2.exit_code == 0, res2.output
    assert "Message: hello" in res2.output
