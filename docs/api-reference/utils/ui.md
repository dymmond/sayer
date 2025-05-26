# UI

This document covers `sayer/utils/ui.py`, which provides helper functions for styled CLI output.

## Overview

The UI module includes functions for common CLI messages, leveraging `rich` formatting for clarity.

## Key Functions

### echo(*args, **kwargs)

Prints messages to the console with rich formatting.

### error(message)

Prints an error message prefixed with `✖` in bold red.

### success(message)

Prints a success message prefixed with `✔` in bold green.

### warning(message)

Prints a warning message prefixed with `⚠` in bold yellow.

### info(message)

Prints an informational message prefixed with `ℹ` in bold blue.

## Example

```python
from sayer.utils.ui import success, error

success("Operation completed successfully.")
error("An error occurred.")
```

## Best Practices

* ✅ Use these functions instead of raw `print` statements for consistency.
* ✅ Tailor messages for clarity and brevity.
* ❌ Avoid nesting `echo` calls or combining with print.

## Related Modules

* [Console](./console.md)
