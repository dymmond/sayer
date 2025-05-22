# Context Injection

Sayer allows you to inject rich context into your CLI commands, making them more powerful, dynamic, and composable.

This guide explains how context injection works in Sayer, what you can inject, and how it's resolved internally.

---

## 🧩 What is Context Injection?

Context injection is the mechanism by which Sayer **automatically provides certain objects to your command functions** — without you needing to pass them manually from the CLI.

It’s Sayer’s version of dependency injection: simple, automatic, and useful.

---

## ✅ What Can Be Injected?

| Type                 | Description                                               |
|----------------------|-----------------------------------------------------------|
| `State` subclasses   | Shared, mutable app-level state objects                   |
| Middleware context   | Injected indirectly via `args` in `before/after` hooks    |
| Parameters           | CLI args, options, and env vars (not "context" strictly)  |

---

## 🧠 Injecting State

If you define a class that inherits from `sayer.state.State`, you can inject it into **any command**:

```python
from sayer.state import State

class Settings(State):
    debug: bool = True
    region: str = "eu"
```

Sayer will detect this class, instantiate it once, and provide it to all commands that need it.

```python
from sayer import command

@command()
def show(settings: Settings):
    print("Debug mode:", settings.debug)
    print("Region:", settings.region)
```

You don’t register it — just import it, subclass `State`, and Sayer does the rest.

---

## 🔄 Singleton Behavior

All injected `State` objects are **singletons** by default.

If you mutate one in a command, the change is visible in other commands during the same app run.

```python
@command()
def switch(settings: Settings):
    settings.region = "us"

@command()
def verify(settings: Settings):
    print("Current region:", settings.region)
```

---

## 🧪 Testable and Swappable

You can override or mock injected context in tests by registering your own `State` subclasses.

```python
from sayer.state import get_state_classes

class MockSettings(State):
    debug = False
    region = "test"

get_state_classes().clear()
get_state_classes().append(MockSettings)
```

---

## 🧰 How It Works Under the Hood

1. Sayer uses a registry to track all `State` subclasses via `StateMeta`.
2. During command resolution, it checks each parameter:
    * Is this a subclass of `State`?
    * If so, instantiate (once) and cache.
3. The resolved context is passed into the command along with CLI args.

This happens inside `sayer/core/engine.py` transparently to the user.

---

## 🧬 Context vs Params

| Concept    | Injected? | Source       | Example                    |
| ---------- | --------- | ------------ | -------------------------- |
| `State`    | ✅         | Internal     | `settings: Settings`       |
| CLI Option | ✅         | CLI args/env | `name: str = Option(...)`  |
| CLI Arg    | ✅         | CLI args     | `file: Path`               |
| Middleware | 🟡        | args dict    | `args["some_key"]` in hook |

---

## 🤯 Advanced: Custom Context Resolvers *(Planned)*

In the future, Sayer may support custom context injection (similar to DI containers):

```python
@command()
def run(client: HttpClient):  # <- custom resolver
    ...
```

Stay tuned for updates.

---

## 🧰 Recap

| Feature             | Supported |
| ------------------- | --------- |
| State injection     | ✅         |
| Singleton state     | ✅         |
| CLI param injection | ✅         |
| Custom DI (planned) | 🕐 Soon   |

Sayer's context system is **minimal, powerful, and automatic** — no complex decorators or containers needed.

---

👉 Next: [Encoders](./encoders.md)
```
