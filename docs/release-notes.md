---
hide:
  - navigation
---

## 0.4.1

### Fixed

- Error when parsing Boolean values from environment variables.
- Fixed error when Boolean values are parsed from environment variables.

## 0.4.0

### Changed

In the past, Sayer was using `dataclass` to manage all the settings but we found out that can be a bit cumbersome for a lot
of people that are more used to slightly cleaner interfaces and therefore, the internal API was updated to stop using `@dataclass` and
use directly a typed `Settings` object.

- Replace `Settings` to stop using `@dataclass` and start using direct objects instead.

**Example before**

```python
from dataclasses import dataclass, field
from sayer.conf.global_settings import Settings


@dataclass
class MyCustomSettings(Settings):
    hosts: list[str] = field(default_factory=lambda: ["example.com"])
```

**Example after**

```python
from sayer.conf.global_settings import Settings


class MyCustomSettings(Settings):
    hosts: list[str] = ["example.com"]
```

This makes the code cleaner and readable.

## 0.3.4

### Fixed

- Displaying the Arguments in the help of subcommands.

## 0.3.3

!!! Note
    Version 0.3.2 had issues and it was skipped

### Changed

- Add `get_help` and `format_help` directly via Sayer instance.
- Add support to markup, emoji and styles in the default console.

## 0.3.1

### Changed

- Make the UI help display cleaner and simpler.

## 0.3.0

### Added

* **BaseSayerCommand**: Introduced a new base class for commands, `BaseSayerCommand`,
which provides a more structured way to define commands and allows for easier extension of command functionality.
* **BaseSayerGroup**: Introduced a new base class for groups, `BaseSayerGroup`.
* `override_help_text`: A new parameter for the `add_app` and `add_sayer` decorator that allows you to override the help text for a command, providing more flexibility in how commands are documented.

### Changed

- **SayerCommand**: Now inherits from `BaseSayerCommand`, this brings some structure and allows an easier way to extend the command
functionality.
- **SayerGroup**: Now inherits from `BaseSayerGroup`, this brings some structure and allows an easier way to extend the group.
- To check the version, you can use `-v` instead of `-V`.

## 0.2.7

### Fixed

- `Argument` was not declaring the *param_decls properly and the required display was not accurate.

## 0.2.6

### Fixed

- `nargs` detection and default.

## 0.2.5

### Added

- `display_full_help` and `display_help_length` in the settings and `SayerGroup` allowing to specifify if the help
of commands/subcommands must be displayed in full.

## 0.2.4

### Added

- Custom typing overrides making sure you can specify your own typing for the `@command` decorator.
- `SayerCommand` now supports all the parameters of `click.Command`, allowing for more flexibility in command definitions when `app.add_command` is used.

### Fixed

- Help text for arguments was not being displayed correctly when using the `@command` decorator.
- `@command` decorator was not wrapping the decorator properly and loosing critical information for type checking and for type hints.

## 0.2.3

This was missed from the version 0.2.2 and it should have been included.

### Changed

- Postpone Annotations and Type Hints: The `@command` decorator now postpones annotations and type
hints until the command is executed, allowing for more dynamic behavior and flexibility in command definitions.

###

## 0.2.2

### Added

- **Positional & Keyword Naming**: `@command` now accepts a first-positional string or name= kwarg to override CLI names without affecting signature introspection.
- **Kebab-case Defaults**: Functions named in snake_case are automatically converted to kebab-case CLI commands by default.
- **Click Attr Forwarding**: All extra Click attributes (hidden, short_help, short_help, etc.) passed to @command are forwarded directly into @click.command(...).
- **Enhanced add_command**: `Sayer.add_command` now distinguishes between Sayer instances (unwrap → SayerGroup), any click.Group (mounted as-is),
and leaf commands (wrapped in SayerCommand).

### Fixed

- When using `from __future__ import annotations` this was not parsing the annotations correctly.
- Union types were not being parsed correctly.
- Argument conflicts were not being handled properly.
- **Nested Sub-app Support**: Sub-apps maintain their nested commands and rich help panels when mounted under a root app.

### Changed

- **Error Handling**: Eliminated AttributeError when using string-based names in @command.

## 0.2.1

### Added

- Pass custom context and context class into a Sayer app.
- Callback integration for easy use.
- Invoke without command on a Sayer level.
- Parameter declarations for Option and display

### Fixed

- Wrapping Sayer apps it was not adding the native SayerGroup.
- SayerGroup and command split.
- Display of help messages was not properly tested.

## 0.2.0

### Fixed

- Fixed async middleware order `before` and `after` execution.

## 0.1.0 – First Release

We're proud to announce the **first official release of Sayer**, a modern,
async-native Python CLI framework designed for maintainability, scalability, and expressiveness.

No more glue scripts. No more boilerplate. Just clean commands, smart params, and CLI magic out-of-the-box.

---

### ✅ Decorator-Based Command System
- `@app.command()` and `@command()` support
- Command nesting, grouping, and docstring-based help
- Supports both sync and async commands

### 🎛️ Parameter System
- Rich typing with `Option`, `Argument`, and `Env`
- `Annotated` support for combining types and metadata
- Flag handling, lists, enums, and more

### 🔌 Middleware
- Global and named middleware hooks
- Before/after execution
- `args` injection and abort support
- Perfect for logging, validation, and feature toggling

### 🧠 State Injection
- Class-based singleton state via `State` protocol
- Automatic injection into commands
- Great for sharing config, DB handles, etc.

### 🪵 Logging
- `logger` proxy with Rich integration
- Auto-configured via `settings.logging_level`
- Fully pluggable backend

### 📦 Configuration System
- `SAYER_SETTINGS_MODULE` environment var
- Class-based settings with inheritance
- Rich features like dict/tuple export

### 🔄 Encoders
- Automatic JSON-to-object parsing via `JsonParam`
- Fully pluggable and overridable

### 🧪 Testing Tools
- `SayerTestClient` based on `click.testing`
- Simulate CLI calls, inject env vars, assert output
- Test-ready out-of-the-box

### 🧰 CLI Features
- Built-in `sayer new` for scaffolding a CLI project
- Built-in `sayer docs generate` to export docs to Markdown
- Clean terminal output via `echo`, `success`, `warning`, `error`

---

## 📚 Documentation

Extensive documentation available, including:

- [Getting Started](https://sayer.dymmond.com)
- [Commands & Params](https://sayer.dymmond.com/features/commands/)
- [Encoders](https://sayer.dymmond.com/features/encoders/)
- [Testing](https://sayer.dymmond.com/testing/)
