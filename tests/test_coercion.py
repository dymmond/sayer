import click

from sayer.utils.coercion import coerce_argument_to_option
from sayer.utils.coersion import coerce_argument_to_option as coerce_argument_to_option_legacy


def test_coercion_shim_exports_same_function() -> None:
    assert coerce_argument_to_option_legacy is coerce_argument_to_option


def test_coerce_argument_to_option_returns_original_without_force() -> None:
    argument = click.Argument(["name"], type=click.STRING, required=False)
    coerced = coerce_argument_to_option(argument, force=False)

    assert coerced is argument


def test_coerce_argument_to_option_converts_when_forced() -> None:
    argument = click.Argument(["name"], type=click.STRING, default="alice", required=False)
    coerced = coerce_argument_to_option(argument, force=True)

    assert isinstance(coerced, click.Option)
    assert coerced.opts == ["--name"]
    assert coerced.default == "alice"
    assert coerced.show_default is True


def test_variadic_argument_stays_argument_when_not_forced() -> None:
    argument = click.Argument(["items"], type=click.STRING, nargs=-1, required=False)
    coerced = coerce_argument_to_option(argument, force=False)

    assert coerced is argument
