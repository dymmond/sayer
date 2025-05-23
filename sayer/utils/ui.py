from typing import Any, Callable, TypeVar

from sayer.utils.console import console

T = TypeVar("T", bound=Callable[..., Any])


def echo(*args: Any, **kwargs: Any) -> None:
    """
    Prints messages to the console using the Rich `console.print` method.

    This function acts as a wrapper around `console.print`, allowing for rich
    text formatting in CLI output. It uses the `console` instance managed
    by `sayer.utils.console`.

    Args:
        *args: Positional arguments to be printed (e.g., strings, Rich renderables).
        **kwargs: Keyword arguments passed directly to `console.print`
                  (e.g., `style`, `justify`).
    """
    console.print(*args, **kwargs)


def error(message: str) -> None:
    """
    Prints an error message to the console with a distinct red color and '✖' symbol.

    This function formats the given message as an error, ensuring it stands out
    in the console output, and prints it using the global Rich console.

    Args:
        message: The error message string to display.
    """
    # Print the error message with bold red styling and an '✖' prefix.
    # highlight=False prevents Rich from attempting to highlight syntax within the message.
    console.print(f"[bold red]✖ {message}[/]", highlight=False)


def success(message: str) -> None:
    """
    Prints a success message to the console with a distinct green color and '✔' symbol.

    This function formats the given message as a success indicator, making it
    clear when an operation has completed successfully.

    Args:
        message: The success message string to display.
    """
    # Print the success message with bold green styling and a '✔' prefix.
    console.print(f"[bold green]✔ {message}[/]", highlight=False)


def warning(message: str) -> None:
    """
    Prints a warning message to the console with a distinct yellow color and '⚠' symbol.

    This function formats the given message as a warning, drawing attention to
    potential issues or non-critical problems.

    Args:
        message: The warning message string to display.
    """
    # Print the warning message with bold yellow styling and a '⚠' prefix.
    console.print(f"[bold yellow]⚠ {message}[/]", highlight=False)


def info(message: str) -> None:
    """
    Prints an informational message to the console with a distinct blue color and 'ℹ' symbol.

    This function formats the given message as general information, useful for
    providing contextual updates or non-critical details to the user.

    Args:
        message: The informational message string to display.
    """
    # Print the info message with bold blue styling and an 'ℹ' prefix.
    console.print(f"[bold blue]ℹ {message}[/]", highlight=False)
