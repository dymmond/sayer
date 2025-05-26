---
hide:
  - navigation
---

## 0.2.2

### Fixed

- When using `from __future__ import annotations` this was not parsing the annotations correctly.

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
