# How-to: Use Parameters

## Goal

Select the right parameter type for each input source.

## Quick Matrix

| Need | Use |
| --- | --- |
| Optional flag like `--verbose` | `Option` |
| Positional input like `file_path` | `Argument` |
| Environment fallback like `API_TOKEN` | `Env` |
| Structured JSON payload | `JsonParam` |

## Example

```python
from typing import Annotated
from sayer import Option, Argument, Env, JsonParam


@app.command()
def deploy(
    service: Annotated[str, Argument(help="Service name")],
    region: Annotated[str, Option("eu-west-1")],
    token: Annotated[str, Env("API_TOKEN")],
    metadata: Annotated[dict, JsonParam()],
):
    ...
```

## Validation Tips

- Put required business inputs in `Argument` or required `Option`.
- Use `Env` for secrets and CI environments.
- Keep JSON inputs small and schema-like.

## Related

- [Concepts: Parameter System](../concepts/parameter-system.md)
- [Feature Guide: Parameters](../features/params.md)
- [API Reference: Params](../api-reference/params.md)
