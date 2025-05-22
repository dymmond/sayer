# Middleware

Middleware in Sayer lets you hook into the execution lifecycle of commands using **named sets** or **global logic**.

It’s a clean, scalable way to:

* Run logic before or after a command
* Inject validation, authentication, logging
* Reuse behavior across multiple commands

Unlike class-based web middleware, **Sayer uses named sets and function-based hooks**.

---

## 🧩 Global Middleware

Global middleware affects **every command** — registered with:

```python
from sayer.middleware import add_before_global, add_after_global

add_before_global(lambda name, args: print("[GLOBAL BEFORE]", name, args))
add_after_global(lambda name, args, result: print("[GLOBAL AFTER]", result))
```

Good for universal hooks like logging or telemetry.

---

## 🔖 Named Middleware Sets

Sayer lets you **register named sets of hooks**, and attach them to specific commands using the `@command()` decorator.

```python
from sayer.middleware import register
from sayer.core.engine import command

# Register a middleware set called 'auth'
def auth_check(name, args):
    if args.get("user") != "admin":
        raise Exception("Access denied")

register("auth", before=[auth_check])

@command(middleware=["auth"])
def restricted(user: str):
    print("Welcome admin")
```

---

## 🧠 How It Works

When you define a command using `@command(...)`, Sayer collects:

* The command name
* The argument mapping
* Any middleware names from `middleware=[...]`

Then, when the command runs:

1. Global before middleware runs (in order registered)
2. All named middleware `before` hooks run
3. The command function is invoked
4. All named middleware `after` hooks run
5. Global after middleware runs

Each middleware hook receives:

* `cmd_name: str`
* `args: dict[str, Any]`
* (and for after hooks) `result: Any`

---

## ✅ Full Example

```python
from sayer.middleware import register, add_before_global, add_after_global
from sayer.core.engine import command

# Global hooks
add_before_global(lambda name, args: print("[before]", name))
add_after_global(lambda name, args, result: print("[after]", result))

# Middleware set for safety checks
def safety_check(name, args):
    if not args.get("confirm"):
        raise Exception("Must confirm deletion")

register("safety", before=[safety_check])

@command(middleware=["safety"])
def delete(confirm: bool = False):
    print("DELETED!")
```

```bash
$ python app.py delete
Exception: Must confirm deletion

$ python app.py delete --confirm
DELETED!
```

---

## 🧪 Middleware Testing

You can test middleware like any other logic:

```python
from sayer.core.engine import command, get_commands
from sayer.middleware import register

called = []

register("trace", before=[lambda name, args: called.append(name)])

@command(middleware=["trace"])
def hello():
    return "hi"

assert get_commands()["hello"]() == "hi"
assert called == ["hello"]
```

---

## 🧰 Recap

| Type              | Use                                     | Applies to          |
| ----------------- | --------------------------------------- | ------------------- |
| Global Middleware | `add_before_global`, `add_after_global` | All commands        |
| Named Sets        | `register("name", before=...)`          | Attached by command |
| Per Command       | `@command(middleware=[...])`            | Specific commands   |

Sayer middleware is **simple, composable, and robust** — built for full CLI lifecycle control.

Next up: share data globally with **Application State**.

👉 [Working with State](./state.md)
