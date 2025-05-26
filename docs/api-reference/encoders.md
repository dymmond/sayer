# Encoders

This document explores `sayer/encoders.py`, covering serialization and deserialization in Sayer.

## Overview

The `encoders` module manages how complex data types are:

* Serialized into JSON-compatible formats.
* Deserialized (molded) back into Python structures.

## Key Functions

### json_encode_default(obj)

Serializes complex Python objects (e.g., dataclasses, enums, paths) into JSON-compatible values.

### apply_structure(data, type_)

Deserializes JSON-like data into a specified Python type.

### get_encoders()

Returns the registry of available encoders.

### register_encoder(type_, encoder, molder)

Registers custom encoders and molders for a specific Python type.

## Example

```python
from sayer.encoders import register_encoder

register_encoder(MyTypeCustomEncoder)
```

## Best Practices

* ✅ Register custom encoders for complex types early in your app.
* ✅ Use `apply_structure` to safely convert input data.
* ✅ Test serialization logic thoroughly.
* ❌ Avoid overwriting default encoders unless absolutely necessary.

## Related Modules

* [Parameters](./params.md)
