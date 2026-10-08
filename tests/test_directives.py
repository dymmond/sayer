import sys
import zipfile
from pathlib import Path

import pytest

from tests.testdirectives.definitions import (
    execute_directive,
    find_directive,
    find_directive_system,
    find_directive_zipapp,
)


@pytest.fixture(scope="function")
def create_zipfile(tmp_path):
    test_directive_source = Path(__file__).parent / "testdirectives" / "build.zipfile"
    test_directive_target = tmp_path / "zipfile_zipped.zip"
    with zipfile.PyZipFile(str(test_directive_target), mode="w") as zip:
        zip.writepy(str(test_directive_source / "valid4"))
    test_directive_target_str = str(test_directive_target)
    sys.path.append(test_directive_target_str)
    try:
        yield test_directive_target
    finally:
        sys.path.remove(test_directive_target_str)
        to_remove = [module_name for module_name in sys.modules if module_name.startswith("valid4")]
        for module in to_remove:
            del sys.modules[module]


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


def test_collisions_simple():
    # collision
    with pytest.raises(SystemExit):
        execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions1", "directive1")
    # works
    execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions1", "collisions1.directive1")
    execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions1", "")


def test_collisions_fully():
    # collision
    with pytest.raises(SystemExit):
        execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions2", "directive1")
    # collision
    with pytest.raises(SystemExit):
        execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions2", "foo.directive1")
    # collision
    with pytest.raises(SystemExit):
        execute_directive(Path(__file__).parent / "testdirectives" / "coll.isions2", "")


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


@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [pytest.param(lambda tup: tup.root.name, id="root"), pytest.param(lambda tup: "valid3", id="fixed")],
)
def test_find_not_directive_system(prefixed, app_name_func):
    name = "stub3"
    if prefixed:
        name = f"valid3.{name}"
    with pytest.raises(SystemExit):
        find_directive_system(name, app_name_func)


@pytest.mark.parametrize("name", ["hidden4", "shown4", "packaged_op4"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [pytest.param(lambda tup: tup.root.name, id="root"), pytest.param(lambda tup: "valid4", id="fixed")],
)
def test_find_directive_zipapp(name, prefixed, app_name_func, create_zipfile):
    if prefixed:
        name = f"valid4.{name}"
    result = find_directive_zipapp(name, app_name_func)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [pytest.param(lambda tup: tup.root.name, id="root"), pytest.param(lambda tup: "valid4", id="fixed")],
)
def test_find_not_directive_zipapp(prefixed, app_name_func, create_zipfile):
    name = "stub4"
    if prefixed:
        name = f"valid4.{name}"
    with pytest.raises(SystemExit):
        find_directive_zipapp(name, app_name_func)


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


def test_execute_directive_help(capsys):
    name1 = "app_name"
    package = "\n[.ff...foo]\n"
    name2 = f"\n  {name1}"
    package_and_name = f"{package}  {name1}:\n"
    package_and_name_and_help = f"{package}  {name1}:\n    With app name.\n"
    assert execute_directive(Path(__file__).parent / "testdirectives", "") is None
    out, err = capsys.readouterr()
    assert "Available directives:\n" in out
    assert f"  {name1}:\n" in out
    assert package in out
    assert name2 in out
    assert package_and_name in out
    assert package_and_name_and_help in out


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
