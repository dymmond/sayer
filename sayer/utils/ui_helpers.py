from functools import wraps
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress
from rich.prompt import Confirm
from rich.table import Table

console = Console()


def confirm(
    prompt: str = "Continue?", abort_message: str = "Aborted."
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    A decorator to prompt the user for confirmation before executing a function.

    If the user does not confirm, an abort message is printed, and the decorated
    function is not executed.

    Args:
        prompt: The confirmation message displayed to the user. Defaults to "Continue?".
        abort_message: The message printed if the user aborts. Defaults to "Aborted.".

    Returns:
        A decorator that wraps the target function with the confirmation logic.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Display the confirmation prompt to the user.
            if not Confirm.ask(f"[bold yellow]? {prompt}"):
                # If the user declines, print the abort message and return None.
                console.print(f"[red]{abort_message}[/]")
                return
            # If the user confirms, execute the original function with its arguments.
            return func(*args, **kwargs)

        return wrapper

    return decorator


def progress(items: list[Any], description: str = "Processing") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    A decorator to display a progress bar while iterating and processing a list of items.

    The decorated function will be called for each item in the `items` list,
    and its results will be collected and returned as a list.

    Args:
        items: A list of items to be processed. The decorated function will
               receive each item as its first argument.
        description: The text displayed next to the progress bar. Defaults to "Processing".

    Returns:
        A decorator that wraps the target function with progress bar functionality.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> list[Any]:
            results: list[Any] = []
            # Initialize a Rich progress bar context.
            with Progress() as p:
                # Add a new task to the progress bar.
                task = p.add_task(description, total=len(items))
                # Iterate through each item, processing it and updating the progress.
                for item in items:
                    # Execute the decorated function for the current item.
                    results.append(func(item, *args, **kwargs))
                    # Advance the progress bar by one step.
                    p.update(task, advance=1)
            # Return the collected results from processing all items.
            return results

        return wrapper

    return decorator


def table(data: list[dict[str, Any]], title: str = "Output") -> None:
    """
    Prints a formatted table to the console using Rich.

    The table columns are dynamically created from the keys of the first
    dictionary in the `data` list. Each dictionary in the list represents a row.

    Args:
        data: A list of dictionaries, where each dictionary represents a row
              and its keys are column headers. If the list is empty, a
              "No data to display" message is printed.
        title: The title displayed above the table. Defaults to "Output".
    """
    # Check if there is any data to display.
    if not data:
        console.print("[italic]No data to display.[/]")
        return

    # Extract column headers from the keys of the first dictionary.
    headers: list[str] = list(data[0].keys())
    # Create a new Rich Table instance with the specified title.
    t = Table(title=title)
    # Add columns to the table based on the extracted headers.
    for h in headers:
        t.add_column(str(h))

    # Populate the table with rows from the data.
    for row in data:
        # For each row, add values corresponding to the defined headers.
        t.add_row(*(str(row[h]) for h in headers))

    # Print the fully constructed table to the console.
    console.print(t)
