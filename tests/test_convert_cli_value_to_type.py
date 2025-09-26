import json
import typing as t
from datetime import date, datetime
from enum import Enum

import click
import pytest
from click.testing import CliRunner

from sayer import Option, command

# Adjust the import path if different in your repo
from sayer.core.engine import _convert_cli_value_to_type


def test_dict_str_int_from_pairs():
    pairs = ["key1=1", "key2=2", "foo=42"]
    result = _convert_cli_value_to_type(pairs, dict[str, int])
    assert result == {"key1": 1, "key2": 2, "foo": 42}


def test_list_int_from_list():
    value = ["1", "2", "3"]
    result = _convert_cli_value_to_type(value, list[int])
    assert result == [1, 2, 3]


def test_tuple_varlen_int():
    value = ["1", "2", "3"]
    result = _convert_cli_value_to_type(value, tuple[int, ...])
    assert result == (1, 2, 3)


def test_tuple_fixed_heterogeneous():
    value = ["42", "yes"]
    result = _convert_cli_value_to_type(value, tuple[int, bool])
    assert result == (42, True)


def test_set_str_from_list():
    value = ["a", "b", "a"]
    result = _convert_cli_value_to_type(value, set[str])
    assert result == {"a", "b"}


def test_frozenset_int_from_list():
    value = ["1", "2", "2"]
    result = _convert_cli_value_to_type(value, frozenset[int])
    assert result == frozenset({1, 2})


def test_bool_parsing_truthy_and_falsey():
    assert _convert_cli_value_to_type("true", bool) is True
    assert _convert_cli_value_to_type("1", bool) is True
    assert _convert_cli_value_to_type("yes", bool) is True
    assert _convert_cli_value_to_type("on", bool) is True

    assert _convert_cli_value_to_type("false", bool) is False
    assert _convert_cli_value_to_type("0", bool) is False
    assert _convert_cli_value_to_type("no", bool) is False
    assert _convert_cli_value_to_type("off", bool) is False

    # Already bool passes through
    assert _convert_cli_value_to_type(True, bool) is True


def test_date_downcast_from_datetime():
    dt = datetime(2025, 1, 2, 3, 4, 5)
    assert _convert_cli_value_to_type(dt, date) == date(2025, 1, 2)


class Color(Enum):
    RED = "red"
    BLUE = "blue"


def test_enum_is_left_as_string():
    # Sayer leaves Enum values as strings so Click.Choice can validate.
    assert _convert_cli_value_to_type("RED", Color) == "RED"
    assert _convert_cli_value_to_type("red", Color) == "red"


def test_optional_int_success():
    # Ensure Union/Optional doesn't raise "cannot create 'types.UnionType' instances"
    T = int | None
    assert _convert_cli_value_to_type("42", T) == 42


def test_union_int_str_prefers_first_type():
    # If your conversion tries in declared order, int first succeeds
    T = int | str
    assert _convert_cli_value_to_type("42", T) == 42
    # If int fails, fallback to str (stays as "foo")
    assert _convert_cli_value_to_type("foo", T) == "foo"


def test_annotated_dict_preserves_generics_for_conversion():
    Annotated = t.Annotated  # local alias to avoid lint issues
    ann = Annotated[dict[str, int], "meta"]
    result = _convert_cli_value_to_type(["a=1", "b=2"], ann)
    assert result == {"a": 1, "b": 2}


def test_dict_raises_on_malformed_item():
    # Your current implementation raises on items without "="
    with pytest.raises(ValueError):
        _convert_cli_value_to_type(["a=1", "oops", "b=2"], dict[str, int])


@command
def emails(
    to: t.Annotated[
        list[str],
        Option(help="Recipient email address. Can be used multiple times.", required=True),
    ],
):
    click.echo(json.dumps(list(to)))


def test_list_str_option_multiple_values():
    r = CliRunner().invoke(
        emails,
        ["--to", "user@example.com", "--to", "caa@gmail.com"],
    )
    assert r.exit_code == 0
    assert r.output.strip() == '["user@example.com", "caa@gmail.com"]'
