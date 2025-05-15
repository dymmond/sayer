from typing import Any, Callable, Dict, List

_before_middlewares: List[Callable[[str, Dict[str, Any]], None]] = []
_after_middlewares: List[Callable[[str, Dict[str, Any], Any], None]] = []

def before_command(func: Callable[[str, Dict[str, Any]], None]) -> Callable:
    _before_middlewares.append(func)
    return func

def after_command(func: Callable[[str, Dict[str, Any], Any], None]) -> Callable:
    _after_middlewares.append(func)
    return func

def run_before(name: str, args: Dict[str, Any]) -> None:
    for mw in _before_middlewares:
        mw(name, args)

def run_after(name: str, args: Dict[str, Any], result: Any) -> None:
    for mw in _after_middlewares:
        mw(name, args, result)
