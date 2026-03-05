"""Backward-compatible shim for the misspelled module path.

Prefer importing from `sayer.utils.coercion`.
"""

from sayer.utils.coercion import coerce_argument_to_option

__all__ = ["coerce_argument_to_option"]
