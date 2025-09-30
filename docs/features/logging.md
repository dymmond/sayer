# Logging

Sayer provides a lightweight but powerful logging system that supports:

- Lazy and safe logger initialization
- Pluggable logging backends via `LoggerProtocol`
- Configuration using `Settings`
- Rich or standard terminal output
- Thread-safe logger proxy

This document covers how Sayer handles logging internally and how you can customize it.

---

## 🧠 Core Concepts

Sayer uses a **proxy-based design** for logging:

- You access `sayer.logging.logger` anywhere in your app
- Internally, this is a `LoggerProxy` — a thread-safe wrapper
- At runtime, the proxy is bound to a concrete logger (like `StandardLoggingConfig`) using `bind_logger(...)`
- Logging is controlled through the `settings.logging_level`

---

## 🔧 How to Use It

### Basic Usage

```python
from sayer.logging import logger

logger.info("This is an info message")
logger.warning("Watch out!")
logger.debug("Debugging details")
```

No setup required if your app uses `Sayer()` or `sayer.core.client.run()`, since logging is automatically configured.

---

## 🛠 Logging Setup Flow

Logging is initialized through:

```python
from sayer.logging import setup_logging
setup_logging(settings)
```

You normally don't need to call this manually — Sayer handles it on startup.

---

## 🔧 Configuration via Settings

Logging behavior is configured using the active [settings](./settings.md) object.

Key fields:

| Field              | Type     | Description                                                       |
| ------------------ | -------- | ----------------------------------------------------------------- |
| `logging_level`    | `str`    | One of: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` |
| `is_logging_setup` | `bool`   | Prevents double-initialization                                    |
| `logging_config`   | property | Returns a `LoggingConfig` instance                                |

---

## 🎨 Output Styles

Sayer defaults to using **Rich** for colorful, formatted terminal logs.

Example:

```bash
[INFO] Starting app
[ERROR] Something went wrong
```

You can override the logging backend by setting a custom `LoggingConfig`:

```python
from sayer.logging import logger
from sayer.core.logging import StandardLoggingConfig

settings.logging_config = StandardLoggingConfig(level="DEBUG")
logger.info("Using custom backend")
```

---

## 🧪 Testing Logging

In test mode, you can mock or replace the logger entirely:

```python
from sayer.logging import logger

logger.bind_logger(None)  # Disable
```

Or inject a test-specific logger that captures logs for assertions.

---

## 📦 LoggingProtocol

All loggers must implement `LoggerProtocol`, which includes:

```python
class LoggerProtocol(Protocol):
    def info(self, msg: str): ...
    def debug(self, msg: str): ...
    def warning(self, msg: str): ...
    def error(self, msg: str): ...
    def critical(self, msg: str): ...
```

You can build and bind your own structured logger like Loguru, structlog, etc.

---

## 🧰 Recap

| Feature             | Supported |
| ------------------- | --------- |
| Proxy logger access | ✅         |
| Rich logging output | ✅         |
| Standard fallback   | ✅         |
| Pluggable config    | ✅         |
| Settings-integrated | ✅         |
| Thread-safe access  | ✅         |

Logging in Sayer is **ready to use, safe by default, and fully extensible**.

---
