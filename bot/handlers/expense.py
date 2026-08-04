"""Expense registration handlers for group chat."""

import telebot
from telebot.types import CallbackQuery, Message

from bot import db, state
from bot.classifier import get_classifier
from bot.config import ADMIN_ID, ALLOWED_USERS, GROUP_CHAT_ID, msg
from bot.file_manager import get_extension_from_mime, save_receipt
from bot.keyboards import (
    categories_keyboard,
    confirmation_keyboard,
    payment_methods_keyboard,
)
from bot.models import PendingExpense, PendingState
from bot.parser import parse_expense_text


def _is_authorized(message: Message) -> bool:
    """Check if user and chat are authorized for expense operations."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Allow in configured group chat
    if chat_id == GROUP_CHAT_ID and user_id in ALLOWED_USERS:
        return True

    # Allow admin in DM for testing
    if chat_id == user_id == ADMIN_ID:
        return True

    return False


def _is_authorized_callback(call: CallbackQuery) -> bool:
    """Check callback authorization."""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if chat_id == GROUP_CHAT_ID and user_id in ALLOWED_USERS:
        return True
    if chat_id == user_id == ADMIN_ID:
        return True

    return False


def _format_expense_summary(pending: PendingExpense) -> str:
    """Format a pending expense for display."""
    parts = []
    parts.append(f"💰 *Monto:* ${pending.amount:,.2f}")

    if pending.method_name:
        parts.append(f"💳 *Método:* {pending.method_name}")

    if pending.vendor:
        parts.append(f"🏪 *Comercio:* {pending.vendor}")

    if pending.category_name:
        parts.append(f"📁 *Categoría:* {pending.category_name}")

    if pending.receipt_path:
        parts.append("📎 *Comprobante:* adjunto")

    return "\n".join(parts)


def _send_confirmation(bot: telebot.TeleBot, chat_id: int, pending: PendingExpense) -> None:
    """Send expense confirmation prompt as a NEW message."""
    text = msg("expense_confirmation_prompt") + "\n\n" + _format_expense_summary(pending)
    bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=confirmation_keyboard(),
    )


def register_handlers(bot: telebot.TeleBot) -> None:
    """Register all expense-related handlers."""

    @bot.message_handler(
        func=lambda m: (
            m.content_type == "text"
            and not m.text.startswith("/")
            and _is_authorized(m)
        ),
        content_types=["text"],
    )
    def handle_text_expense(message: Message) -> None:
        """Handle free-text expense input or follow-up answers."""
        user_id = message.from_user.id
        chat_id = message.chat.id
        text = message.text.strip()

        # Check if user has a pending expense awaiting more info
        pending = state.get_pending(user_id)

        if pending:
            _handle_pending_text(bot, message, pending, text)
            return

        # Try to parse as a new expense
        result = parse_expense_text(text)

        if result.amount is None:
            # Not a recognizable expense, ignore
            return

        # Create pending expense
        pending = PendingExpense(
            user_id=user_id,
            chat_id=chat_id,
            amount=result.amount,
            method_id=result.method_id,
            method_name=result.method_name,
            vendor=result.vendor,
        )

        # Try to classify vendor
        if result.vendor:
            cat_id, cat_name = get_classifier().classify(result.vendor)
            pending.category_id = cat_id
            pending.category_name = cat_name

        # Determine what's missing and set state
        if pending.method_id is None:
            pending.state = PendingState.AWAITING_METHOD
            state.set_pending(user_id, pending)
            methods = db.get_payment_methods()
            bot.send_message(
                chat_id,
                msg("ask_payment_method", amount=f"${pending.amount:,.2f}"),
                reply_markup=payment_methods_keyboard(methods),
            )
        elif pending.category_id is None:
            pending.state = PendingState.AWAITING_CATEGORY
            state.set_pending(user_id, pending)
            categories = db.get_categories()
            bot.send_message(
                chat_id,
                msg("ask_category", amount=f"${pending.amount:,.2f}", vendor=pending.vendor or ""),
                reply_markup=categories_keyboard(categories),
            )
        else:
            # All info available, ask for confirmation
            pending.state = PendingState.AWAITING_CONFIRMATION
            state.set_pending(user_id, pending)
            _send_confirmation(bot, chat_id, pending)

    def _handle_pending_text(
        bot: telebot.TeleBot, message: Message, pending: PendingExpense, text: str
    ) -> None:
        """Handle text input when user has a pending expense."""
        user_id = message.from_user.id
        chat_id = message.chat.id

        if pending.state == PendingState.AWAITING_VENDOR:
            pending.vendor = text
            # Try to classify
            cat_id, cat_name = get_classifier().classify(text)
            pending.category_id = cat_id
            pending.category_name = cat_name

            if pending.category_id is None:
                pending.state = PendingState.AWAITING_CATEGORY
                state.set_pending(user_id, pending)
                categories = db.get_categories()
                bot.send_message(
                    chat_id,
                    msg("ask_category", amount=f"${pending.amount:,.2f}", vendor=pending.vendor or ""),
                    reply_markup=categories_keyboard(categories),
                )
            else:
                pending.state = PendingState.AWAITING_CONFIRMATION
                state.set_pending(user_id, pending)
                _send_confirmation(bot, chat_id, pending)

        elif pending.state == PendingState.AWAITING_CONFIRMATION:
            # User sent text while awaiting confirmation - might be additional description
            # Ignore - they should use the buttons
            pass

    @bot.message_handler(
        func=lambda m: _is_authorized(m),
        content_types=["photo", "document"],
    )
    def handle_receipt(message: Message) -> None:
        """Handle receipt photo/document upload."""
        user_id = message.from_user.id
        chat_id = message.chat.id

        pending = state.get_pending(user_id)

        if pending is None:
            # Check if it's a photo with caption that could be an expense
            caption = message.caption
            if caption:
                result = parse_expense_text(caption)
                if result.amount is not None:
                    # Create a new pending expense from caption
                    pending = PendingExpense(
                        user_id=user_id,
                        chat_id=chat_id,
                        amount=result.amount,
                        method_id=result.method_id,
                        method_name=result.method_name,
                        vendor=result.vendor,
                    )
                    if result.vendor:
                        cat_id, cat_name = get_classifier().classify(result.vendor)
                        pending.category_id = cat_id
                        pending.category_name = cat_name

                    # Save the receipt
                    _save_receipt_to_pending(bot, message, pending)

                    # Continue flow
                    if pending.method_id is None:
                        pending.state = PendingState.AWAITING_METHOD
                        state.set_pending(user_id, pending)
                        methods = db.get_payment_methods()
                        bot.send_message(
                            chat_id,
                            msg("ask_payment_method", amount=f"${pending.amount:,.2f}"),
                            reply_markup=payment_methods_keyboard(methods),
                        )
                    elif pending.category_id is None:
                        pending.state = PendingState.AWAITING_CATEGORY
                        state.set_pending(user_id, pending)
                        categories = db.get_categories()
                        bot.send_message(
                            chat_id,
                            msg("ask_category", amount=f"${pending.amount:,.2f}", vendor=pending.vendor or ""),
                            reply_markup=categories_keyboard(categories),
                        )
                    else:
                        pending.state = PendingState.AWAITING_CONFIRMATION
                        state.set_pending(user_id, pending)
                        _send_confirmation(bot, chat_id, pending)
                    return
            # No pending and no parseable caption - ignore
            return

        # User has a pending expense - attach receipt
        if pending.state in (
            PendingState.AWAITING_RECEIPT,
            PendingState.AWAITING_CONFIRMATION,
        ):
            _save_receipt_to_pending(bot, message, pending)
            pending.state = PendingState.AWAITING_CONFIRMATION
            state.set_pending(user_id, pending)
            bot.send_message(chat_id, msg("receipt_attached"))
            _send_confirmation(bot, chat_id, pending)

    def _save_receipt_to_pending(
        bot: telebot.TeleBot, message: Message, pending: PendingExpense
    ) -> None:
        """Download and save a receipt file to the pending expense."""
        if message.content_type == "photo":
            # Get largest photo
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            extension = ".jpg"
            original_name = f"photo_{photo.file_id}.jpg"
        elif message.content_type == "document":
            doc = message.document
            file_info = bot.get_file(doc.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            extension = get_extension_from_mime(doc.mime_type)
            original_name = doc.file_name or f"document_{doc.file_id}{extension}"
        else:
            return

        expense_data = {
            "category_name": pending.category_name,
            "vendor": pending.vendor,
            "amount": pending.amount,
        }

        relative_path = save_receipt(file_bytes, extension, expense_data)
        pending.receipt_path = relative_path
        pending.original_filename = original_name

    @bot.callback_query_handler(func=lambda call: call.data == "exp_confirm")
    def handle_confirm(call: CallbackQuery) -> None:
        """Confirm and record the expense."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        pending = state.clear_pending(user_id)

        if not pending:
            bot.answer_callback_query(call.id, "No hay gasto pendiente.")
            return

        bot.answer_callback_query(call.id)

        # Record in database
        registered_by = call.from_user.first_name or "Unknown"
        expense_id = db.add_expense(
            amount=pending.amount,
            category_id=pending.category_id,
            payment_method_id=pending.method_id,
            vendor=pending.vendor,
            description=None,
            registered_by=registered_by,
            registered_by_id=user_id,
            receipt_path=pending.receipt_path,
            original_filename=pending.original_filename,
        )

        # Build confirmation message
        cat_str = f" | {pending.category_name}" if pending.category_name else ""
        method_str = f" | {pending.method_name}" if pending.method_name else ""
        vendor_str = f" | {pending.vendor}" if pending.vendor else ""
        receipt_str = " | 📎" if pending.receipt_path else ""

        text = msg(
            "expense_registered",
            id=expense_id,
            amount=f"${pending.amount:,.2f}",
            category=cat_str,
            method=method_str,
            vendor=vendor_str,
            receipt=receipt_str,
            user=registered_by,
        )

        # CRITICAL: Send as NEW message
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "exp_cancel")
    def handle_cancel(call: CallbackQuery) -> None:
        """Cancel the pending expense."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        state.clear_pending(user_id)
        bot.answer_callback_query(call.id)

        # CRITICAL: Send as NEW message
        bot.send_message(call.message.chat.id, msg("expense_cancelled"))

    @bot.callback_query_handler(func=lambda call: call.data == "exp_attach")
    def handle_attach(call: CallbackQuery) -> None:
        """Request receipt attachment."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        pending = state.get_pending(user_id)

        if not pending:
            bot.answer_callback_query(call.id, "No hay gasto pendiente.")
            return

        pending.state = PendingState.AWAITING_RECEIPT
        state.set_pending(user_id, pending)
        bot.answer_callback_query(call.id)

        # CRITICAL: Send as NEW message
        bot.send_message(call.message.chat.id, msg("ask_receipt"))

    @bot.callback_query_handler(func=lambda call: call.data == "exp_correct")
    def handle_correct(call: CallbackQuery) -> None:
        """Allow user to re-enter the expense."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        state.clear_pending(user_id)
        bot.answer_callback_query(call.id)

        # CRITICAL: Send as NEW message
        bot.send_message(call.message.chat.id, msg("expense_correct"))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("method_"))
    def handle_method_selection(call: CallbackQuery) -> None:
        """Handle payment method selection from inline keyboard."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        pending = state.get_pending(user_id)

        if not pending:
            bot.answer_callback_query(call.id, "No hay gasto pendiente.")
            return

        method_id = int(call.data.replace("method_", ""))
        method = db.get_payment_method(method_id)

        if not method:
            bot.answer_callback_query(call.id, "Método no encontrado.")
            return

        bot.answer_callback_query(call.id)

        pending.method_id = method_id
        pending.method_name = method["name"]

        # Check what's next
        if pending.category_id is None:
            pending.state = PendingState.AWAITING_CATEGORY
            state.set_pending(user_id, pending)
            categories = db.get_categories()
            bot.send_message(
                call.message.chat.id,
                msg("ask_category", amount=f"${pending.amount:,.2f}", vendor=pending.vendor or ""),
                reply_markup=categories_keyboard(categories),
            )
        else:
            pending.state = PendingState.AWAITING_CONFIRMATION
            state.set_pending(user_id, pending)
            _send_confirmation(bot, call.message.chat.id, pending)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
    def handle_category_selection(call: CallbackQuery) -> None:
        """Handle category selection from inline keyboard."""
        if not _is_authorized_callback(call):
            bot.answer_callback_query(call.id, msg("unauthorized"))
            return

        user_id = call.from_user.id
        pending = state.get_pending(user_id)

        if not pending:
            bot.answer_callback_query(call.id, "No hay gasto pendiente.")
            return

        category_id = int(call.data.replace("cat_", ""))
        category = db.get_category(category_id)

        if not category:
            bot.answer_callback_query(call.id, "Categoría no encontrada.")
            return

        bot.answer_callback_query(call.id)

        pending.category_id = category_id
        pending.category_name = category["name"]
        pending.state = PendingState.AWAITING_CONFIRMATION
        state.set_pending(user_id, pending)

        _send_confirmation(bot, call.message.chat.id, pending)
