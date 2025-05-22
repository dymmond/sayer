from __future__ import annotations

from typing import Any, TypeVar

_STATE_REGISTRY: list[type[State]] = []  # Registry of all `State` subclasses.


class StateMeta(type):
    """
    Metaclass that automatically registers every subclass of `State`.

    When a class inherits from `State` (which uses this metaclass), `StateMeta`
    intercepts the class creation. It then adds the newly created `State` subclass
    to a central registry (`_STATE_REGISTRY`), making it discoverable for
    dependency injection or other application-wide state management. The base
    `State` class itself is not registered.
    """

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        """
        Creates a new class and registers it if it's a subclass of `State`.

        Args:
            mcs: The metaclass itself (`StateMeta`).
            name: The name of the class being created.
            bases: A tuple of base classes.
            namespace: A dictionary of the class's attributes and methods.

        Returns:
            The newly created class.
        """
        cls = super().__new__(mcs, name, bases, namespace)

        # Do not register the base `State` class itself, only its subclasses.
        if name != "State":
            _STATE_REGISTRY.append(cls)
        return cls


class State(metaclass=StateMeta):
    """
    Base class for defining shared application state that can be built once
    and injected into commands or other components.

    Developers should subclass `State` to define any application-specific
    state. Instances of these state classes are typically singletons that are
    initialized once during the application's startup phase.

    Subclasses can define their own attributes, implement a custom `__init__`
    method, or provide a `classmethod build()` method to facilitate complex
    initialization, such as loading configuration from external sources.

    Example:
        ```python
        class DatabaseState(State):
            connection: Any

            def __init__(self, db_path: str):
                self.connection = connect_to_db(db_path)


        # In your command:
        # @command()
        # def my_command(db: DatabaseState):
        #     db.connection.execute(...)
        ```
    """

    ...


T = TypeVar("T", bound=State)  # Type variable constrained to `State` subclasses.


def get_state_classes() -> list[type[State]]:
    """
    Returns a list of all registered `State` subclasses.

    This function provides access to the internal registry of `State` classes,
    allowing the application to discover and manage all defined state components.
    The order of the classes in the list corresponds to their registration order.

    Returns:
        A `list` of `type` objects, where each type is a subclass of `State`.
    """
    return list(_STATE_REGISTRY)  # Return a copy to prevent external modification of the registry.
