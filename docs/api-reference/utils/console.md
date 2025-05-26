# Console Utility

This document covers `sayer/utils/console.py`, focusing on `ConsoleProxy` and global `console` usage.

## Overview

`ConsoleProxy` provides a flexible wrapper around `rich.console.Console`, ensuring output is correctly captured and styled, especially in testing environments.

## Key Components

### ConsoleProxy

* Creates a new `Console` instance on each attribute access.
* Ensures output goes to the correct stream (`sys.stdout`).
* Inherits color system and terminal forcing from Sayer settings.

### console

A globally available instance of `ConsoleProxy` for use across Sayer applications.

## Example

```python
from sayer.utils.console import console

console.print("Hello, [bold green]World![/]")
```

## Best Practices

* ✅ Use `console` for styled CLI output.
* ✅ Avoid using `print`; leverage Rich features via `console`.
* ✅ Test CLI output to confirm styling and stream handling.

## Related Modules

* [UI](./ui.md)
* [UI Helpers](./ui-helpers.md)
