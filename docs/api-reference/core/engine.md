# Core Engine API Reference

Reference for `sayer/core/engine.py`, which defines command/group decorators and parameter binding behavior.

## `command(...)`

Transforms a Python function into a Click command with Sayer runtime behavior.

### Supports

- typed parameter conversion
- `Option`, `Argument`, `Env`, `JsonParam`
- middleware resolution and execution
- `click.Context` and `State` injection
- async command execution

### Signature modes

```python
@command
@command()
@command("custom-name")
@command(name="custom-name", hidden=True)
@command(middleware=[...])
```

## `group(name, group_cls=None, help=None, is_custom=False, custom_command_name=None, **kwargs)`

Creates or retrieves a group and patches its `.command` method to use Sayer's command decorator.

## `build_click_parameter(...)`

Internal helper that converts an inspected function parameter plus metadata into the correct Click option/argument decorator.

## Registries

- `COMMANDS`: global registry of top-level commands
- `GROUPS`: global registry of groups

## Utility Functions

- `get_commands()`
- `get_groups()`
- `bind_command_to_group(...)`

## Runtime Flow

1. Inspect function signature and type hints.
2. Build Click parameters from metadata.
3. Bind and convert parsed values at invocation.
4. Inject state/context.
5. Execute middleware and command function.
6. Return value to Click/testing layers.

## Related

- [Concepts: Command Lifecycle](../../concepts/command-lifecycle.md)
- [Concepts: Parameter System](../../concepts/parameter-system.md)
- [Feature Guide: Commands](../../features/commands.md)
