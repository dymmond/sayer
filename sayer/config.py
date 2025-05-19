import os
from functools import lru_cache
from typing import Any, Optional


class SayerConfig:
    """
    Manages configuration settings, layering in-memory values over environment variables.

    Looks for settings in the internal dictionary first, then checks environment
    variables (using the uppercase key), and finally falls back to a provided
    default value.
    """

    def __init__(self):
        """
        Initializes a new SayerConfig instance with an empty internal configuration dictionary.
        """
        self._config: dict[str, Any] = {}

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Retrieves a configuration value by key.

        Checks the internal configuration dictionary first. If the key is not
        found, it then checks environment variables using the uppercase version
        of the key. If still not found, returns the provided default value.

        Args:
            key: The configuration key (string).
            default: The value to return if the key is not found in configuration
                     or environment variables. Defaults to None.

        Returns:
            The configuration value found, or the default value if not found.
        """
        return self._config.get(key, os.getenv(key.upper(), default))

    def set(self, key: str, value: Any):
        """
        Sets a configuration value in the internal in-memory dictionary.

        This value will override any environment variable with the same key
        when `get` or `all` is called.

        Args:
            key: The configuration key (string).
            value: The value to set for the key.
        """
        self._config[key] = value

    def all(self) -> dict[str, Any]:
        """
        Returns a dictionary containing all effective configuration values.

        This includes all environment variables and the in-memory settings,
        with in-memory settings overriding environment variables for duplicate keys.

        Returns:
            A dictionary containing all configuration keys and their values.
        """
        return {**os.environ, **self._config}


@lru_cache(maxsize=1)
def get_config() -> SayerConfig:
    """
    Returns a cached singleton instance of SayerConfig.

    Uses `functools.lru_cache` to ensure that subsequent calls
    return the same SayerConfig instance.

    Returns:
        The singleton SayerConfig instance.
    """
    return SayerConfig()
