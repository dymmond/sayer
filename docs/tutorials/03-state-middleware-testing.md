# Tutorial 3: State, Middleware, and Testing

This tutorial adds production-grade behavior: shared state, middleware hooks, and tests.

## Step 1. Add shared state

```python
from sayer.state import State


class AppState(State):
    debug: bool = False
```

Inject it into commands:

```python
@app.command()
def status(state: AppState):
    print(f"debug={state.debug}")
```

## Step 2. Register middleware

```python
from sayer.middleware import register


def before(name, args):
    print(f"[before] {name} -> {args}")


def after(name, args, result):
    print(f"[after] {name} -> {result}")


register("audit", before=[before], after=[after])


@app.command(middleware=["audit"])
def ping():
    return "pong"
```

## Step 3. Add tests

```python
from sayer.testing import SayerTestClient


def test_ping():
    client = SayerTestClient(app=app)
    result = client.invoke(["ping"], with_return_value=True)
    assert result.exit_code == 0
    assert result.return_value == "pong"
```

## Step 4. Validate behavior

```bash
pytest -q
```

## What changed

- `State` provides shared, injected context.
- Middleware adds cross-cutting behavior.
- `SayerTestClient` validates output and return values.

## Next

- [Developer Workflow](../workflows/dev-loop.md)
- [How-to: Test CLI](../how-to/test-cli.md)
- [Concepts: Middleware Model](../concepts/middleware-model.md)
