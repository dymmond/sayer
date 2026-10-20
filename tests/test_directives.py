import sys
import zipfile
from pathlib import Path

import pytest

from tests.testdirectives.definitions import (
    execute_directive,
    extract_directives_raw,
    find_directive,
    find_directive_system,
    find_directive_zipapp,
)


@pytest.fixture(scope="function")
def create_zipfile(tmp_path):
    test_directive_source = Path(__file__).parent / "testdirectives" / "build.zipfile"
    test_directive_target = tmp_path / "zipfile_zipped.zip"
    with zipfile.PyZipFile(str(test_directive_target), mode="w") as zip_file:
        zip_file.writepy(str(test_directive_source / "valid_zipapp"))
    test_directive_target_str = str(test_directive_target)
    sys.path.append(test_directive_target_str)
    try:
        yield test_directive_target
    finally:
        sys.path.remove(test_directive_target_str)
        to_remove = [
            module_name for module_name in sys.modules if module_name.startswith("valid_zipapp")
        ]
        for module in to_remove:
            del sys.modules[module]


@pytest.mark.parametrize(
    "name", ["class_based_hidden", "class_based_shown", "hidden", "shown", "packaged_op"]
)
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize("use_files", [True, None])
def test_find_directive_classic(name, prefixed, use_files):
    if prefixed:
        name = f"valid_module.{name}"
    result = find_directive(
        Path(__file__).parent / "testdirectives", directive=name, use_files=use_files
    )
    assert result


@pytest.mark.parametrize("name", ["shownx", "invalid.shown", "valid_module.sho"])
def test_find_not_directive_suggestion(name, capsys):
    prefixed = "." in name
    with pytest.raises(SystemExit):
        find_directive(Path(__file__).parent / "testdirectives", name)
    out, err = capsys.readouterr()
    assert f"Specified directive: `{name}` not found." in out
    if prefixed:
        assert "\nDid you mean `valid_module.shown`?\n" in out
    else:
        assert "\nDid you mean `shown`?\n" in out


@pytest.mark.parametrize("name", ["class_based_hidden", "class_based_shown", "hidden", "shown"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize("use_files", [True, None])
def test_execute_directive_classic(name, prefixed, use_files):
    if prefixed:
        name = f"valid_module.{name}"
    execute_directive(Path(__file__).parent / "testdirectives", name, use_files=use_files)


@pytest.mark.parametrize(
    "name", ["[/]", "valid_module.class_based-shown", "valid_module.[/]", "valid_modu.le.shown"]
)
def test_invalid(name, capsys):
    with pytest.raises(SystemExit):
        execute_directive(Path(__file__).parent / "testdirectives", name)
    out, err = capsys.readouterr()
    assert f"✖ Specified directive: `{name}` not valid as directive." in out


@pytest.mark.parametrize("use_files", [True, None, False])
def test_path_is_file_fails(use_files):
    assert (
        extract_directives_raw(
            Path(__file__).parent / "valid_module" / "directives" / "operations" / "shown.py",
            patterns=["*"],
            use_files=use_files,
        )
        == {}
    )


@pytest.mark.parametrize("cleanup_imports", [True, False])
@pytest.mark.parametrize("use_files", [True, None, False])
def test_cleanup(use_files, cleanup_imports):
    for k in list(sys.modules.keys()):
        if "valid_system" in k:
            del sys.modules[k]
    sentinel = object()
    sys.modules["valid_system.directives"] = sentinel
    try:
        path = Path(__file__).parent / "testdirectives" / "_modules_for_system_and_cleanup"
        assert path.is_dir()
        results = extract_directives_raw(
            path,
            use_files=use_files,
            patterns=["**/directives/[!_]*.py", "**/directives/*/__init__.py"],
            cleanup_imports=cleanup_imports,
        )
        assert results
        leftovers = [k for k in sys.modules if "valid_system" in k]
        if not cleanup_imports:
            assert leftovers
            assert sys.modules["valid_system.directives"] is not sentinel
        else:
            assert leftovers == ["valid_system.directives"]
            assert sys.modules["valid_system.directives"] is sentinel
    finally:
        for k in list(sys.modules.keys()):
            if "valid_system" in k:
                del sys.modules[k]


def test_collisions_directives(capsys):
    # collision
    with pytest.raises(SystemExit):
        execute_directive(
            Path(__file__).parent / "testdirectives" / "coll.isions_conflicting_directives",
            "directive1",
        )
    out, err = capsys.readouterr()
    assert "\nPossible directives:\n" in out
    assert "\n  collisions1.directive1\n" in out
    assert "\n  collisions2.directive1\n" in out
    # works
    execute_directive(
        Path(__file__).parent / "testdirectives" / "coll.isions_conflicting_directives",
        "collisions1.directive1",
    )
    execute_directive(
        Path(__file__).parent / "testdirectives" / "coll.isions_conflicting_directives", ""
    )


def test_collisions_app_names_and_directives(capsys):
    # collision
    with pytest.raises(SystemExit):
        execute_directive(
            Path(__file__).parent
            / "testdirectives"
            / "coll.isions_conflicting_app_names_and_directives",
            "directive1",
        )
    out, err = capsys.readouterr()
    assert "✖ Following directives have collisions:\n" in out
    assert "\n  foo.directive1\n" in out
    # collision
    with pytest.raises(SystemExit):
        execute_directive(
            Path(__file__).parent
            / "testdirectives"
            / "coll.isions_conflicting_app_names_and_directives",
            "foo.directive1",
        )
    # collision
    with pytest.raises(SystemExit):
        execute_directive(
            Path(__file__).parent
            / "testdirectives"
            / "coll.isions_conflicting_app_names_and_directives",
            "",
        )


@pytest.mark.parametrize("name", ["hidden3", "shown3", "packaged_op3"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [
        pytest.param(lambda tup: tup.root.name, id="root"),
        pytest.param(lambda tup: "valid_system", id="fixed"),
    ],
)
def test_find_directive_system(name, prefixed, app_name_func):
    if prefixed:
        name = f"valid_system.{name}"
    result = find_directive_system(name, app_name_func)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [
        pytest.param(lambda tup: tup.root.name, id="root"),
        pytest.param(lambda tup: "valid_system", id="fixed"),
    ],
)
def test_find_not_directive_system(prefixed, app_name_func):
    name = "stub3"
    if prefixed:
        name = f"valid_system.{name}"
    with pytest.raises(SystemExit):
        find_directive_system(name, app_name_func)


@pytest.mark.parametrize("name", ["hidden4", "shown4", "packaged_op4"])
@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [
        pytest.param(lambda tup: tup.root.name, id="root"),
        pytest.param(lambda tup: "valid_zipapp", id="fixed"),
    ],
)
def test_find_directive_zipapp(name, prefixed, app_name_func, create_zipfile):
    if prefixed:
        name = f"valid_zipapp.{name}"
    result = find_directive_zipapp(name, app_name_func)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize(
    "app_name_func",
    [
        pytest.param(lambda tup: tup.root.name, id="root"),
        pytest.param(lambda tup: "valid_zipapp", id="fixed"),
    ],
)
def test_find_not_directive_zipapp(prefixed, app_name_func, create_zipfile):
    name = "stub4"
    if prefixed:
        name = f"valid_zipapp.{name}"
    with pytest.raises(SystemExit):
        find_directive_zipapp(name, app_name_func)


@pytest.mark.parametrize("prefixed", [True, False])
def test_find_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f"_föooòäo.{name}"
    result = find_directive(Path(__file__).parent / "testdirectives", name)
    assert result


@pytest.mark.parametrize("prefixed", [True, False])
def test_execute_directive_app_name(prefixed):
    name = "app_name"
    if prefixed:
        name = f"_föooòäo.{name}"
    execute_directive(Path(__file__).parent / "testdirectives", name)


def test_execute_directive_help(capsys):
    name1 = "app_name"
    package = "\n[_föooòäo]\n"
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
    # class based and function based
    assert out.count("shown") == 2
    # neither class_based_hidden nor hidden should appear
    assert "hidden" not in out


@pytest.mark.parametrize("prefixed", [True, False])
@pytest.mark.parametrize("use_files", [None, True])
def test_find_directive_invalid_path(prefixed, use_files):
    # test cleanup
    assert "valid_beyond_invalid_module" not in sys.modules
    name = "shown2"
    if prefixed:
        name = f"valid_beyond_invalid_module.{name}"
    result = find_directive(
        Path(__file__).parent / "testdirectives" / "invalid_modul.e", name, use_files=use_files
    )
    assert result
    assert "valid_beyond_invalid_module" not in sys.modules


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
