from sayer.conf.global_settings import Settings


class TestSettings(Settings):
    debug: bool = True
    display_full_help: bool = True
