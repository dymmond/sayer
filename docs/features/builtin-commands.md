# Built-in CLI Commands

Sayer comes with built-in CLI commands that support:

- 📦 Project scaffolding (`new`)
- 📚 Automatic documentation generation (`docs generate`)

These are registered automatically and available immediately after installation.

---

## 🚀 `sayer new` – Project Generator

The `sayer new` command scaffolds a complete new Sayer CLI application in seconds.

It sets up:

- `main.py` bootstrap
- `commands/` folder with a working command
- `pyproject.toml` with `sayer` dependency
- `.gitignore` and README

### ✅ Usage

```bash
sayer new my-cli
```

Creates a structure like:

```
my-cli/
├── main.py
├── pyproject.toml
├── .gitignore
├── README.md
└── commands/
    ├── __init__.py
    └── hello.py
```

### 🔍 Command Reference

```bash
sayer new --help
```

```
Usage: sayer new <name>

Create a new Sayer CLI project in <name> directory.
```

You can immediately test it:

```bash
cd my-cli
python main.py hello --name Sayer
```

---

## 📚 `sayer docs generate` – Docs Generator

Generates Markdown documentation for **all commands and subcommands** in your CLI app.

### ✅ Usage

```bash
sayer docs generate
```

Or set a custom output directory:

```bash
sayer docs generate --output ./my-docs/
```

### 🧾 What It Does

* Builds a `README.md` with command list
* Generates one `.md` file per command and subcommand
* Outputs to `docs/` by default (compatible with MkDocs!)

### 🧪 Example

```
docs/
├── README.md
└── commands/
    ├── hello.md
    ├── users-create.md
    └── users-delete.md
```

---

## 🧰 Recap

| Command               | Description                             |
| --------------------- | --------------------------------------- |
| `sayer new`           | Scaffold a new CLI project              |
| `sayer docs generate` | Generate Markdown docs for all commands |

Sayer's built-in commands are here to help you **bootstrap and document faster**.

👉 See also: [Testing](./testing.md), [Encoders](./encoders.md), [Developer Workflow](../workflows/dev-loop.md)
