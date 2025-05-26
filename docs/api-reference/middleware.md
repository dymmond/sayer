# Middleware

This document explores `sayer/middleware.py`, which manages global and named middleware in Sayer CLI applications.

## Overview

The `middleware` module allows developers to:

* Register `before` and `after` hooks for commands.
* Create named middleware sets.
* Execute hooks with support for async and sync functions.

## Key Functions

* **register(name, before, after)**: Register a named middleware set.
* **resolve(middleware)**: Resolve a middleware reference (by name or callables) into a `before` and `after` tuple.
* **add_before_global(func)**: Add a global `before` hook.
* **add_after_global(func)**: Add a global `after` hook.
* **run_before(ctx)** and **run_after(ctx)**: Execute all applicable middleware hooks for a given context.

## Example

```python
from sayer.middleware import register, add_before_global

async def log_before(ctx):
    print(f"Running before {ctx.command.name}")

register("logger", before=[log_before], after=[])
add_before_global(log_before)
```

## Best Practices

* ✅ Use named middleware sets for reusable behavior across commands.
* ✅ Handle errors within middleware to prevent cascading failures.
* ✅ Use async functions for IO-bound middleware hooks.
* ❌ Avoid long-running middleware; keep hooks fast.

## Related Modules

* [engine.py](./core/engine.md)
