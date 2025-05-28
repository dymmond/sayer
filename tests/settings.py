from dataclasses import dataclass

from sayer.conf.global_settings import Settings


@dataclass
class TestSettings(Settings):
    debug: bool = True
    display_full_help: bool = True
