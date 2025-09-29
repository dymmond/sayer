from abc import ABC, abstractmethod
from typing import Any

import click


class BaseSayerCommand(ABC, click.Command):
    @abstractmethod
    def get_help(self, ctx: click.Context) -> str:
        """
        Render help for the command using Sayer's rich help renderer.

        This method should be implemented to provide custom help rendering
        logic that integrates with Sayer's console output.
        """
        raise NotImplementedError("Subclasses must implement get_help method.")

    def invoke(self, ctx: click.Context) -> Any:
        # Call the original implementation and capture the callback's return value.
        return_value = super().invoke(ctx)
        # Stash for any out-of-band consumers too (useful if Click version doesn't expose return_value).
        ctx._sayer_return_value = return_value

        # Optionally also stash on the command instance as a robust fallback:
        self._sayer_last_return_value = return_value  # noqa
        return return_value
