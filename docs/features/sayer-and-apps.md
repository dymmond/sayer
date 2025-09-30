# Sayer and Sub-apps

This guide offers an exhaustive, richly annotated explanation of Sayer's **Sayer app system**, including main applications, sub-applications, command mounting, and advanced usage.

## Overview

Sayer's CLI framework is built around the **Sayer app**, a container for commands, callbacks, and middleware.

Sub-apps enable modular design by nesting independent Sayer applications within a parent app, allowing reusable logic,
dynamic structures, and clear separation of concerns.

## Key Concepts

* **Sayer App (`Sayer`)**: Represents a root CLI application.
* **Subapp**: A nested Sayer app mounted under a parent's namespace.
* **add.sayer()**: Method to mount a sub-app, including its commands and callback logic.
* **Command Resolution**: Sayer resolves commands hierarchically from the parent to sub-apps.
* **Middleware Integration**: Sub-apps can define their own middleware and callbacks.

## Creating a Sayer App

```python
from sayer import Sayer

app = Sayer(help="Main CLI App")

@app.command()
def greet():
    return "Hello!"
```

**Why**: The `Sayer` instance initializes the CLI, registering commands and global options.
**How**: `@command()` registers `greet` as a top-level command.

## Adding Sub-apps

```python
from sayer import Sayer

sub_app = Sayer(help="Subapp CLI")

@sub-app.command()
def sub_hello():
    return "Hello from sub-app!"

app.add_sayer("sub", sub_app)
```

**Why**: This modularizes commands, encapsulating them under `sub` namespace.
**How**: `add_sayer("sub", sub-app)` mounts `sub-app`'s commands as `sub sub_hello`.

## Combining Middleware and Sub-apps

```python
from sayer.middleware import register

register("audit", before=[lambda n,a: print(f"[Audit] {n}")])

app.add_sayer("nested", sub_app, middleware=["audit"])
```

**Why**: Sub-apps can have their own middleware or callbacks.
**How**: Middleware like `audit` runs before/after sub-app commands.

## Controlling Execution Flow

* **Hierarchical Resolution**: Commands are resolved from the parent down to sub-apps.
* **Callback Isolation**: Each Sayer app can have a callback, only affecting its own commands.
* **Scoped Middleware**: Middleware in sub-apps only applies to their scope.

## Complex Example: Nested Apps

```python
from sayer import Sayer

main = Sayer(help="Main App")
admin = Sayer(help="Admin Subapp")
reports = Sayer(help="Reports Subapp")

@main.command()
def home():
    return "Home command"

@admin.command()
def manage():
    return "Admin management"

@reports.command()
def summary():
    return "Report summary"

main.add_sayer("admin", admin)
admin.add_sayer("reports", reports)
```

**Why**: Supports deeply nested CLIs for complex projects.
**How**: Commands are invoked as `admin reports summary`.

## Dynamic Subapp Loading

```python
from sayer import Sayer
from sayer.utils.loader import load_commands_from

reports_app = Sayer()

load_commands_from("myproject.reports.commands")
main.add_sayer("reports", reports_app)
```

**Why**: Dynamically discovers and registers commands from modules.
**How**: `load_commands_from` scans modules and auto-registers commands.

## Best Practices

* ✅ Use sub-apps to modularize large CLIs.
* ✅ Keep each sub-app self-contained with its own commands and middleware.
* ✅ Clearly define app and sub-app help strings.
* ✅ Isolate callbacks and global state to their app.
* ❌ Avoid cross-app state dependencies.
* ❌ Don't overload the root app with excessive sub-apps; structure them logically.

## Conclusion

Sayer's app and sub-app system enables scalable, modular CLI architectures. Mastery of this system allows developers to build flexible, maintainable command-line applications.
