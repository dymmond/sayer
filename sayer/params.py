from typing import Any, Callable, Optional


class Param:
    """
    Represents a parameter definition used in schema generation or validation.

    Stores the default value, description, and an explicit required flag
    for a parameter.
    """

    def __init__(
        self,
        default: Any = ...,
        *,
        description: str = "",
        required: bool | None = None,
    ):
        """
        Initializes a new Param instance.

        Args:
            default: The default value for the parameter. Defaults to `...`
                     indicating no default and potentially required if not explicitly set.
            description: A description of the parameter. Defaults to an empty string.
            required: An optional boolean to explicitly set whether the parameter is
                      required. If None, being required is determined by the default value.
        """
        self.default = default
        self.description = description
        self.explicit_required = required

    def is_required(self):
        """
        Determines if the parameter is required.

        If `explicit_required` is set, that value is used. Otherwise,
        the parameter is considered required if its default value is `...`.

        Returns:
            True if the parameter is required, False otherwise.
        """
        if self.explicit_required is not None:
            return self.explicit_required
        return self.default is ...


class Option:
    """
    Represents a command-line option parameter definition.

    Stores configuration like default value, help text, environment variable name,
    prompting behavior, and required status.
    """
    def __init__(
        self,
        default: Any = ...,
        *,
        help: str | None = None,
        envvar: str | None = None,
        prompt: bool | str = False,
        confirmation_prompt: bool = False,
        hide_input: bool = False,
        show_default: bool = True,
        required: Optional[bool] = None,
        callback: Optional[Callable[[Any], Any]] = None,
    ):
        """
        Initializes a new Option instance.

        Args:
            default: The default value for the option. Defaults to `...`.
            help: Help text for the option.
            envvar: The name of the environment variable to read the value from.
            prompt: Whether to prompt the user for the value. Can be a boolean
                    or a string to use as the prompt message.
            confirmation_prompt: Whether to ask for confirmation when prompting.
            hide_input: Whether to hide input when prompting (e.g., for passwords).
            show_default: Whether to show the default value in the help text.
            required: An optional boolean to explicitly set whether the option is
                      required. If None, being required is determined by the default value.
            callback: A function to call to process the value after parsing.
        """
        self.default = default
        self.help = help
        self.envvar = envvar
        self.prompt = prompt
        self.confirmation_prompt = confirmation_prompt
        self.hide_input = hide_input
        self.show_default = show_default
        self.required = required if required is not None else default is ...
        self.callback = callback


class Argument:
    """
    Represents a command-line argument parameter definition.

    Stores configuration like default value, help text, and required status.
    """
    def __init__(
        self,
        default: Any = ...,
        *,
        help: str | None = None,
        required: Optional[bool] = None,
        callback: Optional[Callable[[Any], Any]] = None,
    ):
        """
        Initializes a new Argument instance.

        Args:
            default: The default value for the argument. Defaults to `...`.
            help: Help text for the argument.
            required: An optional boolean to explicitly set whether the argument is
                      required. If None, being required is determined by the default value.
            callback: A function to call to process the value after parsing.
        """
        self.default = default
        self.help = help
        self.required = required if required is not None else default is ...
        self.callback = callback


class Env:
    """
    Represents an environment variable parameter definition.

    Stores the environment variable name, default value, and required status.
    """
    def __init__(self, envvar: str, default: Any = ..., required: Optional[bool] = None):
        """
        Initializes a new Env instance.

        Args:
            envvar: The name of the environment variable.
            default: The default value for the environment variable if not set.
                     Defaults to `...`.
            required: An optional boolean to explicitly set whether the environment
                      variable is required. If None, being required is determined
                      by the default value.
        """
        self.envvar = envvar
        self.default = default
        self.required = required if required is not None else default is ...
