# Middleware Model

Middleware in Sayer adds before/after hooks around command execution.

## Execution Order

```mermaid
flowchart TD
  Start --> GlobalBefore[Global before hooks]
  GlobalBefore --> NamedBefore[Named command hooks]
  NamedBefore --> Command[Command function]
  Command --> NamedAfter[Named command hooks]
  NamedAfter --> GlobalAfter[Global after hooks]
  GlobalAfter --> End
```

## Behavior Notes

- Hooks can be sync or async.
- Named middleware is resolved at command decoration time.
- Global middleware runs for every command.

## Design Guidance

- Use named middleware for domain concerns (audit, auth, telemetry).
- Keep hook signatures consistent (`(name, args)` and `(name, args, result)`).
- Avoid long-running blocking operations in hooks.

## Related

- [Feature Guide: Middleware](../features/middleware.md)
- [API Reference: Middleware](../api-reference/middleware.md)
- [Command Lifecycle](./command-lifecycle.md)
