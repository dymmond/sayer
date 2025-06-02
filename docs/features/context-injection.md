# Context Injection

Sayer’s Context Injection system equips your CLI commands with automatically provided dependencies, no wiring or factory functions needed.

Whether you need shared config, database sessions, custom environment loaders, or HTTP clients, you simply declare them in your function signature,
and Sayer does the rest.

---

## 1. Why Context Injection Matters

1. **Decoupling & Clarity**: Business logic remains free of boilerplate; your function signature lists exactly what it needs.
2. **Reusability**: Share objects (config, state, clients) across multiple commands without global variables.
3. **Testability**: Swap real dependencies for fakes in tests by overriding or mocking injected types.
4. **Composability**: Build higher-level commands on top of lower-level services seamlessly.

---

## 2. What You Can Inject

| Injectable Type        | Description                                                        | Usage Example                                |
| ---------------------- | ------------------------------------------------------------------ | -------------------------------------------- |
| **`click.Context`**    | Access raw Click context (`ctx`) including `ctx.obj`, `ctx.params` | Reading flags or storing logs                |
| **`State` subclasses** | Global singletons (e.g., config, feature flags, session)           | App config, feature toggles                  |
| **Custom classes**     | Any user-defined class via `ctx.ensure_object(SomeClass)`          | Env loaders, database sessions, HTTP clients |

Sayer detects these by inspecting your function’s annotations.  Any parameter whose type matches one of the above will be injected automatically.

---

## 3. How It Works

Internally, Sayer’s `click_command_wrapper` does:

1. Inspect your command function’s signature (`inspect.signature`).
2. For each parameter:

   * If annotation is `click.Context`, pass the `ctx` object.
   * If annotation is a subclass of `State`, instantiate once and cache in `ctx._sayer_state`.
   * Otherwise, bind from CLI-parsed args.
3. If you subclass `SayerGroup`, you can override `add_command` and wrap the callback to call `ctx.ensure_object(YourType)` for any custom types.

This mechanism ensures a single pass that merges CLI inputs and injected context before calling your function.

---

## 4. Built‑in Injection: `State`

### Defining a Shared Config

```python
from sayer import command
from sayer.state import State

class Config(State):
    debug: bool = False
    db_url: str = "sqlite:///app.db"

@command()
def show_config(config: Config):
    print(f"Debug: {config.debug}")
    print(f"DB URL: {config.db_url}")
```

* `Config` is instantiated **once** on first use and reused across all commands.
* Available as long as you import it; no extra registration.

### Singleton Behavior

```python
@command()
def enable_debug(config: Config):
    config.debug = True

@command()
def check_debug(config: Config):
    print(config.debug)  # → True if enable_debug ran earlier in same session
```

---

## 5. Custom Injection via `SayerGroup`

If you have a type that isn’t a `State` subclass—such as an environment loader or HTTP client—you can write a custom group class to inject it.

```python
import inspect
from functools import wraps
import click
from sayer import Sayer
from sayer.core.groups.sayer import SayerGroup


class EnvLoader:
    def __init__(self):
        self.name = "prod"


class CustomGroup(SayerGroup):
    def add_command(self, cmd, name=None):
        if cmd.callback:
            cmd.callback = self._wrap(cmd.callback)
        return super().add_command(cmd, name)

    def _wrap(self, func):
        original = inspect.unwrap(func)
        params = inspect.signature(original).parameters

        @wraps(func)
        def wrapped(ctx, /, *args, **kwargs):
            env = ctx.ensure_object(EnvLoader)
            if 'env' in params:
                kwargs['env'] = env
            return func(**kwargs)

        return click.pass_context(wrapped)
```

Then use it:

```python
app = Sayer(group_class=CustomGroup)

@app.command()
def run(env: EnvLoader):
    print(env.name)  # → "prod"
```

This pattern was exercised in our tests (`test_inject_custom`, `test_inject_custom_multiple`), ensuring custom types can be injected.

---

## 6. Injecting `click.Context`

If you need low‑level access to Click—for example to read `ctx.obj` or custom flags—just add `ctx: click.Context`:

```python
from sayer import command
import click

@command()
def info(ctx: click.Context):
    verbose = ctx.obj.get('verbose', False)
    click.echo(f"Verbose mode is {verbose}")
```

You can seed `ctx.obj` via `runner.invoke(..., obj={})` in tests or by setting `obj=` in your CLI entry.

---

## 7. Testing Context Injection

### Overriding `State`

```python
from sayer.state import State, get_state_classes

class FakeConfig(State):
    debug = True
    db_url = ":memory:"

get_state_classes().clear()
get_state_classes().append(FakeConfig)
```

Now any command accepting `config: Config` will receive `FakeConfig`.

### Testing CustomGroup

```python
from sayer.testing import SayerTestClient

runner = SayerTestClient(app)
result = runner.invoke(["run"])
assert "prod" in result.output
```

This confirms your custom wrapper successfully injects `EnvLoader`.

---

## 8. Real‑World Use Cases

1. **Databases**: inject sessions (`Session`), run migrations, queries.
2. **HTTP clients**: configured with base URLs, auth tokens.
3. **Feature flags**: load per‑user or environment toggles.
4. **Logging**: share logger instances or contexts.
5. **Testing harnesses**: swap real services for mocks by changing group or state classes.

With these patterns, your CLI commands are fully decoupled, highly testable, and ready for complex workflows.
