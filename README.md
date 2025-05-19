# 🚀 Sayer — The Modern Python CLI Framework

<p align="center">
  <a href="https://sayer.tarsild.io"><img src="https://res.cloudinary.com/tarsild/image/upload/v1747661493/packages/Sayer/Logo/w8bq4nqcphyd99kns0wl.svg" alt='Esmerald'></a>
</p>

<p align="center">
    <em>🚀 Highly scalable, performant, easy to learn, easy to code and for every application. 🚀</em>
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

**Sayer** is a fast, powerful, and modern Python framework for building command-line interfaces — inspired by [Typer](https://typer.tiangolo.com/), but with more **scalability**, **middleware**, and **async-first design**.

If Typer is FastAPI for the CLI, **Sayer is FastAPI++ for serious CLI tools**.

---

### ✅ Why Sayer?

| Feature                           | Typer      | Sayer ✅       |
| --------------------------------- | ---------- | ------------- |
| Type hint–based commands          | ✅          | ✅             |
| Async-native execution            | ⚠️ Basic   | ✅ First-class |
| Middleware & Interceptors         | ❌          | ✅             |
| Modular & scalable apps           | ⚠️ Clunky  | ✅ Clean       |
| Command aliases                   | ❌          | ✅             |
| CLI UI with `rich`                | ⚠️ Partial | ✅ Native      |
| Dynamic command discovery         | ❌          | ✅             |
| Testing support (CLI test client) | ❌          | ✅             |

---

### 🧪 Example

```python
from sayer import command, run


@command
def hello(name: str, loud: bool = False):
    """Say hello to someone."""
    message = f"Hello, {name}!"
    print(message.upper() if loud else message)


if __name__ == "__main__":
    run()
```

```bash
$ python hello.py hello Alice
Hello, Alice!

$ python hello.py hello Alice true
HELLO, ALICE!
```

---

### 🔥 Highlights

* 🧠 **Type-hint based** CLI definition
* 🕹️ **Interactive help** auto-generated from code
* 🧩 **Middleware system** for context, logging, auth
* 🌐 **Async-first**, built for concurrency
* 🧪 **Testable** with CLI test client
* 🎨 **Rich-powered output** out of the box
* 📁 **Modular command discovery** and grouping
* ⚡ **Lightning-fast DX**

---

### 🧰 Perfect For:

* Developer tools
* Task runners
* Build systems
* Automation scripts
* CLI-based microservices
* Anything that grows beyond a single script

---

Would you like me to push this as `README.md` content in `docs_src/index.md` or just keep iterating for now?
