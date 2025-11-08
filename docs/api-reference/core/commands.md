# Core Commands

This document provides a comprehensive reference for `sayer/core/commands.py`, focusing on the `SayerCommand` class and its role in enhancing CLI commands.

## SayerCommand Class

`SayerCommand` extends `click.Command` and customizes the help output.

### Initialization

Commands are usually created using the `@command` decorator in Sayer, but `SayerCommand` is applied internally to wrap these commands for advanced features.

### Key Features

* **Enhanced Help**: Overrides `get_help()` to provide rich, formatted help output using Sayer's `render_help`.
* **Automatic Parameter Parsing**: Supports `Annotated` types and custom parameter injection.

### Example

```python
from sayer.core.commands.sayer import SayerCommand
from click import Context

cmd = SayerCommand(
    name="greet",
    callback=lambda name: print(f"Hello, {name}"),
    params=[click.Argument(["name"])],
    help="Greet someone by name."
)
ctx = Context(cmd)
```

### Best Practices

* ✅ Let Sayer handle command creation using `@command`. Avoid instantiating `SayerCommand` manually unless extending behavior.
* ✅ Provide clear `help` strings to improve user experience.
* ❌ Avoid duplicating functionality already handled by Sayer.

## Related Modules

* [Engine](./engine.md)
* [Groups](./groups.md)
