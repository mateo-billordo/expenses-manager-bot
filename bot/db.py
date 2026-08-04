"""SQLite database layer for expenses bot."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

from bot.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    emoji TEXT DEFAULT '📁'
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    emoji TEXT DEFAULT '💳',
    aliases TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'ARS',
    category_id INTEGER REFERENCES categories(id),
    payment_method_id INTEGER REFERENCES payment_methods(id),
    vendor TEXT,
    description TEXT,
    registered_by TEXT NOT NULL,
    registered_by_id INTEGER NOT NULL,
    receipt_path TEXT,
    original_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed INTEGER DEFAULT 1
);
"""

_DEFAULT_CATEGORIES = [
    ("Alimentación", "🛒", ["supermercado", "carrefour", "coto", "dia", "chino", "almacen", "verduleria", "kiosco"]),
    ("Transporte", "🚗", ["nafta", "sube", "uber", "taxi", "peaje", "estacionamiento", "gnc", "cabify"]),
    ("Hogar", "🏠", ["luz", "gas", "agua", "internet", "alquiler", "expensas", "limpieza", "ferreteria"]),
    ("Salud", "🏥", ["farmacia", "medico", "obra social", "odontologo", "analisis", "hospital"]),
    ("Entretenimiento", "🎬", ["cine", "netflix", "spotify", "restaurant", "bar", "delivery", "rappi", "pedidosya", "cerveza"]),
    ("Ropa", "👕", ["ropa", "zapatillas", "zara", "remera", "pantalon"]),
    ("Educación", "📚", ["curso", "libro", "universidad", "colegio", "capacitacion"]),
    ("Mascotas", "🐾", ["veterinaria", "alimento mascota", "petshop"]),
    ("Otros", "📦", []),
]

_DEFAULT_METHODS = [
    ("Efectivo", "💵", "efectivo,cash,efec"),
    ("Cuenta compartida", "🏦", "compartida,cuenta"),
    ("Débito Mateo", "💳", "debito,débito"),
    ("Crédito Mateo", "💳", "credito,crédito,tarjeta"),
]


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database schema and seed default data."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)

        # Check if categories already exist
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            for name, emoji, keywords in _DEFAULT_CATEGORIES:
                cursor = conn.execute(
                    "INSERT INTO categories (name, emoji) VALUES (?, ?)",
                    (name, emoji),
                )
                cat_id = cursor.lastrowid
                for kw in keywords:
                    conn.execute(
                        "INSERT INTO keywords (keyword, category_id) VALUES (?, ?)",
                        (kw, cat_id),
                    )

        # Check if payment methods already exist
        count = conn.execute("SELECT COUNT(*) FROM payment_methods").fetchone()[0]
        if count == 0:
            for name, emoji, aliases in _DEFAULT_METHODS:
                conn.execute(
                    "INSERT INTO payment_methods (name, emoji, aliases) VALUES (?, ?, ?)",
                    (name, emoji, aliases),
                )


# --- Category operations ---


def get_categories() -> list[dict]:
    """Get all categories."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, emoji FROM categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_category(category_id: int) -> Optional[dict]:
    """Get a single category by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT id, name, emoji FROM categories WHERE id = ?", (category_id,)).fetchone()
        return dict(row) if row else None


def add_category(name: str, emoji: str = "📁") -> int:
    """Add a new category and return its ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO categories (name, emoji) VALUES (?, ?)", (name, emoji)
        )
        return cursor.lastrowid


def update_category(category_id: int, name: str, emoji: str) -> None:
    """Update a category."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE categories SET name = ?, emoji = ? WHERE id = ?",
            (name, emoji, category_id),
        )


def delete_category(category_id: int) -> None:
    """Delete a category (keywords cascade)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


# --- Keyword operations ---


def get_keywords(category_id: Optional[int] = None) -> list[dict]:
    """Get keywords, optionally filtered by category."""
    with get_connection() as conn:
        if category_id:
            rows = conn.execute(
                "SELECT k.id, k.keyword, k.category_id, c.name as category_name "
                "FROM keywords k JOIN categories c ON k.category_id = c.id "
                "WHERE k.category_id = ? ORDER BY k.keyword",
                (category_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT k.id, k.keyword, k.category_id, c.name as category_name "
                "FROM keywords k JOIN categories c ON k.category_id = c.id "
                "ORDER BY c.name, k.keyword"
            ).fetchall()
        return [dict(r) for r in rows]


def add_keyword(keyword: str, category_id: int) -> int:
    """Add a keyword to a category."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO keywords (keyword, category_id) VALUES (?, ?)",
            (keyword, category_id),
        )
        return cursor.lastrowid


def delete_keyword(keyword_id: int) -> None:
    """Delete a keyword."""
    with get_connection() as conn:
        conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))


# --- Payment method operations ---


def get_payment_methods() -> list[dict]:
    """Get all payment methods."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, emoji, aliases FROM payment_methods ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_payment_method(method_id: int) -> Optional[dict]:
    """Get a single payment method by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, emoji, aliases FROM payment_methods WHERE id = ?",
            (method_id,),
        ).fetchone()
        return dict(row) if row else None


def add_payment_method(name: str, emoji: str = "💳", aliases: str = "") -> int:
    """Add a new payment method."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO payment_methods (name, emoji, aliases) VALUES (?, ?, ?)",
            (name, emoji, aliases),
        )
        return cursor.lastrowid


def update_payment_method(method_id: int, name: str, emoji: str, aliases: str) -> None:
    """Update a payment method."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE payment_methods SET name = ?, emoji = ?, aliases = ? WHERE id = ?",
            (name, emoji, aliases, method_id),
        )


def delete_payment_method(method_id: int) -> None:
    """Delete a payment method."""
    with get_connection() as conn:
        conn.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))


# --- Expense operations ---


def add_expense(
    amount: float,
    category_id: Optional[int],
    payment_method_id: Optional[int],
    vendor: Optional[str],
    description: Optional[str],
    registered_by: str,
    registered_by_id: int,
    receipt_path: Optional[str] = None,
    original_filename: Optional[str] = None,
    currency: str = "ARS",
) -> int:
    """Record a confirmed expense."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO expenses "
            "(amount, currency, category_id, payment_method_id, vendor, description, "
            "registered_by, registered_by_id, receipt_path, original_filename) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                amount,
                currency,
                category_id,
                payment_method_id,
                vendor,
                description,
                registered_by,
                registered_by_id,
                receipt_path,
                original_filename,
            ),
        )
        return cursor.lastrowid


def get_expenses_by_date_range(
    start_date: str, end_date: str
) -> list[dict]:
    """Get expenses within a date range (inclusive)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as category_name, c.emoji as category_emoji, "
            "m.name as method_name, m.emoji as method_emoji "
            "FROM expenses e "
            "LEFT JOIN categories c ON e.category_id = c.id "
            "LEFT JOIN payment_methods m ON e.payment_method_id = m.id "
            "WHERE date(e.created_at) >= date(?) AND date(e.created_at) <= date(?) "
            "ORDER BY e.created_at DESC",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]


def get_monthly_summary(year: int, month: int) -> list[dict]:
    """Get expense totals grouped by category for a given month."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.name, c.emoji, SUM(e.amount) as total, COUNT(*) as count "
            "FROM expenses e "
            "LEFT JOIN categories c ON e.category_id = c.id "
            "WHERE e.created_at >= ? AND e.created_at < ? "
            "GROUP BY e.category_id "
            "ORDER BY total DESC",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]


def get_last_expenses(limit: int = 5) -> list[dict]:
    """Get last N expenses."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*, c.name as category_name, c.emoji as category_emoji, "
            "m.name as method_name, m.emoji as method_emoji "
            "FROM expenses e "
            "LEFT JOIN categories c ON e.category_id = c.id "
            "LEFT JOIN payment_methods m ON e.payment_method_id = m.id "
            "ORDER BY e.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_monthly_total(year: int, month: int) -> float:
    """Get total expenses for a month."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM expenses "
            "WHERE created_at >= ? AND created_at < ?",
            (start, end),
        ).fetchone()
        return row[0]
