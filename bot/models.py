"""Data models for the expense bot."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PendingState(Enum):
    """States for a pending expense registration flow."""

    AWAITING_METHOD = "awaiting_method"
    AWAITING_VENDOR = "awaiting_vendor"
    AWAITING_CATEGORY = "awaiting_category"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_RECEIPT = "awaiting_receipt"


@dataclass
class ParseResult:
    """Result of parsing a user message for expense data."""

    amount: Optional[float] = None
    method_id: Optional[int] = None
    method_name: Optional[str] = None
    vendor: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None


@dataclass
class PendingExpense:
    """Tracks an in-progress expense registration."""

    user_id: int
    chat_id: int
    amount: Optional[float] = None
    method_id: Optional[int] = None
    method_name: Optional[str] = None
    vendor: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    receipt_path: Optional[str] = None
    original_filename: Optional[str] = None
    state: PendingState = PendingState.AWAITING_CONFIRMATION
    message_id: Optional[int] = None
    timer: Optional[threading.Timer] = field(default=None, repr=False)
    created_at: datetime = field(default_factory=datetime.now)
