import sys
from typing import Any

from rich.console import Console

from sayer.conf import monkay


class ConsoleProxy:
    """
    Proxy that creates a new Rich Console bound to the current sys.stdout
    on each attribute access, so ANSI output is captured by Click's runner.
    """

    def __getattr__(self, name: str) -> Any:
        # Instantiate a fresh Console writing to the current stdout
        console = Console(
            file=sys.stdout,
            force_terminal=monkay.settings.force_terminal,
            color_system=monkay.settings.color_system,
        )
        return getattr(console, name)


console = ConsoleProxy()
