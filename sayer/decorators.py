from __future__ import annotations

from typing import TypeVar

from sayer.params import BaseParam

P = TypeVar("P", bound=BaseParam)


def silent_param(param: P) -> P:
    """
    Marks a parameter as silent (expose_value=False).

    This prevents the parameter value from being injected into the
    command callback kwargs, while still allowing it to be parsed,
    validated, and used internally (envvar, defaults, etc.).

    Example:
        ```python
        from sayerimport silent_param
        from sayer.params import Option

        @app.command()
        def hello(
            user: str,
            secret: str = silent_param(Option("--secret"))
        ):
            print(f"Hello {user}")
        ```
        # Running: sayer hello --user Tiago --secret topsecret
        # prints only "Hello Tiago"
    """
    param.expose_value = False
    return param
