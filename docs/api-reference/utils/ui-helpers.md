# UI Helpers

This document covers `sayer/utils/ui_helpers.py`, which provides advanced UI functionality such as user prompts and progress bars.

## Overview

The UI Helpers module includes decorators and functions to enhance CLI interactions.

## Key Functions

### confirm(prompt="Continue?", abort_message="Aborted.")

* Decorator that prompts the user for confirmation.
* Aborts execution with a message if the user declines.

### progress(items, description="Processing")

* Decorator that applies a progress bar to iteration over `items`.
* Displays processing status and collects results.

### table(data, title="Output")

* Prints a formatted table to the console.
* Columns derived from keys in the first data dictionary.

## Example

```python
from sayer.utils.ui_helpers import confirm, progress, table

@confirm()
def dangerous_action():
    print("Action confirmed.")

@progress([1, 2, 3])
def process_item(item):
    return item * 2

data = [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]
table(data)
```

## Best Practices

* ✅ Use `confirm` to safeguard critical actions.
* ✅ Use `progress` for visibility in long-running tasks.
* ✅ Format tables for readability.
* ❌ Avoid cluttering the UI with too many progress bars or prompts.

## Related Modules

* [UI](./ui.md)
