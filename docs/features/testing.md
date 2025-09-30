# Testing

This guide thoroughly explains Sayer's testing system, covering setup, usage, and advanced examples.

## Overview

Sayer includes testing utilities that make it easy to simulate CLI interactions and validate outputs. The core is `SayerTestClient`,
which extends `click.testing.CliRunner` with Sayer-specific features.

## Setup

```bash
pip install pytest
```

**Why**: `pytest` is used for discovery and running tests.

## SayerTestClient Basics

```python
from sayer.testing import SayerTestClient

client = SayerTestClient()
```

**Why**: Initializes a test client for CLI interaction.
**How**: Wraps `CliRunner` and links to the global or custom app.

### Basic Command Testing

```python
def test_hello():
    result = client.invoke(["hello", "--name", "Ada"])
    assert result.exit_code == 0
    assert "Hello, Ada" in result.output
```

**Why**: Tests command execution and output.
**How**: Calls the CLI with arguments, checks output and exit code.

### Simulating Input

```python
result = client.invoke(["upload"], input="file contents\n")
```

**Why**: Simulates user input for interactive commands.

### SayerTestResult Attributes

```python
result = client.invoke(["hello", "--name", "Alan"])

print(result.exit_code)  # 0
print(result.output)     # Command output
```

| Attribute  | Description                           |
| ---------- | ------------------------------------- |
| exit\_code | Command exit status                   |
| output     | Stdout and stderr combined            |
| stdout     | Standard output                       |
| stderr     | Standard error                        |
| exception  | Any exception raised during execution |

## Environment and Working Directory

```python
result = client.invoke(["env-read"], env={"MY_VAR": "123"})
result = client.invoke(["whoami"], cwd="/tmp/test-env")
```

**Why**: Sets environment or working directory for the command.

## Complete Example

```python
from sayer.testing import SayerTestClient

def test_verbose():
    result = SayerTestClient().invoke(["diagnose", "--debug"])
    assert "Debug mode enabled" in result.output
    assert result.exit_code == 0
```

**Why**: Full test showing command, output check, and exit validation.

## Best Practices

✅ Use `invoke` to simulate CLI calls.
✅ Use `input` to test interactive commands.
✅ Set `env` for environment simulation.
✅ Use `cwd` to control test context.
✅ Clean up state between tests.

## Custom App Testing

```python
from myproject.cli import app

client = SayerTestClient(app=app)
```

**Why**: Tests a specific app instead of the default.
**How**: Provides full control over the tested CLI.

## Recap Table

| Feature          | Usage                         |
| ---------------- | ----------------------------- |
| Basic Invocation | `client.invoke(["cmd", ...])` |
| Input Simulation | `input="..."`                 |
| Env Simulation   | `env={"KEY": "value"}`        |
| Output Checking  | `result.output`, `exit_code`  |
| CWD Override     | `cwd="/path/to/dir"`          |

## Conclusion

Sayer's testing utilities simplify comprehensive CLI tests, letting you control inputs, environments, and verify outputs for robust command validation.
