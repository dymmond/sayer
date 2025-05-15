from functools import wraps
from typing import Any, Callable, Dict, List

from rich.console import Console
from rich.progress import Progress
from rich.prompt import Confirm
from rich.table import Table

console = Console()


def confirm(prompt: str = "Continue?", abort_message: str = "Aborted.") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not Confirm.ask(f"[bold yellow]? {prompt}"):
                console.print(f"[red]{abort_message}[/]")
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator


def progress(items: List[Any], description: str = "Processing") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            with Progress() as p:
                task = p.add_task(description, total=len(items))
                for item in items:
                    results.append(func(item, *args, **kwargs))
                    p.update(task, advance=1)
            return results
        return wrapper
    return decorator


def table(data: List[Dict[str, Any]], title: str = "Output") -> None:
    if not data:
        console.print("[italic]No data to display.[/]")
        return

    headers = list(data[0].keys())
    t = Table(title=title)
    for h in headers:
        t.add_column(str(h))

    for row in data:
        t.add_row(*(str(row[h]) for h in headers))

    console.print(t)
