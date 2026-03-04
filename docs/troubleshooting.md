# Troubleshooting

## Command not found

Cause:
- command module not imported, so decorators never registered

Fix:
- ensure the module is imported at startup
- or call `load_commands_from("your_package.commands")`

## Required option reported as missing

Cause:
- option defined as required and no CLI value/env/default is available

Fix:
- provide the option explicitly
- or define `default`, `default_factory`, or `Env` fallback

## JSON parameter parsing errors

Cause:
- invalid JSON string
- mismatched target type

Fix:
- validate JSON before passing to CLI
- keep payload schema aligned with annotated type

## Async command behavior is unexpected

Cause:
- mixed sync/async flows around command calls

Fix:
- keep command as `async def` and let Sayer handle execution
- avoid manually running event loops inside commands

## Middleware not running

Cause:
- middleware not registered before command decoration
- hook signature mismatch

Fix:
- call `register(...)` before command definition
- use valid signatures: `(name, args)` or `(name, args, result)`

## Related

- [Concepts: Command Lifecycle](./concepts/command-lifecycle.md)
- [Concepts: Middleware Model](./concepts/middleware-model.md)
- [Feature Guide: Testing](./features/testing.md)
