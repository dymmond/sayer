# Configuration Settings

This document details `sayer/conf/settings.py`, which manages dynamic configuration for Sayer.

## Overview

The `Settings` class provides a centralized configuration system, layered with environment variables and in-memory overrides.

## Key Components

* **`ENVIRONMENT_VARIABLE`**: Defines the environment variable (`SAYER_SETTINGS_MODULE`) that can point to a custom settings module.
* **`SettingsForward`**: A proxy descriptor that forwards attribute access to the actual `Settings` instance.
* **`settings`**: A globally available proxy instance of `Settings`, used throughout Sayer.

## Usage

```python
from sayer.conf import settings

print(settings.debug)
settings.debug = True
print(settings.debug)
```

## How It Works

* **In-Memory Overrides**: Attributes set on `settings` override environment variables.
* **Environment Variables**: `settings` checks the environment if an attribute is not set in memory.
* **Fallback**: If neither is set, defaults are used from `global_settings`.

## Best Practices

* ✅ Use `settings` for accessing and modifying global configuration.
* ✅ Define a custom settings module and set `SAYER_SETTINGS_MODULE` for environment-specific configs.
* ❌ Avoid hardcoding settings; use `settings` everywhere.

## Related Modules

* [Global Settings](./global-settings.md)
