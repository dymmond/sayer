# Core Plugins API Reference

Reference for `sayer/core/plugins.py`.

## `load_plugins()`

Discovers and loads plugin entry points under `sayer.commands`.

### Behavior

1. Iterate installed entry points in `sayer.commands`.
2. Load each callable.
3. Execute callable to register plugin commands.
4. Report plugin load failures.

## Entry Point Contract

```toml
[project.entry-points."sayer.commands"]
myplugin = mypackage.module:register_func
```

## Related

- [How-to: Build a Plugin](../../how-to/build-plugin.md)
- [Feature Guide: Plugins](../../features/plugins.md)
- [API Reference: Core Engine](./engine.md)
