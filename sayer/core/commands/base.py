from abc import ABC, abstractmethod

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

    def invoke(self, ctx: click.Context) -> click.Command:
        rv = super().invoke(ctx)
        if hasattr(ctx, "obj") and isinstance(ctx.obj, dict):
            ctx.obj["_last_return"] = rv
        return rv
