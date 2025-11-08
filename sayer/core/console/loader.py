from typing import Any

import click


def render_help(*args: Any, **kwargs: Any) -> None:
    """
    Renders help using the RichHelpFormatter class.

    This function is designed to be called in two ways,
    due to inconsistencies in the Sayer framework:

    1. As a direct function: render_help(ctx)
       (Likely used by SayerCommand.format_help)
    2. As a 'format_help' method replacement: cmd.format_help = render_help
       (Likely used by SayerGroup, which passes [self, ctx, formatter])

    To provide a custom formatter, create a subclass of RichHelpFormatter
    and attach it to the context, e.g.:
    ctx.formatter_class = MyCustomHelpFormatter
    """
    from sayer.conf import monkay

    ctx: click.Context
    if args and isinstance(args[0], click.Context):
        # render_help(ctx)
        ctx = args[0]
    elif len(args) > 1 and isinstance(args[1], click.Context):
        # render_help(self, ctx, formatter)
        ctx = args[1]
    else:
        raise TypeError("Could not find click.Context in args for render_help. " f"Received args: {args}")

    # Look for a custom formatter class on the context,
    # default to our new base class.
    FormatterClass = getattr(ctx, "formatter_class", monkay.settings.formatter_class)

    # If the formatter_class on the context is NOT one of our rich
    # formatters (e.g., it's a default click.HelpFormatter),
    # we MUST ignore it and use our RichHelpFormatter,
    # otherwise we'll crash trying to call methods that don't exist.
    try:
        if not issubclass(FormatterClass, monkay.settings.formatter_class):
            FormatterClass = monkay.settings.formatter_class
    except TypeError:
        # issubclass fails if FormatterClass is not a class
        FormatterClass = monkay.settings.formatter_class

    formatter = FormatterClass(ctx)
    formatter.render_help()
