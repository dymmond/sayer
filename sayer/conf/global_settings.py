from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from sayer.__version__ import __version__  # noqa

if TYPE_CHECKING:
    from sayer.logging import LoggingConfig


@dataclass
class Settings:
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
    color_system: str | None = "auto"
    """
    Specifies the color system to use for terminal output.
    If set to "auto", the application will automatically detect the
    appropriate color system based on the terminal's capabilities. If set
    to a specific color system (e.g., "256", "16m"), the application will
    use that system for color output. This setting allows for customization
    of the color output in different environments, ensuring that the
    application can adapt to various terminal capabilities.
    """

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

        # Returns a logging configuration object with the specified level.
        return StandardLoggingConfig(level=self.logging_level)

    def dict(self, exclude_none: bool = False, upper: bool = False) -> dict[str, Any]:
        """
        Converts the Settings object into a dictionary representation.

        Provides a dictionary containing all the configuration settings defined
        in the dataclass. Offers options to exclude None values and transform
        keys to uppercase.

        Args:
            exclude_none: If True, omits key-value pairs where the value is None.
                          Defaults to False.
            upper: If True, converts all dictionary keys to uppercase strings.
                   Defaults to False.

        Returns:
            A dictionary where keys are setting names and values are the
            corresponding setting values.
        """
        original = asdict(self)  # Get the dataclass fields as a dictionary.

        # Handle the case where None values should be included in the output.
        if not exclude_none:
            # Return either the original dictionary or an uppercase-keyed version.
            return {k.upper(): v for k, v in original.items()} if upper else original

        # Handle the case where None values should be excluded from the output.
        # Create a filtered dictionary, then potentially uppercase the keys.
        filtered = {k: v for k, v in original.items() if v is not None}
        return {k.upper(): v for k, v in filtered.items()} if upper else filtered

    def tuple(self, exclude_none: bool = False, upper: bool = False) -> list[tuple[str, Any]]:
        """
        Converts the Settings object into a list of key-value tuples.

        Provides a list of (key, value) tuples representing each configuration
        setting. Allows for excluding tuples with None values and converting
        keys to uppercase within the tuples.

        Args:
            exclude_none: If True, omits tuples where the value is None.
                          Defaults to False.
            upper: If True, converts the key string in each tuple to uppercase.
                   Defaults to False.

        Returns:
            A list of (string, Any) tuples, where each tuple contains a setting
            name and its corresponding value.
        """
        original = asdict(self)  # Get the dataclass fields as a dictionary.

        # Handle the case where None values should be included in the output.
        if not exclude_none:
            # Return a list of items from either the original or uppercase-keyed
            # dictionary.
            return list({k.upper(): v for k, v in original.items()}.items()) if upper else list(original.items())

        # Handle the case where None values should be excluded from the output.
        # Create a filtered list of tuples, then potentially uppercase the keys.
        filtered_tuples = [(k, v) for k, v in original.items() if v is not None]
        return [(k.upper(), v) for k, v in filtered_tuples] if upper else filtered_tuples
