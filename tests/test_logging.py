import pytest

from sayer.conf import monkay, settings
from sayer.logging import LoggingConfig, logger


@pytest.fixture
def setup_logging_config(monkeypatch):
    """
    Fixture to set up a custom logging configuration for testing.
    """
    # Set the logging configuration to a dummy one
    original_logging_level = settings.logging_level

    monkay.settings.logging_config = DummyConfig()
    yield
    monkay.settings.logging_config = original_logging_level


class DummyConfig(LoggingConfig):
    def __init__(self):
        super().__init__()
        self.configured = False

    def configure(self):
        self.configured = True

    def get_logger(self):
        import logging

        return logging.getLogger("dummy")


def test_custom_logging_config_via_env(setup_logging_config):
    assert isinstance(monkay.settings.logging_config, DummyConfig)

    logger.info("hi")

    assert settings.is_logging_setup

    settings.is_logging_setup = False
    logger.error("bye")
