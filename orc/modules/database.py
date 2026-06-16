from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "bills.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL DEFAULT 'Unknown',
    amount REAL NOT NULL DEFAULT 0,
    tax REAL DEFAULT 0,
    date TEXT,
    category TEXT NOT NULL DEFAULT 'Other',
    invoice_number TEXT,
    image_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    raw_text TEXT,
    ocr_confidence REAL DEFAULT 0,
    payment_method TEXT,
    extraction_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(date);
CREATE INDEX IF NOT EXISTS idx_bills_category ON bills(category);
CREATE INDEX IF NOT EXISTS idx_bills_vendor ON bills(vendor);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def get_connection(db_path: Path = DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_bill(
    vendor: str,
    amount: float,
    tax: float,
    date: str | None,
    category: str,
    invoice_number: str | None,
    image_path: str,
    raw_text: str,
    ocr_confidence: float,
    payment_method: str | None,
    extraction_json: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bills (vendor, amount, tax, date, category, invoice_number, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vendor or "Unknown", amount or 0, tax or 0, date, category or "Other", invoice_number, image_path),
        )
        bill_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO expense_summary
                (bill_id, raw_text, ocr_confidence, payment_method, extraction_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (bill_id, raw_text, ocr_confidence, payment_method, extraction_json),
        )
        return bill_id


def get_bills(
    search: str = "",
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    query = """
        SELECT
            b.id, b.vendor, b.amount, b.tax, b.date, b.category,
            b.invoice_number, b.image_path, b.created_at, b.updated_at,
            s.raw_text, s.ocr_confidence, s.payment_method
        FROM bills b
        LEFT JOIN expense_summary s ON s.bill_id = b.id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if search:
        query += " AND (LOWER(b.vendor) LIKE ? OR LOWER(b.invoice_number) LIKE ? OR LOWER(s.raw_text) LIKE ?)"
        like = f"%{search.lower()}%"
        params.extend([like, like, like])
    if category and category != "All":
        query += " AND b.category = ?"
        params.append(category)
    if start_date:
        query += " AND date(b.date) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(b.date) <= date(?)"
        params.append(end_date)
    query += " ORDER BY COALESCE(date(b.date), date(b.created_at)) DESC, b.id DESC"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_bill(bill_id: int) -> dict[str, Any] | None:
    df = get_bills()
    if df.empty:
        return None
    row = df[df["id"] == bill_id]
    return None if row.empty else row.iloc[0].to_dict()


def update_bill(bill_id: int, values: dict[str, Any]) -> None:
    allowed = {"vendor", "amount", "tax", "date", "category", "invoice_number", "image_path"}
    bill_values = {key: values[key] for key in values if key in allowed}
    summary_values = {key: values[key] for key in values if key in {"raw_text", "ocr_confidence", "payment_method"}}
    with get_connection() as conn:
        if bill_values:
            assignments = ", ".join(f"{key} = ?" for key in bill_values)
            params = list(bill_values.values()) + [bill_id]
            conn.execute(f"UPDATE bills SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params)
        if summary_values:
            assignments = ", ".join(f"{key} = ?" for key in summary_values)
            params = list(summary_values.values()) + [bill_id]
            conn.execute(f"UPDATE expense_summary SET {assignments} WHERE bill_id = ?", params)


def delete_bill(bill_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))


def clear_all() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM expense_summary")
        conn.execute("DELETE FROM bills")


def database_schema() -> str:
    return SCHEMA_SQL.strip()

