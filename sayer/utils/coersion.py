import inspect

import click

SUPPORTS_HIDDEN = "hidden" in inspect.signature(click.Option).parameters


def coerce_argument_to_option(param_config: click.Argument, *, force: bool = False) -> click.Parameter:
    """
    Convert a click.Argument into a click.Option, if and only if explicitly requested.

    - Variadic arguments (nargs=-1) are always left as Arguments.
    - If `force` is True, the argument is wrapped into an Option with a flag name.
    - Otherwise, the original Argument is returned untouched.
    """
    if not isinstance(param_config, click.Argument) or param_config.type is click.UNPROCESSED:
        return param_config

    if param_config.nargs == -1 and not force:
        return param_config

    if not force:
        return param_config

    flag_name = f"--{param_config.name.replace('_', '-')}"
    option_kwargs = {
        "param_decls": [flag_name],
        "type": param_config.type,
        "required": False,
        "help": getattr(param_config, "help", None),
        "multiple": param_config.multiple,
        "nargs": param_config.nargs,
        "expose_value": getattr(param_config, "expose_value", True),
    }

    if param_config.default is not None:
        option_kwargs["default"] = param_config.default
        option_kwargs["show_default"] = True
    else:
        option_kwargs["show_default"] = False

    # Preserve hidden if supported
    if SUPPORTS_HIDDEN and getattr(param_config, "hidden", False):
        option_kwargs["hidden"] = True

    return click.Option(**option_kwargs)
