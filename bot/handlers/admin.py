"""Admin configuration handlers (DM only)."""

import telebot
from telebot.types import CallbackQuery, Message

from bot import db
from bot.classifier import refresh_classifier
from bot.config import ADMIN_ID, DB_PATH, msg
from bot.keyboards import (
    admin_categories_keyboard,
    admin_category_detail_keyboard,
    admin_keyword_actions_keyboard,
    admin_keywords_by_category_keyboard,
    admin_main_keyboard,
    admin_method_detail_keyboard,
    admin_methods_keyboard,
)


def _is_admin_dm(message: Message) -> bool:
    """Check if message is from admin in DM."""
    return (
        message.from_user.id == ADMIN_ID
        and message.chat.id == ADMIN_ID
        and message.chat.type == "private"
    )


def _is_admin_callback(call: CallbackQuery) -> bool:
    """Check if callback is from admin in DM."""
    return (
        call.from_user.id == ADMIN_ID
        and call.message.chat.id == ADMIN_ID
        and call.message.chat.type == "private"
    )


# Tracks admin conversational state for multi-step operations
_admin_state: dict[str, object] = {}


def register_handlers(bot: telebot.TeleBot) -> None:
    """Register admin-only command and callback handlers."""

    @bot.message_handler(commands=["config"], func=_is_admin_dm)
    def handle_config(message: Message) -> None:
        """Show admin configuration menu."""
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            msg("admin_welcome"),
            reply_markup=admin_main_keyboard(),
        )

    @bot.message_handler(commands=["backup"], func=_is_admin_dm)
    def handle_backup(message: Message) -> None:
        """Send database file as backup."""
        if DB_PATH.exists():
            with open(DB_PATH, "rb") as f:
                bot.send_document(
                    message.chat.id,
                    f,
                    visible_file_name="expenses_backup.db",
                    caption=msg("backup_sent"),
                )
        else:
            bot.send_message(message.chat.id, "❌ Base de datos no encontrada.")

    # --- Admin callback handlers ---

    @bot.callback_query_handler(func=lambda call: call.data == "admin_back" and _is_admin_callback(call))
    def handle_admin_back(call: CallbackQuery) -> None:
        """Go back to admin main menu."""
        _admin_state.clear()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            msg("admin_welcome"),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=admin_main_keyboard(),
        )

    # --- Categories ---

    @bot.callback_query_handler(func=lambda call: call.data == "admin_categories" and _is_admin_callback(call))
    def handle_admin_categories(call: CallbackQuery) -> None:
        """Show categories list."""
        bot.answer_callback_query(call.id)
        categories = db.get_categories()
        text = msg("admin_categories_list") + "\n\n"
        for c in categories:
            text += f"{c['emoji']} {c['name']}\n"

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=admin_categories_keyboard(categories),
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_") and not call.data.startswith("admin_cat_add") and not call.data.startswith("admin_cat_edit_") and not call.data.startswith("admin_cat_del_") and _is_admin_callback(call))
    def handle_admin_category_detail(call: CallbackQuery) -> None:
        """Show detail for a specific category."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_cat_", ""))
        category = db.get_category(category_id)

        if not category:
            bot.answer_callback_query(call.id, "Categoría no encontrada.")
            return

        keywords = db.get_keywords(category_id)
        kw_text = ", ".join(k["keyword"] for k in keywords) if keywords else "Sin keywords"

        text = (
            f"{category['emoji']} *{category['name']}*\n\n"
            f"🔑 Keywords: {kw_text}"
        )

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_category_detail_keyboard(category_id),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_cat_add" and _is_admin_callback(call))
    def handle_admin_cat_add(call: CallbackQuery) -> None:
        """Prompt to add a new category."""
        bot.answer_callback_query(call.id)
        _admin_state["action"] = "add_category"
        bot.edit_message_text(
            "📁 Enviá el nombre de la nueva categoría.\n"
            "Formato: `nombre emoji`\n"
            "Ejemplo: `Viajes ✈️`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_edit_") and _is_admin_callback(call))
    def handle_admin_cat_edit(call: CallbackQuery) -> None:
        """Prompt to edit a category."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_cat_edit_", ""))
        _admin_state["action"] = "edit_category"
        _admin_state["category_id"] = category_id
        category = db.get_category(category_id)
        bot.edit_message_text(
            f"✏️ Editando: {category['emoji']} {category['name']}\n\n"
            "Enviá el nuevo nombre y emoji.\n"
            "Formato: `nombre emoji`\n"
            "Ejemplo: `Viajes ✈️`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_del_") and _is_admin_callback(call))
    def handle_admin_cat_del(call: CallbackQuery) -> None:
        """Delete a category."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_cat_del_", ""))
        category = db.get_category(category_id)

        if category:
            db.delete_category(category_id)
            refresh_classifier()
            bot.edit_message_text(
                f"🗑️ Categoría '{category['name']}' eliminada.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_main_keyboard(),
            )
        else:
            bot.edit_message_text(
                "❌ Categoría no encontrada.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_main_keyboard(),
            )

    # --- Payment Methods ---

    @bot.callback_query_handler(func=lambda call: call.data == "admin_methods" and _is_admin_callback(call))
    def handle_admin_methods(call: CallbackQuery) -> None:
        """Show payment methods list."""
        bot.answer_callback_query(call.id)
        methods = db.get_payment_methods()
        text = msg("admin_methods_list") + "\n\n"
        for m in methods:
            aliases = m.get("aliases", "")
            text += f"{m['emoji']} {m['name']}"
            if aliases:
                text += f" ({aliases})"
            text += "\n"

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=admin_methods_keyboard(methods),
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_meth_") and not call.data.startswith("admin_meth_add") and not call.data.startswith("admin_meth_edit_") and not call.data.startswith("admin_meth_del_") and _is_admin_callback(call))
    def handle_admin_method_detail(call: CallbackQuery) -> None:
        """Show detail for a specific payment method."""
        bot.answer_callback_query(call.id)
        method_id = int(call.data.replace("admin_meth_", ""))
        method = db.get_payment_method(method_id)

        if not method:
            return

        aliases = method.get("aliases", "") or "Sin aliases"
        text = (
            f"{method['emoji']} *{method['name']}*\n\n"
            f"🔤 Aliases: {aliases}"
        )

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_method_detail_keyboard(method_id),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_meth_add" and _is_admin_callback(call))
    def handle_admin_meth_add(call: CallbackQuery) -> None:
        """Prompt to add a new payment method."""
        bot.answer_callback_query(call.id)
        _admin_state["action"] = "add_method"
        bot.edit_message_text(
            "💳 Enviá los datos del nuevo método de pago.\n"
            "Formato: `nombre | emoji | alias1,alias2`\n"
            "Ejemplo: `MercadoPago | 📱 | mercadopago,mp`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_meth_edit_") and _is_admin_callback(call))
    def handle_admin_meth_edit(call: CallbackQuery) -> None:
        """Prompt to edit a payment method."""
        bot.answer_callback_query(call.id)
        method_id = int(call.data.replace("admin_meth_edit_", ""))
        _admin_state["action"] = "edit_method"
        _admin_state["method_id"] = method_id
        method = db.get_payment_method(method_id)
        bot.edit_message_text(
            f"✏️ Editando: {method['emoji']} {method['name']}\n\n"
            "Enviá los nuevos datos.\n"
            "Formato: `nombre | emoji | alias1,alias2`\n"
            "Ejemplo: `MercadoPago | 📱 | mercadopago,mp`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_meth_del_") and _is_admin_callback(call))
    def handle_admin_meth_del(call: CallbackQuery) -> None:
        """Delete a payment method."""
        bot.answer_callback_query(call.id)
        method_id = int(call.data.replace("admin_meth_del_", ""))
        method = db.get_payment_method(method_id)

        if method:
            db.delete_payment_method(method_id)
            bot.edit_message_text(
                f"🗑️ Método '{method['name']}' eliminado.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_main_keyboard(),
            )
        else:
            bot.edit_message_text(
                "❌ Método no encontrado.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_main_keyboard(),
            )

    # --- Keywords ---

    @bot.callback_query_handler(func=lambda call: call.data == "admin_keywords" and _is_admin_callback(call))
    def handle_admin_keywords(call: CallbackQuery) -> None:
        """Show categories for keyword management."""
        bot.answer_callback_query(call.id)
        categories = db.get_categories()
        bot.edit_message_text(
            msg("admin_keywords_list"),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=admin_keywords_by_category_keyboard(categories),
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_kw_cat_") and _is_admin_callback(call))
    def handle_admin_kw_category(call: CallbackQuery) -> None:
        """Show keywords for a specific category."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_kw_cat_", ""))
        category = db.get_category(category_id)
        keywords = db.get_keywords(category_id)

        kw_list = ", ".join(k["keyword"] for k in keywords) if keywords else "Sin keywords"
        text = f"🔑 Keywords de *{category['emoji']} {category['name']}*:\n\n{kw_list}"

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_keyword_actions_keyboard(category_id),
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_kw_add_") and _is_admin_callback(call))
    def handle_admin_kw_add(call: CallbackQuery) -> None:
        """Prompt to add a keyword."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_kw_add_", ""))
        _admin_state["action"] = "add_keyword"
        _admin_state["category_id"] = category_id
        category = db.get_category(category_id)
        bot.edit_message_text(
            f"🔑 Enviá el keyword para *{category['name']}*.\n"
            "Podés enviar varios separados por coma.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_kw_del_") and _is_admin_callback(call))
    def handle_admin_kw_del(call: CallbackQuery) -> None:
        """Prompt to delete a keyword."""
        bot.answer_callback_query(call.id)
        category_id = int(call.data.replace("admin_kw_del_", ""))
        keywords = db.get_keywords(category_id)

        if not keywords:
            bot.edit_message_text(
                "No hay keywords para eliminar.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_main_keyboard(),
            )
            return

        _admin_state["action"] = "delete_keyword"
        _admin_state["category_id"] = category_id

        text = "🗑️ Enviá el keyword a eliminar:\n\n"
        for kw in keywords:
            text += f"• {kw['keyword']}\n"

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_backup" and _is_admin_callback(call))
    def handle_admin_backup_callback(call: CallbackQuery) -> None:
        """Send backup via callback."""
        bot.answer_callback_query(call.id)
        if DB_PATH.exists():
            with open(DB_PATH, "rb") as f:
                bot.send_document(
                    call.message.chat.id,
                    f,
                    visible_file_name="expenses_backup.db",
                    caption=msg("backup_sent"),
                )
        else:
            bot.send_message(call.message.chat.id, "❌ Base de datos no encontrada.")

    # --- Admin text handler for multi-step actions ---

    @bot.message_handler(func=lambda m: _is_admin_dm(m) and "action" in _admin_state and not m.text.startswith("/"))
    def handle_admin_text(message: Message) -> None:
        """Handle admin text input for multi-step operations."""
        action = _admin_state.get("action")
        text = message.text.strip()

        if action == "add_category":
            _process_add_category(bot, message, text)
        elif action == "edit_category":
            _process_edit_category(bot, message, text)
        elif action == "add_method":
            _process_add_method(bot, message, text)
        elif action == "edit_method":
            _process_edit_method(bot, message, text)
        elif action == "add_keyword":
            _process_add_keyword(bot, message, text)
        elif action == "delete_keyword":
            _process_delete_keyword(bot, message, text)


def _process_add_category(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process adding a new category."""
    parts = text.rsplit(" ", 1)
    name = parts[0].strip()
    emoji = parts[1].strip() if len(parts) > 1 else "📁"

    # Check if emoji is actually an emoji (basic check)
    if len(emoji) > 4 or emoji.isalnum():
        name = text
        emoji = "📁"

    try:
        db.add_category(name, emoji)
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            f"✅ Categoría *{emoji} {name}* agregada.",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")


def _process_edit_category(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process editing a category."""
    category_id = _admin_state.get("category_id")
    parts = text.rsplit(" ", 1)
    name = parts[0].strip()
    emoji = parts[1].strip() if len(parts) > 1 else "📁"

    if len(emoji) > 4 or emoji.isalnum():
        name = text
        emoji = "📁"

    try:
        db.update_category(category_id, name, emoji)
        refresh_classifier()
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            f"✅ Categoría actualizada: *{emoji} {name}*",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")


def _process_add_method(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process adding a new payment method."""
    parts = [p.strip() for p in text.split("|")]

    if len(parts) >= 3:
        name, emoji, aliases = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        name, emoji = parts[0], parts[1]
        aliases = name.lower()
    else:
        name = text
        emoji = "💳"
        aliases = name.lower()

    try:
        db.add_payment_method(name, emoji, aliases)
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            f"✅ Método *{emoji} {name}* agregado.",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")


def _process_edit_method(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process editing a payment method."""
    method_id = _admin_state.get("method_id")
    parts = [p.strip() for p in text.split("|")]

    if len(parts) >= 3:
        name, emoji, aliases = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        name, emoji = parts[0], parts[1]
        aliases = name.lower()
    else:
        name = text
        emoji = "💳"
        aliases = name.lower()

    try:
        db.update_payment_method(method_id, name, emoji, aliases)
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            f"✅ Método actualizado: *{emoji} {name}*",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")


def _process_add_keyword(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process adding keywords."""
    category_id = _admin_state.get("category_id")
    keywords = [kw.strip().lower() for kw in text.split(",") if kw.strip()]

    added = []
    for kw in keywords:
        db.add_keyword(kw, category_id)
        added.append(kw)

    refresh_classifier()
    _admin_state.clear()

    category = db.get_category(category_id)
    bot.send_message(
        message.chat.id,
        f"✅ Keywords agregados a *{category['name']}*: {', '.join(added)}",
        parse_mode="Markdown",
        reply_markup=admin_main_keyboard(),
    )


def _process_delete_keyword(bot: telebot.TeleBot, message: Message, text: str) -> None:
    """Process deleting a keyword."""
    category_id = _admin_state.get("category_id")
    keyword_text = text.strip().lower()

    keywords = db.get_keywords(category_id)
    found = None
    for kw in keywords:
        if kw["keyword"].lower() == keyword_text:
            found = kw
            break

    if found:
        db.delete_keyword(found["id"])
        refresh_classifier()
        _admin_state.clear()
        bot.send_message(
            message.chat.id,
            f"✅ Keyword '{found['keyword']}' eliminado.",
            reply_markup=admin_main_keyboard(),
        )
    else:
        bot.send_message(message.chat.id, f"❌ Keyword '{keyword_text}' no encontrado. Intentá de nuevo.")
