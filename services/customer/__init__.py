"""Customer-experience services.

Hosts customer-lifecycle send paths that are NOT artifact-generation —
e.g. the first-brag-card celebration (C-AC1) and the 24-hour inactive
nudge (C-S2). These reuse the consolidated :class:`EmailSender`
infrastructure in ``services/email/sender.py`` (Phase 7) so they
inherit the same opt-out gate, RFC 8058 List-Unsubscribe header, and
SendGrid → Brevo → SMTP cascade as every artefact mailer.

Each entry point is a thin orchestrator; the EmailCategory enum on the
sender is the single source of truth for 정통망법 §50 ① 분리 동의
gating.
"""
from __future__ import annotations

__all__: list[str] = []
