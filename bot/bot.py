import os
import sqlite3
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    name TEXT,
                    phone TEXT,
                    address TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    category TEXT,
                    stock INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cart (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (user_id, product_id)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    total REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL
                )
                """
            )

            product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if product_count == 0:
                products = [
                    ("قهوة عربية", "قهوة عربية مميزة مع رائحة غنية", 18.0, "مشروبات", 20),
                    ("شاي أخضر", "شاي أخضر طبيعي مع نكهات لطيفة", 15.0, "مشروبات", 30),
                    ("كيك الشوكولاتة", "كيك دسم بنكهة الشوكولاتة", 22.0, "حلويات", 15),
                    ("كب كيك", "كب كيك صغير ومناسب للوجبات الخفيفة", 12.0, "حلويات", 25),
                    ("سندويتش لحم", "سندويتش لحم مع سلطة", 28.0, "وجبات", 12),
                    ("ميني شاورما", "شاورما صغير بمذاق رائع", 20.0, "وجبات", 18),
                ]
                conn.executemany(
                    "INSERT INTO products (name, description, price, category, stock) VALUES (?, ?, ?, ?, ?)",
                    products,
                )

    def get_or_create_user(self, telegram_id: int, name: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET name = ? WHERE telegram_id = ?",
                    (name, telegram_id),
                )
                return int(row["id"])

            cursor = conn.execute(
                "INSERT INTO users (telegram_id, name) VALUES (?, ?)",
                (telegram_id, name),
            )
            return int(cursor.lastrowid)

    def get_user(self, telegram_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()

    def save_user_contact(self, telegram_id: int, phone: str, address: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET phone = ?, address = ? WHERE telegram_id = ?",
                (phone, address, telegram_id),
            )

    def get_products(self) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM products WHERE active = 1 ORDER BY id DESC"
            ).fetchall()

    def get_product(self, product_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM products WHERE id = ? AND active = 1",
                (product_id,),
            ).fetchone()

    def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ).fetchone()
            if existing:
                new_qty = int(existing["quantity"]) + quantity
                conn.execute(
                    "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                    (new_qty, user_id, product_id),
                )
            else:
                conn.execute(
                    "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
                    (user_id, product_id, quantity),
                )

    def get_cart(self, user_id: int) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT c.product_id, c.quantity, p.name, p.price, p.stock
                FROM cart c
                JOIN products p ON p.id = c.product_id
                WHERE c.user_id = ?
                ORDER BY p.name ASC
                """,
                (user_id,),
            ).fetchall()

    def change_cart_quantity(self, user_id: int, product_id: int, delta: int) -> None:
        with self._connect() as conn:
            current = conn.execute(
                "SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ).fetchone()
            if not current:
                return

            new_qty = int(current["quantity"]) + delta
            if new_qty <= 0:
                conn.execute(
                    "DELETE FROM cart WHERE user_id = ? AND product_id = ?",
                    (user_id, product_id),
                )
            else:
                conn.execute(
                    "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                    (new_qty, user_id, product_id),
                )

    def remove_from_cart(self, user_id: int, product_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM cart WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )

    def clear_cart(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))

    def create_order(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cart_items = conn.execute(
                """
                SELECT c.product_id, c.quantity, p.name, p.price, p.stock
                FROM cart c
                JOIN products p ON p.id = c.product_id
                WHERE c.user_id = ?
                """,
                (user_id,),
            ).fetchall()

            if not cart_items:
                return None

            total = 0.0
            for row in cart_items:
                total += float(row["price"]) * int(row["quantity"])

            order_id = conn.execute(
                "INSERT INTO orders (user_id, total, status) VALUES (?, ?, 'pending')",
                (user_id, total),
            ).lastrowid

            for row in cart_items:
                product_id = int(row["product_id"])
                quantity = int(row["quantity"])
                price = float(row["price"])
                conn.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                    (order_id, product_id, quantity, price),
                )
                conn.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product_id),
                )

            conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            return {"order_id": int(order_id), "total": total}

    def get_orders(self, limit: int = 10) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT o.id, o.user_id, o.total, o.status, o.created_at,
                       u.name, u.phone, u.address
                FROM orders o
                JOIN users u ON u.id = o.user_id
                ORDER BY o.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def add_product(self, name: str, description: str, price: float, category: str, stock: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO products (name, description, price, category, stock) VALUES (?, ?, ?, ?, ?)",
                (name, description, price, category, stock),
            )
            return int(cursor.lastrowid)

    def get_order_items(self, order_id: int) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT oi.product_id, oi.quantity, oi.price, p.name
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id = ?
                """,
                (order_id,),
            ).fetchall()
