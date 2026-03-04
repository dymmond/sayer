# How-to: Add a Command

## Goal

Add a new command with typed options and help text.

## Steps

1. Define command on your app.

```python
from sayer import Sayer, Option

app = Sayer()


@app.command()
def sync_users(limit: int = Option(100, help="Maximum users to sync")):
    print(f"Syncing {limit} users")
```

2. Run it.

```bash
python app.py sync-users --limit 200
```

3. Verify help.

```bash
python app.py sync-users --help
```

## Notes

- Command names default to kebab-case from function names.
- Prefer explicit `help=` for every user-facing parameter.

## Related

- [Concepts: Parameter System](../concepts/parameter-system.md)
- [API Reference: `command`](../api-reference/core/engine.md)
