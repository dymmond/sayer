from __future__ import annotations

import inspect
import os
from functools import cached_property
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from sayer.__version__ import __version__  # noqa

if TYPE_CHECKING:
    from sayer.logging import LoggingConfig


def safe_get_type_hints(cls: type) -> dict[str, Any]:
    """
    Safely get type hints for a class, handling potential errors.
    This function attempts to retrieve type hints for the given class,
    and if it fails, it prints a warning and returns the class annotations.
    Args:
        cls (type): The class to get type hints for.
    Returns:
        dict[str, Any]: A dictionary of type hints for the class.
    """
    try:
        return get_type_hints(cls, include_extras=True)
    except Exception:
        return cls.__annotations__


class BaseSettings:
    """
    Base of all the settings for any system.
    """

    __type_hints__: dict[str, Any] = None
    __truthy__: set[str] = {"true", "1", "yes", "on", "y"}

    def __init__(self, **kwargs: Any) -> None:
        """
        Initializes the settings by loading environment variables
        and casting them to the appropriate types.
        This method uses type hints from the class attributes to determine
        the expected types of the settings.
        It will look for environment variables with the same name as the class attributes,
        converted to uppercase, and cast them to the specified types.
        If an environment variable is not set, it will use the default value
        defined in the class attributes.
        """
        cls = self.__class__
        if cls.__type_hints__ is None:
            cls.__type_hints__ = safe_get_type_hints(cls)

        if kwargs:
            for key, value in kwargs.items():
                setattr(self, key, value)

        for key, typ in cls.__type_hints__.items():
            base_type = self._extract_base_type(typ)

            env_value = os.getenv(key.upper(), None)
            if env_value is not None:
                value = self._cast(env_value, base_type)
            else:
                value = getattr(self, key, None)
            setattr(self, key, value)

        # Call post_init if it exists
        self.post_init()

    def post_init(self) -> None:
        """
        Post-initialization method that can be overridden by subclasses.
        This method is called after all settings have been initialized.
        """
        ...

    def _extract_base_type(self, typ: Any) -> Any:
        origin = get_origin(typ)
        if origin is Annotated:
            return get_args(typ)[0]
        return typ

    def _cast(self, value: str, typ: type[Any]) -> Any:
        """
        Casts the value to the specified type.
        If the type is `bool`, it checks for common truthy values.
        Raises a ValueError if the value cannot be cast to the type.

        Args:
            value (str): The value to cast.
            typ (type): The type to cast the value to.
        Returns:
            Any: The casted value.
        Raises:
            ValueError: If the value cannot be cast to the specified type.
        """
        try:
            origin = get_origin(typ)
            if origin is Union or origin is UnionType:
                non_none_types = [t for t in get_args(typ) if t is not type(None)]
                if len(non_none_types) == 1:
                    typ = non_none_types[0]
                else:
                    raise ValueError(f"Cannot cast to ambiguous Union type: {typ}")

            if typ is bool or str(typ) == "bool" :
                return value.lower() in self.__truthy__
            return typ(value)
        except Exception:
            if get_origin(typ) is Union or get_origin(UnionType):
                type_name = " | ".join(t.__name__ if hasattr(t, "__name__") else str(t) for t in get_args(typ))
            else:
                type_name = getattr(typ, "__name__", str(typ))
            raise ValueError(f"Cannot cast value '{value}' to type '{type_name}'") from None

    def dict(
        self,
        exclude_none: bool = False,
        upper: bool = False,
        exclude: set[str] | None = None,
        include_properties: bool = False,
    ) -> dict[str, Any]:
        """
        Dumps all the settings into a python dictionary.
        """
        result = {}
        exclude = exclude or set()

        for key in self.__annotations__:
            if key in exclude:
                continue
            value = getattr(self, key, None)
            if exclude_none and value is None:
                continue
            result_key = key.upper() if upper else key
            result[result_key] = value

        if include_properties:
            for name, _ in inspect.getmembers(
                type(self),
                lambda o: isinstance(
                    o,
                    (property, cached_property),
                ),
            ):
                if name in exclude or name in self.__annotations__:
                    continue
                try:
                    value = getattr(self, name)
                    if exclude_none and value is None:
                        continue
                    result_key = name.upper() if upper else name
                    result[result_key] = value
                except Exception:
                    # Skip properties that raise errors
                    continue

        return result


class Settings(BaseSettings):
    """
    Defines a comprehensive set of configuration parameters for the Sayer library.

    This dataclass encapsulates various settings controlling core aspects of
    Sayer's behavior, including debugging modes, logging configuration.

    It provides a centralized place to manage and access
    these operational monkay.settings.
    """

    debug: bool = False
    """
    Enables debug mode if True.

    Debug mode may activate additional logging, detailed error reporting,
    and potentially other debugging features within the AsyncMQ system.
    Defaults to False.
    """

    logging_level: str = "INFO"
    """
    Specifies the minimum severity level for log messages to be processed.

    Standard logging levels include "DEBUG", "INFO", "WARNING", "ERROR",
    and "CRITICAL". This setting determines the verbosity of the application's
    logging output. Defaults to "INFO".
    """

    version: str = __version__
    """
    Stores the current version string of the AsyncMQ library.

    This attribute holds the version information as defined in the library's
    package metadata. It's read-only and primarily for informational purposes.
    """

    is_logging_setup: bool = False
    """
    Indicates whether the logging system has been initialized.

    This flag is used internally to track the setup status of the logging
    configuration and prevent repeated initialization. Defaults to False.
    """
    force_terminal: bool | None = None
    """
    Specifies whether to force terminal output.
    If set to True, the application will attempt to force terminal output
    regardless of the environment. If False, it will respect the environment's
    settings. If None, the application will use the default behavior.
    This setting is useful for controlling the output format in different
    environments, such as when running in a terminal or redirecting output
    to a file.
    """
    color_system: Literal["auto", "standard", "256", "truecolor", "windows"] = "auto"
    """
    Specifies the color system to use for terminal output.
    If set to "auto", the application will automatically detect the
    appropriate color system based on the terminal's capabilities. If set
    to a specific color system (e.g., "256", "16m"), the application will
    use that system for color output. This setting allows for customization
    of the color output in different environments, ensuring that the
    application can adapt to various terminal capabilities.
    """
    display_full_help: bool = False
    """
    Controls whether to display the full help text for commands.
    If set to True, the application will show detailed help information
    for commands, including descriptions, options, and usage examples.
    If set to False, it will provide a more concise help output. This setting
    is useful for controlling the verbosity of help messages, especially in
    environments where space is limited or when a more streamlined help
    output is desired.
    """
    display_help_length: int = 99
    """
    Specifies the maximum length of help text lines.
    This setting determines how long each line of help text will be
    before wrapping. If set to a specific integer value, the application
    will ensure that help text lines do not exceed this length, improving
    readability in terminal output. If set to 0, it will use the terminal's
    default width. This setting is particularly useful for ensuring that
    help messages are formatted correctly in different terminal sizes and
    environments.
    """
    __logging_config__: LoggingConfig | None = None

    @property
    def logging_config(self) -> "LoggingConfig" | None:
        """
        Provides the configured logging setup based on current monkay.settings.

        This property dynamically creates and returns an object that adheres
        to the `LoggingConfig` protocol, configured according to the
        `logging_level` attribute. It abstracts the specifics of the logging
        implementation.

        Returns:
            An instance implementing `LoggingConfig` with the specified
            logging level, or None if logging should not be configured
            (though the current implementation always returns a config).
        """
        # Import StandardLoggingConfig locally to avoid potential circular imports
        # if sayer.logging depends on sayer.conf.monkay.settings.
        from sayer.core.logging import StandardLoggingConfig

        if self.__logging_config__ is None:
            # Returns a logging configuration object with the specified level.
            self.__logging_config__ = StandardLoggingConfig(level=self.logging_level)
        return self.__logging_config__

    @logging_config.setter
    def logging_config(self, config: "LoggingConfig") -> None:
        """
        Sets the logging configuration.

        This setter allows for dynamic assignment of a custom logging
        configuration object that adheres to the `LoggingConfig` protocol.
        It can be used to override the default logging behavior.

        Args:
            config: An instance implementing `LoggingConfig` to set as the
                    current logging configuration.
        """
        # Set the logging configuration directly.
        self.__logging_config__ = config
