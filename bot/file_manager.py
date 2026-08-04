"""File management for receipt storage."""

import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Optional

from bot.config import RECEIPTS_DIR


def _sanitize_name(text: str) -> str:
    """Remove accents, lowercase, replace spaces with underscores, remove special chars."""
    # Normalize unicode and remove accents
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    # Lowercase and replace spaces
    clean = ascii_text.lower().strip()
    clean = re.sub(r'[\s]+', '_', clean)
    # Keep only alphanumeric, underscore, hyphen
    clean = re.sub(r'[^a-z0-9_\-]', '', clean)
    return clean


def _get_unique_path(path: Path) -> Path:
    """If path exists, append _1, _2, etc. until unique."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def save_receipt(
    file_bytes: bytes,
    extension: str,
    expense_data: dict,
) -> str:
    """Save receipt file and return relative path from data/receipts/.

    Args:
        file_bytes: The file content
        extension: File extension (e.g., ".jpg", ".pdf")
        expense_data: Dict with keys: category_name, vendor, amount, date (optional)

    Returns:
        Relative path from RECEIPTS_DIR (e.g., "2026/08/2026-08-03_alimentacion_carrefour_5200.jpg")
    """
    today = expense_data.get("date", date.today())
    if isinstance(today, str):
        today = date.fromisoformat(today)

    year_str = f"{today.year:04d}"
    month_str = f"{today.month:02d}"

    # Build directory
    target_dir = RECEIPTS_DIR / year_str / month_str
    target_dir.mkdir(parents=True, exist_ok=True)

    # Build filename parts
    date_part = today.isoformat()
    category_part = _sanitize_name(expense_data.get("category_name", "otros") or "otros")
    vendor_part = _sanitize_name(expense_data.get("vendor", "sin_comercio") or "sin_comercio")
    amount_part = str(int(expense_data.get("amount", 0)))

    # Ensure extension starts with dot
    if not extension.startswith('.'):
        extension = f".{extension}"

    filename = f"{date_part}_{category_part}_{vendor_part}_{amount_part}{extension}"
    full_path = _get_unique_path(target_dir / filename)

    # Write file
    with open(full_path, 'wb') as f:
        f.write(file_bytes)

    # Return relative path
    return str(full_path.relative_to(RECEIPTS_DIR))


def get_receipt_path(relative_path: str) -> Optional[Path]:
    """Get the absolute path for a stored receipt.

    Returns None if the file doesn't exist.
    """
    full_path = RECEIPTS_DIR / relative_path
    if full_path.exists():
        return full_path
    return None


def get_extension_from_mime(mime_type: Optional[str]) -> str:
    """Map MIME type to file extension."""
    mime_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "application/pdf": ".pdf",
    }
    return mime_map.get(mime_type or "", ".bin")
