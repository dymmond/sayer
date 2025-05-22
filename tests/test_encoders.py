import inspect
import json
from dataclasses import dataclass
from typing import Annotated, Any

import attrs
import click
import msgspec
import pytest
from attrs import asdict as _attrs_asdict, has as _attrs_has
from click.testing import CliRunner
from pydantic import BaseModel

from sayer.core.engine import command, get_commands
from sayer.encoders import Encoder, EncoderProtocol, MoldingProtocol, register_encoder
from sayer.params import JsonParam


class MsgSpecEncoder(Encoder):
    __type__ = msgspec.Struct

    def serialize(self, obj: Any) -> Any:
        return msgspec.json.decode(msgspec.json.encode(obj))

    def encode(self, structure: Any, obj: Any) -> Any:
        return msgspec.json.decode(obj, type=structure)


register_encoder(MsgSpecEncoder())


class AttrsEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Handles the serialization and deserialization of attrs-generated classes.
    """

    __type__ = object  # actual checks via _attrs_has()

    def is_type(self, v: Any) -> bool:
        return _attrs_has(v)

    def is_type_structure(self, v: Any) -> bool:
        return inspect.isclass(v) and _attrs_has(v)

    def serialize(self, obj: Any) -> dict:
        return _attrs_asdict(obj)

    def encode(self, cls: type, data: dict) -> Any:
        return cls(**data)


register_encoder(AttrsEncoder())


@dataclass
class DC:
    x: int
    y: str


@command
def echo_dc(obj: Annotated[DC, JsonParam()]):
    """Echo a dataclass"""
    click.echo(f"{obj.x},{obj.y}")


@attrs.define
class AT:
    x: int
    y: str


@command
def echo_at(obj: Annotated[AT, JsonParam()]):
    """Echo an attrs class"""
    click.echo(f"{obj.x},{obj.y}")


class PD(BaseModel):
    x: int
    y: str


@command
def echo_pd(obj: Annotated[PD, JsonParam()]):
    """Echo a Pydantic model"""
    click.echo(f"{obj.x},{obj.y}")


class MS(msgspec.Struct):
    x: int
    y: str


@command
def echo_ms(obj: Annotated[MS, JsonParam()]):
    """Echo a msgspec Struct"""
    click.echo(f"{obj.x},{obj.y}")


@pytest.fixture
def runner():
    return CliRunner()


def _run_and_assert(runner, cmd_name, cls, data):
    """Invoke `cmd_name` with JSON for `cls` and assert output."""
    json_str = json.dumps(data)
    cmd = get_commands()[cmd_name]
    result = runner.invoke(cmd, [f"--obj={json_str}"])

    assert result.exit_code == 0, result.output
    expected = f"{data['x']},{data['y']}"
    assert result.output.strip() == expected


def test_dataclass_encoder(runner):
    _run_and_assert(runner, "echo-dc", DC, {"x": 42, "y": "dataclass"})


def test_attrs_encoder(runner):
    _run_and_assert(runner, "echo-at", AT, {"x": 7, "y": "attrs"})


def test_pydantic_encoder(runner):
    _run_and_assert(runner, "echo-pd", PD, {"x": 1, "y": "pydantic"})


def test_msgspec_encoder(runner):
    _run_and_assert(runner, "echo-ms", MS, {"x": 9, "y": "msgspec"})
