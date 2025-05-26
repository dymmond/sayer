# Core Logging

This document covers `sayer/core/logging.py`, which manages logging configuration for Sayer CLI applications.

## Overview

The `logging` module provides a standardized logging setup, using Python’s `logging` module and Rich console formatting.

## Key Component

### StandardLoggingConfig

`StandardLoggingConfig` is a class that implements logging setup.

* **default_config()**: Returns a dictionary with default logging settings.
* **configure()**: Applies logging settings using `logging.config.dictConfig`.
* **get_logger()**: Returns a logger instance named `sayer`.

## Example Usage

```python
from sayer.core.logging import StandardLoggingConfig

config = StandardLoggingConfig()
config.configure()
logger = config.get_logger()
logger.info("Logging setup complete.")
```

## Best Practices

* ✅ Configure logging at the start of your CLI application.
* ✅ Use consistent log formats for clarity.
* ❌ Avoid extensive logging in command callbacks; use middleware or global hooks instead.

## Related Modules

* [Engine](./engine.md)
* [Middleware](../middleware.md)
