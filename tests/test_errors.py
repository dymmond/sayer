from typing import Annotated

import pytest

from sayer import Argument, command


def test_raise_value_error_on_default_with_nargs():
    """
    Test that a ValueError is raised when a command with nargs is defined with a default value.
    """
    with pytest.raises(ValueError):

        @command
        def foo(arg: Annotated[str, Argument(nargs=-1, default="default")]): ...
