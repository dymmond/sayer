# Sayer

Sayer is an async-friendly, decorator-first framework for building Python CLIs with strong typing, middleware hooks, and rich help output.

## Documentation Map

- New to Sayer: [Start Here](./start-here.md)
- Learn by building: [Tutorials](./tutorials/index.md)
- Solve one task: [How-to Guides](./how-to/index.md)
- Understand internals: [Concepts](./concepts/index.md)
- Look up APIs: [API Reference](./api-reference/sayer.md)

## Why Sayer

- Typed command parameters (`Option`, `Argument`, `Env`, `JsonParam`)
- Sync and async command support
- Middleware hooks (`before` and `after`)
- State and context injection
- Rich help and output integration

## Quick Example

```python
from sayer import Sayer, Option

app = Sayer(name="demo")


@app.command()
def hello(name: str = Option(..., help="Name to greet")):
    print(f"Hello, {name}!")


if __name__ == "__main__":
    app()
```

Run:

```bash
python app.py hello --name Ada
```

## Recommended Learning Path

1. [Getting Started](./getting-started.md)
2. [Tutorial 1: First CLI](./tutorials/01-first-cli.md)
3. [Architecture](./concepts/architecture.md)
4. [How-to: Add a Command](./how-to/add-a-command.md)

## Related

- [Developer Workflow](./workflows/dev-loop.md)
- [Troubleshooting](./troubleshooting.md)
- [Contributing](./contributing.md)
