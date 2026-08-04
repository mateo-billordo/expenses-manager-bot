"""Inline keyboard builders for the expense bot."""

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirmation_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for confirming a parsed expense."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Confirmar", callback_data="exp_confirm"),
        InlineKeyboardButton("📎 Adjuntar", callback_data="exp_attach"),
        InlineKeyboardButton("✏️ Corregir", callback_data="exp_correct"),
        InlineKeyboardButton("❌ Cancelar", callback_data="exp_cancel"),
    )
    return kb


def payment_methods_keyboard(methods: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for selecting a payment method."""
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(
            f"{m['emoji']} {m['name']}", callback_data=f"method_{m['id']}"
        )
        for m in methods
    ]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("❌ Cancelar", callback_data="exp_cancel"))
    return kb


def categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for selecting a category."""
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(
            f"{c['emoji']} {c['name']}", callback_data=f"cat_{c['id']}"
        )
        for c in categories
    ]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("❌ Cancelar", callback_data="exp_cancel"))
    return kb


def export_format_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for export format selection."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📄 CSV", callback_data="export_csv"),
        InlineKeyboardButton("📦 CSV + Comprobantes", callback_data="export_zip"),
    )
    return kb


def admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin configuration main menu."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💳 Métodos de pago", callback_data="admin_methods"),
        InlineKeyboardButton("📁 Categorías", callback_data="admin_categories"),
        InlineKeyboardButton("🔑 Keywords", callback_data="admin_keywords"),
        InlineKeyboardButton("💾 Backup", callback_data="admin_backup"),
    )
    return kb


def admin_categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Admin keyboard to manage categories."""
    kb = InlineKeyboardMarkup(row_width=1)
    for c in categories:
        kb.add(
            InlineKeyboardButton(
                f"{c['emoji']} {c['name']}", callback_data=f"admin_cat_{c['id']}"
            )
        )
    kb.add(
        InlineKeyboardButton("➕ Agregar categoría", callback_data="admin_cat_add"),
        InlineKeyboardButton("⬅️ Volver", callback_data="admin_back"),
    )
    return kb


def admin_methods_keyboard(methods: list[dict]) -> InlineKeyboardMarkup:
    """Admin keyboard to manage payment methods."""
    kb = InlineKeyboardMarkup(row_width=1)
    for m in methods:
        kb.add(
            InlineKeyboardButton(
                f"{m['emoji']} {m['name']}", callback_data=f"admin_meth_{m['id']}"
            )
        )
    kb.add(
        InlineKeyboardButton("➕ Agregar método", callback_data="admin_meth_add"),
        InlineKeyboardButton("⬅️ Volver", callback_data="admin_back"),
    )
    return kb


def admin_keywords_by_category_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Admin keyboard to select category for keyword management."""
    kb = InlineKeyboardMarkup(row_width=1)
    for c in categories:
        kb.add(
            InlineKeyboardButton(
                f"{c['emoji']} {c['name']}", callback_data=f"admin_kw_cat_{c['id']}"
            )
        )
    kb.add(InlineKeyboardButton("⬅️ Volver", callback_data="admin_back"))
    return kb


def admin_category_detail_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard for a single category's actions."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ Editar", callback_data=f"admin_cat_edit_{category_id}"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"admin_cat_del_{category_id}"),
        InlineKeyboardButton("⬅️ Volver", callback_data="admin_categories"),
    )
    return kb


def admin_method_detail_keyboard(method_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard for a single payment method's actions."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ Editar", callback_data=f"admin_meth_edit_{method_id}"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"admin_meth_del_{method_id}"),
        InlineKeyboardButton("⬅️ Volver", callback_data="admin_methods"),
    )
    return kb


def admin_keyword_actions_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard for keyword actions within a category."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Agregar keyword", callback_data=f"admin_kw_add_{category_id}"),
        InlineKeyboardButton("🗑️ Eliminar keyword", callback_data=f"admin_kw_del_{category_id}"),
        InlineKeyboardButton("⬅️ Volver", callback_data="admin_keywords"),
    )
    return kb
