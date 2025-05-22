---
hide:
  - navigation
---

# Sayer

<p align="center">
  <a href="https://sayer.tarsild.io"><img src="https://res.cloudinary.com/tarsild/image/upload/v1747661493/packages/Sayer/Logo/w8bq4nqcphyd99kns0wl.svg" alt='Sayer logo'></a>
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

**Documentation**: [https://sayer.tarsild.io](https://sayer.tarsild.io) 📚

**Source Code**: [https://github.com/tarsil/sayer](https://github.com/tarsil/sayer)

**The official supported version is always the latest released**.

---

# Motivation

Sayer is a **modern, async-native, parameter-rich Python CLI framework** designed for real-world usage.
Whether you’re building a one-liner or a suite of enterprise commands, Sayer’s declarative, testable, and elegant approach to CLI building will help you ship faster and with less boilerplate.

---

## 🚀 Why Sayer?

Sayer was built from the ground up with three things in mind:

* **Structure**: Make it easy to build large CLIs.
* **Power**: Expose async support, middleware, state, metadata, and configuration.
* **Simplicity**: Lower the barrier to entry while embracing modern Python.

You can go from:

```bash
python mytool.py run --env production
```

To building complex pipelines, nested commands, and testable apps with shared state.

---

## 📦 Installation

You can install Sayer using either `pip` or the ultra-fast `uv`.

### Using pip:

```bash
pip install sayer
```

### Using uv (recommended):

```bash
uv pip install sayer
```

---

## ✨ Quick Example

```python
from sayer import Sayer, Option

app = Sayer()

@app.command()
def hello(name: str = Option(..., help="Your name")):
    """Say hello to someone."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Run it with:

```bash
python app.py hello --name Ada
```

---

## 📚 Where to Next?

* [Getting Started](./getting-started.md)
* [Defining Commands](./features/commands.md)
* [Using Parameters](./features/params.md)
* [Adding Middleware](./features/middleware.md)
* [Working with State](./features/state.md)
* [Testing Your CLI](./features/testing.md)

Dive in — the CLI magic awaits! 🧙
