"""Export and reporting handlers."""

import csv
import io
import os
import re
import zipfile
from datetime import date, datetime

import telebot
from telebot.types import Message

from bot import db
from bot.config import ALLOWED_USERS, ADMIN_ID, GROUP_CHAT_ID, RECEIPTS_DIR, msg
from bot.file_manager import get_receipt_path


def _is_authorized(message: Message) -> bool:
    """Check authorization for export commands."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if chat_id == GROUP_CHAT_ID and user_id in ALLOWED_USERS:
        return True
    if chat_id == user_id == ADMIN_ID:
        return True

    return False


def _parse_month_year(args: list[str]) -> tuple[int, int, str, str]:
    """Parse month/year from command arguments.

    Returns (year, month, start_date, end_date).
    """
    now = date.today()

    if not args:
        # Default: current month
        year = now.year
        month = now.month
    elif len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        month = int(args[0])
        year = int(args[1])
    elif len(args) == 1 and args[0].isdigit():
        month = int(args[0])
        year = now.year
    else:
        # Try date range format dd/mm/yyyy dd/mm/yyyy
        return _parse_date_range(args)

    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    return year, month, start, end


def _parse_date_range(args: list[str]) -> tuple[int, int, str, str]:
    """Parse dd/mm/yyyy dd/mm/yyyy format."""
    date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')

    dates = []
    for arg in args:
        match = date_pattern.match(arg)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            dates.append(date(year, month, day))

    if len(dates) >= 2:
        start_date = min(dates[0], dates[1])
        end_date = max(dates[0], dates[1])
        return end_date.year, end_date.month, start_date.isoformat(), end_date.isoformat()

    # Fallback to current month
    now = date.today()
    start = f"{now.year:04d}-{now.month:02d}-01"
    if now.month == 12:
        end = f"{now.year + 1:04d}-01-01"
    else:
        end = f"{now.year:04d}-{now.month + 1:02d}-01"
    return now.year, now.month, start, end


def _generate_csv(expenses: list[dict]) -> bytes:
    """Generate CSV content from expenses."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "fecha", "monto", "categoría", "método_pago",
        "comercio", "descripción", "registrado_por",
        "comprobante", "archivo_comprobante"
    ])

    for exp in expenses:
        writer.writerow([
            exp.get("created_at", ""),
            f"{exp.get('amount', 0):.2f}",
            exp.get("category_name", "Sin categoría"),
            exp.get("method_name", "Sin método"),
            exp.get("vendor", ""),
            exp.get("description", ""),
            exp.get("registered_by", ""),
            "Sí" if exp.get("receipt_path") else "No",
            exp.get("receipt_path", ""),
        ])

    return output.getvalue().encode("utf-8-sig")


def _generate_zip(expenses: list[dict], csv_bytes: bytes) -> bytes:
    """Generate ZIP with CSV and receipt files."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("gastos.csv", csv_bytes)

        for exp in expenses:
            receipt_rel = exp.get("receipt_path")
            if receipt_rel:
                receipt_abs = get_receipt_path(receipt_rel)
                if receipt_abs and receipt_abs.exists():
                    arcname = f"comprobantes/{os.path.basename(receipt_rel)}"
                    zf.write(str(receipt_abs), arcname)

    return buffer.getvalue()


def register_handlers(bot: telebot.TeleBot) -> None:
    """Register export-related command handlers."""

    @bot.message_handler(commands=["exportar"])
    def handle_export(message: Message) -> None:
        """Export expenses as CSV or ZIP."""
        if not _is_authorized(message):
            bot.reply_to(message, msg("unauthorized"))
            return

        text = message.text or ""
        parts = text.split()[1:]  # Remove /exportar

        # Check for --zip flag
        include_zip = "--zip" in parts
        parts = [p for p in parts if p != "--zip"]

        year, month, start, end = _parse_month_year(parts)

        expenses = db.get_expenses_by_date_range(start, end)

        if not expenses:
            bot.send_message(message.chat.id, msg("export_empty"))
            return

        csv_bytes = _generate_csv(expenses)

        if include_zip:
            zip_bytes = _generate_zip(expenses, csv_bytes)
            filename = f"gastos_{year:04d}_{month:02d}.zip"
            bot.send_document(
                message.chat.id,
                io.BytesIO(zip_bytes),
                visible_file_name=filename,
                caption=msg("export_header", count=len(expenses), period=f"{month:02d}/{year}"),
            )
        else:
            filename = f"gastos_{year:04d}_{month:02d}.csv"
            bot.send_document(
                message.chat.id,
                io.BytesIO(csv_bytes),
                visible_file_name=filename,
                caption=msg("export_header", count=len(expenses), period=f"{month:02d}/{year}"),
            )

    @bot.message_handler(commands=["resumen"])
    def handle_summary(message: Message) -> None:
        """Show monthly expense summary."""
        if not _is_authorized(message):
            bot.reply_to(message, msg("unauthorized"))
            return

        now = date.today()
        year = now.year
        month = now.month

        # Check if month/year args provided
        parts = (message.text or "").split()[1:]
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            month = int(parts[0])
            year = int(parts[1])
        elif len(parts) == 1 and parts[0].isdigit():
            month = int(parts[0])

        summary = db.get_monthly_summary(year, month)
        total = db.get_monthly_total(year, month)

        if not summary:
            bot.send_message(message.chat.id, msg("export_empty"))
            return

        lines = [msg("summary_header", month=f"{month:02d}/{year}")]
        lines.append("")

        total_count = 0
        for row in summary:
            emoji = row.get("emoji", "📁") or "📁"
            name = row.get("name", "Sin categoría") or "Sin categoría"
            cat_total = row.get("total", 0)
            count = row.get("count", 0)
            total_count += count
            lines.append(f"{emoji} *{name}:* ${cat_total:,.2f} ({count})")

        lines.append("")
        lines.append(f"💰 *Total:* ${total:,.2f} ({total_count} gastos)")

        bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    @bot.message_handler(commands=["ultimos"])
    def handle_last_expenses(message: Message) -> None:
        """Show last N expenses."""
        if not _is_authorized(message):
            bot.reply_to(message, msg("unauthorized"))
            return

        parts = (message.text or "").split()[1:]
        limit = 5
        if parts and parts[0].isdigit():
            limit = min(int(parts[0]), 50)

        expenses = db.get_last_expenses(limit)

        if not expenses:
            bot.send_message(message.chat.id, msg("export_empty"))
            return

        lines = [msg("last_expenses_header", count=len(expenses))]
        lines.append("")

        for exp in expenses:
            created = exp.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    date_str = dt.strftime("%d/%m %H:%M")
                except (ValueError, TypeError):
                    date_str = str(created)[:10]
            else:
                date_str = "?"

            cat_emoji = exp.get("category_emoji", "📁") or "📁"
            cat_name = exp.get("category_name", "Sin categoría") or "Sin categoría"
            method_name = exp.get("method_name", "") or ""
            vendor = exp.get("vendor", "") or ""
            amount = exp.get("amount", 0)
            receipt = "📎" if exp.get("receipt_path") else ""
            user = exp.get("registered_by", "")

            line = f"{cat_emoji} {date_str} | *${amount:,.2f}* | {cat_name}"
            if method_name:
                line += f" | {method_name}"
            if vendor:
                line += f" | {vendor}"
            if receipt:
                line += f" {receipt}"
            if user:
                line += f" — _{user}_"

            lines.append(line)

        bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")
