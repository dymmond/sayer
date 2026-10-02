from pathlib import Path
import pytest

from .testdirectives.definitions import execute_directive, find_directive

@pytest.mark.parametrize("name", [
    "class_based_hidden", "class_based_shown", "hidden", "shown"
])
@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_simple(name, prefixed):
    if prefixed:
        name = f"valid_module.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives", name)
    assert result

@pytest.mark.parametrize("name", [
    "class_based_hidden", "class_based_shown", "hidden", "shown"
])
@pytest.mark.parametrize("prefixed", [True, False])
def test_execute_directive_simple(name, prefixed):
    if prefixed:
        name = f"valid_module.{name}"
    execute_directive(Path(__file__).parent / "testdirectives", name)

@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f"foo.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives", name)
    assert result

@pytest.mark.parametrize("prefixed", [True, False])
def test_execute_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f"foo.{name}"
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


@pytest.mark.parametrize("name", ["notknown", "packaged_op"])
def test_find_invalid_directives(name):
    with pytest.raises(SystemExit):
        find_directive(Path(__file__).parent / "testdirectives", name)
