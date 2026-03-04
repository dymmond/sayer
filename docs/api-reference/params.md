# Params API Reference

Reference for `sayer/params.py`.

## `Option`

Represents named CLI options (e.g. `--region`, `--verbose`).

### Key constructor parameters

- `default`
- `*param_decls`
- `help`
- `envvar`
- `required`
- `default_factory`
- `is_flag`
- `expose_value`

## `Argument`

Represents positional CLI arguments.

### Key constructor parameters

- `default`
- `*param_decls`
- `help`
- `required`
- `default_factory`
- `expose_value`

## `Env`

Represents environment-backed parameters.

### Key constructor parameters

- `envvar`
- `default`
- `required`
- `default_factory`
- `expose_value`

## `Param`

Generic metadata type that can be normalized to `Option` (`Param.as_option()`) when option-style behavior is implied.

## `JsonParam`

Specialized metadata indicating JSON input that should be decoded and molded into annotated target type.

## Usage Example

```python
from typing import Annotated
from sayer import Option, Argument, Env, JsonParam


@app.command()
def deploy(
    service: Annotated[str, Argument()],
    region: Annotated[str, Option("eu-west-1")],
    token: Annotated[str, Env("API_TOKEN")],
    config: Annotated[dict, JsonParam()],
):
    ...
```

## Related

- [Concepts: Parameter System](../concepts/parameter-system.md)
- [How-to: Use Parameters](../how-to/use-parameters.md)
- [Feature Guide: Parameters](../features/params.md)
