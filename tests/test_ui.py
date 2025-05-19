from pathlib import Path

import pytest
from click.testing import CliRunner

from sayer.client import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize(
    "args, expected_snippets",
    [
        (
            [],
            [
                "Sayer CLI Application",
                "Usage",
                "Parameters",
                "Commands",
                "new",
                "docs",
            ],
        ),
    ],
)
def test_root_help(runner, args, expected_snippets):
    result = runner.invoke(app.cli, args + ["--help"] if args else ["--help"])

    assert result.exit_code == 0, f"Output: {result.output}"

    out = result.output

    for snippet in expected_snippets:
        assert snippet in out, f"Expected '{snippet}' in root help"


def test_docs_group_help(runner):
    result = runner.invoke(app.cli, ["docs", "--help"])

    assert result.exit_code == 0, f"Output: {result.output}"

    out = result.output

    # Should contain docs group description
    assert "Generate Markdown documentation for all Sayer commands and groups" in out

    # Should include Usage and Parameters and Commands
    assert "Usage" in out
    assert "Parameters" in out
    assert "Commands" in out

    # Should list the 'generate' subcommand
    assert "generate" in out


def test_docs_generate_help(runner):
    # Invoke the generate command help
    result = runner.invoke(app.cli, ["docs", "generate", "--help"])

    assert result.exit_code == 0, f"Output: {result.output}"
    out = result.output

    # Should show generate command description and --output option
    assert "Generate Markdown documentation for all Sayer commands and groups" in out
    assert "--output" in out
    assert "Default" in out


def test_docs_generate_executes_and_writes_files(runner, tmp_path):
    # Use isolated filesystem and custom output directory
    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        out_dir = Path("out_docs")
        result = runner.invoke(app.cli, ["docs", "generate", "--output", str(out_dir)])

        assert result.exit_code == 0, f"Output: {result.output}"
        # Expect out_docs/commands/new.md and out_docs/commands/docs-generate.md
        cmds_dir = out_dir / "commands"
        assert cmds_dir.exists() and cmds_dir.is_dir()

        # Check new.md
        new_md = cmds_dir / "new.md"
        assert new_md.exists(), f"Missing file {new_md}"

        content = new_md.read_text()
        assert "# sayer new" in content

        # Check docs-generate.md
        dg_md = cmds_dir / "docs-generate.md"
        assert dg_md.exists(), f"Missing file {dg_md}"

        content2 = dg_md.read_text()
        assert "# sayer docs generate" in content2
