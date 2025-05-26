# Loader

This document covers `sayer/utils/loader.py`, which handles dynamic module discovery and loading.

## Overview

The loader module:

* Dynamically imports modules and submodules.
* Supports reloading of modules during development.
* Enables dynamic command registration via decorators.

## Key Function

### load_commands_from(module_path)

* Imports a module or package specified by `module_path`.
* If a package, recursively imports all submodules.
* Reloads modules to ensure fresh command registration.

## Example

```python
from sayer.utils.loader import load_commands_from

load_commands_from("myapp.commands")
```

## Best Practices

* ✅ Organize commands into separate modules under a common package.
* ✅ Use `load_commands_from` during startup to discover all commands.
* ✅ Reload modules during development to reflect changes.

## Related Modules

* [Engine](../core/engine.md)
