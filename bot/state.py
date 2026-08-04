"""In-memory state management for pending expense flows."""

import threading
from typing import Optional

import telebot

from bot.config import PENDING_TIMEOUT, msg
from bot.models import PendingExpense, PendingState

# Global state: user_id -> PendingExpense
_pending_expenses: dict[int, PendingExpense] = {}
_lock = threading.Lock()

# Reference to bot instance (set during initialization)
_bot: Optional[telebot.TeleBot] = None


def set_bot(bot: telebot.TeleBot) -> None:
    """Set the bot instance for timeout notifications."""
    global _bot
    _bot = bot


def get_pending(user_id: int) -> Optional[PendingExpense]:
    """Get pending expense for a user."""
    with _lock:
        return _pending_expenses.get(user_id)


def set_pending(user_id: int, expense: PendingExpense) -> None:
    """Set or update pending expense for a user, starting the timeout timer."""
    with _lock:
        # Cancel existing timer if any
        existing = _pending_expenses.get(user_id)
        if existing and existing.timer:
            existing.timer.cancel()

        # Start new timeout timer
        timer = threading.Timer(PENDING_TIMEOUT, _timeout_handler, args=[user_id])
        timer.daemon = True
        timer.start()
        expense.timer = timer

        _pending_expenses[user_id] = expense


def clear_pending(user_id: int) -> Optional[PendingExpense]:
    """Remove and return pending expense for a user."""
    with _lock:
        expense = _pending_expenses.pop(user_id, None)
        if expense and expense.timer:
            expense.timer.cancel()
        return expense


def _timeout_handler(user_id: int) -> None:
    """Called when a pending expense times out."""
    with _lock:
        expense = _pending_expenses.pop(user_id, None)

    if expense and _bot:
        try:
            _bot.send_message(
                expense.chat_id,
                msg("timeout_expired"),
            )
        except Exception:
            pass  # Best effort notification
