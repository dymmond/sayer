import click
from click.testing import CliRunner

from sayer import Sayer
from sayer.core.commands import SayerCommand
from sayer.core.groups import SayerGroup


def test_add_leaf_command_wraps_in_sayer_command():
    runner = CliRunner()
    sayer = Sayer(name="test", help="Test app")

    @click.command("foo", help="Foo command")
    def foo():
        """Foo command"""
        pass

    sayer.add_command(foo)
    cmd = sayer.cli.get_command(None, "foo")
    assert isinstance(cmd, SayerCommand)

    result = runner.invoke(sayer.cli, ["foo", "--help"])
    assert "Foo command" in result.output


def test_add_plain_group_passes_through():
    runner = CliRunner()
    sayer = Sayer(name="test2", help="Test app 2")

    grp = click.Group(name="grp", help="Group help")

    @grp.command("bar", help="Bar command")
    def bar():
        """Bar command"""
        pass

    sayer.add_command(grp)
    cmd = sayer.cli.get_command(None, "grp")
    assert isinstance(cmd, click.Group)
    assert not isinstance(cmd, SayerCommand)
    assert cmd.help == "Group help"

    result = runner.invoke(sayer.cli, ["grp", "--help"])
    assert "Group help" in result.output
    assert "bar" in result.output


def test_add_sayer_instance_mounts_group():
    runner = CliRunner()
    nested = Sayer(name="nested", help="Nested group")

    @nested.command("baz", help="Baz command")
    def baz():
        """Baz command"""
        pass

    root = Sayer(name="root", help="Root app")
    root.add_command(nested)
    cmd = root.cli.get_command(None, "nested")
    assert isinstance(cmd, SayerGroup)
    assert cmd.help == "Nested group"

    result = runner.invoke(root.cli, ["nested", "--help"])
    assert "Baz command" in result.output


def test_nested_sayer_add_leaf_command_wraps_in_sayer_command():
    runner = CliRunner()
    nested = Sayer(name="nestedA", help="Nested app A")

    @click.command("fooA", help="Nested foo A")
    def fooA():
        pass

    nested.add_command(fooA)
    cmd = nested.cli.get_command(None, "fooA")
    assert isinstance(cmd, SayerCommand)

    result = runner.invoke(nested.cli, ["fooA", "--help"])
    assert "Nested foo A" in result.output


def test_nested_sayer_add_plain_group_passes_through():
    runner = CliRunner()
    nested = Sayer(name="nestedB", help="Nested app B")

    grp = click.Group(name="grpB", help="Nested grp B help")

    @grp.command("barB", help="Nested bar B")
    def barB():
        pass

    nested.add_command(grp)
    cmd = nested.cli.get_command(None, "grpB")
    assert isinstance(cmd, click.Group)
    assert not isinstance(cmd, SayerCommand)
    assert cmd.help == "Nested grp B help"

    result = runner.invoke(nested.cli, ["grpB", "--help"])
    assert "Nested grp B help" in result.output


def test_nested_sayer_add_sayer_instance_mounts_group():
    runner = CliRunner()
    nested = Sayer(name="nestedC", help="Nested app C")
    sub = Sayer(name="subC", help="Sub sayer C")

    @sub.command("bazC", help="Sub baz C")
    def bazC():
        pass

    nested.add_command(sub)
    cmd = nested.cli.get_command(None, "subC")
    assert isinstance(cmd, SayerGroup)
    assert cmd.help == "Sub sayer C"

    result = runner.invoke(nested.cli, ["subC", "--help"])
    assert "Sub baz C" in result.output


def test_add_app_alias_mounts_group_via_add_app():
    runner = CliRunner()
    root = Sayer(name="root2", help="Root2")
    nested = Sayer(name="nest", help="Nested")

    @nested.command("qux", help="Qux command")
    def qux():
        pass

    root.add_app("alias", nested)
    cmd = root.cli.get_command(None, "alias")
    assert isinstance(cmd, SayerGroup)

    result = runner.invoke(root.cli, ["alias", "--help"])
    assert "Qux command" in result.output


def test_add_sayer_alias_mounts_group_via_add_sayer():
    runner = CliRunner()
    root = Sayer(name="root3", help="Root3")
    nested = Sayer(name="nest2", help="Nested2")

    @nested.command("corge", help="Corge command")
    def corge():
        pass

    root.add_sayer("alias2", nested)
    cmd = root.cli.get_command(None, "alias2")
    assert isinstance(cmd, SayerGroup)

    result = runner.invoke(root.cli, ["alias2", "--help"])
    assert "Corge command" in result.output


def test_add_command_with_custom_name_wraps_and_uses_name():
    runner = CliRunner()
    sayer = Sayer(name="test3", help="Test3")

    @click.command("orig", help="Original help")
    def orig():
        pass

    sayer.add_command(orig, name="renamed")
    cmd = sayer.cli.get_command(None, "renamed")
    assert isinstance(cmd, SayerCommand)

    result = runner.invoke(sayer.cli, ["renamed", "--help"])
    assert "Original help" in result.output


def test_nested_add_command_with_custom_name_wraps_and_uses_name():
    runner = CliRunner()
    nested = Sayer(name="nestedD", help="Nested app D")

    @click.command("origD", help="Orig help D")
    def origD():
        pass

    nested.add_command(origD, name="renamedD")
    cmd = nested.cli.get_command(None, "renamedD")
    assert isinstance(cmd, SayerCommand)

    result = runner.invoke(nested.cli, ["renamedD", "--help"])
    assert "Orig help D" in result.output


def test_leaf_command_executes_successfully():
    runner = CliRunner()
    sayer = Sayer(name="test4", help="Test4")
    called = []

    @sayer.command("do", help="Do something")
    def do():
        called.append(True)

    result = runner.invoke(sayer.cli, ["do"])
    assert result.exit_code == 0
    assert called == [True]


def test_plain_group_command_executes_successfully():
    runner = CliRunner()
    nested = Sayer(name="nested4", help="Nested4")
    grp = click.Group(name="g4", help="Group4")

    @grp.command("act", help="Act something")
    def act():
        pass

    nested.add_command(grp)
    result = runner.invoke(nested.cli, ["g4", "act"])
    assert result.exit_code == 0


def test_sayer_group_command_executes_successfully():
    runner = CliRunner()
    nested = Sayer(name="nested5", help="Nested5")
    sub = Sayer(name="sub2", help="Sub2")

    @sub.command("run", help="Run something")
    def run():
        pass

    nested.add_command(sub)
    result = runner.invoke(nested.cli, ["sub2", "run"])
    assert result.exit_code == 0


def test_root_help_lists_all_commands():
    runner = CliRunner()
    root = Sayer(name="root5", help="Root5")

    @click.command("a1", help="A1")
    def a1():
        pass

    grp = click.Group(name="g1", help="G1")

    @grp.command("b1", help="B1")
    def b1():
        pass

    nested = Sayer(name="n1", help="N1")

    @nested.command("c1", help="C1")
    def c1():
        pass

    root.add_command(a1)
    root.add_command(grp)
    root.add_command(nested)

    result = runner.invoke(root.cli, ["--help"])
    assert "a1" in result.output
    assert "g1" in result.output
    assert "n1" in result.output


def test_nested_help_lists_all_subcommands():
    runner = CliRunner()
    nested = Sayer(name="nested6", help="Nested6")

    @click.command("x1", help="X1")
    def x1():
        pass

    grp = click.Group(name="g2", help="G2")

    @grp.command("y1", help="Y1")
    def y1():
        pass

    sub = Sayer(name="sub3", help="Sub3")

    @sub.command("z1", help="Z1")
    def z1():
        pass

    nested.add_command(x1)
    nested.add_command(grp)
    nested.add_command(sub)

    result = runner.invoke(nested.cli, ["--help"])
    assert "x1" in result.output
    assert "g2" in result.output
    assert "sub3" in result.output
