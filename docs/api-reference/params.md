# Parameters

This document covers `sayer/params.py`, which manages command parameter metadata and behavior in Sayer.

## Overview

Sayer extends parameter management with flexible support for:

* Options (`Option`)
* Arguments (`Argument`)
* Environment Variables (`Env`)
* JSON Parameters (`JsonParam`)

## Key Classes

### Option

Represents a command-line option with rich metadata.

```python
from sayer import Option

@app.command()
def cmd(verbose: Option(default=False, help="Enable verbose output")):
    ...
```

* Supports prompts, env fallback, default factories.

### Argument

Represents a positional argument.

```python
from sayer import Argument

def cmd(file: Argument(help="Path to the file")):
    ...
```

### Env

Fetches a value from an environment variable.

```python
from typing import Annotated
from sayer import Env

def cmd(api_key: Annotated[str, Env(...)]):
    ...
```

### JsonParam

Parses JSON input into Python objects.

```python
from typing import Annotated
from sayer import JsonParam

def cmd(data: Annotated[dict, JsonParam]):
    ...
```

## Best Practices

* ✅ Use `Option` for configurable parameters with defaults.
* ✅ Use `Argument` for required positional inputs.
* ✅ Use `Env` and `JsonParam` for environment-configured and complex data.
* ❌ Avoid hardcoding defaults; use dynamic or env-based defaults.

## Related Modules

* [engine.py](./core/engine.md)
* [middleware.md](./middleware.md)
