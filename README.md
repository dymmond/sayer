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

## 🤔 What is Sayer?

Sayer is a modern, async-native Python CLI framework built for developers who want more:

- More structure.
- More power.
- More expressiveness.

Less boilerplate. Less headache. Less "why doesn't this just work?".

Designed to scale from weekend scripts to enterprise-grade CLI suites — with a touch of magic.

---

## 📦 Installation

**Using [pip](https://pip.pypa.io/):**

```bash
pip install sayer
```

**Or with [uv](https://github.com/astral-sh/uv) (blazing fast):**

```bash
uv pip install sayer
```

---

## 🧩 Features

* ✅ Fully async support out-of-the-box
* ✅ Param metadata via `Option(...)`, `Argument(...)`, `Env(...)` — inspired by the best
* ✅ Declarative CLI building with decorators
* ✅ Built-in middleware system (yes, for CLI!)
* ✅ Shared app state and lifecycle management
* ✅ Terminal-rich output via `rich`
* ✅ Easy testing with `SayerTestClient`
* ✅ Flexible help and docs rendering
* ✅ Clean project scaffolding, sensible defaults
* ✅ 100% type annotated.

---

## 🔥 Why Sayer?

| Feature               | Sayer        | Notes                             |
| --------------------- | ------------ | --------------------------------- |
| Async Support         | ✅ Yes        | Truly async from top to bottom    |
| Param Metadata        | ✅ Yes        | With rich options, env vars, etc. |
| Middleware Support    | ✅ Yes        | Per-command, app-wide, scoped     |
| Lifecycle Hooks       | ✅ Yes        | `on_startup`, `on_shutdown`       |
| State Management      | ✅ Yes        | Like a Flask `g` but better       |
| Testability           | ✅ Yes        | CLI client for unit tests         |
| Output Styling        | ✅ Yes        | Built-in `rich` integration       |
| Based on Modern Tools | ✅ Hatch + UV | Modern dev setup from day 1       |
| Full Typing           | ✅ Yes        | Mypy + Ruff compliant             |
| Fun to Use?           | 🕺 Extremely | Let the code dance with you       |

---

## 🚀 Getting Started

Create your first CLI app:

```python
from sayer import Sayer, Option

app = Sayer()

@app.command()
def hello(name: str = Option(..., help="Your name")):
    """Say hello to someone"""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Run it:

```bash
$ python app.py hello --name Ada
Hello, Ada!
```

---

## 🧪 Testing

```bash
hatch run test:test
```

Or with pytest:

```bash
pytest -v
```

---

## 📚 Documentation

Full docs available at: [https://sayer.dymmond.com](https://sayer.dymmond.com)

You’ll find:

* Full API reference
* Command examples
* Parameter deep dives
* Middleware patterns
* Configuration strategies
* ... and some fun easter eggs 🐣
