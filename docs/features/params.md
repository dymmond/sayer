# Parameters

This guide provides a comprehensive and richly explained view of Sayer’s parameter system, covering every aspect from the basics to advanced use cases.

## Overview

Sayer transforms function parameters into CLI options, arguments, and environment variable inputs. With explicit metadata via helper classes, you can:

* Define required and optional inputs.
* Use type annotations to control parsing and validation.
* Combine CLI inputs with environment variables for flexible configuration.

## Key Concepts

* **Options**: Named CLI flags (`--name value`).
* **Arguments**: Positional CLI inputs.
* **Env**: Environment variable inputs, with fallback support.
* **Annotated**: Combines typing with metadata for clarity.

## Fully Explained Examples

### Basic Option Parsing

```python
from sayer import Sayer

app = Sayer()

@app.command()
def greet(name: str):
    print(f"Hello, {name}")
```

**Why**: Maps the `name` parameter to a CLI option `--name`.
**How**: Sayer infers `str` and makes it required.

### Explicit Required Option with Help

```python
from sayer import Option

@app.command()
def greet(name: str = Option(..., help="Your name")):
    print(f"Hello, {name}")
```

**Why**: `Option(...)` makes it required, with a help message.
**How**: `...` indicates required, shown in help output.

### Optional Option with Default Value

```python
@app.command()
def greet(name: str = Option("World")):
    print(f"Hello, {name}")
```

**Why**: Default value makes it optional.
**How**: If `--name` is omitted, defaults to "World".

### Positional Arguments

```python
from sayer import Argument

@app.command()
def read(file: str = Argument(..., help="File to read")):
    print(f"Reading {file}")
```

**Why**: `Argument(...)` binds `file` as a positional argument.
**How**: Called as `read myfile.txt`.

### Environment Variable Fallback

```python
from sayer import Env

@app.command()
def auth(token: str = Env(..., env="API_TOKEN")):
    print(f"Using token: {token}")
```

**Why**: Loads `token` from environment variable if no CLI input.
**How**: `export API_TOKEN=abc` and call `auth`.

### Combined Env and Option

```python
def auth(token: str = Option(None) | Env(..., env="API_TOKEN")):
    print(f"Token: {token}")
```

**Why**: First tries CLI `--token`, then `API_TOKEN` env var.

### Advanced Types and Parsing

```python
@app.command()
def config(level: int = Option(...), tags: list[str] = Option([]), size: float = Option(1.5)):
    print(f"Level: {level}, Tags: {tags}, Size: {size}")
```

**Why**: Parses complex types like int, list, and float.
**How**: Handles JSON-style list input for `--tags`.

### Booleans as Flags

```python
@app.command()
def debug(verbose: bool = Option(False)):
    if verbose:
        print("Verbose mode enabled")
```

**Why**: `bool` options convert to CLI flags.
**How**: `--verbose` sets it True.

### Using Annotated for Clarity

```python
from typing import Annotated

@app.command()
def user(name: Annotated[str, Option(..., help="User name")]):
    print(f"User: {name}")
```

**Why**: Combines typing with metadata.
**How**: Cleaner syntax, aligns with Python standards.

### Required vs Optional Behavior Explained

| Type Hint     | Default           | Behavior |
| ------------- | ----------------- | -------- |
| `str`         | None / missing    | Required |
| `str = "foo"` | default provided  | Optional |
| `Option(...)` | required override | Required |
| `Option("x")` | optional override | Optional |

### Execution Order of Params

* **Arguments**: Parsed first (positional).
* **Options**: Named flags, follow.
* **Env**: Checked for missing inputs.
* **State Injection**: Non-CLI params injected later.

### Debugging and Tips

* ✅ Check types for mismatches.
* ✅ Use `help` in `Option` and `Argument` for clarity.
* ✅ Combine `Option` and `Env` for flexible config.
* ✅ Use `Annotated` for clean type+metadata declarations.
* ❌ Avoid ambiguous types like `list` without clear parsing logic.

### Complete Example with Explanations

```python
@app.command()
def run(
    config: Annotated[dict, Option(..., help="JSON config")],
    token: Annotated[str, Option(None) | Env(..., env="API_TOKEN")],
    debug: Annotated[bool, Option(False)]
):
    print(f"Config: {config}, Token: {token}, Debug: {debug}")
```

**Why**: Demonstrates complex CLI structure with options, env fallback, and flags.
**How**: Combines best practices into one command.

## Conclusion

Sayer’s parameter system is expressive, Pythonic, and powerful. Use it to build clean, maintainable, and user-friendly CLIs.
