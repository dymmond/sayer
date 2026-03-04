# Core Groups API Reference

Reference for `sayer/core/groups/base.py` and `sayer/core/groups/sayer.py`.

## `SayerGroup`

`click.Group` extension responsible for Sayer-style help rendering and group behavior.

### Key behavior

- Overrides `format_help(...)` and delegates to `render_help`.
- Works with Sayer command wrappers to provide rich command listings.

## Group Integration

Groups created through `sayer.group(...)` are registered in the engine registry and can be mounted into apps with `app.add_command(...)`.

## Related

- [Feature Guide: Groups](../../features/groups.md)
- [How-to: Organize Groups and Sub-apps](../../how-to/organize-groups-subapps.md)
- [API Reference: Core Engine](./engine.md)
