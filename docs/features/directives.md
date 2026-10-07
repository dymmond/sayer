# Directives

Sometimes you want to add directives (that are auto-detectable cli functions) to a project.
The directive feature provides the boilerplate to do so.
It simplifies and unifies the logic used by `lilya` and `ravyn`.

The helper code consists of conversion functions:

- `find_directives_from_module` (limited to a module or package) and `find_directives_from_path` (more versatile) directive collectors. You can however use any collector,
  which outputs `Mapping[string path to origin, tuple[module, RootPath, RelativePath, function_or_callable to use] | None]`.
- `transpose_directives`: which transposes the mapping to `Mapping[tuple[directive name] | tuple[app name, directive name], tuple[help_string | None, function_or_callable] | None]`. 
  Provide value `None` for collisions.
- `directive_function_or_help`: For extracting the function or providing help in case of either no provided directive name, directive name collisions or an ambiguous directive name.

## Writing a directive

Writing a directive is quite simple:

### Function based:

``` python
def directive(
    func: F | None = None,
    *,
    display_in_cli: bool = False,
) -> Callable[[F], F]:
    def wrapper(f: F) -> F:
        f.__is_custom_directive__ = True  # type: ignore[attr-defined]
        f.__display_in_cli__ = display_in_cli  # type: ignore[attr-defined]
        return f

    if func is not None:
        return wrapper(func)

    return wrapper
```

And use it like this:

``` python
@directive(display_in_cli=True)
def testfunc():
    return success

```

### Class based:

``` python
class BaseDirective(ABC):
    __is_custom_directive__: ClassVar[bool] = True
    __display_in_cli__: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def run(*args) -> None:
        pass
```

And use it like this:

``` python
class Directive(BaseDirective):
    __display_in_cli__ = True

    def run():
        return success
```


## Collecting

When using the file based collector, you can specify something like

``` python
from sayer.utils.directives import find_directives_from_path
def extractor_directive(module: ModuleType, relative: Path):
    found: Callable | None = None
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "__is_custom_directive__", False):
            if isroutine(obj):
                new_found = obj
            elif obj.__name__ == "Directive":
                new_found = obj.run
            else:
                continue
            if found is not None:
                raise RuntimeError(f"Detected multiple directives in the same file: `{module.__file__}`.")
            found = new_found
    return found
internal_file_paths_to_not_collect = {str(Path("sayer/cli/foo.py").resolve())}
directives = find_directives_from_path(
    path,
    patterns=["**/directives/operations/[!_]*.py", "**/directives/operations/*/__init__.py", "**/directives/operations/[!_]*.pyc", "**/directives/operations/*/__init__.pyc"], extractor_directive=extractor_directive,
    ignore=internal_file_paths_to_not_collect,
    # optionally
    # Walk over modules
    # use_files=False
    # Force walking over files, returns empty dict, when no files were found.
    # use_files=True
    # Prefers walking over files, except if path does not exist in the filesystem (default)
    # use_files=None
)
```

the same for the module based collector (note: the submodules must be reachable like for `use_files=False`)

``` python
from sayer.utils.directives import find_directives_from_module

def extractor_directive(module: ModuleType, relative: Path):
    found: Callable | None = None
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "__is_custom_directive__", False):
            if isroutine(obj):
                new_found = obj
            elif obj.__name__ == "Directive":
                new_found = obj.run
            else:
                continue
            if found is not None:
                raise RuntimeError(f"Detected multiple directives in the same file: `{module.__file__}`.")
            found = new_found
    return found

internal_file_paths_to_not_collect = {str(Path("sayer/cli/foo.py").resolve())}
# walks always over modules (like use_files=False) for guranteed compatibility if the module module is zipped
directives = find_directives_from_module(
    module,
    extractor_directive=extractor_directive,
    patterns=["**/directives/operations/[!_]*.py", "**/directives/operations/*/__init__.py", "**/directives/operations/[!_]*.pyc", "**/directives/operations/*/__init__.pyc"],
    ignore=internal_file_paths_to_not_collect,
)
```

!!! Warning
    Every path part beyond the root must be a valid python identifier and not be prefixed with `_` (private).
    Relative imports may fail with file-based collection (`use_files=True`, or the default when the path exists).

!!! Note
    You will need to check for `.pyc` files because site-packages can be zipped.


### `use_files=True` vs `use_files=False`

`find_directives_from_path` support a parameter named `use_files`

`use_files=True`:

Use globbing together with Path.walk(). When the specified path doesn't exist, return an empty dictionary.
This is less strict, as not every path needs to contain an `__init__.py`.
You can also jump to disconnected source folders (no valid path).

`use_files=False`: Use globbing together with pkgutils.walk_packages(). This requires the path is importable by the standard importer.

Recommendation: leave `use_files=None` (the default) to automatically select the file-based less-strict retrieval when possible (the path exists) and falling back to module walking.

## Transposing

You have now the mapping from files to directives (and `None` placeholders). The next step is to transpose to directive names and app names.
This can be done via `transpose_directives`. 

To get a valid format to fetch directives it must be transposed via `transpose_directives`.

```python
from sayer.utils.directives import find_directives_from_module, transpose_directives
directives = ...
transposed = transpose_directives(directives)
```
That was it. You might want to remove some directives from the help:

```python
from sayer.utils.directives import find_directives_from_module, transpose_directives, DirectiveTuple
directives = ...
def extractor_help(tup: DirectiveTuple) -> str | None:
    if not getattr(tup.func, "__display_in_cli__", False):
        return None
    return tup.func.__doc__ or ""

transposed = transpose_directives(directives, extractor_help=extractor_help)
```

By default the relative part most below the root is used for the app name and if there is none, the basename of the root. You can however overwrite it by
providing in the module an extra variable `app_name = "foo"`. When `app_name` is available it will be used.
You can also overwrite the `extractor_app_name`:

```python
from sayer.utils.directives import find_directives_from_module, transpose_directives, DirectiveTuple
directives = ...

transposed = transpose_directives(
    directives,
    extractor_help=...,
    extractor_app_name = lambda tup: tup.root.name,
    # or
    # extractor_app_name = lambda tup: "fixed_name",
)
```

## Retrieving the directive function or getting help

The last step is to integrate everything via `directive_function_or_help`

``` python
import sys
from inspect import isawaitable
from pathlib import Path
from pkgutil import ModuleInfo
from typing import Annotated, Any

import click

from sayer.core.engine import command
from sayer.params import Argument
from sayer.utils.directives import find_directives_from_path, DirectiveTuple

def extractor_directive(module: ModuleType, relative: Path):
    found: Callable | None = None
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "__is_custom_directive__", False):
            if isroutine(obj):
                new_found = obj
            elif obj.__name__ == "Directive":
                new_found = obj.run
            else:
                continue
            if found is not None:
                raise RuntimeError(f"Detected multiple directives in the same file: `{module.__file__}`.")
            found = new_found
    return found

@command(
    context_settings={
        "allow_interspersed_args": False
    },
)
async def directive(
    directive: Annotated[
        str,
        Argument("", required=False, help="The name of the directive to execute. Leave empty to list directives."),
    ],
    directive_args: Annotated[
        list[str],
        Argument(
            nargs=-1,
            type=click.UNPROCESSED,
            help="The arguments needed to be passed to the custom directive",
            required=False,
        ),
    ],
) -> None:

    directives = find_directives_from_path(
        path,
        patterns=["**/directives/operations/[!_]*.py", "**/directives/operations/*/__init__.py", "**/directives/operations/[!_]*.pyc", "**/directives/operations/*/__init__.pyc"], extractor_directive=extractor_directive,
    )
    transposed = transpose_directives(directives)
    retrieved = directive_function_or_help(transposed, directive=directive)
    if retrieved is not None:
        retrieved = retrieved(*directive_args)
        if isawaitable(retrieved):
            await retrieved
```

If `directive_function_or_help` returns `None` the help was requested. You can change the help preamble (shown when directive is empty and the availabe directives are listed),
by providing a custom `help_text_preamble` parameter. The preamble should end with `\n`.