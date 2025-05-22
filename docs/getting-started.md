# Getting Started

Welcome to your first steps with **Sayer**, the modern async CLI framework. This guide will walk you through installing Sayer, running your first command, and understanding the basics of how it works.

---

## 📦 Installing Sayer

Sayer supports Python 3.10 and above.

### Using pip:

```bash
pip install sayer
```

### Using uv (recommended for speed):

```bash
uv pip install sayer
```

Once installed, you’ll have everything you need to start building CLIs immediately.

---

## 🚀 Your First CLI

Here’s a simple Hello World app using Sayer:

```python
# app.py
from sayer import Sayer, Option

app = Sayer()

@app.command()
def hello(name: str = Option(..., help="Your name")):
    """Says hello to the given name."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Run it like so:

```bash
python app.py hello --name Ada
```

### 🔍 What just happened?

* `@app.command()` turns a function into a CLI command.
* `Option(...)` declares a named parameter.
* `app()` runs the CLI parser.

This already provides help text, argument validation, and a beautifully formatted CLI!

Try:

```bash
python app.py --help
python app.py hello --help
```

---

## 🧠 Under the Hood

Sayer creates a full CLI parser under the hood, powered by [`click`](https://click.palletsprojects.com/) + async + a metadata-rich decorator system.

When you call `app()`, it:

1. Parses the CLI args.
2. Resolves the command.
3. Maps inputs to the function signature.
4. Runs any middleware.
5. Executes the function (sync or async).

---

## 🧪 Going Async

Want to use `async def` in your commands? No problem:

```python
@app.command()
async def ping():
    """Asynchronous command"""
    print("Pong!")
```

It runs just like the sync version:

```bash
python app.py ping
```

You can even await async database calls, HTTP requests, etc.

---

## 🗂️ Project Layout Tips

You can put all commands in a single file or split them across modules. Example structure:

```
mycli/
├── main.py
├── commands/
│   ├── greet.py
│   └── utils.py
```

Then import them in your app:

```python
# main.py
from sayer import Sayer
from commands import greet, utils

app = Sayer()

# commands auto-register from decorators

if __name__ == "__main__":
    app()
```

---

## 🧰 Recap

* ✅ Install Sayer with pip or uv
* ✅ Create a Sayer app with `Sayer()`
* ✅ Use `@app.command()` to define CLI functions
* ✅ Run via `python app.py` or `sayer` script
* ✅ Add parameters using `Option`, `Argument`, or `Env`

Next, let’s build more complex commands!

👉 [Defining Commands](./features/commands.md)
