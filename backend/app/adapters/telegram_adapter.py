"""Backwards-compatible alias for the Telegram Bot API path.

The real implementation now lives in telegram_bot.py (Bot API) and
telegram_mtproto.py (historical path), sharing telegram_normalizer.py.
"""
from .telegram_bot import API_ROOT, TelegramBotAdapter
from .telegram_bot import TelegramBotAdapter as TelegramAdapter

__all__ = ["TelegramAdapter", "TelegramBotAdapter", "API_ROOT"]
