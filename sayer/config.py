import os
from functools import lru_cache
from typing import Any, Optional


class SayerConfig:
    def __init__(self):
        self._config: dict[str, Any] = {}

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._config.get(key, os.getenv(key.upper(), default))

    def set(self, key: str, value: Any):
        self._config[key] = value

    def all(self) -> dict[str, Any]:
        return {**os.environ, **self._config}


@lru_cache(maxsize=1)
def get_config() -> SayerConfig:
    return SayerConfig()
