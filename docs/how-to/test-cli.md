# How-to: Test CLI Behavior

## Goal

Test output, exit codes, and return values.

## Basic test

```python
from sayer.testing import SayerTestClient
from myproject.main import app


def test_hello():
    client = SayerTestClient(app=app)
    result = client.invoke(["hello", "--name", "Ada"])
    assert result.exit_code == 0
    assert "Hello, Ada" in result.output
```

## Return value assertions

```python
result = client.invoke(["compute"], with_return_value=True)
assert result.return_value == {"ok": True}
```

## Environment and cwd

```python
result = client.invoke(["whoami"], env={"USER": "ci"}, cwd="/tmp")
```

## Related

- [Feature Guide: Testing](../features/testing.md)
- [Tutorial 3](../tutorials/03-state-middleware-testing.md)
- [Troubleshooting](../troubleshooting.md)
