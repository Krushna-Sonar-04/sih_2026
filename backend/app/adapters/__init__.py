from .base import (
    AdapterHealth,
    ConnectionTest,
    HistoryUnsupported,
    NormalizedPost,
    PermanentAuthError,
    PlannedAdapter,
    PlatformAdapter,
    RateLimitError,
    mask,
)
from .registry import (
    ADAPTERS,
    PLATFORM_PRIORITY,
    adapter_health,
    get_adapter,
    get_telegram_history_adapter,
    test_connection,
)
from .telegram_bot import TelegramBotAdapter
from .telegram_mtproto import TelegramMTProtoAdapter
from .telegram_normalizer import CommonTelegramNormalizer
from .x_adapter import XAdapter, XConnectionTester, XNormalizer

__all__ = [
    "AdapterHealth",
    "ConnectionTest",
    "HistoryUnsupported",
    "NormalizedPost",
    "PermanentAuthError",
    "PlannedAdapter",
    "PlatformAdapter",
    "RateLimitError",
    "mask",
    "ADAPTERS",
    "PLATFORM_PRIORITY",
    "adapter_health",
    "get_adapter",
    "get_telegram_history_adapter",
    "test_connection",
    "TelegramBotAdapter",
    "TelegramMTProtoAdapter",
    "CommonTelegramNormalizer",
    "XAdapter",
    "XNormalizer",
    "XConnectionTester",
]
