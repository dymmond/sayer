# Sayer API Reference

## `sayer.Sayer`

Primary application object for building and running a CLI.

## Constructor

```python
Sayer(
    name: str | None = None,
    help: str | None = None,
    epilog: str | None = None,
    context_settings: dict | None = None,
    add_version_option: bool = False,
    version: str | None = None,
    group_class: type[click.Group] = SayerGroup,
    command_class: type[click.Command] = SayerCommand,
    context: Any = None,
    context_class: type[click.Context] = click.Context,
    invoke_without_command: bool = False,
    no_args_is_help: bool = False,
    display_full_help: bool = settings.display_full_help,
    display_help_length: int = settings.display_help_length,
    **group_attrs,
)
```

## Core Methods

### `command(*args, **kwargs)`

Decorator used to register command functions on this app instance.

### `callback(*args, **kwargs)`

Decorator for root-level callback(s). Callback parameters support Sayer parameter metadata (`Option`, `Argument`, `JsonParam`) and `click.Context` injection.

### `add_command(cmd, name=None, is_custom=False)`

Adds a command or group to the app.

- If `cmd` is a `Sayer` app, its internal group is mounted.
- If `cmd` is a group, it is mounted as-is.
- If `cmd` is a leaf command, it is wrapped in `SayerCommand`.

### `add_sayer(alias, app, override_helper_text=True)`

Mounts another `Sayer` app under an alias.

### `add_app(alias, app, override_helper_text=True)`

Alias of `add_sayer`.

### `run(args=None)` and `__call__(args=None)`

Executes CLI dispatch. `__call__` delegates to `run`.

## Behavior Notes

- Root callbacks are executed according to `invoke_without_command` and the resolved command path.
- Callback parameter validation mirrors Click required option behavior.
- Return values are preserved for testing workflows.

## Example

```python
from sayer import Sayer, Option

app = Sayer(name="demo", help="Demo app")


@app.callback(invoke_without_command=True)
def root(verbose: bool = Option(False, "--verbose", is_flag=True)):
    if verbose:
        print("verbose mode")


@app.command()
def hello(name: str = Option(...)):
    print(f"Hello, {name}")


if __name__ == "__main__":
    app()
```

## Related

- [Concepts: Architecture](../concepts/architecture.md)
- [Concepts: Command Lifecycle](../concepts/command-lifecycle.md)
- [Feature Guide: Sayer and Sub-apps](../features/sayer-and-apps.md)
