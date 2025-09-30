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

    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """
        Override Click's usage rendering to hide parameters
        explicitly marked as hidden (e.g., expose_value=False).
        """
        original_params = self.params
        sanitized_params = []
        for p in original_params:
            if getattr(p, "hidden", False):
                p_copy = click.Option(param_decls=[], expose_value=False, hidden=True)
                p_copy.name = p.name
                sanitized_params.append(p_copy)
            else:
                sanitized_params.append(p)

        self.params = sanitized_params
        try:
            super().format_usage(ctx, formatter)
        finally:
            self.params = original_params
