"""Parser for extracting expense data from free-text messages."""

import re
from typing import Optional

from bot import db
from bot.models import ParseResult


def _parse_amount(text: str) -> tuple[Optional[float], str]:
    """Extract amount from text and return (amount, remaining_text).

    Handles formats:
    - "$5.200" -> 5200 (dot as thousands separator when no decimals follow)
    - "5200" -> 5200
    - "5.200,50" -> 5200.50 (dot thousands, comma decimals)
    - "$5200.50" -> 5200.50 (dot as decimal when it's the only separator with <=2 decimals)
    - "5200,50" -> 5200.50 (comma as decimal)
    - "$5.200.300" -> 5200300 (multiple dots = thousands)
    """
    # Pattern matches optional $, then digits with optional dots/commas
    pattern = r'\$?\s*(\d[\d.,]*\d|\d+)'
    match = re.search(pattern, text)
    if not match:
        return None, text

    raw = match.group(1)
    full_match = match.group(0)

    # Determine separator meaning
    has_comma = ',' in raw
    has_dot = '.' in raw
    dot_count = raw.count('.')
    comma_count = raw.count(',')

    amount: float

    if has_comma and has_dot:
        # Both present: determine which is thousands, which is decimal
        last_comma = raw.rfind(',')
        last_dot = raw.rfind('.')
        if last_comma > last_dot:
            # Comma is decimal: "5.200,50"
            integer_part = raw[:last_comma].replace('.', '').replace(',', '')
            decimal_part = raw[last_comma + 1:]
            amount = float(f"{integer_part}.{decimal_part}")
        else:
            # Dot is decimal: "5,200.50"
            integer_part = raw[:last_dot].replace(',', '').replace('.', '')
            decimal_part = raw[last_dot + 1:]
            amount = float(f"{integer_part}.{decimal_part}")
    elif has_comma and not has_dot:
        # Only comma: check if it's decimal separator
        parts = raw.split(',')
        if comma_count == 1 and len(parts[1]) <= 2:
            # Comma as decimal: "5200,50"
            amount = float(raw.replace(',', '.'))
        else:
            # Comma as thousands: "5,200,300"
            amount = float(raw.replace(',', ''))
    elif has_dot and not has_comma:
        # Only dot(s)
        parts = raw.split('.')
        if dot_count == 1 and len(parts[1]) <= 2:
            # Could be decimal "5200.50" or thousands "5.200"
            # Heuristic: if the part after dot is exactly 3 digits, it's thousands
            if len(parts[1]) == 3 and len(parts[0]) <= 3:
                # Thousands separator: "5.200" -> 5200
                amount = float(raw.replace('.', ''))
            else:
                # Decimal: "5200.50" -> 5200.50
                amount = float(raw)
        else:
            # Multiple dots = thousands separators: "5.200.300"
            amount = float(raw.replace('.', ''))
    else:
        # No separator
        amount = float(raw)

    # Remove the matched amount from text
    remaining = text[:match.start()] + text[match.end():]
    remaining = re.sub(r'\s+', ' ', remaining).strip()

    return amount, remaining


def _match_payment_method(text: str) -> tuple[Optional[int], Optional[str], str]:
    """Match payment method from text.

    Returns (method_id, method_name, remaining_text).
    """
    methods = db.get_payment_methods()
    text_lower = text.lower()

    best_match = None
    best_match_len = 0

    for method in methods:
        aliases = [a.strip().lower() for a in method["aliases"].split(",") if a.strip()]
        # Also check the method name itself
        all_names = aliases + [method["name"].lower()]

        for alias in all_names:
            if alias in text_lower and len(alias) > best_match_len:
                best_match = method
                best_match_len = len(alias)

    if best_match:
        # Remove the matched alias from text
        # Find and remove case-insensitively
        aliases = [a.strip().lower() for a in best_match["aliases"].split(",") if a.strip()]
        all_names = aliases + [best_match["name"].lower()]
        all_names.sort(key=len, reverse=True)

        remaining = text
        for alias in all_names:
            pattern = re.compile(re.escape(alias), re.IGNORECASE)
            new_remaining = pattern.sub('', remaining, count=1)
            if new_remaining != remaining:
                remaining = new_remaining
                break

        remaining = re.sub(r'\s+', ' ', remaining).strip()
        return best_match["id"], best_match["name"], remaining

    return None, None, text


def parse_expense_text(text: str) -> ParseResult:
    """Parse free-text expense input.

    Expected format: "[amount] [payment_method] [vendor/description]"
    All parts are optional except amount.
    """
    result = ParseResult()

    # Step 1: Extract amount
    amount, remaining = _parse_amount(text)
    result.amount = amount

    if not remaining:
        return result

    # Step 2: Extract payment method from remaining text
    method_id, method_name, remaining = _match_payment_method(remaining)
    result.method_id = method_id
    result.method_name = method_name

    # Step 3: Remaining text is vendor/description
    if remaining:
        result.vendor = remaining.strip()

    return result
