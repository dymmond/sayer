# Parameters

This guide dives deep into Sayer's parameter system, explaining **what** each feature is, **why** you'd use it, and **when** it's most appropriate. Examples illustrate real‐world patterns.

---

## 1. Core Parameter Types

| Type        | CLI Style             | Typical Use Case                                                  |
| ----------- | --------------------- | ----------------------------------------------------------------- |
| `Option`    | `--flag value`        | Named flags, optional or required toggles, environment fallbacks. |
| `Argument`  | positional values     | Natural, required list/sequence inputs (e.g., filenames).         |
| `Env`       | environment variables | Secrets, credentials, settings loaded from the environment.       |
| `JsonParam` | JSON string           | Complex data structures (e.g., Pydantic models) via JSON.         |

### 1.1 `Option`

**What**: A named CLI parameter: `--name foo` or flag `--verbose`.

**Why**: Use for any value where clarity and explicit naming help the user. Good for:

* Configuration values (ports, hosts, file paths).
* Feature flags (`--dry-run`, `--force`).
* Any optional input where a default makes sense.

**When**:

* You want `--timeout 30` instead of positional `30` to avoid ambiguity in order.
* You have multiple optional values in one command.
* You need `--help` to clearly annotate each parameter.

**Example**:

```python
from sayer import Sayer, Option
app = Sayer()

@app.command()
def upload(
    file: str = Option(..., help="Path to the file to upload."),
    retry: int = Option(3, help="Number of retries on failure."),
    force: bool = Option(False, help="Overwrite existing files."),
):
    pass
```

* `file` is **required** (`Option(...)`).
* `retry` is **optional** with default `3`.
* `force` is a boolean flag (no value needed).

---

### 1.2 `Argument`

**What**: Positional CLI parameters: `cmd input1 input2 ...`.

**Why**: When order matters, or you want succinct commands:

* File lists: `process file1.txt file2.txt`.
* Data points: `compute 1 2 3`.

**When**:

* Inputs form a natural sequence.
* You expect users to type multiple values quickly.
* You prefer brevity over explicit naming.

**Example**:

```python
from sayer import Argument

@app.command()
def process(
    inputs: list[str] = Argument(
        nargs=-1, help="Files to process.")
    ):
    pass
```

* `nargs=-1` captures *all* remaining tokens.

---

### 1.3 `Env`

**What**: Injects values from environment variables.

**Why**: For secrets and configuration you don't want on the CLI:

* API keys
* Database URIs
* Cloud credentials

**When**:

* You want CI/CD or server automation to provide values via environment.
* You want to **avoid** revealing secrets in shell history.

**Example**:

```python
from sayer import Env

@app.command()
def deploy(
    token: str = Env(..., envvar="DEPLOY_TOKEN", help="Auth token."),
):
    pass
```

* User runs `export DEPLOY_TOKEN=xyz` once, then `deploy` with no flags.

---

### 1.4 `JsonParam`

**What**: Accepts a JSON string on the CLI and parses it into Python objects.

**Why**: Complex nested data (configs, records) without writing a file.

**When**:

* You need a rich structure: lists of dicts, nested objects.
* You prefer inline JSON over `--opt key1=val1 --opt key2=val2`.

**Example**:

```python
from sayer.params import JsonParam

@app.command()
def create(
    data: MyPydanticModel = JsonParam(help="JSON of the new record."),
):
    pass
```

* CLI: `create '{"name": "Alice", "age": 30}'`

---

## 2. Annotated Metadata

Use `typing.Annotated` to group type hints with metadata in one place:

```python
from typing import Annotated
from sayer.params import Option, Argument

@app.command()
def run(
    path: Annotated[str, Argument(..., help="Source path.")],
    level: Annotated[int, Option(1, help="Verbosity level.")],
):
    pass
```

* Cleaner than mixing defaults and metadata.
* Leverages standard Python typing.

---

## 3. Container Types Support

Sayer now casts multiple CLI tokens into Python containers with element-wise conversion.

| Container      | `nargs=-1` | Example CLI          | Parsed Python Type     |
| -------------- | ---------- | -------------------- | ---------------------- |
| `list[T]`      | Yes        | `prog cmd 1 2 3`     | `[1,2,3]`              |
| `tuple[T,...]` | Yes        | `prog cmd 1 2 3`     | `(1,2,3)`              |
| `tuple[A,B,C]` | Yes        | `prog cmd a 1 2.5`   | `('a',1,2.5)`          |
| `set[T]`       | Yes        | `prog cmd a b a`     | `{'a','b'}`            |
| `frozenset[T]` | Yes        | `prog cmd x y x`     | `frozenset({'x','y'})` |
| `dict[K,V]`    | Yes        | `prog cmd k1=1 k2=2` | `{'k1':1,'k2':2}`      |

**Implementation Details**:

* Under the hood, `convert_cli_value_to_type` inspects `typing.get_origin` and `get_args`.
* Lists/tuples/sets/frozensets: iterate and cast each item.
* `dict[K,V]`: expects tokens `key=value`, splitting and casting both sides.

---

## 4. When to Use What

| Scenario                                  | Recommended Parameter                       |
| ----------------------------------------- | ------------------------------------------- |
| Single required value                     | `Option(..., help="...")`                   |
| Multiple unnamed values                   | `Argument(nargs=-1)`                        |
| Secret/token                              | `Env(..., envvar="...", help="...")`        |
| Rich structured payload                   | `JsonParam()`                               |
| Multiple homogeneous numeric inputs       | `list[int] = Argument(nargs=-1)`            |
| Fixed-format heterogeneous inputs (x,y,z) | `tuple[str,int,float] = Argument(nargs=-1)` |
| Unique values from CLI                    | `set[...]` or `frozenset[...]`              |
| Key-value option list                     | `dict[str,int] = Argument(nargs=-1)`        |

---

## 5. Execution & Validation Order

1. **Positional Arguments** (`Argument`).
2. **Options** (`Option`, including boolean flags).
3. **Environment** fallback for missing values.
4. **Container conversion** (list/tuple/set/frozenset/dict).
5. **JSON deserialization** (`JsonParam`).
6. **Custom callbacks** and `Param.callback` hooks.
7. **Context / State** injection.

---

## 7. Silent Parameters (`silent_param`)

### **What**

A decorator for parameter metadata (`Option`, `JsonParam`, etc.) that marks a parameter as **silent** (`expose_value=False`).
Silent parameters are **parsed and validated** like any other, but **never injected into the command callback**.

### **Why**

Use silent parameters when you need values available for parsing, environment fallback, or internal validation,
but you don't want them cluttering the function signature or being exposed to business logic.

Common examples:

* **Secrets and tokens** — you don't want them passed around or accidentally logged.
* **Auxiliary config** — parsed for correctness, but consumed internally by Sayer.
* **Flags for environment overrides** — visible to the parser, invisible to callbacks.

### **When**

* You want a parameter to exist for CLI/environment, but keep it **out of the callback kwargs**.
* You need to **hide** a parameter from `--help` and usage strings.
* You still want environment injection (`Env`) or defaults applied quietly.

### **Example**

```python
from typing import Annotated
from sayer import Sayer
from sayer.params import Option, JsonParam
from sayer.decorators import silent_param

app = Sayer(name="demo")

@app.command()
def hello(user: Annotated[str, Option()], secret: str = silent_param(Option("--secret"))):
    # secret is parsed and validated, but not injected
    return f"Hello {user}"
```

**CLI:**

```bash
$ demo hello --user Sayer --secret topsecret
Hello Sayer
```

Notice:

* `--secret` is accepted on the command line.
* `secret` is not injected into `hello()` — only `user` is passed.
* Help output hides the secret option:

```bash
$ demo hello --help
Usage: demo hello [--user <user>]

Options:
  --user   Required
```

### **Silent with JSON**

```python
@app.command()
def create(
    user: Annotated[str, Option()],
    config: dict = silent_param(JsonParam("--config")),
):
    return {"user": user}
```

**CLI:**

```bash
$ demo create --user Alice --config '{"debug": true}'
{"user": "Alice"}
```

* The `config` value is parsed and validated as JSON, but not injected into the callback return.

### **Silent from Environment**

```python
@app.command()
def deploy(
    user: Annotated[str, Option()],
    token: str = silent_param(Option("--token", envvar="DEPLOY_TOKEN")),
):
    return f"Deploying as {user}"
```

```bash
export DEPLOY_TOKEN=supersecret
$ demo deploy --user Dana
Deploying as Dana
```

* `DEPLOY_TOKEN` is read from the environment.
* `token` never appears in the callback kwargs.

### **Summary**

* Parse & validate
* Environment + defaults
* Not injected into callback
* Not shown in `--help` or usage

Silent parameters give you **security** and **clarity** by keeping sensitive/internal values invisible where they don't belong.

---

## 8. Best Practices

* **Favor `Option`** for clarity if order of args might confuse users.
* **Use `Argument`** for natural, required sequences.
* **Combine** `Option` + `Env` for sensitive defaults (`--token` or `$TOKEN`).
* **Leverage** container types to avoid manual `split()` logic.
* **Annotate** with `Annotated[...]` to keep definitions tidy.
* **Document** every parameter with `help=`.

With these tools, Sayer makes building rich, user-friendly Python CLIs a breeze—embrace the full power of typing, metadata, and automatic conversion!
