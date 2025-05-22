# Encoders

Sayer provides a powerful **encoder system** that allows you to serialize and deserialize complex data structures from and into CLI arguments — automatically.

This system is used behind the scenes when using features like:

- `JsonParam(...)` for complex input objects
- Annotated CLI parameters with structured types
- Data validation using Pydantic, attrs, dataclasses, msgspec, or custom types

---

## 🧠 What Are Encoders?

Encoders are **plug-and-play serializers and deserializers** that Sayer uses to:

- Convert complex Python types → JSON-friendly dicts (serialization)
- Convert JSON input from CLI → Python objects (molding/decoding)

They follow a set of protocols:

| Protocol           | Role                                      |
|--------------------|-------------------------------------------|
| `EncoderProtocol`  | Can this value be serialized?             |
| `MoldingProtocol`  | Can this structure be parsed/deserialized?|

---

## 🧩 Built-in Encoders

Sayer includes encoders for:

- **dataclasses**

These are registered globally via `register_encoder(...)` and work out-of-the-box.

---

## ✨ Example: Using `JsonParam`

```python
from dataclasses import dataclass
from sayer.params import JsonParam
from sayer import command
from typing import Annotated

@dataclass
class Coordinates:
    x: int
    y: int

@command
def print_coords(obj: Annotated[Coordinates, JsonParam()]):
    print(obj.x, obj.y)
```

```bash
python app.py print-coords --obj '{"x": 1, "y": 2}'
# Output: 1 2
```

This works because Sayer detects the dataclass and uses its registered encoder to parse the JSON input.

---

## 🧬 Encoder Protocols (API)

### `EncoderProtocol`

```python
class EncoderProtocol(Protocol):
    def is_type(self, value: Any) -> bool:
        ...
    def serialize(self, value: Any) -> Any:
        ...
```

### `MoldingProtocol`

```python
class MoldingProtocol(Protocol):
    def is_type_structure(self, target_type: Any) -> bool:
        ...
    def encode(self, structure: Any, data: Any) -> Any:
        ...
```

---

## 🔧 Writing Your Own Encoder

You can register custom types:

```python
from sayer.encoders import Encoder, register_encoder

class CustomStruct:
    def __init__(self, val: int):
        self.val = val

class CustomEncoder(Encoder):
    __type__ = CustomStruct

    def serialize(self, obj):
        return {"val": obj.val}

    def encode(self, structure, data):
        return CustomStruct(**data)

register_encoder(CustomEncoder())
```

You can also use the [settings](./settings.md) system to manage complex configurations and setup register your encoders.

---

## 🔍 How Sayer Resolves Encoders

1. Parameter uses `Annotated[MyType, JsonParam()]`
2. Sayer inspects `MyType` and input value
3. It matches against all registered encoders
4. If `is_type()` and `is_type_structure()` succeed:

   * Calls `encode()` to build object
   * Passes object to command

If no encoder matches, Sayer raises a descriptive error.

---

## 🧪 Example from Tests

```python
@attrs.define
class Item:
    id: int
    name: str

@command
def echo_item(obj: Annotated[Item, JsonParam()]):
    print(obj.name)
```

```bash
python app.py echo-item --obj '{"id": 123, "name": "Cool"}'
# Output: Cool
```

Tested structures also include:

* `@dataclass`
* `attrs.define`
* `pydantic.BaseModel`
* `msgspec.Struct`

---

## 🛠 Advanced Features

* Encoders are **pluggable** — you can add support for any custom format
* You can override existing encoders for advanced control
* Serialization via `serialize()` is useful for logging or snapshotting

---

## ⚠️ Notes and Limitations

* Encoder matching is **based on type inspection**, not duck typing
* You must use `Annotated[Type, JsonParam()]` for it to trigger
* Encoders do **not** do CLI parsing; they only handle structure transformation

---

## 🧰 Recap

| Concept            | Description                                    |
| ------------------ | ---------------------------------------------- |
| EncoderProtocol    | Defines serialization behavior                 |
| MoldingProtocol    | Defines deserialization behavior               |
| `register_encoder` | Globally adds a new encoder                    |
| `JsonParam()`      | Activates encoding for complex CLI params      |
| Built-in support   | Works with dataclass, attrs, Pydantic, msgspec |

---
