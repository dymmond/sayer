# Middleware API Reference

Reference for `sayer/middleware.py`.

## Registries

- `_MIDDLEWARE_REGISTRY`: named middleware sets
- `_GLOBAL_BEFORE`: before hooks applied to all commands
- `_GLOBAL_AFTER`: after hooks applied to all commands

## Functions

### `register(name, before=(), after=())`

Registers a named middleware set.

### `resolve(middleware)`

Resolves middleware names/callables into two lists:

- before hooks with signature `(command_name, args)`
- after hooks with signature `(command_name, args, result)`

### `add_before_global(hook)`

Adds a global before hook.

### `add_after_global(hook)`

Adds a global after hook.

### `run_before(cmd_name, args)`

Executes global before hooks.

### `run_after(cmd_name, args, result)`

Executes global after hooks.

## Usage Example

```python
from sayer.middleware import register


def before(name, args):
    print(f"before: {name}")


def after(name, args, result):
    print(f"after: {name} -> {result}")


register("audit", before=[before], after=[after])


@command(middleware=["audit"])
def sync_users():
    return "ok"
```

## Related

- [Concepts: Middleware Model](../concepts/middleware-model.md)
- [Concepts: Command Lifecycle](../concepts/command-lifecycle.md)
- [Feature Guide: Middleware](../features/middleware.md)
