import json
from base64 import b64decode, b64encode
from collections import deque
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from inspect import isclass
from pathlib import PurePath
from types import GeneratorType
from typing import Annotated, Any, Protocol, TypeVar, get_args, get_origin, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class EncoderProtocol(Protocol):
    """
    Defines the interface for an object capable of **serializing** a Python value
    into a format suitable for JSON.

    Implementations of this protocol provide two core functionalities:
    1. Identifying if they can process a given Python object (`is_type`).
    2. Transforming that Python object into its JSON-compatible representation
       (`serialize`).
    """

    def is_type(self, value: Any) -> bool:
        """
        Determines if this encoder can handle the provided Python `value` for
        serialization.

        Args:
            value: The Python object to inspect.

        Returns:
            True if this encoder is designed to serialize the `value`'s type;
            False otherwise.
        """
        ...

    def serialize(self, value: Any) -> Any:
        """
        Converts the given Python `value` into a basic, JSON-compatible type.

        This method should transform complex Python objects (e.g., custom
        classes, datetimes) into standard JSON types like dictionaries, lists,
        strings, numbers, or booleans.

        Args:
            value: The Python object to serialize.

        Returns:
            The JSON-compatible representation of the `value`.
        """
        ...


@runtime_checkable
class MoldingProtocol(Protocol):
    """
    Defines the interface for an object capable of **molding** or **decoding** a
    JSON-compatible value back into a specific Python type or structure.

    Implementations facilitate the reverse process of serialization, enabling the
    reconstruction of Python objects from their basic data representations. It
    provides three key functionalities:
    1. Identifying if it can decode to a target type structure (`is_type_structure`).
    2. Optionally, checking if a raw value already matches a type (`is_type`),
       often inherited from `EncoderProtocol`.
    3. Performing the actual decoding or molding process (`encode`).
    """

    def is_type(self, value: Any) -> bool:
        """
        Determines if this molder can handle the provided Python `value`.

        This method is often inherited from `EncoderProtocol` and serves a dual
        purpose: checking if a raw value already matches the target structure
        before molding.

        Args:
            value: The Python object to inspect.

        Returns:
            True if the `value` is of a type this molder recognizes; False otherwise.
        """
        ...

    def is_type_structure(self, value: Any) -> bool:
        """
        Checks if this molder is responsible for decoding into the given type
        annotation or class structure.

        This method is crucial for matching a generic type hint (like `list[str]`)
        or a specific class (`MyDataclass`) to the appropriate molder.

        Args:
            value: The target Python type, type annotation, or class that the
                   incoming data should be molded into.

        Returns:
            True if this molder can decode into the specified `value` structure;
            False otherwise.
        """
        ...

    def encode(self, structure: Any, value: Any) -> Any:
        """
        Decodes or molds the `value` (which is typically from a JSON-like source)
        into an instance of the specified `structure` type.

        Although named `encode` for historical reasons, this method's role is
        deserialization or reconstruction of Python objects.

        Args:
            structure: The target Python type or class that the `value` should
                       be molded into (e.g., `MyClass`, `datetime.date`).
            value: The raw, JSON-compatible data (e.g., a dict, list, string)
                   to be transformed.

        Returns:
            An instance of `structure` populated with data from `value`.
        """
        ...


class Encoder:
    """
    A foundational, user-extensible base class for defining type encoders and
    molders.

    This class streamlines the process of converting Python objects to and from
    JSON-compatible formats by providing common attributes and default behaviors.
    Subclasses should inherit from `Encoder` and implement `EncoderProtocol`
    and/or `MoldingProtocol` as needed, defining their specific `__type__` and
    overriding `serialize` and/or `encode`.
    """

    __type__: type | tuple[type, ...] | None = None
    # Specifies the Python type(s) this encoder/molder is designed to handle.
    # Can be a single type (e.g., `datetime.date`) or a tuple of types
    # (e.g., `(bytes, memoryview)`). If `None`, `is_type` and `is_type_structure`
    # will return `False` by default.

    __encode__: bool = True
    # A flag indicating whether the `encode` method should be implemented by
    # subclasses. If `True` (the default), `encode` must be overridden. If
    # `False`, the base `encode` method will simply return the input `value`
    # as-is, implying no special decoding is necessary or possible for this type.

    def is_type(self, value: Any) -> bool:
        """
        Checks if the provided `value` is an instance of the type(s) defined
        in the `__type__` attribute of this encoder.

        This method offers a convenient default implementation for type checking.
        Subclasses requiring more sophisticated type identification (e.g., based
        on object attributes or interfaces) should override this method.

        Args:
            value: The Python object to evaluate.

        Returns:
            True if `value` is an instance of `self.__type__`; False otherwise,
            or if `self.__type__` is `None`.
        """
        if self.__type__ is None:
            return False
        return isinstance(value, self.__type__)

    def is_type_structure(self, value: Any) -> bool:
        """
        Determines if the given `value` (representing a type annotation or a class)
        matches the type(s) that this molder handles for decoding.

        This method is particularly useful for matching target types during the
        molding process. It ensures that `value` is a class and a subclass of
        `self.__type__` without raising errors for incompatible types.

        Args:
            value: The target Python type or class to evaluate (e.g., `MyClass`,
                   `list`).

        Returns:
            True if `value` is a class and a subclass of `self.__type__`; False
            otherwise, or if `self.__type__` is `None`.
        """
        if self.__type__ is None:
            return False
        if not isclass(value):
            return False
        try:
            return issubclass(value, self.__type__)
        except TypeError:
            # Catch TypeError if `value` cannot be used with `issubclass` (e.g.,
            # it's a generic type or not a class).
            return False

    def serialize(self, value: Any) -> Any:
        """
        Abstract method: Serializes a Python `value` into a JSON-compatible format.

        This method must be implemented by any concrete subclass that adheres
        to the `EncoderProtocol`. It defines the specific logic for converting
        a Python object into its serializable representation.

        Args:
            value: The Python object to serialize.

        Returns:
            A JSON-compatible representation of the `value`.

        Raises:
            NotImplementedError: Always, as this is an abstract method that must
                                 be overridden by subclasses.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement 'serialize'.")

    def encode(self, structure: Any, value: Any) -> Any:
        """
        Abstract method: Decodes or molds a JSON-compatible `value` back into
        an instance of the specified `structure` type.

        This method must be implemented by concrete subclasses that conform to
        `MoldingProtocol` if their `__encode__` attribute is set to `True`. If
        `__encode__` is `False`, the base implementation simply returns the
        input `value` as-is, indicating no special decoding is needed.

        Args:
            structure: The target Python type or class for molding.
            value: The raw, JSON-compatible data to decode.

        Returns:
            An instance of `structure` (or the original `value` if `__encode__`
            is `False`).

        Raises:
            NotImplementedError: If `__encode__` is `True` and this method is
                                 not overridden by a subclass.
        """
        if not self.__encode__:
            return value
        raise NotImplementedError(f"{type(self).__name__} must implement 'encode' if '__encode__' is True.")


class DataclassEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Handles the serialization and deserialization of Python `dataclasses` instances.

    This encoder converts dataclass objects to standard dictionaries for
    serialization and reconstructs them from dictionaries during molding.
    """

    __type__ = object  # Placeholder; actual check uses `is_dataclass` in methods.

    def is_type(self, v: Any) -> bool:
        """Checks if the given value is an instance of a dataclass."""
        return is_dataclass(v)

    def is_type_structure(self, v: Any) -> bool:
        """Checks if the given value is a dataclass class (the type itself)."""
        return isclass(v) and is_dataclass(v)

    def serialize(self, obj: Any) -> dict:
        """Serializes a dataclass instance into a dictionary."""
        return asdict(obj)

    def encode(self, cls: type, data: dict) -> Any:
        """Molds a dictionary into an instance of the specified dataclass `cls`."""
        return cls(**data)


class NamedTupleEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Manages serialization and deserialization for `collections.namedtuple`
    instances.

    Namedtuples are serialized to dictionaries using their `_asdict()` method
    and can be reconstructed from either dictionaries or iterables.
    """

    def is_type(self, v: Any) -> bool:
        """Checks if the value is a namedtuple instance by verifying it's a
        tuple with `_asdict`."""
        return isinstance(v, tuple) and hasattr(v, "_asdict")

    def is_type_structure(self, v: Any) -> bool:
        """Checks if the value is a namedtuple class by verifying it's a tuple
        subclass with `_asdict`."""
        return isclass(v) and issubclass(v, tuple) and hasattr(v, "_asdict")

    def serialize(self, obj: Any) -> dict:
        """Serializes a namedtuple instance into a dictionary."""
        return obj._asdict()

    def encode(self, cls: type, v: Any) -> Any:
        """
        Molds a dictionary or an iterable into an instance of the specified
        namedtuple `cls`.

        If `v` is a dictionary, it uses keyword arguments; otherwise, it unpacks
        as positional.
        """
        if isinstance(v, dict):
            return cls(**v)
        return cls(*v)


class ModelDumpEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Provides serialization and deserialization capabilities for Pydantic v2+
    models.

    It leverages Pydantic's `model_dump()` for converting instances to
    dictionaries and `model_validate()` for reconstructing models from data.
    """

    def is_type(self, v: Any) -> bool:
        """Checks if the value is a Pydantic v2+ model instance (has
        `model_dump` method)."""
        return hasattr(v, "model_dump")

    def is_type_structure(self, v: Any) -> bool:
        """Checks if the value is a Pydantic v2+ model class (has
        `model_validate` method)."""
        return isclass(v) and hasattr(v, "model_validate")

    def serialize(self, v: Any) -> dict:
        """Serializes a Pydantic model instance to a dictionary using
        `model_dump`."""
        return v.model_dump()

    def encode(self, cls: type, v: Any) -> Any:
        """Molds a dictionary into a Pydantic model instance using
        `model_validate`."""
        return cls.model_validate(v)


class EnumEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Handles the serialization and deserialization of `enum.Enum` members.

    Enum members are serialized to their raw `value` and reconstructed by
    passing the value back to the Enum class constructor.
    """

    __encode__ = True
    __type__ = Enum

    def serialize(self, obj: Any) -> Any:
        """Serializes an Enum member to its underlying value."""
        return obj.value

    def encode(self, cls: type, v: Any) -> Any:
        """Molds a value back into an Enum member of the specified `cls`."""
        return cls(v)


class PurePathEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Manages serialization and deserialization for `pathlib.PurePath` objects
    (and its subclasses like `pathlib.Path`).

    Paths are converted to strings for serialization and reconstructed from
    strings during molding.
    """

    __type__ = PurePath

    def serialize(self, obj: PurePath) -> str:
        """Serializes a PurePath object to its string representation."""
        return str(obj)

    def encode(self, cls: type, v: Any) -> PurePath:
        """Molds a string into a PurePath object of the specified `cls`."""
        return cls(v)


class DateEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Provides serialization and deserialization for `datetime.date` and
    `datetime.datetime` objects.

    Dates and datetimes are serialized to ISO 8601 format strings. During
    molding, they are reconstructed from these strings, ensuring the correct
    type (`date` or `datetime`) is returned based on the target `structure`.
    """

    __type__ = date

    def serialize(self, obj: date | datetime) -> str:
        """Serializes a date or datetime object to an ISO 8601 format string."""
        return obj.isoformat()

    def encode(self, cls: type, v: Any) -> date | datetime:
        """
        Molds an ISO 8601 string into a `date` or `datetime` object.

        Returns a `date` if `cls` is `date` (and not `datetime` itself),
        otherwise a `datetime`.
        """
        dt = datetime.fromisoformat(v)
        # If the target class is `date` (and not `datetime`), return only the date part.
        return dt.date() if issubclass(cls, date) and cls is not datetime else dt


class BytesEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Handles the serialization and deserialization of `bytes` and `memoryview`
    objects.

    Binary data is encoded to Base64 strings for serialization and decoded back
    to `bytes` during molding.
    """

    __type__ = (bytes, memoryview)

    def serialize(self, obj: bytes | memoryview) -> str:
        """
        Serializes `bytes` or `memoryview` objects to a Base64 encoded UTF-8 string.

        Memoryview objects are converted to bytes before encoding.
        """
        if isinstance(obj, memoryview):
            obj = obj.tobytes()  # Convert memoryview to bytes.
        # Base64 encode bytes and then decode to UTF-8 string.
        return b64encode(obj).decode("utf-8")

    def encode(self, cls: type, v: Any) -> bytes:
        """
        Molds a Base64 encoded string back into a `bytes` object.

        The input string is first encoded to UTF-8 bytes, then Base64 decoded.
        """
        # Encode string to bytes, then Base64 decode.
        return b64decode(v.encode("utf-8"))


class StructureEncoder(Encoder, EncoderProtocol, MoldingProtocol):
    """
    Manages serialization and deserialization for common Python collection types:
    `list`, `set`, `frozenset`, `GeneratorType`, `tuple`, and `collections.deque`.

    Any supported iterable is serialized into a standard Python `list`. During
    molding, this encoder attempts to reconstruct the specific target collection
    type from the input list or iterable.
    """

    __type__ = (list, set, frozenset, GeneratorType, tuple, deque)

    def is_type(self, v: Any) -> bool:
        """
        Checks if the `value` is an instance of a supported iterable type,
        explicitly excluding `str`, `bytes`, and `memoryview` to prevent
        unintended serialization of these primitives as collections.
        """
        return isinstance(v, Iterable) and not isinstance(v, (str, bytes, memoryview))

    def is_type_structure(self, v: Any) -> bool:
        """
        Checks if the `value` (representing a type or type hint) is one of the
        supported collection types or a subclass thereof.

        This method correctly handles generic type hints (e.g., `list[str]`) by
        resolving their origin type.
        """
        # Get the base type for generics like list[str].
        origin = get_origin(v) or v
        return isclass(origin) and issubclass(origin, self.__type__)

    def serialize(self, obj: Iterable) -> list:
        """Serializes any supported iterable into a standard Python `list`."""
        return list(obj)

    def encode(self, cls: type, v: Any) -> Any:
        """
        Molds an iterable `v` into an instance of the specified collection type `cls`.

        Attempts to construct `cls` directly from `v`. If this fails (e.g.,
        `GeneratorType` cannot be directly instantiated from a list), it falls
        back to returning a `list`.

        Args:
            cls: The target collection type (e.g., `list`, `set`, `tuple`).
            v: The iterable (typically a list from JSON) to convert.

        Returns:
            An instance of `cls` populated with elements from `v`, or a `list`
            if `cls` cannot be directly constructed.
        """
        try:
            return cls(v)
        except TypeError:
            # Fallback if the target class cannot be directly constructed from
            # the iterable (e.g., `GeneratorType` is not directly instantiable).
            return list(v)


# A tuple of default encoder/molder instances.
# The order of these encoders is significant: more specific encoders should appear
# earlier in the tuple, as the first matching encoder in `json_encode_default`
# or `apply_structure` will be used. This ensures correct type resolution
# (e.g., `DataclassEncoder` before `dict`).
_DEFAULT_ENCODERS: tuple[EncoderProtocol | MoldingProtocol, ...] = (
    DataclassEncoder(),
    NamedTupleEncoder(),
    ModelDumpEncoder(),
    EnumEncoder(),
    PurePathEncoder(),
    DateEncoder(),
    BytesEncoder(),
    StructureEncoder(),
)

# A `ContextVar` managing the active list of encoders and molders.
# Using `ContextVar` allows for per-context customization of the encoder
# registry, making it possible to add or remove encoders dynamically in
# different parts of an application. A `deque` (double-ended queue) is used as
# the default value to enable efficient `appendleft` operations when registering
# new encoders (giving them higher priority).
_ENCODERS: ContextVar[deque[EncoderProtocol | MoldingProtocol] | None] = ContextVar("ENCODERS", default=None)


def register_encoder(enc: type | EncoderProtocol | MoldingProtocol) -> None:
    """
    Registers a new encoder or molder, placing it at the front of the active
    registry.

    This function is central to extending `sayer`'s serialization and molding
    capabilities. When a new encoder is registered, it takes precedence over
    existing ones of the same type, ensuring that the most recently added custom
    logic is applied.

    Args:
        enc: The encoder instance to register, or its class. If a class is
             provided, an instance will be automatically created.
    """
    if isinstance(enc, type):
        enc = enc()  # Instantiate the encoder if a class was provided.

    # Retrieve the current list of encoders from the ContextVar.
    current = get_encoders()
    # Create a new deque, filtering out any existing encoder that has the same
    # class name as the `enc` being registered. This ensures that new
    # registrations replace old ones.
    filtered = deque(e for e in current if type(e).__name__ != type(enc).__name__)
    # Add the new/updated encoder to the very front, giving it highest priority.
    filtered.appendleft(enc)
    # Update the ContextVar with the new list of encoders.
    _ENCODERS.set(filtered)


def json_encode_default(value: Any) -> Any:
    """
    A versatile default encoder function designed to be used with `json.dumps()`.

    This function iterates through all currently registered `EncoderProtocol`
    implementations. The first encoder found that `is_type` (can serialize) the
    given `value` will be used to `serialize` it. This allows `json.dumps` to
    handle complex Python objects by delegating to custom `sayer` encoders.

    Args:
        value: The Python object that `json.dumps` is attempting to serialize.

    Returns:
        The JSON-compatible serialized representation of the `value`.

    Raises:
        TypeError: If no registered encoder is found that can serialize the
                   `value`. This is the standard exception expected by
                   `json.dumps` when an object is not JSON serializable.
    """
    for enc in _ENCODERS.get():  # Iterate through the active encoders.
        # Check if it's an EncoderProtocol and can handle the type.
        if isinstance(enc, EncoderProtocol) and enc.is_type(value):
            return enc.serialize(value)  # Serialize the value using the found encoder.
    # If no suitable encoder is found after checking all registered ones,
    # raise a TypeError. This aligns with the expected behavior of the
    # `default` argument in `json.dumps`.
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable: {value!r}")


def _get_type_from_annotation(annotation: Any) -> Any:
    """
    Extract the underlying type from an Annotated[T, ...]. Otherwise return the
    annotation.

    This is particularly useful for handling `typing.Annotated` types, where
    the actual type is wrapped within the annotation. For example,
    `Annotated[int, "description"]` would resolve to `int`. For other
    annotations, it returns the annotation itself.

    Args:
        annotation: A type annotation, which could be a simple type (`str`),
                    a generic type (`list[int]`), or an `Annotated` type.

    Returns:
        The resolved base type from the annotation.
    """
    # Check if the annotation is an `Annotated` type.
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]  # Extract the first argument, which is the actual type.
    return annotation  # For all other annotations, return them as is.


def apply_structure(structure: Any, value: Any) -> Any:
    """
    Decodes or molds a `value` (typically raw data from a JSON source) into
    an instance of the specified `structure` type.

    This function is the counterpart to `json_encode_default`. It iterates
    through all registered `MoldingProtocol` implementations. The first molder
    found that can handle the `resolved_structure` will be used to `encode`
    (mold) the `value`. It includes an optimization to return the `value` directly
    if it already matches the target `structure`'s exact type, avoiding
    unnecessary conversions.

    Args:
        structure: The target Python type or type annotation (e.g.,
                   `MyDataclass`, `list[str]`, `datetime.date`) that the `value`
                   should be transformed into. This can be a class or a generic
                   type hint.
        value: The raw, JSON-compatible data (e.g., a dictionary, list, string)
               that needs to be molded into the `structure`.

    Returns:
        The `value` transformed into an instance of the `structure` type.
        If no suitable molder is found for the `structure`, or if the `value`
        already perfectly matches the `structure`'s exact type, the original
        `value` is returned as-is.
    """
    # Resolve the underlying base type from potentially complex type annotations,
    # such as `Annotated[MyType, "some_metadata"]`.
    struct = _get_type_from_annotation(structure)

    for enc in _ENCODERS.get():  # Iterate through the active list of registered encoders/molders.
        # Check if the current object implements `MoldingProtocol` and can handle
        # the `resolved_structure` type.
        if isinstance(enc, MoldingProtocol) and enc.is_type_structure(struct):
            # Optimization: If the raw `value` is already an instance of the target
            # type and its exact type matches the `resolved_structure`, return it
            # directly. This prevents redundant processing for already correctly
            # typed data.
            try:
                return enc.encode(struct, value)
            except:
                if isinstance(value, (dict, list)):
                    text = json.dumps(value)
                    return enc.encode(struct, text)
                raise
    # If no registered molder can handle the `resolved_structure`,
    # return the original `value` without any transformation. This serves as a
    # fallback for basic types that don't require custom molding.
    return value


def get_encoders() -> list[EncoderProtocol | MoldingProtocol]:
    """
    Retrieves the current list of active encoders and molders.

    This function provides access to the registry of encoders and molders that
    `sayer` uses for serialization and deserialization operations. The returned
    list reflects any custom encoders that have been registered via
    `register_encoder`.

    Returns:
        A list of `EncoderProtocol` or `MoldingProtocol` instances, representing
        the currently active encoders and molders in their priority order.
    """
    current_encoders = _ENCODERS.get()
    if current_encoders is None:
        # 2. Initialize with a *copy* of _DEFAULT_ENCODERS if not already set
        current_encoders = deque(_DEFAULT_ENCODERS)
        _ENCODERS.set(current_encoders)
    return current_encoders
