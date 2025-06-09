import sys
from typing import Any

from rich.console import Console

from sayer.conf import monkay


class ConsoleProxy:
    """
    A proxy object for `rich.console.Console` that ensures ANSI output is
    correctly captured by Click's testing utilities, like `CliRunner`.

    This proxy works by creating a new `Console` instance each time one of
    its attributes is accessed. This new `Console` is explicitly bound to
    the current `sys.stdout`, guaranteeing that any Rich output is directed
    to the correct stream, even when `sys.stdout` has been redirected (e.g.,
    during command-line interface testing).
    """

    def __getattr__(self, name: str) -> Any:
        """
        Dynamically creates and returns an attribute from a fresh `Console` instance.

        When any attribute (method or property) is accessed on `ConsoleProxy`,
        this method is invoked. It instantiates a new `rich.console.Console`
        object, ensuring it writes to the current `sys.stdout` and inherits
        color system and terminal forcing settings from `sayer.conf.monkay.settings`.
        It then returns the requested attribute from this newly created console.

        Args:
            name: The name of the attribute being accessed (e.g., 'print', 'status').

        Returns:
            The requested attribute (method or property) from a dynamically
            created `Console` instance.
        """
        # Create a new Console instance, explicitly setting its file to the current sys.stdout.
        # This is crucial for environments like Click's CliRunner where sys.stdout is redirected.
        console = Console(
            file=sys.stdout,
            force_terminal=monkay.settings.force_terminal,
            color_system=monkay.settings.color_system,
            markup=True,
            highlight=True,
            emoji=True,
        )
        # Return the requested attribute from the newly created console instance.
        return getattr(console, name)


# Export an instance of ConsoleProxy as the globally accessible console object for Sayer.
console = ConsoleProxy()
