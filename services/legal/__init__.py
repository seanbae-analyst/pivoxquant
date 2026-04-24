"""Legal compliance scrubs.

Centralised because diverging copies of the forbidden-term list have
historically opened compliance gaps (a term added to one defense-in-
depth list and forgotten in another). All artifact / template / API
surfaces should pull the canonical set from
:mod:`services.legal.forbidden_terms`.
"""
from .forbidden_terms import (
    FORBIDDEN_DIRECTIVE_TERMS,
    assert_legal_safe,
    contains_forbidden_term,
)

__all__ = [
    "FORBIDDEN_DIRECTIVE_TERMS",
    "assert_legal_safe",
    "contains_forbidden_term",
]
