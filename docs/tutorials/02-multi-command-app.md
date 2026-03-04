# Tutorial 2: Multi-command App

Organize commands with groups and sub-apps for larger CLI surfaces.

## Goal

Create a CLI with separate domains:

- root commands (`hello`)
- grouped commands (`admin create-user`)

## Step 1. Create grouped commands

```python
from sayer import Sayer, group, Option

app = Sayer(name="demo", help="Modular CLI")
admin = group("admin", help="Admin operations")


@app.command()
def hello(name: str = Option(...)):
    print(f"Hello, {name}!")


@admin.command()
def create_user(email: str = Option(..., help="User email")):
    print(f"Created {email}")


app.add_command(admin)

if __name__ == "__main__":
    app()
```

## Step 2. Run commands

```bash
python app.py hello --name Ada
python app.py admin create-user --email ada@example.com
```

## Step 3. Add root callback for shared options

```python
from sayer import Option


@app.callback(invoke_without_command=True)
def root(verbose: bool = Option(False, "--verbose", is_flag=True)):
    if verbose:
        print("Verbose mode enabled")
```

## Step 4. Check command tree

```bash
python app.py --help
python app.py admin --help
```

## Why this matters

- Groups make command namespaces explicit.
- Sub-apps and groups support independent modules.
- Callback options can centralize shared flags.

## Next

- Continue to [Tutorial 3](./03-state-middleware-testing.md)
- Read [Architecture](../concepts/architecture.md)
- Use [How-to: Organize Groups and Sub-apps](../how-to/organize-groups-subapps.md)
