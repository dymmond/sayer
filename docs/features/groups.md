# Groups

>Organize related commands under a shared namespace with first‑class Sayer integration and polished help output.

Sayer builds on top of Click's grouping model and adds:

- A convenience **`group()`** factory that returns a `click.Group` (defaulting to Sayer's rich UI `SayerGroup`);
- Automatic **binding of `@...command` to Sayer's enhanced `@command`** (type conversion, state injection, JSON molding, middleware hooks, async support);
- A **global registry** for groups created via `sayer.group(...)`, useful for inspection and testing.

This page shows how to define groups, add commands, nest groups, plug them into your `Sayer` application, and test them.

---

## Quick Start

```python
from sayer import Sayer, group
import click

app = Sayer(name="myapp", help="Demo app")

# 1) Create (or retrieve) a group
tools = group(name="tools", help="Utilities & helpers")

# 2) Attach commands to the group
@tools.command(name="echo", help="Echo a message")
def echo(msg: str):
    click.echo(msg)

# 3) Register the group in your app
app.add_command(tools)

# 4) CLI
# $ myapp tools echo --msg "Hello"
```

---

## When should I use `sayer.group(...)` vs `click.Group`?

You can use **either**:

- `sayer.group(...)` returns a `click.Group` (by default a `SayerGroup`) and **auto‑registers** it in Sayer's group registry.
- Any `click.Group` (including ones you create from Click directly) will still **bind commands via Sayer's command decorator**, because Sayer **monkey‑patches `click.Group.command`** globally. You still need to add your group to your `Sayer` app with `app.add_command(group)`.

!!! Tip
    **Recommendation:** Use `sayer.group(...)` for consistent help formatting and easier discovery in tests/tooling.

---

## Creating a Group

```python
from sayer import group

admin = group(
    name="admin",
    help="Administrative commands"
    # group_cls=<custom click.Group subclass>  # optional
)
```

**Parameters**

- `name: str` — CLI name (`admin` → invoked as `myapp admin ...`).
- `help: str | None` — Text shown in `--help`.
- `group_cls: type[click.Group] | None` — Custom group class. Defaults to **`SayerGroup`** for rich help formatting.
- `kwargs: type[Any]` - Any kwargs to be passed to the `click.Group`.

**Behavior**

- If a group with the same `name` already exists, `group(name, ...)` returns the **existing** instance (idempotent by name).
- All groups created via `sayer.group(...)` are recorded in Sayer's `_GROUPS` registry (accessible via `get_groups()`).

!!! Note
    If you pass a custom `group_cls`, Sayer still binds the `.command` method so your commands get the full Sayer behavior.

---

## Adding Commands to a Group

Attach commands to the group exactly like with Click:

```python
import click
from sayer import command, group

tools = group("tools", help="Utilities")

@tools.command(name="greet", help="Greet someone")
def greet(name: str, upper: bool = False):
    msg = f"hello {name}"
    click.echo(msg.upper() if upper else msg)
```

**What Sayer adds on top of Click:**

- Automatic **type conversion** based on annotations (e.g., `bool`, `int`, `Enum`, `UUID`, `date/datetime`, `Path`).
- **JSON → object molding** when using `JsonParam` or supported encoders (`dataclasses`, Pydantic, msgspec, etc.).
- **State injection**: annotate a parameter with a `State` subclass to receive the app's state instance.
- **Middleware hooks** (`before` / `after`) at the command level.
- **Async support**: `async def` commands are supported (executed via AnyIO when invoked from CLI; programmatic calls are AnyIO‑aware).

---

## Nesting Groups

You can nest groups in two ways:

### Using Click's `@parent.group(...)` decorator

Because Sayer patches `click.Group.command` globally, commands inside nested groups still bind to Sayer:

```python
from sayer import group
import click

root = group("root", help="Root commands")

@root.group(name="db", help="Database operations")
def db():  # this returns a click.Group
    """Subgroup created via Click."""
    pass

@db.command(name="init")
def db_init(url: str):
    click.echo(f"init db at {url}")
```

### Creating subgroups via `sayer.group()` and adding them

```python
from sayer import group

root = group("root")
db = group("db", help="Database operations")
root.add_command(db)   # db lives under root

@db.command
def init(url: str): ...
```

**Which to choose?**  

Use whichever fits your style. If you want Sayer's registry to know about the subgroup, prefer the `sayer.group()` approach for the subgroup as well.

---

## Registering Groups in an App

Attach your groups to a `Sayer` application:

```python
from sayer import Sayer, group

app = Sayer(name="myapp", help="Demo application")

admin = group("admin", help="Administrative commands")

@app.command  # optional: top-level commands directly on app
def version():
    return "1.0.0"

app.add_command(admin)  # now accessible under `myapp admin ...`
```

**CLI**

```bash
$ myapp --help
$ myapp admin --help
$ myapp admin users list
```

---

## Rich Help Output

Groups created with `sayer.group(...)` default to `SayerGroup`, which formats help content with Sayer's rich console renderer.
If you need a custom presentation, pass your own `group_cls`.

The **command** objects themselves also use Sayer's `SayerCommand` (by default), which integrates a rich help renderer for command-level help.

---

## Testing Groups

Sayer supports both Click's `CliRunner` and a convenience **`SayerTestClient`**.

### Using `CliRunner`

```python
import click
from click.testing import CliRunner
from sayer import Sayer, group

def test_group_with_click_runner():
    app = Sayer(name="test", help="A test application")

    nested = group(name="nested", help="An example group")

    @nested.command(name="display", help="A command within the group")
    def display():
        click.echo("hello from group")

    app.add_command(nested)

    runner = CliRunner()
    result = runner.invoke(app.cli, ["nested", "display"])

    assert result.exit_code == 0
    assert result.output.strip() == "hello from group"
```

### Using `SayerTestClient`

```python
from sayer.testing import SayerTestClient

def test_group_with_sayer_client():
    app = Sayer(name="test", help="A test application")

    nested = group(name="nested", help="An example group")

    @nested.command(name="display", help="A command within the group")
    def display():
        click.echo("hello from group")

    app.add_command(nested)

    client = SayerTestClient(app)
    result = client.invoke(["nested", "display"])

    assert result.exit_code == 0
    assert result.output.strip() == "hello from group"
```

!!! Tip
    `SayerTestClient` mirrors Click's `CliRunner` API but is pre-wired for Sayer's app entrypoint (`app.cli`), so you don't have to pass it explicitly.

---

## Group Patterns & How‑tos

### Group‑level organization

Keep each group in its own module to keep large CLIs maintainable:

```
myapp/
  __init__.py
  app.py               # creates Sayer app, attaches groups
  groups/
    __init__.py
    admin.py           # defines `admin` group + its commands
    tools.py           # defines `tools` group + its commands
```

`groups/admin.py`:

```python
# groups/admin.py
from sayer import group
import click

admin = group("admin", help="Administrative commands")

@admin.command
def users_list():
    click.echo("alice\nbob")
```

`app.py`:

```python
from sayer import Sayer
from .groups.admin import admin
from .groups.tools import tools

app = Sayer(name="myapp", help="Demo app")
app.add_command(admin)
app.add_command(tools)
```

### Sharing common options across group commands

Create a thin decorator that wraps Sayer's `@command` to inject common options:

```python
from functools import wraps
from sayer import command
from sayer.params import Option

def group_command_with_token(fn=None, /, *, required=True):
    def decorator(f):
        @command  # Sayer's command (still binds to group via .command)
        @wraps(f)
        def inner(token: str = Option(required=required), **kwargs):
            return f(token=token, **kwargs)
        return inner
    return decorator(fn) if fn else decorator

# usage:
@admin.command
@group_command_with_token
def rotate_keys(token: str):
    ...
```

### Group discovery at runtime

If you created groups with `sayer.group(...)`, you can inspect them:

```python
from sayer.temp import get_groups  # adjust import path to your engine

for name, grp in get_groups().items():
    print(name, grp.commands.keys())
```

---

## Common Pitfalls & Troubleshooting

**"My command doesn't show under the group."**

- Ensure you **decorated with the group's `.command`**, not `@command` alone, or add the decorated command object to the group manually.
- Ensure you **added the group to the app** via `app.add_command(group)`.

**"I created a group with the same name and got the old one."**

- `sayer.group(name, ...)` is **idempotent by name**. If you want a different instance, use a different name.

**"Help output looks like vanilla Click."**

- You may have supplied a custom `group_cls` that doesn't render with Sayer's `SayerGroup`. Use the default or implement similar help formatting in your custom class.

**"Nested subgroup isn't in Sayer's registry."**

- Subgroups defined via `@parent.group` are standard Click objects. They still bind commands through Sayer, but they won't appear in `get_groups()` unless you created them with `sayer.group(...)`.

---

## Examples

### Minimal grouped command

```python
from sayer import Sayer, group
import click

app = Sayer(name="demo", help="Demo")

files = group("files", help="File operations")

@files.command
def ls(path: str = "."):
    import os
    click.echo("\n".join(sorted(os.listdir(path))))

app.add_command(files)
```

```
$ demo files ls --path src
```

### Nested groups

```python
root = group("root")

@root.group("db")
def db(): pass

@db.command
def migrate(step: int = 1):
    click.echo(f"Migrating by {step}")
```

---

## Best Practices

- **One group per module** for clarity; attach in your app's single assembly point.
- Prefer **kebab‑case** command names for readability (Sayer converts underscores in function names).
- Keep **group names stable**; changing them is a breaking CLI change.
- Use **`sayer.group(...)`** for subgroups you want to **discover/test** via the registry.
- Write **CLI tests** with `CliRunner` and **app‑level tests** with `SayerTestClient`.
