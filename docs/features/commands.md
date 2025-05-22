# Commands

In Sayer, **commands are the heart of your CLI**. Every function you decorate with `@app.command()` or `@command()` becomes a runnable CLI command.

This guide covers:

- Defining commands
- Differences between `@app.command()` and `@command()`
- Custom naming and ordering
- Command grouping and nesting
- Async support and state injection
- Command registration and lifecycle

---

## 🚀 Defining a Basic Command

```python
from sayer import Sayer

app = Sayer()

@app.command()
def greet():
    print("Hello from Sayer!")

if __name__ == "__main__":
    app()
````

Run:

```bash
python app.py greet
```

---

## 🧠 `@app.command()` vs `@command()`

Sayer provides **two decorators** for commands:

| Decorator        | Usage Context              | Registers Automatically    |
| ---------------- | -------------------------- | -------------------------- |
| `@app.command()` | When using a `Sayer()` app | ✅ Yes, inline              |
| `@command()`     | Standalone or modular use  | ✅ Yes, via global registry |

### ✅ Using `@command()` for Reusability

```python
from sayer import command

@command()
def hello():
    print("Hello!")
```

Register it with an app:

```python
from sayer import Sayer
from sayer.core.engine import get_commands

app = Sayer()
app.register_commands(get_commands())
```

---

## ✍️ Naming and Help

Use a function docstring to auto-generate help:

```python
@app.command()
def greet():
    \"\"\"Say a friendly hello.\"\"\"
    print("Hi!")
```

Use a custom name:

```python
@app.command(name="hello")
def greet():
    print("Hi!")
```

---

## 📚 Help Output

```bash
$ python app.py greet --help

Usage: app.py greet

  Say a friendly hello.
```

---

## ⚙️ Command Parameters

Commands can receive typed parameters (covered in depth in [Parameters](./params.md)):

```python
from sayer import Option

@app.command()
def welcome(name: str = Option("World", help="Name to greet")):
    print(f"Hello, {name}!")
```

```bash
python app.py welcome --name Ada
```

---

## 🧬 Async Support

```python
from sayer import command

@command()
async def run():
    await some_async_call()
```

Sayer handles it out-of-the-box.

---

## 🧩 Grouping and Nesting Commands

```python
from sayer import Sayer

app = Sayer()

@app.group()
def users():
    """User management."""
    pass

@users.command()
def create():
    print("User created")

@users.command()
def delete():
    print("User deleted")
```

You can nest as deeply as needed:

```python
@app.group()
def admin():
    pass

@admin.group()
def db():
    pass

@db.command()
def wipe():
    print("Database wiped.")
```

---

## 🧠 Injecting State

You can inject state objects:

```python
from myproject.state import Settings
from sayer import command

@command()
def config(settings: Settings):
    print(settings.debug)
```

---

## 🚨 Reserved Names and Conflicts

* Function names become CLI names
* Use `name="..."` to override
* Reserved Python keywords (`class`, `async`, etc.) should be avoided
* Duplicate names will raise an error

---

## 🛠 Advanced: Manual Execution

Use the CLI runner directly:

```python
from sayer.core.client import run

if __name__ == "__main__":
    run()
```

---

## 🧰 Recap

| Topic              | Feature                          |
| ------------------ | -------------------------------- |
| Create Commands    | `@app.command()` or `@command()` |
| Reusable Commands  | Define globally + register       |
| Help & Docstrings  | Shown in CLI                     |
| Nesting & Groups   | Use `.group()` on decorators     |
| Async Support      | Works out-of-the-box             |
| State Injection    | Accept state classes as args     |
| Conflicts/Reserved | Avoid dupes and Python keywords  |

---

👉 Next up: [Using Parameters](./params.md)
