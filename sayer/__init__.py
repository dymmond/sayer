from typing import TYPE_CHECKING

from monkay import Monkay

from .__version__ import get_version

if TYPE_CHECKING:
    from .app import Sayer
    from .conf import settings
    from .conf.global_settings import Settings
    from .core.engine import command, group
    from .params import Argument, Option, Param
    from .utils.config import get_config
    from .utils.loader import load_commands_from
    from .utils.ui_helpers import confirm, progress, table

__version__ = get_version()

monkay: Monkay = Monkay(
    globals(),
    lazy_imports={
        "Sayer": ".app.Sayer",
        "command": ".core.engine.command",
        "group": ".core.engine.group",
        "load_commands_from": ".utils.loader.load_commands_from",
        "confirm": ".utils.ui_helpers.confirm",
        "progress": ".utils.ui_helpers.progress",
        "table": ".utils.ui_helpers.table",
        "get_config": ".utils.config.get_config",
        "Param": ".params.Param",
        "Option": ".params.Option",
        "Argument": ".params.Argument",
        "Settings": ".conf.global_settings.Settings",
        "settings": ".conf.settings",
    },
    skip_all_update=True,
    package="sayer",
)

__all__ = [
    "command",
    "group",
    "Sayer",
    "load_commands_from",
    "confirm",
    "progress",
    "table",
    "get_config",
    "Param",
    "Option",
    "Argument",
    "Settings",
    "settings",
]
