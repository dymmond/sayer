# Parameters

Sayer gives you rich, expressive ways to define CLI arguments using Python type annotations, default values, and explicit metadata.

This guide explains:

- How Sayer maps parameters to CLI options
- Differences between `Option`, `Argument`, and `Env`
- Advanced types and annotations
- Common patterns and edge cases

---

## 🧱 Basics

Sayer uses Python function parameters to define CLI inputs.

```python
from sayer import Sayer

app = Sayer()

@app.command()
def greet(name: str):
    print("Hello,", name)
```

```bash
python app.py greet --name Ada
# Output: Hello, Ada
```

By default:

* Parameters with no default = **required options**
* Parameters with defaults = **optional options**

---

## 🧩 Explicit Parameter Types

Sayer provides three helpers:

| Type       | Purpose                           | CLI Format         |
| ---------- | --------------------------------- | ------------------ |
| `Option`   | Named flags / options             | `--name John`      |
| `Argument` | Positional arguments              | `print foo.txt`    |
| `Env`      | Values from environment variables | `export TOKEN=...` |

---

## ✨ Using `Option`

```python
from sayer import Option

@app.command()
def greet(name: str = Option(..., help="Your name")):
    print("Hello,", name)
```

The `...` means required.

```bash
python app.py greet --name Ada
```

Optional variant:

```python
def greet(name: str = Option("World")):
    print("Hello,", name)
```

---

## 🔢 Positional Arguments: `Argument`

```python
from sayer import Argument

@app.command()
def cat(file: str = Argument(..., help="File to read")):
    print("Reading", file)
```

Called like:

```bash
python app.py cat myfile.txt
```

---

## 🌱 Environment Variables: `Env`

```python
from sayer import Env

@app.command()
def auth(token: str = Env(..., env="API_TOKEN")):
    print("Using token:", token)
```

```bash
export API_TOKEN=abc123
python app.py auth
```

You can combine:

```python
def auth(token: str = Option(None) | Env(..., env="API_TOKEN")):
    ...
```

---

## 🧠 Under the Hood

Each helper returns a **Param object**, which stores metadata:

* name
* help text
* default
* required
* env var fallback
* validators (future)

---

## 🧪 Advanced Types

You can use:

```python
@app.command()
def example(
    level: int = Option(...),
    tags: list[str] = Option([]),
    size: float = Option(1.5),
):
    ...
```

Booleans are treated as flags:

```python
@app.command()
def verbose(debug: bool = Option(False)):
    if debug:
        print("Debug mode")
```

Call:

```bash
python app.py verbose --debug
```

---

## 🧬 Using Annotated

Sayer supports `Annotated` to combine typing + metadata:

```python
from typing import Annotated
from sayer import Option

@app.command()
def user(name: Annotated[str, Option(..., help="User name")]):
    print(name)
```

This is equivalent to:

```python
def user(name: str = Option(..., help="User name")):
    ...
```

---

## ❓ Required vs Optional

| Type hint     | Default           | Behavior |
| ------------- | ----------------- | -------- |
| `str`         | None / missing    | Required |
| `str = "foo"` | default provided  | Optional |
| `Option(...)` | required override | Required |
| `Option("x")` | optional override | Optional |

---

## 🧰 Debugging Tips

* 💡 **Missing `--flag`?** → check if your param has a default
* 💡 **Env var ignored?** → make sure you use `Env(...)` or `Option() | Env(...)`
* 💡 **Wrong type?** → check your annotation (`list[int]`, `bool`, etc.)

---

## 🔁 Param Order in CLI

* `Argument`s are parsed first (positional)
* Then `Option`s (named flags)
* Then `Env` fallback
* Then injected state (not CLI)

---

## 🧰 Recap

| Param Type  | Syntax                      | Use Case                |
| ----------- | --------------------------- | ----------------------- |
| `Option`    | `Option(...), Option("x")`  | Named CLI options       |
| `Argument`  | `Argument(...)`             | Positional CLI args     |
| `Env`       | `Env(..., env="NAME")`      | Load from env variables |
| `Annotated` | `Annotated[T, Option(...)]` | Type + metadata combo   |

Sayer lets you express everything **clearly and Pythonically** — with no magic, just clean annotations.

---

👉 Next: [Middleware](./middleware.md)
