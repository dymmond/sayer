from typing import Any


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
