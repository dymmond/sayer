# Terminal Output Helpers

Sayer provides a set of helpful functions to improve terminal output — clean, colorful, and readable using **Rich** under the hood.

These helpers are available directly from the top-level `sayer` package:

```python
from sayer import echo, success, warning, error
```

---

## 🖨️ `echo(...)`

```python
echo("Hello, world!")
```

Basic printing to the terminal using `rich.print()`. It supports:

* Markdown-like rich formatting
* Inline color tags (e.g. `[green]`, `[bold red]`)

```python
echo("[bold cyan]Starting CLI...[/bold cyan]")
```

---

## ✅ `success(...)`

```python
success("✔ Operation completed")
```

* Prints the message in a green success panel
* Adds a checkmark-style emoji prefix
* Ideal for confirmation or completion messages

---

## ⚠️ `warning(...)`

```python
warning("Something may be wrong...")
```

* Prints the message in a yellow warning panel
* Great for non-fatal issues

---

## ❌ `error(...)`

```python
error("Something went wrong!")
```

* Prints the message in a red error panel
* Meant for fatal or recoverable errors
* Also used internally in command failures

---

## `info(...)`

```python
info("Something went wrong!")
```

* Prints the message in a cyan informative panel
* Meant for informational messages

---

## 🔍 Styling Example

```python
from sayer import echo, success, warning, error

echo("Loading CLI...")
success("Project created")
warning("Missing .env file, using defaults")
error("Could not connect to server")
info("Some info message")
```

Output:

```
Loading CLI...
[✅] Project created
[⚠️] Missing .env file, using defaults
[❌] Could not connect to server
```

---

## 📦 Internals

All output uses:

* `rich.console.Console` instance
* Rich formatting markup
* `rich.panel.Panel` for boxed output

You can control color rendering via:

```python
from sayer.conf import settings

settings.force_terminal = True
settings.color_system = "256"  # or "truecolor"
```

---

## 🧰 Recap

| Helper      | Color               | Use Case                     |
|-------------|---------------------|------------------------------|
| `echo()`    | Inherits Rich style | General CLI messages         |
| `success()` | Green               | Positive results or confirms |
| `warning()` | Yellow              | Caution messages             |
| `error()`   | Red                 | Fatal/failed state messages  |
| `info()`    | Info                | Informational messages       |

These functions are designed to make your CLI feel **polished and professional** out-of-the-box.
