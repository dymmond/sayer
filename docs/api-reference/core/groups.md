# Core Groups

This document details `sayer/core/groups.py`, focusing on the `SayerGroup` class and its role in organizing CLI commands.

## SayerGroup Class

`SayerGroup` extends `click.Group` to provide enhanced group management for Sayer CLI applications.

### Key Features

* **Automatic Command Registration**: Ensures nested commands inherit Sayer's advanced capabilities.
* **Rich Error Handling**: Formats errors and help messages with `rich` for better UX.
* **Custom Help Rendering**: Overrides `format_help()` to use `render_help` for beautiful, readable help output.

### Example

```python
from sayer import group, command

cli = group(help="My CLI Group")

@cli.command()
def subcmd():
    print("Subcommand executed.")

if __name__ == "__main__":
    cli()
```

### Best Practices

* ✅ Use `group()` to organize related commands into logical groups.
* ✅ Provide helpful descriptions and help strings.
* ✅ Test subcommand behavior and help output.
* ❌ Avoid manual registration of commands inside groups; use decorators.

## Related Modules

* [Engine](./engine.md)
* [Commands](./commands.md)
