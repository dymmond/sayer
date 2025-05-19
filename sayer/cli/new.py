from pathlib import Path
from typing import Annotated

from sayer.core.engine import command
from sayer.params import Argument
from sayer.utils.ui import error, success

TEMPLATE: dict[str, str] = {
    "main.py": """from sayer import run, load_commands_from, echo

load_commands_from("commands")

if __name__ == "__main__":
    run()
""",
    "commands/__init__.py": "",
    "commands/hello.py": """from sayer import command

@command
def hello(name: str = "World"):
    echo(f"Hello, {name}!")
""",
    "pyproject.toml": """[project]
name = "mycli"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["sayer"]
""",
    ".gitignore": "__pycache__/\n*.pyc\n.env\n",
    "README.md": "# My Sayer CLI\n\nPowered by [Sayer](https://github.com/your/sayer)\n",
}


@command
def new(name: Annotated[str, Argument(help="The name given for the new cli project")]) -> None:
    """
    Create a new Sayer CLI project in *NAME* directory.
    """
    base = Path(name)
    if base.exists():
        error(f"Directory '{name}' already exists.")
        return

    for rel, content in TEMPLATE.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    success(f"✔ Created new Sayer project at ./{name}")
