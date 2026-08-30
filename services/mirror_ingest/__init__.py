"""mirror_ingest — turn a user's existing records into TradeHistory rows.

The behavioural mirrors (``services/behavior/*_mirror.py``) are pure
functions over ``TradeHistory``. Everything in this package exists to fill
that list from what a user already has — today an MTS 거래내역 screenshot,
later a CSV or a photographed notebook.

Why screenshots rather than a broker API: Korean broker APIs are closed to
us. KIS states outright that partnership is unavailable to non-licensed
firms ("제도권금융회사(투자일임업, 투자자문업)이 아닌 경우 제휴 불가
(ex. 핀테크사)"), and Toss's Open API terms §5② forbid lending the app key
to a third party — the key is an 접근매체 under 전자금융거래법, so a user
pasting it into our service would breach the terms and forfeit the
protection in §16③. A record the user exports or screenshots themselves
carries none of that.

The one rule this package must never break: **do not invent a trade.**
A mirror's only claim is that it reports the user's own record back to
them. A single fabricated row makes every number in the product a guess,
and the user has no way to tell which. Anything unreadable is reported as
unreadable — never filled in with a plausible value.
"""

from services.mirror_ingest.screenshot import (  # noqa: F401
    ExtractedTrade,
    ExtractionResult,
    extract_trades_from_image,
)

__all__ = [
    "ExtractedTrade",
    "ExtractionResult",
    "extract_trades_from_image",
]
