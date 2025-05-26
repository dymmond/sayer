# Core Engine

This document provides a comprehensive look at `sayer/core/engine.py`, the heart of Sayer's CLI mechanics.

## Overview

The `engine` module handles:

* Command registration via decorators.
* Group creation and monkey-patching.
* Parameter binding and injection.
* Global command registries.

## Key Components

### @command Decorator

```python
from sayer import command

@command()
def greet(name: str):
    print(f"Hello, {name}!")
```

* Converts a Python function into a rich CLI command.
* Supports `Annotated` types, options, arguments, JSON parameters, and environment variables.
* Allows middleware hooks and async commands.

### group() Function

```python
from sayer import group

cli = group(name="mycli")
```

* Creates a `SayerGroup` for nested command structures.
* Monkey-patches Click’s `Group.command` to ensure Sayer’s decorators are used.

### Middleware and Context

* Parameter binding supports custom types and callbacks.
* Middleware `before` and `after` hooks can wrap commands for logging, validation, etc.

## Best Practices

* ✅ Use `@command` and `group()` to structure CLI commands and groups.
* ✅ Leverage parameter annotations and `Option`, `Argument`, `Env`, `JsonParam` for input parsing.
* ✅ Use middleware for cross-cutting concerns.

## Related Modules

* [Commands](./commands.md)
* [Groups](./groups.md)
* [Middleware](../middleware.md)
* [Parameters](../params.md)
