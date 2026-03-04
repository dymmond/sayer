# State and Injection

Sayer supports dependency-style injection for:

- `click.Context`
- subclasses of `State`
- custom injection flows via custom group wrappers

## Injection Rules

- `click.Context` parameters receive the active Click context.
- `State` subclasses are instantiated and cached in command context.
- Other parameters are bound from parsed CLI inputs.

## When to Use `State`

- shared configuration loaded once
- runtime flags reused across commands
- shared client objects in one CLI session

## Common Pitfalls

- using mutable global module variables instead of injected state
- hiding required setup in callbacks instead of explicit state objects
- mixing unrelated dependencies in one state class

## Related

- [Feature Guide: Context Injection](../features/context-injection.md)
- [Feature Guide: State](../features/state.md)
- [Command Lifecycle](./command-lifecycle.md)
