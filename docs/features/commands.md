# Commands

This document provides an extensive, Django-style guide to Sayer’s command system. It offers detailed explanations, numerous examples, and actionable how-tos to help you fully leverage Sayer’s capabilities.

## What is a Command?

A command is a Python function decorated with `@command`. Sayer automatically parses parameters using `Annotated` types and manages help, execution flow, and middleware.

## Key Features of Sayer Commands

* Decorator-based registration (`@command`).
* Parameter parsing with `Annotated` types (Option, Argument, Env, JsonParam).
* Sync and async support.
* Middleware integration (before/after hooks).
* Rich help output with auto-generated parameter documentation.

## Step-by-Step Guide

### Defining Basic Commands

```python
from sayer import Sayer, command, Option
from typing import Annotated

app = Sayer(help="My CLI App")

@app.command()
def greet(name: Annotated[str, Option()], shout: Annotated[bool, Option()] = False):
    """Greet a user by name."""
    message = f"Hello, {name}!"
    if shout:
        message = message.upper()
    print(message)
```

Run:

```bash
python main.py greet --name Alice --shout
```

Output:

```
HELLO, ALICE!
```

### Complex Parameters with Annotations

```python
from sayer import Argument, Env, JsonParam
from typing import Annotated

@app.command()
def process(
    input_file: Annotated[str, Argument()],
    config: Annotated[dict, JsonParam()],
    token: Annotated[str, Env("API_TOKEN")],
    count: Annotated[int, Option()] = 1
):
    print(f"File: {input_file}, Config: {config}, Token: {token}, Count: {count}")
```

Run:

```bash
python main.py process input.txt --config '{"key": "value"}' --token secret --count 5
```

### Middleware Integration

```python
from sayer.middleware import add_before_global

async def before(ctx):
    print(f"Preparing to run {ctx.command.name}")
add_before_global(before)
```

### Subcommands and Groups

```python
from sayer import group, command

cli = group(help="Main CLI")

@cli.command()
def subcmd():
    print("Subcommand executed.")

cli()
```

### Async Commands

```python
from sayer import Sayer, command
import anyio

app = Sayer()

@app.command()
async def async_greet():
    await anyio.sleep(1)
    print("Async Hello!")

app()
```

### Dynamic Registration

```python
from sayer.utils.loader import load_commands_from
load_commands_from("myapp.commands")
```

## Comprehensive Best Practices

* ✅ Use clear docstrings and parameter annotations for help output.
* ✅ Test commands with different parameters and edge cases.
* ✅ Keep commands focused; delegate complex logic to functions.
* ✅ Use groups for modular CLI structures.
* ✅ Use `JsonParam` for structured inputs.
* ❌ Don’t mix `Option` and `Argument` on the same parameter.
* ❌ Avoid hardcoding sensitive data; use `Env` for secrets.

## Advanced Techniques

* Leverage dynamic module loading for large apps.
* Use async commands for network or I/O tasks.
* Customize middleware for logging, validation, or context prep.
* Implement complex parsers with `JsonParam`.

## Visual Diagram

```mermaid
graph TD
  Command[Command]
  Param[Parameter Parsing]
  Middleware[Middleware Hooks]
  Help[Help Generation]
  Command --> Param
  Command --> Middleware
  Command --> Help
```

## API Reference

* [Engine](../api-reference/core/engine.md)
* [Groups](../api-reference/core/groups.md)
* [Middleware](../api-reference/middleware.md)
* [Params](../api-reference/params.md)
