# Config Utility

This document covers `sayer/utils/config.py`, detailing the `SayerConfig` class for configuration management.

## Overview

`SayerConfig` provides a simple configuration system that:

* Stores settings in memory.
* Falls back to environment variables.
* Supports default values.

## Key Methods

### get(key, default=None)

Retrieves a configuration value.

* Checks in-memory first.
* Falls back to `os.environ`.
* Uses `default` if not found.

### set(key, value)

Sets a configuration value in memory.

### all()

Returns all configuration key-value pairs, combining environment variables and in-memory overrides.

### get_config()

Returns a singleton instance of `SayerConfig`.

## Example

```python
from sayer.utils.config import get_config

config = get_config()
config.set("debug", True)
print(config.get("debug"))
```

## Best Practices

* ✅ Use `get_config()` for consistent access.
* ✅ Leverage `all()` to inspect configuration during debugging.
* ❌ Avoid direct environment access; use `get` and `set` methods.

## Related Modules

* [Settings](../conf/settings.md)
