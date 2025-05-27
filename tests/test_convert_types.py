from typing import Annotated

import click
import pytest
from click.testing import CliRunner

from sayer import command
from sayer.params import Argument


@pytest.fixture
def runner():
    return CliRunner()

# 1) Test list[int]
@command(name="list_ints")
def cmd_list_ints(
    items: Annotated[
        list[int],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    """Echo the parsed list[int]"""
    click.echo(repr(items))

# 2) Test homogeneous tuple[int, ...]
@command(name="tuple_ints")
def cmd_tuple_ints(
    items: Annotated[
        tuple[int, ...],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    click.echo(repr(items))

# 3) Test heterogeneous tuple[str,int,float]
@command(name="tuple_mixed")
def cmd_tuple_mixed(
    items: Annotated[
        tuple[str, int, float],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    click.echo(repr(items))

# 4) Test set[str]
@command(name="set_strs")
def cmd_set_strs(
    items: Annotated[
        set[str],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    # sort for deterministic output
    click.echo(repr(set(items)))

# 5) Test dict[str,int]
@command(name="dict_str_int")
def cmd_dict_str_int(
    kv: Annotated[
        dict[str, int],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    click.echo(repr(kv))

# 6) Test frozenset[str]
@command(name="fset_strs")
def cmd_frozenset_strs(
    items: Annotated[
        frozenset[str],
        Argument(nargs=-1, type=click.UNPROCESSED)
    ]
) -> None:
    click.echo(repr(items))


def test_list_ints(runner):
    result = runner.invoke(cmd_list_ints, ["1", "2", "3", "4"])
    assert result.exit_code == 0
    assert result.output.strip() == "[1, 2, 3, 4]"


def test_tuple_ints(runner):
    result = runner.invoke(cmd_tuple_ints, ["10", "20", "30"])
    assert result.exit_code == 0
    assert result.output.strip() == "(10, 20, 30)"


def test_tuple_mixed(runner):
    result = runner.invoke(cmd_tuple_mixed, ["hello", "42", "3.14"])
    assert result.exit_code == 0
    assert result.output.strip() == "('hello', 42, 3.14)"


def test_set_strs(runner):
    result = runner.invoke(cmd_set_strs, ["a", "b", "a", "c"])
    assert result.exit_code == 0
    output = eval(result.output.strip())
    assert output == {"a", "b", "c"}


def test_dict_str_int(runner):
    result = runner.invoke(cmd_dict_str_int, ["key1=1", "key2=2", "foo=42"])
    assert result.exit_code == 0
    assert result.output.strip() == "{'key1': 1, 'key2': 2, 'foo': 42}"


def test_frozenset_strs(runner):
    result = runner.invoke(cmd_frozenset_strs, ["a", "b", "a", "c"])
    assert result.exit_code == 0
    output = eval(result.output.strip())
    assert output == frozenset({"a", "b", "c"})
