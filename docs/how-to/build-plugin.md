# How-to: Build a Plugin

## Goal

Register external commands through Python entry points.

## Step 1. Add entry point

```toml
[project.entry-points."sayer.commands"]
myplugin = mypackage.module:register_func
```

## Step 2. Register commands

```python
from sayer import command


def register_func():
    @command()
    def hello_plugin():
        print("hello from plugin")
```

## Step 3. Install and run

```bash
pip install -e .
python app.py hello-plugin
```

## Design Guidelines

- Keep `register_func` lightweight.
- Avoid side effects during import.
- Treat plugin load failures as recoverable.

## Related

- [Concepts: Architecture](../concepts/architecture.md)
- [API Reference: Core Plugins](../api-reference/core/plugins.md)
- [Feature Guide: Plugins](../features/plugins.md)
