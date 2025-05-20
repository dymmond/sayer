import uuid
from datetime import date, datetime
from enum import Enum
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from sayer.core.engine import command, get_commands


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

@command
def paint(color: Color):
    click.echo(color)

@command
def paint_default(color: Color = Color.GREEN):  # default value
    click.echo(color)

@command
def show_path(p: Path):
    click.echo(str(p.resolve()))

@command
def sum_nums(nums: list[int]):
    click.echo(str(sum(nums)))

@command
def idcmd(identifier: uuid.UUID):
    click.echo(str(identifier))

@command
def when(d: date):
    click.echo(d.isoformat())

@command
def timestamp(dt: datetime):
    click.echo(dt.isoformat())

@command
def timestamp_default(dt: datetime = datetime(2025, 5, 20, 15, 30)):  # default datetime
    click.echo(dt.isoformat())

@pytest.fixture
def runner():
    return CliRunner()

def test_enum_choice_success(runner):
    cmd = get_commands()["paint"]
    result = runner.invoke(cmd, ["--color", "red"])

    assert result.exit_code == 0
    assert result.output.strip() == "red"

def test_enum_choice_invalid(runner):
    cmd = get_commands()["paint"]
    result = runner.invoke(cmd, ["--color", "yellow"])

    assert result.exit_code != 0
    assert "Invalid value for '--color'" in result.output

def test_enum_default(runner):
    cmd = get_commands()["paint-default"]
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert result.output.strip() == "green"

def test_path_success(tmp_path, runner):
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    cmd = get_commands()["show-path"]
    result = runner.invoke(cmd, [str(file_path)])

    assert result.exit_code == 0
    assert result.output.strip().endswith("file.txt")

def test_sequence_multiple_values(runner):
    cmd = get_commands()["sum-nums"]
    result = runner.invoke(cmd, ["--nums", "1", "--nums", "2", "--nums", "3"])

    assert result.exit_code == 0
    assert result.output.strip() == "6"

def test_uuid_success(runner):
    cmd = get_commands()["idcmd"]
    uid = uuid.uuid4()
    result = runner.invoke(cmd, [str(uid)])

    assert result.exit_code == 0
    assert result.output.strip() == str(uid)

def test_date_parsing_success(runner):
    cmd = get_commands()["when"]
    result = runner.invoke(cmd, ["2025-05-20"])

    assert result.exit_code == 0
    assert result.output.strip() == "2025-05-20"

def test_date_parsing_invalid(runner):
    cmd = get_commands()["when"]
    result = runner.invoke(cmd, ["20/05/2025"])

    assert result.exit_code != 0

def test_datetime_parsing_success(runner):
    cmd = get_commands()["timestamp"]
    iso = "2025-05-20T15:30:00"
    result = runner.invoke(cmd, [iso])

    assert result.exit_code == 0
    assert result.output.strip().startswith(iso)

def test_datetime_default(runner):
    cmd = get_commands()["timestamp-default"]
    result = runner.invoke(cmd, [])

    assert result.exit_code == 0
    assert result.output.strip().startswith("2025-05-20T15:30:00")
