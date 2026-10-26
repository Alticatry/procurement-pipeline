import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "procurement.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


@contextmanager
def connection(db_path=None):
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None):
    with connection(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _ensure_supplier_and_product(conn, offer):
    supplier = str(offer["supplier"]).strip()
    product = str(offer["product"]).strip()
    unit = str(offer.get("unit") or "").strip()
    conn.execute("INSERT OR IGNORE INTO suppliers (name) VALUES (?)", (supplier,))
    conn.execute(
        "INSERT OR IGNORE INTO products (name, unit) VALUES (?, ?)",
        (product, unit),
    )
    return supplier, product


def save_offers(offers, source_text="", db_path=None):
    with connection(db_path) as conn:
        for offer in offers:
            supplier, product = _ensure_supplier_and_product(conn, offer)
            conn.execute(
                """
                INSERT INTO offers
                    (supplier_id, product_id, quantity, unit_price, delivery_days, source_text)
                VALUES (
                    (SELECT id FROM suppliers WHERE name = ?),
                    (SELECT id FROM products WHERE name = ?),
                    ?, ?, ?, ?
                )
                """,
                (
                    supplier,
                    product,
                    float(offer["quantity"]),
                    float(offer["unit_price"]),
                    int(offer["delivery_days"]),
                    source_text,
                ),
            )
    return len(offers)


def get_offers(product=None, db_path=None):
    query = """
        SELECT o.id, s.name AS supplier, p.name AS product, p.unit AS unit,
               o.quantity, o.unit_price, o.delivery_days, o.created_at
        FROM offers o
        JOIN suppliers s ON s.id = o.supplier_id
        JOIN products p ON p.id = o.product_id
    """
    params = ()
    if product:
        query += " WHERE p.name = ?"
        params = (product,)
    query += " ORDER BY o.id DESC"
    with connection(db_path) as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def save_purchase_order(offer, channel, draft_text, db_path=None):
    quantity = float(offer["quantity"])
    unit_price = float(offer["unit_price"])
    with connection(db_path) as conn:
        supplier, product = _ensure_supplier_and_product(conn, offer)
        cursor = conn.execute(
            """
            INSERT INTO purchase_orders
                (supplier_id, product_id, quantity, unit_price, total_price, channel, draft_text)
            VALUES (
                (SELECT id FROM suppliers WHERE name = ?),
                (SELECT id FROM products WHERE name = ?),
                ?, ?, ?, ?, ?
            )
            """,
            (supplier, product, quantity, unit_price, quantity * unit_price, channel, draft_text),
        )
        return cursor.lastrowid


def get_purchase_orders(db_path=None):
    query = """
        SELECT po.id, s.name AS supplier, p.name AS product, po.quantity,
               po.unit_price, po.total_price, po.channel, po.draft_text, po.created_at
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN products p ON p.id = po.product_id
        ORDER BY po.id DESC
    """
    with connection(db_path) as conn:
        return [dict(row) for row in conn.execute(query).fetchall()]
