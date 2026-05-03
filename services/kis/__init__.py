"""KIS (Korean Investment & Securities) integration package.

Originally at project root (kis_service.py / kis_token_manager.py /
kis_websocket_service.py); consolidated 2026-05-02 into this subpackage
for clearer organization.

Public re-exports below. New code should import from the explicit submodule
(e.g. ``from services.kis.service import KISService``); the top-level
shortcuts here are kept for ergonomics.
"""

from services.kis.service import KISService
from services.kis.token_manager import (
    KISTokenManager,
    get_kis_token,
    get_kis_token_manager,
)
from services.kis.websocket_service import KISWebSocketService

__all__ = [
    "KISService",
    "KISTokenManager",
    "KISWebSocketService",
    "get_kis_token",
    "get_kis_token_manager",
]
