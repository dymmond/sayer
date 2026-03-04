# How-to: Organize Groups and Sub-apps

## Goal

Split a growing CLI into clear domains.

## Pattern

```python
from sayer import Sayer, group

app = Sayer(name="mycli")
users = group("users", help="User operations")
projects = group("projects", help="Project operations")


@users.command()
def list_users():
    print("listing users")


@projects.command()
def list_projects():
    print("listing projects")


app.add_command(users)
app.add_command(projects)
```

## Invocation

```bash
python app.py users list-users
python app.py projects list-projects
```

## Decision Guide

- Use groups for related commands in one app.
- Use sub-app mounting when modules should stay independently maintainable.

## Related

- [Concepts: Architecture](../concepts/architecture.md)
- [Feature Guide: Sayer and Sub-apps](../features/sayer-and-apps.md)
