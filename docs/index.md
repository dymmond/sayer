---
hide:
  - navigation
---

# Sayer

<p align="center">
  <a href="https://sayer.dymmond.com"><img src="https://res.cloudinary.com/tarsild/image/upload/v1747661493/packages/Sayer/Logo/w8bq4nqcphyd99kns0wl.svg" alt='Sayer logo'></a>
</p>

<p align="center">
    <em>Fast. Scalable. Elegant. Command the CLI like a boss. 🧙‍♂️</em>
</p>

<p align="center">
<a href="https://github.com/dymmond/sayer/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" target="_blank">
    <img src="https://github.com/dymmond/sayer/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" alt="Test Suite">
</a>

<a href="https://pypi.org/project/sayer" target="_blank">
    <img src="https://img.shields.io/pypi/v/sayer?color=%2334D058&label=pypi%20package" alt="Package version">
</a>

<a href="https://pypi.org/project/sayer" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/sayer.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

---

**Documentation**: [https://sayer.dymmond.com](https://sayer.dymmond.com) 📚

**Source Code**: [https://github.com/dymmond/sayer](https://github.com/dymmond/sayer)

**The official supported version is always the latest released**.

---

This comprehensive guide will help you set up and understand Sayer.

We’ll walk you through installation, project creation, and writing your first commands, all with explanations, examples, and common pitfalls.

## Prerequisites

Before you begin, ensure you have:

* Python 3.8 or higher installed.
* A terminal/command prompt.
* A basic understanding of Python and CLI concepts.

## Installation

Install Sayer using pip:

```bash
pip install sayer
```

If you encounter permission errors, try:

```bash
pip install --user sayer
```

Or use a virtual environment:

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install sayer
```

## Creating a New CLI Project

Sayer can scaffold a complete project structure with one command:

```bash
sayer new myapp
```

This creates the following structure:

```
myapp/
├── main.py            # Entry point for your CLI
├── commands/          # Directory for your custom commands
│   └── __init__.py
├── pyproject.toml     # Project metadata
├── README.md
└── .gitignore
```

**What to do:**

* Edit `main.py` to define your commands.
* Add new modules under `commands/` to organize functionality.

**What NOT to do:**

* Don’t modify `pyproject.toml` unless you understand Python packaging.
* Avoid hardcoding absolute paths inside your CLI; use dynamic paths.

## Writing Your First Command

Open `main.py` and add a basic command:

```python
from sayer import Sayer, command

app = Sayer()

@app.command()
def hello(name: str):
    """Say hello to a user by name."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Run it:

```bash
python main.py hello --name Alice
```

Output:

```
Hello, Alice!
```

## Understanding the Code

* `Sayer()` creates the CLI app.
* `@app.command()` decorates the `hello` function to expose it as a CLI command.
* The `name` parameter is automatically parsed from `--name`.
* `if __name__ == "__main__": app()` runs the CLI when the script is executed.

## Best Practices

* ✅ Use clear and concise help strings (docstrings) for commands.
* ✅ Test your commands with various argument combinations.
* ❌ Avoid complex logic inside commands; delegate to helper functions.
* ❌ Don’t assume `name` will always be provided – consider adding defaults.

## Next Steps

* Explore [API Reference](./api-reference/sayer.md) for detailed module docs.
* Learn about [Middleware](./features/middleware.md) for hooks and validation.
* Add complex parameters and encoders for advanced use cases.

With Sayer, you’re not just writing a CLI – you’re building a robust, maintainable, and user-friendly command-line application. Let’s get started!
