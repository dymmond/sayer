# Core Commands API Reference

Reference for `sayer/core/commands/base.py` and `sayer/core/commands/sayer.py`.

## `BaseSayerCommand`

Abstract base command that extends `click.Command` and defines:

- `get_help(ctx)` (abstract)
- `invoke(ctx)` override that stores return values (`ctx._sayer_return_value`)

## `SayerCommand`

Concrete command class used by Sayer to render enhanced help and preserve command result behavior.

## Why It Matters

- Return values are available to testing client wrappers.
- Help rendering is consistently routed through Sayer's formatter.

## Related

- [API Reference: Core Engine](./engine.md)
- [Feature Guide: Commands](../../features/commands.md)
