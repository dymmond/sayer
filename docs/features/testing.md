# Testing

Sayer comes with built-in tools to make testing your CLI commands easy, robust, and expressive. Testing in Sayer is based on `pytest`
and the `click.testing.CliRunner` under the hood — but enhanced with Sayer-specific helpers like `SayerTestClient`.

---

## 🔧 Test Setup

To get started, install test dependencies (if not already in your project):

```bash
pip install pytest
```

Sayer automatically supports all `pytest`-based test discovery and CLI tests.

---

## 🚀 `SayerTestClient`

Sayer provides a lightweight wrapper around `CliRunner` to simplify CLI testing:

```python
from sayer.testing import SayerTestClient

client = SayerTestClient()
```

### ✅ Basic Usage

```python
def test_hello_command():
    result = SayerTestClient().invoke(["hello", "--name", "Ada"])
    assert result.exit_code == 0
    assert "Hello, Ada" in result.output
```

You can simulate input:

```python
result = client.invoke(["upload"], input="file contents\n")
```

---

## 📦 `SayerTestResult`

The result returned by `invoke(...)` is a `SayerTestResult`:

```python
result = client.invoke(["hello", "--name", "Alan"])
print(result.exit_code)
print(result.output)
```

### Available Attributes:

| Attribute   | Description                                |
| ----------- | ------------------------------------------ |
| `exit_code` | Integer exit code of the command           |
| `output`    | Combined stdout and stderr (raw)           |
| `stdout`    | Standard output (usually same as `output`) |
| `stderr`    | Captured standard error                    |
| `exception` | Any raised exception (if not handled)      |

---

## 🌍 Environment and CWD

You can override environment variables:

```python
result = client.invoke(["env-read"], env={"MY_VAR": "123"})
```

Or simulate a different working directory:

```python
result = client.invoke(["whoami"], cwd="/tmp/test-env")
```

---

## 🧪 Example Test

```python
from sayer.testing import SayerTestClient

def test_verbose_output():
    result = SayerTestClient().invoke(["diagnose", "--debug"])
    assert "Debug mode enabled" in result.output
    assert result.exit_code == 0
```

---

## 🧠 Best Practices

* 🧪 Use `SayerTestClient().invoke([...])` for simulating command-line execution
* 📥 Use `input="..."` to test interactive commands
* 🧪 Use `env={"VAR": "value"}` to simulate configuration
* 🧼 Clean up or isolate state between tests to avoid leakage

---

## 🔍 Advanced: Accessing the CLI App

By default, `SayerTestClient()` uses the global CLI instance from `sayer.core.client`.

If you want to test a custom app:

```python
from myproject.cli import app

client = SayerTestClient(app=app)
```

---

## 🧰 Recap

| Feature                | Usage                         |
| ---------------------- | ----------------------------- |
| Basic CLI invocation   | `client.invoke(["cmd", ...])` |
| Input piping           | `input="..."`                 |
| Environment simulation | `env={"KEY": "value"}`        |
| Output assertions      | `result.output`, `exit_code`  |
| CWD override           | `cwd="/path/to/dir"`          |

---

Sayer’s testing utilities make it easy to simulate real-world CLI interactions with full control over input, environment, and assertions.
