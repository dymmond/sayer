# Sayer

## sayer.Sayer

The `Sayer` class is the central entry point for building a Sayer CLI application.

### Initialization

```python
from sayer import Sayer
app = Sayer()
```

* `Sayer()` initializes a new CLI application.
* Accepts optional `name` and `help` parameters for customization.

### Key Methods

* `app()` — Starts the CLI. Equivalent to calling `app.cli()`.
* `cli` — The underlying Click group object.
* `run()` — Runs the CLI, optionally with custom arguments.

### Sub-App Registration

Sayer supports adding sub-applications (nested CLIs) for modular command design.

```python
sub_app = Sayer()
app.add_sayer(sub_app)
```

### Usage Example

```python
from sayer import Sayer, command

app = Sayer(help="My CLI App")

@app.command()
def greet(name: str):
    """Greet a user by name."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Run it:

```bash
python main.py greet --name Alice
```

## Best Practices

* ✅ Always provide clear `help` strings for your app and commands.
* ✅ Structure commands using sub-apps or groups for large projects.
* ✅ Use `run()` or `app()` consistently to start the CLI.
* ❌ Avoid mixing `print` and `console.print` output.
* ❌ Don’t directly manipulate the underlying `cli` unless necessary.

## Related Topics

* [Middleware](../features/middleware.md)
* [Encoders](./encoders.md)
* [Command Groups](./core/groups.md)

This reference will expand with detailed entries for each module and function in the Sayer framework.
