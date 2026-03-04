# Getting Started

Get a working Sayer CLI in a few minutes.

## 1. Install

```bash
pip install sayer
```

## 2. Create `app.py`

```python
from sayer import Sayer, Option

app = Sayer(name="demo", help="Demo CLI")


@app.command()
def hello(name: str = Option(..., help="Name to greet")):
    """Say hello."""
    print(f"Hello, {name}!")


if __name__ == "__main__":
    app()
```

## 3. Run

```bash
python app.py hello --name Ada
```

Expected output:

```text
Hello, Ada!
```

## 4. Inspect generated help

```bash
python app.py --help
python app.py hello --help
```

## 5. Next Steps

- Build progressively with [Tutorials](./tutorials/index.md)
- Solve focused tasks via [How-to Guides](./how-to/index.md)
- Understand internals in [Concepts](./concepts/index.md)
