# Settings and Configuration

Sayer provides a built-in way to configure your CLI application using **centralized settings**, powered by the `SAYER_SETTINGS_MODULE` environment variable.

This mechanism lets you:

- Keep config logic out of command code
- Load settings dynamically
- Easily override settings in dev, test, and prod environments

## ⚙️ Default Settings Class

Sayer includes a built-in `Settings` dataclass that defines the default configuration used when no `SAYER_SETTINGS_MODULE` is set,
or when internal tools need immediate settings access.

This class covers:

- Debug mode and logging
- Output color systems
- Version tagging
- Serialization utilities

---

### 📦 Location

```python
from sayer.conf.settings import Settings
```

This is not to be confused with your application-level settings — it is used internally and as a base for custom configurations.

---

## 🧾 Default Fields

| Field                 | Type                                  | Description                                                                                    |
|-----------------------| ------------------------------------- |------------------------------------------------------------------------------------------------|
| `debug`               | `bool`                                | Enables debug mode (more logging, errors)                                                      |
| `logging_level`       | `str`                                 | Logging threshold (`DEBUG`, `INFO`, etc.)                                                      |
| `version`             | `str`                                 | Version of the Sayer library (auto-filled)                                                     |
| `is_logging_setup`    | `bool`                                | Tracks if logging has already been configured                                                  |
| `force_terminal`      | `bool | None`                                                                                          | Force terminal output regardless of environment |
| `color_system`        | `"auto" | "standard"                                                                                     | "256" | ...`    | Controls terminal color profile                 |
| `display_full_help`   | `bool`                                | Flag indicating the the display of each command must be diplayed in full                       |
| `display_help_length` | `int`                                 | The length of the help if `display_full_help` is set to False. Defaults to 99                  |
| `formatter_class`     | `RichHelpFormatter`                   | The formatter used to render the Sayer Rich UI. This can be overridden by any custom renderer. |

---

### 🎛️ Field Examples

```python
settings.debug = True
settings.logging_level = "DEBUG"
settings.force_terminal = True
settings.color_system = "256"
```

---

### 🧠 `logging_config` Property

This is a dynamic property that returns a `LoggingConfig` object based on the current logging level.

```python
config = settings.logging_config
```

Sayer uses this internally to configure rich/standard logging output. You can override it:

```python
from sayer.logging import CustomLoggingConfig

settings.logging_config = CustomLoggingConfig(level="DEBUG")
```

---

### 🔄 Converting to Dict or Tuples

The `Settings` class provides two helpers to introspect or export the config:

### `dict(...)`

```python
settings.dict(exclude_none=True, upper=True)
```

**Args:**

* `exclude_none`: Omit fields with `None` values
* `upper`: Transform keys to uppercase (useful for env-like exports)

Returns:

```python
{
  "DEBUG": True,
  "LOGGING_LEVEL": "INFO",
  ...
}
```

### `tuple(...)`

```python
settings.tuple(exclude_none=True, upper=False)
```

Returns:

```python
[("debug", True), ("logging_level", "INFO"), ...]
```

Useful for exporting to `.env` files or logging config introspection.

---

### 🧰 Internal Use

The `Settings` class is primarily used:

* As the fallback configuration if `SAYER_SETTINGS_MODULE` is not defined
* By components like `sayer.logging` and `rich` terminal integration
* To bootstrap internal state when settings aren't user-defined

---

### 🧪 Customizing in Tests

You can use it in test environments or override fields dynamically:

```python
from sayer.conf.global_settings import Settings

s = Settings(debug=True, logging_level="DEBUG")
print(s.dict())
```

---

### 🧬 Summary

| Feature                    | Supported |
| -------------------------- | --------- |
| Built-in debug mode        | ✅         |
| Color and terminal control | ✅         |
| Logging abstraction        | ✅         |
| Dict export                | ✅         |
| Tuple export               | ✅         |
| Used in fallback mode      | ✅         |

This class is the **core config contract** Sayer uses internally — you can use it as a reference to build more advanced or environment-specific config systems.

---

## 📦 How It Works

At runtime, Sayer looks for the environment variable:

```

SAYER_SETTINGS_MODULE=your_project.settings.Dev

```

It will:

1. Import the specified module
2. Access the specified class (e.g., `Dev`)
3. Instantiate and expose it as `settings` anywhere you need

---

## 🧠 Anatomy of a Settings Module

```python
# your_project/settings.py
from sayer.conf.global_settings import BaseSettings

class Base(BaseSettings):
    debug = False
    retries = 3

class Dev(Base):
    debug = True
    retries = 10
```

---

## 🚀 Setting the Module

You must set the environment variable **before launching the CLI**:

```bash
export SAYER_SETTINGS_MODULE=your_project.settings.Dev
python app.py my-command
```

You can also set it inline:

```bash
SAYER_SETTINGS_MODULE=your_project.settings.Dev python app.py my-command
```

---

## 🧪 Accessing Settings in Commands

```python
from sayer.conf import settings

@command()
def show():
    print("Debug mode:", settings.debug)
```

No need to pass it explicitly — it's global, and lazily loaded on first access.

---

## 🧰 Settings Best Practices

### 1. Split environments:

```python
# settings.py
from dataclasses import dataclass
from sayer.conf.global_settings import BaseSettings

class Base(BaseSettings):
    retries = 3

class Dev(Base):
    debug = True

class Prod(Base):
    debug = False
    retries = 1
```

Use different envs like:

```bash
SAYER_SETTINGS_MODULE=myapp.settings.Dev
```

---

### 2. Type Your Settings

Sayer doesn't enforce typing but it's recommended:

```python
class Dev:
    debug: bool = True
    retries: int = 3
```

You can combine this with Pydantic, attrs, or msgspec for stricter validation if desired.

---

## 🧪 Overriding Settings in Tests

Tests that rely on settings should override the environment variable or monkey-patch `sayer.conf.settings`.

Example:

```python
import os
from sayer.conf import settings

def test_behavior(monkeypatch):
    monkeypatch.setenv("SAYER_SETTINGS_MODULE", "tests.fake_settings.Mocked")
    assert settings.debug is True
```

Or if `settings` is already imported:

```python
settings.debug = True  # override directly for testing
```

---

## 🧠 Under the Hood

If `SAYER_SETTINGS_MODULE` is unset, it will use the internal by default or if invalid, Sayer will raise a helpful exception.

---

## 🧰 Recap

| Feature                 | Description                                |
| ----------------------- | ------------------------------------------ |
| `SAYER_SETTINGS_MODULE` | Points to your settings class              |
| `settings`              | Auto-loaded global settings object         |
| Lazy loading            | Only instantiated when accessed            |
| Nested inheritance      | Use `Base`, `Dev`, `Prod` hierarchies      |
| Test override           | Patch env var or mutate `settings` in test |

---

## ✅ Example Project Structure

```
myapp/
├── settings.py
│   ├── class Base
│   ├── class Dev(Base)
│   └── class Prod(Base)
├── commands.py
└── main.py
```

Set it:

```bash
export SAYER_SETTINGS_MODULE=myapp.settings.Dev
```

Access it:

```python
from sayer.conf import settings
print(settings.retries)
```

---

👉 Next: [Commands](./commands.md)
