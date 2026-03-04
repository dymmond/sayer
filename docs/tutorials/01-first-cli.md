# Tutorial 1: First CLI

Build and run your first Sayer command, then verify behavior with help output.

## Prerequisites

- Python 3.10+
- `pip install sayer`

## Step 1. Create `app.py`

```python
from sayer import Sayer, Option

app = Sayer(name="demo", help="My first Sayer app")


@app.command()
def hello(name: str = Option(..., help="Name to greet")):
    """Greet a user."""
    print(f"Hello, {name}!")


if __name__ == "__main__":
    app()
```

## Step 2. Run the command

```bash
python app.py hello --name Ada
```

Expected output:

```text
Hello, Ada!
```

## Step 3. Inspect help output

```bash
python app.py --help
python app.py hello --help
```

## Step 4. Understand what happened

- `@app.command()` registers the function as a CLI command.
- `Option(...)` defines a named option with validation and help metadata.
- `app()` dispatches to Click/Sayer runtime.

## Next

- Continue to [Tutorial 2](./02-multi-command-app.md)
- Read [Command Lifecycle](../concepts/command-lifecycle.md)
- Use [How-to: Add a Command](../how-to/add-a-command.md)
