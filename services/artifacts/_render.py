"""Shared lazy importers for optional rendering dependencies.

WeasyPrint (needs native pango/cairo) and Jinja2 are not guaranteed in every
environment (CI / lightweight dev containers). These helpers return ``None`` so
the artifact pipeline degrades gracefully — skip the PDF / fall back to string —
instead of crashing at import time.

They were copy-pasted as private ``_try_import_weasyprint`` (14×) and
``_try_import_jinja`` (18×) across the artifact builders, differing only in log
wording/level. One copy now (log level normalised to WARNING for operator
visibility — the level weekly_memo had already deliberately bumped to).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def try_import_weasyprint():
    """Return the WeasyPrint ``HTML`` class, or ``None`` if unavailable."""
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover — native libs / env-dependent
        logger.warning("WeasyPrint unavailable (%s); PDF generation will be skipped.", exc)
        return None


def try_import_jinja():
    """Return ``(Environment, FileSystemLoader, select_autoescape)`` or a None triple."""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s); template rendering will fail.", exc)
        return None, None, None
