# Global Settings

This document covers `sayer/conf/global_settings.py`, detailing the default settings available for Sayer.

## Settings Class

`Settings` is a dataclass providing the default configuration for Sayer.

### Fields

* **debug**: Enables debug mode. Default is `False`.
* **logging_level**: The logging level (e.g., `INFO`, `DEBUG`). Default is `INFO`.
* **version**: The application version.
* **force_terminal**: Force terminal output even when redirected. Default is `False`.
* **color_system**: Terminal color system (e.g., `auto`, `standard`, `256`, `truecolor`).
* **display_full_help**: Controls whether to display the full help text for commands.
* **display_help_length**: Specifies the maximum length of help text lines if `display_full_help` is False.

### Logging Configuration

* **logging_config**: Generates a `StandardLoggingConfig` with dynamic settings.

### Serialization Methods

* `as_dict()`: Serializes the settings into a dictionary.
* `as_tuple()`: Serializes the settings into a tuple.

## Example

```python
from sayer.conf.global_settings import Settings

s = Settings(debug=True)
print(s.as_dict())
```

## Best Practices

* ✅ Use `as_dict()` for exporting settings, e.g., for diagnostic purposes.
* ✅ Rely on environment-specific settings for production use.
* ❌ Avoid hardcoding settings into your code.

## Related Modules

* [Settings](./settings.md)
* [Logging](../core/logging.md)
