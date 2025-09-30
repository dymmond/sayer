# Core Plugins

This document covers `sayer/core/plugins.py`, which manages the dynamic plugin loading system in Sayer.

## Overview

The `plugins` module enables Sayer to:

* Dynamically discover commands and extensions from installed packages.
* Use entry points defined under the `sayer.commands` group.

## Key Function

### load_plugins()

* **Purpose**: Scans installed packages for entry points named `sayer.commands`.
* **Process**:
   * Iterates over each entry point.
   * Imports the entry point's module and calls its `register_func`.
   * Catches and logs any import or execution errors.
* **Usage**:

```python
from sayer.core.plugins import load_plugins
load_plugins()
```

## Writing a Plugin

1. In your package's `pyproject.toml` or `setup.cfg`, define an entry point:

```toml
[project.entry-points."sayer.commands"]
myplugin = mypackage.module:register_func
```

2. Implement `register_func`:

```python
def register_func():
    from sayer import command
    @command()
    def mycmd():
        print("Hello from my plugin!")
```

3. Install your package and restart the CLI.

## Best Practices

* ✅ Use plugins to modularize large CLI applications.
* ✅ Handle import errors gracefully in `register_func`.
* ❌ Avoid side-effects during plugin load (e.g., DB connections).

## Related Modules

* [Engine](./engine.md)
