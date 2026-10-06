from pathlib import Path

import pytest

from .testdirectives.definitions import (
    execute_directive,
    find_directive,
    find_directive_system,
    find_directive_zipapp,
)


@pytest.mark.parametrize("name", ["class_based_hidden", "class_based_shown", "hidden", "shown", "packaged_op"])
@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_simple(name, prefixed):
    if prefixed:
        name = f"valid_module.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives", name)
    assert result


@pytest.mark.parametrize("name", ["class_based_hidden", "class_based_shown", "hidden", "shown"])
@pytest.mark.parametrize("prefixed", [True, False])
def test_execute_directive_simple(name, prefixed):
    if prefixed:
        name = f"valid_module.{name}"
    execute_directive(Path(__file__).parent / "testdirectives", name)


@pytest.mark.parametrize("name", ["hidden3", "shown3", "packaged_op3"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [pytest.param(lambda tup: tup.root.name, id="root"), pytest.param(lambda tup: "valid3", id="fixed")],
)
def test_find_directive_system(name, prefixed, app_name_func):
    if prefixed:
        name = f"valid3.{name}"
    result = find_directive_system(name, app_name_func)
    assert result


@pytest.mark.parametrize("name", ["hidden4", "shown4", "packaged_op4"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [pytest.param(lambda tup: tup.root.name, id="root"), pytest.param(lambda tup: "valid4", id="fixed")],
)
def test_find_directive_zipapp(name, prefixed, app_name_func):
    if prefixed:
        name = f"valid4.{name}"
    result = find_directive_zipapp(name, app_name_func)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f".ff...foo.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives", name)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
def test_execute_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f".ff...foo.{name}"
    execute_directive(Path(__file__).parent / "testdirectives", name)


@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_invalid_path(prefixed):
    name = "shown2"
    if prefixed:
        name = f"valid.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives" / "invalid_modul.e", name)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_invalid_path_app_name(prefixed):
    name = "app_name2"
    if prefixed:
        name = f"foo2.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives" / "invalid_modul.e", name)
    assert result


# the both last would require to cross an invalid directory
@pytest.mark.parametrize("name", ["notknown", "shown2", "app_name2"])
def test_find_invalid_directives(name):
    with pytest.raises(SystemExit):
        find_directive(Path(__file__).parent / "testdirectives", name)
