# Parameter System

Sayer translates annotated Python function signatures into Click parameters and typed runtime values.

## Mental Model

- Declaration layer: Python signature + metadata (`Option`, `Argument`, `Env`, `JsonParam`).
- Parsing layer: Click options/arguments.
- Conversion layer: type coercion and JSON molding.
- Invocation layer: bound arguments passed to your command function.

## Data Flow

```mermaid
flowchart TD
  Args[argv and env vars] --> Parse[Click parsing]
  Parse --> Meta[Parameter metadata resolution]
  Meta --> Convert[Type conversion]
  Meta --> Json[JSON decode and apply_structure]
  Convert --> Bind[Bound arguments map]
  Json --> Bind
  Bind --> Inject[Context and State injection]
  Inject --> Execute[Command execution]
  Execute --> Result[Output and return value]
```

## Parameter Selection

- `Option`: named values (`--region eu-west-1`).
- `Argument`: positional values (`deploy billing`).
- `Env`: environment-provided values (`API_TOKEN`).
- `JsonParam`: structured JSON payloads.

## Related

- [How-to: Use Parameters](../how-to/use-parameters.md)
- [Feature Guide: Parameters](../features/params.md)
- [API Reference: Params](../api-reference/params.md)
