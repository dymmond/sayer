# Working with State

In Sayer, application state is **explicit, typed, and injectable**.

Unlike traditional frameworks that attach `.state` to the app or request objects, **Sayer uses Python classes** to define and share global state.
This makes it safer, testable, and fully compatible with dependency injection.

---

## 🧠 What Is State in Sayer?

Sayer uses a special base class `State`, and any class that inherits from it becomes globally available to commands — like a dependency.

```python
from sayer.state import State

class Config(State):
    region: str = "us"
    debug: bool = False
```

You can now inject this into any command:

```python
from sayer import command

@command()
def show(config: Config):
    print("Region:", config.region)
    print("Debug:", config.debug)
```

---

## ⚙️ How It Works

* All subclasses of `State` are auto-registered
* Sayer creates a single shared instance per subclass
* These instances are injected into commands when used as parameters

It’s zero-config and fully typed.

---

## 🛠️ Mutating State

State is **singleton-scoped** and mutable:

```python
@command()
def init(config: Config):
    config.region = "eu"

@command()
def status(config: Config):
    print("Current region is:", config.region)
```

If `init()` runs first, `status()` sees the changed value.

---

## 📁 Real-World Use Cases

* Load environment or config from disk
* Store API credentials
* Track dry-run flags or debug mode
* Inject shared services (client, database wrapper, etc.)

---

## 🔒 Type-Safe Defaults

Because state is class-based, you get default values, validation, and IDE support:

```python
class Settings(State):
    debug: bool = False
    retries: int = 3

@command()
def run(settings: Settings):
    if settings.debug:
        print("Debugging...")
```

---

## 🧪 Testing State

You can override state for tests:

```python
from sayer.state import State, get_state_classes

class Fake(State):
    token = "xyz"

def test_token():
    get_state_classes().clear()
    get_state_classes().append(Fake)

    @command()
    def whoami(state: Fake):
        assert state.token == "xyz"
```

---

## 🧰 Recap

| Feature              | Description                             |
| -------------------- | --------------------------------------- |
| Define global state  | Subclass `State`                        |
| Inject into commands | Use class as param                      |
| Singleton lifetime   | One shared instance per run             |
| Fully typed          | Yes, with autocompletion and defaults   |
| Works in tests       | Yes, override via `get_state_classes()` |

State in Sayer is simple, explicit, and structured — perfect for clean CLI design.

Back to [Middleware](./middleware.md) or explore the [Testing](./testing.md) guide next!
