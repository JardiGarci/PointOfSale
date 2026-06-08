import tkinter as tk
from tkinter import ttk, messagebox

import sqlite3
import numpy as np
import os
import io
import platform
import subprocess
import calendar
import logging
import traceback
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════════
# Registro de errores  →  DATA/pos_errors.log
# ═══════════════════════════════════════════════════════════════════════════════
try:
    _LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DATA")
    os.makedirs(_LOG_DIR, exist_ok=True)
except Exception:
    _LOG_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    filename=os.path.join(_LOG_DIR, "pos_errors.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_logger = logging.getLogger("POS")


def log_exc(context=""):
    """Registra la excepción actual en DATA/pos_errors.log sin interrumpir la app."""
    try:
        _logger.warning("%s\n%s", context, traceback.format_exc())
    except Exception:
        pass


def dmy_to_iso(s):
    """'DD/MM/YYYY' (o sin ceros) → 'YYYY-MM-DD'. Devuelve '' si no se puede parsear.

    Las cadenas ISO se ordenan y comparan correctamente como texto, lo que permite
    filtrar y ordenar fechas sin volver a parsearlas con strptime.
    """
    try:
        d, m, y = str(s).strip().split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except Exception:
        return ""

try:
    from fpdf import FPDF
    _FPDF = True
except ImportError:
    _FPDF = False

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.ticker as mticker
    _MPL = True
except ImportError:
    _MPL = False

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

# ═══════════════════════════════════════════════════════════════════════════════
# Paleta de colores
# ═══════════════════════════════════════════════════════════════════════════════
BG_MAIN    = "#F0F4F8"
BG_PANEL   = "#FFFFFF"
BG_SIDEBAR = "#1E293B"
SB_HOVER   = "#334155"
SB_ACTIVE  = "#2563EB"
PRIMARY    = "#2563EB"
PRIMARY_DK = "#1D4ED8"
SUCCESS    = "#059669"
SUCCESS_DK = "#047857"
DANGER     = "#DC2626"
DANGER_DK  = "#B91C1C"
WARNING    = "#D97706"
TXT_MAIN   = "#0F172A"
TXT_GRAY   = "#64748B"
TXT_LIGHT  = "#F1F5F9"
BORDER     = "#E2E8F0"
ROW_ALT    = "#F8FAFC"


# ═══════════════════════════════════════════════════════════════════════════════
# Base de datos SQLite  (reemplaza todos los .npz)
# ═══════════════════════════════════════════════════════════════════════════════
class BiomedDB:
    def __init__(self, db_path, data_path):
        self.db_dir = os.path.dirname(os.path.abspath(db_path))
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._create_rental_tables()
        self._migrate_columns()
        if not self._has_users():
            self._migrate(data_path)
        self.merge_conflicts()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                sku TEXT DEFAULT '', pcu TEXT DEFAULT '',
                name TEXT DEFAULT '', field3 TEXT DEFAULT '',
                category TEXT DEFAULT '', size_color TEXT DEFAULT '',
                brand TEXT DEFAULT '', vendor TEXT DEFAULT '',
                quantity INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0, price REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                client TEXT DEFAULT '', vendor TEXT DEFAULT '',
                date TEXT DEFAULT '', time TEXT DEFAULT '',
                payment_method TEXT DEFAULT '', total REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL, product_id TEXT NOT NULL,
                quantity INTEGER DEFAULT 1, discount_pct REAL DEFAULT 0.0,
                discount_amount REAL DEFAULT 0.0, amount REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT, pin TEXT,
                access_level INTEGER DEFAULT 2,
                photo TEXT DEFAULT '', sales_target REAL DEFAULT 0.0,
                birth_date TEXT DEFAULT '',
                emergency_name TEXT DEFAULT '',
                emergency_phone TEXT DEFAULT '',
                entry_date TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS clients (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                name               TEXT NOT NULL DEFAULT '',
                phone              TEXT DEFAULT '',
                price_tier         INTEGER DEFAULT 1,
                acepta_whatsapp    INTEGER DEFAULT 0,
                categoria_interes  TEXT DEFAULT '',
                como_nos_conocio   TEXT DEFAULT '',
                notas              TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, concept TEXT, amount REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY, value TEXT
            );
            CREATE TABLE IF NOT EXISTS receptions (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                date    TEXT DEFAULT '',
                vendor  TEXT DEFAULT '',
                folio   TEXT DEFAULT '',
                invoice_total REAL DEFAULT 0.0,
                notes   TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reception_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                reception_id INTEGER NOT NULL,
                product_id   TEXT NOT NULL,
                quantity     INTEGER DEFAULT 1,
                unit_cost    REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS checadas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT DEFAULT '',
                tipo      TEXT DEFAULT 'entrada',
                timestamp TEXT DEFAULT '',
                date      TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS notas_checador (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                autor     TEXT DEFAULT '',
                texto     TEXT DEFAULT '',
                timestamp TEXT DEFAULT '',
                date      TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT DEFAULT '',
                vendor TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                subtotal REAL DEFAULT 0.0,
                iva REAL DEFAULT 0.0,
                total REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pendiente'
            );
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                sku TEXT DEFAULT '',
                name TEXT DEFAULT '',
                size_color TEXT DEFAULT '',
                quantity INTEGER DEFAULT 1,
                unit_cost REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT '',
                percentage REAL DEFAULT 0.0,
                categories TEXT DEFAULT 'TODAS',
                brands TEXT DEFAULT 'TODAS',
                date_start TEXT DEFAULT '',
                date_end TEXT DEFAULT '',
                min_amount REAL DEFAULT 0.0,
                max_amount REAL DEFAULT 0.0,
                restrictions INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            );
        """)
        self.conn.commit()

    def _has_users(self):
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0

    def _create_rental_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS rental_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT DEFAULT '',
                sku TEXT DEFAULT '',
                name TEXT DEFAULT '',
                size_color TEXT DEFAULT '',
                available_qty INTEGER DEFAULT 1,
                deposit REAL DEFAULT 0.0,
                rate_daily REAL DEFAULT 0.0,
                rate_weekly REAL DEFAULT 0.0,
                rate_biweekly REAL DEFAULT 0.0,
                rate_monthly REAL DEFAULT 0.0,
                activo INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS rentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rental_product_id INTEGER NOT NULL,
                client_name TEXT DEFAULT '',
                client_phone TEXT DEFAULT '',
                client_address TEXT DEFAULT '',
                client_id TEXT DEFAULT '',
                date_out TEXT DEFAULT '',
                date_return_expected TEXT DEFAULT '',
                date_returned TEXT DEFAULT '',
                rate_type TEXT DEFAULT 'diaria',
                deposit_paid REAL DEFAULT 0.0,
                rental_amount REAL DEFAULT 0.0,
                balance_returned REAL DEFAULT 0.0,
                status TEXT DEFAULT 'activa',
                notes TEXT DEFAULT '',
                vendor TEXT DEFAULT ''
            );
        """)
        self.conn.commit()

    def _migrate_columns(self):
        # Users table — add missing columns
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        for col, typedef in [("birth_date",      "TEXT DEFAULT ''"),
                             ("emergency_name",  "TEXT DEFAULT ''"),
                             ("emergency_phone", "TEXT DEFAULT ''"),
                             ("entry_date",      "TEXT DEFAULT ''"),
                             ("activo",          "INTEGER DEFAULT 1"),
                             ("full_name",       "TEXT DEFAULT ''")]:
            if col not in existing:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")

        # Products table — add stock threshold columns
        prod_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(products)").fetchall()}
        for col, typedef in [("thresh_yellow", "INTEGER DEFAULT 1"),
                             ("thresh_green",  "INTEGER DEFAULT 3")]:
            if col not in prod_cols:
                self.conn.execute(f"ALTER TABLE products ADD COLUMN {col} {typedef}")

        # Orders table — add status, cancel request, and discount_reason columns
        ord_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(orders)").fetchall()}
        for col, typedef in [("status",              "TEXT DEFAULT 'activa'"),
                             ("cancel_requested_at", "TEXT DEFAULT ''"),
                             ("cancel_requested_by", "TEXT DEFAULT ''"),
                             ("discount_reason",     "TEXT DEFAULT 'Sin descuento'"),
                             ("date_iso",            "TEXT DEFAULT ''")]:
            if col not in ord_cols:
                self.conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {typedef}")

        # Rellenar date_iso (YYYY-MM-DD) en órdenes que aún no lo tengan,
        # convirtiendo la fecha mostrada DD/MM/YYYY. Permite ordenar/filtrar por SQL.
        pend = self.conn.execute(
            "SELECT id, date FROM orders WHERE date_iso IS NULL OR date_iso=''").fetchall()
        for r in pend:
            iso = dmy_to_iso(r["date"])
            if iso:
                self.conn.execute("UPDATE orders SET date_iso=? WHERE id=?",
                                  (iso, r["id"]))
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_date_iso ON orders(date_iso)")

        # Clients table — migrate from old schema (name PK) to new (id PK)
        cli_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(clients)").fetchall()}
        if "id" not in cli_cols:
            self.conn.executescript("""
                ALTER TABLE clients RENAME TO clients_old;
                CREATE TABLE clients (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    name               TEXT NOT NULL DEFAULT '',
                    phone              TEXT DEFAULT '',
                    price_tier         INTEGER DEFAULT 1,
                    acepta_whatsapp    INTEGER DEFAULT 0,
                    categoria_interes  TEXT DEFAULT '',
                    como_nos_conocio   TEXT DEFAULT '',
                    notas              TEXT DEFAULT ''
                );
                INSERT INTO clients (name, phone, price_tier)
                    SELECT name, phone, price_tier FROM clients_old;
                DROP TABLE clients_old;
            """)
        else:
            for col, typedef in [("acepta_whatsapp",   "INTEGER DEFAULT 0"),
                                  ("categoria_interes", "TEXT DEFAULT ''"),
                                  ("como_nos_conocio",  "TEXT DEFAULT ''"),
                                  ("notas",             "TEXT DEFAULT ''")]:
                if col not in cli_cols:
                    self.conn.execute(f"ALTER TABLE clients ADD COLUMN {col} {typedef}")

        # notas_checador — añadir columna tipo si no existe
        nts_cols = {row[1] for row in self.conn.execute(
            "PRAGMA table_info(notas_checador)").fetchall()}
        if "tipo" not in nts_cols:
            self.conn.execute("ALTER TABLE notas_checador ADD COLUMN tipo TEXT DEFAULT 'nota'")

        # purchase_orders — añadir columna vendor si no existe
        po_cols = {row[1] for row in self.conn.execute(
            "PRAGMA table_info(purchase_orders)").fetchall()}
        if "vendor" not in po_cols:
            self.conn.execute("ALTER TABLE purchase_orders ADD COLUMN vendor TEXT DEFAULT ''")

        # clients — índice único en name para evitar duplicados por merge de Dropbox
        idxs = {row[1] for row in self.conn.execute(
            "PRAGMA index_list(clients)").fetchall()}
        if "uq_clients_name" not in idxs:
            # Primero eliminar duplicados dejando el id menor por nombre
            self.conn.execute("""
                DELETE FROM clients
                WHERE id NOT IN (SELECT MIN(id) FROM clients GROUP BY name)
            """)
            self.conn.execute(
                "CREATE UNIQUE INDEX uq_clients_name ON clients(name)")

        self.conn.commit()

    def _safe_int(self, v):
        try:
            return int(v)
        except Exception:
            return 0

    def _safe_float(self, v):
        try:
            return float(v)
        except Exception:
            return 0.0

    def _migrate(self, data_path):
        c = self.conn.cursor()
        print("Migrando datos de .npz a SQLite...")

        # Productos
        pp = os.path.join(data_path, "data_products.npz")
        if os.path.exists(pp):
            try:
                data = np.load(pp, allow_pickle=True)["data"].item()
                for pid, item in data.items():
                    if not isinstance(item, list):
                        item = list(item)
                    while len(item) < 11:
                        item.append("")
                    c.execute(
                        "INSERT OR IGNORE INTO products"
                        "(id,sku,pcu,name,field3,category,size_color,brand,vendor,quantity,cost,price) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(pid), str(item[0] or ""), str(item[1] or ""),
                         str(item[2] or ""), str(item[3] if len(item) > 3 else ""),
                         str(item[4] or ""), str(item[5] or ""),
                         str(item[6] or ""), str(item[7] or ""),
                         self._safe_int(item[8]), self._safe_float(item[9]), self._safe_float(item[10])))
            except Exception as e:
                print(f"  Error productos: {e}")

        # Ordenes
        po = os.path.join(data_path, "data_orders.npz")
        if os.path.exists(po):
            try:
                data = np.load(po, allow_pickle=True)["data"].item()
                for oid, order in data.items():
                    c.execute("INSERT OR IGNORE INTO orders(id,client,vendor,date,time,payment_method,total) VALUES(?,?,?,?,?,?,?)",
                        (str(oid), str(order.get("Cliente", "")), str(order.get("Vendedor", "")),
                         str(order.get("Fecha", "")), str(order.get("Hora", "")),
                         str(order.get("Metodo_pago", "")), self._safe_float(order.get("Importe_total", 0))))
                    for pid, pi in order.get("Productos", {}).items():
                        c.execute("INSERT INTO order_items(order_id,product_id,quantity,discount_pct,discount_amount,amount) VALUES(?,?,?,?,?,?)",
                            (str(oid), str(pid), self._safe_int(pi.get("Cantidad", 1)),
                             self._safe_float(pi.get("Porcentaje_Descuento", 0)),
                             self._safe_float(pi.get("Descuento", 0)),
                             self._safe_float(pi.get("Importe", 0))))
            except Exception as e:
                print(f"  Error ordenes: {e}")

        # Usuarios
        pu = os.path.join(data_path, "data_users.npz")
        if os.path.exists(pu):
            try:
                data = np.load(pu, allow_pickle=True)["data"].item()
                users  = list(data.get("users", []))
                pins   = list(data.get("keys", []))
                access = list(data.get("access", []))
                photos = list(data.get("photos", []))
                tops   = list(data.get("top", []))
                for i in range(len(users)):
                    c.execute("INSERT OR IGNORE INTO users(username,pin,access_level,photo,sales_target) VALUES(?,?,?,?,?)",
                        (str(users[i]), str(pins[i]),
                         int(access[i]) if i < len(access) else 2,
                         str(photos[i]) if i < len(photos) else "",
                         self._safe_float(tops[i]) if i < len(tops) else 0.0))
            except Exception as e:
                print(f"  Error usuarios: {e}")

        # Clientes
        pc = os.path.join(data_path, "data_clients.npz")
        if os.path.exists(pc):
            try:
                data = np.load(pc, allow_pickle=True)["data"].item()
                for name, info in data.items():
                    c.execute("INSERT OR IGNORE INTO clients(name,phone,price_tier) VALUES(?,?,?)",
                        (str(name), str(info.get("cel", "")), self._safe_int(info.get("Precio", 1))))
            except Exception as e:
                print(f"  Error clientes: {e}")
        c.execute("INSERT OR IGNORE INTO clients(name,phone,price_tier) VALUES('Publico General','NA',1)")
        # Agrega aquí clientes iniciales si es necesario

        # Estado
        ps = os.path.join(data_path, "data_state.npz")
        try:
            data = np.load(ps, allow_pickle=True)["data"].item()
            c.execute("INSERT OR IGNORE INTO app_state VALUES('caja',?)", (str(data.get("caja", "Cerrada")),))
            c.execute("INSERT OR IGNORE INTO app_state VALUES('efectivo',?)", (str(self._safe_float(data.get("efectivo", 0))),))
        except Exception:
            c.execute("INSERT OR IGNORE INTO app_state VALUES('caja','Cerrada')")
            c.execute("INSERT OR IGNORE INTO app_state VALUES('efectivo','0.0')")

        self.conn.commit()
        print("  Migracion completada.")

    # ── Unificación de conflictos Dropbox ─────────────────────────────────────
    def merge_conflicts(self):
        """Detecta archivos biomed*.db en conflicto (Dropbox), los unifica y archiva."""
        import glob, shutil
        conflict_files = [
            f for f in glob.glob(os.path.join(self.db_dir, "biomed*.db"))
            if not f.endswith("biomed.db")
        ]
        if not conflict_files:
            return
        archive_dir = os.path.join(self.db_dir, "conflict_archives")
        os.makedirs(archive_dir, exist_ok=True)
        print(f"Unificando {len(conflict_files)} archivo(s) en conflicto de Dropbox...")
        for path in conflict_files:
            try:
                self._merge_one_conflict(path)
                dest = os.path.join(archive_dir, os.path.basename(path))
                shutil.move(path, dest)
                print(f"  Unificado y archivado: {os.path.basename(path)}")
            except Exception as e:
                print(f"  Error al unificar {os.path.basename(path)}: {e}")

    def _merge_one_conflict(self, conflict_path):
        """Integra órdenes, productos y clientes de un DB en conflicto al principal."""
        src = sqlite3.connect(conflict_path)
        src.row_factory = sqlite3.Row
        c = self.conn.cursor()

        # Órdenes nuevas (no existen en el DB principal)
        new_order_ids = set()
        for row in src.execute("SELECT * FROM orders").fetchall():
            exists = c.execute("SELECT 1 FROM orders WHERE id=?", (row["id"],)).fetchone()
            if not exists:
                new_order_ids.add(row["id"])
                try: status = row["status"]
                except Exception: status = "activa"
                try: cat = row["cancel_requested_at"]
                except Exception: cat = ""
                try: cby = row["cancel_requested_by"]
                except Exception: cby = ""
                c.execute(
                    "INSERT OR IGNORE INTO orders"
                    "(id,client,vendor,date,time,payment_method,total,status,"
                    "cancel_requested_at,cancel_requested_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (row["id"], row["client"], row["vendor"], row["date"], row["time"],
                     row["payment_method"], float(row["total"]), status, cat, cby))

        # Items de las órdenes nuevas + calcular delta de inventario
        product_deltas = {}
        for row in src.execute("SELECT * FROM order_items").fetchall():
            if row["order_id"] in new_order_ids:
                c.execute(
                    "INSERT INTO order_items"
                    "(order_id,product_id,quantity,discount_pct,discount_amount,amount) "
                    "VALUES(?,?,?,?,?,?)",
                    (row["order_id"], row["product_id"], int(row["quantity"]),
                     float(row["discount_pct"]), float(row["discount_amount"]),
                     float(row["amount"])))
                pid = str(row["product_id"])
                product_deltas[pid] = product_deltas.get(pid, 0) + int(row["quantity"])

        # Descontar inventario por las ventas que ocurrieron en el conflicto
        for pid, qty_sold in product_deltas.items():
            c.execute(
                "UPDATE products SET quantity = MAX(0, quantity - ?) WHERE id=?",
                (qty_sold, pid))

        # Productos nuevos del archivo en conflicto (no existen en el principal)
        for row in src.execute("SELECT * FROM products").fetchall():
            try:
                c.execute(
                    "INSERT OR IGNORE INTO products"
                    "(id,sku,pcu,name,field3,category,size_color,brand,vendor,quantity,cost,price) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(row["id"]), str(row["sku"] or ""), str(row["pcu"] or ""),
                     str(row["name"] or ""), str(row["field3"] if "field3" in row.keys() else ""),
                     str(row["category"] or ""), str(row["size_color"] or ""),
                     str(row["brand"] or ""), str(row["vendor"] or ""),
                     int(row["quantity"]), float(row["cost"]), float(row["price"])))
            except Exception:
                log_exc("_merge_one_conflict")

        # Clientes nuevos — INSERT OR IGNORE respeta el índice único en name
        for row in src.execute("SELECT * FROM clients").fetchall():
            try:
                c.execute(
                    "INSERT OR IGNORE INTO clients(name,phone,price_tier) VALUES(?,?,?)",
                    (str(row["name"]), str(row["phone"] or ""), int(row["price_tier"] or 1)))
            except Exception:
                log_exc("_merge_one_conflict")

        # Usuarios nuevos (no existen por username en el principal)
        try:
            for row in src.execute("SELECT * FROM users").fetchall():
                exists = c.execute(
                    "SELECT 1 FROM users WHERE username=?", (row["username"],)).fetchone()
                if not exists:
                    try: pin        = row["pin"]
                    except Exception: pin = ""
                    try: access     = int(row["access_level"])
                    except Exception: access = 3
                    try: photo      = row["photo"] or ""
                    except Exception: photo = ""
                    try: target     = float(row["sales_target"])
                    except Exception: target = 0.0
                    try: bdate      = row["birth_date"] or ""
                    except Exception: bdate = ""
                    try: emgname    = row["emergency_name"] or ""
                    except Exception: emgname = ""
                    try: emgphone   = row["emergency_phone"] or ""
                    except Exception: emgphone = ""
                    try: edate      = row["entry_date"] or ""
                    except Exception: edate = ""
                    try: activo     = int(row["activo"])
                    except Exception: activo = 1
                    c.execute(
                        "INSERT INTO users(username,pin,access_level,photo,sales_target,"
                        "birth_date,emergency_name,emergency_phone,entry_date,activo) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (str(row["username"]), str(pin), access, str(photo), target,
                         str(bdate), str(emgname), str(emgphone), str(edate), activo))
                    print(f"    Usuario recuperado: {row['username']}")
        except Exception as e:
            print(f"    Error fusionando usuarios: {e}")

        # Gastos (deduplicar por fecha+concepto+importe)
        try:
            for row in src.execute("SELECT * FROM expenses").fetchall():
                exists = c.execute(
                    "SELECT 1 FROM expenses WHERE date=? AND concept=? AND amount=?",
                    (row["date"], row["concept"], float(row["amount"]))).fetchone()
                if not exists:
                    c.execute(
                        "INSERT INTO expenses(date,concept,amount) VALUES(?,?,?)",
                        (row["date"], row["concept"], float(row["amount"])))
        except Exception:
            log_exc("_merge_one_conflict")

        self.conn.commit()
        src.close()

    # ── Productos ─────────────────────────────────────────────────────────────
    def get_products(self):
        rows = self.conn.execute("SELECT * FROM products ORDER BY CAST(id AS INTEGER)").fetchall()
        def _thresh(r, col, default):
            try:
                v = r[col]
                return int(v) if v is not None else default
            except Exception:
                return default
        return {r["id"]: [r["sku"], r["pcu"], r["name"], r["field3"],
                          r["category"], r["size_color"], r["brand"],
                          r["vendor"], r["quantity"], r["cost"], r["price"],
                          _thresh(r, "thresh_yellow", 1),
                          _thresh(r, "thresh_green",  3)]
                for r in rows}

    def save_product(self, pid, item):
        while len(item) < 13:
            item.append("")
        self.conn.execute(
            "INSERT OR REPLACE INTO products "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(pid), str(item[0] or ""), str(item[1] or ""), str(item[2] or ""), "",
             str(item[4] or ""), str(item[5] or ""), str(item[6] or ""), str(item[7] or ""),
             int(item[8])   if str(item[8]).strip()  else 0,
             float(item[9]) if str(item[9]).strip()  else 0.0,
             float(item[10]) if str(item[10]).strip() else 0.0,
             int(item[11]) if str(item[11]).strip() else 1,
             int(item[12]) if str(item[12]).strip() else 3))
        self.conn.commit()

    def update_stock(self, pid, delta):
        self.conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (int(delta), str(pid)))
        self.conn.commit()

    def delete_product(self, pid):
        self.conn.execute("DELETE FROM products WHERE id = ?", (str(pid),))
        self.conn.commit()

    def max_product_id(self):
        row = self.conn.execute("SELECT MAX(CAST(id AS INTEGER)) as m FROM products").fetchone()
        return str((row["m"] or 0) + 1)

    # ── Ordenes ───────────────────────────────────────────────────────────────
    def get_orders(self):
        orders = {}
        for r in self.conn.execute("SELECT * FROM orders").fetchall():
            try:   st  = r["status"] or "activa"
            except Exception: st = "activa"
            try:   cat = r["cancel_requested_at"] or ""
            except Exception: cat = ""
            try:   cby = r["cancel_requested_by"] or ""
            except Exception: cby = ""
            try:   dr  = r["discount_reason"] or "Sin descuento"
            except Exception: dr = "Sin descuento"
            try:   iso = r["date_iso"] or ""
            except Exception: iso = ""
            if not iso:                       # respaldo si aún no está migrada
                iso = dmy_to_iso(r["date"])
            orders[r["id"]] = {"Cliente": r["client"], "Vendedor": r["vendor"],
                               "Fecha": r["date"], "Fecha_iso": iso,
                               "Hora": r["time"],
                               "Metodo_pago": r["payment_method"],
                               "Importe_total": r["total"],
                               "Status": st,
                               "CancelAt": cat, "CancelBy": cby,
                               "Descuento_razon": dr,
                               "Productos": {}}
        for r in self.conn.execute("SELECT * FROM order_items").fetchall():
            oid, pid = r["order_id"], r["product_id"]
            if oid in orders:
                orders[oid]["Productos"][pid] = {
                    "Cantidad": r["quantity"], "Porcentaje_Descuento": r["discount_pct"],
                    "Descuento": r["discount_amount"], "Importe": r["amount"]}
        return orders

    def update_order_status(self, oid, status, requested_by="", requested_at=""):
        self.conn.execute(
            "UPDATE orders SET status=?, cancel_requested_by=?, cancel_requested_at=? WHERE id=?",
            (status, requested_by, requested_at, str(oid)))
        self.conn.commit()

    def save_order(self, oid, order):
        self.conn.execute(
            "INSERT OR REPLACE INTO orders"
            "(id,client,vendor,date,date_iso,time,payment_method,total,status,discount_reason)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (str(oid), order["Cliente"], order["Vendedor"], order["Fecha"],
             dmy_to_iso(order["Fecha"]), order["Hora"],
             order["Metodo_pago"], float(order["Importe_total"]),
             order.get("Status", "activa"),
             order.get("Descuento_razon", "Sin descuento")))
        for pid, pi in order["Productos"].items():
            self.conn.execute("INSERT INTO order_items(order_id,product_id,quantity,discount_pct,discount_amount,amount) VALUES(?,?,?,?,?,?)",
                (str(oid), str(pid), int(pi["Cantidad"]), float(pi["Porcentaje_Descuento"]),
                 float(pi["Descuento"]), float(pi["Importe"])))
        self.conn.commit()
        self.merge_conflicts()

    def delete_order(self, oid):
        self.conn.execute("DELETE FROM order_items WHERE order_id=?", (str(oid),))
        self.conn.execute("DELETE FROM orders WHERE id=?", (str(oid),))
        self.conn.commit()

    # ── Usuarios ──────────────────────────────────────────────────────────────
    def get_users(self):
        rows = self.conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return {"users":  [r["username"]     for r in rows],
                "keys":   [r["pin"]          for r in rows],
                "access": [r["access_level"] for r in rows],
                "photos": [r["photo"]        for r in rows],
                "top":    [r["sales_target"] for r in rows],
                "ids":    [r["id"]           for r in rows]}

    # ── Clientes ──────────────────────────────────────────────────────────────
    def get_clients(self):
        rows = self.conn.execute("SELECT * FROM clients ORDER BY id").fetchall()
        return {r["name"]: {"id": r["id"], "cel": r["phone"],
                            "Precio": r["price_tier"]} for r in rows}

    def get_clients_full(self):
        return self.conn.execute("SELECT * FROM clients ORDER BY id").fetchall()

    def get_client_by_id(self, client_id):
        return self.conn.execute("SELECT * FROM clients WHERE id=?",
                                 (client_id,)).fetchone()

    def save_client(self, client_id, name, phone,
                    acepta_whatsapp=0, categoria_interes="",
                    como_nos_conocio="", notas=""):
        if client_id:
            self.conn.execute(
                "UPDATE clients SET name=?,phone=?,acepta_whatsapp=?,"
                "categoria_interes=?,como_nos_conocio=?,notas=? WHERE id=?",
                (name, phone, int(acepta_whatsapp),
                 categoria_interes, como_nos_conocio, notas, client_id))
        else:
            self.conn.execute(
                "INSERT INTO clients(name,phone,acepta_whatsapp,"
                "categoria_interes,como_nos_conocio,notas) VALUES(?,?,?,?,?,?)",
                (name, phone, int(acepta_whatsapp),
                 categoria_interes, como_nos_conocio, notas))
        self.conn.commit()

    def delete_client(self, client_id):
        self.conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
        self.conn.commit()

    def get_client_orders(self, client_name):
        return self.conn.execute(
            "SELECT * FROM orders WHERE client=? ORDER BY date DESC, time DESC",
            (client_name,)).fetchall()

    def client_total_purchases(self, client_name):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(total),0) AS t FROM orders WHERE client=?",
            (client_name,)).fetchone()
        return float(row["t"]) if row else 0.0

    # ── Recepciones de pedidos ────────────────────────────────────────────────
    def save_reception(self, date, vendor, folio, invoice_total, notes):
        cur = self.conn.execute(
            "INSERT INTO receptions(date,vendor,folio,invoice_total,notes) VALUES(?,?,?,?,?)",
            (date, vendor, folio, float(invoice_total), notes))
        self.conn.commit()
        return cur.lastrowid

    def save_reception_item(self, reception_id, product_id, quantity, unit_cost):
        self.conn.execute(
            "INSERT INTO reception_items(reception_id,product_id,quantity,unit_cost) VALUES(?,?,?,?)",
            (reception_id, str(product_id), int(quantity), float(unit_cost)))
        self.conn.commit()

    def get_receptions(self):
        return self.conn.execute(
            "SELECT r.*, COUNT(ri.id) AS n_items FROM receptions r "
            "LEFT JOIN reception_items ri ON ri.reception_id=r.id "
            "GROUP BY r.id ORDER BY r.date DESC, r.id DESC").fetchall()

    def update_product_cost(self, pid, cost):
        self.conn.execute("UPDATE products SET cost=? WHERE id=?", (float(cost), str(pid)))
        self.conn.commit()

    # ── Pedidos de compra ─────────────────────────────────────────────────────
    def save_purchase_order(self, items, notes="", vendor=""):
        """items: list of dicts con keys: product_id, sku, name, size_color, quantity, unit_cost"""
        subtotal = sum(float(it['unit_cost']) * int(it['quantity']) for it in items)
        iva      = round(subtotal * 0.16, 2)
        total    = round(subtotal + iva, 2)
        date     = datetime.now().strftime("%d/%m/%Y %H:%M")
        cur = self.conn.execute(
            "INSERT INTO purchase_orders(date,vendor,notes,subtotal,iva,total,status) "
            "VALUES(?,?,?,?,?,?,'pendiente')",
            (date, vendor, notes, round(subtotal, 2), iva, total))
        oid = cur.lastrowid
        for it in items:
            self.conn.execute(
                "INSERT INTO purchase_order_items"
                "(order_id,product_id,sku,name,size_color,quantity,unit_cost) "
                "VALUES(?,?,?,?,?,?,?)",
                (oid, str(it['product_id']), str(it['sku']),
                 str(it['name']), str(it['size_color']),
                 int(it['quantity']), float(it['unit_cost'])))
        self.conn.commit()
        return oid

    def get_purchase_orders(self):
        rows = self.conn.execute(
            "SELECT po.*, COUNT(poi.id) AS n_items "
            "FROM purchase_orders po "
            "LEFT JOIN purchase_order_items poi ON poi.order_id=po.id "
            "GROUP BY po.id ORDER BY po.id DESC").fetchall()
        return rows

    def get_purchase_order_items(self, order_id):
        return self.conn.execute(
            "SELECT * FROM purchase_order_items WHERE order_id=? ORDER BY id",
            (order_id,)).fetchall()

    def update_purchase_order_status(self, order_id, status):
        self.conn.execute(
            "UPDATE purchase_orders SET status=? WHERE id=?",
            (status, int(order_id)))
        self.conn.commit()

    def update_purchase_order(self, order_id, items, notes="", vendor=""):
        """Actualiza un pedido existente conservando el mismo id."""
        subtotal = sum(float(it['unit_cost']) * int(it['quantity']) for it in items)
        iva      = round(subtotal * 0.16, 2)
        total    = round(subtotal + iva, 2)
        date     = datetime.now().strftime("%d/%m/%Y %H:%M")
        oid      = int(order_id)
        self.conn.execute(
            "UPDATE purchase_orders SET date=?,vendor=?,notes=?,subtotal=?,iva=?,total=? "
            "WHERE id=?",
            (date, vendor, notes, round(subtotal, 2), iva, total, oid))
        self.conn.execute(
            "DELETE FROM purchase_order_items WHERE order_id=?", (oid,))
        for it in items:
            self.conn.execute(
                "INSERT INTO purchase_order_items"
                "(order_id,product_id,sku,name,size_color,quantity,unit_cost) "
                "VALUES(?,?,?,?,?,?,?)",
                (oid, str(it['product_id']), str(it['sku']),
                 str(it['name']), str(it['size_color']),
                 int(it['quantity']), float(it['unit_cost'])))
        self.conn.commit()
        return oid

    def delete_purchase_order(self, order_id):
        self.conn.execute(
            "DELETE FROM purchase_order_items WHERE order_id=?", (int(order_id),))
        self.conn.execute(
            "DELETE FROM purchase_orders WHERE id=?", (int(order_id),))
        self.conn.commit()

    # ── Rentas ────────────────────────────────────────────────────────────────
    def save_rental_product(self, product_id, sku, name, size_color,
                            available_qty, deposit,
                            rate_daily, rate_weekly, rate_biweekly, rate_monthly,
                            rp_id=None):
        if rp_id:
            self.conn.execute(
                "UPDATE rental_products SET product_id=?,sku=?,name=?,size_color=?,"
                "available_qty=?,deposit=?,rate_daily=?,rate_weekly=?,"
                "rate_biweekly=?,rate_monthly=? WHERE id=?",
                (str(product_id), str(sku), str(name), str(size_color),
                 int(available_qty), float(deposit), float(rate_daily),
                 float(rate_weekly), float(rate_biweekly), float(rate_monthly),
                 int(rp_id)))
        else:
            self.conn.execute(
                "INSERT INTO rental_products(product_id,sku,name,size_color,"
                "available_qty,deposit,rate_daily,rate_weekly,rate_biweekly,rate_monthly)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (str(product_id), str(sku), str(name), str(size_color),
                 int(available_qty), float(deposit), float(rate_daily),
                 float(rate_weekly), float(rate_biweekly), float(rate_monthly)))
        self.conn.commit()

    def get_rental_products(self):
        return self.conn.execute(
            "SELECT rp.*, "
            "(SELECT COUNT(*) FROM rentals r WHERE r.rental_product_id=rp.id "
            " AND r.status='activa') AS rented_out "
            "FROM rental_products rp WHERE rp.activo=1 ORDER BY rp.name"
        ).fetchall()

    def delete_rental_product(self, rp_id):
        self.conn.execute("UPDATE rental_products SET activo=0 WHERE id=?", (int(rp_id),))
        self.conn.commit()

    def save_rental(self, rental_product_id, client_name, client_phone,
                    client_address, client_id, date_out, date_return_expected,
                    rate_type, deposit_paid, vendor="", notes=""):
        cur = self.conn.execute(
            "INSERT INTO rentals(rental_product_id,client_name,client_phone,"
            "client_address,client_id,date_out,date_return_expected,"
            "rate_type,deposit_paid,status,vendor,notes)"
            " VALUES(?,?,?,?,?,?,?,?,?,'activa',?,?)",
            (int(rental_product_id), str(client_name), str(client_phone),
             str(client_address), str(client_id), str(date_out),
             str(date_return_expected), str(rate_type), float(deposit_paid),
             str(vendor), str(notes)))
        self.conn.commit()
        return cur.lastrowid

    def get_rentals(self, status=None):
        q = ("SELECT r.*, rp.name AS prod_name, rp.sku AS prod_sku, "
             "rp.size_color AS prod_size, rp.deposit AS prod_deposit, "
             "rp.rate_daily, rp.rate_weekly, rp.rate_biweekly, rp.rate_monthly "
             "FROM rentals r "
             "JOIN rental_products rp ON rp.id=r.rental_product_id ")
        if status:
            q += f"WHERE r.status='{status}' "
        q += "ORDER BY r.id DESC"
        return self.conn.execute(q).fetchall()

    def return_rental(self, rental_id, date_returned, rental_amount, balance_returned):
        self.conn.execute(
            "UPDATE rentals SET status='devuelta', date_returned=?,"
            "rental_amount=?,balance_returned=? WHERE id=?",
            (str(date_returned), float(rental_amount),
             float(balance_returned), int(rental_id)))
        self.conn.commit()

    # ── Descuentos ────────────────────────────────────────────────────────────
    def save_discount(self, name, percentage, categories="TODAS", brands="TODAS",
                      date_start="", date_end="", min_amount=0.0, max_amount=0.0,
                      restrictions=0):
        self.conn.execute(
            "INSERT INTO discounts(name,percentage,categories,brands,date_start,date_end,"
            "min_amount,max_amount,restrictions,active) VALUES(?,?,?,?,?,?,?,?,?,1)",
            (str(name), float(percentage), str(categories), str(brands),
             str(date_start), str(date_end),
             float(min_amount), float(max_amount), int(restrictions)))
        self.conn.commit()

    def get_discounts(self):
        return self.conn.execute(
            "SELECT * FROM discounts ORDER BY id DESC").fetchall()

    def get_active_discounts(self):
        """Returns discounts whose date range includes today."""
        today_str = datetime.now().strftime("%d/%m/%Y")
        rows = self.conn.execute(
            "SELECT * FROM discounts WHERE active=1 ORDER BY id DESC").fetchall()
        fmt = "%d/%m/%Y"
        result = []
        for r in rows:
            try:
                ds = datetime.strptime(r["date_start"], fmt)
                de = datetime.strptime(r["date_end"], fmt)
                cd = datetime.strptime(today_str, fmt)
                if ds <= cd <= de:
                    result.append(r)
            except Exception:
                log_exc("get_active_discounts")
        return result

    def update_discount(self, discount_id, name, percentage, categories, brands,
                        date_start, date_end, min_amount, max_amount, restrictions):
        self.conn.execute(
            "UPDATE discounts SET name=?,percentage=?,categories=?,brands=?,"
            "date_start=?,date_end=?,min_amount=?,max_amount=?,restrictions=? "
            "WHERE id=?",
            (str(name), float(percentage), str(categories), str(brands),
             str(date_start), str(date_end),
             float(min_amount), float(max_amount), int(restrictions),
             int(discount_id)))
        self.conn.commit()

    def delete_discount(self, discount_id):
        self.conn.execute("DELETE FROM discounts WHERE id=?", (int(discount_id),))
        self.conn.commit()

    # ── Gastos ────────────────────────────────────────────────────────────────
    def get_expenses(self, date_i=None, date_f=None):
        rows = self.conn.execute("SELECT * FROM expenses ORDER BY date").fetchall()
        result = []
        fmt = "%d/%m/%Y"
        for r in rows:
            if date_i and date_f:
                try:
                    d  = datetime.strptime(r["date"], fmt)
                    di = datetime.strptime(date_i, fmt)
                    df = datetime.strptime(date_f, fmt)
                    if d < di or d > df:
                        continue
                except Exception:
                    log_exc("get_expenses")
            result.append(dict(r))
        return result

    def save_expense(self, date, concept, amount):
        self.conn.execute("INSERT INTO expenses(date,concept,amount) VALUES(?,?,?)", (date, concept, float(amount)))
        self.conn.commit()

    # ── Empleados (CRUD completo) ──────────────────────────────────────────────
    def get_users_full(self):
        return self.conn.execute("SELECT * FROM users ORDER BY id").fetchall()

    def save_user(self, user_id, username, pin, access_level, photo, sales_target,
                  birth_date="", emergency_name="", emergency_phone="", entry_date="",
                  activo=1, full_name=""):
        if user_id:
            self.conn.execute(
                "UPDATE users SET username=?,pin=?,access_level=?,photo=?,sales_target=?,"
                "birth_date=?,emergency_name=?,emergency_phone=?,entry_date=?,activo=?,full_name=? WHERE id=?",
                (username, pin, int(access_level), photo, float(sales_target),
                 birth_date, emergency_name, emergency_phone, entry_date, int(activo),
                 full_name, user_id))
        else:
            self.conn.execute(
                "INSERT INTO users(username,pin,access_level,photo,sales_target,"
                "birth_date,emergency_name,emergency_phone,entry_date,activo,full_name) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (username, pin, int(access_level), photo, float(sales_target),
                 birth_date, emergency_name, emergency_phone, entry_date, int(activo), full_name))
        self.conn.commit()

    def toggle_user_activo(self, user_id, activo):
        self.conn.execute("UPDATE users SET activo=? WHERE id=?", (int(activo), user_id))
        self.conn.commit()

    def update_employee_info(self, user_id, birth_date=None,
                             emergency_name=None, emergency_phone=None):
        updates, values = [], []
        if birth_date      is not None: updates.append("birth_date=?");      values.append(birth_date)
        if emergency_name  is not None: updates.append("emergency_name=?");  values.append(emergency_name)
        if emergency_phone is not None: updates.append("emergency_phone=?"); values.append(emergency_phone)
        if updates:
            values.append(user_id)
            self.conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", values)
            self.conn.commit()

    def delete_user(self, user_id):
        self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    # ── Estado ────────────────────────────────────────────────────────────────
    def get_state(self):
        rows = self.conn.execute("SELECT key, value FROM app_state").fetchall()
        state = {r["key"]: r["value"] for r in rows}
        return {"caja": state.get("caja", "Cerrada"), "efectivo": float(state.get("efectivo", "0.0"))}

    def save_state(self, caja, efectivo):
        self.conn.execute("INSERT OR REPLACE INTO app_state VALUES('caja',?)", (str(caja),))
        self.conn.execute("INSERT OR REPLACE INTO app_state VALUES('efectivo',?)", (str(float(efectivo)),))
        self.conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Aplicacion principal
# ═══════════════════════════════════════════════════════════════════════════════
class PuntoDeVenta:
    def __init__(self, root):
        self.root = root

        # Registra en DATA/pos_errors.log cualquier error no atrapado en un
        # callback de Tkinter (handlers de botones, etc.) en vez de fallar en silencio.
        self.root.report_callback_exception = lambda exc, val, tb: _logger.error(
            "Excepción no capturada en Tk", exc_info=(exc, val, tb))

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = int(sw * 0.95)
        wh = int(sh * 0.85)
        x  = int((sw - ww) / 2)
        y  = int((sh * 0.9 - wh) / 2)
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.title("Biomed POS")
        self.root.configure(bg=BG_MAIN)

        # Layout uses window dims, not screen dims — prevents right-edge clipping
        self.screen_width  = ww
        self.screen_height = wh
        self._current_screen = None
        self._resize_job     = None

        path = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(path, "DATA")

        db_path = os.path.join(self.path, "biomed.db")
        self.db = BiomedDB(db_path, self.path)

        self.data_state  = self.db.get_state()
        self.data_orders = self.db.get_orders()
        self.data_clients = {}

        icon_path = os.path.join(self.path, "icon_search.png")
        if os.path.exists(icon_path):
            self.icon_search = tk.PhotoImage(file=icon_path).subsample(13, 13)
        else:
            self.icon_search = None

        self.index_precio = 10
        self._apply_styles()
        self.root.bind("<Configure>", self._on_resize)
        self.solicitar_contraseña()

    # ── Estilos ttk ───────────────────────────────────────────────────────────
    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("Treeview",
            background=BG_PANEL, foreground=TXT_MAIN,
            fieldbackground=BG_PANEL, font=("Arial", 11),
            rowheight=30, borderwidth=0, relief="flat")
        s.configure("Treeview.Heading",
            background=BG_SIDEBAR, foreground=TXT_LIGHT,
            font=("Arial", 11, "bold"), relief="flat", padding=(8, 7))
        s.map("Treeview",
            background=[("selected", PRIMARY)],
            foreground=[("selected", "white")])
        s.map("Treeview.Heading",
            background=[("active", SB_HOVER)])

        s.configure("TCombobox",
            selectbackground=PRIMARY, fieldbackground=BG_PANEL,
            background=BG_PANEL, foreground=TXT_MAIN, font=("Arial", 12))

        s.configure("success.Horizontal.TProgressbar",
            troughcolor=BORDER, background=SUCCESS,
            lightcolor=SUCCESS, darkcolor=SUCCESS_DK,
            bordercolor=BORDER, thickness=22)

        s.configure("TScrollbar", background=BG_PANEL,
            troughcolor=BG_MAIN, bordercolor=BG_MAIN, arrowcolor=TXT_GRAY)

    # ── Logo helper ──────────────────────────────────────────────────────────
    def _remove_bg(self, img, tolerance=28):
        data = np.array(img, dtype=np.uint8)
        corners = [data[0, 0, :3], data[0, -1, :3], data[-1, 0, :3], data[-1, -1, :3]]
        bg = np.array(np.median(corners, axis=0), dtype=np.int16)
        diff = np.abs(data[:, :, :3].astype(np.int16) - bg).max(axis=2)
        data[diff < tolerance, 3] = 0
        return Image.fromarray(data)

    def _logo_photo(self, max_w, max_h, azul=True):
        if not _PIL:
            return None
        fname = "Logo_azul.png" if azul else "Logo_blanco.png"
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        if not os.path.exists(fpath):
            return None
        img = Image.open(fpath).convert("RGBA")
        img = self._remove_bg(img)
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    # ── Resize support ───────────────────────────────────────────────────────
    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        if abs(event.width - self.screen_width) < 8 and \
           abs(event.height - self.screen_height) < 8:
            return
        self.screen_width  = event.width
        self.screen_height = event.height
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(220, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if self._current_screen is None:
            return
        # Detener reloj del Checador antes de reconstruir
        self._chk_running = False
        if hasattr(self, "_chk_clock_id"):
            try:
                self.root.after_cancel(self._chk_clock_id)
            except Exception:
                log_exc("_do_resize")
            self._chk_clock_id = None
        for w in self.root.winfo_children():
            w.destroy()
        self.opciones()
        self._current_screen()

    # ── Helpers de widgets ────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=PRIMARY, fg="white",
             font_size=12, bold=True, **kw):
        wt = "bold" if bold else "normal"
        b = tk.Label(parent, text=text,
                     bg=bg, fg=fg,
                     font=("Arial", font_size, wt),
                     cursor="hand2", **kw)
        dk = self._darken(bg)
        b.bind("<Button-1>", lambda _e: cmd())
        b.bind("<Enter>",    lambda _e: b.config(bg=dk))
        b.bind("<Leave>",    lambda _e: b.config(bg=bg))
        return b

    @staticmethod
    def _darken(hex_color):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        f = 0.82
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"

    def _header(self, parent, title, subtitle=""):
        hh = int(self.screen_height * 0.07)
        h = tk.Frame(parent, bg=BG_PANEL,
                     highlightbackground=BORDER, highlightthickness=1)
        h.place(x=0, y=0, width=int(self.screen_width * 0.9), height=hh)
        tk.Label(h, text=title, bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 20, "bold"), anchor="w"
                 ).place(x=20, y=0, height=hh, width=int(self.screen_width * 0.5))
        if subtitle:
            tk.Label(h, text=subtitle, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 13), anchor="e"
                     ).place(x=int(self.screen_width * 0.55), y=0,
                             height=hh, width=int(self.screen_width * 0.3))
        return h

    def _card(self, parent, x, y, w, h, title=""):
        f = tk.Frame(parent, bg=BG_PANEL,
                     highlightbackground=BORDER, highlightthickness=1)
        f.place(x=x, y=y, width=w, height=h)
        if title:
            tk.Label(f, text=title, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 9, "bold"), anchor="w").place(x=8, y=4)
        return f

    def _tag_rows(self, tree):
        tree.tag_configure("even", background=BG_PANEL)
        tree.tag_configure("odd",  background=ROW_ALT)

    def _insert_row(self, tree, values, text="", idx=0):
        tag = "even" if idx % 2 == 0 else "odd"
        tree.insert("", "end", text=text, values=values, tags=(tag,))

    def _add_scrollbar(self, parent, tree, x, y, w, h):
        sb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        sb.place(x=x + w, y=y, width=14, height=h)
        tree.configure(yscrollcommand=sb.set)
        return sb

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIN
    # ══════════════════════════════════════════════════════════════════════════
    def solicitar_contraseña(self):
        # Detener cualquier reloj del Checador antes de destruir widgets
        self._chk_running = False
        if hasattr(self, "_chk_clock_id"):
            try:
                self.root.after_cancel(self._chk_clock_id)
            except Exception:
                log_exc("solicitar_contraseña")
            self._chk_clock_id = None

        for w in self.root.winfo_children():
            w.destroy()

        SW, SH = self.screen_width, self.screen_height

        bg_frame = tk.Frame(self.root, bg=BG_SIDEBAR)
        bg_frame.place(x=0, y=0, width=SW, height=SH)

        # Decorative shapes
        cv = tk.Canvas(bg_frame, bg=BG_SIDEBAR, highlightthickness=0,
                       width=300, height=300)
        cv.place(x=SW - 260, y=-80)
        cv.create_oval(0, 0, 300, 300, fill=SB_HOVER, outline="")
        cv.create_oval(60, 60, 240, 240, fill=SB_ACTIVE, outline="")

        cv2 = tk.Canvas(bg_frame, bg=BG_SIDEBAR, highlightthickness=0,
                        width=200, height=200)
        cv2.place(x=-70, y=SH - 170)
        cv2.create_oval(0, 0, 200, 200, fill=SB_HOVER, outline="")

        # Card
        cw = int(SW * 0.27)
        ch = int(SH * 0.52)
        cx = (SW - cw) // 2
        cy = (SH - ch) // 2 - 20

        card = tk.Frame(bg_frame, bg=BG_PANEL)
        card.place(x=cx, y=cy, width=cw, height=ch)

        top_h = int(ch * 0.24)
        top_f = tk.Frame(card, bg=SB_ACTIVE)
        top_f.place(x=0, y=0, width=cw, height=top_h)
        _logo = self._logo_photo(cw - 20, top_h - 10, azul=True)
        if _logo:
            lbl_logo = tk.Label(top_f, image=_logo, bg=SB_ACTIVE)
            lbl_logo.image = _logo
            lbl_logo.place(x=0, y=0, width=cw, height=top_h)
        else:
            tk.Label(top_f, text="BIOMED", bg=SB_ACTIVE, fg="white",
                     font=("Arial", 22, "bold")).place(x=0, y=0, width=cw, height=top_h)

        tk.Label(card, text="Sistema de Punto de Venta",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 11)
                 ).place(x=0, y=top_h + 8, width=cw, height=int(ch * 0.07))

        py = int(ch * 0.40)
        tk.Label(card, text="PIN de acceso:", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 12), anchor="w"
                 ).place(x=int(cw * 0.1), y=py, width=int(cw * 0.8), height=int(ch * 0.07))

        entry_pin = tk.Entry(card, font=("Arial", 18), show="*",
                             justify="center", relief="flat",
                             bg=BG_MAIN, fg=TXT_MAIN, insertbackground=PRIMARY)
        entry_pin.place(x=int(cw * 0.1), y=py + int(ch * 0.09),
                        width=int(cw * 0.8), height=int(ch * 0.10))
        tk.Frame(card, bg=PRIMARY).place(
            x=int(cw * 0.1), y=py + int(ch * 0.19), width=int(cw * 0.8), height=2)

        err_lbl = tk.Label(card, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.place(x=0, y=py + int(ch * 0.23), width=cw, height=int(ch * 0.06))

        btn_in = self._btn(card, "INGRESAR", lambda: _login(),
                           bg=PRIMARY, font_size=13, pady=10)
        btn_in.place(x=int(cw * 0.1), y=int(ch * 0.74),
                     width=int(cw * 0.8), height=int(ch * 0.13))

        def _login(event=None):
            pin  = entry_pin.get()
            data = self.db.get_users()
            pins = list(data["keys"])
            if pin in pins:
                idx = pins.index(pin)
                self.usuario            = data["users"][idx]
                self.prioridad_usuario  = data["access"][idx]
                self.usuario_id         = data["ids"][idx]
                self.path_photo         = os.path.join(self.path, "pictures",
                                                       data["photos"][idx])
                self.umbral_usuario     = data["top"][idx]
                bg_frame.destroy()
                self.iniciar_punto_de_venta()
                # Cerrar salidas olvidadas de días anteriores
                self._auto_checkout_forgotten()
                # Si el empleado que entra no está activo, registrar entrada
                if data["access"][idx] > 1:
                    self._auto_checkin_if_needed(data["ids"][idx], data["users"][idx])
                self.opciones()
                if self.prioridad_usuario <= 1:
                    self.opcion_estado_general()
                else:
                    self.opcion_punto_venta()
                self.root.after(400, lambda: self._check_employee_info(self.usuario_id))
            else:
                err_lbl.config(text="PIN incorrecto. Intente de nuevo.")
                entry_pin.delete(0, tk.END)

        entry_pin.bind("<Return>", _login)
        entry_pin.focus_set()

    # ══════════════════════════════════════════════════════════════════════════
    # FILTROS Y UTILIDADES
    # ══════════════════════════════════════════════════════════════════════════
    def FiltrarData(self, vendedor=False, cliente=False, metodo_pago=False,
                    fecha_inicial=False, fecha_final=False):
        data_orders  = self.data_orders
        data_filter  = data_orders.copy()
        # Comparación por fecha ISO (texto YYYY-MM-DD): ordena correctamente y
        # no se rompe si una orden tiene la fecha vacía o mal formada.
        iso_ini = dmy_to_iso(fecha_inicial) if fecha_inicial else ""
        iso_fin = dmy_to_iso(fecha_final)   if fecha_final   else ""
        for order, item in data_orders.items():
            d_iso = item.get("Fecha_iso") or dmy_to_iso(item.get("Fecha", ""))
            if vendedor and order in data_filter:
                if item["Vendedor"] != vendedor:
                    data_filter.pop(order)
            if cliente and order in data_filter:
                if item["Cliente"] != cliente:
                    data_filter.pop(order)
            if metodo_pago and order in data_filter:
                if item["Metodo_pago"] != metodo_pago:
                    data_filter.pop(order)
            if iso_ini and order in data_filter:
                if not d_iso or d_iso < iso_ini:
                    data_filter.pop(order)
            if iso_fin and order in data_filter:
                if not d_iso or d_iso > iso_fin:
                    data_filter.pop(order)
        return data_filter

    def _last_valid_saturday(self, month, year):
        """Last Saturday in month with at least 3 days remaining after it."""
        last_day = calendar.monthrange(year, month)[1]
        d = datetime(year, month, last_day) - timedelta(3)
        while d.weekday() != 5:   # 5 = Saturday
            d -= timedelta(1)
        return d

    def _first_cut_monday(self, month, year):
        """First Monday of this month's weekly cuts (2 days after prev month's last Saturday)."""
        pm, py = (12, year - 1) if month == 1 else (month - 1, year)
        return self._last_valid_saturday(pm, py) + timedelta(2)

    def cortes_semanas(self, month, year):
        """List of (monday, saturday) datetime pairs for Mon-Sat weekly cuts in month/year."""
        last_sat = self._last_valid_saturday(month, year)
        d = self._first_cut_monday(month, year)
        cuts = []
        while True:
            saturday = d + timedelta(5)
            if saturday > last_sat:
                break
            cuts.append((d, saturday))
            d = saturday + timedelta(2)   # skip Sunday → next Monday
        return cuts

    def _semanas_checador(self, month, year):
        """All Mon-Sat calendar-week pairs that overlap with month/year.
        Unlike cortes_semanas(), this includes the last partial week even if
        it extends into the next month (e.g. May 25-30 when May 31 is Sunday).
        """
        import calendar as _cal
        first_day = datetime(year, month, 1)
        last_day  = datetime(year, month, _cal.monthrange(year, month)[1])
        # Monday on or before the 1st of the month
        start_mon = first_day - timedelta(days=first_day.weekday())
        weeks = []
        d = start_mon
        while d <= last_day:
            weeks.append((d, d + timedelta(5)))   # Mon → Sat
            d += timedelta(7)                      # next Monday
        return weeks

    def cortes_mes(self, month, year):
        """Start-date string of this month's full reporting period (first Monday of cuts)."""
        cuts = self.cortes_semanas(month, year)
        d = cuts[0][0] if cuts else datetime(year, month, 1)
        return [f"{d.day}/{d.month}/{d.year}"]

    def ajusta(self, i):
        i = str(i)
        return i if len(i) >= 2 else "0" + i

    def order_id(self):
        date = datetime.now()
        def aj(i, s=2):
            i = str(i)
            return i[-s:] if len(i) >= s else "0" * (s - len(i)) + i
        return f"{aj(date.year)}{aj(date.month)}{aj(date.day)}{aj(date.hour)}{aj(date.minute)}{aj(date.second)}"

    def find(self, lista, search):
        for element in lista:
            if search.lower() in str(element).lower():
                return True
        return False

    def years_orders(self):
        years = []
        for _, item in self.data_orders.items():
            d_iso = item.get("Fecha_iso") or dmy_to_iso(item.get("Fecha", ""))
            if not d_iso:
                continue
            y = int(d_iso[:4])
            if y not in years:
                years.append(y)
        return years

    def cortes(self, year, month, n_cortes=0, mes=False):
        cuts = self.cortes_semanas(month, year)
        if not cuts:
            self.n_cortes = 1
            last_day = calendar.monthrange(year, month)[1]
            return (f"01/{month:02d}/{year}", f"{last_day:02d}/{month:02d}/{year}")
        if mes:
            date_i = cuts[0][0]
            date_f = cuts[-1][1]
        else:
            if n_cortes == 0:
                now = datetime.now()
                n_cortes = len(cuts)   # default to last if past all cuts
                for i, (di, df) in enumerate(cuts):
                    if di.date() <= now.date() <= df.date():
                        n_cortes = i + 1
                        break
                    if now.date() < di.date():
                        n_cortes = max(1, i)
                        break
            n_cortes  = min(max(n_cortes, 1), len(cuts))
            date_i, date_f = cuts[n_cortes - 1]
        self.n_cortes = n_cortes
        return (f"{date_i.day:02d}/{date_i.month:02d}/{date_i.year}",
                f"{date_f.day:02d}/{date_f.month:02d}/{date_f.year}")

    def filtrar_orders(self, usuario="", fecha_inicial="", fecha_final=""):
        result = {}
        iso_ini = dmy_to_iso(fecha_inicial) if fecha_inicial else ""
        iso_fin = dmy_to_iso(fecha_final) if fecha_final else datetime.now().strftime("%Y-%m-%d")
        for oid, item in self.data_orders.items():
            if usuario and item["Vendedor"] != usuario:
                continue
            d_iso = item.get("Fecha_iso") or dmy_to_iso(item.get("Fecha", ""))
            if not d_iso:
                continue
            if iso_ini and d_iso < iso_ini:
                continue
            if d_iso <= iso_fin:
                result[oid] = item
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════
    def opciones(self):
        sw, sh = self.screen_width, self.screen_height
        sb_w = int(sw * 0.1)

        self.frame_Opciones = tk.Frame(self.root, bg=BG_SIDEBAR)
        self.frame_Opciones.place(x=0, y=0, width=sb_w, height=sh)

        # Brand
        brand = tk.Frame(self.frame_Opciones, bg=SB_ACTIVE)
        brand.pack(fill="x")
        _logo_sb = self._logo_photo(sb_w - 6, 110, azul=True)
        if _logo_sb:
            lbl_sb = tk.Label(brand, image=_logo_sb, bg=SB_ACTIVE, pady=8)
            lbl_sb.image = _logo_sb
            lbl_sb.pack()
            self._logo_sidebar = _logo_sb  # prevent garbage collection
        else:
            tk.Label(brand, text="BIOMED", bg=SB_ACTIVE, fg="white",
                     font=("Arial", 22, "bold"), pady=18).pack()

        tk.Frame(self.frame_Opciones, bg=SB_HOVER, height=1).pack(fill="x", pady=6)

        menu = []
        if self.prioridad_usuario <= 1:          # CEO y Gerente
            menu.append(("  General",    self.opcion_estado_general))
        menu.append(("  Caja",       self.opcion_punto_venta))
        menu.append(("  Ordenes",    self.opcion_ordenes))
        menu.append(("  Clientes",   self.opcion_clientes))
        if self.prioridad_usuario <= 2:
            menu.append(("  Corte",      self.opcion_reportes))
            menu.append(("  Análisis",   self.opcion_analisis))
        if self.prioridad_usuario < 2:
            menu.append(("  Inventario", self.opcion_inventario))
            menu.append(("  Pedidos",    self.opcion_pedidos))
        menu.append(("  Rentas",     self.opcion_rentas))
        if self.prioridad_usuario == 0:
            menu.append(("  Descuentos", self.opcion_descuentos))
            menu.append(("  Usuarios",   self.opcion_empleados))

        for label, cmd in menu:
            b = tk.Label(self.frame_Opciones, text=label,
                         bg=BG_SIDEBAR, fg=TXT_LIGHT,
                         font=("Arial", 15),
                         anchor="w", pady=12, padx=4, cursor="hand2")
            b.pack(fill="x", pady=1)
            b.bind("<Button-1>", lambda _e, c=cmd: c())
            b.bind("<Enter>",    lambda _e, btn=b: btn.config(bg=SB_HOVER))
            b.bind("<Leave>",    lambda _e, btn=b: btn.config(bg=BG_SIDEBAR))

        tk.Frame(self.frame_Opciones, bg=SB_HOVER, height=1).pack(
            fill="x", side="bottom", pady=4)
        b_usr = tk.Label(self.frame_Opciones, text="  Cambiar\n  Usuario",
                         bg=BG_SIDEBAR, fg=TXT_GRAY,
                         font=("Arial", 10),
                         anchor="w", pady=8, padx=4, cursor="hand2")
        b_usr.pack(fill="x", side="bottom")
        b_usr.bind("<Button-1>", lambda _e: self.solicitar_contraseña())
        b_usr.bind("<Enter>",    lambda _e: b_usr.config(bg=SB_HOVER, fg=TXT_LIGHT))
        b_usr.bind("<Leave>",    lambda _e: b_usr.config(bg=BG_SIDEBAR, fg=TXT_GRAY))

    # ══════════════════════════════════════════════════════════════════════════
    # INICIO
    # ══════════════════════════════════════════════════════════════════════════
    def iniciar_punto_de_venta(self):
        self.carrito            = {}
        self.Total              = 0
        self.cliente            = "Publico General"
        self._cliente_descuento = 0
        self._discount_reason       = "Sin descuento"
        self._discount_restrictions = 0   # 0=ambos, 1=solo tarjeta, 2=solo efectivo
        self.data_products = self.db.get_products()
        self.data_clients  = self.db.get_clients()

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD — Estado General
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_estado_general(self):
        self._current_screen = self.opcion_estado_general
        sw, sh = self.screen_width, self.screen_height
        now    = datetime.now()
        today  = f"{now.day}/{now.month}/{now.year}"
        cortes = self.cortes_mes(now.month, now.year)

        self.frame_estado = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_estado.place(x=int(sw * 0.1), y=0,
                                width=int(sw * 0.9), height=sh)

        self._header(self.frame_estado, "Panel General",
                     subtitle=f"Bienvenido, {self.usuario}")

        pw = int(sw * 0.9)
        hh = int(sh * 0.07)  # header height offset

        # ── Dos columnas: izquierda = pendientes, derecha = horario ────────────
        top_y  = hh + int(sh * 0.02)
        side_h = int(sh * 0.30)
        lp_x   = int(pw * 0.02)
        lp_w   = int(pw * 0.44)
        rp_x   = int(pw * 0.48)
        rp_w   = int(pw * 0.50)

        # ── Columna izquierda: Pendientes ────────────────────────────────────
        pend_orders = [(oid, o) for oid, o in self.data_orders.items()
                       if o.get("Status") == "cancelacion_pendiente"]

        today_dt = f"{now.day:02d}/{now.month:02d}/{now.year}"
        notas_rows = self.db.conn.execute(
            "SELECT autor, texto, timestamp, tipo FROM notas_checador"
            " WHERE date=? ORDER BY id DESC",
            (today_dt,)).fetchall()

        row_h = int(sh * 0.038)
        hdr_h = int(sh * 0.040)
        gap_h = int(sh * 0.006)

        pend_card = self._card(self.frame_estado, x=lp_x, y=top_y,
                               w=lp_w, h=side_h, title="⏳ PENDIENTES")
        tk.Frame(pend_card, bg=WARNING, height=3).place(x=0, y=0, width=lp_w, height=3)

        cur_y = int(sh * 0.045)

        # Notas del checador
        tk.Label(pend_card, text="  📝  Notas del día",
                 bg="#FFF7ED", fg="#92400E",
                 font=("Arial", 9, "bold"), anchor="w"
                 ).place(x=0, y=cur_y, width=lp_w, height=hdr_h)
        cur_y += hdr_h

        if not notas_rows:
            tk.Label(pend_card, text="  Sin notas para hoy",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10), anchor="w"
                     ).place(x=0, y=cur_y, width=lp_w, height=row_h)
        else:
            for ni, nr in enumerate(notas_rows):
                tipo  = nr["tipo"] if nr["tipo"] else "nota"
                icon  = "📝" if tipo == "nota" else "⏳"
                color = PRIMARY if tipo == "nota" else "#B45309"
                bg_r  = BG_MAIN if ni % 2 == 0 else BG_PANEL
                rf = tk.Frame(pend_card, bg=bg_r)
                rf.place(x=0, y=cur_y, width=lp_w, height=row_h - 2)
                txt = f"  {icon}  [{nr['timestamp']}] {nr['autor']}: {nr['texto']}"
                tk.Label(rf, text=txt, bg=bg_r, fg=color,
                         font=("Arial", 10), anchor="w"
                         ).place(x=8, y=2, width=lp_w - 16, height=row_h - 6)
                cur_y += row_h

        cur_y += gap_h

        # Cancelaciones pendientes
        tk.Label(pend_card, text="  🚫  Cancelaciones pendientes",
                 bg="#FEF3C7", fg="#92400E",
                 font=("Arial", 9, "bold"), anchor="w"
                 ).place(x=0, y=cur_y, width=lp_w, height=hdr_h)
        cur_y += hdr_h

        if not pend_orders:
            tk.Label(pend_card, text="  Sin cancelaciones pendientes",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10), anchor="w"
                     ).place(x=0, y=cur_y, width=lp_w, height=row_h)
        else:
            for pi, (oid, o) in enumerate(pend_orders):
                bg_r = BG_MAIN if pi % 2 == 0 else BG_PANEL
                rf = tk.Frame(pend_card, bg=bg_r)
                rf.place(x=0, y=cur_y, width=lp_w, height=row_h - 2)
                cancel_by = o.get("CancelBy") or o.get("Vendedor", "—")
                cancel_at = o.get("CancelAt", "—")
                txt = (f"  Orden #{oid}  ·  {o['Cliente']}  ·  "
                       f"$ {o['Importe_total']}  ·  "
                       f"Sol. por: {cancel_by}  el {cancel_at}")
                tk.Label(rf, text=txt, bg=bg_r, fg="#92400E",
                         font=("Arial", 10, "bold"), anchor="w"
                         ).place(x=8, y=2, width=lp_w - 16, height=row_h - 6)
                cur_y += row_h

        # ── Columna derecha: Horario de entradas ─────────────────────────────
        chk_panel = tk.Frame(self.frame_estado, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        chk_panel.place(x=rp_x, y=top_y, width=rp_w, height=side_h)

        _g_hdr = tk.Frame(chk_panel, bg=BG_PANEL)
        _g_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(_g_hdr, text="HORARIO DE ENTRADAS", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9, "bold"), anchor="w").pack(side="left")
        tk.Frame(chk_panel, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 4))

        _g_nav = tk.Frame(chk_panel, bg=BG_PANEL)
        _g_nav.pack(fill="x", padx=8, pady=(2, 4))

        btn_g_prev = self._btn(_g_nav, "◀", lambda: None,
                               bg=BG_MAIN, fg=TXT_MAIN, font_size=10, bold=False)
        btn_g_prev.pack(side="left", ipadx=6, ipady=2)

        lbl_g_week = tk.Label(_g_nav, text="", bg=BG_PANEL, fg=TXT_MAIN,
                              font=("Arial", 9, "bold"))
        lbl_g_week.pack(side="left", padx=4, expand=True)

        btn_g_next = self._btn(_g_nav, "▶", lambda: None,
                               bg=BG_MAIN, fg=TXT_MAIN, font_size=10, bold=False)
        btn_g_next.pack(side="right", ipadx=6, ipady=2)

        _g_day_names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb")
        _g_cols      = ("Empleado",) + _g_day_names
        g_tree_chk   = ttk.Treeview(chk_panel, columns=_g_cols, show="headings")
        g_tree_chk.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        _g_emp_w = int(rp_w * 0.22)
        _g_day_w = max(30, int((rp_w - _g_emp_w - 20) / 6))
        g_tree_chk.column("Empleado", anchor="w", width=_g_emp_w, minwidth=60)
        g_tree_chk.heading("Empleado", text="Empleado")
        for _gd in _g_day_names:
            g_tree_chk.column(_gd, anchor="center", width=_g_day_w, minwidth=30)
            g_tree_chk.heading(_gd, text=_gd)
        self._tag_rows(g_tree_chk)

        _gnow    = datetime.now()
        _g_state = {"month": _gnow.month, "year": _gnow.year, "idx": 0}
        _g_icut  = self._semanas_checador(_gnow.month, _gnow.year)
        for _gi, (_gm, _gs) in enumerate(_g_icut):
            if _gm.date() <= _gnow.date() <= _gs.date():
                _g_state["idx"] = _gi
                break

        def _g_get_cuts():
            return self._semanas_checador(_g_state["month"], _g_state["year"])

        def _g_fill():
            _gc = _g_get_cuts()
            if not _gc:
                lbl_g_week.config(text="Sin semanas")
                g_tree_chk.delete(*g_tree_chk.get_children())
                return
            _gi2 = min(_g_state["idx"], len(_gc) - 1)
            _g_state["idx"] = _gi2
            _gmon, _gsat = _gc[_gi2]
            _mn = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
                   "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
            lbl_g_week.config(
                text=(f"Sem. {_gi2 + 1}  "
                      f"{_gmon.day} {_mn[_gmon.month]} — "
                      f"{_gsat.day} {_mn[_gsat.month]} {_gsat.year}"))
            _g_dates = [(_gmon + timedelta(i)).strftime("%d/%m/%Y") for i in range(6)]
            _g_users = [r for r in self.db.get_users_full()
                        if int(r["activo"] or 0) == 1 and int(r["access_level"]) >= 2]
            g_tree_chk.delete(*g_tree_chk.get_children())
            self._tag_rows(g_tree_chk)
            for _ri, _ru in enumerate(_g_users):
                _rv = [_ru["username"]]
                for _ds in _g_dates:
                    _rh = self.db.conn.execute(
                        "SELECT timestamp FROM checadas"
                        " WHERE user_id=? AND date=? AND tipo='entrada'"
                        " ORDER BY id ASC LIMIT 1",
                        (_ru["id"], _ds)).fetchone()
                    if _rh:
                        _ts = str(_rh["timestamp"])
                        _rv.append(_ts[:5] if len(_ts) >= 5 else _ts)
                    else:
                        _rv.append("—")
                _rtag = "even" if _ri % 2 == 0 else "odd"
                g_tree_chk.insert("", "end", values=_rv, tags=(_rtag,))

        def _g_prev():
            _gc = _g_get_cuts()
            if _g_state["idx"] > 0:
                _g_state["idx"] -= 1
            else:
                _m, _y = _g_state["month"], _g_state["year"]
                if _m == 1:
                    _m, _y = 12, _y - 1
                else:
                    _m -= 1
                _g_state["month"], _g_state["year"] = _m, _y
                _g_state["idx"] = max(0, len(_g_get_cuts()) - 1)
            _g_fill()

        def _g_next():
            _gc = _g_get_cuts()
            if _g_state["idx"] < len(_gc) - 1:
                _g_state["idx"] += 1
            else:
                _m, _y = _g_state["month"], _g_state["year"]
                if _m == 12:
                    _m, _y = 1, _y + 1
                else:
                    _m += 1
                _g_state["month"], _g_state["year"] = _m, _y
                _g_state["idx"] = 0
            _g_fill()

        btn_g_prev.bind("<Button-1>", lambda _e: _g_prev())
        btn_g_next.bind("<Button-1>", lambda _e: _g_next())
        _g_fill()

        # ── Ventas (para tabla de productos) ────────────────────────────────
        week_start   = now - timedelta(days=now.weekday())
        fecha_semana = f"{week_start.day}/{week_start.month}/{week_start.year}"

        if self.prioridad_usuario <= 2:
            ventas_dia    = self.FiltrarData(fecha_inicial=today)
            ventas_semana = self.FiltrarData(fecha_inicial=fecha_semana)
            ventas_mes    = self.FiltrarData(fecha_inicial=cortes[0])
        else:
            ventas_dia    = self.FiltrarData(vendedor=self.usuario, fecha_inicial=today)
            ventas_semana = self.FiltrarData(vendedor=self.usuario, fecha_inicial=fecha_semana)
            ventas_mes    = self.FiltrarData(vendedor=self.usuario, fecha_inicial=cortes[0])

        # ── Selector de período + tabla de productos vendidos ────────────────
        prod_y = top_y + side_h + int(sh * 0.01)
        tw     = int(pw * 0.84)
        tx     = int(pw * 0.08)
        hdr_y  = prod_y + int(sh * 0.008)
        hdr_h  = int(sh * 0.042)
        ty     = hdr_y + hdr_h + int(sh * 0.006)
        th     = sh - ty - int(sh * 0.02)

        # Selector Hoy / Semana / Mes  (columna izquierda del header)
        sel_frame = tk.Frame(self.frame_estado, bg=BG_MAIN)
        sel_frame.place(x=int(pw * 0.02), y=hdr_y,
                        width=int(pw * 0.22), height=hdr_h)
        tk.Label(sel_frame, text="Período:", bg=BG_MAIN, fg=TXT_GRAY,
                 font=("Arial", 10)).pack(side="left", padx=4)
        self.combobox_plazo = ttk.Combobox(sel_frame, state="readonly",
                                           values=["Hoy", "Semana", "Mes"],
                                           justify="center", width=8)
        self.combobox_plazo.pack(side="left", padx=4, pady=6)
        self.combobox_plazo.set("Hoy")

        # Título (columna derecha del header, sin solapar al selector)
        self.lbl_resumen_titulo = tk.Label(
            self.frame_estado, text="Productos vendidos — Hoy",
            bg=BG_MAIN, fg=TXT_MAIN, font=("Arial", 12, "bold"), anchor="w")
        self.lbl_resumen_titulo.place(x=int(pw * 0.26), y=hdr_y,
                                      width=int(pw * 0.68), height=hdr_h)

        pcols = ("SKU", "Producto", "Categoría", "Cant.", "Desc. $", "Motivo", "Importe", "Última venta")
        self.tree_orders = ttk.Treeview(self.frame_estado,
                                        columns=pcols, show="headings", height=12)
        pwidths = [int(sw * w) for w in (0.06, 0.17, 0.08, 0.04, 0.06, 0.10, 0.06, 0.07)]
        for col, w in zip(pcols, pwidths):
            anchor = "w" if col in ("SKU", "Producto", "Motivo") else "center"
            self.tree_orders.column(col, anchor=anchor, width=w)
            self.tree_orders.heading(col, text=col)
        self.tree_orders.place(x=tx, y=ty, width=tw, height=th)
        self._tag_rows(self.tree_orders)
        self._add_scrollbar(self.frame_estado, self.tree_orders, tx, ty, tw, th)

        def _aggregate(source):
            prods = {}
            for item in source.values():
                fecha  = item.get("Fecha", "")
                reason = item.get("Descuento_razon", "Sin descuento") or "Sin descuento"
                for pid, pi in item["Productos"].items():
                    info = self.data_products.get(pid, ["", "", "—", "", "", "—"])
                    sku  = info[0] if info else ""
                    name = info[2] if len(info) > 2 else "—"
                    cat  = info[5] if len(info) > 5 else "—"
                    if name not in prods:
                        prods[name] = {"sku": sku, "cat": cat, "qty": 0,
                                       "discount": 0.0, "amount": 0.0,
                                       "last_date": "", "last_reason": "Sin descuento"}
                    prods[name]["qty"]      += int(pi["Cantidad"])
                    prods[name]["discount"] += float(pi.get("Descuento", 0))
                    prods[name]["amount"]   += float(pi["Importe"])
                    if fecha > prods[name]["last_date"]:
                        prods[name]["last_date"]   = fecha
                        prods[name]["last_reason"] = reason

            def _date_key(d):
                try:
                    return datetime.strptime(d["last_date"], "%d/%m/%Y")
                except Exception:
                    return datetime.min

            return sorted(prods.items(), key=lambda x: _date_key(x[1]), reverse=True)

        TITULOS = {"Hoy": "Hoy", "Semana": "Esta semana", "Mes": "Este mes"}

        def _fill(source, label="Hoy"):
            for row in self.tree_orders.get_children():
                self.tree_orders.delete(row)
            self.lbl_resumen_titulo.config(
                text=f"Productos vendidos — {TITULOS.get(label, label)}")
            for i, (name, d) in enumerate(_aggregate(source)):
                disc_s = f"$ {d['discount']:,.2f}" if d["discount"] > 0.005 else "—"
                self._insert_row(self.tree_orders,
                    (d["sku"], name, d["cat"], d["qty"],
                     disc_s, d["last_reason"],
                     f"$ {d['amount']:,.2f}", d["last_date"]),
                    idx=i)

        def plazo_changed(event=None):
            p = self.combobox_plazo.get()
            src = {"Hoy": ventas_dia, "Semana": ventas_semana, "Mes": ventas_mes}
            _fill(src.get(p, ventas_dia), p)

        self.combobox_plazo.bind("<<ComboboxSelected>>", plazo_changed)
        _fill(ventas_dia, "Hoy")

    # ══════════════════════════════════════════════════════════════════════════
    # REPORTES / CORTE
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_reportes(self):
        self._current_screen = self.opcion_reportes
        sw, sh = self.screen_width, self.screen_height
        now = datetime.now()
        year, month = now.year, now.month
        cuts = self.cortes_semanas(month, year)
        if cuts and now.date() > cuts[-1][1].date():
            month = month + 1 if month < 12 else 1
            year  = year if month > 1 else year + 1
        self.report_month = month
        self.report_year  = year
        self.date_i, self.date_f = self.cortes(self.report_year, self.report_month)

        self.frame_reportes = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_reportes.place(x=int(sw * 0.1), y=0,
                                  width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self._header(self.frame_reportes, "Corte de Ventas")

        # ── Selectores de fecha ──────────────────────────────────────────────
        sel = self._card(self.frame_reportes,
                         x=int(pw * 0.02), y=hh + int(sh * 0.02),
                         w=int(pw * 0.60), h=int(sh * 0.07))
        for lbl, vals, attr, x_pct in [
            ("Año",   self.years_orders(), "combobox_ano",  0.02),
            ("Mes",   list(range(1, 13)),  "combobox_mes",  0.22),
            ("Corte", ["Mes completo"] + list(range(1, len(self.cortes_semanas(self.report_month, self.report_year)) + 1)), "combobox_corte", 0.42),
        ]:
            tk.Label(sel, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10)).place(x=int(pw * x_pct), y=6,
                                               width=int(pw * 0.10), height=int(sh * 0.03))
            cb = ttk.Combobox(sel, state="readonly", values=vals,
                              justify="center", width=8)
            cb.place(x=int(pw * x_pct), y=int(sh * 0.035),
                     width=int(pw * 0.12), height=int(sh * 0.03))
            setattr(self, attr, cb)

        self.combobox_ano.set(self.report_year)
        self.combobox_mes.set(self.report_month)
        self.combobox_corte.set(self.n_cortes)

        # Fechas display
        date_card = self._card(self.frame_reportes,
                               x=int(pw * 0.64), y=hh + int(sh * 0.02),
                               w=int(pw * 0.32), h=int(sh * 0.07))
        self.lbl_fi = tk.Label(date_card, text=f"Inicio: {self.date_i}",
                               bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 11))
        self.lbl_fi.pack(pady=(8, 2), padx=8, anchor="w")
        self.lbl_ff = tk.Label(date_card, text=f"Fin:    {self.date_f}",
                               bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 11))
        self.lbl_ff.pack(padx=8, anchor="w")

        # ── Ventas ──────────────────────────────────────────────────────────
        vcols = ("Fecha", "Producto", "Cant.", "Precio", "Descuento", "Importe")
        self.tree_ventas = ttk.Treeview(self.frame_reportes,
                                        columns=vcols, show="headings", height=10)
        vw = [int(sw * w) for w in (0.04, 0.16, 0.03, 0.05, 0.05, 0.05)]
        for col, w in zip(vcols, vw):
            self.tree_ventas.column(col, anchor="center", width=w)
            self.tree_ventas.heading(col, text=col)
        vy  = hh + int(sh * 0.13)   # ↓ bajado para que label no se encime con el selector
        vx  = int(pw * 0.02)
        vtw = int(pw * 0.52)
        vth = int(sh * 0.37)
        self.tree_ventas.place(x=vx, y=vy, width=vtw, height=vth)
        self._tag_rows(self.tree_ventas)
        self._add_scrollbar(self.frame_reportes, self.tree_ventas, vx, vy, vtw, vth)

        tk.Label(self.frame_reportes, text="VENTAS",
                 bg=BG_MAIN, fg=TXT_MAIN, font=("Arial", 11, "bold")
                 ).place(x=vx, y=vy - int(sh * 0.028),
                         width=int(pw * 0.20), height=int(sh * 0.026))

        # ── Gastos ──────────────────────────────────────────────────────────
        gcols = ("Fecha", "Concepto", "Importe")
        self.tree_gastos = ttk.Treeview(self.frame_reportes,
                                        columns=gcols, show="headings", height=5)
        gw = [int(sw * w) for w in (0.04, 0.22, 0.05)]
        for col, w in zip(gcols, gw):
            self.tree_gastos.column(col, anchor="center", width=w)
            self.tree_gastos.heading(col, text=col)
        gy  = vy + vth + int(sh * 0.06)
        gx  = int(pw * 0.02)
        gtw = int(pw * 0.52)
        gth = int(sh * 0.17)
        self.tree_gastos.place(x=gx, y=gy, width=gtw, height=gth)
        self._tag_rows(self.tree_gastos)

        tk.Label(self.frame_reportes, text="GASTOS",
                 bg=BG_MAIN, fg=TXT_MAIN, font=("Arial", 11, "bold")
                 ).place(x=gx, y=gy - int(sh * 0.028),
                         width=int(pw * 0.20), height=int(sh * 0.026))

        self._btn(self.frame_reportes, "Agregar Gasto", self.agregar_gasto,
                  bg=WARNING, font_size=11
                  ).place(x=int(pw * 0.40), y=gy - int(sh * 0.030),
                          width=int(pw * 0.14), height=int(sh * 0.026))

        # ── Resumen detallado ─────────────────────────────────────────────────
        tot_card = self._card(self.frame_reportes,
                              x=int(pw * 0.58), y=hh + int(sh * 0.11),
                              w=int(pw * 0.38), h=int(sh * 0.48))

        def _res_row(parent, label, fg=TXT_MAIN, bold=False, size=10):
            r = tk.Frame(parent, bg=BG_PANEL)
            r.pack(fill="x", padx=12, pady=2)
            tk.Label(r, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", size), anchor="w").pack(side="left")
            lbl = tk.Label(r, text="$ 0.00", bg=BG_PANEL, fg=fg,
                           font=("Arial", size, "bold" if bold else "normal"),
                           anchor="e")
            lbl.pack(side="right")
            return lbl

        def _sep_line(parent, thick=False):
            tk.Frame(parent, bg=TXT_MAIN if thick else BORDER,
                     height=2 if thick else 1
                     ).pack(fill="x", padx=12, pady=(4, 2))

        tk.Label(tot_card, text="RESUMEN DEL CORTE", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        _sep_line(tot_card)

        tk.Label(tot_card, text="INGRESOS POR MÉTODO DE PAGO",
                 bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 8)).pack(anchor="w", padx=12, pady=(4, 0))
        self.lbl_ef = _res_row(tot_card, "Efectivo:",      fg=SUCCESS)
        self.lbl_tj = _res_row(tot_card, "Tarjeta:",       fg=PRIMARY)
        self.lbl_tr = _res_row(tot_card, "Transferencia:", fg=PRIMARY)

        _sep_line(tot_card)
        self.lbl_vt   = _res_row(tot_card, "Total ventas:",  fg=SUCCESS, bold=True, size=11)
        self.lbl_desc = _res_row(tot_card, "Descuentos:",    fg=DANGER)

        _sep_line(tot_card)
        self.lbl_gt   = _res_row(tot_card, "Gastos:",        fg=DANGER)

        _sep_line(tot_card, thick=True)

        neto_row = tk.Frame(tot_card, bg=BG_PANEL)
        neto_row.pack(fill="x", padx=12, pady=(6, 10))
        tk.Label(neto_row, text="NETO:", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold"), anchor="w").pack(side="left")
        self.lbl_total = tk.Label(neto_row, text="$ 0.00", bg=BG_PANEL, fg=TXT_MAIN,
                                  font=("Arial", 14, "bold"), anchor="e")
        self.lbl_total.pack(side="right")

        def _year_sel(e=None):
            self.report_year = int(self.combobox_ano.get())
            # Refrescar opciones de corte para el nuevo año/mes
            new_cuts = self.cortes_semanas(self.report_year, self.report_month)
            self.combobox_corte.configure(
                values=["Mes completo"] + list(range(1, len(new_cuts) + 1)))
            self.date_i, self.date_f = self.cortes(self.report_year, self.report_month, mes=True)
            self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i, fecha_final=self.date_f)
            self.actualizar_ventas()
            self.actualizar_gastos()
            self.combobox_corte.set("Mes completo")

        def _month_sel(e=None):
            self.report_month = int(self.combobox_mes.get())
            new_cuts = self.cortes_semanas(self.report_year, self.report_month)
            self.combobox_corte.configure(
                values=["Mes completo"] + list(range(1, len(new_cuts) + 1)))
            self.date_i, self.date_f = self.cortes(self.report_year, self.report_month, mes=True)
            self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i, fecha_final=self.date_f)
            self.actualizar_ventas()
            self.actualizar_gastos()
            self.combobox_corte.set("Mes completo")

        def _corte_sel(e=None):
            val = self.combobox_corte.get()
            if val == "Mes completo":
                self.date_i, self.date_f = self.cortes(
                    self.report_year, self.report_month, mes=True)
            else:
                try:
                    n = int(val)
                except ValueError:
                    return
                self.date_i, self.date_f = self.cortes(
                    self.report_year, self.report_month, n_cortes=n)
            self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i, fecha_final=self.date_f)
            self.actualizar_ventas()
            self.actualizar_gastos()

        self.combobox_ano.bind("<<ComboboxSelected>>",  _year_sel)
        self.combobox_mes.bind("<<ComboboxSelected>>",  _month_sel)
        self.combobox_corte.bind("<<ComboboxSelected>>", _corte_sel)

        self.ventas_filtradas = self.filtrar_orders(fecha_inicial=self.date_i, fecha_final=self.date_f)
        self.actualizar_ventas()
        self.actualizar_gastos()

    def agregar_gasto(self):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Agregar Gasto")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.28), int(sh * 0.30)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        tk.Frame(win, bg=WARNING, height=4).pack(fill="x")
        tk.Label(win, text="Nuevo Gasto", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(12, 6))

        for lbl_txt, var_name in [("Fecha (dd/mm/aaaa):", "e_fecha"),
                                   ("Concepto:",            "e_concepto"),
                                   ("Importe ($):",         "e_importe")]:
            row = tk.Frame(win, bg=BG_PANEL)
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=lbl_txt, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=18, anchor="w").pack(side="left")
            e = tk.Entry(row, font=("Arial", 12), relief="flat", bg=BG_MAIN)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            setattr(win, var_name, e)

        now = datetime.now()
        win.e_fecha.insert(0, f"{self.ajusta(now.day)}/{self.ajusta(now.month)}/{now.year}")

        def _guardar():
            try:
                fecha   = win.e_fecha.get()
                concepto = win.e_concepto.get()
                importe  = float(win.e_importe.get())
                self.db.save_expense(fecha, concepto, importe)
                win.destroy()
                self.actualizar_gastos()
            except Exception:
                log_exc("_guardar")

        self._btn(win, "Guardar", _guardar, bg=SUCCESS, font_size=12
                  ).pack(pady=16, ipadx=20, ipady=6)

    def actualizar_ventas(self):
        if not hasattr(self, "gasto_total"):
            self.gasto_total = 0
        self.venta_total = 0
        for row in self.tree_ventas.get_children():
            self.tree_ventas.delete(row)
        i = 0
        for oid, item in self.ventas_filtradas.items():
            for pid, pi in item["Productos"].items():
                self.venta_total += float(pi["Importe"])
                nombre = self.data_products.get(pid, ["?"] * 3)[2]
                precio_unit = (float(pi["Importe"]) + float(pi["Descuento"])) / max(int(pi["Cantidad"]), 1)
                desc_val    = float(pi["Descuento"])
                self._insert_row(self.tree_ventas,
                    (item["Fecha"], nombre, pi["Cantidad"],
                     f"$ {precio_unit:,.2f}",
                     f"$ {desc_val:,.2f}" if desc_val else "—",
                     f"$ {pi['Importe']:,.2f}"),
                    text=oid, idx=i)
                i += 1
        self._actualizar_totales_reporte()

    def actualizar_gastos(self):
        self.gasto_total = 0
        for row in self.tree_gastos.get_children():
            self.tree_gastos.delete(row)
        gastos = self.db.get_expenses(self.date_i, self.date_f)
        for i, g in enumerate(gastos):
            self.gasto_total += float(g["amount"])
            self._insert_row(self.tree_gastos,
                (g["date"], g["concept"], f"$ {g['amount']:.2f}"),
                idx=i)
        self._actualizar_totales_reporte()

    def _actualizar_totales_reporte(self):
        ef = tj = tr = desc = 0.0
        for oid, item in self.ventas_filtradas.items():
            mp = item.get("Metodo_pago", "")
            order_t = sum(float(pi["Importe"])             for pi in item["Productos"].values())
            order_d = sum(float(pi.get("Descuento", 0))   for pi in item["Productos"].values())
            desc += order_d
            if mp == "Tarjeta":
                tj += order_t
            elif mp == "Transferencia":
                tr += order_t
            else:                       # Efectivo o sin clasificar
                ef += order_t
        total = ef + tj + tr
        neto  = total - self.gasto_total

        self.lbl_ef.config(   text=f"$ {ef:,.2f}")
        self.lbl_tj.config(   text=f"$ {tj:,.2f}")
        self.lbl_tr.config(   text=f"$ {tr:,.2f}")
        self.lbl_vt.config(   text=f"$ {total:,.2f}")
        self.lbl_desc.config( text=f"- $ {desc:,.2f}")
        self.lbl_gt.config(   text=f"- $ {self.gasto_total:,.2f}")
        self.lbl_total.config(text=f"$ {neto:,.2f}",
                              fg=SUCCESS if neto >= 0 else DANGER)
        self.lbl_fi.config(text=f"Inicio: {self.date_i}")
        self.lbl_ff.config(text=f"Fin:    {self.date_f}")

    # ══════════════════════════════════════════════════════════════════════════
    # INVENTARIO
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_inventario(self):
        self._current_screen = self.opcion_inventario
        sw, sh = self.screen_width, self.screen_height
        self.data_products       = self.db.get_products()
        self.productos_filtrados = dict(self.data_products)
        if not hasattr(self, '_pedido_carrito'):
            self._pedido_carrito = {}

        self.frame_inventario = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_inventario.place(x=int(sw * 0.1), y=0,
                                    width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)
        self._header(self.frame_inventario, "Inventario / Pedido")

        lx     = int(pw * 0.01)
        lw     = int(pw * 0.57)
        rx     = lx + lw + int(pw * 0.015)
        rw     = pw - rx - int(pw * 0.01)
        cont_y = hh + int(sh * 0.01)

        # ── Panel izquierdo: inventario ──────────────────────────────────────
        row1_y = cont_y
        row1_h = int(sh * 0.05)

        sf = tk.Frame(self.frame_inventario, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        sf.place(x=lx, y=row1_y, width=int(lw * 0.48), height=row1_h)
        tk.Label(sf, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left", padx=8)
        self.entrada_busqueda = tk.Entry(sf, font=("Arial", 12),
                                         relief="flat", bg=BG_PANEL, fg=TXT_MAIN)
        self.entrada_busqueda.pack(side="left", fill="x", expand=True, padx=4)
        self.entrada_busqueda.bind("<KeyRelease>", self._aplicar_filtros_inventario)

        bx = lx + int(lw * 0.50)
        bw = int(lw * 0.23)
        self._btn(self.frame_inventario, "  Agregar",
                  self.window_editar_inventario, bg=SUCCESS, font_size=11
                  ).place(x=bx, y=row1_y, width=bw, height=row1_h)
        self._btn(self.frame_inventario, "  Eliminar",
                  self.eliminar_producto, bg=DANGER, font_size=11
                  ).place(x=bx + bw + int(lw * 0.02), y=row1_y, width=bw, height=row1_h)

        # Filtros
        row2_y = row1_y + row1_h + int(sh * 0.01)
        row2_h = int(sh * 0.042)
        frow = tk.Frame(self.frame_inventario, bg=BG_MAIN)
        frow.place(x=lx, y=row2_y, width=lw, height=row2_h)

        vendedores = ["Todos"] + sorted({
            str(p[7]).strip() for p in self.data_products.values()
            if len(p) > 7 and p[7] and str(p[7]).strip()
        })
        cats = ["Todas"] + sorted({
            str(p[4]).strip() for p in self.data_products.values()
            if len(p) > 4 and p[4] and str(p[4]).strip()
        })
        for lbl_txt, opts, attr in [
            ("Proveedor:", vendedores,                     "_inv_cb_vendor"),
            ("Categoría:", cats,                           "_inv_cb_cat"),
            ("Stock:",     ["Todos","🔴 Sin stock","🟡 Bajo","🟢 OK"], "_inv_cb_stock"),
        ]:
            tk.Label(frow, text=lbl_txt, bg=BG_MAIN, fg=TXT_GRAY,
                     font=("Arial", 10)).pack(side="left", padx=(8, 2))
            cb = ttk.Combobox(frow, values=opts, state="readonly",
                              font=("Arial", 10), width=13)
            cb.set(opts[0])
            cb.pack(side="left", padx=(0, 2))
            cb.bind("<<ComboboxSelected>>", self._aplicar_filtros_inventario)
            setattr(self, attr, cb)
        self._btn(frow, "✕ Limpiar", self._limpiar_filtros_inventario,
                  bg=TXT_GRAY, font_size=10).pack(side="left", padx=10, ipady=2)

        # Árbol de inventario
        ty = row2_y + row2_h + int(sh * 0.01)
        tw = lw - 14
        th = sh - ty - int(sh * 0.02)
        cols = ("SKU", "Producto", "Tall/Color", "Categoría", "Marca", "Cant.", "Costo")
        self.tree_inventario = ttk.Treeview(self.frame_inventario,
                                            columns=cols, show="headings", height=20)
        col_ws = [int(lw * w) for w in (0.07, 0.28, 0.12, 0.13, 0.11, 0.07, 0.09)]
        for col, cw in zip(cols, col_ws):
            self.tree_inventario.column(col, anchor="center", width=cw, minwidth=30)
            self.tree_inventario.heading(col, text=col)
        self.tree_inventario.place(x=lx, y=ty, width=tw, height=th)
        self._tag_rows(self.tree_inventario)
        self.tree_inventario.tag_configure("qty_red",    foreground=DANGER)
        self.tree_inventario.tag_configure("qty_yellow", foreground=WARNING)
        self.tree_inventario.tag_configure("qty_green",  foreground=SUCCESS)
        self._add_scrollbar(self.frame_inventario, self.tree_inventario, lx, ty, tw, th)
        self.tree_inventario.bind("<Double-Button-1>", self.editar_inventario)
        self._inv_click_timer = None
        self.tree_inventario.bind("<ButtonRelease-1>", self._inv_click_add_to_cart)

        # ── Ordenamiento por columna ──────────────────────────────────────────
        # Mapeo: nombre columna → índice en item[] y tipo de dato
        self._inv_sort = {"col": None, "asc": True}
        _SORT_MAP = {
            "SKU":       (0,  str),
            "Producto":  (2,  str),
            "Tall/Color":(5,  str),
            "Categoría": (4,  str),
            "Marca":     (6,  str),
            "Cant.":     (8,  int),
            "Costo":     (9,  float),
        }

        def _sort_by(col):
            idx, cast = _SORT_MAP[col]
            asc = not self._inv_sort["asc"] if self._inv_sort["col"] == col else True
            self._inv_sort["col"] = col
            self._inv_sort["asc"] = asc

            def _key(pair):
                val = pair[1][idx]
                try:
                    return cast(val)
                except (ValueError, TypeError):
                    return cast() if cast != str else ""

            self.productos_filtrados = dict(
                sorted(self.productos_filtrados.items(), key=_key, reverse=not asc)
            )

            # Actualizar flechas en encabezados
            for c in cols:
                arrow = (" ↑" if asc else " ↓") if c == col else ""
                self.tree_inventario.heading(c, text=c + arrow)

            self.actualizar_tree_inventario()

        for col in cols:
            self.tree_inventario.heading(col, command=lambda c=col: _sort_by(c))

        # ── Panel derecho: carrito ───────────────────────────────────────────
        cart_outer = tk.Frame(self.frame_inventario, bg=BG_PANEL,
                              highlightbackground=BORDER, highlightthickness=1)
        cart_outer.place(x=rx, y=cont_y, width=rw, height=sh - cont_y - int(sh * 0.02))

        tk.Label(cart_outer, text="  Pedido de Compra",
                 bg=PRIMARY, fg="white",
                 font=("Arial", 12, "bold"), anchor="w"
                 ).pack(fill="x", ipady=6)

        # Selector de proveedor
        prov_row = tk.Frame(cart_outer, bg=BG_PANEL)
        prov_row.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(prov_row, text="Proveedor:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), width=10, anchor="w").pack(side="left")
        _prov_opts = [""] + sorted({
            str(p[7]).strip() for p in self.data_products.values()
            if len(p) > 7 and p[7] and str(p[7]).strip()
        })
        self._pedido_vendor_cb = ttk.Combobox(prov_row, values=_prov_opts,
                                              font=("Arial", 11), width=20)
        self._pedido_vendor_cb.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Área scrollable del carrito
        mid = tk.Frame(cart_outer, bg=BG_PANEL)
        mid.pack(fill="both", expand=True)

        self._cart_canvas = tk.Canvas(mid, bg=BG_PANEL, highlightthickness=0)
        cart_sb = ttk.Scrollbar(mid, orient="vertical",
                                command=self._cart_canvas.yview)
        cart_sb.pack(side="right", fill="y")
        self._cart_canvas.pack(side="left", fill="both", expand=True)
        self._cart_canvas.configure(yscrollcommand=cart_sb.set)

        self._cart_inner = tk.Frame(self._cart_canvas, bg=BG_PANEL)
        self._cart_win_id = self._cart_canvas.create_window(
            (0, 0), window=self._cart_inner, anchor="nw")

        def _on_inner_cfg(e):
            self._cart_canvas.configure(scrollregion=self._cart_canvas.bbox("all"))
        def _on_canvas_cfg(e):
            self._cart_canvas.itemconfig(self._cart_win_id, width=e.width)
        self._cart_inner.bind("<Configure>", _on_inner_cfg)
        self._cart_canvas.bind("<Configure>", _on_canvas_cfg)

        # Footer: totales + botones
        footer = tk.Frame(cart_outer, bg=BG_PANEL)
        footer.pack(fill="x", side="bottom", pady=6)
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 6))

        self._lbl_subtotal = tk.Label(footer, text="Subtotal (sin IVA):  $0.00",
                                       bg=BG_PANEL, fg=TXT_GRAY,
                                       font=("Arial", 11), anchor="e")
        self._lbl_subtotal.pack(fill="x", padx=12)
        self._lbl_iva = tk.Label(footer, text="IVA 16%:             $0.00",
                                  bg=BG_PANEL, fg=TXT_GRAY,
                                  font=("Arial", 11), anchor="e")
        self._lbl_iva.pack(fill="x", padx=12)
        self._lbl_total = tk.Label(footer, text="TOTAL:               $0.00",
                                    bg=BG_PANEL, fg=TXT_MAIN,
                                    font=("Arial", 13, "bold"), anchor="e")
        self._lbl_total.pack(fill="x", padx=12, pady=(2, 6))

        brow = tk.Frame(footer, bg=BG_PANEL)
        brow.pack(fill="x", padx=8, pady=(0, 4))
        self._btn(brow, "💾 Guardar Pedido", self._guardar_pedido,
                  bg=SUCCESS, font_size=11
                  ).pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=5)
        self._btn(brow, "🖨 Imprimir Pedido", self._imprimir_pedido,
                  bg=PRIMARY, font_size=11
                  ).pack(side="left", fill="x", expand=True, padx=(4, 0), ipady=5)

        self.actualizar_tree_inventario()
        self._refresh_cart()

    def actualizar_tree_inventario(self):
        for row in self.tree_inventario.get_children():
            self.tree_inventario.delete(row)
        for i, (idx, item) in enumerate(self.productos_filtrados.items()):
            qty = int(item[8]) if str(item[8]).strip() else 0
            ty  = int(item[11]) if len(item) > 11 and str(item[11]).strip() else 1
            tg  = int(item[12]) if len(item) > 12 and str(item[12]).strip() else 3
            qty_tag = ("qty_red" if qty < ty else
                       "qty_yellow" if qty < tg else "qty_green")
            stripe = "even" if i % 2 == 0 else "odd"
            costo_fmt = f"${float(item[9]):,.2f}" if item[9] else "$0.00"
            self.tree_inventario.insert("", "end", text=idx,
                values=(item[0], item[2], item[5], item[4],
                        item[6], item[8], costo_fmt),
                tags=(stripe, qty_tag))

    def buscar_producto_inventario(self, event=None):
        self._aplicar_filtros_inventario()

    def _aplicar_filtros_inventario(self, event=None):
        self.data_products = self.db.get_products()
        term       = self.entrada_busqueda.get().lower().strip()
        sel_vendor = getattr(self, "_inv_cb_vendor", None)
        sel_cat    = getattr(self, "_inv_cb_cat",    None)
        sel_stock  = getattr(self, "_inv_cb_stock",  None)
        vendor = sel_vendor.get() if sel_vendor else "Todos"
        cat    = sel_cat.get()    if sel_cat    else "Todas"
        stock  = sel_stock.get()  if sel_stock  else "Todos"

        result = {}
        for idx, item in self.data_products.items():
            if term and not self.find(item[:5], term):
                continue
            if vendor != "Todos" and str(item[7]).strip() != vendor:
                continue
            if cat != "Todas" and str(item[4]).strip() != cat:
                continue
            if stock != "Todos":
                qty = int(item[8]) if str(item[8]).strip() else 0
                ty  = int(item[11]) if len(item) > 11 and str(item[11]).strip() else 1
                tg  = int(item[12]) if len(item) > 12 and str(item[12]).strip() else 3
                if stock == "🔴 Sin stock" and not (qty < ty):
                    continue
                if stock == "🟡 Bajo" and not (ty <= qty < tg):
                    continue
                if stock == "🟢 OK" and not (qty >= tg):
                    continue
            result[idx] = item
        self.productos_filtrados = result
        # Resetear ordenamiento al filtrar para evitar flechas inconsistentes
        if hasattr(self, "_inv_sort") and self._inv_sort["col"]:
            self._inv_sort["col"] = None
            self._inv_sort["asc"] = True
            if hasattr(self, "tree_inventario"):
                for _c in ("SKU","Producto","Tall/Color","Categoría","Marca","Cant.","Costo"):
                    try:
                        self.tree_inventario.heading(_c, text=_c)
                    except Exception:
                        log_exc("_aplicar_filtros_inventario")
        self.actualizar_tree_inventario()

    def _limpiar_filtros_inventario(self):
        self.entrada_busqueda.delete(0, tk.END)
        for attr, default in [("_inv_cb_vendor", "Todos"),
                              ("_inv_cb_cat",    "Todas"),
                              ("_inv_cb_stock",  "Todos")]:
            cb = getattr(self, attr, None)
            if cb:
                cb.set(default)
        self._aplicar_filtros_inventario()

    # ── Carrito de pedido de compra ──────────────────────────────────────────
    def _inv_click_add_to_cart(self, event=None):
        region = self.tree_inventario.identify_region(event.x, event.y)
        if region not in ("cell", "tree"):
            return
        if self._inv_click_timer:
            self.frame_inventario.after_cancel(self._inv_click_timer)
            self._inv_click_timer = None
            return   # doble clic → cancelar add, dejar que editar_inventario actúe
        self._inv_click_timer = self.frame_inventario.after(
            250, self._do_add_selected_to_cart)

    def _do_add_selected_to_cart(self):
        self._inv_click_timer = None
        sel = self.tree_inventario.selection()
        if not sel:
            return
        pid = self.tree_inventario.item(sel[0], "text")
        if not pid or pid not in self.data_products:
            return
        if pid in self._pedido_carrito:
            self._pedido_carrito[pid]['qty'] += 1
        else:
            self._pedido_carrito[pid] = {
                'item': self.data_products[pid],
                'qty': 1
            }
        self._refresh_cart()

    def _refresh_cart(self):
        """Redibuja el contenido del carrito de pedido."""
        if not hasattr(self, '_cart_inner'):
            return
        for w in self._cart_inner.winfo_children():
            w.destroy()

        if not self._pedido_carrito:
            tk.Label(self._cart_inner,
                     text="Haz clic en un producto\npara agregarlo al pedido",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 11),
                     justify="center").pack(pady=40)
            self._update_cart_totals()
            return

        # Encabezado de la lista
        hdr = tk.Frame(self._cart_inner, bg=BG_SIDEBAR)
        hdr.pack(fill="x")
        for txt, expand, w in [
            ("Producto",  True,  0),
            ("Cant.",     False, 52),
            ("Costo",     False, 62),
            ("Total",     False, 68),
            ("",          False, 28),
        ]:
            tk.Label(hdr, text=txt, bg=BG_SIDEBAR, fg=TXT_LIGHT,
                     font=("Arial", 9, "bold"),
                     anchor="center", padx=3, width=w if w else 1
                     ).pack(side="left", fill="x" if expand else None,
                            expand=expand)

        for i, (pid, entry) in enumerate(list(self._pedido_carrito.items())):
            item = entry['item']
            cost = float(item[9]) if item[9] else 0.0
            name = str(item[2])
            sku  = str(item[0])
            sc   = str(item[5])

            bg   = BG_PANEL if i % 2 == 0 else ROW_ALT
            row  = tk.Frame(self._cart_inner, bg=bg, pady=3)
            row.pack(fill="x")

            # Nombre + SKU
            info = tk.Frame(row, bg=bg)
            info.pack(side="left", fill="x", expand=True, padx=(6, 2))
            tk.Label(info, text=name[:22], bg=bg, fg=TXT_MAIN,
                     font=("Arial", 10), anchor="w").pack(anchor="w")
            tk.Label(info, text=f"{sku}  {sc}"[:26], bg=bg, fg=TXT_GRAY,
                     font=("Arial", 8), anchor="w").pack(anchor="w")

            # Cantidad (Spinbox)
            qty_var = tk.StringVar(value=str(entry['qty']))
            line_total_var = tk.StringVar(
                value=f"${cost * entry['qty']:,.2f}")

            spn = tk.Spinbox(row, from_=1, to=99999,
                             textvariable=qty_var,
                             width=5, font=("Arial", 11),
                             relief="flat", bg=BG_PANEL, fg=TXT_MAIN)
            spn.pack(side="left", padx=2)

            tk.Label(row, text=f"${cost:,.2f}", bg=bg, fg=TXT_GRAY,
                     font=("Arial", 10), width=7,
                     anchor="e").pack(side="left")

            lbl_total = tk.Label(row, textvariable=line_total_var,
                                 bg=bg, fg=TXT_MAIN,
                                 font=("Arial", 10, "bold"),
                                 width=8, anchor="e")
            lbl_total.pack(side="left")

            def _remove(p=pid):
                del self._pedido_carrito[p]
                self._refresh_cart()

            tk.Button(row, text="×", bg=bg, fg=DANGER, bd=0,
                      font=("Arial", 14, "bold"), cursor="hand2",
                      command=_remove).pack(side="left", padx=(2, 4))

            def _on_qty(*args, p=pid, c=cost, lv=line_total_var):
                try:
                    q = max(1, int(qty_var.get()))
                    self._pedido_carrito[p]['qty'] = q
                    lv.set(f"${c * q:,.2f}")
                    self._update_cart_totals()
                except ValueError:
                    pass
            qty_var.trace_add("write", _on_qty)

        self._update_cart_totals()

    def _update_cart_totals(self):
        if not hasattr(self, '_lbl_subtotal'):
            return
        subtotal = sum(
            float(e['item'][9]) * e['qty']
            for e in self._pedido_carrito.values()
            if e['item'][9]
        )
        iva   = subtotal * 0.16
        total = subtotal + iva
        self._lbl_subtotal.config(text=f"Subtotal (sin IVA):  ${subtotal:,.2f}")
        self._lbl_iva.config(text=f"IVA 16%:             ${iva:,.2f}")
        self._lbl_total.config(text=f"TOTAL:               ${total:,.2f}")

    @staticmethod
    def _safe_pdf_str(s):
        """Convierte texto a windows-1252, reemplazando caracteres no soportados."""
        return str(s).encode("windows-1252", errors="replace").decode("windows-1252")

    @staticmethod
    def _downloads_path(filename):
        """Devuelve la ruta completa en la carpeta Descargas del usuario."""
        dl = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(dl, exist_ok=True)
        return os.path.join(dl, filename)

    def _pdf_save_and_open(self, pdf, filename):
        """Guarda el PDF en Descargas y lo abre automáticamente."""
        out = self._downloads_path(filename)
        pdf.output(out)
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", out])
            elif platform.system() == "Windows":
                os.startfile(out)
            else:
                subprocess.Popen(["xdg-open", out])
        except Exception:
            log_exc("_pdf_save_and_open")
        return out

    def _guardar_pedido(self):
        if not self._pedido_carrito:
            messagebox.showwarning("Carrito vacío",
                                   "Agrega productos al pedido antes de guardar.")
            return
        items = [
            {'product_id': pid,
             'sku':        str(e['item'][0]),
             'name':       str(e['item'][2]),
             'size_color': str(e['item'][5]),
             'quantity':   e['qty'],
             'unit_cost':  float(e['item'][9]) if e['item'][9] else 0.0}
            for pid, e in self._pedido_carrito.items()
        ]
        _cb = getattr(self, '_pedido_vendor_cb', None)
        vendor_str = _cb.get().strip() if _cb else ''
        editing_id = getattr(self, '_editing_purchase_order_id', None)
        if editing_id:
            # Actualizar el pedido existente conservando el mismo número
            oid = self.db.update_purchase_order(editing_id, items, vendor=vendor_str)
            self._editing_purchase_order_id = None
        else:
            oid = self.db.save_purchase_order(items, vendor=vendor_str)
        messagebox.showinfo("Pedido guardado",
                            f"Pedido #{oid} guardado correctamente.")
        self._pedido_carrito = {}
        if _cb:
            _cb.set('')
        self._refresh_cart()

    def _imprimir_pedido(self):
        if not self._pedido_carrito:
            messagebox.showwarning("Carrito vacío",
                                   "Agrega productos al pedido antes de imprimir.")
            return
        if not _FPDF:
            messagebox.showerror("PDF no disponible",
                                 "Instala fpdf2:\n  pip install fpdf2")
            return
        try:
            _cb = getattr(self, '_pedido_vendor_cb', None)
            vendor_str = _cb.get().strip() if _cb else ''
            self._generar_pdf_pedido(self._pedido_carrito, vendor_name=vendor_str)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

    def _generar_pdf_pedido(self, carrito, pedido_id=None, vendor_name="",
                            show_cost=True):
        """Genera PDF de pedido de compra. carrito: dict {pid: {item, qty}}
           o lista de dicts con keys sku/name/size_color/quantity/unit_cost."""
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        _vslug   = vendor_name.replace(" ", "_")[:20] if vendor_name else ""
        _cost_sfx = "" if show_cost else "_sin_costo"
        out_name = (f"pedido_{_vslug}{_cost_sfx}_{ts}.pdf" if _vslug
                    else f"pedido{_cost_sfx}_{ts}.pdf")
        sf  = self._safe_pdf_str

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.core_fonts_encoding = "windows-1252"
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(15, 15, 15)
        pdf.add_page()
        W = 180

        # Encabezado
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(W, 8, "ORTOPEDIA BIOMED", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        lbl_pid = f"  #{pedido_id}" if pedido_id else ""
        pdf.cell(W, 5, sf(f"Pedido de Compra{lbl_pid}"),
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(W, 5,
                 sf(f"Fecha: {datetime.now().strftime('%d/%m/%Y  %H:%M')}"),
                 align="C", new_x="LMARGIN", new_y="NEXT")
        if vendor_name:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(W, 5, sf(f"Proveedor: {vendor_name}"),
                     align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(4)

        # Columnas según modo
        if show_cost:
            # SKU | Producto | Talla/Color | Cant. | Costo unit. | Total línea
            COL = [28, 55, 30, 18, 28, 21]
            HDR = ["SKU", "Producto", "Talla/Color", "Cant.", "Costo unit.", "Total"]
        else:
            # SKU | Producto | Talla/Color | Cant.
            COL = [35, 85, 40, 20]
            HDR = ["SKU", "Producto", "Talla/Color", "Cant."]

        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        for h, c in zip(HDR, COL):
            pdf.cell(c, 7, h, border=0, align="C", fill=True)
        pdf.ln()

        # Filas — acepta tanto el carrito del inventario como lista de items del DB
        pdf.set_text_color(15, 23, 42)
        subtotal = 0.0
        rows = []
        if isinstance(carrito, dict):
            for pid, entry in carrito.items():
                item = entry['item']
                rows.append((str(item[0]), str(item[2]), str(item[5]),
                             entry['qty'],
                             float(item[9]) if item[9] else 0.0))
        else:
            for it in carrito:
                rows.append((str(it['sku']), str(it['name']), str(it['size_color']),
                             int(it['quantity']), float(it['unit_cost'])))

        for i, (sku, name, sc, qty, cost) in enumerate(rows):
            fill = (i % 2 == 0)
            pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.set_font("Helvetica", "", 9)
            linea = qty * cost
            subtotal += linea
            pdf.cell(COL[0], 6.5, sf(sku[:18]),    border=0, fill=fill, align="C")
            pdf.cell(COL[1], 6.5, sf(name[:34]),   border=0, fill=fill)
            pdf.cell(COL[2], 6.5, sf(sc[:16]),     border=0, fill=fill, align="C")
            pdf.cell(COL[3], 6.5, str(qty),        border=0, fill=fill, align="C")
            if show_cost:
                pdf.cell(COL[4], 6.5, f"${cost:,.2f}",   border=0, fill=fill, align="R")
                pdf.cell(COL[5], 6.5, f"${linea:,.2f}",  border=0, fill=fill, align="R")
            pdf.ln()

        # Totales (solo con costo)
        if show_cost:
            iva   = round(subtotal * 0.16, 2)
            total = round(subtotal + iva, 2)
            pdf.ln(3)
            pdf.set_draw_color(30, 41, 59)
            pdf.set_line_width(0.3)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)
            col_lbl = sum(COL[:4])
            col_val = COL[4] + COL[5]
            for lbl, val in (("Subtotal:", subtotal), ("IVA 16%:", iva), ("TOTAL:", total)):
                bold = lbl == "TOTAL:"
                pdf.set_font("Helvetica", "B" if bold else "", 9)
                pdf.cell(col_lbl, 6, lbl, border=0, align="R")
                pdf.cell(col_val, 6, f"${val:,.2f}", border=0, align="R",
                         new_x="LMARGIN", new_y="NEXT")

        self._pdf_save_and_open(pdf, out_name)

    def editar_inventario(self, event=None):
        sel = self.tree_inventario.selection()
        if not sel:
            return
        idx_pos = self.tree_inventario.index(sel[0])
        idx = list(self.productos_filtrados.keys())[idx_pos]
        self.window_editar_inventario(index=idx, item_producto=self.data_products[idx])

    def eliminar_producto(self):
        sel = self.tree_inventario.selection()
        if not sel:
            return
        idx_pos = self.tree_inventario.index(sel[0])
        idx = list(self.productos_filtrados.keys())[idx_pos]
        nombre = f"{self.data_products[idx][2]} {self.data_products[idx][5]}"

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Confirmar")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.28), int(sh * 0.22)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        tk.Frame(win, bg=DANGER, height=4).pack(fill="x")
        tk.Label(win, text="Eliminar producto", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(win, text=nombre, bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(pady=4)

        btn_row = tk.Frame(win, bg=BG_PANEL)
        btn_row.pack(pady=16)

        def _confirmar():
            self.data_products.pop(idx, None)
            self.productos_filtrados.pop(idx, None)
            self.db.delete_product(idx)
            win.destroy()
            self.actualizar_tree_inventario()

        self._btn(btn_row, "Eliminar", _confirmar, bg=DANGER, font_size=12
                  ).pack(side="left", padx=8, ipadx=16, ipady=6)
        self._btn(btn_row, "Cancelar", win.destroy, bg=TXT_GRAY, font_size=12
                  ).pack(side="left", padx=8, ipadx=16, ipady=6)

    def window_editar_inventario(self, index="", item_producto=""):
        if not item_producto:
            index = self.db.max_product_id()

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Producto")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.32), int(sh * 0.82)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(win, text=f"Producto #{index}", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(10, 6))

        def _valores_existentes(fi):
            return sorted({
                str(p[fi]).strip()
                for p in self.data_products.values()
                if len(p) > fi and p[fi] and str(p[fi]).strip()
            })

        combo_opts = {
            4: _valores_existentes(4),
            5: _valores_existentes(5),
            6: _valores_existentes(6),
            7: _valores_existentes(7),   # proveedores que venden a la tienda
        }

        fields = [
            ("SKU",         0), ("PCU",      1), ("Producto", 2),
            ("Talla/Color", 5), ("Categoria",4), ("Marca",    6),
            ("Vendedor",    7), ("Cantidad", 8), ("Costo",    9),
            ("Precio",     10),
        ]
        entries = {}
        for lbl, fi in fields:
            row = tk.Frame(win, bg=BG_PANEL)
            row.pack(fill="x", padx=24, pady=3)
            tk.Label(row, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=12, anchor="w").pack(side="left")
            if fi in combo_opts:
                e = ttk.Combobox(row, font=("Arial", 12),
                                 values=combo_opts[fi], width=22)
                e.pack(side="left", fill="x", expand=True, ipady=4)
            else:
                e = tk.Entry(row, font=("Arial", 12), relief="flat",
                             bg=BG_MAIN, highlightbackground=BORDER,
                             highlightthickness=1)
                e.pack(side="left", fill="x", expand=True, ipady=4)
            if item_producto:
                e.delete(0, tk.END)
                e.insert(0, str(item_producto[fi]))
            entries[fi] = e

        # ── Umbrales de stock ────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(8, 4))
        tk.Label(win, text="Umbrales de stock", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=24)

        thresh_defaults = {11: 1, 12: 3}
        thresh_colors   = {11: WARNING, 12: SUCCESS}
        thresh_labels   = {11: "🟡 Min. amarillo", 12: "🟢 Min. verde"}
        for fi, lbl_txt in thresh_labels.items():
            row = tk.Frame(win, bg=BG_PANEL)
            row.pack(fill="x", padx=24, pady=2)
            tk.Label(row, text=lbl_txt, bg=BG_PANEL, fg=thresh_colors[fi],
                     font=("Arial", 11, "bold"), width=16, anchor="w").pack(side="left")
            e = tk.Entry(row, font=("Arial", 12), relief="flat", width=6,
                         bg=BG_MAIN, highlightbackground=thresh_colors[fi],
                         highlightthickness=2)
            e.pack(side="left", ipady=4)
            default_val = str(item_producto[fi]) if item_producto and len(item_producto) > fi and str(item_producto[fi]).strip() else str(thresh_defaults[fi])
            e.insert(0, default_val)
            entries[fi] = e

        def _aplicar():
            try:
                if not item_producto:
                    self.data_products[index] = [""] * 13
                item = list(self.data_products[index]) if item_producto else [""] * 13
                while len(item) < 13:
                    item.append("")
                for fi, e in entries.items():
                    val = e.get()
                    if fi == 8:
                        item[fi] = int(val)
                    elif fi in (9, 10):
                        item[fi] = float(val)
                    elif fi in (11, 12):
                        item[fi] = int(val) if str(val).strip() else thresh_defaults[fi]
                    else:
                        item[fi] = val
                self.data_products[index] = item
                self.db.save_product(index, item)
                self.productos_filtrados[index] = item
                self.actualizar_tree_inventario()
                win.destroy()
            except Exception:
                log_exc("_aplicar")

        self._btn(win, "Guardar cambios", _aplicar, bg=SUCCESS, font_size=12
                  ).pack(pady=14, ipadx=20, ipady=6)

    # ══════════════════════════════════════════════════════════════════════════
    # ORDENES
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_ordenes(self):
        self._current_screen = self.opcion_ordenes
        sw, sh = self.screen_width, self.screen_height
        self.data_products = self.db.get_products()

        self.frame_ordenes = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_ordenes.place(x=int(sw * 0.1), y=0,
                                 width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self._header(self.frame_ordenes, "Historial de Ordenes")

        # ── Barra de filtros ──────────────────────────────────────────────────
        self._orders_filter = "dia"
        self._orders_offset = 0          # 0=current, -1=prev, +1=next period

        fbar_y = hh + int(sh * 0.012)
        fbar_h = int(sh * 0.042)
        nav_h  = int(sh * 0.042)

        fbar = tk.Frame(self.frame_ordenes, bg=BG_MAIN)
        fbar.place(x=int(pw * 0.06), y=fbar_y, width=int(pw * 0.88), height=fbar_h)

        self._ord_filter_btns = {}
        for ftxt, fkey in [("  Día  ", "dia"), ("  Semana  ", "semana"),
                            ("  Mes  ", "mes"), ("  Año  ", "anio")]:
            is_sel = fkey == "dia"
            btn = tk.Label(fbar, text=ftxt,
                           bg=PRIMARY if is_sel else BG_PANEL,
                           fg="white" if is_sel else TXT_GRAY,
                           font=("Arial", 11, "bold"), cursor="hand2",
                           padx=6, pady=4,
                           highlightbackground=BORDER, highlightthickness=1)
            btn.pack(side="left", padx=4)

            def _sel(k=fkey):
                self._orders_filter = k
                self._orders_offset = 0
                for kk, bb in self._ord_filter_btns.items():
                    bb.config(bg=PRIMARY if kk == k else BG_PANEL,
                              fg="white" if kk == k else TXT_GRAY)
                self.actualizar_ordenes()

            btn.bind("<Button-1>", lambda e, s=_sel: s())
            self._ord_filter_btns[fkey] = btn

        self._lbl_ord_count = tk.Label(fbar, text="", bg=BG_MAIN, fg=TXT_GRAY,
                                       font=("Arial", 10))
        self._lbl_ord_count.pack(side="left", padx=16)

        # ── Navegador de período (oculto para "dia") ──────────────────────────
        nav_y = fbar_y + fbar_h + int(sh * 0.006)
        nav_frame = tk.Frame(self.frame_ordenes, bg=BG_MAIN)
        nav_frame.place(x=int(pw * 0.06), y=nav_y, width=int(pw * 0.60), height=nav_h)

        self._lbl_periodo = tk.Label(nav_frame, text="", bg=BG_PANEL, fg=TXT_MAIN,
                                     font=("Arial", 11, "bold"), width=28)

        def _nav(delta):
            self._orders_offset += delta
            self.actualizar_ordenes()

        btn_prev = self._btn(nav_frame, " ◀ ", lambda: _nav(-1), bg=BG_SIDEBAR, font_size=11)
        btn_next = self._btn(nav_frame, " ▶ ", lambda: _nav(+1), bg=BG_SIDEBAR, font_size=11)
        btn_prev.pack(side="left", ipady=3, ipadx=4)
        self._lbl_periodo.pack(side="left", padx=8)
        btn_next.pack(side="left", ipady=3, ipadx=4)
        self._nav_frame = nav_frame

        # ── Tabla ─────────────────────────────────────────────────────────────
        cols = ("ID", "Fecha", "Hora", "Cliente", "Vendedor",
                "Pago", "Importe", "Desc. $", "Motivo", "Estatus", "Ticket")
        self.tree_orders = ttk.Treeview(self.frame_ordenes,
                                        columns=cols, show="headings", height=22)
        widths = [int(sw * w) for w in (0.05, 0.05, 0.04, 0.09, 0.07, 0.05, 0.06, 0.06, 0.09, 0.07, 0.04)]
        for col, w in zip(cols, widths):
            self.tree_orders.column(col,
                anchor="w" if col == "Motivo" else "center", width=w)
            self.tree_orders.heading(col, text=col)

        ty = nav_y + nav_h + int(sh * 0.018)
        tw = int(pw * 0.88)
        th = sh - ty - int(sh * 0.03)
        self.tree_orders.place(x=int(pw * 0.06), y=ty, width=tw, height=th)
        self._tag_rows(self.tree_orders)
        self.tree_orders.tag_configure("st_pending",   background="#FEF3C7", foreground="#92400E")
        self.tree_orders.tag_configure("st_cancelled", foreground=DANGER)
        self._add_scrollbar(self.frame_ordenes, self.tree_orders,
                            int(pw * 0.06), ty, tw, th)
        self.tree_orders.bind("<Double-Button-1>", self.modificar_ordenes)

        def _on_ticket_click(event):
            row = self.tree_orders.identify_row(event.y)
            col = self.tree_orders.identify_column(event.x)
            if not row or col != "#11":
                return
            vals = self.tree_orders.item(row)["values"]
            if vals and str(vals[10]) == "Ver":
                pdf_path = self._ticket_path(str(vals[0]))
                if os.path.exists(pdf_path):
                    try:
                        if platform.system() == "Windows":
                            os.startfile(pdf_path)
                        elif platform.system() == "Darwin":
                            subprocess.Popen(["open", pdf_path])
                        else:
                            subprocess.Popen(["xdg-open", pdf_path])
                    except Exception:
                        log_exc("_on_ticket_click")

        self.tree_orders.bind("<ButtonRelease-1>", _on_ticket_click)

        tk.Label(self.frame_ordenes,
                 text="Doble clic para ver detalle  ·  Clic en «Ver» para abrir ticket",
                 bg=BG_MAIN, fg=TXT_GRAY, font=("Arial", 10)
                 ).place(x=int(pw * 0.06), y=ty - int(sh * 0.025),
                         width=tw, height=int(sh * 0.022))
        self.actualizar_ordenes()

    def actualizar_ordenes(self):
        import calendar as _cal
        fmt    = "%d/%m/%Y"
        now    = datetime.now()
        filt   = getattr(self, "_orders_filter", "dia")
        offset = getattr(self, "_orders_offset", 0)
        MESES  = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

        if filt == "dia":
            target_day = (now + timedelta(days=offset)).date()
            ok         = lambda d, t=target_day: d.date() == t
            DIAS_ES    = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
            period_lbl = f"{DIAS_ES[target_day.weekday()]}  {target_day.strftime('%d/%m/%Y')}"
            show_nav   = True
        elif filt == "semana":
            ref  = now + timedelta(weeks=offset)
            lun  = ref.date() - timedelta(days=ref.weekday())
            sab  = lun + timedelta(days=5)
            ok   = lambda d, a=lun, b=sab: a <= d.date() <= b
            period_lbl = f"{lun.strftime('%d %b')} – {sab.strftime('%d %b %Y')}"
            show_nav   = True
        elif filt == "mes":
            m = now.month + offset
            y = now.year
            while m < 1:  m += 12; y -= 1
            while m > 12: m -= 12; y += 1
            last = _cal.monthrange(y, m)[1]
            from datetime import date as _date
            first_d = _date(y, m, 1)
            last_d  = _date(y, m, last)
            ok      = lambda d, a=first_d, b=last_d: a <= d.date() <= b
            period_lbl = f"{MESES[m-1]} {y}"
            show_nav   = True
        else:   # anio
            target_y   = now.year + offset
            ok         = lambda d, ty=target_y: d.year == ty
            period_lbl = str(now.year + offset)
            show_nav   = True

        # Actualizar etiqueta del período
        try:
            if hasattr(self, "_lbl_periodo"):
                self._lbl_periodo.config(text=period_lbl if show_nav else "")
        except Exception:
            log_exc("actualizar_ordenes")

        for row in self.tree_orders.get_children():
            self.tree_orders.delete(row)

        order_list = list(self.data_orders.keys())
        order_list.reverse()
        i = 0
        for oid in order_list:
            item = self.data_orders[oid]
            try:
                fecha_dt = datetime.strptime(item["Fecha"], fmt)
            except Exception:
                continue
            if not ok(fecha_dt):
                continue

            status = item.get("Status", "activa")
            st_lbl = {"activa": "✓ Activa",
                      "cancelacion_pendiente": "⏳ Pendiente",
                      "cancelada": "✗ Cancelada"}.get(status, status)
            tiene_ticket = os.path.exists(self._ticket_path(oid))
            stripe = "even" if i % 2 == 0 else "odd"
            if status == "cancelacion_pendiente":
                tags = ("st_pending",)
            elif status == "cancelada":
                tags = (stripe, "st_cancelled")
            else:
                tags = (stripe,)

            dr = item.get("Descuento_razon", "Sin descuento") or "Sin descuento"
            disc_total = sum(float(pi.get("Descuento", 0))
                             for pi in item.get("Productos", {}).values())
            disc_str = f"$ {disc_total:,.2f}" if disc_total > 0.005 else "—"
            self.tree_orders.insert("", "end", text=oid,
                values=(oid, item["Fecha"], item["Hora"], item["Cliente"],
                        item["Vendedor"], item.get("Metodo_pago", "—"),
                        f"$ {item['Importe_total']}",
                        disc_str, dr, st_lbl, "Ver" if tiene_ticket else "—"),
                tags=tags)
            i += 1

        count = i
        if hasattr(self, "_lbl_ord_count"):
            self._lbl_ord_count.config(text=f"{count} orden{'es' if count != 1 else ''}")

    def modificar_ordenes(self, event=None):
        sel = self.tree_orders.selection()
        if not sel:
            return
        oid   = self.tree_orders.item(sel[0], "text")
        order = self.data_orders.get(oid)
        if not order:
            return

        status = order.get("Status", "activa")
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Detalle de Orden")
        win.configure(bg=BG_PANEL)
        win.resizable(True, True)
        ww = max(int(sw * 0.52), 540)
        wh = max(int(sh * 0.84), 600)
        win.minsize(500, 560)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        # Banner de estatus
        st_colors = {"activa": (SUCCESS, "✓ Activa"),
                     "cancelacion_pendiente": (WARNING, "⏳ Cancelación pendiente de aprobación"),
                     "cancelada": (DANGER,  "✗ Cancelada")}
        bar_col, bar_txt = st_colors.get(status, (PRIMARY, status))
        tk.Frame(win, bg=bar_col, height=4).pack(fill="x")
        tk.Label(win, text=f"Orden #{oid}", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(10, 2))
        tk.Label(win, text=bar_txt, bg=bar_col, fg="white",
                 font=("Arial", 10, "bold"), pady=3).pack(fill="x", padx=20)

        # Info labels
        dr = order.get("Descuento_razon", "Sin descuento") or "Sin descuento"
        info = [("Cliente",        order["Cliente"]),
                ("Vendedor",       order["Vendedor"]),
                ("Fecha",          order["Fecha"]),
                ("Hora",           order["Hora"]),
                ("Método de pago", order.get("Metodo_pago", "—")),
                ("Total",          f"$ {order['Importe_total']}"),
                ("Descuento",      dr)]
        for lbl, val in info:
            row = tk.Frame(win, bg=BG_PANEL)
            row.pack(fill="x", padx=20, pady=2)
            tk.Label(row, text=f"{lbl}:", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=16, anchor="w").pack(side="left")
            tk.Label(row, text=str(val), bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 11, "bold"), anchor="w").pack(side="left")

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        # Productos en la orden
        pcols = ("SKU", "Producto", "Cant", "Precio", "Descuento", "Importe")
        ptree = ttk.Treeview(win, columns=pcols, show="headings", height=7)
        for col, w in zip(pcols, [int(ww * f) for f in (0.12, 0.28, 0.10, 0.14, 0.14, 0.14)]):
            ptree.column(col, anchor="w" if col == "Producto" else "center", width=w)
            ptree.heading(col, text=col)
        ptree.pack(padx=20, fill="x")
        self._tag_rows(ptree)
        for i, (pid, pi) in enumerate(order["Productos"].items()):
            prod = self.data_products.get(pid, ["?"] * 11)
            sku    = str(prod[0]) if prod[0] else "—"
            nombre = f"{prod[2]} ({prod[5]})" if prod[5] else str(prod[2])
            precio_unit = (float(pi["Importe"]) + float(pi["Descuento"])) / max(int(pi["Cantidad"]), 1)
            desc_val    = float(pi["Descuento"])
            self._insert_row(ptree,
                (sku, nombre, pi["Cantidad"],
                 f"$ {precio_unit:,.2f}",
                 f"$ {desc_val:,.2f}" if desc_val else "—",
                 f"$ {pi['Importe']:,.2f}"),
                idx=i)

        # ── Botones según rol y estatus ───────────────────────────────────────
        def _do_eliminar():
            self.data_state["efectivo"] -= float(order["Importe_total"])
            for pid, pi in order["Productos"].items():
                if pid in self.data_products:
                    self.data_products[pid][8] += pi["Cantidad"]
                    self.db.update_stock(pid, pi["Cantidad"])
            self.data_orders.pop(oid)
            self.db.delete_order(oid)
            self.db.save_state(self.data_state["caja"], self.data_state["efectivo"])
            win.destroy()
            self.actualizar_ordenes()

        btn_row = tk.Frame(win, bg=BG_PANEL)
        btn_row.pack(pady=14)

        if self.prioridad_usuario <= 1:          # Gerente / CEO
            if status == "cancelacion_pendiente":
                self._btn(btn_row, "✓ Aprobar cancelación", _do_eliminar,
                          bg=DANGER, font_size=12
                          ).pack(side="left", padx=8, ipadx=12, ipady=6)

                def _rechazar():
                    order["Status"] = "activa"
                    self.db.update_order_status(oid, "activa")
                    win.destroy()
                    self.actualizar_ordenes()

                self._btn(btn_row, "✗ Rechazar", _rechazar,
                          bg=TXT_GRAY, font_size=12
                          ).pack(side="left", padx=8, ipadx=12, ipady=6)
            elif status == "activa":
                self._btn(btn_row, "✎ Editar Orden",
                          lambda: self._window_editar_orden(oid, order, win),
                          bg=PRIMARY, font_size=12
                          ).pack(side="left", padx=8, ipadx=16, ipady=6)
                self._btn(btn_row, "Eliminar Orden", _do_eliminar,
                          bg=DANGER, font_size=12
                          ).pack(side="left", padx=8, ipadx=16, ipady=6)

        else:                                    # Vendedor / Vendedor Jr.
            if status == "activa":
                def _solicitar():
                    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
                    order["Status"]   = "cancelacion_pendiente"
                    order["CancelAt"] = ts
                    order["CancelBy"] = self.usuario
                    self.db.update_order_status(oid, "cancelacion_pendiente",
                                                requested_by=self.usuario,
                                                requested_at=ts)
                    win.destroy()
                    self.actualizar_ordenes()

                self._btn(btn_row, "Solicitar cancelación", _solicitar,
                          bg=WARNING, font_size=12
                          ).pack(side="left", padx=8, ipadx=12, ipady=6)
            elif status == "cancelacion_pendiente":
                tk.Label(btn_row,
                         text="⏳ Cancelación enviada, pendiente de aprobación del gerente",
                         bg=BG_PANEL, fg=WARNING, font=("Arial", 10, "bold")).pack(pady=4)

    # ──────────────────────────────────────────────────────────────────────────
    def _window_editar_orden(self, oid, order, parent_win):
        """Ventana emergente para editar todos los campos de una orden."""
        sw, sh = self.screen_width, self.screen_height
        ewin = tk.Toplevel(self.root)
        ewin.title(f"Editar Orden #{oid}")
        ewin.configure(bg=BG_PANEL)
        ewin.resizable(True, True)
        ww = max(int(sw * 0.70), 700)
        wh = max(int(sh * 0.88), 620)
        ewin.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        ewin.grab_set()

        tk.Frame(ewin, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(ewin, text=f"Editar Orden #{oid}", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(10, 6))

        # ── Info general (Cliente, Método de pago) ────────────────────────────
        info_fr = tk.Frame(ewin, bg=BG_PANEL)
        info_fr.pack(fill="x", padx=24, pady=(0, 6))

        def _lf(parent, label, val, w=22):
            f = tk.Frame(parent, bg=BG_PANEL)
            f.pack(side="left", padx=10)
            tk.Label(f, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10)).pack(anchor="w")
            e = tk.Entry(f, font=("Arial", 11), width=w,
                         bg="white", fg=TXT_MAIN,
                         highlightbackground=BORDER, highlightthickness=1)
            e.insert(0, str(val))
            e.pack()
            return e

        ent_cliente = _lf(info_fr, "Cliente", order["Cliente"])
        ent_pago    = _lf(info_fr, "Método de pago", order.get("Metodo_pago", ""), w=16)
        ent_razon   = _lf(info_fr, "Motivo descuento", order.get("Descuento_razon", "Sin descuento"), w=26)

        tk.Frame(ewin, bg=BORDER, height=1).pack(fill="x", padx=20, pady=6)

        # ── Encabezado de columnas ────────────────────────────────────────────
        hdr = tk.Frame(ewin, bg=BG_SIDEBAR)
        hdr.pack(fill="x", padx=20)
        col_cfg = [("Producto",      36), ("SKU",   10), ("Cantidad", 8),
                   ("Costo unit. $", 12), ("Desc $", 10), ("Importe $", 12), ("", 3)]
        for ctxt, cw in col_cfg:
            tk.Label(hdr, text=ctxt, bg=BG_SIDEBAR, fg="white",
                     font=("Arial", 10, "bold"), width=cw, anchor="center"
                     ).pack(side="left", padx=2, pady=4)

        # ── Área scrollable de filas ──────────────────────────────────────────
        canvas = tk.Canvas(ewin, bg=BG_PANEL, highlightthickness=0)
        vsb = tk.Scrollbar(ewin, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 4))
        canvas.pack(fill="both", expand=True, padx=(20, 0), pady=4)

        rows_fr = tk.Frame(canvas, bg=BG_PANEL)
        canvas_win_id = canvas.create_window((0, 0), window=rows_fr, anchor="nw")

        def _on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_win_id, width=canvas.winfo_width())

        rows_fr.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win_id, width=e.width))

        # Mapa de productos para el combobox: "Nombre (Talla)" -> pid
        prod_display = {}
        for pid_, p_ in self.data_products.items():
            nombre_ = str(p_[2]) if len(p_) > 2 else "?"
            talla_  = str(p_[5]) if len(p_) > 5 and p_[5] else ""
            lbl_    = f"{nombre_} ({talla_})" if talla_ else nombre_
            prod_display[lbl_] = pid_
        prod_names = sorted(prod_display.keys())

        # Lista de filas editables: cada entrada es un dict con vars
        edit_rows = []

        def _recalc_importe(row_dict):
            try:
                qty  = float(row_dict["var_qty"].get() or 0)
                cost = float(row_dict["var_cost"].get() or 0)
                disc = float(row_dict["var_disc"].get() or 0)
                total = max(qty * cost - disc, 0)
                row_dict["lbl_importe"].config(text=f"${total:,.2f}")
                row_dict["_importe"] = total
            except Exception:
                log_exc("_recalc_importe")

        def _on_prod_select(row_dict, event=None):
            sel = row_dict["cmb_prod"].get()
            pid_ = prod_display.get(sel)
            if pid_ and pid_ in self.data_products:
                p_ = self.data_products[pid_]
                row_dict["var_sku"].set(str(p_[0]) if p_[0] else "")
                # Precio = precio de venta (índice 3)
                try:
                    row_dict["var_cost"].set(str(float(p_[3])))
                except Exception:
                    log_exc("_on_prod_select")
                row_dict["_pid"] = pid_
                _recalc_importe(row_dict)

        def _add_row(pid="", pi=None, producto_lbl=""):
            fr = tk.Frame(rows_fr, bg=BG_PANEL,
                          highlightbackground=BORDER, highlightthickness=1)
            fr.pack(fill="x", pady=2)

            if pi:
                qty_val  = int(pi.get("Cantidad", 1))
                disc_val = float(pi.get("Descuento", 0))
                cost_val = (float(pi["Importe"]) + disc_val) / max(qty_val, 1)
                imp_val  = float(pi.get("Importe", 0))
            else:
                qty_val, disc_val, cost_val, imp_val = 1, 0.0, 0.0, 0.0

            var_sku  = tk.StringVar()
            var_qty  = tk.StringVar(value=str(qty_val))
            var_cost = tk.StringVar(value=f"{cost_val:.2f}")
            var_disc = tk.StringVar(value=f"{disc_val:.2f}")

            if pid and pid in self.data_products:
                p_ = self.data_products[pid]
                nombre_ = str(p_[2]) if len(p_) > 2 else "?"
                talla_  = str(p_[5]) if len(p_) > 5 and p_[5] else ""
                producto_lbl = f"{nombre_} ({talla_})" if talla_ else nombre_
                var_sku.set(str(p_[0]) if p_[0] else "")

            row_dict = {
                "_pid": pid, "_importe": imp_val,
                "var_sku": var_sku, "var_qty": var_qty,
                "var_cost": var_cost, "var_disc": var_disc,
            }

            # Combobox producto
            cmb = ttk.Combobox(fr, values=prod_names, font=("Arial", 10), width=34)
            cmb.set(producto_lbl)
            cmb.pack(side="left", padx=3, pady=4)
            row_dict["cmb_prod"] = cmb
            cmb.bind("<<ComboboxSelected>>", lambda e, rd=row_dict: _on_prod_select(rd, e))

            def _make_entry(var, w=9):
                e = tk.Entry(fr, textvariable=var, font=("Arial", 10), width=w,
                             justify="center", bg="white", fg=TXT_MAIN,
                             highlightbackground=BORDER, highlightthickness=1)
                e.pack(side="left", padx=3, pady=4)
                e.bind("<KeyRelease>", lambda ev, rd=row_dict: _recalc_importe(rd))
                return e

            _make_entry(var_sku, w=10)
            _make_entry(var_qty, w=8)
            _make_entry(var_cost, w=12)
            _make_entry(var_disc, w=10)

            lbl_imp = tk.Label(fr, text=f"${imp_val:,.2f}", bg=BG_PANEL, fg=TXT_MAIN,
                               font=("Arial", 10, "bold"), width=12, anchor="center")
            lbl_imp.pack(side="left", padx=3)
            row_dict["lbl_importe"] = lbl_imp

            def _remove(rd=row_dict, f=fr):
                edit_rows.remove(rd)
                f.destroy()

            tk.Button(fr, text="×", bg=DANGER, fg="white", font=("Arial", 11, "bold"),
                      width=2, bd=0, cursor="hand2", command=_remove
                      ).pack(side="left", padx=4)

            edit_rows.append(row_dict)

        # Cargar filas actuales
        for pid, pi in order["Productos"].items():
            _add_row(pid=pid, pi=pi)

        # ── Botones inferiores ────────────────────────────────────────────────
        bot_fr = tk.Frame(ewin, bg=BG_PANEL)
        bot_fr.pack(fill="x", padx=20, pady=10)

        self._btn(bot_fr, "+ Agregar producto", lambda: _add_row(),
                  bg=BG_SIDEBAR, font_size=10
                  ).pack(side="left", ipadx=8, ipady=4)

        def _guardar():
            nuevos_productos = {}
            for rd in edit_rows:
                # Resolver pid: si cambió el combobox, buscar pid nuevo
                sel_lbl = rd["cmb_prod"].get().strip()
                pid_nuevo = prod_display.get(sel_lbl, rd["_pid"])
                if not pid_nuevo:
                    continue
                try:
                    qty  = int(float(rd["var_qty"].get() or 0))
                    cost = float(rd["var_cost"].get() or 0)
                    disc = float(rd["var_disc"].get() or 0)
                except ValueError:
                    continue
                if qty <= 0:
                    continue
                importe = max(qty * cost - disc, 0)
                pct = (disc / (qty * cost) * 100) if cost > 0 and qty > 0 else 0
                nuevos_productos[pid_nuevo] = {
                    "Cantidad": qty,
                    "Importe":  round(importe, 2),
                    "Descuento": round(disc, 2),
                    "Porcentaje_Descuento": round(pct, 2),
                }

            if not nuevos_productos:
                tk.messagebox.showwarning("Sin productos",
                    "La orden debe tener al menos un producto.", parent=ewin)
                return

            total_nuevo = sum(p["Importe"] for p in nuevos_productos.values())

            order["Cliente"]        = ent_cliente.get().strip() or order["Cliente"]
            order["Metodo_pago"]    = ent_pago.get().strip() or order["Metodo_pago"]
            order["Descuento_razon"]= ent_razon.get().strip() or "Sin descuento"
            order["Productos"]      = nuevos_productos
            order["Importe_total"]  = round(total_nuevo, 2)

            self.db.delete_order(oid)
            self.db.save_order(oid, order)
            self.data_orders[oid] = order

            ewin.destroy()
            parent_win.destroy()
            self.actualizar_ordenes()

        self._btn(bot_fr, "✓ Guardar cambios", _guardar,
                  bg=SUCCESS, font_size=12
                  ).pack(side="right", ipadx=16, ipady=6)
        self._btn(bot_fr, "Cancelar", ewin.destroy,
                  bg=TXT_GRAY, font_size=12
                  ).pack(side="right", padx=8, ipadx=12, ipady=6)

    # ══════════════════════════════════════════════════════════════════════════
    # PUNTO DE VENTA — Caja
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_punto_venta(self):
        self._current_screen = self.opcion_punto_venta
        sw, sh = self.screen_width, self.screen_height
        self.data_products     = self.db.get_products()
        self.productos_filtrados = dict(self.data_products)

        self.frame_POS = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_POS.place(x=int(sw * 0.1), y=0,
                             width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        caja_abierta = self.data_state["caja"] == "Abierta"
        self._header(self.frame_POS, "Punto de Venta")

        # Botón Cerrar/Abrir Caja — esquina derecha del header
        badge_h = int(hh * 0.55)
        badge_y = int(hh * 0.22)
        if caja_abierta:
            cc_w  = int(pw * 0.13)
            btn_x = pw - cc_w - int(pw * 0.015)
            self._btn(self.frame_POS, "Cerrar Caja", self.accion_caja,
                      bg=DANGER, font_size=10
                      ).place(x=btn_x, y=badge_y, width=cc_w, height=badge_h)
        else:
            bw = int(pw * 0.14)
            tk.Label(self.frame_POS, text="● Caja Cerrada",
                     bg=DANGER, fg="white", font=("Arial", 10, "bold")
                     ).place(x=pw - bw - int(pw * 0.015), y=badge_y,
                             width=bw, height=badge_h)

        # ── Sección de asistencia de usuarios ─────────────────────────────────
        # Mínimo 120px para que las tarjetas quepan con fuentes de Linux
        emp_bar_h = max(int(sh * 0.16), 120)
        emp_bar_y = hh
        emp_bar = tk.Frame(self.frame_POS, bg=BG_PANEL,
                           highlightbackground=BORDER, highlightthickness=1)
        emp_bar.place(x=0, y=emp_bar_y, width=pw, height=emp_bar_h)

        today_dt = datetime.now().strftime("%d/%m/%Y")

        # Sub-encabezado
        ep_hdr = tk.Frame(emp_bar, bg=BG_PANEL)
        ep_hdr.pack(fill="x", padx=12, pady=(4, 0))
        tk.Label(ep_hdr, text="ASISTENCIA", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(ep_hdr, text="Doble clic para registrar entrada / salida",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 8)).pack(side="left", padx=10)
        tk.Frame(emp_bar, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(3, 0))

        # Área scrollable horizontal de tarjetas (sin altura fija — se adapta)
        cards_canvas = tk.Canvas(emp_bar, bg=BG_PANEL, highlightthickness=0)
        cards_hsb    = ttk.Scrollbar(emp_bar, orient="horizontal",
                                     command=cards_canvas.xview)
        cards_canvas.configure(xscrollcommand=cards_hsb.set)
        cards_hsb.pack(side="bottom", fill="x", padx=8)
        cards_canvas.pack(fill="both", expand=True, padx=6)

        cards_frame = tk.Frame(cards_canvas, bg=BG_PANEL)
        _cf_id = cards_canvas.create_window((0, 0), window=cards_frame, anchor="nw")
        cards_frame.bind("<Configure>",
                         lambda e: cards_canvas.configure(
                             scrollregion=cards_canvas.bbox("all")))

        # Lista de empleados (sin gerente/CEO y sin "prueba")
        emp_list_caja = [
            (r["username"], r["id"], r["pin"])
            for r in self.db.get_users_full()
            if int(r["access_level"]) > 1
            and int(r["activo"] if r["activo"] is not None else 1) == 1
            and r["username"].strip().lower() != "prueba"
        ]

        def _is_active_caja(uid):
            row = self.db.conn.execute(
                "SELECT tipo FROM checadas WHERE user_id=? AND date=? ORDER BY id DESC LIMIT 1",
                (uid, today_dt)).fetchone()
            return row is not None and row["tipo"] == "entrada"

        def _render_cards_caja():
            for w in cards_frame.winfo_children():
                w.destroy()
            card_w = int(pw * 0.095)
            # header(~28px) + separador(~8px) + scrollbar(~20px) + paddings(~10px) ≈ 66px
            card_h = max(emp_bar_h - 66, 65)
            for idx, (name, uid, pin) in enumerate(emp_list_caja):
                active = _is_active_caja(uid)
                if active:
                    card_bg = "#DCFCE7"; brd_col = "#86EFAC"
                    dot_col = "#16A34A"; status  = "● En turno"; st_col = "#15803D"
                else:
                    card_bg = "#F8FAFC"; brd_col = "#CBD5E1"
                    dot_col = "#94A3B8"; status  = "○ Fuera";    st_col = TXT_GRAY

                cell = tk.Frame(cards_frame, bg=card_bg,
                                highlightbackground=brd_col,
                                highlightthickness=2, cursor="hand2",
                                width=card_w, height=card_h)
                cell.pack(side="left", padx=6, pady=4)
                cell.pack_propagate(False)

                tk.Label(cell, text="⬤", bg=card_bg, fg=dot_col,
                         font=("Arial", 11)).pack(pady=(8, 1))
                tk.Label(cell, text=name, bg=card_bg, fg=TXT_MAIN,
                         font=("Arial", 10, "bold"), wraplength=card_w - 10).pack(pady=1)
                tk.Label(cell, text=status, bg=card_bg, fg=st_col,
                         font=("Arial", 8)).pack(pady=(1, 8))

                def _dbl_caja(event, _uid=uid, _name=name, _pin=pin):
                    _pin_dialog_caja(_uid, _name, _pin)
                for w in [cell] + list(cell.winfo_children()):
                    w.bind("<Double-Button-1>", _dbl_caja)

        def _pin_dialog_caja(uid, name, correct_pin):
            active  = _is_active_caja(uid)
            action  = "salida" if active else "entrada"
            act_lbl = "Registrar Salida" if active else "Registrar Entrada"
            act_col = DANGER if active else SUCCESS

            dw, dh = 330, 390
            sx = self.root.winfo_x() + (self.root.winfo_width()  - dw) // 2
            sy = self.root.winfo_y() + (self.root.winfo_height() - dh) // 2

            dlg = tk.Toplevel(self.root)
            dlg.title("Registro de asistencia")
            dlg.resizable(False, False)
            dlg.geometry(f"{dw}x{dh}+{sx}+{sy}")
            dlg.configure(bg=BG_PANEL)
            dlg.transient(self.root)
            # overrideredirect falla en Wayland/Linux — solo en macOS/Windows
            if platform.system() != "Linux":
                dlg.overrideredirect(True)
            dlg.grab_set()
            dlg.lift()
            dlg.focus_force()

            outer = tk.Frame(dlg, bg=BORDER, highlightbackground=BORDER,
                             highlightthickness=1)
            outer.place(x=0, y=0, width=dw, height=dh)
            inner = tk.Frame(outer, bg=BG_PANEL)
            inner.place(x=1, y=1, width=dw-2, height=dh-2)

            close_btn = tk.Label(inner, text="✕", bg=BG_PANEL, fg=TXT_GRAY,
                                 font=("Arial", 13), cursor="hand2")
            close_btn.place(relx=1.0, x=-28, y=8)
            close_btn.bind("<Button-1>", lambda _e: dlg.destroy())

            mini_clk = tk.Label(inner, text="", bg=BG_PANEL, fg=PRIMARY,
                                font=("Courier", 20, "bold"))
            mini_clk.place(x=0, y=8, width=dw-2)

            def _tick_dlg():
                try:
                    mini_clk.config(text=datetime.now().strftime("%H : %M : %S"))
                    dlg.after(1000, _tick_dlg)
                except tk.TclError:
                    pass
            _tick_dlg()

            dot_c = DANGER if active else SUCCESS
            tk.Label(inner, text="⬤", bg=BG_PANEL, fg=dot_c,
                     font=("Arial", 18)).place(x=0, y=62, width=dw-2)
            tk.Label(inner, text=name, bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 17, "bold")).place(x=0, y=90, width=dw-2)
            tk.Label(inner, text=act_lbl, bg=BG_PANEL, fg=act_col,
                     font=("Arial", 11, "bold")).place(x=0, y=120, width=dw-2)
            tk.Frame(inner, bg=BORDER, height=1).place(x=20, y=148, width=dw-42)
            tk.Label(inner, text="Ingresa tu PIN", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10)).place(x=0, y=158, width=dw-2)

            pin_var = tk.StringVar()
            pin_entry = tk.Entry(inner, textvariable=pin_var, show="●",
                                 font=("Arial", 22, "bold"), justify="center",
                                 relief="flat", bg=BG_MAIN, fg=TXT_MAIN,
                                 insertbackground=PRIMARY,
                                 highlightbackground=BORDER, highlightthickness=1)
            pin_entry.place(x=36, y=186, width=dw-74, height=52)
            pin_entry.focus_force()

            err_lbl = tk.Label(inner, text="", bg=BG_PANEL, fg=DANGER,
                               font=("Arial", 10))
            err_lbl.place(x=0, y=246, width=dw-2)

            def _validar(event=None):
                entered = pin_var.get().strip()
                if entered == correct_pin:
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.db.conn.execute(
                        "INSERT INTO checadas(user_id,username,tipo,timestamp,date)"
                        " VALUES(?,?,?,?,?)",
                        (uid, name, action, ts, today_dt))
                    self.db.conn.commit()
                    dlg.destroy()
                    _render_cards_caja()
                else:
                    err_lbl.config(text="PIN incorrecto")
                    pin_var.set("")
                    pin_entry.focus_force()

            pin_entry.bind("<Return>", _validar)
            btn_frame = tk.Frame(inner, bg=BG_PANEL)
            btn_frame.place(x=24, y=290, width=dw-50)
            self._btn(btn_frame, act_lbl, _validar,
                      bg=act_col, font_size=12).pack(fill="x", ipady=8)
            self._btn(btn_frame, "Cancelar", dlg.destroy,
                      bg=TXT_GRAY, font_size=11).pack(fill="x", ipady=5, pady=(8, 0))

        _render_cards_caja()

        if not caja_abierta:
            tk.Label(self.frame_POS,
                     text="Necesitas abrir la caja para realizar ventas.",
                     bg=BG_MAIN, fg=TXT_GRAY, font=("Arial", 14)
                     ).place(x=int(pw * 0.15), y=int(sh * 0.35),
                             width=int(pw * 0.50), height=int(sh * 0.08))
            self._btn(self.frame_POS, "Abrir Caja", self.accion_caja,
                      bg=SUCCESS, font_size=14
                      ).place(x=int(pw * 0.30), y=int(sh * 0.47),
                              width=int(pw * 0.20), height=int(sh * 0.07))
            return

        # ── Columna izquierda: productos ─────────────────────────────────────
        lx = int(pw * 0.01)
        ly = emp_bar_y + emp_bar_h + int(sh * 0.01)
        lw = int(pw * 0.46)

        # Search
        sf = tk.Frame(self.frame_POS, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        sf.place(x=lx, y=ly, width=lw, height=int(sh * 0.045))
        tk.Label(sf, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left", padx=8)
        self.entrada_busqueda = tk.Entry(sf, font=("Arial", 12),
                                         relief="flat", bg=BG_PANEL, fg=TXT_MAIN)
        self.entrada_busqueda.pack(side="left", fill="x", expand=True, padx=4)
        self.entrada_busqueda.bind("<KeyRelease>", self.buscar_producto)

        # Product table
        cols = ("SKU", "Producto", "Marca", "Ext", "Precio")
        self.tree = ttk.Treeview(self.frame_POS,
                                 columns=cols, show="headings", height=22)
        col_w = [int(sw * w) for w in (0.03, 0.20, 0.05, 0.02, 0.05)]
        for col, w in zip(cols, col_w):
            self.tree.column(col, anchor="center" if col != "Producto" else "w", width=w)
            self.tree.heading(col, text=col)
        ty = ly + int(sh * 0.055)
        # Calcular altura desde espacio restante, no fracción fija (evita overflow en Linux)
        th = sh - ty - int(sh * 0.015)
        self.tree.place(x=lx, y=ty, width=lw, height=th)
        self._tag_rows(self.tree)
        self._add_scrollbar(self.frame_POS, self.tree, lx, ty, lw, th)
        self.tree.bind("<Double-Button-1>", self.agregar_al_carrito)

        # ── Columna derecha: carrito ─────────────────────────────────────────
        rx = int(pw * 0.49)
        ry = ly          # misma altura que columna izquierda
        rw = int(pw * 0.49)

        # Info usuario / cliente
        info_row = tk.Frame(self.frame_POS, bg=BG_PANEL,
                            highlightbackground=BORDER, highlightthickness=1)
        info_row.place(x=rx, y=ry, width=rw, height=int(sh * 0.06))
        tk.Label(info_row, text=f"Vendedor: {self.usuario}", bg=BG_PANEL,
                 fg=TXT_MAIN, font=("Arial", 11)
                 ).place(x=8, y=0, width=int(rw * 0.45), height=int(sh * 0.06))

        tk.Label(info_row, text="Cliente:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)
                 ).place(x=int(rw * 0.48), y=0,
                         width=int(rw * 0.18), height=int(sh * 0.06))
        self.boton_cliente = tk.Label(info_row, text=self.cliente,
                                      bg=PRIMARY, fg="white",
                                      font=("Arial", 10, "bold"),
                                      cursor="hand2")
        self.boton_cliente.bind("<Button-1>", lambda _e: self.client_Window())
        self.boton_cliente.bind("<Enter>",    lambda _e: self.boton_cliente.config(bg=PRIMARY_DK))
        self.boton_cliente.bind("<Leave>",    lambda _e: self.boton_cliente.config(bg=PRIMARY))
        self.boton_cliente.place(x=int(rw * 0.65), y=int(sh * 0.01),
                                 width=int(rw * 0.32), height=int(sh * 0.04))

        # ── Bottom-up layout: fix pay buttons first, build upward ──────────
        gap          = int(sh * 0.01)
        pay_h        = int(sh * 0.07)
        pay_y        = sh - int(sh * 0.02) - pay_h

        tot_h        = int(sh * 0.21)
        tot_y        = pay_y - gap - tot_h

        btn_h        = int(sh * 0.05)
        bty          = tot_y - gap - btn_h

        cty          = ry + int(sh * 0.07)
        cth          = max(bty - gap - cty, int(sh * 0.15))

        # Cart table
        ccols = ("Producto", "Cant", "Precio", "Desc", "Importe")
        self.tree_carrito = ttk.Treeview(self.frame_POS,
                                         columns=ccols, show="headings", height=12)
        cw_cols = [int(sw * w) for w in (0.15, 0.03, 0.05, 0.04, 0.05)]
        for col, w in zip(ccols, cw_cols):
            self.tree_carrito.column(col, anchor="center" if col != "Producto" else "w", width=w)
            self.tree_carrito.heading(col, text=col)
        self.tree_carrito.place(x=rx, y=cty, width=rw, height=cth)
        self._tag_rows(self.tree_carrito)

        # ── Botones de carrito ─────────────────────────────────────────────
        bw = int(rw * 0.19)
        self._btn(self.frame_POS, "  -  ", self.quitar_producto,
                  bg=DANGER, font_size=14, bold=True
                  ).place(x=rx, y=bty, width=bw, height=btn_h)
        self._btn(self.frame_POS, "  +  ", self.agregar_producto,
                  bg=SUCCESS, font_size=14, bold=True
                  ).place(x=rx + bw + 4, y=bty, width=bw, height=btn_h)
        self._btn(self.frame_POS, "Desc.", self.ventana_descuentos,
                  bg=WARNING, font_size=13, bold=True
                  ).place(x=rx + 2*(bw + 4), y=bty, width=bw, height=btn_h)

        # ── Totales ────────────────────────────────────────────────────────
        tot_card = self._card(self.frame_POS, x=rx, y=tot_y, w=rw, h=tot_h)
        rows_tot = [("Subtotal (sin IVA):", "etiqueta_subtotal"),
                    ("IVA (16%):",          "etiqueta_IVA"),
                    ("Descuento:",          "etiqueta_descuento"),
                    ("TOTAL:",              "etiqueta_total")]
        fonts = [("Arial", 11), ("Arial", 11), ("Arial", 11), ("Arial", 14, "bold")]
        row_h = int(tot_h * 0.23)
        for i, ((lbl, attr), fnt) in enumerate(zip(rows_tot, fonts)):
            yy = i * row_h + 8
            key_lbl = tk.Label(tot_card, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                               font=("Arial", 11), anchor="w")
            key_lbl.place(x=10, y=yy, width=int(rw * 0.55), height=row_h - 4)
            if attr == "etiqueta_descuento":
                self.lbl_key_descuento = key_lbl
            lbl_val = tk.Label(tot_card, text="$ 0.00", bg=BG_PANEL, fg=TXT_MAIN,
                               font=fnt, anchor="e")
            lbl_val.place(x=int(rw * 0.55), y=yy,
                          width=int(rw * 0.42), height=row_h - 4)
            setattr(self, attr, lbl_val)
        self.etiqueta_descuento.config(text="—", fg=SUCCESS)
        self.etiqueta_total.config(fg=PRIMARY)

        # ── Botones de accion ──────────────────────────────────────────────
        self._btn(self.frame_POS, "PAGAR", self.pagar,
                  bg=SUCCESS, font_size=15
                  ).place(x=rx, y=pay_y, width=int(rw * 0.74), height=pay_h)
        self._btn(self.frame_POS, "Borrar", self.reiniciar_caja,
                  bg=TXT_GRAY, font_size=12
                  ).place(x=rx + int(rw * 0.76), y=pay_y,
                           width=int(rw * 0.24), height=pay_h)

        self.actualizar_tree_productos()
        self.actualizar_tree_carrito()

    # ── Caja open/close ───────────────────────────────────────────────────────
    def accion_caja(self):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Caja")
        win.configure(bg=BG_PANEL)
        ww, wh = max(int(sw * 0.26), 340), max(int(sh * 0.42), 360)
        win.minsize(320, 340)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        color = DANGER if self.data_state["caja"] == "Abierta" else SUCCESS
        tk.Frame(win, bg=color, height=4).pack(fill="x")
        accion = "Cerrar" if self.data_state["caja"] == "Abierta" else "Abrir"
        tk.Label(win, text=f"{accion} Caja", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(12, 8))

        def _entry_row(lbl_text, default="0"):
            row = tk.Frame(win, bg=BG_PANEL)
            row.pack(fill="x", padx=24, pady=5)
            tk.Label(row, text=lbl_text, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=10, anchor="w").pack(side="left")
            e = tk.Entry(row, font=("Arial", 13), justify="right",
                         relief="flat", bg=BG_MAIN)
            e.insert(0, default)
            e.pack(side="left", fill="x", expand=True, ipady=5)
            return e

        if self.data_state["caja"] == "Cerrada":
            e_bil = _entry_row("Billetes $:")
            e_mon = _entry_row("Monedas $:")

            lbl_total = tk.Label(win, text="Total: $ 0.00", bg=BG_PANEL,
                                 fg=PRIMARY, font=("Arial", 13, "bold"))
            lbl_total.pack(pady=(6, 2))

            def _upd(ev=None):
                try:
                    t = float(e_bil.get()) + float(e_mon.get())
                    lbl_total.config(text=f"Total: $ {t:,.2f}")
                except Exception:
                    lbl_total.config(text="Total: $ --")

            e_bil.bind("<KeyRelease>", _upd)
            e_mon.bind("<KeyRelease>", _upd)

            def _abrir():
                try:
                    self.data_state["caja"]     = "Abierta"
                    self.data_state["efectivo"] = float(e_bil.get()) + float(e_mon.get())
                    self.db.save_state("Abierta", self.data_state["efectivo"])
                    win.destroy()
                    self.opcion_punto_venta()
                except Exception:
                    log_exc("_abrir")

            self._btn(win, "Abrir Caja", _abrir, bg=SUCCESS, font_size=13
                      ).pack(pady=12, ipadx=20, ipady=10)
        else:
            # ── Corte de caja (adaptado del HTML showCorteCaja) ───────────────
            win.geometry(f"{int(sw*0.44)}x{int(sh*0.72)}+{(sw-int(sw*0.44))//2}+{(sh-int(sh*0.72))//2}")

            now_c   = datetime.now()
            today_c = f"{now_c.day}/{now_c.month}/{now_c.year}"
            ventas_hoy = self.FiltrarData(fecha_inicial=today_c)

            # Totales del día
            total_dia = sum(float(i["Importe_total"]) for i in ventas_hoy.values())
            ef_dia    = sum(float(i["Importe_total"]) for i in ventas_hoy.values()
                           if i.get("Metodo_pago", "") == "Efectivo")
            tk_dia    = total_dia - ef_dia
            iva_dia   = total_dia / 1.16 * 0.16
            n_ventas  = len(ventas_hoy)

            # Resumen numérico
            rf = tk.Frame(win, bg=BG_MAIN, padx=10, pady=8)
            rf.pack(fill="x", padx=14, pady=(4, 0))
            stats = [
                ("Ventas del día",    str(n_ventas),           TXT_MAIN),
                ("Efectivo",          f"$ {ef_dia:,.2f}",      SUCCESS),
                ("Tarjeta / Transf.", f"$ {tk_dia:,.2f}",      PRIMARY),
                ("IVA estimado",      f"$ {iva_dia:,.2f}",     TXT_GRAY),
                ("TOTAL DÍA",         f"$ {total_dia:,.2f}",   SUCCESS),
            ]
            for lbl_t, val_t, col in stats:
                row_s = tk.Frame(rf, bg=BG_MAIN)
                row_s.pack(fill="x", pady=2)
                tk.Label(row_s, text=lbl_t, bg=BG_MAIN, fg=TXT_GRAY,
                         font=("Arial", 10), anchor="w").pack(side="left")
                bold = "bold" if lbl_t == "TOTAL DÍA" else "normal"
                tk.Label(row_s, text=val_t, bg=BG_MAIN, fg=col,
                         font=("Arial", 11, bold), anchor="e").pack(side="right")
            tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=14, pady=6)

            # Desglose por producto (del HTML)
            tk.Label(win, text="Productos vendidos hoy",
                     bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 11, "bold"),
                     anchor="w").pack(fill="x", padx=14, pady=(0, 4))

            prod_sales = {}
            for item in ventas_hoy.values():
                for pid, pi in item["Productos"].items():
                    info = self.data_products.get(pid, ["", "", "—"])
                    name = info[2]
                    if name not in prod_sales:
                        prod_sales[name] = {"qty": 0, "amount": 0.0}
                    prod_sales[name]["qty"]    += int(pi["Cantidad"])
                    prod_sales[name]["amount"] += float(pi["Importe"])

            prod_sorted = sorted(prod_sales.items(),
                                 key=lambda x: x[1]["amount"], reverse=True)

            pt_frame = tk.Frame(win, bg=BG_PANEL,
                                highlightbackground=BORDER, highlightthickness=1)
            pt_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))

            pcols = ("Producto", "Cant.", "Importe")
            tree_c = ttk.Treeview(pt_frame, columns=pcols, show="headings", height=8)
            cw_map = [int(sw * w) for w in (0.22, 0.04, 0.07)]
            for col, cw in zip(pcols, cw_map):
                tree_c.column(col, anchor="w" if col == "Producto" else "center", width=cw)
                tree_c.heading(col, text=col)
            tree_c.pack(side="left", fill="both", expand=True)
            sb_c = ttk.Scrollbar(pt_frame, orient="vertical", command=tree_c.yview)
            sb_c.pack(side="right", fill="y")
            tree_c.configure(yscrollcommand=sb_c.set)
            self._tag_rows(tree_c)

            if prod_sorted:
                for i, (name, d) in enumerate(prod_sorted):
                    self._insert_row(tree_c,
                        (name, d["qty"], f"$ {d['amount']:,.2f}"), idx=i)
            else:
                tree_c.insert("", "end", values=("Sin ventas hoy", "—", "—"))

            # Botones
            btn_row = tk.Frame(win, bg=BG_PANEL)
            btn_row.pack(pady=8)

            def _cerrar():
                self.data_state["caja"]     = "Cerrada"
                self.data_state["efectivo"] = 0
                self.db.save_state("Cerrada", 0)
                win.destroy()
                self.opcion_punto_venta()

            self._btn(btn_row, "Cancelar", win.destroy,
                      bg=TXT_GRAY, font_size=11
                      ).pack(side="left", padx=8, ipadx=14, ipady=6)
            self._btn(btn_row, "Cerrar Caja", _cerrar,
                      bg=DANGER, font_size=12
                      ).pack(side="left", padx=8, ipadx=14, ipady=6)

    def reiniciar_caja(self):
        self.carrito = {}
        self._cliente_descuento     = 0
        self._discount_reason       = "Sin descuento"
        self._discount_restrictions = 0
        self.cliente = "Publico General"
        self.boton_cliente.config(text="Publico General")
        self.actualizar_tree_carrito()

    # ── Tabla productos ───────────────────────────────────────────────────────
    def actualizar_tree_productos(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, (idx, item) in enumerate(self.productos_filtrados.items()):
            self._insert_row(self.tree,
                (item[0], f"{item[2]}  ({item[5]})", item[6],
                 item[8], f"$ {float(item[self.index_precio]):,.2f}"),
                text=idx, idx=i)

    def buscar_producto(self, event=None):
        term = self.entrada_busqueda.get().lower()
        self.data_products = self.db.get_products()
        self.productos_filtrados = {
            idx: item for idx, item in self.data_products.items()
            if self.find(item[:5], term)
        }
        self.actualizar_tree_productos()

    # ── Carrito ───────────────────────────────────────────────────────────────
    def agregar_al_carrito(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        pos = self.tree.index(sel[0])
        idx = list(self.productos_filtrados.keys())[pos]
        if idx in self.carrito:
            self.carrito[idx]["Cantidad"] += 1
        else:
            self.carrito[idx] = {"Cantidad": 1, "Porcentaje_Descuento": 0.0}
        self.actualizar_importe(idx)
        self.actualizar_tree_carrito()

    def actualizar_importe(self, index, item=""):
        precio   = float(self.data_products[index][self.index_precio])
        p_desc   = self.carrito[index]["Porcentaje_Descuento"]
        cantidad = self.carrito[index]["Cantidad"]
        descuento = round(precio * p_desc * cantidad, 2)
        self.carrito[index]["Descuento"] = descuento
        self.carrito[index]["Importe"]   = round(precio * cantidad - descuento, 2)
        if item:
            self.tree_carrito.set(item, "Cant",   self.carrito[index]["Cantidad"])
            self.tree_carrito.set(item, "Precio", f"$ {precio:,.2f}")
            self.tree_carrito.set(item, "Desc",   f"$ {descuento:,.2f}" if descuento else "—")
            self.tree_carrito.set(item, "Importe", f"$ {self.carrito[index]['Importe']:,.2f}")
            self.actualizar_totales()

    def actualizar_tree_carrito(self):
        for row in self.tree_carrito.get_children():
            self.tree_carrito.delete(row)
        for i, (idx, item) in enumerate(self.carrito.items()):
            prod  = self.data_products[idx]
            precio = float(prod[self.index_precio])
            desc   = item.get("Descuento", 0)
            self._insert_row(self.tree_carrito,
                (f"{prod[2]} ({prod[5]})", item["Cantidad"],
                 f"$ {precio:,.2f}",
                 f"$ {desc:,.2f}" if desc else "—",
                 f"$ {item['Importe']:,.2f}"),
                text=idx, idx=i)
        self.actualizar_totales()

    def actualizar_totales(self):
        subtotal_bruto  = sum(item["Importe"] for item in self.carrito.values())
        total_item_disc = sum(item.get("Descuento", 0) for item in self.carrito.values())
        cli_disc = getattr(self, "_cliente_descuento", 0)
        if cli_disc > 0:
            disc_amount = subtotal_bruto * cli_disc / 100
            self.Total = subtotal_bruto - disc_amount
            self.etiqueta_descuento.config(text=f"-$ {disc_amount:,.2f}", fg=SUCCESS)
            self.lbl_key_descuento.config(text=f"Descuento {cli_disc}%:")
        elif total_item_disc > 0.005:
            self.Total = subtotal_bruto
            reason = getattr(self, "_discount_reason", "Descuento")
            short  = reason if len(reason) <= 20 else reason[:18] + "…"
            self.etiqueta_descuento.config(text=f"-$ {total_item_disc:,.2f}", fg=SUCCESS)
            self.lbl_key_descuento.config(text=f"{short}:")
        else:
            self.Total = subtotal_bruto
            self.etiqueta_descuento.config(text="—", fg=TXT_GRAY)
            self.lbl_key_descuento.config(text="Descuento:")
        self.etiqueta_total.config(text=f"$ {self.Total:,.2f}")
        self.etiqueta_subtotal.config(text=f"$ {self.Total / 1.16:,.2f}")
        self.etiqueta_IVA.config(text=f"$ {(self.Total / 1.16) * 0.16:,.2f}")

    def agregar_producto(self):
        sel = self.tree_carrito.selection()
        if not sel or not self.carrito:
            return
        pos = self.tree_carrito.index(sel[0])
        idx = list(self.carrito.keys())[pos]
        self.carrito[idx]["Cantidad"] += 1
        self.actualizar_importe(idx, item=sel[0])

    def quitar_producto(self):
        sel = self.tree_carrito.selection()
        if not sel or not self.carrito:
            return
        pos = self.tree_carrito.index(sel[0])
        idx = list(self.carrito.keys())[pos]
        if self.carrito[idx]["Cantidad"] > 1:
            self.carrito[idx]["Cantidad"] -= 1
            self.actualizar_importe(idx, item=sel[0])
        else:
            self.tree_carrito.delete(sel[0])
            self.carrito.pop(idx)
            self.actualizar_totales()

    def descuento_producto(self):
        sel = self.tree_carrito.selection()
        if not sel or not self.carrito:
            return
        pos = self.tree_carrito.index(sel[0])
        idx = list(self.carrito.keys())[pos]
        prod  = self.data_products[idx]
        precio = float(prod[self.index_precio])
        nombre = f"{prod[2]} ({prod[5]})"

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Descuento")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.28), int(sh * 0.28)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        tk.Frame(win, bg=WARNING, height=4).pack(fill="x")
        tk.Label(win, text=nombre, bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 12, "bold"), wraplength=ww - 20
                 ).pack(pady=(10, 4), padx=10)

        lbl_desc_val = tk.Label(win, text=f"$ 0.00", bg=BG_PANEL, fg=WARNING,
                                font=("Arial", 13, "bold"))
        lbl_desc_val.pack()
        lbl_imp_val = tk.Label(win, text=f"Importe: $ {precio:.2f}", bg=BG_PANEL,
                               fg=TXT_GRAY, font=("Arial", 12))
        lbl_imp_val.pack(pady=2)

        row = tk.Frame(win, bg=BG_PANEL)
        row.pack(fill="x", padx=20, pady=6)
        tk.Label(row, text="Descuento %:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")
        e_desc = tk.Entry(row, font=("Arial", 13), justify="right",
                          relief="flat", bg=BG_MAIN, width=8)
        e_desc.pack(side="left", padx=8, ipady=4)

        def _calc(ev=None):
            try:
                d = float(e_desc.get()) / 100
                lbl_desc_val.config(text=f"Descuento: $ {precio * d:.2f}")
                lbl_imp_val.config(text=f"Importe: $ {precio * (1 - d):.2f}")
            except Exception:
                log_exc("_calc")

        def _aplicar():
            try:
                d = float(e_desc.get()) / 100
                self.carrito[idx]["Porcentaje_Descuento"] = d
                self.actualizar_importe(idx)
                self.actualizar_tree_carrito()
                win.destroy()
            except Exception:
                log_exc("_aplicar")

        e_desc.bind("<KeyRelease>", _calc)
        self._btn(win, "Aplicar", _aplicar, bg=WARNING, font_size=12
                  ).pack(pady=10, ipadx=16, ipady=6)

    # ── Descuentos globales al carrito ────────────────────────────────────────
    def _aplicar_descuento_global(self, pct, reason, restrictions=0):
        """Aplica un descuento porcentual a todos los productos del carrito.
        restrictions: 0=ambos, 1=solo tarjeta, 2=solo efectivo."""
        if not self.carrito:
            return
        for idx in list(self.carrito.keys()):
            self.carrito[idx]["Porcentaje_Descuento"] = pct / 100.0
            self.actualizar_importe(idx)
        self._discount_reason       = reason
        self._discount_restrictions = int(restrictions)
        self._cliente_descuento     = 0   # limpiar descuento de cliente si había
        self.actualizar_tree_carrito()

    def ventana_descuentos(self):
        """Ventana de selección de descuento para el carrito actual."""
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Descuentos")
        win.configure(bg=BG_PANEL)
        ww = int(sw * 0.50)
        # Use a generous height so buttons are not clipped on Linux (larger fonts)
        wh = min(int(sh * 0.86), sh - 80)
        cx = (sw - ww) // 2
        cy = max((sh - wh) // 2, 30)
        win.geometry(f"{ww}x{wh}+{cx}+{cy}")
        win.transient(self.root)
        win.lift()
        win.grab_set()
        win.focus_force()

        tk.Frame(win, bg=WARNING, height=4).pack(fill="x")
        tk.Label(win, text="Aplicar Descuento", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(10, 4))

        # ── Lista de descuentos vigentes ──────────────────────────────────────
        tk.Label(win, text="Descuentos vigentes", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=16, pady=(4, 2))

        RESTRICT_LBL = {0: "Efectivo y Tarjeta", 1: "Solo Tarjeta", 2: "Solo Efectivo"}
        disc_cols = ("Nombre", "%", "Categorías", "Marcas", "Vigencia", "Restricción")
        disc_tree = ttk.Treeview(win, columns=disc_cols, show="headings", height=4)
        cw_d = [int(ww * f) for f in (0.22, 0.07, 0.16, 0.16, 0.22, 0.15)]
        for col, w in zip(disc_cols, cw_d):
            disc_tree.column(col,
                anchor="center" if col not in ("Nombre", "Categorías", "Marcas") else "w",
                width=w)
            disc_tree.heading(col, text=col)
        self._tag_rows(disc_tree)
        disc_tree.pack(padx=16, fill="x")

        active_discs = self.db.get_active_discounts()
        _disc_data = {}   # row_iid -> dict
        for i, r in enumerate(active_discs):
            rl = RESTRICT_LBL.get(int(r["restrictions"]), "—")
            vigencia = f"{r['date_start']} – {r['date_end']}"
            iid = disc_tree.insert("", "end",
                values=(r["name"], f"{r['percentage']:.1f}%",
                        r["categories"], r["brands"], vigencia, rl),
                tags=("even" if i % 2 == 0 else "odd",))
            _disc_data[iid] = r

        if not active_discs:
            disc_tree.insert("", "end",
                values=("Sin descuentos vigentes", "—", "—", "—", "—", "—"))

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)
        tk.Label(win, text="Descuento manual", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=16, pady=(0, 4))

        manual_row = tk.Frame(win, bg=BG_PANEL)
        manual_row.pack(fill="x", padx=16, pady=2)
        tk.Label(manual_row, text="Porcentaje:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")
        e_manual = tk.Entry(manual_row, font=("Arial", 13), justify="right",
                            relief="flat", bg=BG_MAIN, width=7)
        e_manual.pack(side="left", padx=8, ipady=4)
        tk.Label(manual_row, text="%", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")

        lbl_preview = tk.Label(win, text="", bg=BG_PANEL, fg=SUCCESS,
                               font=("Arial", 11, "bold"))
        lbl_preview.pack(pady=2)

        total_carrito = sum(it["Importe"] for it in self.carrito.values())

        def _calc_manual(ev=None):
            try:
                pct_v = float(e_manual.get())
                ahorro = round(total_carrito * pct_v / 100, 2)
                lbl_preview.config(text=f"Ahorro: $ {ahorro:,.2f}")
            except Exception:
                lbl_preview.config(text="")

        e_manual.bind("<KeyRelease>", _calc_manual)

        # ── Botones ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(win, bg=BG_PANEL)
        btn_row.pack(pady=12)

        def _apply_catalog():
            sel = disc_tree.selection()
            if not sel:
                messagebox.showwarning("Sin selección",
                    "Selecciona un descuento de la lista.", parent=win)
                return
            iid = sel[0]
            if iid not in _disc_data:
                return
            r = _disc_data[iid]
            self._aplicar_descuento_global(
                float(r["percentage"]), str(r["name"]), int(r["restrictions"]))
            win.destroy()

        def _apply_manual():
            try:
                pct_v = float(e_manual.get())
                if pct_v <= 0:
                    messagebox.showwarning("Valor inválido",
                        "Ingresa un porcentaje mayor a 0.", parent=win)
                    return
            except Exception:
                messagebox.showwarning("Valor inválido",
                    "Ingresa un número válido.", parent=win)
                return
            self._aplicar_descuento_global(pct_v, "Descuento manual")
            win.destroy()

        def _quitar():
            for idx in list(self.carrito.keys()):
                self.carrito[idx]["Porcentaje_Descuento"] = 0.0
                self.actualizar_importe(idx)
            self._discount_reason       = "Sin descuento"
            self._discount_restrictions = 0
            self._cliente_descuento     = 0
            self.actualizar_tree_carrito()
            win.destroy()

        self._btn(btn_row, "Aplicar del catálogo", _apply_catalog,
                  bg=WARNING, font_size=12
                  ).pack(side="left", padx=6, ipadx=10, ipady=6)
        self._btn(btn_row, "Aplicar manual", _apply_manual,
                  bg=PRIMARY, font_size=12
                  ).pack(side="left", padx=6, ipadx=10, ipady=6)
        self._btn(btn_row, "Quitar descuento", _quitar,
                  bg=TXT_GRAY, font_size=12
                  ).pack(side="left", padx=6, ipadx=10, ipady=6)

    # ── Calendario emergente (selector de fecha genérico) ─────────────────────
    def _show_calendar(self, entry_widget):
        """Abre un calendario Toplevel y escribe la fecha seleccionada en entry_widget."""
        import calendar as _cal
        from datetime import date as _date

        # Leer fecha actual del campo si es válida
        try:
            cur  = datetime.strptime(entry_widget.get().strip(), "%d/%m/%Y")
            sy, sm = cur.year, cur.month
        except Exception:
            n = datetime.now(); sy, sm = n.year, n.month

        state = {"year": sy, "month": sm}

        MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        DIAS_HDR = ["Lu","Ma","Mi","Ju","Vi","Sá","Do"]

        ww, wh = 296, 298
        win = tk.Toplevel(self.root)
        win.title("Fecha")
        win.configure(bg=BG_PANEL)
        win.resizable(False, False)
        win.grab_set()

        # Posicionar debajo del Entry
        entry_widget.update_idletasks()
        ex = entry_widget.winfo_rootx()
        ey = entry_widget.winfo_rooty() + entry_widget.winfo_height() + 3
        if ex + ww > self.screen_width:  ex = self.screen_width  - ww - 8
        if ey + wh > self.screen_height: ey = entry_widget.winfo_rooty() - wh - 3
        win.geometry(f"{ww}x{wh}+{ex}+{ey}")

        # Barra de color
        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")

        # ── Navegación mes ────────────────────────────────────────────────────
        nav = tk.Frame(win, bg=BG_PANEL)
        nav.pack(fill="x", padx=6, pady=5)
        lbl_m = tk.Label(nav, text="", bg=BG_PANEL, fg=TXT_MAIN,
                         font=("Arial", 11, "bold"), anchor="center")

        def _prev():
            m, y = state["month"] - 1, state["year"]
            if m < 1: m, y = 12, y - 1
            state["month"], state["year"] = m, y; _render()

        def _next():
            m, y = state["month"] + 1, state["year"]
            if m > 12: m, y = 1, y + 1
            state["month"], state["year"] = m, y; _render()

        self._btn(nav, " ◀ ", _prev, bg=BG_SIDEBAR, font_size=10
                  ).pack(side="left", ipady=2, ipadx=3)
        lbl_m.pack(side="left", fill="x", expand=True)
        self._btn(nav, " ▶ ", _next, bg=BG_SIDEBAR, font_size=10
                  ).pack(side="left", ipady=2, ipadx=3)

        # ── Encabezado días de la semana ──────────────────────────────────────
        hdr = tk.Frame(win, bg=BG_SIDEBAR)
        hdr.pack(fill="x", padx=6, pady=(0, 2))
        for d in DIAS_HDR:
            tk.Label(hdr, text=d, bg=BG_SIDEBAR, fg=TXT_LIGHT,
                     font=("Arial", 9, "bold"), width=3, anchor="center"
                     ).pack(side="left", expand=True, padx=1, pady=2)

        # ── Cuadrícula de días ────────────────────────────────────────────────
        grid = tk.Frame(win, bg=BG_PANEL)
        grid.pack(fill="both", expand=True, padx=6, pady=2)

        today = datetime.now().date()

        def _render():
            y, m = state["year"], state["month"]
            lbl_m.config(text=f"{MESES_ES[m-1]}  {y}")
            for w in grid.winfo_children():
                w.destroy()

            first_wd, n_days = _cal.monthrange(y, m)
            # first_wd: 0=Lunes … 6=Domingo

            for week_row in range(6):
                # Saltar filas vacías al final
                if week_row * 7 >= first_wd + n_days:
                    break
                row_f = tk.Frame(grid, bg=BG_PANEL)
                row_f.pack(fill="x", pady=1)
                for col in range(7):
                    cell_idx = week_row * 7 + col
                    day_n    = cell_idx - first_wd + 1
                    if 1 <= day_n <= n_days:
                        d_date   = _date(y, m, day_n)
                        is_today = (d_date == today)
                        bg_n     = PRIMARY   if is_today else BG_PANEL
                        fg_n     = "white"   if is_today else TXT_MAIN
                        bg_hv    = PRIMARY_DK if is_today else BG_MAIN
                        lbl = tk.Label(row_f, text=str(day_n),
                                       bg=bg_n, fg=fg_n,
                                       font=("Arial", 10,
                                             "bold" if is_today else "normal"),
                                       width=3, cursor="hand2", anchor="center")
                        lbl.pack(side="left", expand=True, ipady=3)
                        lbl.bind("<Button-1>",
                                 lambda _e, d=day_n, yr=y, mo=m: (
                                     entry_widget.delete(0, "end"),
                                     entry_widget.insert(0, f"{d:02d}/{mo:02d}/{yr}"),
                                     win.destroy()))
                        lbl.bind("<Enter>",
                                 lambda _e, b=lbl, hbg=bg_hv: b.config(bg=hbg))
                        lbl.bind("<Leave>",
                                 lambda _e, b=lbl, obg=bg_n:  b.config(bg=obg))
                    else:
                        tk.Label(row_f, text="", bg=BG_PANEL, width=3
                                 ).pack(side="left", expand=True)

        # ── Botón "Hoy" ───────────────────────────────────────────────────────
        def _go_today():
            n = datetime.now()
            entry_widget.delete(0, "end")
            entry_widget.insert(0, n.strftime("%d/%m/%Y"))
            win.destroy()

        self._btn(win, "Hoy", _go_today, bg=SUCCESS, font_size=10
                  ).pack(pady=(3, 6), ipadx=18, ipady=3)

        _render()

    # ── Cliente ───────────────────────────────────────────────────────────────
    def client_Window(self):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Seleccionar Cliente")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.36), int(sh * 0.55)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.grab_set()

        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(win, text="Seleccionar Cliente", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(10, 4))

        # Search bar
        search_var = tk.StringVar()
        sf = tk.Frame(win, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        sf.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(sf, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left", padx=6, pady=4)
        tk.Entry(sf, textvariable=search_var, font=("Arial", 12),
                 relief="flat", bg=BG_PANEL
                 ).pack(side="left", fill="x", expand=True, ipady=5, padx=4)

        cols = ("ID", "Cliente", "Teléfono", "Descuento")
        tree_cli = ttk.Treeview(win, columns=cols, show="headings", height=14)
        tree_cli.column("ID",        anchor="center", width=int(ww * 0.12))
        tree_cli.column("Cliente",   anchor="w",      width=int(ww * 0.44))
        tree_cli.column("Teléfono",  anchor="center", width=int(ww * 0.24))
        tree_cli.column("Descuento", anchor="center", width=int(ww * 0.16))
        for col in cols:
            tree_cli.heading(col, text=col)
        tree_cli.pack(padx=16, fill="x")
        self._tag_rows(tree_cli)

        all_clients = self.db.get_clients_full()

        def _refresh(*_):
            query = search_var.get().strip().lower()
            for row in tree_cli.get_children():
                tree_cli.delete(row)
            for i, c in enumerate(all_clients):
                if query and query not in c["name"].lower() \
                        and query not in str(c["id"]) \
                        and query not in (c["phone"] or "").lower():
                    continue
                total    = self.db.client_total_purchases(c["name"])
                disc_str = self._discount_label(total, c["name"]) or "—"
                self._insert_row(tree_cli,
                    (f"{c['id']:04d}", c["name"], c["phone"] or "—", disc_str),
                    idx=i)

        search_var.trace_add("write", _refresh)
        _refresh()

        def _sel(event=None):
            sel = tree_cli.selection()
            if not sel:
                return
            vals  = tree_cli.item(sel[0])["values"]
            nombre = str(vals[1])
            total  = self.db.client_total_purchases(nombre)
            disc   = self._discount_for(total, nombre)
            self.boton_cliente.config(
                text=f"{nombre}  {disc}%↓" if disc > 0 else nombre)
            self.cliente = nombre
            self._cliente_descuento = disc
            win.destroy()
            if self.carrito:
                self.actualizar_totales()

        tree_cli.bind("<Double-Button-1>", _sel)
        tk.Label(win, text="Doble clic para seleccionar", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9)).pack(pady=4)

    # ── Pago ──────────────────────────────────────────────────────────────────
    def pagar(self):
        if not self.carrito:
            return

        Total = self.Total
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Cobro")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.26), int(sh * 0.50)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        self.metodo_pago   = ""
        self.cobro_efectivo = 0.0

        tk.Frame(win, bg=SUCCESS, height=4).pack(fill="x")
        tk.Label(win, text=f"Total: $ {Total:,.2f}", bg=BG_PANEL, fg=SUCCESS,
                 font=("Arial", 18, "bold")).pack(pady=(12, 6))

        # Radio-style payment selection
        pay_frame = tk.Frame(win, bg=BG_PANEL)
        pay_frame.pack(fill="x", padx=20, pady=4)
        var_metodo = tk.StringVar(value="")

        # Change calc area
        cambio_frame = tk.Frame(win, bg=BG_PANEL)
        lbl_cambio = tk.Label(cambio_frame, text="Cambio: $ 0.00",
                              bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 13))
        e_recibido = tk.Entry(cambio_frame, font=("Arial", 13),
                              justify="right", relief="flat", bg=BG_MAIN)

        # ── Aviso de restricción de promoción ────────────────────────────────
        lbl_promo_warn = tk.Label(win, text="", bg="#FEF3C7", fg="#92400E",
                                  font=("Arial", 10, "bold"),
                                  wraplength=ww - 30, justify="center",
                                  padx=8, pady=4)

        def _check_promo_warn():
            restr  = getattr(self, "_discount_restrictions", 0)
            reason = getattr(self, "_discount_reason", "Sin descuento")
            mp     = self.metodo_pago
            if reason == "Sin descuento" or restr == 0 or not mp:
                lbl_promo_warn.pack_forget()
                return
            if restr == 1 and mp == "Efectivo":
                lbl_promo_warn.config(
                    text=f"⚠  «{reason}» aplica solo con Tarjeta / Transferencia.\n"
                         "Con Efectivo el descuento no es válido.")
                lbl_promo_warn.pack(fill="x", padx=16, pady=(0, 4))
            elif restr == 2 and mp in ("Tarjeta", "Transferencia"):
                lbl_promo_warn.config(
                    text=f"⚠  «{reason}» aplica solo con Efectivo.\n"
                         f"Con {mp} el descuento no es válido.")
                lbl_promo_warn.pack(fill="x", padx=16, pady=(0, 4))
            else:
                lbl_promo_warn.pack_forget()

        def _show_efectivo():
            self.metodo_pago    = "Efectivo"
            self.cobro_efectivo = Total
            cambio_frame.pack(fill="x", padx=20, pady=4)
            tk.Label(cambio_frame, text="Recibido $:", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11)).grid(row=0, column=0, sticky="w", pady=2)
            e_recibido.grid(row=0, column=1, padx=8, ipady=4)
            lbl_cambio.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

            def _calc(ev=None):
                try:
                    c = float(e_recibido.get()) - Total
                    lbl_cambio.config(text=f"Cambio: $ {c:,.2f}",
                                      fg=SUCCESS if c >= 0 else DANGER)
                except Exception:
                    lbl_cambio.config(text="Cambio: $ --", fg=TXT_GRAY)

            e_recibido.bind("<KeyRelease>", _calc)
            _check_promo_warn()

        def _show_tarjeta():
            self.metodo_pago    = "Tarjeta"
            self.cobro_efectivo = 0.0
            cambio_frame.pack_forget()
            _check_promo_warn()

        def _show_transferencia():
            self.metodo_pago    = "Transferencia"
            self.cobro_efectivo = 0.0
            cambio_frame.pack_forget()
            _check_promo_warn()

        for txt, val, cmd in [("Efectivo",      "Efectivo",      _show_efectivo),
                               ("Tarjeta",       "Tarjeta",       _show_tarjeta),
                               ("Transferencia", "Transferencia", _show_transferencia)]:
            rb = tk.Radiobutton(pay_frame, text=txt, variable=var_metodo,
                                value=val, command=cmd,
                                bg=BG_PANEL, fg=TXT_MAIN,
                                font=("Arial", 13), selectcolor=BG_PANEL,
                                activebackground=BG_PANEL, cursor="hand2")
            rb.pack(side="left", padx=8, pady=4)

        # ── Selector Uso CFDI ─────────────────────────────────────────────────
        cfdi_frame = tk.Frame(win, bg=BG_PANEL)
        cfdi_frame.pack(fill="x", padx=20, pady=(6, 2))
        tk.Label(cfdi_frame, text="Uso CFDI:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")
        var_cfdi = tk.StringVar(value="G03")
        cfdi_combo = ttk.Combobox(
            cfdi_frame,
            textvariable=var_cfdi,
            state="readonly",
            values=["G03 - Gastos en general",
                    "D01 - Honorarios médicos",
                    "S01 - Sin efectos fiscales"],
            width=24,
        )
        cfdi_combo.pack(side="left", padx=8)
        cfdi_combo.set("G03 - Gastos en general")

        def _do_cobrar(vendedor_nombre):
            """Ejecuta el cobro una vez validado el PIN del empleado."""
            t   = datetime.now()
            oid = self.order_id()
            productos = {pid: dict(pi) for pid, pi in self.carrito.items()}
            cli_disc  = getattr(self, "_cliente_descuento", 0)
            if cli_disc > 0 and productos:
                subtotal   = sum(pi["Importe"] for pi in productos.values())
                total_disc = round(subtotal * cli_disc / 100, 2)
                applied    = 0.0
                items_list = list(productos.items())
                for i, (pid, pi) in enumerate(items_list):
                    share = round(total_disc - applied, 2) \
                            if i == len(items_list) - 1 \
                            else round(pi["Importe"] * cli_disc / 100, 2)
                    pi["Descuento"] = round(pi.get("Descuento", 0.0) + share, 2)
                    pi["Importe"]   = round(pi["Importe"] - share, 2)
                    lt = pi["Importe"] + pi["Descuento"]
                    pi["Porcentaje_Descuento"] = round(pi["Descuento"] / lt, 4) if lt else 0.0
                    applied += share

            order = {
                "Cliente":        self.cliente,
                "Vendedor":       vendedor_nombre,
                "Fecha":          f"{self.ajusta(t.day)}/{self.ajusta(t.month)}/{t.year}",
                "Hora":           f"{self.ajusta(t.hour)}:{self.ajusta(t.minute)}:{self.ajusta(t.second)}",
                "Metodo_pago":    self.metodo_pago,
                "Productos":      productos,
                "Importe_total":  Total,
                "Descuento_razon": getattr(self, "_discount_reason", "Sin descuento"),
            }
            self.data_state["efectivo"] += self.cobro_efectivo
            self.data_orders[oid] = order
            self.db.save_order(oid, order)
            self.db.save_state(self.data_state["caja"], self.data_state["efectivo"])
            self.actualiza_data()
            uso_cfdi = var_cfdi.get()[:3].strip()
            self.generar_ticket_pdf(oid, order, productos, uso_cfdi)
            self.carrito                = {}
            self.cliente                = "Publico General"
            self._cliente_descuento     = 0
            self._discount_reason       = "Sin descuento"
            self._discount_restrictions = 0
            win.destroy()
            self.opcion_punto_venta()

        def _cobrar():
            if not self.metodo_pago:
                return

            # ── Ventana de confirmación con PIN ───────────────────────────────
            # Crear como hijo de self.root (no de win) para evitar jerarquía
            # anidada que Linux no dibuja bien.
            pw_pin = tk.Toplevel(self.root)
            pw_pin.title("Confirmar vendedor")
            pw_pin.configure(bg=BG_PANEL)
            pw_pin.resizable(False, False)
            # transient sobre win (ventana de cobro) para stacking correcto
            pw_pin.transient(win)

            # Construir contenido ANTES de fijar geometría para que
            # winfo_reqheight() devuelva el tamaño real en Linux
            tk.Frame(pw_pin, bg=SUCCESS, height=4).pack(fill="x")
            tk.Label(pw_pin, text="Ingresa tu PIN", bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 13, "bold")).pack(pady=(14, 4))
            tk.Label(pw_pin, text="para registrar la venta a tu nombre",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10)).pack(pady=(0, 10))

            pin_var   = tk.StringVar()
            pin_entry = tk.Entry(pw_pin, textvariable=pin_var, show="●",
                                 font=("Arial", 20), justify="center",
                                 relief="flat", bg=BG_MAIN,
                                 highlightbackground=PRIMARY, highlightthickness=2)
            pin_entry.pack(fill="x", padx=24, ipady=8)

            lbl_err = tk.Label(pw_pin, text="", bg=BG_PANEL, fg=DANGER,
                               font=("Arial", 10))
            lbl_err.pack(pady=6)

            lbl_emp = tk.Label(pw_pin, text="", bg=BG_PANEL, fg=SUCCESS,
                               font=("Arial", 11, "bold"))
            lbl_emp.pack()

            def _validar(event=None):
                data   = self.db.get_users()
                pin    = pin_var.get().strip()
                pins   = list(data["keys"])
                if pin in pins:
                    idx    = pins.index(pin)
                    nombre = data["users"][idx]
                    uid    = data["ids"][idx]
                    lbl_err.config(text="")
                    lbl_emp.config(text=f"✓  {nombre}")
                    # Auto check-in si el vendedor no estaba activo
                    if data["access"][idx] > 1:
                        self._auto_checkin_if_needed(uid, nombre)
                    pw_pin.after(600, lambda: (pw_pin.destroy(), _do_cobrar(nombre)))
                else:
                    lbl_err.config(text="PIN incorrecto, intenta de nuevo")
                    lbl_emp.config(text="")
                    pin_var.set("")

            pin_entry.bind("<Return>", _validar)
            self._btn(pw_pin, "Confirmar", _validar, bg=SUCCESS, font_size=12
                      ).pack(pady=14, ipadx=20, ipady=8)

            # Centrar sobre la ventana de cobro, con altura calculada tras
            # construir todos los widgets
            ppw = int(sw * 0.22)
            pw_pin.update_idletasks()
            pph = pw_pin.winfo_reqheight() + 20   # margen de seguridad
            win.update_idletasks()
            px = win.winfo_rootx() + (win.winfo_width()  - ppw) // 2
            py = win.winfo_rooty() + (win.winfo_height() - pph) // 2
            pw_pin.geometry(f"{ppw}x{pph}+{px}+{py}")
            pw_pin.grab_set()
            pw_pin.lift()
            pin_entry.focus_set()

        self._btn(win, "Confirmar Cobro", _cobrar, bg=SUCCESS, font_size=14
                  ).pack(pady=14, ipadx=20, ipady=8)

    def actualiza_data(self):
        for idx, item in self.carrito.items():
            self.data_products[idx][8] -= item["Cantidad"]
            self.db.update_stock(idx, -item["Cantidad"])

    # ══════════════════════════════════════════════════════════════════════════
    # ── Generación de ticket PDF ──────────────────────────────────────────────
    def _ticket_path(self, oid):
        """Devuelve la ruta del PDF para un oid dado (se crea o no el archivo)."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        oid = str(oid)
        # oid formato: YYMMDDHHMMSS → extraer fecha
        try:
            fecha_dir = f"20{oid[0:2]}-{oid[2:4]}-{oid[4:6]}"
        except Exception:
            fecha_dir = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(base_dir, "tickets", fecha_dir, f"ticket-{oid}.pdf")

    def generar_ticket_pdf(self, oid, order, productos, uso_cfdi="G03"):
        if not _FPDF:
            messagebox.showwarning(
                "PDF no disponible",
                "Instala fpdf2 para generar tickets:\npip install fpdf2")
            return

        try:
            self._generar_ticket_pdf_interno(oid, order, productos, uso_cfdi)
        except Exception as e:
            messagebox.showerror("Error al generar ticket", str(e))

    def _generar_ticket_pdf_interno(self, oid, order, productos, uso_cfdi):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pdf_path = self._ticket_path(oid)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        W = 70   # content width in mm

        pdf = FPDF(orientation="P", unit="mm", format=(80, 250))
        pdf.core_fonts_encoding = "windows-1252"
        pdf.set_auto_page_break(auto=True, margin=8)
        pdf.set_margins(5, 5, 5)
        pdf.add_page()

        # ── Logo ─────────────────────────────────────────────────────────────
        # Convertir RGBA → RGB sobre fondo blanco para máxima compatibilidad
        logo_path   = os.path.join(base_dir, "Logo_blanco.png")
        logo_y      = 5
        logo_w      = 40
        logo_bottom = logo_y + 20   # fallback si PIL no disponible
        if os.path.exists(logo_path) and _PIL:
            from PIL import Image as _PILImg
            _img = _PILImg.open(logo_path)
            _iw, _ih = _img.size
            logo_bottom = logo_y + (_ih / _iw) * logo_w
            if _img.mode in ("RGBA", "LA", "P"):
                bg = _PILImg.new("RGB", _img.size, (255, 255, 255))
                alpha = _img.convert("RGBA").split()[3]
                bg.paste(_img.convert("RGBA"), mask=alpha)
                _img = bg
            else:
                _img = _img.convert("RGB")
            _buf = io.BytesIO()
            _img.save(_buf, format="PNG")
            _buf.seek(0)
            pdf.image(_buf, x=(80 - logo_w) / 2, y=logo_y, w=logo_w)
        pdf.set_y(logo_bottom + 5)

        # ── Encabezado emisor ─────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(W, 5, "ORTOPEDIA BIOMED", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(30, 41, 59)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(1)

        pdf.set_font("Helvetica", "", 7)
        for linea in [
            "RFC: GABJ960220TV2",
            "Régimen: Simplificado de Confianza",
            "CP: 70805",
            "Av. 3 de Octubre 424, Miahuatlán de Porfirio Díaz",
            "ortopediabiomed@gmail.com",
        ]:
            pdf.cell(W, 3.5, linea, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(2)

        # ── Datos del ticket ──────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(W, 4, f"TICKET #: {oid}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(W, 4, f"Fecha: {order['Fecha']}   Hora: {order['Hora']}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(W, 4, f"Vendedor: {order['Vendedor']}", new_x="LMARGIN", new_y="NEXT")

        cliente = order.get("Cliente", "Publico General")
        if cliente and cliente != "Publico General":
            pdf.cell(W, 4, f"Cliente: {cliente}", new_x="LMARGIN", new_y="NEXT")
            tel = self.data_clients.get(cliente, {}).get("cel", "")
            if tel:
                pdf.cell(W, 4, f"Tel: {tel}", new_x="LMARGIN", new_y="NEXT")

        cfdi_labels = {
            "G03": "G03 - Gastos en general",
            "D01": "D01 - Honorarios médicos",
            "S01": "S01 - Sin efectos fiscales",
        }
        pdf.cell(W, 4, f"Uso CFDI: {cfdi_labels.get(uso_cfdi, uso_cfdi)}",
                 new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(2)

        # ── Encabezado de productos ───────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(32, 4, "Producto",  new_x="RIGHT")
        pdf.cell(8,  4, "Cant.",     align="C", new_x="RIGHT")
        pdf.cell(14, 4, "P.Unit.",   align="R", new_x="RIGHT")
        pdf.cell(16, 4, "Importe",   align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(1)

        # ── Renglones de productos ────────────────────────────────────────────
        pdf.set_font("Helvetica", "", 7)
        subtotal_bruto  = 0.0
        total_descuento = 0.0

        for pid, pi in productos.items():
            info    = self.data_products.get(str(pid), ["", "", "—"])
            nombre  = str(info[2]) if len(info) > 2 else "—"
            cant    = int(pi.get("Cantidad", 1))
            importe = float(pi.get("Importe", 0))
            desc    = float(pi.get("Descuento", 0))
            p_unit  = (importe + desc) / cant if cant else 0

            subtotal_bruto  += importe + desc
            total_descuento += desc

            if len(nombre) > 20:
                nombre = nombre[:19] + "."

            pdf.cell(32, 4, nombre,             new_x="RIGHT")
            pdf.cell(8,  4, str(cant),           align="C", new_x="RIGHT")
            pdf.cell(14, 4, f"${p_unit:,.2f}",  align="R", new_x="RIGHT")
            pdf.cell(16, 4, f"${importe:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(1)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(2)

        # ── Totales ───────────────────────────────────────────────────────────
        hay_descuento = total_descuento > 0.005
        total_neto    = float(order["Importe_total"])
        iva           = round(total_neto * 0.16 / 1.16, 2)
        base_sin_iva  = round(total_neto - iva, 2)

        def _fila_total(etiqueta, monto, bold=False, prefijo=""):
            pdf.set_font("Helvetica", "B" if bold else "", 8 if not bold else 10)
            pdf.cell(46, 5 if not bold else 6, etiqueta, new_x="RIGHT")
            pdf.cell(24, 5 if not bold else 6,
                     f"{prefijo}$ {monto:,.2f}", align="R",
                     new_x="LMARGIN", new_y="NEXT")

        _fila_total("Subtotal (sin IVA):", base_sin_iva)
        if hay_descuento:
            _fila_total("Descuento:", total_descuento, prefijo="- ")
        _fila_total("IVA (16%):", iva)
        _fila_total("TOTAL:", total_neto, bold=True)

        pdf.ln(3)
        pdf.set_draw_color(30, 41, 59)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(3)

        # ── Pie ───────────────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(W, 4, "Gracias por su compra", align="C",
                 new_x="LMARGIN", new_y="NEXT")

        pdf.output(pdf_path)

        # ── Copiar a Descargas y abrir ────────────────────────────────────────
        try:
            dl_name = f"ticket-{oid}.pdf"
            dl_path = self._downloads_path(dl_name)
            import shutil as _shutil
            _shutil.copy2(pdf_path, dl_path)
            open_path = dl_path
        except Exception:
            open_path = pdf_path
        try:
            if platform.system() == "Windows":
                os.startfile(open_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", open_path])
            else:
                subprocess.Popen(["xdg-open", open_path])
        except Exception:
            log_exc("_fila_total")

    # ══════════════════════════════════════════════════════════════════════════
    # ── Info faltante del empleado ────────────────────────────────────────────
    def _check_employee_info(self, user_id):
        rows = self.db.get_users_full()
        row  = next((dict(r) for r in rows if r["id"] == user_id), None)
        if not row:
            return
        needs_birth     = not str(row.get("birth_date",      "") or "").strip()
        needs_emergency = (not str(row.get("emergency_name", "") or "").strip() or
                           not str(row.get("emergency_phone","") or "").strip())
        if needs_birth or needs_emergency:
            self._popup_employee_info(user_id, row, needs_birth, needs_emergency)

    # ── Checador: utilidades de asistencia ────────────────────────────────────
    def _auto_checkin_if_needed(self, user_id, username):
        """Registra entrada automática si el empleado no está activo hoy."""
        today = datetime.now().strftime("%d/%m/%Y")
        row = self.db.conn.execute(
            "SELECT tipo FROM checadas WHERE user_id=? AND date=? ORDER BY id DESC LIMIT 1",
            (user_id, today)).fetchone()
        is_active = (row is not None and row["tipo"] == "entrada")
        if not is_active:
            ts = datetime.now().strftime("%H:%M:%S")
            self.db.conn.execute(
                "INSERT INTO checadas(user_id,username,tipo,timestamp,date)"
                " VALUES(?,?,?,?,?)",
                (user_id, username, "entrada", ts, today))
            self.db.conn.commit()

    def _auto_checkout_forgotten(self):
        """Registra salida automática a empleados que olvidaron checar ayer o antes."""
        today = datetime.now().strftime("%d/%m/%Y")
        # Busca empleados cuya última checada de cualquier día anterior fue "entrada"
        rows = self.db.conn.execute("""
            SELECT c.user_id, c.username, c.date
            FROM checadas c
            WHERE c.date != ?
              AND c.tipo = 'entrada'
              AND c.id = (
                  SELECT MAX(c2.id) FROM checadas c2
                  WHERE c2.user_id = c.user_id AND c2.date = c.date
              )
        """, (today,)).fetchall()
        for r in rows:
            self.db.conn.execute(
                "INSERT INTO checadas(user_id,username,tipo,timestamp,date)"
                " VALUES(?,?,?,?,?)",
                (r["user_id"], r["username"], "salida", "23:59 (auto)", r["date"]))
        if rows:
            self.db.conn.commit()

    def _buscar_producto_popup(self, line_data):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Buscar Producto")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.52), int(sh * 0.62)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.grab_set()

        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(win, text="Buscar Producto", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(10, 4))

        search_var = tk.StringVar()
        sf = tk.Frame(win, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        sf.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(sf, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left", padx=6, pady=4)
        tk.Entry(sf, textvariable=search_var, font=("Arial", 12),
                 relief="flat", bg=BG_PANEL
                 ).pack(side="left", fill="x", expand=True, ipady=5, padx=4)

        cols = ("SKU", "Nombre", "Categoría", "Exist.", "Costo")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for col, frac in zip(cols, (0.10, 0.38, 0.18, 0.08, 0.12)):
            tree.column(col,
                anchor="w" if col in ("Nombre", "Categoría") else "center",
                width=int(ww * frac))
            tree.heading(col, text=col)
        tree.pack(padx=16, fill="x")
        self._tag_rows(tree)

        def _refresh(*_):
            query = search_var.get().strip().lower()
            for r in tree.get_children():
                tree.delete(r)
            for i, (pid, info) in enumerate(self.data_products.items()):
                sku  = str(info[0]).strip() if info[0] else ""
                name = str(info[2]).strip() if len(info) > 2 else "—"
                cat  = str(info[4]).strip() if len(info) > 4 else "—"
                qty  = info[8] if len(info) > 8 else 0
                cost = float(info[9]) if len(info) > 9 else 0.0
                if query and query not in sku.lower() and query not in name.lower() \
                        and query not in cat.lower():
                    continue
                self._insert_row(tree,
                    (sku, name, cat, qty, f"$ {cost:,.2f}"),
                    text=str(pid), idx=i)

        search_var.trace_add("write", _refresh)
        _refresh()

        def _sel(event=None):
            sel = tree.selection()
            if not sel:
                return
            pid  = tree.item(sel[0], "text")
            info = self.data_products.get(pid, [])
            sku  = str(info[0]).strip() if info[0] else ""
            name = str(info[2]).strip() if len(info) > 2 else pid
            cost = float(info[9]) if len(info) > 9 else 0.0
            line_data["pid_var"].set(pid)
            disp = f"{sku}  {name}" if sku else name
            line_data["lbl"].config(text=disp, fg=TXT_MAIN)
            line_data["cost_e"].delete(0, tk.END)
            line_data["cost_e"].insert(0, f"{cost:.2f}")
            win.destroy()

        tree.bind("<Double-Button-1>", _sel)
        tk.Label(win, text="Doble clic para seleccionar", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9)).pack(pady=4)

    def _show_calendar_var(self, var, parent=None):
        class _FakeEntry:
            def __init__(self, v): self._v = v
            def get(self): return self._v.get()
            def delete(self, a, b): pass
            def insert(self, idx, val): self._v.set(val)
        self._show_calendar(_FakeEntry(var), parent=parent)

    def _popup_employee_info(self, user_id, row, needs_birth, needs_emergency):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Completa tu perfil")
        win.configure(bg=BG_PANEL)
        win.resizable(False, False)
        ww = int(sw * 0.36)
        wh = int(sh * 0.48 + (int(sh * 0.12) if needs_birth else 0)
                             + (int(sh * 0.16) if needs_emergency else 0))
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        # transient + grab: funciona correctamente en Linux sin bloquear
        # ventanas hijas (como el calendario). -topmost no se usa porque
        # aplasta incluso los propios diálogos en algunos WM de Linux.
        win.transient(self.root)
        win.lift()
        win.grab_set()
        win.focus_force()

        def _keep_focus():
            try:
                if not win.winfo_exists():
                    return
                current = win.grab_current()
                if current is None:
                    # Grab perdido — restaurar
                    win.grab_set()
                    win.lift()
                    win.focus_force()
                elif current == win:
                    # Solo forzar foco si no hay ningún widget activo dentro
                    if win.focus_get() is None:
                        win.focus_force()
                # Si current != win hay un diálogo hijo con grab (ej. calendario):
                # dejar pasar, él mismo lo libera al cerrarse
                win.after(400, _keep_focus)
            except tk.TclError:
                pass

        win.after(400, _keep_focus)

        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(win, text=f"¡Hola, {self.usuario}!", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(14, 2))
        tk.Label(win, text="Ingresa tus datos para poder utilizar la aplicación.",
                 bg=BG_PANEL, fg=PRIMARY, font=("Arial", 11, "bold")).pack(pady=(0, 4))
        tk.Label(win, text="Necesitamos completar tu información de usuario.",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10)).pack(pady=(0, 12))

        birth_var   = tk.StringVar(value=str(row.get("birth_date",      "") or ""))
        em_name_var = tk.StringVar(value=str(row.get("emergency_name",  "") or ""))
        em_tel_var  = tk.StringVar(value=str(row.get("emergency_phone", "") or ""))

        if needs_birth:
            sec = tk.Frame(win, bg=BG_MAIN, pady=8)
            sec.pack(fill="x", padx=20, pady=4)
            tk.Label(sec, text="Fecha de nacimiento", bg=BG_MAIN, fg=TXT_GRAY,
                     font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=4)
            row_b = tk.Frame(sec, bg=BG_MAIN)
            row_b.pack(fill="x", padx=4, pady=4)
            self._btn(row_b, "  Seleccionar fecha  ",
                      lambda: self._show_calendar_var(birth_var, parent=win),
                      bg=PRIMARY, font_size=11
                      ).pack(side="left", ipady=6)
            tk.Label(row_b, textvariable=birth_var, bg=BG_MAIN, fg=TXT_MAIN,
                     font=("Arial", 12), anchor="w", width=14
                     ).pack(side="left", padx=8)

        if needs_emergency:
            sec2 = tk.Frame(win, bg=BG_MAIN, pady=8)
            sec2.pack(fill="x", padx=20, pady=4)
            tk.Label(sec2, text="Contacto de emergencia", bg=BG_MAIN, fg=TXT_GRAY,
                     font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=4)
            for lbl, var in [("Nombre completo", em_name_var),
                              ("Teléfono",        em_tel_var)]:
                rf = tk.Frame(sec2, bg=BG_MAIN)
                rf.pack(fill="x", padx=4, pady=3)
                tk.Label(rf, text=lbl, bg=BG_MAIN, fg=TXT_GRAY,
                         font=("Arial", 10), width=16, anchor="w").pack(side="left")
                ent = tk.Entry(rf, textvariable=var, font=("Arial", 12), relief="flat",
                               bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
                ent.pack(side="left", fill="x", expand=True, ipady=6)
                # En Linux el foco en Entry con grab activo requiere llamada explícita
                ent.bind("<Button-1>", lambda ev, e=ent: e.focus_set())

        err = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err.pack(pady=4)

        def _guardar():
            bd = birth_var.get().strip()   if needs_birth     else None
            en = em_name_var.get().strip() if needs_emergency else None
            ep = em_tel_var.get().strip()  if needs_emergency else None
            if needs_birth:
                try:
                    datetime.strptime(bd, "%d/%m/%Y")
                except Exception:
                    err.config(text="Formato de fecha inválido. Usa dd/mm/aaaa")
                    return
            if needs_emergency and (not en or not ep):
                err.config(text="Nombre y teléfono de emergencia son obligatorios.")
                return
            self.db.update_employee_info(user_id, birth_date=bd,
                                         emergency_name=en, emergency_phone=ep)
            win.destroy()

        self._btn(win, "Guardar", _guardar, bg=PRIMARY, font_size=13
                  ).pack(pady=16, ipadx=30, ipady=8)

    # ══════════════════════════════════════════════════════════════════════════
    # GESTIÓN DE CLIENTES
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _discount_for(total, name=""):
        if name == "Publico General":
            return 0
        if total == 0:     return 5   # bienvenida — primera compra
        if total >= 20000: return 15
        if total >= 10000: return 10
        if total >= 5000:  return 5
        return 0

    @staticmethod
    def _discount_label(total, name=""):
        if name == "Publico General":
            return ""
        if total == 0:
            return "5% bienvenida"
        disc = PuntoDeVenta._discount_for(total, name)
        return f"{disc}%" if disc else ""

    # ══════════════════════════════════════════════════════════════════════════
    # RECEPCIÓN DE PEDIDOS
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_recepcion(self):
        self._current_screen = self.opcion_recepcion
        sw, sh = self.screen_width, self.screen_height
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self.frame_recepcion = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_recepcion.place(x=int(sw * 0.1), y=0, width=pw, height=sh)

        self._header(self.frame_recepcion, "Recepción de Pedidos",
                     subtitle="Entrada de mercancía — actualiza stock y costo")

        lw = int(pw * 0.54)
        lx = int(pw * 0.02)
        rx = lx + lw + int(pw * 0.02)
        rw = pw - rx - int(pw * 0.01)
        cont_y = hh + int(sh * 0.02)
        sq = int(sh * 0.048)

        # ── Formulario (izquierda) ────────────────────────────────────────────
        form_card = self._card(self.frame_recepcion, lx, cont_y, lw,
                               sh - cont_y - int(sh * 0.02))

        # Campos encabezado
        fields_y = 28
        fh = int(sh * 0.038)
        fgap = int(sh * 0.012)

        fecha_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))

        field_defs = [
            ("Proveedor",      None),
            ("Folio factura",  None),
            ("Total factura",  None),
        ]
        f_entries = {}
        for label, _ in field_defs:
            row_f = tk.Frame(form_card, bg=BG_PANEL)
            row_f.place(x=8, y=fields_y, width=lw - 18, height=fh)
            tk.Label(row_f, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10), width=16, anchor="w").pack(side="left")
            e = tk.Entry(row_f, font=("Arial", 11), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            f_entries[label] = e
            fields_y += fh + fgap

        # Fecha (calendar)
        fecha_row = tk.Frame(form_card, bg=BG_PANEL)
        fecha_row.place(x=8, y=fields_y, width=lw - 18, height=fh)
        tk.Label(fecha_row, text="Fecha recepción", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), width=16, anchor="w").pack(side="left")
        self._btn(fecha_row, "📅",
                  lambda: self._show_calendar_var(fecha_var),
                  bg=PRIMARY, font_size=10
                  ).pack(side="left", ipadx=4, ipady=4)
        tk.Label(fecha_row, textvariable=fecha_var, bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 11), anchor="w").pack(side="left", padx=8)
        fields_y += fh + fgap

        # Separator
        sep_y = fields_y + int(sh * 0.005)
        tk.Frame(form_card, bg=BORDER, height=1).place(x=8, y=sep_y, width=lw - 18)
        tk.Label(form_card, text="PRODUCTOS RECIBIDOS", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9, "bold")).place(x=8, y=sep_y + 6)
        fields_y = sep_y + int(sh * 0.04)

        # Product lines — scrollable canvas
        lines_h = int(sh * 0.30)
        lines_canvas = tk.Canvas(form_card, bg=BG_PANEL, highlightthickness=0)
        lines_sb = ttk.Scrollbar(form_card, orient="vertical",
                                 command=lines_canvas.yview)
        lines_inner = tk.Frame(lines_canvas, bg=BG_PANEL)

        lines_canvas.place(x=8, y=fields_y, width=lw - 30, height=lines_h)
        lines_sb.place(x=lw - 20, y=fields_y, width=14, height=lines_h)
        lines_canvas.configure(yscrollcommand=lines_sb.set)
        win_id = lines_canvas.create_window((0, 0), window=lines_inner, anchor="nw")

        def _on_inner_config(event):
            lines_canvas.configure(scrollregion=lines_canvas.bbox("all"))
            lines_canvas.itemconfig(win_id, width=lines_canvas.winfo_width())
        lines_inner.bind("<Configure>", _on_inner_config)

        # Column headers
        hdr = tk.Frame(lines_inner, bg=BG_SIDEBAR)
        hdr.pack(fill="x")
        for txt, w in [("Producto / SKU", 0.52), ("Cant.", 0.12),
                       ("Costo unit.", 0.18), ("", 0.08)]:
            tk.Label(hdr, text=txt, bg=BG_SIDEBAR, fg=TXT_LIGHT,
                     font=("Arial", 9, "bold"), anchor="w"
                     ).pack(side="left", padx=4, pady=3, ipadx=2)

        self.data_products = self.db.get_products()
        self._ped_lines = []

        def _add_line():
            lf = tk.Frame(lines_inner, bg=BG_PANEL,
                          highlightbackground=BORDER, highlightthickness=1)
            lf.pack(fill="x", padx=2, pady=2)

            pid_var = tk.StringVar(value="")
            sel_lbl = tk.Label(lf, text="— seleccionar —", bg=BG_MAIN,
                               fg=TXT_GRAY, font=("Arial", 10), anchor="w",
                               width=26, relief="flat")
            sel_lbl.pack(side="left", padx=3, pady=4, ipady=3)

            qty_e = tk.Entry(lf, font=("Arial", 10), width=5, justify="center",
                             relief="flat", bg=BG_MAIN,
                             highlightbackground=BORDER, highlightthickness=1)
            qty_e.insert(0, "1")
            qty_e.pack(side="left", padx=3, ipady=3)

            cost_e = tk.Entry(lf, font=("Arial", 10), width=9, justify="right",
                              relief="flat", bg=BG_MAIN,
                              highlightbackground=BORDER, highlightthickness=1)
            cost_e.pack(side="left", padx=3, ipady=3)

            line_data = {"frame": lf, "pid_var": pid_var,
                         "lbl": sel_lbl, "qty_e": qty_e, "cost_e": cost_e}
            self._ped_lines.append(line_data)

            self._btn(lf, "🔍", lambda ld=line_data: self._buscar_producto_popup(ld),
                      bg=PRIMARY, font_size=11
                      ).pack(side="left", padx=3, ipady=3)

            def _remove(ld=line_data):
                self._ped_lines.remove(ld)
                ld["frame"].destroy()
            self._btn(lf, "×", _remove, bg=DANGER, font_size=12, bold=False
                      ).pack(side="left", padx=2, ipady=1)

        self._btn(form_card, "+ Línea", _add_line,
                  bg=SUCCESS, font_size=10
                  ).place(x=8, y=fields_y + lines_h + int(sh * 0.008),
                          width=int(lw * 0.22), height=int(sh * 0.038))

        # Notas
        notas_y = fields_y + lines_h + int(sh * 0.058)
        tk.Label(form_card, text="Notas:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10)).place(x=8, y=notas_y)
        t_notas = tk.Text(form_card, font=("Arial", 10), relief="flat",
                          bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1,
                          height=3)
        t_notas.place(x=8, y=notas_y + int(sh * 0.025),
                      width=lw - 18, height=int(sh * 0.07))

        # ── Guardar ───────────────────────────────────────────────────────────
        def _guardar():
            lines = []
            for ld in self._ped_lines:
                pid = ld["pid_var"].get().strip()
                if not pid:
                    continue
                try:
                    qty = int(ld["qty_e"].get() or 0)
                except Exception:
                    qty = 0
                try:
                    cost = float(ld["cost_e"].get() or 0)
                except Exception:
                    cost = 0.0
                if pid and qty > 0:
                    lines.append((pid, qty, cost))
            if not lines:
                return

            vendor  = f_entries["Proveedor"].get().strip()
            folio   = f_entries["Folio factura"].get().strip()
            try:
                inv_t = float(f_entries["Total factura"].get() or 0)
            except Exception:
                inv_t = 0.0
            fecha   = fecha_var.get().strip()
            notas   = t_notas.get("1.0", tk.END).strip()

            rec_id = self.db.save_reception(fecha, vendor, folio, inv_t, notas)
            for pid, qty, cost in lines:
                self.db.save_reception_item(rec_id, pid, qty, cost)
                self.db.update_stock(pid, qty)
                if cost > 0:
                    self.db.update_product_cost(pid, cost)
            self.data_products = self.db.get_products()

            # Reset form
            for e in f_entries.values():
                e.delete(0, tk.END)
            t_notas.delete("1.0", tk.END)
            for ld in list(self._ped_lines):
                ld["frame"].destroy()
            self._ped_lines.clear()
            fecha_var.set(datetime.now().strftime("%d/%m/%Y"))
            _load_history()

        save_y = notas_y + int(sh * 0.105)
        self._btn(form_card, "✓ Guardar entrada", _guardar,
                  bg=SUCCESS, font_size=12
                  ).place(x=int(lw * 0.35), y=save_y,
                          width=int(lw * 0.58), height=int(sh * 0.048))

        _add_line()  # start with one empty line

        # ── Historial (derecha) ───────────────────────────────────────────────
        tk.Label(self.frame_recepcion, text="Historial de entradas",
                 bg=BG_MAIN, fg=TXT_MAIN, font=("Arial", 12, "bold"), anchor="w"
                 ).place(x=rx, y=cont_y, width=rw, height=int(sh * 0.03))

        hist_y = cont_y + int(sh * 0.033)
        hist_h = sh - hist_y - int(sh * 0.02)
        hcols  = ("Fecha", "Proveedor", "Folio", "Productos", "Total")
        self.tree_recepciones = ttk.Treeview(self.frame_recepcion,
                                              columns=hcols, show="headings",
                                              height=20)
        for col, frac in zip(hcols, (0.09, 0.16, 0.09, 0.06, 0.09)):
            self.tree_recepciones.column(col, anchor="center", width=int(pw * frac))
            self.tree_recepciones.heading(col, text=col)
        self.tree_recepciones.place(x=rx, y=hist_y, width=rw, height=hist_h)
        self._tag_rows(self.tree_recepciones)
        self._add_scrollbar(self.frame_recepcion, self.tree_recepciones,
                            rx, hist_y, rw, hist_h)

        def _load_history():
            for r in self.tree_recepciones.get_children():
                self.tree_recepciones.delete(r)
            for i, rec in enumerate(self.db.get_receptions()):
                self._insert_row(self.tree_recepciones,
                    (rec["date"], rec["vendor"] or "—", rec["folio"] or "—",
                     rec["n_items"], f"$ {rec['invoice_total']:,.2f}"),
                    idx=i)

        _load_history()

    def opcion_pedidos(self):
        self._current_screen = self.opcion_pedidos
        sw, sh = self.screen_width, self.screen_height
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self.frame_pedidos = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_pedidos.place(x=int(sw * 0.1), y=0, width=pw, height=sh)
        self._header(self.frame_pedidos, "Pedidos de Compra",
                     subtitle="Selecciona un pedido para cambiar estado, modificar o imprimir")

        cont_y  = hh + int(sh * 0.015)
        lx      = int(pw * 0.02)
        tree_w  = int(pw * 0.95)
        bar_h   = int(sh * 0.075)
        bar_y   = sh - bar_h - int(sh * 0.015)
        tree_h  = bar_y - cont_y - int(sh * 0.01)

        # ── Lista de pedidos ──────────────────────────────────────────────────
        STATUSES = ["Pedido pendiente", "En cotización", "En revisión", "Aceptado"]

        cols = ("#", "Fecha", "Vendedor", "# Prods", "Subtotal", "IVA", "Total", "Estado")
        self.tree_pedidos = ttk.Treeview(self.frame_pedidos,
                                         columns=cols, show="headings")
        cw_p = [int(tree_w * w) for w in (0.04, 0.16, 0.12, 0.07, 0.13, 0.08, 0.13, 0.13)]
        for col, cw in zip(cols, cw_p):
            self.tree_pedidos.column(col, anchor="center", width=cw, minwidth=20)
            self.tree_pedidos.heading(col, text=col)
        self.tree_pedidos.place(x=lx, y=cont_y, width=tree_w - 14, height=tree_h)
        self._tag_rows(self.tree_pedidos)
        self.tree_pedidos.tag_configure("status_pend", foreground=TXT_GRAY)
        self.tree_pedidos.tag_configure("status_cot",  foreground=WARNING)
        self.tree_pedidos.tag_configure("status_rev",  foreground=PRIMARY)
        self.tree_pedidos.tag_configure("status_real", foreground=SUCCESS)
        self._add_scrollbar(self.frame_pedidos, self.tree_pedidos,
                            lx, cont_y, tree_w - 14, tree_h)

        # ── Barra de acciones ─────────────────────────────────────────────────
        bar = tk.Frame(self.frame_pedidos, bg=BG_PANEL,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.place(x=lx, y=bar_y, width=tree_w, height=bar_h)

        self._ped_btn_detalle   = self._btn(bar, "  Ver detalle",
                                             self._ped_detalle_ventana,
                                             bg=PRIMARY, font_size=11)
        self._ped_btn_detalle.pack(side="left", padx=(14, 6), ipady=3)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", pady=6)

        self._ped_btn_modificar = self._btn(bar, "  Modificar",
                                             self._ped_modificar,
                                             bg=WARNING, font_size=11)
        self._ped_btn_modificar.pack(side="left", padx=(12, 6), ipady=3)

        self._ped_btn_imprimir  = self._btn(bar, "  Imprimir",
                                             self._ped_imprimir_sel,
                                             bg=TXT_GRAY, font_size=11)
        self._ped_btn_imprimir.pack(side="left", padx=(0, 6), ipady=3)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", pady=6)

        self._ped_btn_eliminar  = self._btn(bar, "  Eliminar",
                                             self._ped_eliminar,
                                             bg=DANGER, font_size=11)
        self._ped_btn_eliminar.pack(side="left", padx=(12, 6), ipady=3)

        # Deshabilitar botones hasta selección
        for b in (self._ped_btn_detalle, self._ped_btn_modificar,
                  self._ped_btn_imprimir, self._ped_btn_eliminar):
            b.config(state="disabled")

        # ── Cargar datos ──────────────────────────────────────────────────────
        def _reload():
            for r in self.tree_pedidos.get_children():
                self.tree_pedidos.delete(r)
            for i, po in enumerate(self.db.get_purchase_orders()):
                st = po["status"]
                if "pendiente" in st.lower():  st_tag = "status_pend"
                elif "cotiz" in st.lower():    st_tag = "status_cot"
                elif "revis" in st.lower():    st_tag = "status_rev"
                else:                          st_tag = "status_real"
                stripe = "even" if i % 2 == 0 else "odd"
                try:    vnd = po["vendor"] or "—"
                except Exception: vnd = "—"
                self.tree_pedidos.insert("", "end",
                    text=str(po["id"]),
                    values=(po["id"], po["date"], vnd, po["n_items"],
                            f"${po['subtotal']:,.2f}",
                            f"${po['iva']:,.2f}",
                            f"${po['total']:,.2f}",
                            po["status"]),
                    tags=(stripe, st_tag))
        self._ped_reload = _reload
        _reload()

        def _on_select(event=None):
            sel = self.tree_pedidos.selection()
            if not sel:
                for b in (self._ped_btn_detalle, self._ped_btn_modificar,
                          self._ped_btn_imprimir, self._ped_btn_eliminar):
                    b.config(state="disabled")
                return
            vals = self.tree_pedidos.item(sel[0], "values")
            current_status = vals[7]
            es_aceptado = "acept" in current_status.lower() or "realiz" in current_status.lower()
            self._ped_btn_detalle.config(state="normal")
            self._ped_btn_modificar.config(
                state="disabled" if es_aceptado else "normal")
            self._ped_btn_imprimir.config(state="normal")
            self._ped_btn_eliminar.config(state="normal")

        self.tree_pedidos.bind("<<TreeviewSelect>>", _on_select)
        self.tree_pedidos.bind("<Double-Button-1>", self._ped_detalle_ventana)

    def _ped_detalle_ventana(self, event=None):
        sel = self.tree_pedidos.selection()
        if not sel:
            return
        oid    = int(self.tree_pedidos.item(sel[0], "text"))
        vals   = self.tree_pedidos.item(sel[0], "values")
        fecha  = vals[1]
        vendor = vals[2] if vals[2] != "—" else ""
        status = vals[7]
        items  = self.db.get_purchase_order_items(oid)
        if not items:
            return

        STATUS_ORDER = ["Pedido pendiente", "En cotización", "En revisión", "Aceptado"]
        # Normalizar estado para comparar con el orden
        def _match_status(st):
            sl = st.lower()
            if "pendiente" in sl: return "Pedido pendiente"
            if "cotiz" in sl:     return "En cotización"
            if "revis" in sl:     return "En revisión"
            if "acept" in sl or "realiz" in sl: return "Aceptado"
            return st
        status_norm = _match_status(status)
        try:
            status_idx = STATUS_ORDER.index(status_norm)
        except ValueError:
            status_idx = 0
        es_aceptado = status_norm == "Aceptado"
        es_cotizacion = status_norm == "En cotización"

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title(f"Pedido #{oid}")
        win.configure(bg=BG_PANEL)
        win.resizable(True, True)
        ww = max(int(sw * 0.65), 720)
        wh = max(int(sh * 0.86), 580)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.grab_set()

        # ── Encabezado ────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=BG_SIDEBAR)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"  Pedido #{oid}", bg=BG_SIDEBAR, fg=TXT_LIGHT,
                 font=("Arial", 14, "bold"), anchor="w").pack(side="left",
                 padx=14, pady=10)
        st_color = (TXT_GRAY if "pendiente" in status.lower() else
                    WARNING  if "cotiz"    in status.lower() else
                    PRIMARY  if "revis"    in status.lower() else SUCCESS)
        tk.Label(hdr, text=f"  {status}  ", bg=st_color, fg="white",
                 font=("Arial", 10, "bold")).pack(side="right", padx=14, pady=10)

        # ── Fecha + Vendedor editable ─────────────────────────────────────────
        info = tk.Frame(win, bg=BG_PANEL)
        info.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(info, text=f"Fecha: {fecha}", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")
        tk.Label(info, text="  |  Distribuidor:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left")
        _dist_rows = self.db.conn.execute(
            "SELECT DISTINCT vendor FROM products WHERE vendor IS NOT NULL AND vendor != '' "
            "ORDER BY vendor").fetchall()
        dist_names = [r[0] for r in _dist_rows]
        if es_aceptado:
            ent_vendor = tk.Entry(info, font=("Arial", 11), width=20,
                                  bg=BG_MAIN, fg=TXT_MAIN,
                                  highlightbackground=BORDER, highlightthickness=1,
                                  state="disabled")
            ent_vendor.insert(0, vendor)
            ent_vendor.pack(side="left", padx=6)
        else:
            ent_vendor = ttk.Combobox(info, values=dist_names,
                                      font=("Arial", 11), width=18, state="normal")
            ent_vendor.set(vendor)
            ent_vendor.pack(side="left", padx=6)

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(6, 0))

        # ── Encabezado de columnas ────────────────────────────────────────────
        col_hdr = tk.Frame(win, bg=BG_SIDEBAR)
        col_hdr.pack(fill="x", padx=16, pady=(0, 0))
        if es_cotizacion:
            tk.Label(col_hdr, text="✓", bg=BG_SIDEBAR, fg="white",
                     font=("Arial", 10, "bold"), width=3, anchor="center"
                     ).pack(side="left", padx=2, pady=5)
        col_specs = [("SKU",         9),  ("Producto",    26),
                     ("Talla/Color", 14), ("Cantidad",    8),
                     ("Costo unit.", 12), ("Total línea", 12)]
        for ctxt, cw in col_specs:
            tk.Label(col_hdr, text=ctxt, bg=BG_SIDEBAR, fg="white",
                     font=("Arial", 10, "bold"), width=cw, anchor="center"
                     ).pack(side="left", padx=2, pady=5)

        # ── Área scrollable de filas editables ───────────────────────────────
        canvas = tk.Canvas(win, bg=BG_PANEL, highlightthickness=0)
        vsb = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 4))
        canvas.pack(fill="both", expand=True, padx=(16, 0), pady=2)

        rows_fr = tk.Frame(canvas, bg=BG_PANEL)
        cwin_id = canvas.create_window((0, 0), window=rows_fr, anchor="nw")
        rows_fr.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cwin_id, width=e.width))

        edit_rows = []

        def _recalc(_=None):
            subtotal = 0.0
            for rd in edit_rows:
                try:
                    qty  = float(rd["qty"].get() or 0)
                    cost = float(rd["cost"].get() or 0)
                    linea = qty * cost
                except Exception:
                    linea = 0.0
                subtotal += linea
                rd["lbl_total"].config(text=f"${linea:,.2f}")
            iva   = subtotal * 0.16
            total = subtotal + iva
            lbl_subtotal.config(text=f"${subtotal:,.2f}")
            lbl_iva.config(text=f"${iva:,.2f}")
            lbl_total.config(text=f"${total:,.2f}")

        for i, it in enumerate(items):
            bg_row = "#F8F8F8" if i % 2 == 0 else "white"
            fr = tk.Frame(rows_fr, bg=bg_row,
                          highlightbackground=BORDER, highlightthickness=1)
            fr.pack(fill="x", pady=1)

            check_var = None
            if es_cotizacion:
                check_var = tk.BooleanVar(value=True)
                tk.Checkbutton(fr, variable=check_var, bg=bg_row,
                               activebackground=bg_row
                               ).pack(side="left", padx=4, pady=5)

            def _lbl(text, w, anchor="center", _fr=fr, _bg=bg_row):
                tk.Label(_fr, text=text, bg=_bg, fg=TXT_MAIN,
                         font=("Arial", 10), width=w, anchor=anchor
                         ).pack(side="left", padx=3, pady=5)

            _lbl(it["sku"] or "—",        9)
            _lbl(it["name"],              26, "w")
            _lbl(it["size_color"] or "—", 14)

            qty_var  = tk.StringVar(value=str(int(it["quantity"])))
            cost_var = tk.StringVar(value=f"{float(it['unit_cost']):.2f}")

            def _mk_entry(var, w=8, _fr=fr):
                st = "normal" if not es_aceptado else "disabled"
                e = tk.Entry(_fr, textvariable=var, font=("Arial", 10),
                             width=w, justify="center", bg="white", fg=TXT_MAIN,
                             highlightbackground=BORDER, highlightthickness=1,
                             state=st)
                e.pack(side="left", padx=3, pady=5)
                if not es_aceptado:
                    e.bind("<KeyRelease>", _recalc)
                return e

            _mk_entry(qty_var,  8)
            _mk_entry(cost_var, 12)

            linea_val = float(it["unit_cost"]) * int(it["quantity"])
            lbl_t = tk.Label(fr, text=f"${linea_val:,.2f}", bg=bg_row, fg=TXT_MAIN,
                             font=("Arial", 10, "bold"), width=12, anchor="center")
            lbl_t.pack(side="left", padx=3)

            edit_rows.append({
                "it": it, "qty": qty_var, "cost": cost_var,
                "lbl_total": lbl_t, "check_var": check_var
            })

        # ── Totales ───────────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(6, 2))

        tots = tk.Frame(win, bg=BG_PANEL)
        tots.pack(fill="x", padx=16, pady=(0, 4))

        def _tot_row(label, bold=False):
            r = tk.Frame(tots, bg=BG_PANEL)
            r.pack(fill="x")
            font_l = ("Arial", 11, "bold") if bold else ("Arial", 11)
            font_v = ("Arial", 12, "bold") if bold else ("Arial", 11)
            fg_v   = TXT_MAIN if bold else TXT_GRAY
            tk.Label(r, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=font_l, anchor="e", width=22).pack(side="left")
            lbl = tk.Label(r, text="$0.00", bg=BG_PANEL, fg=fg_v,
                           font=font_v, anchor="w", width=16)
            lbl.pack(side="left")
            return lbl

        lbl_subtotal = _tot_row("Subtotal (sin IVA):")
        lbl_iva      = _tot_row("IVA 16%:")
        lbl_total    = _tot_row("TOTAL:", bold=True)
        _recalc()   # poblar valores iniciales

        # ── Botones ───────────────────────────────────────────────────────────
        btn_fr = tk.Frame(win, bg=BG_PANEL)
        btn_fr.pack(fill="x", padx=16, pady=(2, 10))

        def _collect_items(rows):
            result = []
            for rd in rows:
                try:
                    qty  = int(float(rd["qty"].get() or 0))
                    cost = float(rd["cost"].get() or 0)
                except ValueError:
                    qty  = int(rd["it"]["quantity"])
                    cost = float(rd["it"]["unit_cost"])
                if qty <= 0:
                    continue
                it = rd["it"]
                result.append({"product_id": it["product_id"], "sku": it["sku"],
                                "name": it["name"], "size_color": it["size_color"],
                                "quantity": qty, "unit_cost": cost})
            return result

        if not es_aceptado:
            def _guardar():
                new_items = _collect_items(edit_rows)
                if not new_items:
                    messagebox.showwarning("Sin productos",
                        "El pedido debe tener al menos un producto.", parent=win)
                    return
                vendor_nuevo = ent_vendor.get().strip()
                self.db.update_purchase_order(oid, new_items, vendor=vendor_nuevo)
                win.destroy()
                self._ped_reload()

            self._btn(btn_fr, "✓ Guardar", _guardar,
                      bg=SUCCESS, font_size=11
                      ).pack(side="right", ipadx=14, ipady=5)

        # ── Botón Retroceder ─────────────────────────────────────────────────
        if status_idx > 0:
            prev_status = STATUS_ORDER[status_idx - 1]
            def _retroceder():
                msg = (f"¿Regresar el pedido #{oid} a '{prev_status}'?\n"
                       "Nota: si ya se actualizó el inventario, no se revertirá.")
                if not messagebox.askyesno("Retroceder estado", msg, parent=win):
                    return
                self.db.update_purchase_order_status(oid, prev_status)
                win.destroy()
                self._ped_reload()
            self._btn(btn_fr, f"◀ {prev_status}", _retroceder,
                      bg=TXT_GRAY, font_size=11
                      ).pack(side="left", ipadx=12, ipady=5)

        # ── Botón Avanzar ────────────────────────────────────────────────────
        if status_idx < len(STATUS_ORDER) - 1:
            next_status = STATUS_ORDER[status_idx + 1]
            def _avanzar():
                new_vendor = ent_vendor.get().strip()

                if es_cotizacion:
                    # Separar productos marcados y no marcados
                    checked   = [rd for rd in edit_rows
                                 if rd["check_var"] and rd["check_var"].get()]
                    unchecked = [rd for rd in edit_rows
                                 if rd["check_var"] and not rd["check_var"].get()]
                    if not checked:
                        messagebox.showwarning("Sin productos seleccionados",
                            "Marca al menos un producto para avanzar.", parent=win)
                        return
                    checked_items = _collect_items(checked)
                    if not checked_items:
                        messagebox.showwarning("Sin productos",
                            "Los productos marcados tienen cantidad 0.", parent=win)
                        return
                    # Actualizar pedido actual con sólo los productos marcados
                    self.db.update_purchase_order(oid, checked_items, vendor=new_vendor)
                    self.db.update_purchase_order_status(oid, next_status)
                    # Crear nuevo pedido pendiente con los no marcados
                    msg_extra = ""
                    if unchecked:
                        pending_items = _collect_items(unchecked)
                        if pending_items:
                            new_oid = self.db.save_purchase_order(
                                pending_items, vendor=new_vendor)
                            msg_extra = (f"\n\nSe creó el Pedido #{new_oid} en "
                                         f"'Pedido pendiente' con "
                                         f"{len(pending_items)} producto(s) no cotizado(s).")
                    win.destroy()
                    self._ped_reload()
                    messagebox.showinfo("Estado actualizado",
                        f"Pedido #{oid} avanzó a '{next_status}'.{msg_extra}")

                elif status_norm == "En revisión":
                    if not messagebox.askyesno("Aceptar pedido",
                            f"Al aceptar el pedido #{oid} se actualizará el inventario "
                            "sumando las cantidades.\n\n¿Continuar?", parent=win):
                        return
                    items_db = self.db.get_purchase_order_items(oid)
                    for it in items_db:
                        self.db.update_stock(str(it["product_id"]), int(it["quantity"]))
                    if hasattr(self, 'data_products'):
                        self.data_products = self.db.get_products()
                    self.db.update_purchase_order_status(oid, next_status)
                    win.destroy()
                    self._ped_reload()
                    messagebox.showinfo("Pedido aceptado",
                        f"Pedido #{oid} aceptado. Inventario actualizado.")

                else:
                    # Pedido pendiente → En cotización (o cualquier otro avance simple)
                    self.db.update_purchase_order_status(oid, next_status)
                    win.destroy()
                    self._ped_reload()

            btn_color = SUCCESS if next_status == "Aceptado" else PRIMARY
            self._btn(btn_fr, f"Avanzar ▶ {next_status}", _avanzar,
                      bg=btn_color, font_size=11
                      ).pack(side="left", padx=(8, 0), ipadx=12, ipady=5)

        def _imprimir_detalle():
            items_list = [{"sku": it["sku"], "name": it["name"],
                           "size_color": it["size_color"],
                           "quantity": it["quantity"],
                           "unit_cost": it["unit_cost"]}
                          for it in items]
            self._ped_dialogo_imprimir(items_list, oid,
                                       vendor_name=ent_vendor.get().strip(),
                                       parent=win)

        self._btn(btn_fr, "Imprimir", _imprimir_detalle, bg=TXT_GRAY, font_size=11
                  ).pack(side="right", padx=(0, 6), ipadx=12, ipady=5)
        self._btn(btn_fr, "Cerrar", win.destroy, bg="#888888", font_size=11
                  ).pack(side="right", padx=(0, 8), ipadx=14, ipady=5)

    def _ped_apply_status(self):
        # Kept for backward compatibility — state changes now happen in the detail window
        pass

    def _ped_modificar(self):
        sel = self.tree_pedidos.selection()
        if not sel:
            return
        oid   = int(self.tree_pedidos.item(sel[0], "text"))
        items = self.db.get_purchase_order_items(oid)
        if not items:
            return

        # Cargar items en el carrito
        self._pedido_carrito = {}
        self._editing_purchase_order_id = oid
        prods = self.db.get_products()
        for it in items:
            pid = str(it["product_id"])
            qty = int(it["quantity"])
            if pid in prods:
                item_data = prods[pid]
            else:
                # Reconstruir datos mínimos desde el pedido
                item_data = [it["sku"], "", it["name"], "", "", it["size_color"],
                             "", "", 0, float(it["unit_cost"]), 0.0, 1, 3]
            self._pedido_carrito[pid] = {'item': item_data, 'qty': qty}

        self.opcion_inventario()

    def _ped_imprimir_sel(self):
        sel = self.tree_pedidos.selection()
        if not sel:
            return
        if not _FPDF:
            messagebox.showerror("PDF no disponible",
                                 "Instala fpdf2:\n  pip install fpdf2")
            return
        oid   = int(self.tree_pedidos.item(sel[0], "text"))
        vals  = self.tree_pedidos.item(sel[0], "values")
        vendor = vals[2] if vals[2] != "—" else ""
        items = self.db.get_purchase_order_items(oid)
        items_list = [{"sku": it["sku"], "name": it["name"],
                       "size_color": it["size_color"],
                       "quantity": it["quantity"],
                       "unit_cost": it["unit_cost"]}
                      for it in items]
        self._ped_dialogo_imprimir(items_list, oid, vendor)

    def _ped_dialogo_imprimir(self, items_list, oid, vendor_name="", parent=None):
        """Muestra diálogo para elegir imprimir con o sin costo."""
        sw, sh = self.screen_width, self.screen_height
        dlg = tk.Toplevel(self.root)
        dlg.title("Imprimir pedido")
        dlg.configure(bg=BG_PANEL)
        dlg.resizable(False, False)
        ww, wh = 320, 160
        dlg.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        if parent:
            dlg.transient(parent)
        dlg.grab_set()

        tk.Frame(dlg, bg=PRIMARY, height=4).pack(fill="x")
        tk.Label(dlg, text=f"Imprimir Pedido #{oid}",
                 bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(14, 4))
        tk.Label(dlg, text="¿Incluir precios en el PDF?",
                 bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(pady=(0, 12))

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack()

        def _imprimir(show_cost):
            dlg.destroy()
            try:
                self._generar_pdf_pedido(items_list, pedido_id=oid,
                                         vendor_name=vendor_name,
                                         show_cost=show_cost)
            except Exception as e:
                messagebox.showerror("Error al generar PDF", str(e))

        self._btn(btn_row, "Con precio", lambda: _imprimir(True),
                  bg=PRIMARY, font_size=11
                  ).pack(side="left", padx=8, ipadx=10, ipady=6)
        self._btn(btn_row, "Sin precio", lambda: _imprimir(False),
                  bg=TXT_GRAY, font_size=11
                  ).pack(side="left", padx=8, ipadx=10, ipady=6)

    def _ped_eliminar(self):
        sel = self.tree_pedidos.selection()
        if not sel:
            return
        oid = int(self.tree_pedidos.item(sel[0], "text"))
        if not messagebox.askyesno("Eliminar pedido",
                                   f"¿Eliminar el pedido #{oid}?\nEsta acción no se puede deshacer."):
            return
        self.db.delete_purchase_order(oid)
        self._ped_reload()
        for b in (self._ped_btn_aplicar, self._ped_btn_modificar,
                  self._ped_btn_imprimir, self._ped_btn_eliminar):
            b.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # RENTAS
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_rentas(self):
        self._current_screen = self.opcion_rentas
        sw, sh = self.screen_width, self.screen_height
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self.frame_rentas = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_rentas.place(x=int(sw * 0.1), y=0, width=pw, height=sh)
        self._header(self.frame_rentas, "Renta de Productos",
                     subtitle="Gestión de productos en renta y activas")

        cont_y = hh + int(sh * 0.015)
        lx     = int(pw * 0.015)
        bar_h  = int(sh * 0.07)
        bar_y  = sh - bar_h - int(sh * 0.01)

        # ── Notebook: Productos / Rentas activas / Historial ─────────────────
        nb_style = ttk.Style()
        nb_style.configure("RN.TNotebook",       background=BG_MAIN, borderwidth=0)
        nb_style.configure("RN.TNotebook.Tab",
                           background=BG_SIDEBAR, foreground=TXT_LIGHT,
                           font=("Arial", 10, "bold"), padding=(12, 5))
        nb_style.map("RN.TNotebook.Tab",
                     background=[("selected", PRIMARY)],
                     foreground=[("selected", "white")])

        nb = ttk.Notebook(self.frame_rentas, style="RN.TNotebook")
        nb.place(x=lx, y=cont_y, width=pw - lx * 2,
                 height=bar_y - cont_y - int(sh * 0.01))

        # ── Tab 1: Catálogo de productos en renta ─────────────────────────────
        tab_cat = tk.Frame(nb, bg=BG_PANEL)
        nb.add(tab_cat, text="  Catálogo  ")

        cat_cols = ("#", "Producto", "Tall/Color", "Disponibles",
                    "Depósito", "$/día <7d", "$/día 7-14d", "$/día 15-29d", "$/día ≥30d")
        cat_cws  = [int((pw - lx*2) * w)
                    for w in (0.04, 0.24, 0.12, 0.09, 0.10, 0.09, 0.09, 0.09, 0.09)]
        self.tree_rp = ttk.Treeview(tab_cat, columns=cat_cols, show="headings")
        for col, cw in zip(cat_cols, cat_cws):
            self.tree_rp.column(col, anchor="center", width=cw, minwidth=20)
            self.tree_rp.heading(col, text=col)
        self.tree_rp.pack(fill="both", expand=True, padx=6, pady=6)
        self._tag_rows(self.tree_rp)
        self.tree_rp.tag_configure("disponible", foreground=SUCCESS)
        self.tree_rp.tag_configure("agotado",    foreground=DANGER)
        self.tree_rp.tag_configure("parcial",    foreground=WARNING)
        self.tree_rp.bind("<Double-Button-1>",
                          lambda e: self._renta_nueva_desde_catalogo())

        # ── Tab 2: Rentas activas ─────────────────────────────────────────────
        tab_act = tk.Frame(nb, bg=BG_PANEL)
        nb.add(tab_act, text="  Activas  ")

        act_cols = ("#", "Producto", "Cliente", "Tel.", "Salida",
                    "Días activa", "Depósito")
        act_cws  = [int((pw - lx*2) * w)
                    for w in (0.05, 0.22, 0.18, 0.12, 0.11, 0.11, 0.12)]
        self.tree_ra = ttk.Treeview(tab_act, columns=act_cols, show="headings")
        for col, cw in zip(act_cols, act_cws):
            self.tree_ra.column(col, anchor="center", width=cw, minwidth=20)
            self.tree_ra.heading(col, text=col)
        self.tree_ra.pack(fill="both", expand=True, padx=6, pady=6)
        self._tag_rows(self.tree_ra)
        self.tree_ra.tag_configure("vencida", foreground=DANGER)
        self.tree_ra.tag_configure("activa",  foreground=SUCCESS)
        self.tree_ra.bind("<Double-Button-1>",
                          lambda e: self._renta_devolucion())

        # ── Tab 3: Historial ──────────────────────────────────────────────────
        tab_his = tk.Frame(nb, bg=BG_PANEL)
        nb.add(tab_his, text="  Historial  ")

        his_cols = ("#", "Producto", "Cliente", "Salida", "Devuelto",
                    "Tarifa", "Depósito", "Renta", "Devuelto $")
        his_cws  = [int((pw - lx*2) * w)
                    for w in (0.04, 0.18, 0.14, 0.09, 0.09, 0.08, 0.09, 0.09, 0.09)]
        self.tree_rh = ttk.Treeview(tab_his, columns=his_cols, show="headings")
        for col, cw in zip(his_cols, his_cws):
            self.tree_rh.column(col, anchor="center", width=cw, minwidth=20)
            self.tree_rh.heading(col, text=col)
        self.tree_rh.pack(fill="both", expand=True, padx=6, pady=6)
        self._tag_rows(self.tree_rh)

        # ── Barra de acciones ─────────────────────────────────────────────────
        bar = tk.Frame(self.frame_rentas, bg=BG_PANEL,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.place(x=lx, y=bar_y, width=pw - lx * 2, height=bar_h)

        es_ceo = (self.prioridad_usuario == 0)
        if es_ceo:
            self._btn(bar, "＋ Agregar producto",
                      self._renta_agregar_producto,
                      bg=SUCCESS, font_size=11
                      ).pack(side="left", padx=(12, 6), ipady=4)
        self._btn(bar, "✎ Editar tarifas",
                  self._renta_editar_producto,
                  bg=WARNING, font_size=11
                  ).pack(side="left", padx=(12 if not es_ceo else 0, 6), ipady=4)
        if es_ceo:
            self._btn(bar, "✕ Eliminar",
                      self._renta_eliminar_producto,
                      bg=DANGER, font_size=11
                      ).pack(side="left", padx=(0, 18), ipady=4)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", pady=6)

        self._btn(bar, "📋 Nueva renta",
                  self._renta_nueva_desde_catalogo,
                  bg=PRIMARY, font_size=11
                  ).pack(side="left", padx=(18, 6), ipady=4)
        self._btn(bar, "↩ Registrar devolución",
                  self._renta_devolucion,
                  bg=BG_SIDEBAR, font_size=11
                  ).pack(side="left", padx=(0, 6), ipady=4)
        self._btn(bar, "🖨 Imprimir renta",
                  self._renta_imprimir,
                  bg=TXT_GRAY, font_size=11
                  ).pack(side="left", padx=(6, 0), ipady=4)

        self._renta_nb = nb
        self._renta_reload()

    # ── Helpers de recarga ────────────────────────────────────────────────────
    def _renta_reload(self):
        self._renta_reload_catalogo()
        self._renta_reload_activas()
        self._renta_reload_historial()

    def _renta_reload_catalogo(self):
        for r in self.tree_rp.get_children():
            self.tree_rp.delete(r)
        today = datetime.now().date()
        for i, rp in enumerate(self.db.get_rental_products()):
            total = int(rp["available_qty"])
            out   = int(rp["rented_out"])
            avail = total - out
            stripe = "even" if i % 2 == 0 else "odd"
            tag    = ("disponible" if avail > 0 else
                      "parcial"    if avail > 0 and out > 0 else "agotado")
            self.tree_rp.insert("", "end", text=str(rp["id"]),
                values=(rp["id"],
                        rp["name"],
                        rp["size_color"] or "—",
                        f"{avail}/{total}",
                        f"${rp['deposit']:,.2f}",
                        f"${rp['rate_daily']:,.2f}",
                        f"${rp['rate_weekly']:,.2f}",
                        f"${rp['rate_biweekly']:,.2f}",
                        f"${rp['rate_monthly']:,.2f}"),
                tags=(stripe, tag))

    def _renta_reload_activas(self):
        for r in self.tree_ra.get_children():
            self.tree_ra.delete(r)
        today = datetime.now().date()
        fmt = "%d/%m/%Y"
        for i, r in enumerate(self.db.get_rentals(status="activa")):
            try:
                d_out = datetime.strptime(r["date_out"], fmt).date()
                dias  = (today - d_out).days
            except Exception:
                dias = 0
            stripe = "even" if i % 2 == 0 else "odd"
            self.tree_ra.insert("", "end", text=str(r["id"]),
                values=(r["id"],
                        r["prod_name"],
                        r["client_name"],
                        r["client_phone"] or "—",
                        r["date_out"],
                        f"{dias} día(s)",
                        f"${r['deposit_paid']:,.2f}"),
                tags=(stripe,))

    def _renta_reload_historial(self):
        for r in self.tree_rh.get_children():
            self.tree_rh.delete(r)
        for i, r in enumerate(self.db.get_rentals(status="devuelta")):
            stripe = "even" if i % 2 == 0 else "odd"
            self.tree_rh.insert("", "end", text=str(r["id"]),
                values=(r["id"],
                        r["prod_name"],
                        r["client_name"],
                        r["date_out"],
                        r["date_returned"] or "—",
                        r["rate_type"].capitalize(),
                        f"${r['deposit_paid']:,.2f}",
                        f"${r['rental_amount']:,.2f}",
                        f"${r['balance_returned']:,.2f}"),
                tags=(stripe,))

    # ── Agregar producto al catálogo de rentas ────────────────────────────────
    def _renta_agregar_producto(self, prefill_pid=None):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Producto para renta")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.52), int(sh * 0.88)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.transient(self.root)
        win.grab_set()

        tk.Frame(win, bg=SUCCESS, height=4).pack(fill="x")
        tk.Label(win, text="Agregar producto al catálogo de rentas",
                 bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(10, 4))

        self.data_products = self.db.get_products()
        _selected_pid = {"pid": None}

        # ── Buscador ──────────────────────────────────────────────────────────
        search_fr = tk.Frame(win, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        search_fr.pack(fill="x", padx=18, pady=(0, 4))

        tk.Label(search_fr, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).pack(side="left", padx=(10, 4))
        e_search = tk.Entry(search_fr, font=("Arial", 12), relief="flat",
                            bg=BG_PANEL, fg=TXT_MAIN,
                            highlightbackground=BORDER, highlightthickness=0)
        e_search.pack(side="left", fill="x", expand=True, padx=4, ipady=5)
        e_search.focus_set()

        # ── Treeview de resultados ─────────────────────────────────────────────
        tree_fr = tk.Frame(win, bg=BG_PANEL)
        tree_fr.pack(fill="x", padx=18, pady=(0, 6))

        p_cols = ("SKU", "Producto", "Talla/Color", "Marca", "Cant.", "Precio")
        p_cws  = [int(ww * w) for w in (0.08, 0.34, 0.16, 0.14, 0.08, 0.10)]
        tree_p = ttk.Treeview(tree_fr, columns=p_cols, show="headings", height=8)
        for col, cw in zip(p_cols, p_cws):
            tree_p.column(col, anchor="center" if col != "Producto" else "w",
                          width=cw, minwidth=20)
            tree_p.heading(col, text=col)
        vsb_p = ttk.Scrollbar(tree_fr, orient="vertical", command=tree_p.yview)
        tree_p.configure(yscrollcommand=vsb_p.set)
        vsb_p.pack(side="right", fill="y")
        tree_p.pack(fill="both", expand=True)
        self._tag_rows(tree_p)

        # ── Chip de producto seleccionado ─────────────────────────────────────
        sel_chip = tk.Label(win, text="Ningún producto seleccionado",
                            bg=BG_MAIN, fg=TXT_GRAY,
                            font=("Arial", 10, "italic"),
                            anchor="w", padx=10)
        sel_chip.pack(fill="x", padx=18, pady=(0, 4))

        def _populate(term=""):
            for r in tree_p.get_children():
                tree_p.delete(r)
            term = term.lower()
            for i, (pid, p) in enumerate(self.data_products.items()):
                name = str(p[2])
                sku  = str(p[0])
                sc   = str(p[5]) if p[5] else ""
                marca = str(p[6]) if len(p) > 6 and p[6] else ""
                if term and not any(term in s.lower()
                                    for s in [name, sku, sc, marca]):
                    continue
                qty   = int(p[8]) if str(p[8]).strip() else 0
                price = float(p[10]) if p[10] else 0.0
                stripe = "even" if i % 2 == 0 else "odd"
                tree_p.insert("", "end", text=str(pid),
                    values=(sku, name, sc or "—", marca or "—",
                            qty, f"${price:,.2f}"),
                    tags=(stripe,))
            # Si hay prefill, seleccionarlo
            if prefill_pid:
                for iid in tree_p.get_children():
                    if tree_p.item(iid, "text") == str(prefill_pid):
                        tree_p.selection_set(iid)
                        tree_p.see(iid)
                        _on_select()
                        break

        def _on_search(*_):
            _populate(e_search.get())

        def _on_select(*_):
            sel = tree_p.selection()
            if not sel:
                return
            pid = tree_p.item(sel[0], "text")
            _selected_pid["pid"] = pid
            p   = self.data_products.get(pid)
            if p:
                name = str(p[2])
                sc   = f" ({p[5]})" if p[5] else ""
                sel_chip.config(
                    text=f"✓  {name}{sc}",
                    bg="#DCFCE7", fg="#15803D",
                    font=("Arial", 10, "bold"))

        e_search.bind("<KeyRelease>", _on_search)
        tree_p.bind("<<TreeviewSelect>>", _on_select)
        _populate()

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=4)
        tk.Label(win, text="Tarifas y depósito", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=20)

        fields_data = [
            ("Unidades disponibles para renta", "qty",      "1"),
            ("Depósito ($)",                    "deposit",  ""),
            ("$/día  si renta < 7 días",          "daily",    ""),
            ("$/día  si renta 7–14 días",        "weekly",   ""),
            ("$/día  si renta 15–29 días",       "biweekly", ""),
            ("$/día  si renta ≥ 30 días",        "monthly",  ""),
        ]
        entries = {}
        for lbl, key, default in fields_data:
            rf = tk.Frame(win, bg=BG_PANEL)
            rf.pack(fill="x", padx=20, pady=2)
            tk.Label(rf, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10), width=28, anchor="w").pack(side="left")
            e = tk.Entry(rf, font=("Arial", 11), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER,
                         highlightthickness=1)
            e.insert(0, default)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            entries[key] = e

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=3)

        def _guardar():
            pid = _selected_pid["pid"]
            if not pid:
                err_lbl.config(text="Selecciona un producto de la lista.")
                return
            p = self.data_products.get(pid)
            if not p:
                err_lbl.config(text="Producto no encontrado.")
                return
            try:
                qty      = int(entries["qty"].get()       or 1)
                deposit  = float(entries["deposit"].get()  or 0)
                daily    = float(entries["daily"].get()    or 0)
                weekly   = float(entries["weekly"].get()   or 0)
                biweekly = float(entries["biweekly"].get() or 0)
                monthly  = float(entries["monthly"].get()  or 0)
            except ValueError:
                err_lbl.config(text="Revisa los valores numéricos.")
                return
            # Verificar stock suficiente
            stock_actual = int(p[8]) if str(p[8]).strip() else 0
            if qty > stock_actual:
                err_lbl.config(
                    text=f"Stock insuficiente. Disponibles: {stock_actual} unidad(es).")
                return
            self.db.save_rental_product(
                pid, str(p[0]), str(p[2]), str(p[5]) if p[5] else "",
                qty, deposit, daily, weekly, biweekly, monthly)
            # Descontar del inventario
            self.db.update_stock(pid, -qty)
            if hasattr(self, "data_products"):
                self.data_products = self.db.get_products()
            win.destroy()
            self._renta_reload_catalogo()

        self._btn(win, "✓ Guardar producto", _guardar,
                  bg=SUCCESS, font_size=12
                  ).pack(pady=8, ipadx=20, ipady=6)

    # ── Editar tarifas de un producto en catálogo ─────────────────────────────
    def _renta_editar_producto(self):
        sel = self.tree_rp.selection()
        if not sel:
            return
        rp_id = int(self.tree_rp.item(sel[0], "text"))
        rows  = self.db.get_rental_products()
        rp    = next((r for r in rows if r["id"] == rp_id), None)
        if not rp:
            return

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Editar producto de renta")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.36), int(sh * 0.60)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.transient(self.root)
        win.grab_set()

        tk.Frame(win, bg=WARNING, height=4).pack(fill="x")
        tk.Label(win, text=f"Editar: {rp['name']}",
                 bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 13, "bold")).pack(pady=(12, 6))

        fields_data = [
            ("Unidades disponibles", "qty",      str(rp["available_qty"])),
            ("Depósito ($)",         "deposit",  f"{rp['deposit']:.2f}"),
            ("$/día  si renta < 7 días",    "daily",    f"{rp['rate_daily']:.2f}"),
            ("$/día  si renta 7–14 días",   "weekly",   f"{rp['rate_weekly']:.2f}"),
            ("$/día  si renta 15–29 días",  "biweekly", f"{rp['rate_biweekly']:.2f}"),
            ("$/día  si renta ≥ 30 días",   "monthly",  f"{rp['rate_monthly']:.2f}"),
        ]
        entries = {}
        for lbl, key, default in fields_data:
            rf = tk.Frame(win, bg=BG_PANEL)
            rf.pack(fill="x", padx=24, pady=4)
            tk.Label(rf, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10), width=22, anchor="w").pack(side="left")
            e = tk.Entry(rf, font=("Arial", 11), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1)
            e.insert(0, default)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            entries[key] = e

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=2)

        def _guardar():
            try:
                qty      = int(entries["qty"].get()      or 1)
                deposit  = float(entries["deposit"].get() or 0)
                daily    = float(entries["daily"].get()   or 0)
                weekly   = float(entries["weekly"].get()  or 0)
                biweekly = float(entries["biweekly"].get()or 0)
                monthly  = float(entries["monthly"].get() or 0)
            except ValueError:
                err_lbl.config(text="Revisa los valores numéricos.")
                return
            self.db.save_rental_product(
                rp["product_id"], rp["sku"], rp["name"], rp["size_color"],
                qty, deposit, daily, weekly, biweekly, monthly,
                rp_id=rp_id)
            win.destroy()
            self._renta_reload_catalogo()

        self._btn(win, "✓ Guardar cambios", _guardar,
                  bg=WARNING, font_size=12
                  ).pack(pady=10, ipadx=20, ipady=6)

    # ── Eliminar producto del catálogo ────────────────────────────────────────
    def _renta_eliminar_producto(self):
        sel = self.tree_rp.selection()
        if not sel:
            return
        rp_id = int(self.tree_rp.item(sel[0], "text"))
        vals  = self.tree_rp.item(sel[0], "values")
        name  = vals[1] if len(vals) > 1 else "este producto"
        if not messagebox.askyesno("Eliminar",
                f"¿Quitar '{name}' del catálogo de rentas?\n"
                "Las rentas activas no se verán afectadas."):
            return
        self.db.delete_rental_product(rp_id)
        self._renta_reload_catalogo()

    # ── Nueva renta ───────────────────────────────────────────────────────────
    def _renta_nueva_desde_catalogo(self):
        sel = self.tree_rp.selection()
        if not sel:
            messagebox.showinfo("Selecciona un producto",
                "Selecciona un producto del catálogo primero.")
            return
        rp_id = int(self.tree_rp.item(sel[0], "text"))
        rows  = self.db.get_rental_products()
        rp    = next((r for r in rows if r["id"] == rp_id), None)
        if not rp:
            return
        avail = int(rp["available_qty"]) - int(rp["rented_out"])
        if avail <= 0:
            messagebox.showwarning("Sin disponibilidad",
                "No hay unidades disponibles de este producto.")
            return
        self._window_nueva_renta(rp)

    def _window_nueva_renta(self, rp):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title(f"Nueva renta — {rp['name']}")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.52), int(sh * 0.90)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.transient(self.root)
        win.grab_set()

        # Header
        tk.Frame(win, bg=PRIMARY, height=4).pack(fill="x")
        hdr = tk.Frame(win, bg=BG_SIDEBAR)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"  📦 {rp['name']}", bg=BG_SIDEBAR, fg=TXT_LIGHT,
                 font=("Arial", 13, "bold"), anchor="w").pack(side="left",
                 padx=10, pady=8)
        if rp["size_color"]:
            tk.Label(hdr, text=rp["size_color"], bg=BG_SIDEBAR, fg="#94A3B8",
                     font=("Arial", 10)).pack(side="left")

        # ── Sección cliente ───────────────────────────────────────────────────
        def _section(title):
            tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(8, 2))
            tk.Label(win, text=title, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10, "bold"), anchor="w"
                     ).pack(fill="x", padx=18)

        def _field_row(parent, label, width=22):
            rf = tk.Frame(parent, bg=BG_PANEL)
            rf.pack(fill="x", padx=18, pady=3)
            tk.Label(rf, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10), width=width, anchor="w").pack(side="left")
            e = tk.Entry(rf, font=("Arial", 11), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER,
                         highlightthickness=1)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            return e

        _section("DATOS DEL CLIENTE")

        # Estado del cliente seleccionado
        _cli_state = {"name": "", "phone": "", "address": "", "id_doc": ""}

        # Chip que muestra el cliente actualmente seleccionado
        cli_chip_fr = tk.Frame(win, bg=BG_MAIN,
                               highlightbackground=BORDER, highlightthickness=1)
        cli_chip_fr.pack(fill="x", padx=18, pady=(4, 6))
        cli_chip_lbl = tk.Label(cli_chip_fr,
                                text="  Sin cliente seleccionado",
                                bg=BG_MAIN, fg=TXT_GRAY,
                                font=("Arial", 11, "italic"), anchor="w")
        cli_chip_lbl.pack(side="left", padx=8, pady=8, fill="x", expand=True)

        def _set_cliente(name, phone="", address="", id_doc=""):
            _cli_state["name"]    = name
            _cli_state["phone"]   = phone
            _cli_state["address"] = address
            _cli_state["id_doc"]  = id_doc
            cli_chip_lbl.config(
                text=f"  ✓  {name}" + (f"  ·  {phone}" if phone else ""),
                bg="#DCFCE7", fg="#15803D",
                font=("Arial", 11, "bold"))
            cli_chip_fr.config(highlightbackground=SUCCESS)

        # ── Botones: Buscar / Agregar ─────────────────────────────────────────
        btn_cli = tk.Frame(win, bg=BG_PANEL)
        btn_cli.pack(fill="x", padx=18, pady=(0, 6))

        def _buscar_cliente():
            dlg = tk.Toplevel(win)
            dlg.title("Buscar cliente")
            dlg.configure(bg=BG_PANEL)
            dlg.transient(win)
            dlg.grab_set()
            dw, dh = int(sw * 0.36), int(sh * 0.60)
            dlg.geometry(f"{dw}x{dh}+{win.winfo_rootx()+(ww-dw)//2}+"
                         f"{win.winfo_rooty()+(wh-dh)//2}")

            tk.Frame(dlg, bg=PRIMARY, height=3).pack(fill="x")
            tk.Label(dlg, text="Buscar cliente", bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 13, "bold")).pack(pady=(10, 6))

            # Barra de búsqueda
            sf2 = tk.Frame(dlg, bg=BG_PANEL,
                           highlightbackground=BORDER, highlightthickness=1)
            sf2.pack(fill="x", padx=14, pady=(0, 6))
            tk.Label(sf2, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11)).pack(side="left", padx=(8, 4))
            e_srch = tk.Entry(sf2, font=("Arial", 11), relief="flat",
                              bg=BG_PANEL, fg=TXT_MAIN)
            e_srch.pack(side="left", fill="x", expand=True, padx=4, ipady=5)
            e_srch.focus_set()

            # Lista de clientes
            cli_rows = self.db.conn.execute(
                "SELECT * FROM clients ORDER BY name").fetchall()

            lb_fr = tk.Frame(dlg, bg=BG_PANEL)
            lb_fr.pack(fill="both", expand=True, padx=14, pady=(0, 6))
            lb = tk.Listbox(lb_fr, font=("Arial", 11), relief="flat",
                            bg=BG_PANEL, fg=TXT_MAIN,
                            selectbackground=PRIMARY, selectforeground="white",
                            activestyle="none", highlightthickness=0, bd=0)
            lb_sb = ttk.Scrollbar(lb_fr, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=lb_sb.set)
            lb_sb.pack(side="right", fill="y")
            lb.pack(fill="both", expand=True)

            def _fill_list(term=""):
                lb.delete(0, tk.END)
                for r in cli_rows:
                    if term.lower() in r["name"].lower() or \
                       term in (r["phone"] or ""):
                        lb.insert(tk.END, r["name"])
            _fill_list()

            def _on_search(*_):
                _fill_list(e_srch.get())
            e_srch.bind("<KeyRelease>", _on_search)

            def _seleccionar(ev=None):
                sel = lb.curselection()
                if not sel:
                    return
                name_sel = lb.get(sel[0])
                row_sel  = next((r for r in cli_rows
                                 if r["name"] == name_sel), None)
                if row_sel:
                    _set_cliente(row_sel["name"],
                                 row_sel["phone"]   or "",
                                 "",
                                 "")
                dlg.destroy()

            lb.bind("<Double-Button-1>", _seleccionar)
            self._btn(dlg, "✓ Seleccionar", _seleccionar,
                      bg=PRIMARY, font_size=12
                      ).pack(pady=(0, 10), ipadx=20, ipady=6)

        def _agregar_cliente():
            # Abrir la misma ventana de _edit_cliente con callback que setea el chip
            def _after_save():
                # Recargar la lista y tomar el cliente más reciente por nombre
                last = self.db.conn.execute(
                    "SELECT * FROM clients ORDER BY id DESC LIMIT 1").fetchone()
                if last:
                    _set_cliente(last["name"], last["phone"] or "", "", "")

            self._edit_cliente(None, _after_save)

        self._btn(btn_cli, "🔍 Buscar cliente", _buscar_cliente,
                  bg=PRIMARY, font_size=11
                  ).pack(side="left", ipadx=14, ipady=5)
        self._btn(btn_cli, "＋ Agregar cliente", _agregar_cliente,
                  bg=SUCCESS, font_size=11
                  ).pack(side="left", padx=(10, 0), ipadx=14, ipady=5)

        # Variables auxiliares para guardar (ya no son Entry, vienen del estado)
        e_client  = type("_FakeEntry", (), {
            "get": lambda self: _cli_state["name"]})()
        e_phone   = type("_FakeEntry", (), {
            "get": lambda self: _cli_state["phone"]})()
        e_address = type("_FakeEntry", (), {
            "get": lambda self: _cli_state["address"]})()
        e_id      = type("_FakeEntry", (), {
            "get": lambda self: _cli_state["id_doc"]})()
        e_client.get  = lambda: _cli_state["name"]
        e_phone.get   = lambda: _cli_state["phone"]
        e_address.get = lambda: _cli_state["address"]
        e_id.get      = lambda: _cli_state["id_doc"]

        # ── Sección fecha de salida y depósito ───────────────────────────────────
        _section("FECHA DE SALIDA Y DEPÓSITO")

        now_str = datetime.now().strftime("%d/%m/%Y")

        # Helper: wraps Entry para _show_calendar_var
        class _EntryVar:
            def __init__(self, e): self._e = e
            def get(self): return self._e.get()
            def set(self, v):
                self._e.delete(0, tk.END); self._e.insert(0, v)
        def _make_var(e): return _EntryVar(e)

        date_fr = tk.Frame(win, bg=BG_PANEL)
        date_fr.pack(fill="x", padx=18, pady=6)
        tk.Label(date_fr, text="Fecha de salida:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), width=18, anchor="w").pack(side="left")
        e_out = tk.Entry(date_fr, font=("Arial", 12), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER,
                         highlightthickness=1, width=13, justify="center")
        e_out.insert(0, now_str)
        e_out.pack(side="left", ipady=5)
        self._btn(date_fr, "▼",
                  lambda: self._show_calendar_var(_make_var(e_out), parent=win),
                  bg=PRIMARY, font_size=9).pack(side="left", padx=(4, 0))

        dep_fr = tk.Frame(win, bg=BG_PANEL)
        dep_fr.pack(fill="x", padx=18, pady=4)
        tk.Label(dep_fr, text="Depósito a cobrar ($):", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), width=22, anchor="w").pack(side="left")
        e_dep = tk.Entry(dep_fr, font=("Arial", 12, "bold"), relief="flat",
                         bg=BG_MAIN, highlightbackground=PRIMARY,
                         highlightthickness=1, width=12, justify="center")
        e_dep.insert(0, f"{rp['deposit']:.2f}")
        e_dep.pack(side="left", ipady=5)

        # Tabla informativa de tarifas
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(win, text="Tarifas (se aplican automáticamente al devolver)",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 9, "italic"),
                 anchor="w").pack(fill="x", padx=18)
        rates_info = tk.Frame(win, bg=BG_MAIN,
                              highlightbackground=BORDER, highlightthickness=1)
        rates_info.pack(fill="x", padx=18, pady=4)
        rate_defs = [
            ("< 7 días",     f"${rp['rate_daily']:,.2f}/día"),
            ("7 – 14 días",  f"${rp['rate_weekly']:,.2f}/día"),
            ("15 – 29 días", f"${rp['rate_biweekly']:,.2f}/día"),
            ("≥ 30 días",    f"${rp['rate_monthly']:,.2f}/día"),
        ]
        for periodo, tarifa in rate_defs:
            rf = tk.Frame(rates_info, bg=BG_MAIN)
            rf.pack(fill="x", padx=8, pady=2)
            tk.Label(rf, text=periodo, bg=BG_MAIN, fg=TXT_GRAY,
                     font=("Arial", 9), width=14, anchor="w").pack(side="left")
            tk.Label(rf, text=tarifa,  bg=BG_MAIN, fg=PRIMARY,
                     font=("Arial", 9, "bold"), anchor="w").pack(side="left")

        # Notas
        _section("NOTAS")
        e_notes = tk.Text(win, font=("Arial", 10), relief="flat", height=3,
                          bg=BG_MAIN, fg=TXT_MAIN,
                          highlightbackground=BORDER, highlightthickness=1)
        e_notes.pack(fill="x", padx=18, pady=4)

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=2)

        def _guardar_renta():
            client = e_client.get().strip()
            phone  = e_phone.get().strip()
            addr   = e_address.get().strip()
            cid    = e_id.get().strip()
            d_out  = e_out.get().strip()
            notes  = e_notes.get("1.0", tk.END).strip()
            try:
                dep = float(e_dep.get() or 0)
            except ValueError:
                dep = 0.0

            if not client:
                err_lbl.config(text="El nombre del cliente es obligatorio.")
                return
            if not d_out:
                err_lbl.config(text="Ingresa la fecha de salida.")
                return
            try:
                datetime.strptime(d_out, "%d/%m/%Y")
            except Exception:
                err_lbl.config(text="Formato de fecha: dd/mm/aaaa")
                return

            self.db.save_rental(
                rp["id"], client, phone, addr, cid,
                d_out, "", "automatica", dep,
                vendor=getattr(self, "usuario", ""),
                notes=notes)
            win.destroy()
            self._renta_reload()
            self._renta_nb.select(1)   # ir a tab Activas

        self._btn(win, "✓ Registrar renta", _guardar_renta,
                  bg=PRIMARY, font_size=12
                  ).pack(pady=(4, 10), ipadx=24, ipady=7)

    # ── Registrar devolución ──────────────────────────────────────────────────
    def _renta_devolucion(self):
        sel = self.tree_ra.selection()
        if not sel:
            messagebox.showinfo("Selecciona una renta",
                "Selecciona una renta activa de la lista.")
            return
        rid = int(self.tree_ra.item(sel[0], "text"))
        rows = self.db.get_rentals(status="activa")
        r = next((x for x in rows if x["id"] == rid), None)
        if not r:
            return
        self._window_devolucion(r)

    def _window_devolucion(self, r):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title(f"Devolución — {r['prod_name']}")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.46), int(sh * 0.82)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.transient(self.root)
        win.grab_set()

        # ── Encabezado ────────────────────────────────────────────────────────
        tk.Frame(win, bg=BG_SIDEBAR, height=4).pack(fill="x")
        hdr = tk.Frame(win, bg=BG_SIDEBAR)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  ↩  Registrar Devolución",
                 bg=BG_SIDEBAR, fg=TXT_LIGHT,
                 font=("Arial", 13, "bold"), anchor="w"
                 ).pack(side="left", padx=10, pady=8)

        # ── Info del producto y cliente ───────────────────────────────────────
        info = tk.Frame(win, bg=BG_MAIN,
                        highlightbackground=BORDER, highlightthickness=1)
        info.pack(fill="x", padx=16, pady=8)
        info_data = [
            ("Producto",        r["prod_name"]),
            ("Cliente",         r["client_name"]),
            ("Teléfono",        r["client_phone"] or "—"),
            ("Fecha de salida", r["date_out"]),
            ("Depósito pagado", f"${r['deposit_paid']:,.2f}"),
        ]
        for i, (lbl, val) in enumerate(info_data):
            bg_i = BG_MAIN if i % 2 == 0 else "#F1F5F9"
            row_ = tk.Frame(info, bg=bg_i)
            row_.pack(fill="x", padx=0)
            tk.Label(row_, text=f"  {lbl}:", bg=bg_i, fg=TXT_GRAY,
                     font=("Arial", 9), width=18, anchor="w"
                     ).pack(side="left", pady=4)
            tk.Label(row_, text=val, bg=bg_i, fg=TXT_MAIN,
                     font=("Arial", 9, "bold"), anchor="w"
                     ).pack(side="left", pady=4)

        # ── Fecha de devolución ───────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(2, 6))
        df = tk.Frame(win, bg=BG_PANEL)
        df.pack(fill="x", padx=16, pady=4)
        tk.Label(df, text="Fecha de devolución:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=22, anchor="w").pack(side="left")
        now_str = datetime.now().strftime("%d/%m/%Y")
        e_dev = tk.Entry(df, font=("Arial", 12, "bold"), relief="flat",
                         bg=BG_MAIN, highlightbackground=PRIMARY,
                         highlightthickness=1, width=13, justify="center")
        e_dev.insert(0, now_str)
        e_dev.pack(side="left", ipady=5)

        class _DEVar:
            def __init__(self, e, cb): self._e = e; self._cb = cb
            def get(self): return self._e.get()
            def set(self, v):
                self._e.delete(0, tk.END); self._e.insert(0, v); self._cb()

        self._btn(df, "▼",
                  lambda: self._show_calendar_var(_DEVar(e_dev, lambda: _calc()),
                                                  parent=win),
                  bg=PRIMARY, font_size=9).pack(side="left", padx=(4, 0))

        # ── Tabla de tarifas con la aplicable resaltada ───────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(win, text="Cálculo de tarifas según días rentado",
                 bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=16)

        tbl_fr = tk.Frame(win, bg=BG_PANEL)
        tbl_fr.pack(fill="x", padx=16, pady=4)

        # Encabezados de tabla
        HDR_BG = BG_SIDEBAR
        for col, txt, w in [("periodo", "Período",    14),
                             ("tarifa",  "Tarifa",     14),
                             ("unids",   "Unidades",   10),
                             ("total",   "Total",      14),
                             ("saldo",   "Dev. depós.", 14)]:
            tk.Label(tbl_fr, text=txt, bg=HDR_BG, fg="white",
                     font=("Arial", 9, "bold"), width=w, anchor="center",
                     pady=4).grid(row=0, column=list(
                         ["periodo","tarifa","unids","total","saldo"]
                     ).index(col), padx=1, pady=1, sticky="nsew")

        # Referencias a labels de filas para actualizarlas
        _row_labels = []   # list of (lbl_periodo, lbl_tarifa, lbl_unids, lbl_total, lbl_saldo, frame)

        RATE_DEFS = [
            ("< 7 días",     "Diaria",    r["rate_daily"],    "días",  1),
            ("7 – 14 días",  "Semanal",   r["rate_weekly"],   "sem.",  7),
            ("15 – 29 días", "Quincenal", r["rate_biweekly"], "quin.", 15),
            ("≥ 30 días",    "Mensual",   r["rate_monthly"],  "mes.",  30),
        ]
        for row_i, (periodo, nombre, rate_val, unid_lbl, period_days) in enumerate(RATE_DEFS):
            row_fr = [None]  # mutable ref
            labels = []
            for col_i, (txt, w) in enumerate([
                    (periodo, 14), (f"${rate_val:,.2f}/{unid_lbl}", 14),
                    ("—", 10), ("—", 14), ("—", 14)]):
                lbl = tk.Label(tbl_fr, text=txt, bg=BG_PANEL, fg=TXT_MAIN,
                               font=("Arial", 9), width=w, anchor="center",
                               pady=3)
                lbl.grid(row=row_i + 1, column=col_i, padx=1, pady=1, sticky="nsew")
                labels.append(lbl)
            _row_labels.append((labels, rate_val, period_days, unid_lbl))

        # ── Resumen final ─────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(8, 4))
        res_fr = tk.Frame(win, bg="#EFF6FF",
                          highlightbackground=PRIMARY, highlightthickness=1)
        res_fr.pack(fill="x", padx=16, pady=4)

        lbl_dias_res  = tk.Label(res_fr, text="Días rentado: —",
                                 bg="#EFF6FF", fg=TXT_MAIN, font=("Arial", 10))
        lbl_dias_res.grid(row=0, column=0, padx=14, pady=6, sticky="w")
        lbl_tarifa_ap = tk.Label(res_fr, text="Tarifa aplicada: —",
                                 bg="#EFF6FF", fg=PRIMARY, font=("Arial", 10, "bold"))
        lbl_tarifa_ap.grid(row=0, column=1, padx=14, pady=6, sticky="w")
        lbl_monto     = tk.Label(res_fr, text="Monto renta: —",
                                 bg="#EFF6FF", fg=DANGER, font=("Arial", 11, "bold"))
        lbl_monto.grid(row=1, column=0, padx=14, pady=2, sticky="w")
        lbl_devolver  = tk.Label(res_fr, text="A devolver: —",
                                 bg="#EFF6FF", fg=SUCCESS, font=("Arial", 13, "bold"))
        lbl_devolver.grid(row=1, column=1, padx=14, pady=2, sticky="w")

        _calc_result = {"rental_amount": 0.0, "balance": 0.0,
                        "days": 0, "tarifa_name": ""}

        def _monto_para_dias(days):
            """días × tarifa del tramo correspondiente."""
            d1 = float(r["rate_daily"])
            d2 = float(r["rate_weekly"])
            d3 = float(r["rate_biweekly"])
            d4 = float(r["rate_monthly"])
            if days < 7:
                return days * d1, "< 7 días",   0, f"{days} días × ${d1:,.2f}/día"
            elif days < 15:
                return days * d2, "7–14 días",  1, f"{days} días × ${d2:,.2f}/día"
            elif days < 30:
                return days * d3, "15–29 días", 2, f"{days} días × ${d3:,.2f}/día"
            else:
                return days * d4, "≥ 30 días",  3, f"{days} días × ${d4:,.2f}/día"

        def _calc(_=None):
            fmt2 = "%d/%m/%Y"
            try:
                d1   = datetime.strptime(r["date_out"].strip(), fmt2)
                d2   = datetime.strptime(e_dev.get().strip(), fmt2)
                days = max((d2 - d1).days, 0)
            except Exception:
                return

            rental_amount, tarifa_name, aplicada_idx, desglose = _monto_para_dias(days)
            dep   = float(r["deposit_paid"])
            saldo = dep - rental_amount

            # Actualizar filas de la tabla
            for i, (labels, rate_val, period_days, unid_lbl) in enumerate(_row_labels):
                is_ap  = (i == aplicada_idx)
                bg_row = "#DCFCE7" if is_ap else BG_PANEL
                weight = "bold"    if is_ap else "normal"
                marker = "✓ " if is_ap else ""

                for lbl in labels:
                    lbl.config(bg=bg_row, font=("Arial", 9, weight))

                if is_ap:
                    labels[2].config(text=desglose)
                    labels[3].config(text=f"${rental_amount:,.2f}", fg="#15803D")
                    labels[4].config(text=f"${max(saldo,0):,.2f}",
                                     fg=SUCCESS if saldo >= 0 else DANGER)
                else:
                    labels[2].config(text="—")
                    labels[3].config(text=f"${rate_val:,.2f}", fg=TXT_GRAY)
                    labels[4].config(text="—", fg=TXT_GRAY)

                labels[0].config(text=marker + RATE_DEFS[i][0])

            _calc_result["rental_amount"] = rental_amount
            _calc_result["balance"]       = saldo
            _calc_result["days"]          = days
            _calc_result["tarifa_name"]   = tarifa_name

            lbl_dias_res.config(text=f"Días rentado: {days}")
            lbl_tarifa_ap.config(text=f"Tarifa aplicada: {tarifa_name}")
            lbl_monto.config(text=f"Monto renta: ${rental_amount:,.2f}")
            lbl_devolver.config(
                text=f"A devolver: ${max(saldo,0):,.2f}",
                fg=SUCCESS if saldo >= 0 else DANGER)

        e_dev.bind("<FocusOut>",   _calc)
        e_dev.bind("<KeyRelease>", _calc)
        _calc()

        # ── Notas y botón ─────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(6, 2))
        tk.Label(win, text="Notas de devolución:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9)).pack(anchor="w", padx=16)
        e_notes = tk.Text(win, font=("Arial", 10), relief="flat", height=2,
                          bg=BG_MAIN, fg=TXT_MAIN,
                          highlightbackground=BORDER, highlightthickness=1)
        e_notes.pack(fill="x", padx=16, pady=4)

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=2)

        def _confirmar():
            date_dev = e_dev.get().strip()
            if not date_dev:
                err_lbl.config(text="Ingresa la fecha de devolución.")
                return
            try:
                datetime.strptime(date_dev, "%d/%m/%Y")
            except Exception:
                err_lbl.config(text="Formato: dd/mm/aaaa")
                return
            ra  = _calc_result["rental_amount"]
            bal = max(_calc_result["balance"], 0)
            days = _calc_result["days"]
            tname = _calc_result["tarifa_name"]
            if not messagebox.askyesno(
                    "Confirmar devolución",
                    f"Días rentado: {days}\n"
                    f"Tarifa aplicada: {tname}\n"
                    f"Monto de renta: ${ra:,.2f}\n"
                    f"Depósito cobrado: ${r['deposit_paid']:,.2f}\n"
                    f"Saldo a devolver al cliente: ${bal:,.2f}\n\n"
                    "¿Confirmar devolución?",
                    parent=win):
                return
            self.db.return_rental(r["id"], date_dev, ra, bal)
            win.destroy()
            self._renta_reload()
            self._renta_nb.select(2)

        self._btn(win, "✓ Confirmar devolución", _confirmar,
                  bg=SUCCESS, font_size=12
                  ).pack(pady=(4, 12), ipadx=20, ipady=7)

    # ── Imprimir información de renta ────────────────────────────────────────
    def _renta_imprimir(self):
        """Imprime la info de la renta seleccionada en Activas o Historial."""
        rid = None
        # Intentar desde tab activas primero, luego historial
        for tree in (self.tree_ra, self.tree_rh):
            sel = tree.selection()
            if sel:
                rid = int(tree.item(sel[0], "text"))
                break
        if rid is None:
            messagebox.showinfo("Selecciona una renta",
                "Selecciona una renta de la lista Activas o Historial.")
            return
        if not _FPDF:
            messagebox.showerror("PDF no disponible",
                                 "Instala fpdf2:\n  pip install fpdf2")
            return
        # Buscar en activas y historial
        all_rentals = self.db.get_rentals()
        r = next((x for x in all_rentals if x["id"] == rid), None)
        if not r:
            return
        try:
            self._renta_generar_pdf(r)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))

    def _renta_generar_pdf(self, r):
        # sqlite3.Row no tiene .get() — convertir a dict para acceso seguro
        r = dict(r)
        sf  = self._safe_pdf_str
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"renta_{r['id']}_{ts}.pdf"

        # ── Paleta ────────────────────────────────────────────────────────────
        C_DARK  = (15,  23,  42)
        C_GRAY  = (100, 116, 139)
        C_GREEN = (5,   150, 105)
        C_RED   = (220, 38,  38)
        C_BLUE  = (37,  99,  235)
        C_HEAD  = (30,  41,  59)
        C_WHITE = (255, 255, 255)
        C_LIGHT = (248, 250, 252)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.set_margins(14, 14, 14)
        pdf.core_fonts_encoding = "windows-1252"
        pdf.add_page()
        W = 182   # ancho útil

        # ══ ENCABEZADO DEL NEGOCIO ════════════════════════════════════════════
        pdf.set_fill_color(*C_HEAD)
        pdf.rect(0, 0, 210, 26, "F")
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(14, 5)
        pdf.cell(W, 8, "ORTOPEDIA BIOMED", align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(14, 14)
        pdf.cell(W, 5, "Comprobante de Renta de Producto",
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_text_color(*C_DARK)

        # ══ INFO DE LA RENTA ═══════════════════════════════════════════════════
        def _sec(txt):
            pdf.set_fill_color(*C_HEAD)
            pdf.set_text_color(*C_WHITE)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(W, 6, f"  {txt}", fill=True,
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*C_DARK)
            pdf.ln(1)

        def _kv(label, value, bold_val=False):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*C_GRAY)
            pdf.cell(52, 5.5, sf(label + ":"))
            pdf.set_font("Helvetica", "B" if bold_val else "", 9)
            pdf.set_text_color(*C_DARK)
            pdf.cell(0, 5.5, sf(str(value)),
                     new_x="LMARGIN", new_y="NEXT")

        def _sep():
            pdf.set_draw_color(226, 232, 240)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(2)

        # Folio + fecha impresión
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*C_GRAY)
        pdf.cell(W, 5,
                 sf(f"Folio: #{r['id']}   |   "
                    f"Impreso: {datetime.now().strftime('%d/%m/%Y %H:%M')}"),
                 align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # ── Producto ──────────────────────────────────────────────────────────
        _sec("PRODUCTO")
        _kv("Nombre",     r["prod_name"])
        _kv("SKU",        r["prod_sku"] or "—")
        _kv("Talla/Color",r["prod_size"] or "—")
        pdf.ln(2)

        # ── Cliente ───────────────────────────────────────────────────────────
        _sec("DATOS DEL CLIENTE")
        _kv("Nombre",    r["client_name"])
        _kv("Teléfono",  r["client_phone"] or "—")
        _kv("Dirección", r["client_address"] or "—")
        _kv("INE / ID",  r["client_id"] or "—")
        pdf.ln(2)

        # ── Renta ─────────────────────────────────────────────────────────────
        _sec("INFORMACIÓN DE LA RENTA")
        _kv("Fecha de salida",   r["date_out"])
        _kv("Depósito cobrado",  f"${r['deposit_paid']:,.2f}", bold_val=True)
        _kv("Vendedor",          r["vendor"] or "—")
        if r.get("notes"):
            _kv("Notas",         r["notes"])
        pdf.ln(2)

        # ── Tarifas vigentes ──────────────────────────────────────────────────
        _sec("TARIFAS")
        rates_info = [
            ("Diaria (< 7 días)",       r["rate_daily"],    "por día"),
            ("Semanal (7–14 días)",      r["rate_weekly"],   "por semana"),
            ("Quincenal (15–29 días)",   r["rate_biweekly"], "por quincena"),
            ("Mensual (≥ 30 días)",      r["rate_monthly"],  "por mes"),
        ]
        for nombre, val, unidad in rates_info:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*C_GRAY)
            pdf.cell(60, 5.5, sf(nombre + ":"))
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*C_BLUE)
            pdf.cell(0, 5.5, sf(f"${val:,.2f} {unidad}"),
                     new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*C_DARK)
        pdf.ln(4)

        # ══ TABLA DÍA 1 – 60 ═══════════════════════════════════════════════════
        _sec("TABLA DE COSTOS POR DÍA (1 – 60)")

        d1 = float(r["rate_daily"])     # < 7 días
        d2 = float(r["rate_weekly"])    # 7–14 días
        d3 = float(r["rate_biweekly"])  # 15–29 días
        d4 = float(r["rate_monthly"])   # ≥ 30 días

        def _rate_for(days):
            if days < 7:   return d1, f"${d1:,.2f}/día  (< 7 días)"
            elif days < 15: return d2, f"${d2:,.2f}/día  (7–14 días)"
            elif days < 30: return d3, f"${d3:,.2f}/día  (15–29 días)"
            else:           return d4, f"${d4:,.2f}/día  (≥ 30 días)"

        # Encabezados
        TW = [14, 52, 52, 64]   # suma = 182
        hdrs = ["Día", "Tarifa diaria", "Monto renta", "A devolver al cliente"]
        pdf.set_fill_color(*C_HEAD)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        for h, cw in zip(hdrs, TW):
            pdf.cell(cw, 6, sf(h), border=0, fill=True, align="C")
        pdf.ln()

        dep = float(r["deposit_paid"])
        pdf.set_text_color(*C_DARK)
        prev_rate = None

        for day in range(1, 61):
            rate, rate_lbl = _rate_for(day)
            monto = day * rate
            devol = max(dep - monto, 0.0)

            cambio = (rate != prev_rate)
            bg = (219, 234, 254) if cambio else (
                 (248, 250, 252) if day % 2 == 0 else (255, 255, 255))
            pdf.set_fill_color(*bg)
            pdf.set_font("Helvetica", "B" if cambio else "", 8)

            pdf.set_text_color(*C_DARK)
            pdf.cell(TW[0], 5.5, str(day), border=0, fill=True, align="C")

            pdf.set_text_color(37, 99, 235) if cambio else pdf.set_text_color(*C_GRAY)
            pdf.cell(TW[1], 5.5, sf(rate_lbl), border=0, fill=True, align="C")

            pdf.set_text_color(*C_RED)
            pdf.cell(TW[2], 5.5, sf(f"${monto:,.2f}"), border=0, fill=True, align="R")

            if devol > 0:
                pdf.set_text_color(5, 150, 105)
                pdf.cell(TW[3], 5.5, sf(f"${devol:,.2f}"), border=0, fill=True, align="R")
            else:
                pdf.set_text_color(*C_RED)
                pdf.cell(TW[3], 5.5, "Sin saldo", border=0, fill=True, align="R")
            pdf.ln()
            prev_rate = rate

        pdf.set_text_color(*C_DARK)
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*C_GRAY)
        pdf.cell(W, 5,
                 "Las filas en azul marcan cambio de tarifa. "
                 "'Sin saldo': el depósito fue consumido.",
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.cell(W, 5,
                 sf(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} "
                    f"— Ortopedia Biomed"),
                 align="C", new_x="LMARGIN", new_y="NEXT")

        self._pdf_save_and_open(pdf, out_name)

    # ══════════════════════════════════════════════════════════════════════════
    # DESCUENTOS  (solo CEO)
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_descuentos(self):
        self._current_screen = self.opcion_descuentos
        sw, sh = self.screen_width, self.screen_height
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self.frame_descuentos = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_descuentos.place(x=int(sw * 0.1), y=0, width=pw, height=sh)
        self._header(self.frame_descuentos, "Gestión de Descuentos",
                     subtitle="Solo visible para CEO")

        RESTRICT_LBL = {0: "Efectivo y Tarjeta", 1: "Solo Tarjeta", 2: "Solo Efectivo"}
        cont_y = hh + int(sh * 0.015)
        form_w = int(pw * 0.40)
        list_x = int(pw * 0.43)
        list_w = int(pw * 0.54)

        # ── Formulario izquierdo ──────────────────────────────────────────────
        form = tk.Frame(self.frame_descuentos, bg=BG_PANEL,
                        highlightbackground=BORDER, highlightthickness=1)
        form.place(x=int(pw * 0.02), y=cont_y, width=form_w,
                   height=sh - cont_y - int(sh * 0.02))
        tk.Label(form, text="Nuevo descuento", bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 12, "bold"), anchor="w"
                 ).pack(fill="x", padx=12, pady=(10, 6))
        tk.Frame(form, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 8))

        def _lbl_entry(parent, label, default=""):
            row = tk.Frame(parent, bg=BG_PANEL)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10), anchor="w", width=18).pack(side="left")
            e = tk.Entry(row, font=("Arial", 11), relief="flat", bg=BG_MAIN)
            e.insert(0, default)
            e.pack(side="left", fill="x", expand=True, ipady=3)
            return e

        e_name       = _lbl_entry(form, "Nombre:")
        e_pct        = _lbl_entry(form, "Porcentaje (%):")
        e_date_start = _lbl_entry(form, "Inicio (doble clic):",
                                  datetime.now().strftime("%d/%m/%Y"))
        e_date_end   = _lbl_entry(form, "Fin (doble clic):")
        # Calendario emergente con doble clic
        for _ef in (e_date_start, e_date_end):
            _ef.config(cursor="hand2", bg="#EEF4FF")
            _ef.bind("<Double-Button-1>",
                     lambda ev, e=_ef: self._show_calendar(e))
        e_min        = _lbl_entry(form, "Monto mínimo $ (0=libre):", "0")
        e_max        = _lbl_entry(form, "Monto máximo $ (0=libre):", "0")

        # Categorías (multi-select) ──────────────────────────────────────────
        tk.Label(form, text="Categorías:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), anchor="w"
                 ).pack(fill="x", padx=12, pady=(4, 0))
        all_cats = sorted({str(v[4]) for v in self.db.get_products().values() if v[4]})
        cats_frame = tk.Frame(form, bg=BG_PANEL)
        cats_frame.pack(fill="x", padx=12, pady=2)
        var_todas_cat = tk.BooleanVar(value=True)
        chk_todas_c = tk.Checkbutton(cats_frame, text="TODAS", variable=var_todas_cat,
                                     bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 10),
                                     activebackground=BG_PANEL, cursor="hand2")
        chk_todas_c.pack(side="left")
        cat_vars = {}
        for c in all_cats[:8]:   # limit to 8 to avoid overflow
            v = tk.BooleanVar(value=False)
            cat_vars[c] = v
            tk.Checkbutton(cats_frame, text=c, variable=v, bg=BG_PANEL, fg=TXT_MAIN,
                           font=("Arial", 9), activebackground=BG_PANEL,
                           cursor="hand2").pack(side="left", padx=2)

        # Marcas (multi-select) ──────────────────────────────────────────────
        tk.Label(form, text="Marcas:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), anchor="w"
                 ).pack(fill="x", padx=12, pady=(4, 0))
        all_brands = sorted({str(v[6]) for v in self.db.get_products().values() if v[6]})
        brands_frame = tk.Frame(form, bg=BG_PANEL)
        brands_frame.pack(fill="x", padx=12, pady=2)
        var_todas_br = tk.BooleanVar(value=True)
        tk.Checkbutton(brands_frame, text="TODAS", variable=var_todas_br,
                       bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 10),
                       activebackground=BG_PANEL, cursor="hand2").pack(side="left")
        brand_vars = {}
        for b in all_brands[:8]:
            v = tk.BooleanVar(value=False)
            brand_vars[b] = v
            tk.Checkbutton(brands_frame, text=b, variable=v, bg=BG_PANEL, fg=TXT_MAIN,
                           font=("Arial", 9), activebackground=BG_PANEL,
                           cursor="hand2").pack(side="left", padx=2)

        # Restricciones ──────────────────────────────────────────────────────
        tk.Label(form, text="Restricciones:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10), anchor="w"
                 ).pack(fill="x", padx=12, pady=(4, 0))
        var_restr = tk.IntVar(value=0)
        restr_frame = tk.Frame(form, bg=BG_PANEL)
        restr_frame.pack(fill="x", padx=12, pady=2)
        for txt, val in [("Efectivo y Tarjeta", 0),
                          ("Solo Tarjeta", 1), ("Solo Efectivo", 2)]:
            tk.Radiobutton(restr_frame, text=txt, variable=var_restr, value=val,
                           bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 10),
                           selectcolor=BG_PANEL, activebackground=BG_PANEL,
                           cursor="hand2").pack(side="left", padx=4)

        # ── Estado de edición ─────────────────────────────────────────────────
        _edit_mode = {"id": None}   # None = nuevo, int = editando ese id

        lbl_modo = tk.Label(form, text="", bg=BG_PANEL, fg=WARNING,
                            font=("Arial", 10, "bold"))
        lbl_modo.pack(pady=(2, 0))

        lbl_form_err = tk.Label(form, text="", bg=BG_PANEL, fg=DANGER,
                                font=("Arial", 10))
        lbl_form_err.pack(pady=2)

        def _limpiar_form():
            """Resetea el formulario a modo 'Nuevo'."""
            _edit_mode["id"] = None
            lbl_modo.config(text="")
            btn_guardar.config(text="Guardar descuento",
                               bg=SUCCESS, activebackground=self._darken(SUCCESS))
            btn_cancelar.config(state="disabled", fg=TXT_GRAY)
            for e in (e_name, e_pct, e_date_end, e_min, e_max):
                e.delete(0, "end")
            e_min.insert(0, "0")
            e_max.insert(0, "0")
            e_date_start.delete(0, "end")
            e_date_start.insert(0, datetime.now().strftime("%d/%m/%Y"))
            var_todas_cat.set(True)
            var_todas_br.set(True)
            var_restr.set(0)
            for v in cat_vars.values():   v.set(False)
            for v in brand_vars.values(): v.set(False)
            lbl_form_err.config(text="")

        def _collect_fields():
            """Valida y devuelve (name, pct, cats, brands, ds, de, min_a, max_a, restr)
            o None si hay error."""
            name = e_name.get().strip()
            if not name:
                lbl_form_err.config(text="El nombre es obligatorio.")
                return None
            try:
                pct = float(e_pct.get())
                if not (0 < pct <= 100): raise ValueError
            except Exception:
                lbl_form_err.config(text="Porcentaje inválido (1–100).")
                return None
            ds = e_date_start.get().strip()
            de = e_date_end.get().strip()
            try:
                datetime.strptime(ds, "%d/%m/%Y")
                datetime.strptime(de, "%d/%m/%Y")
            except Exception:
                lbl_form_err.config(text="Fechas inválidas (DD/MM/YYYY).")
                return None
            try:
                min_a = float(e_min.get() or "0")
                max_a = float(e_max.get() or "0")
            except Exception:
                lbl_form_err.config(text="Montos deben ser números.")
                return None
            cats_str   = "TODAS" if var_todas_cat.get() else (
                ",".join(c for c, v in cat_vars.items()   if v.get()) or "TODAS")
            brands_str = "TODAS" if var_todas_br.get()  else (
                ",".join(b for b, v in brand_vars.items() if v.get()) or "TODAS")
            lbl_form_err.config(text="")
            return name, pct, cats_str, brands_str, ds, de, min_a, max_a, var_restr.get()

        def _guardar_descuento():
            fields = _collect_fields()
            if fields is None:
                return
            name, pct, cats_str, brands_str, ds, de, min_a, max_a, restr = fields
            if _edit_mode["id"] is not None:
                self.db.update_discount(_edit_mode["id"], name, pct,
                                        cats_str, brands_str, ds, de,
                                        min_a, max_a, restr)
            else:
                self.db.save_discount(name, pct, cats_str, brands_str,
                                      ds, de, min_a, max_a, restr)
            _limpiar_form()
            _reload_lists()

        btn_guardar = self._btn(form, "Guardar descuento", _guardar_descuento,
                                bg=SUCCESS, font_size=12)
        btn_guardar.pack(pady=(8, 2), ipadx=12, ipady=6)

        btn_cancelar = self._btn(form, "Cancelar edición", _limpiar_form,
                                 bg=TXT_GRAY, font_size=11)
        btn_cancelar.pack(pady=(0, 8), ipadx=10, ipady=4)
        btn_cancelar.config(state="disabled", fg=TXT_GRAY)

        # ── Listas derecha ────────────────────────────────────────────────────
        right = tk.Frame(self.frame_descuentos, bg=BG_MAIN)
        right.place(x=list_x, y=cont_y, width=list_w,
                    height=sh - cont_y - int(sh * 0.02))

        # Vigentes
        lbl_v = tk.Label(right, text="Descuentos vigentes", bg=BG_MAIN, fg=TXT_MAIN,
                         font=("Arial", 11, "bold"), anchor="w")
        lbl_v.pack(fill="x", pady=(0, 4))
        tree_cols = ("#", "Nombre", "%", "Categorías", "Marcas", "Desde", "Hasta",
                     "Min $", "Max $", "Restricción")
        cw_t = [int(list_w * f) for f in
                (0.05, 0.18, 0.06, 0.13, 0.12, 0.10, 0.10, 0.07, 0.07, 0.12)]

        def _make_tree_framed(height):
            frm = tk.Frame(right, bg=BG_MAIN)
            frm.pack(fill="x", pady=(0, 2))
            vsb = ttk.Scrollbar(frm, orient="vertical")
            vsb.pack(side="right", fill="y")
            t = ttk.Treeview(frm, columns=tree_cols, show="headings",
                             height=height, yscrollcommand=vsb.set)
            vsb.config(command=t.yview)
            for col, w in zip(tree_cols, cw_t):
                t.column(col,
                    anchor="w" if col in ("Nombre", "Categorías", "Marcas") else "center",
                    width=w)
                t.heading(col, text=col)
            self._tag_rows(t)
            t.pack(side="left", fill="x", expand=True)
            return t

        tree_vig = _make_tree_framed(8)

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", pady=8)
        tk.Label(right, text="Historial (expirados / eliminados)",
                 bg=BG_MAIN, fg=TXT_GRAY,
                 font=("Arial", 11, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
        tree_hist = _make_tree_framed(7)

        # Botones de acción
        act_row = tk.Frame(right, bg=BG_MAIN)
        act_row.pack(pady=6)
        btn_edit = self._btn(act_row, "Editar seleccionado", lambda: _editar(),
                             bg=WARNING, font_size=11)
        btn_edit.pack(side="left", ipadx=10, ipady=5, padx=(0, 8))
        btn_del = self._btn(act_row, "Eliminar seleccionado", lambda: _eliminar(),
                            bg=DANGER, font_size=11)
        btn_del.pack(side="left", ipadx=10, ipady=5)

        def _fill_tree(tree, rows):
            for row in tree.get_children():
                tree.delete(row)
            for i, r in enumerate(rows):
                rl = RESTRICT_LBL.get(int(r["restrictions"]), "—")
                min_s = f"$ {r['min_amount']:,.0f}" if r["min_amount"] else "—"
                max_s = f"$ {r['max_amount']:,.0f}" if r["max_amount"] else "—"
                tree.insert("", "end", iid=str(r["id"]),
                    values=(r["id"], r["name"], f"{r['percentage']:.1f}%",
                            r["categories"], r["brands"],
                            r["date_start"], r["date_end"],
                            min_s, max_s, rl),
                    tags=("even" if i % 2 == 0 else "odd",))

        def _reload_lists():
            today_str = datetime.now().strftime("%d/%m/%Y")
            fmt = "%d/%m/%Y"
            all_d  = self.db.get_discounts()
            vigent = []
            hist   = []
            for r in all_d:
                try:
                    de = datetime.strptime(r["date_end"], fmt)
                    cd = datetime.strptime(today_str, fmt)
                    if de >= cd and int(r["active"]) == 1:
                        vigent.append(r)
                    else:
                        hist.append(r)
                except Exception:
                    hist.append(r)
            _fill_tree(tree_vig,  vigent)
            _fill_tree(tree_hist, hist)

        def _get_selected_row():
            """Devuelve el sqlite3.Row del descuento seleccionado (vigentes o historial)."""
            sel = tree_vig.selection() or tree_hist.selection()
            if not sel:
                return None
            did = int(sel[0])
            rows = self.db.get_discounts()
            for r in rows:
                if int(r["id"]) == did:
                    return r
            return None

        def _editar():
            r = _get_selected_row()
            if r is None:
                messagebox.showwarning("Sin selección",
                    "Selecciona un descuento para editar.",
                    parent=self.frame_descuentos)
                return

            # Activar modo edición
            _edit_mode["id"] = int(r["id"])
            lbl_modo.config(text=f"Editando: #{r['id']} {r['name']}")
            btn_guardar.config(text="Actualizar descuento",
                               bg=WARNING, activebackground=self._darken(WARNING))
            btn_cancelar.config(state="normal", fg="white")

            # Rellenar campos
            e_name.delete(0, "end");       e_name.insert(0, r["name"])
            e_pct.delete(0, "end");        e_pct.insert(0, str(r["percentage"]))
            e_date_start.delete(0, "end"); e_date_start.insert(0, r["date_start"])
            e_date_end.delete(0, "end");   e_date_end.insert(0, r["date_end"])
            e_min.delete(0, "end");        e_min.insert(0, str(r["min_amount"]))
            e_max.delete(0, "end");        e_max.insert(0, str(r["max_amount"]))
            var_restr.set(int(r["restrictions"]))

            # Categorías
            cats = r["categories"]
            if cats == "TODAS":
                var_todas_cat.set(True)
                for v in cat_vars.values(): v.set(False)
            else:
                var_todas_cat.set(False)
                sel_cats = [c.strip() for c in cats.split(",")]
                for c, v in cat_vars.items(): v.set(c in sel_cats)

            # Marcas
            brands = r["brands"]
            if brands == "TODAS":
                var_todas_br.set(True)
                for v in brand_vars.values(): v.set(False)
            else:
                var_todas_br.set(False)
                sel_brands = [b.strip() for b in brands.split(",")]
                for b, v in brand_vars.items(): v.set(b in sel_brands)

            lbl_form_err.config(text="")
            # Desplazar la vista al formulario (form ya está visible a la izquierda)

        def _eliminar():
            r = _get_selected_row()
            if r is None:
                messagebox.showwarning("Sin selección",
                    "Selecciona un descuento para eliminar.",
                    parent=self.frame_descuentos)
                return
            did = int(r["id"])
            if _edit_mode["id"] == did:
                _limpiar_form()   # salir del modo edición si estamos editando éste
            if not messagebox.askyesno("Eliminar descuento",
                                       f"¿Eliminar el descuento #{did}?",
                                       parent=self.frame_descuentos):
                return
            self.db.delete_discount(did)
            _reload_lists()

        # Doble clic en cualquiera de las listas → editar
        for _t in (tree_vig, tree_hist):
            _t.bind("<Double-Button-1>", lambda _e: _editar())

        _reload_lists()

    def opcion_clientes(self):
        self._current_screen = self.opcion_clientes
        sw, sh = self.screen_width, self.screen_height
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self.frame_clientes = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_clientes.place(x=int(sw * 0.1), y=0,
                                   width=pw, height=sh)

        self._header(self.frame_clientes, "Clientes",
                     subtitle="Historial y descuentos por volumen")

        lx      = int(pw * 0.02)
        lw      = int(pw * 0.56)
        rx      = lx + lw + int(pw * 0.03)
        rw      = pw - rx - int(pw * 0.02)
        cont_y  = hh + int(sh * 0.02)

        # ── Search bar ────────────────────────────────────────────────────────
        sq_h = int(sh * 0.05)
        sf = tk.Frame(self.frame_clientes, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        sf.place(x=lx, y=cont_y, width=lw, height=sq_h)
        tk.Label(sf, text="Buscar:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11)).place(x=8, y=0, width=60, height=sq_h)
        search_var = tk.StringVar()
        tk.Entry(sf, textvariable=search_var, font=("Arial", 12),
                 relief="flat", bg=BG_PANEL, fg=TXT_MAIN
                 ).place(x=70, y=int(sq_h * 0.15), width=lw - 82, height=int(sq_h * 0.7))

        # ── Clients table ─────────────────────────────────────────────────────
        cli_y = cont_y + sq_h + int(sh * 0.01)
        cli_h = int(sh * 0.52)
        ccols = ("ID", "Nombre", "Teléfono", "Total Compras", "Descuento")
        self.tree_clientes = ttk.Treeview(self.frame_clientes,
                                           columns=ccols, show="headings", height=15)
        for col, frac in zip(ccols, (0.04, 0.22, 0.10, 0.12, 0.07)):
            w = int(pw * frac)
            self.tree_clientes.column(col,
                anchor="w" if col == "Nombre" else "center", width=w)
            self.tree_clientes.heading(col, text=col)
        self.tree_clientes.place(x=lx, y=cli_y, width=lw, height=cli_h)
        self._tag_rows(self.tree_clientes)
        self._add_scrollbar(self.frame_clientes, self.tree_clientes,
                            lx, cli_y, lw, cli_h)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_y = cli_y + cli_h + int(sh * 0.01)
        bw    = int(lw * 0.29)
        self._btn(self.frame_clientes, "+ Agregar",
                  lambda: self._edit_cliente(None, _refresh),
                  bg=SUCCESS, font_size=11
                  ).place(x=lx, y=btn_y, width=bw, height=int(sh * 0.045))
        self._btn(self.frame_clientes, "✎ Editar",
                  lambda: _editar_sel(),
                  bg=PRIMARY, font_size=11
                  ).place(x=lx + bw + 6, y=btn_y, width=bw, height=int(sh * 0.045))
        self._btn(self.frame_clientes, "✕ Eliminar",
                  lambda: _eliminar_sel(),
                  bg=DANGER, font_size=11
                  ).place(x=lx + 2 * (bw + 6), y=btn_y, width=bw, height=int(sh * 0.045))

        # ── Right: detail card ────────────────────────────────────────────────
        det_h = int(sh * 0.32)
        det   = self._card(self.frame_clientes, rx, cont_y, rw, det_h,
                           title="DETALLE DE CLIENTE")

        lh = int(sh * 0.038)
        self._cli_nombre = tk.Label(det, text="—", bg=BG_PANEL, fg=TXT_MAIN,
                                     font=("Arial", 15, "bold"), anchor="w")
        self._cli_nombre.place(x=10, y=26, width=rw - 20, height=lh)

        self._cli_id  = tk.Label(det, text="ID: —", bg=BG_PANEL, fg=TXT_GRAY,
                                  font=("Arial", 10), anchor="w")
        self._cli_id.place(x=10, y=26 + lh, width=rw // 2, height=int(sh * 0.028))

        self._cli_tel = tk.Label(det, text="Tel: —", bg=BG_PANEL, fg=TXT_GRAY,
                                  font=("Arial", 10), anchor="w")
        self._cli_tel.place(x=rw // 2, y=26 + lh, width=rw // 2, height=int(sh * 0.028))

        tot_y_d = 26 + lh + int(sh * 0.04)
        tk.Label(det, text="Total compras:", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10)).place(x=10, y=tot_y_d,
                                           width=rw // 2, height=int(sh * 0.028))
        self._cli_total = tk.Label(det, text="$ 0.00", bg=BG_PANEL, fg=SUCCESS,
                                    font=("Arial", 13, "bold"), anchor="w")
        self._cli_total.place(x=10, y=tot_y_d + int(sh * 0.028),
                               width=int(rw * 0.55), height=int(sh * 0.038))

        self._cli_badge = tk.Label(det, text="Sin descuento", bg=BORDER,
                                    fg=TXT_GRAY, font=("Arial", 11, "bold"),
                                    anchor="center")
        self._cli_badge.place(x=int(rw * 0.58), y=tot_y_d + int(sh * 0.02),
                               width=int(rw * 0.38), height=int(sh * 0.048))

        tier_y = tot_y_d + int(sh * 0.08)
        for j, (txt, col) in enumerate([(">$5k → 5%", SUCCESS),
                                         (">$10k → 10%", WARNING),
                                         (">$20k → 15%", DANGER)]):
            tk.Label(det, text=txt, bg=BG_PANEL, fg=col,
                     font=("Arial", 9, "bold")
                     ).place(x=8 + j * int(rw * 0.34), y=tier_y,
                             width=int(rw * 0.32), height=int(sh * 0.026))

        # ── Right: orders table ───────────────────────────────────────────────
        ord_y = cont_y + det_h + int(sh * 0.03)
        ord_h = sh - ord_y - int(sh * 0.02)
        tk.Label(self.frame_clientes, text="Historial de compras",
                 bg=BG_MAIN, fg=TXT_MAIN, font=("Arial", 12, "bold"), anchor="w"
                 ).place(x=rx, y=ord_y - int(sh * 0.03),
                         width=rw, height=int(sh * 0.028))
        ocols = ("Fecha", "Importe", "Pago", "Vendedor")
        self.tree_cli_orders = ttk.Treeview(self.frame_clientes,
                                             columns=ocols, show="headings", height=10)
        for col, frac in zip(ocols, (0.10, 0.10, 0.09, 0.12)):
            self.tree_cli_orders.column(col, anchor="center", width=int(pw * frac))
            self.tree_cli_orders.heading(col, text=col)
        self.tree_cli_orders.place(x=rx, y=ord_y, width=rw, height=ord_h)
        self._tag_rows(self.tree_cli_orders)
        self._add_scrollbar(self.frame_clientes, self.tree_cli_orders,
                            rx, ord_y, rw, ord_h)

        # ── Internal helpers ──────────────────────────────────────────────────
        def _load_detail(client_row):
            if not client_row:
                self._cli_nombre.config(text="—")
                self._cli_id.config(text="ID: —")
                self._cli_tel.config(text="Tel: —")
                self._cli_total.config(text="$ 0.00" if self.prioridad_usuario == 0 else "—")
                self._cli_badge.config(text="Sin descuento", bg=BORDER, fg=TXT_GRAY)
                for r in self.tree_cli_orders.get_children():
                    self.tree_cli_orders.delete(r)
                return
            cname = client_row["name"]
            total = self.db.client_total_purchases(cname)
            disc  = self._discount_for(total, cname)
            dlbl  = self._discount_label(total, cname)
            self._cli_nombre.config(text=cname)
            self._cli_id.config(text=f"ID: {client_row['id']:04d}")
            self._cli_tel.config(text=f"Tel: {client_row['phone'] or '—'}")
            self._cli_total.config(text=f"$ {total:,.2f}" if self.prioridad_usuario == 0 else "—")
            if dlbl:
                clr = ("#059669" if total == 0 else
                       DANGER if disc == 15 else
                       WARNING if disc == 10 else SUCCESS)
                self._cli_badge.config(text=dlbl, bg=clr, fg="white")
            else:
                self._cli_badge.config(text="Sin descuento", bg=BORDER, fg=TXT_GRAY)
            for r in self.tree_cli_orders.get_children():
                self.tree_cli_orders.delete(r)
            for i, o in enumerate(self.db.get_client_orders(cname)):
                self._insert_row(self.tree_cli_orders,
                    (o["date"], f"$ {o['total']:,.2f}",
                     o["payment_method"], o["vendor"]), idx=i)

        def _refresh():
            query = search_var.get().strip().lower()
            for r in self.tree_clientes.get_children():
                self.tree_clientes.delete(r)
            for i, c in enumerate(self.db.get_clients_full()):
                if query and query not in c["name"].lower() \
                        and query not in str(c["id"]) \
                        and query not in (c["phone"] or "").lower():
                    continue
                total = self.db.client_total_purchases(c["name"])
                dlbl  = self._discount_label(total, c["name"])
                total_txt = f"$ {total:,.2f}" if self.prioridad_usuario == 0 else "—"
                self._insert_row(self.tree_clientes,
                    (f"{c['id']:04d}", c["name"], c["phone"] or "—",
                     total_txt, dlbl if dlbl else "—"),
                    idx=i)
            self.data_clients = self.db.get_clients()

        def _on_select(event=None):
            sel = self.tree_clientes.selection()
            if not sel:
                _load_detail(None)
                return
            try:
                cid = int(str(self.tree_clientes.item(sel[0])["values"][0]))
            except Exception:
                return
            _load_detail(self.db.get_client_by_id(cid))

        def _editar_sel():
            sel = self.tree_clientes.selection()
            if not sel:
                return
            try:
                cid = int(str(self.tree_clientes.item(sel[0])["values"][0]))
            except Exception:
                return
            row = self.db.get_client_by_id(cid)
            if row:
                self._edit_cliente(dict(row), _refresh)

        def _eliminar_sel():
            sel = self.tree_clientes.selection()
            if not sel:
                return
            try:
                cid = int(str(self.tree_clientes.item(sel[0])["values"][0]))
            except Exception:
                return
            row = self.db.get_client_by_id(cid)
            if not row or row["name"] == "Publico General":
                return
            self.db.delete_client(cid)
            _load_detail(None)
            _refresh()

        self.tree_clientes.bind("<<TreeviewSelect>>", _on_select)
        search_var.trace_add("write", lambda *_: _refresh())
        _refresh()

    def _edit_cliente(self, row, refresh_cb):
        sw, sh = self.screen_width, self.screen_height
        is_new = row is None
        win = tk.Toplevel(self.root)
        titulo = "Editar Cliente" if not is_new else "Nuevo Cliente"
        win.title(titulo)
        win.configure(bg=BG_PANEL)
        win.grab_set()
        win.resizable(False, True)
        ww, wh = int(sw * 0.38), int(sh * 0.72)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        color = SUCCESS if is_new else PRIMARY
        tk.Frame(win, bg=color, height=4).pack(fill="x")
        tk.Label(win, text=titulo, bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(10, 4))

        # First-purchase discount banner for new clients
        if is_new:
            banner = tk.Frame(win, bg="#D1FAE5")
            banner.pack(fill="x", padx=20, pady=(0, 6))
            tk.Label(banner, text="★  Recibirá 5 % de descuento en su primera compra",
                     bg="#D1FAE5", fg="#065F46", font=("Arial", 10, "bold")
                     ).pack(pady=5)

        # ── Nombre y Teléfono ──────────────────────────────────────────────
        entries = {}
        for lbl, key in [("Nombre completo", "name"), ("Teléfono", "phone")]:
            rf = tk.Frame(win, bg=BG_PANEL)
            rf.pack(fill="x", padx=24, pady=4)
            tk.Label(rf, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=18, anchor="w").pack(side="left")
            e = tk.Entry(rf, font=("Arial", 12), relief="flat",
                         bg=BG_MAIN,
                         highlightbackground=BORDER, highlightthickness=1)
            e.pack(side="left", fill="x", expand=True, ipady=5)
            entries[key] = e

        # ── Acepta WhatsApp ────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(8, 4))
        wa_var = tk.BooleanVar(value=False)
        wf = tk.Frame(win, bg=BG_PANEL)
        wf.pack(fill="x", padx=24, pady=2)
        tk.Checkbutton(wf, text="Acepta mensajes por WhatsApp",
                       variable=wa_var, bg=BG_PANEL, fg=TXT_MAIN,
                       font=("Arial", 11), activebackground=BG_PANEL,
                       cursor="hand2").pack(side="left")

        # ── Cómo nos conoció ───────────────────────────────────────────────
        cnc_options = ["Pasé por aquí", "Recomendación",
                       "Google / Maps", "Doctor o clínica", "Redes sociales"]
        cnc_var = tk.StringVar()
        cf = tk.Frame(win, bg=BG_PANEL)
        cf.pack(fill="x", padx=24, pady=4)
        tk.Label(cf, text="¿Cómo nos conoció?", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=18, anchor="w").pack(side="left")
        ttk.Combobox(cf, textvariable=cnc_var, values=cnc_options,
                     state="readonly", font=("Arial", 11), width=22
                     ).pack(side="left", padx=4, ipady=4)

        # ── Categorías de interés ──────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(8, 4))
        tk.Label(win, text="Categorías de interés", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=24)

        cats = sorted({str(info[4]).strip()
                       for info in self.data_products.values()
                       if len(info) > 4 and info[4]})
        cat_vars = {c: tk.BooleanVar(value=False) for c in cats}
        cat_frame = tk.Frame(win, bg=BG_PANEL)
        cat_frame.pack(fill="x", padx=24, pady=4)
        for i, cat in enumerate(cats):
            tk.Checkbutton(cat_frame, text=cat, variable=cat_vars[cat],
                           bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 10),
                           activebackground=BG_PANEL, cursor="hand2",
                           wraplength=int(ww * 0.40)
                           ).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=1)

        # ── Notas ──────────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(8, 4))
        tk.Label(win, text="Notas (opcional)", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=24)
        t_notas = tk.Text(win, font=("Arial", 11), relief="flat", height=3,
                          bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1)
        t_notas.pack(fill="x", padx=24, pady=4)

        # ── Pre-fill for edit ──────────────────────────────────────────────
        if row:
            entries["name"].insert(0,  row.get("name",  "") or "")
            entries["phone"].insert(0, row.get("phone", "") or "")
            wa_var.set(bool(row.get("acepta_whatsapp", 0)))
            cnc_var.set(row.get("como_nos_conocio", "") or "")
            for c in (row.get("categoria_interes", "") or "").split(","):
                c = c.strip()
                if c in cat_vars:
                    cat_vars[c].set(True)
            t_notas.insert("1.0", row.get("notas", "") or "")

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=2)

        def _guardar():
            name  = entries["name"].get().strip()
            phone = entries["phone"].get().strip()
            if not name:
                err_lbl.config(text="El nombre es obligatorio.")
                return
            cats_sel = ",".join(c for c, v in cat_vars.items() if v.get())
            self.db.save_client(
                row["id"] if row else None,
                name, phone,
                acepta_whatsapp   = int(wa_var.get()),
                categoria_interes = cats_sel,
                como_nos_conocio  = cnc_var.get(),
                notas             = t_notas.get("1.0", tk.END).strip())
            self.data_clients = self.db.get_clients()
            win.destroy()
            refresh_cb()

        self._btn(win, "Guardar", _guardar, bg=color, font_size=13
                  ).pack(pady=14, ipadx=30, ipady=8)

    # GESTIÓN DE EMPLEADOS  (solo CEO — prioridad == 0)
    # ══════════════════════════════════════════════════════════════════════════
    NIVELES = {0: "CEO", 1: "Gerente", 2: "Vendedor", 3: "Vendedor Jr."}

    def opcion_empleados(self):
        self._current_screen = self.opcion_empleados
        sw, sh = self.screen_width, self.screen_height

        self.frame_empleados = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_empleados.place(x=int(sw * 0.1), y=0,
                                   width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self._header(self.frame_empleados, "Gestión de Usuarios",
                     subtitle="Administración exclusiva CEO")

        # Barra de herramientas
        self._btn(self.frame_empleados, "  Agregar usuario",
                  lambda: self.window_editar_empleado(),
                  bg=SUCCESS, font_size=11
                  ).place(x=int(pw * 0.60), y=hh + int(sh * 0.02),
                           width=int(pw * 0.18), height=int(sh * 0.05))
        self._btn(self.frame_empleados, "  Eliminar",
                  self._eliminar_empleado,
                  bg=DANGER, font_size=11
                  ).place(x=int(pw * 0.80), y=hh + int(sh * 0.02),
                           width=int(pw * 0.14), height=int(sh * 0.05))

        # Tabla
        cols = ("ID", "Alias", "Nombre completo", "PIN", "Nivel", "Meta ($)",
                "F. Nacimiento", "Emergencia", "Teléfono", "F. Entrada", "Estatus")
        self.tree_empleados = ttk.Treeview(self.frame_empleados,
                                           columns=cols, show="headings", height=18)
        col_w = [int(sw * w) for w in (0.02, 0.08, 0.12, 0.05, 0.07, 0.06,
                                        0.07, 0.10, 0.07, 0.07, 0.06)]
        for col, w in zip(cols, col_w):
            self.tree_empleados.column(col, anchor="center", width=w)
            self.tree_empleados.heading(col, text=col)
        ty  = hh + int(sh * 0.10)
        etw = int(pw * 0.60)
        eth = int(sh * 0.65)
        self.tree_empleados.place(x=int(pw * 0.04), y=ty, width=etw, height=eth)
        self._tag_rows(self.tree_empleados)
        self._add_scrollbar(self.frame_empleados, self.tree_empleados,
                            int(pw * 0.04), ty, etw, eth)
        self.tree_empleados.bind("<Double-Button-1>",
                                 lambda _e: self._editar_empleado_sel())

        # ── Panel derecho: registro de actividad ─────────────────────────
        rp_x = int(pw * 0.65)
        rp_w = int(pw * 0.34)
        rp_h = int(sh * 0.65)

        rp = tk.Frame(self.frame_empleados, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        rp.place(x=rp_x, y=ty, width=rp_w, height=rp_h)

        # Título
        tk.Label(rp, text="REGISTRO DE ACTIVIDAD", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9, "bold"), anchor="w"
                 ).pack(fill="x", padx=10, pady=(8, 2))
        tk.Frame(rp, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 4))

        # ── Fila de filtros ───────────────────────────────────────────────
        flt_row = tk.Frame(rp, bg=BG_PANEL)
        flt_row.pack(fill="x", padx=8, pady=(4, 4))

        # Combobox de empleado
        _all_emp_rows = self.db.get_users_full()
        _emp_names    = ["— Todos —"] + [r["username"] for r in _all_emp_rows]
        _flt_emp_var  = tk.StringVar(value="— Todos —")
        _emp_cb = ttk.Combobox(flt_row, textvariable=_flt_emp_var,
                               values=_emp_names, state="readonly",
                               width=13, font=("Arial", 9))
        _emp_cb.pack(side="left", padx=(0, 6), ipady=2)

        # Campo de fecha (doble clic = calendario)
        _act_date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        _date_e = tk.Entry(flt_row, textvariable=_act_date_var, width=10,
                           font=("Arial", 9), relief="flat",
                           bg=BG_MAIN, highlightbackground=BORDER,
                           highlightthickness=1, cursor="hand2")
        _date_e.pack(side="left", padx=(0, 4), ipady=3)
        _date_e.bind("<Double-Button-1>",
                     lambda _e: self._show_calendar(_date_e))
        tk.Label(flt_row, text="📅", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10)).pack(side="left")

        # ── Treeview ──────────────────────────────────────────────────────
        act_cols = ("Empleado", "Tipo", "Hora")
        tree_act = ttk.Treeview(rp, columns=act_cols,
                                show="headings", selectmode="browse")
        tree_act.pack(fill="both", expand=True, padx=4, pady=(2, 0))

        _ca_w = int(rp_w * 0.40)
        _ct_w = int(rp_w * 0.28)
        _ch_w = int(rp_w * 0.22)
        tree_act.column("Empleado", anchor="w",      width=_ca_w, minwidth=50)
        tree_act.column("Tipo",     anchor="center", width=_ct_w, minwidth=40)
        tree_act.column("Hora",     anchor="center", width=_ch_w, minwidth=40)
        tree_act.heading("Empleado", text="Empleado")
        tree_act.heading("Tipo",     text="Tipo")
        tree_act.heading("Hora",     text="Hora")
        self._tag_rows(tree_act)
        tree_act.tag_configure("entrada_row", foreground=SUCCESS)
        tree_act.tag_configure("salida_row",  foreground=DANGER)

        # ── Botones de acción ─────────────────────────────────────────────
        act_btns = tk.Frame(rp, bg=BG_PANEL)
        act_btns.pack(fill="x", padx=8, pady=(6, 8))

        # ── Funciones ─────────────────────────────────────────────────────
        def _reload_act():
            for _row in tree_act.get_children():
                tree_act.delete(_row)
            self._tag_rows(tree_act)
            tree_act.tag_configure("entrada_row", foreground=SUCCESS)
            tree_act.tag_configure("salida_row",  foreground=DANGER)

            emp_f  = _flt_emp_var.get()
            date_f = _act_date_var.get().strip()

            if emp_f == "— Todos —":
                _rows = self.db.conn.execute(
                    "SELECT id, username, tipo, timestamp FROM checadas"
                    " WHERE date=? ORDER BY id ASC",
                    (date_f,)).fetchall()
            else:
                _rows = self.db.conn.execute(
                    "SELECT id, username, tipo, timestamp FROM checadas"
                    " WHERE date=? AND username=? ORDER BY id ASC",
                    (date_f, emp_f)).fetchall()

            for _i, _r in enumerate(_rows):
                _tipo_lbl = "Entrada" if _r["tipo"] == "entrada" else "Salida"
                _ts       = str(_r["timestamp"])
                _hora     = _ts[:5] if len(_ts) >= 5 else _ts
                _base_tag = "even" if _i % 2 == 0 else "odd"
                _clr_tag  = ("entrada_row" if _r["tipo"] == "entrada"
                              else "salida_row")
                tree_act.insert("", "end",
                                text=str(_r["id"]),
                                values=(_r["username"], _tipo_lbl, _hora),
                                tags=(_base_tag, _clr_tag))

        def _edit_entry():
            sel = tree_act.selection()
            if not sel:
                return
            _cid  = int(tree_act.item(sel[0], "text"))
            _vals = tree_act.item(sel[0], "values")
            _hora_actual = _vals[2] if _vals else "00:00"

            wp = tk.Toplevel(self.root)
            wp.title("Editar hora")
            wp.configure(bg=BG_PANEL)
            ww, wh = int(sw * 0.22), int(sh * 0.24)
            wp.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
            wp.grab_set()

            tk.Frame(wp, bg=WARNING, height=4).pack(fill="x")
            tk.Label(wp, text="Editar hora", bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 13, "bold")).pack(pady=(12, 2))
            tk.Label(wp,
                     text=f"{_vals[0]}  ·  {_vals[1]}  ·  {_act_date_var.get()}",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10)).pack(pady=(0, 8))

            _tv = tk.StringVar(value=_hora_actual)
            _ef = tk.Frame(wp, bg=BG_PANEL)
            _ef.pack(padx=16)
            tk.Label(_ef, text="Hora (HH:MM):", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11)).pack(side="left", padx=4)
            tk.Entry(_ef, textvariable=_tv, width=7,
                     font=("Arial", 13), relief="flat",
                     bg=BG_MAIN, highlightbackground=BORDER,
                     highlightthickness=1, justify="center"
                     ).pack(side="left", ipady=5)

            _err = tk.Label(wp, text="", bg=BG_PANEL, fg=DANGER,
                            font=("Arial", 9))
            _err.pack(pady=4)

            def _save():
                import re as _re
                new_t = _tv.get().strip()
                if not _re.match(r"^\d{1,2}:\d{2}$", new_t):
                    _err.config(text="Formato inválido  (HH:MM)")
                    return
                try:
                    _h, _m = map(int, new_t.split(":"))
                    if not (0 <= _h <= 23 and 0 <= _m <= 59):
                        raise ValueError
                except Exception:
                    _err.config(text="Hora inválida")
                    return
                self.db.conn.execute(
                    "UPDATE checadas SET timestamp=? WHERE id=?",
                    (f"{_h:02d}:{_m:02d}:00", _cid))
                self.db.conn.commit()
                wp.destroy()
                _reload_act()

            _rb = tk.Frame(wp, bg=BG_PANEL)
            _rb.pack(pady=4)
            self._btn(_rb, "Guardar",   _save,      bg=SUCCESS,  font_size=11
                      ).pack(side="left", padx=6, ipadx=12, ipady=5)
            self._btn(_rb, "Cancelar",  wp.destroy, bg=TXT_GRAY, font_size=11
                      ).pack(side="left", padx=6, ipadx=12, ipady=5)

        def _delete_entry():
            sel = tree_act.selection()
            if not sel:
                return
            _cid  = int(tree_act.item(sel[0], "text"))
            _vals = tree_act.item(sel[0], "values")

            wp = tk.Toplevel(self.root)
            wp.title("Confirmar")
            wp.configure(bg=BG_PANEL)
            ww, wh = int(sw * 0.26), int(sh * 0.18)
            wp.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
            wp.grab_set()

            tk.Frame(wp, bg=DANGER, height=4).pack(fill="x")
            tk.Label(wp, text="¿Eliminar registro?", bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 12, "bold")).pack(pady=(12, 4))
            tk.Label(wp, text=f"{_vals[0]}  ·  {_vals[1]}  ·  {_vals[2]}",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10)).pack()

            def _ok():
                self.db.conn.execute("DELETE FROM checadas WHERE id=?",
                                     (_cid,))
                self.db.conn.commit()
                wp.destroy()
                _reload_act()

            _rb2 = tk.Frame(wp, bg=BG_PANEL)
            _rb2.pack(pady=14)
            self._btn(_rb2, "Eliminar", _ok,        bg=DANGER,   font_size=11
                      ).pack(side="left", padx=8, ipadx=12, ipady=5)
            self._btn(_rb2, "Cancelar", wp.destroy, bg=TXT_GRAY, font_size=11
                      ).pack(side="left", padx=8, ipadx=12, ipady=5)

        # Colocar botones ahora que las funciones están definidas
        self._btn(act_btns, "✏  Editar hora", _edit_entry,
                  bg=WARNING, font_size=10
                  ).pack(side="left", ipadx=8, ipady=3, padx=(0, 6))
        self._btn(act_btns, "🗑  Eliminar", _delete_entry,
                  bg=DANGER, font_size=10
                  ).pack(side="left", ipadx=8, ipady=3)

        # Doble clic en treeview = editar directo
        tree_act.bind("<Double-Button-1>", lambda _e: _edit_entry())

        # Conectar filtros
        _emp_cb.bind("<<ComboboxSelected>>", lambda _e: _reload_act())
        _date_e.bind("<Return>",    lambda _e: _reload_act())
        _date_e.bind("<FocusOut>",  lambda _e: _reload_act())

        # Selección en árbol de empleados → filtrar automáticamente
        def _on_emp_sel(_e=None):
            _sel = self.tree_empleados.selection()
            if not _sel:
                return
            _uid  = int(self.tree_empleados.item(_sel[0], "text"))
            _urow = next((r for r in self.db.get_users_full()
                          if r["id"] == _uid), None)
            if _urow and _urow["username"] in _emp_names:
                _flt_emp_var.set(_urow["username"])
                _reload_act()

        self.tree_empleados.bind("<<TreeviewSelect>>", _on_emp_sel)

        _reload_act()

        self._actualizar_tree_empleados()

    def _actualizar_tree_empleados(self):
        for row in self.tree_empleados.get_children():
            self.tree_empleados.delete(row)
        # Configure row-background tags (even/odd) and status foreground tags
        self._tag_rows(self.tree_empleados)
        self.tree_empleados.tag_configure("activo_si", foreground="#15803D")
        self.tree_empleados.tag_configure("activo_no", foreground="#DC2626")
        for i, r in enumerate(self.db.get_users_full()):
            nivel  = self.NIVELES.get(int(r["access_level"]), str(r["access_level"]))
            em_tel = str(r["emergency_phone"] or "")
            activo = int(r["activo"]) if r["activo"] is not None else 1
            estatus_txt = "✓ Activo" if activo else "✗ Inactivo"
            full_nm = str(r["full_name"] or "") if "full_name" in r.keys() else ""
            bg_tag  = "even" if i % 2 == 0 else "odd"
            clr_tag = "activo_si" if activo else "activo_no"
            self.tree_empleados.insert(
                "", "end",
                text=str(r["id"]),
                values=(r["id"], r["username"], full_nm or "—", r["pin"], nivel,
                        f"$ {r['sales_target']:,.2f}",
                        r["birth_date"] or "—", r["emergency_name"] or "—",
                        em_tel or "—", r["entry_date"] or "—", estatus_txt),
                tags=(bg_tag, clr_tag))

    def _editar_empleado_sel(self):
        sel = self.tree_empleados.selection()
        if not sel:
            return
        uid = int(self.tree_empleados.item(sel[0], "text"))
        rows = self.db.get_users_full()
        row  = next((r for r in rows if r["id"] == uid), None)
        if row:
            self.window_editar_empleado(uid, dict(row))

    def _eliminar_empleado(self):
        sel = self.tree_empleados.selection()
        if not sel:
            return
        uid  = int(self.tree_empleados.item(sel[0], "text"))
        rows = self.db.get_users_full()
        row  = next((r for r in rows if r["id"] == uid), None)
        if not row:
            return
        # Proteger: no borrar al CEO activo
        if str(row["pin"]) == str(getattr(self, "_current_pin", "")):
            return

        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Confirmar")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.28), int(sh * 0.20)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        tk.Frame(win, bg=DANGER, height=4).pack(fill="x")
        tk.Label(win, text=f"Eliminar a {row['username']}?",
                 bg=BG_PANEL, fg=TXT_MAIN, font=("Arial", 13, "bold")).pack(pady=(12, 4))
        tk.Label(win, text="Esta accion no se puede deshacer.",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 10)).pack(pady=2)

        row_btn = tk.Frame(win, bg=BG_PANEL)
        row_btn.pack(pady=12)

        def _ok():
            self.db.delete_user(uid)
            win.destroy()
            self._actualizar_tree_empleados()

        self._btn(row_btn, "Eliminar", _ok, bg=DANGER, font_size=12
                  ).pack(side="left", padx=8, ipadx=14, ipady=6)
        self._btn(row_btn, "Cancelar", win.destroy, bg=TXT_GRAY, font_size=12
                  ).pack(side="left", padx=8, ipadx=14, ipady=6)

    def window_editar_empleado(self, uid=None, row=None):
        sw, sh = self.screen_width, self.screen_height
        win = tk.Toplevel(self.root)
        win.title("Usuario")
        win.configure(bg=BG_PANEL)
        ww, wh = int(sw * 0.36), int(sh * 0.88)
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        win.transient(self.root)
        win.grab_set()

        color = PRIMARY if uid else SUCCESS
        tk.Frame(win, bg=color, height=4).pack(fill="x")
        titulo = f"Editar usuario #{uid}" if uid else "Nuevo usuario"
        tk.Label(win, text=titulo, bg=BG_PANEL, fg=TXT_MAIN,
                 font=("Arial", 14, "bold")).pack(pady=(12, 6))

        def _field(parent, label, var_name, entries_dict):
            rf = tk.Frame(parent, bg=BG_PANEL)
            rf.pack(fill="x", padx=24, pady=4)
            tk.Label(rf, text=label, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=24, anchor="w").pack(side="left")
            e = tk.Entry(rf, font=("Arial", 12), relief="flat",
                         bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1)
            e.pack(side="left", fill="x", expand=True, ipady=5)
            entries_dict[var_name] = e

        entries = {}
        _field(win, "Alias (se usa en sistema)", "e_name",     entries)
        _field(win, "Nombre completo",            "e_fullname", entries)
        _field(win, "PIN (numérico)",             "e_pin",      entries)
        _field(win, "Meta de ventas ($)",         "e_meta",     entries)
        _field(win, "Foto (nombre archivo)",      "e_foto",     entries)

        # Nivel de acceso
        nf = tk.Frame(win, bg=BG_PANEL)
        nf.pack(fill="x", padx=24, pady=4)
        tk.Label(nf, text="Nivel de acceso", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=24, anchor="w").pack(side="left")
        NIVEL_OPTIONS = ["0 – CEO", "1 – Gerente", "2 – Vendedor", "3 – Vendedor Jr."]
        nivel_var = tk.StringVar()
        nivel_cb  = ttk.Combobox(nf, textvariable=nivel_var, state="readonly",
                                 values=NIVEL_OPTIONS,
                                 width=20, font=("Arial", 11))
        nivel_cb.pack(side="left", padx=4, ipady=4)

        # ── Sección: Fecha de nacimiento ──────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)
        tk.Label(win, text="Datos personales", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=24)

        birth_var = tk.StringVar()
        bf = tk.Frame(win, bg=BG_PANEL)
        bf.pack(fill="x", padx=24, pady=4)
        tk.Label(bf, text="Fecha de nacimiento", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=24, anchor="w").pack(side="left")
        self._btn(bf, "Seleccionar fecha",
                  lambda: self._show_calendar_var(birth_var, parent=win),
                  bg=PRIMARY, font_size=10
                  ).pack(side="left", ipady=5)
        tk.Label(bf, textvariable=birth_var, bg=BG_MAIN, fg=TXT_MAIN,
                 font=("Arial", 12), anchor="w", width=14
                 ).pack(side="left", padx=6)

        # ── Sección: Contacto de emergencia ───────────────────────────────
        em_name_var = tk.StringVar()
        em_tel_var  = tk.StringVar()
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)
        tk.Label(win, text="Contacto de emergencia", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=24)

        for lbl, var in [("Nombre completo", em_name_var), ("Teléfono", em_tel_var)]:
            rf = tk.Frame(win, bg=BG_PANEL)
            rf.pack(fill="x", padx=24, pady=4)
            tk.Label(rf, text=lbl, bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 11), width=24, anchor="w").pack(side="left")
            tk.Entry(rf, textvariable=var, font=("Arial", 12), relief="flat",
                     bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1
                     ).pack(side="left", fill="x", expand=True, ipady=5)

        # ── Sección: Fecha de entrada (solo CEO la llena) ─────────────────
        entry_date_var = tk.StringVar()
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)
        tk.Label(win, text="Administración", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w").pack(fill="x", padx=24)

        edf = tk.Frame(win, bg=BG_PANEL)
        edf.pack(fill="x", padx=24, pady=4)
        tk.Label(edf, text="Fecha de entrada", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=24, anchor="w").pack(side="left")
        tk.Entry(edf, textvariable=entry_date_var, font=("Arial", 12), relief="flat",
                 bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1,
                 width=14).pack(side="left", ipady=5)
        self._btn(edf, "Calendario",
                  lambda: self._show_calendar_var(entry_date_var, parent=win),
                  bg=TXT_GRAY, font_size=10
                  ).pack(side="left", padx=6, ipady=5)

        # ── Estatus (Activo / Inactivo) ───────────────────────────────────
        activo_var = tk.BooleanVar(value=True)
        stf = tk.Frame(win, bg=BG_PANEL)
        stf.pack(fill="x", padx=24, pady=6)
        tk.Label(stf, text="Estatus", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 11), width=24, anchor="w").pack(side="left")

        # Toggle visual: un botón que cambia texto/color al hacer clic
        _toggle_btn = [None]   # lista para acceder desde closure
        def _refresh_toggle():
            val = activo_var.get()
            _toggle_btn[0].config(
                text="✓  Activo",
                bg="#DCFCE7", fg="#15803D",
                activebackground="#BBF7D0", activeforeground="#15803D"
            ) if val else _toggle_btn[0].config(
                text="✗  Inactivo",
                bg="#FEE2E2", fg="#DC2626",
                activebackground="#FECACA", activeforeground="#DC2626"
            )
        def _toggle_activo():
            activo_var.set(not activo_var.get())
            _refresh_toggle()

        btn_toggle = tk.Button(stf, text="", font=("Arial", 11, "bold"),
                               relief="flat", cursor="hand2",
                               bd=0, padx=14, pady=6,
                               command=_toggle_activo)
        btn_toggle.pack(side="left")
        _toggle_btn[0] = btn_toggle
        _refresh_toggle()

        # Pre-llenar si se edita
        if row:
            entries["e_name"].insert(0,     str(row.get("username",     "") or ""))
            entries["e_fullname"].insert(0, str(row.get("full_name",    "") or ""))
            entries["e_pin"].insert(0,      str(row.get("pin",          "") or ""))
            entries["e_meta"].insert(0,     str(row.get("sales_target", 0)  or 0))
            entries["e_foto"].insert(0,     str(row.get("photo",        "") or ""))
            _al = int(row.get('access_level', 2) or 2)
            _target = f"{_al} – {self.NIVELES.get(_al, '')}"
            _idx = NIVEL_OPTIONS.index(_target) if _target in NIVEL_OPTIONS else 2
            win.after(50, lambda i=_idx: nivel_cb.current(i))
            birth_var.set(      str(row.get("birth_date",      "") or ""))
            em_name_var.set(    str(row.get("emergency_name",  "") or ""))
            em_tel_var.set(     str(row.get("emergency_phone", "") or ""))
            entry_date_var.set( str(row.get("entry_date",      "") or ""))
            activo_var.set(bool(int(row.get("activo", 1) or 1)))
            _refresh_toggle()
        else:
            nivel_cb.current(2)   # default: Vendedor

        err_lbl = tk.Label(win, text="", bg=BG_PANEL, fg=DANGER, font=("Arial", 10))
        err_lbl.pack(pady=2)

        def _guardar():
            nombre    = entries["e_name"].get().strip()
            fullname  = entries["e_fullname"].get().strip()
            pin       = entries["e_pin"].get().strip()
            meta      = entries["e_meta"].get().strip()
            foto      = entries["e_foto"].get().strip()
            nivel_str = nivel_cb.get()
            bd        = birth_var.get().strip()
            en        = em_name_var.get().strip()
            ep        = em_tel_var.get().strip()
            ed        = entry_date_var.get().strip()
            activo    = activo_var.get()

            if not nombre or not pin:
                err_lbl.config(text="Alias y PIN son obligatorios.")
                return
            try:
                meta_f  = float(meta) if meta else 0.0
                nivel_i = int(nivel_str.split(" – ")[0].strip())
            except Exception:
                err_lbl.config(text="Meta o nivel inválidos.")
                return
            if bd:
                try:
                    datetime.strptime(bd, "%d/%m/%Y")
                except Exception:
                    err_lbl.config(text="Fecha de nacimiento inválida (dd/mm/aaaa).")
                    return

            self.db.save_user(uid, nombre, pin, nivel_i, foto, meta_f,
                              birth_date=bd, emergency_name=en,
                              emergency_phone=ep, entry_date=ed, activo=activo,
                              full_name=fullname)
            win.destroy()
            self._actualizar_tree_empleados()

        self._btn(win, "Guardar usuario", _guardar, bg=color, font_size=13
                  ).pack(pady=14, ipadx=24, ipady=8)


    # ══════════════════════════════════════════════════════════════════════════
    # ANÁLISIS DE VENTAS
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_analisis(self):
        self._current_screen = self.opcion_analisis
        sw, sh = self.screen_width, self.screen_height

        self.frame_analisis = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_analisis.place(x=int(sw * 0.1), y=0,
                                  width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)
        sq = int(sh * 0.048)   # height of date-row widgets

        self._header(self.frame_analisis, "Análisis de Ventas",
                     subtitle="Selecciona un rango de fechas")

        # ── Fila de rango de fechas ────────────────────────────────────────
        now   = datetime.now()
        # Default to current corte range
        _an_di, _an_df = self.cortes(now.year, now.month)
        dr_y  = hh + int(sh * 0.018)
        lbl_y = dr_y + (sq - int(sh * 0.025)) // 2

        tk.Label(self.frame_analisis, text="Desde:", bg=BG_MAIN, fg=TXT_GRAY,
                 font=("Arial", 11)).place(x=int(pw * 0.02), y=lbl_y)
        self.an_fi = tk.Entry(self.frame_analisis, font=("Arial", 12), justify="center",
                              relief="flat", bg=BG_PANEL, fg=TXT_MAIN,
                              highlightbackground=BORDER, highlightthickness=1)
        self.an_fi.insert(0, _an_di)
        self.an_fi.place(x=int(pw * 0.09), y=dr_y, width=int(pw * 0.12), height=sq)

        self._btn(self.frame_analisis, "▼",
                  lambda: self._show_calendar(self.an_fi),
                  bg=PRIMARY, font_size=11
                  ).place(x=int(pw * 0.22), y=dr_y, width=sq, height=sq)

        tk.Label(self.frame_analisis, text="Hasta:", bg=BG_MAIN, fg=TXT_GRAY,
                 font=("Arial", 11)).place(x=int(pw * 0.27), y=lbl_y)
        self.an_ff = tk.Entry(self.frame_analisis, font=("Arial", 12), justify="center",
                              relief="flat", bg=BG_PANEL, fg=TXT_MAIN,
                              highlightbackground=BORDER, highlightthickness=1)
        self.an_ff.insert(0, _an_df)
        self.an_ff.place(x=int(pw * 0.34), y=dr_y, width=int(pw * 0.12), height=sq)

        self._btn(self.frame_analisis, "▼",
                  lambda: self._show_calendar(self.an_ff),
                  bg=PRIMARY, font_size=11
                  ).place(x=int(pw * 0.47), y=dr_y, width=sq, height=sq)

        self._btn(self.frame_analisis, "Consultar", self._actualizar_analisis,
                  bg=SUCCESS, font_size=12
                  ).place(x=int(pw * 0.52), y=dr_y, width=int(pw * 0.12), height=sq)

        self._btn(self.frame_analisis, "🖨 Imprimir Reporte",
                  self._imprimir_reporte_analisis,
                  bg=BG_SIDEBAR, font_size=11
                  ).place(x=int(pw * 0.76), y=dr_y, width=int(pw * 0.20), height=sq)

        def _set_today():
            ds = f"{now.day:02d}/{now.month:02d}/{now.year}"
            self.an_fi.delete(0, tk.END); self.an_fi.insert(0, ds)
            self.an_ff.delete(0, tk.END); self.an_ff.insert(0, ds)
            self._actualizar_analisis()

        self._btn(self.frame_analisis, "Solo hoy", _set_today,
                  bg=TXT_GRAY, font_size=11
                  ).place(x=int(pw * 0.67), y=dr_y, width=int(pw * 0.09), height=sq)

        # ── Selector de mes con periodos de corte ─────────────────────────
        MESES_NOM = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                     "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        MESES_CORTO = ["Ene","Feb","Mar","Abr","May","Jun",
                       "Jul","Ago","Sep","Oct","Nov","Dic"]

        mes_bar_y = dr_y + sq + int(sh * 0.008)
        mes_bar_h = int(sh * 0.046)

        mes_bar = tk.Frame(self.frame_analisis, bg="#EFF6FF",
                           highlightbackground=PRIMARY,
                           highlightthickness=1)
        mes_bar.place(x=int(pw * 0.02), y=mes_bar_y,
                      width=int(pw * 0.96), height=mes_bar_h)

        # estado de año seleccionado
        _sel_year = {"y": now.year, "m": now.month}
        _mes_chips = {}   # m_num -> Label widget

        yr_lbl = tk.Label(mes_bar, text="", bg="#EFF6FF", fg=PRIMARY,
                          font=("Arial", 11, "bold"), cursor="hand2")
        yr_lbl.pack(side="left", padx=(8, 2))

        def _yr_prev():
            _sel_year["y"] -= 1
            _rebuild_chips()
        def _yr_next():
            _sel_year["y"] += 1
            _rebuild_chips()

        tk.Label(mes_bar, text="◀", bg="#EFF6FF", fg=PRIMARY,
                 font=("Arial", 11, "bold"), cursor="hand2",
                 padx=2).pack(side="left")
        mes_bar.winfo_children()[-1].bind("<Button-1>", lambda _e: _yr_prev())
        tk.Label(mes_bar, text="▶", bg="#EFF6FF", fg=PRIMARY,
                 font=("Arial", 11, "bold"), cursor="hand2",
                 padx=2).pack(side="left", padx=(0, 8))
        mes_bar.winfo_children()[-1].bind("<Button-1>", lambda _e: _yr_next())

        chips_fr = tk.Frame(mes_bar, bg="#EFF6FF")
        chips_fr.pack(side="left", fill="both", expand=True)

        def _set_mes_periodo(m, y):
            try:
                fi, ff = self.cortes(y, m, mes=True)
            except Exception:
                import calendar as _cm
                ld = _cm.monthrange(y, m)[1]
                fi, ff = f"01/{m:02d}/{y}", f"{ld:02d}/{m:02d}/{y}"
            self.an_fi.delete(0, tk.END); self.an_fi.insert(0, fi)
            self.an_ff.delete(0, tk.END); self.an_ff.insert(0, ff)
            _sel_year["m"] = m   # guardar el mes real clicado, no inferirlo de la fecha
            _rebuild_chips()
            self._actualizar_analisis()

        def _rebuild_chips():
            y     = _sel_year["y"]
            cur_m = _sel_year["m"]
            cur_y = y
            yr_lbl.config(text=str(y))
            for w in chips_fr.winfo_children():
                w.destroy()
            _mes_chips.clear()

            chip_h = mes_bar_h - 10
            for i, (abr, nom) in enumerate(zip(MESES_CORTO, MESES_NOM)):
                m_num   = i + 1
                is_sel  = (m_num == cur_m and y == cur_y)
                is_now  = (m_num == now.month and y == now.year)

                if is_sel:
                    bg_c, fg_c, bd_c = PRIMARY, "white", PRIMARY
                elif is_now:
                    bg_c, fg_c, bd_c = "#DBEAFE", PRIMARY, PRIMARY
                else:
                    bg_c, fg_c, bd_c = "white", TXT_MAIN, "#CBD5E1"

                chip = tk.Frame(chips_fr, bg=bd_c,
                                highlightbackground=bd_c,
                                highlightthickness=1)
                chip.pack(side="left", padx=3, pady=5)

                inner = tk.Frame(chip, bg=bg_c)
                inner.pack(padx=1, pady=1)

                lbl = tk.Label(inner, text=abr, bg=bg_c, fg=fg_c,
                               font=("Arial", 9, "bold"),
                               padx=6, pady=2, cursor="hand2")
                lbl.pack()

                # tooltip con nombre completo al hover
                def _enter(e, w=inner, l=lbl, bn=bg_c,
                           hbg=PRIMARY if is_sel else "#BFDBFE",
                           hfg="white" if is_sel else PRIMARY):
                    w.config(bg=hbg); l.config(bg=hbg, fg=hfg)
                def _leave(e, w=inner, l=lbl, bb=bg_c, bf=fg_c):
                    w.config(bg=bb); l.config(bg=bb, fg=bf)
                def _click(e, _m=m_num, _y=y):
                    _set_mes_periodo(_m, _y)

                for ww in (chip, inner, lbl):
                    ww.bind("<Button-1>", _click)
                    ww.bind("<Enter>",    _enter)
                    ww.bind("<Leave>",    _leave)

                _mes_chips[m_num] = lbl

        _rebuild_chips()

        # ── Columna izquierda ──────────────────────────────────────────────
        lx      = int(pw * 0.02)
        lw      = int(pw * 0.37)
        cont_y  = hh + int(sh * 0.135)
        badge_c = [SUCCESS, PRIMARY, WARNING]

        top3_h  = int(sh * 0.28)
        top3_card = self._card(self.frame_analisis, x=lx, y=cont_y,
                               w=lw, h=top3_h, title="TOP 3 PRODUCTOS  (por ganancia)")
        self._an_top3 = []
        row_h = int((top3_h - 28) / 3)
        for i in range(3):
            ry_i = 24 + i * row_h
            rf   = tk.Frame(top3_card, bg=BG_PANEL)
            rf.place(x=6, y=ry_i, width=lw - 14, height=row_h - 2)

            badge = tk.Label(rf, text=f"#{i+1}", bg=badge_c[i], fg="white",
                             font=("Arial", 10, "bold"), anchor="center")
            badge.place(x=0, y=6, width=30, height=22)

            lbl_n = tk.Label(rf, text="—", bg=BG_PANEL, fg=TXT_MAIN,
                             font=("Arial", 11, "bold"), anchor="w")
            lbl_n.place(x=36, y=2, width=int(lw * 0.58), height=int(row_h * 0.42))

            lbl_g = tk.Label(rf, text="", bg=BG_PANEL, fg=SUCCESS,
                             font=("Arial", 11, "bold"), anchor="e")
            lbl_g.place(x=int(lw * 0.62), y=2,
                        width=int(lw * 0.34), height=int(row_h * 0.42))

            lbl_d = tk.Label(rf, text="", bg=BG_PANEL, fg=TXT_GRAY,
                             font=("Arial", 9), anchor="w")
            lbl_d.place(x=36, y=int(row_h * 0.44),
                        width=lw - 50, height=int(row_h * 0.44))
            self._an_top3.append((lbl_n, lbl_g, lbl_d))

        # Totales generales
        tot_y    = cont_y + top3_h + int(sh * 0.015)
        tot_h    = int(sh * 0.20)
        tot_card = self._card(self.frame_analisis, x=lx, y=tot_y,
                              w=lw, h=tot_h, title="TOTALES GENERALES")

        self._an_lbl_total = tk.Label(tot_card, text="$ 0.00", bg=BG_PANEL,
                                      fg=SUCCESS, font=("Arial", 22, "bold"), anchor="center")
        self._an_lbl_total.place(x=0, y=22, width=lw - 12, height=int(sh * 0.065))
        tk.Label(tot_card, text="Ventas totales", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9)).place(x=0, y=22 + int(sh * 0.065),
                                          width=lw - 12, height=int(sh * 0.02))
        sep_y = 22 + int(sh * 0.09)
        tk.Frame(tot_card, bg=BORDER, height=1).place(x=10, y=sep_y, width=lw - 30)

        self._an_lbl_n = tk.Label(tot_card, text="0 ventas", bg=BG_PANEL,
                                   fg=TXT_MAIN, font=("Arial", 12, "bold"), anchor="center")
        self._an_lbl_n.place(x=0, y=sep_y + 8,
                              width=int((lw - 12) * 0.48), height=int(sh * 0.045))

        self._an_lbl_ticket = tk.Label(tot_card, text="Ticket: $ 0.00", bg=BG_PANEL,
                                        fg=PRIMARY, font=("Arial", 12, "bold"), anchor="center")
        self._an_lbl_ticket.place(x=int((lw - 12) * 0.52), y=sep_y + 8,
                                   width=int((lw - 12) * 0.46), height=int(sh * 0.045))

        # TOP 3 CLIENTES card
        cli3_y   = tot_y + tot_h + int(sh * 0.012)
        cli3_h   = int(sh * 0.21)
        cli3_card = self._card(self.frame_analisis, x=lx, y=cli3_y,
                               w=lw, h=cli3_h, title="TOP 3 CLIENTES  (por compras)")
        self._an_top3_cli = []
        cli_row_h = int((cli3_h - 24) / 3)
        cli_badge_c = [SUCCESS, PRIMARY, WARNING]
        for i in range(3):
            ry_i = 22 + i * cli_row_h
            rf   = tk.Frame(cli3_card, bg=BG_PANEL)
            rf.place(x=6, y=ry_i, width=lw - 14, height=cli_row_h - 2)
            badge = tk.Label(rf, text=f"#{i+1}", bg=cli_badge_c[i], fg="white",
                             font=("Arial", 10, "bold"), anchor="center")
            badge.place(x=0, y=4, width=30, height=20)
            lbl_n = tk.Label(rf, text="—", bg=BG_PANEL, fg=TXT_MAIN,
                             font=("Arial", 10, "bold"), anchor="w")
            lbl_n.place(x=36, y=2, width=int(lw * 0.55), height=int(cli_row_h * 0.5))
            lbl_v = tk.Label(rf, text="", bg=BG_PANEL, fg=PRIMARY,
                             font=("Arial", 10, "bold"), anchor="e")
            lbl_v.place(x=int(lw * 0.60), y=2,
                        width=int(lw * 0.36), height=int(cli_row_h * 0.5))
            self._an_top3_cli.append((lbl_n, lbl_v))

        # ── Columna derecha: gráficas con pestañas ────────────────────────
        rx    = int(pw * 0.41)
        rw    = int(pw * 0.57)
        fig_h = sh - cont_y - int(sh * 0.02)

        # Estilo de pestañas
        nb_style = ttk.Style()
        nb_style.configure("AN.TNotebook",        background=BG_MAIN, borderwidth=0)
        nb_style.configure("AN.TNotebook.Tab",
                           background=BG_SIDEBAR, foreground=TXT_LIGHT,
                           font=("Arial", 10, "bold"),
                           padding=(10, 5))
        nb_style.map("AN.TNotebook.Tab",
                     background=[("selected", SB_ACTIVE)],
                     foreground=[("selected", "white")])

        notebook = ttk.Notebook(self.frame_analisis, style="AN.TNotebook")
        notebook.place(x=rx, y=cont_y, width=rw, height=fig_h)

        TAB_DEFS = [
            ("Usuario",   "Usuario",   "bar"),
            ("Cliente",   "Cliente",   "bar"),
            ("Hora",      "Hora",      "bar"),
            ("Día",       "Día",       "bar"),
            ("Categoría", "Categoría", "pie"),
            ("Marca",     "Marca",     "pie"),
            ("Resumen",   "Resumen",   "summary"),
        ]

        self._an_charts = {}
        tab_h = fig_h - 35  # discount tab bar height

        if _MPL:
            for key, tab_title, chart_type in TAB_DEFS:
                tab_frame = tk.Frame(notebook, bg=BG_PANEL)
                notebook.add(tab_frame, text=f"  {tab_title}  ")
                fig = Figure(figsize=(rw / 100, tab_h / 100), dpi=100)
                fig.patch.set_facecolor(BG_PANEL)
                canvas = FigureCanvasTkAgg(fig, master=tab_frame)
                canvas.get_tk_widget().pack(fill="both", expand=True)
                self._an_charts[key] = (fig, canvas, chart_type)
        else:
            tab_frame = tk.Frame(notebook, bg=BG_PANEL)
            notebook.add(tab_frame, text="Gráficas")
            tk.Label(tab_frame,
                     text="Instala matplotlib para ver gráficas\n(pip install matplotlib)",
                     bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 13)).pack(expand=True)

        # ── Pestañas de tabla (no requieren matplotlib) ───────────────────────
        self._an_trees        = {}
        self._an_brand_filter = {}
        self._an_brand_chips  = {}
        tcols = ("SKU", "Producto", "Pzas", "P.Unit.", "Total")

        brands = sorted({
            str(p[6]).strip()
            for p in self.data_products.values()
            if len(p) > 6 and p[6] and str(p[6]).strip()
        })

        for key, tab_title in [("top_vendidos", "Top Vendidos"),
                                ("por_cantidad", "Por Cantidad")]:
            tf = tk.Frame(notebook, bg=BG_PANEL)
            notebook.add(tf, text=f"  {tab_title}  ")

            # ── Chips de marca ──────────────────────────────────────────────
            self._an_brand_filter[key] = "Todas"
            self._an_brand_chips[key]  = {}

            chips_outer = tk.Frame(tf, bg=BG_PANEL)
            chips_outer.pack(fill="x", padx=8, pady=(6, 2))

            chips_canvas = tk.Canvas(chips_outer, bg=BG_PANEL, height=34,
                                     highlightthickness=0)
            chips_sb = ttk.Scrollbar(chips_outer, orient="horizontal",
                                     command=chips_canvas.xview)
            chips_canvas.configure(xscrollcommand=chips_sb.set)
            chips_inner = tk.Frame(chips_canvas, bg=BG_PANEL)
            chips_canvas.create_window((0, 0), window=chips_inner, anchor="nw")
            chips_inner.bind("<Configure>",
                             lambda e, cv=chips_canvas: cv.configure(
                                 scrollregion=cv.bbox("all")))
            chips_canvas.pack(side="top", fill="x")
            chips_sb.pack(side="top", fill="x")

            def _make_chip(k, bname, frame):
                is_sel = (bname == "Todas")
                lbl = tk.Label(frame, text=bname,
                               bg=PRIMARY if is_sel else BG_MAIN,
                               fg="white"  if is_sel else TXT_GRAY,
                               font=("Arial", 9, "bold"),
                               padx=10, pady=3, cursor="hand2")
                lbl.pack(side="left", padx=3, pady=2)

                def _select(b=bname, kk=k):
                    self._an_brand_filter[kk] = b
                    for bn, bl in self._an_brand_chips[kk].items():
                        sel = (bn == b)
                        bl.config(bg=PRIMARY if sel else BG_MAIN,
                                  fg="white"  if sel else TXT_GRAY)
                    self._poblar_tabla_analisis(kk)

                lbl.bind("<Button-1>", lambda e: _select())
                self._an_brand_chips[k][bname] = lbl

            _make_chip(key, "Todas", chips_inner)
            for brand in brands:
                _make_chip(key, brand, chips_inner)

            # ── Treeview ────────────────────────────────────────────────────
            tree = ttk.Treeview(tf, columns=tcols, show="headings")
            for col, frac in zip(tcols, (0.09, 0.44, 0.09, 0.17, 0.17)):
                tree.column(col,
                            anchor="w" if col == "Producto" else "center",
                            width=int(rw * frac))
                tree.heading(col, text=col)
            sb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y", pady=8)
            tree.pack(fill="both", expand=True, padx=(8, 0), pady=8)
            self._tag_rows(tree)
            self._an_trees[key] = tree

        self._an_data = {}
        self._actualizar_analisis()

    # ── Calendario popup ──────────────────────────────────────────────────────
    def _show_calendar(self, entry_widget, parent=None):
        try:
            init = datetime.strptime(entry_widget.get().strip(), "%d/%m/%Y")
        except Exception:
            init = datetime.now()

        state = {"year": init.year, "month": init.month}
        MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

        # Siempre crear el Toplevel como hijo de self.root para evitar
        # jerarquías anidadas que algunos WMs de Linux no manejan bien.
        # Si hay un parent popup, usarlo solo para transient y centrado.
        cal_parent = parent if parent is not None else self.root
        win = tk.Toplevel(self.root)
        win.title("Seleccionar fecha")
        win.configure(bg=BG_PANEL)
        win.resizable(False, False)
        # transient le dice al WM que este diálogo pertenece a cal_parent
        win.transient(cal_parent)
        cw, ch = 390, 430
        # Centrar sobre la ventana parent (popup o root)
        cal_parent.update_idletasks()
        px = cal_parent.winfo_rootx()
        py = cal_parent.winfo_rooty()
        pw_ = cal_parent.winfo_width()
        ph_ = cal_parent.winfo_height()
        rx = px + (pw_ - cw) // 2
        ry = py + (ph_ - ch) // 2
        win.geometry(f"{cw}x{ch}+{rx}+{ry}")
        win.grab_set()
        win.lift()
        win.focus_force()

        # Navigation bar
        nav = tk.Frame(win, bg=BG_SIDEBAR)
        nav.pack(fill="x")

        lbl_mes = tk.Label(nav, text="", bg=BG_SIDEBAR, fg="white",
                           font=("Arial", 14, "bold"), pady=11)
        lbl_mes.pack(side="left", expand=True)

        def _prev():
            state["month"] -= 1
            if state["month"] == 0:
                state["month"] = 12; state["year"] -= 1
            _build()

        def _next():
            state["month"] += 1
            if state["month"] == 13:
                state["month"] = 1; state["year"] += 1
            _build()

        def _prev_year():
            state["year"] -= 1
            _build()

        def _next_year():
            state["year"] += 1
            _build()

        # Flechas: doble = año, simple = mes
        # doble con fondo ligeramente distinto para destacar
        for txt, cmd, side, is_double in [
                ("◀◀", _prev_year, "left",  True),
                (" ◀ ", _prev,     "left",  False),
                ("▶▶", _next_year, "right", True),
                (" ▶ ", _next,     "right", False)]:
            btn_bg = PRIMARY_DK if is_double else BG_SIDEBAR
            btn_hv = "#1e3a8a"  if is_double else SB_HOVER
            lbl = tk.Label(nav, text=txt, bg=btn_bg, fg="white",
                           font=("Arial", 15, "bold"), cursor="hand2",
                           padx=10, pady=6, relief="flat")
            lbl.pack(side=side)
            lbl.bind("<Button-1>", lambda _e, c=cmd: c())
            lbl.bind("<Enter>",  lambda _e, l=lbl, h=btn_hv: l.config(bg=h))
            lbl.bind("<Leave>",  lambda _e, l=lbl, b=btn_bg: l.config(bg=b))

        # Leyenda de navegación
        tk.Label(win, text="◀◀ ▶▶  cambia año     ◀ ▶  cambia mes",
                 bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 9)).pack(pady=(4, 0))

        # Day-of-week headers
        hdr = tk.Frame(win, bg=BG_MAIN)
        hdr.pack(fill="x", padx=8, pady=(6, 0))
        for d in ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]:
            tk.Label(hdr, text=d, bg=BG_MAIN, fg=TXT_GRAY,
                     font=("Arial", 10, "bold"), width=4,
                     anchor="center").pack(side="left", expand=True)

        # Day grid
        grid_f = tk.Frame(win, bg=BG_PANEL)
        grid_f.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        today = datetime.now()

        def _build():
            for w in grid_f.winfo_children():
                w.destroy()
            yr, mn = state["year"], state["month"]
            lbl_mes.config(text=f"  {MESES[mn - 1]} {yr}  ")

            first_wd, n_days = calendar.monthrange(yr, mn)
            row, col = 0, first_wd

            for c in range(first_wd):
                tk.Label(grid_f, text="", bg=BG_PANEL, width=4).grid(
                    row=0, column=c, padx=3, pady=3)

            for day in range(1, n_days + 1):
                is_today = (yr == today.year and mn == today.month and day == today.day)
                bg = PRIMARY if is_today else BG_MAIN
                fg = "white"  if is_today else TXT_MAIN

                btn = tk.Label(grid_f, text=str(day), bg=bg, fg=fg,
                               font=("Arial", 12), width=4, anchor="center",
                               cursor="hand2")
                btn.grid(row=row, column=col, padx=3, pady=3)

                def _click(_e, y=yr, m=mn, d=day):
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, f"{d:02d}/{m:02d}/{y}")
                    win.destroy()

                dk = PRIMARY_DK if is_today else SB_HOVER
                btn.bind("<Button-1>", _click)
                btn.bind("<Enter>",  lambda _e, b=btn, d=dk:   b.config(bg=d, fg="white"))
                btn.bind("<Leave>",  lambda _e, b=btn, ob=bg, of=fg: b.config(bg=ob, fg=of))

                col += 1
                if col == 7:
                    col = 0
                    row += 1

        _build()

    # ── Cálculo de datos de análisis ──────────────────────────────────────────
    def _calcular_analisis(self, di_str, df_str):
        fmt = "%d/%m/%Y"
        iso_ini = dmy_to_iso(di_str)
        iso_fin = dmy_to_iso(df_str)
        if not iso_ini or not iso_fin:
            return {}

        # Filtro por fecha ISO (texto): no truena si una orden tiene la fecha vacía.
        orders = {}
        for oid, o in self.data_orders.items():
            d_iso = o.get("Fecha_iso") or dmy_to_iso(o.get("Fecha", ""))
            if d_iso and iso_ini <= d_iso <= iso_fin:
                orders[oid] = o

        total   = sum(float(o["Importe_total"]) for o in orders.values())
        n       = len(orders)
        ticket  = total / n if n else 0.0

        # Top 3 por ganancia bruta
        prods = {}
        for order in orders.values():
            for pid, pi in order.get("Productos", {}).items():
                p = self.data_products.get(pid)
                if not p:
                    continue
                qty     = pi.get("Cantidad", 0)
                importe = float(pi.get("Importe", 0))
                profit  = importe - float(p[9]) * qty
                name    = f"{p[2]} ({p[5]})" if p[5] else str(p[2])
                if pid not in prods:
                    prods[pid] = {"name": name, "profit": 0.0,
                                  "qty": 0, "revenue": 0.0}
                prods[pid]["profit"]  += profit
                prods[pid]["qty"]     += qty
                prods[pid]["revenue"] += importe
        top3 = sorted(prods.values(), key=lambda x: x["profit"], reverse=True)[:3]

        # Resumen por producto — ordenado por piezas vendidas desc
        prod_resumen = []
        for pid, d in prods.items():
            p = self.data_products.get(pid)
            if not p:
                continue
            price = float(p[10]) if p[10] else 0.0
            prod_resumen.append({
                "sku":     str(p[0]) if p[0] else "—",
                "name":    d["name"],
                "qty":     d["qty"],
                "revenue": d["revenue"],
                "price":   price,
                "brand":   str(p[6]).strip() if len(p) > 6 and p[6] and str(p[6]).strip() else "Sin marca",
            })
        prod_resumen.sort(key=lambda x: x["qty"], reverse=True)
        top_vendidos = [p for p in prod_resumen if p["price"] >= 50.0]


        # Costo total sin IVA de los productos vendidos
        costo_total = sum(
            float(self.data_products[pid][9]) * pi.get("Cantidad", 0)
            for o in orders.values()
            for pid, pi in o.get("Productos", {}).items()
            if self.data_products.get(pid)
        )

        # Helper: agrupar órdenes, sort_key controla el orden final
        def _by_order(key_fn, sort_key=None):
            g = {}
            for o in orders.values():
                k = key_fn(o)
                if k not in g:
                    g[k] = {"v": 0.0, "n": 0}
                g[k]["v"] += float(o["Importe_total"])
                g[k]["n"] += 1
            srt = sort_key if sort_key else (lambda x: -x[1]["v"])
            return {k: {"ventas": d["v"], "n": d["n"],
                        "ticket": d["v"] / d["n"] if d["n"] else 0}
                    for k, d in sorted(g.items(), key=srt)}

        # Helper: agrupar por campo de producto
        def _by_product(key_fn):
            g = {}
            for o in orders.values():
                seen = {}
                for pid, pi in o.get("Productos", {}).items():
                    p = self.data_products.get(pid)
                    k = key_fn(p) if p else "Sin datos"
                    seen[k] = seen.get(k, 0.0) + float(pi.get("Importe", 0))
                for k, v in seen.items():
                    if k not in g:
                        g[k] = {"v": 0.0, "n": 0}
                    g[k]["v"] += v
                    g[k]["n"] += 1
            return {k: {"ventas": d["v"], "n": d["n"],
                        "ticket": d["v"] / d["n"] if d["n"] else 0}
                    for k, d in sorted(g.items(), key=lambda x: -x[1]["v"])}

        DIAS    = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
        DIA_IDX = {d: i for i, d in enumerate(DIAS)}

        # Hora: ordenar cronológicamente (00–23)
        hora_data = _by_order(
            lambda o: f"{o['Hora'][:2]}:00 h",
            sort_key=lambda x: int(x[0][:2]))

        # Día: ordenar por día de semana (Lunes … Domingo)
        dia_data = _by_order(
            lambda o: DIAS[datetime.strptime(
                o.get("Fecha_iso") or dmy_to_iso(o["Fecha"]), "%Y-%m-%d").weekday()],
            sort_key=lambda x: DIA_IDX.get(x[0], 9))

        # Categoría: agrupar las que sean < 2% del total en "Otras"
        cat_raw   = _by_product(lambda p: str(p[4]) if p[4] else "Sin categoría")
        total_cat = sum(d["ventas"] for d in cat_raw.values()) or 1
        cat_main, otras_v, otras_n = {}, 0.0, 0
        for k, d in cat_raw.items():
            if d["ventas"] / total_cat < 0.02:
                otras_v += d["ventas"]
                otras_n += d["n"]
            else:
                cat_main[k] = d
        if otras_v > 0:
            cat_main["Otras"] = {"ventas": otras_v, "n": otras_n,
                                 "ticket": otras_v / otras_n if otras_n else 0}

        # Clientes: excluir "Publico General" del análisis
        cli_raw = _by_order(lambda o: o["Cliente"])
        cli_data = {k: v for k, v in cli_raw.items() if k != "Publico General"}
        top3_cli = sorted(cli_data.items(),
                          key=lambda x: x[1]["ventas"], reverse=True)[:3]

        return {
            "total":       total,
            "n":           n,
            "ticket":      ticket,
            "costo":       costo_total,
            "top3":        top3,
            "top3_cli":    top3_cli,
            "top_vendidos": top_vendidos,
            "por_cantidad": prod_resumen,
            "Usuario":     _by_order(lambda o: o["Vendedor"]),
            "Hora":        hora_data,
            "Día":         dia_data,
            "Categoría":   cat_main,
            "Marca":       _by_product(lambda p: str(p[6]) if p[6] else "Sin marca"),
            "Cliente":     cli_data,
        }

    # ── Actualizar vista de análisis ──────────────────────────────────────────
    def _actualizar_analisis(self):
        self._an_data = self._calcular_analisis(
            self.an_fi.get(), self.an_ff.get())
        if not self._an_data:
            return

        # Top 3
        top3 = self._an_data.get("top3", [])
        for i, (lbl_n, lbl_g, lbl_d) in enumerate(self._an_top3):
            if i < len(top3):
                p = top3[i]
                lbl_n.config(text=p["name"])
                lbl_g.config(text=f"$ {p['profit']:,.2f}")
                lbl_d.config(text=f"Qty: {p['qty']}  |  Ingresos: $ {p['revenue']:,.2f}")
            else:
                lbl_n.config(text="—")
                lbl_g.config(text="")
                lbl_d.config(text="")

        # Totales
        self._an_lbl_total.config( text=f"$ {self._an_data['total']:,.2f}")
        self._an_lbl_n.config(     text=f"{self._an_data['n']} ventas")
        self._an_lbl_ticket.config(text=f"Ticket: $ {self._an_data['ticket']:,.2f}")

        # Top 3 clientes
        top3_cli = self._an_data.get("top3_cli", [])
        for i, (lbl_n, lbl_v) in enumerate(self._an_top3_cli):
            if i < len(top3_cli):
                cname, cd = top3_cli[i]
                lbl_n.config(text=cname)
                lbl_v.config(text=f"$ {cd['ventas']:,.2f}")
            else:
                lbl_n.config(text="—")
                lbl_v.config(text="")

        self._render_charts()

        # Poblar pestañas de tabla
        for key in getattr(self, "_an_trees", {}):
            self._poblar_tabla_analisis(key)

    def _poblar_tabla_analisis(self, key):
        tree = self._an_trees.get(key)
        if not tree or not self._an_data:
            return
        brand = getattr(self, "_an_brand_filter", {}).get(key, "Todas")
        rows  = self._an_data.get(key, [])
        if brand != "Todas":
            rows = [p for p in rows if p.get("brand", "Sin marca") == brand]
        for row in tree.get_children():
            tree.delete(row)
        for i, p in enumerate(rows):
            self._insert_row(tree,
                (p["sku"], p["name"], p["qty"],
                 f"$ {p['price']:,.2f}",
                 f"$ {p['revenue']:,.2f}"),
                idx=i)

    # ── Reporte PDF de análisis ───────────────────────────────────────────────
    def _imprimir_reporte_analisis(self):
        if not _FPDF:
            messagebox.showerror("PDF no disponible",
                                 "Instala fpdf2:\n  pip install fpdf2")
            return
        d = getattr(self, "_an_data", {})
        if not d or not d.get("n", 0):
            messagebox.showwarning("Sin datos",
                "Primero consulta un período con ventas.")
            return

        fi_str = self.an_fi.get().strip()
        ff_str = self.an_ff.get().strip()
        sf = self._safe_pdf_str

        # ── helpers ──────────────────────────────────────────────────────────
        C_DARK   = (15, 23, 42)
        C_GRAY   = (100, 116, 139)
        C_GREEN  = (5, 150, 105)
        C_RED    = (220, 38, 38)
        C_BLUE   = (37, 99, 235)
        C_PURPLE = (124, 58, 237)
        C_WARN   = (217, 119, 6)
        C_LIGHT  = (248, 250, 252)
        C_WHITE  = (255, 255, 255)
        C_HEAD   = (30, 41, 59)

        def _sec_title(pdf, txt, color=C_HEAD):
            pdf.set_fill_color(*color)
            pdf.set_text_color(*C_WHITE)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, sf(txt), fill=True,
                     new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

        def _kv(pdf, label, val, val_color=C_DARK):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*C_GRAY)
            pdf.cell(65, 6, sf(label))
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*val_color)
            pdf.cell(0, 6, sf(val), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*C_DARK)

        def _sep(pdf):
            pdf.set_draw_color(226, 232, 240)
            pdf.line(pdf.l_margin, pdf.get_y(),
                     pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)

        def _tbl_header(pdf, cols, widths):
            pdf.set_fill_color(*C_HEAD)
            pdf.set_text_color(*C_WHITE)
            pdf.set_font("Helvetica", "B", 8)
            for h, w in zip(cols, widths):
                pdf.cell(w, 6, sf(h), border=0, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(*C_DARK)

        def _tbl_row(pdf, vals, widths, i, aligns=None):
            bg = C_LIGHT if i % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)
            pdf.set_font("Helvetica", "", 8)
            aligns = aligns or ["C"] * len(vals)
            for v, w, a in zip(vals, widths, aligns):
                pdf.cell(w, 5.5, sf(str(v)), border=0, fill=True, align=a)
            pdf.ln()

        # ── datos ─────────────────────────────────────────────────────────────
        total        = d["total"]
        n            = d["n"]
        ticket       = d["ticket"]
        costo_sin    = d.get("costo", 0.0)
        sin_iva      = total / 1.16
        iva          = total - sin_iva
        costo_con    = costo_sin * 1.16
        ganancia     = sin_iva - costo_sin
        margen_pct   = (ganancia / sin_iva * 100) if sin_iva else 0.0

        # Órdenes para el corte (filtro por fecha ISO en texto, a prueba de fechas vacías)
        iso_ini = dmy_to_iso(fi_str)
        iso_fin = dmy_to_iso(ff_str)
        orders_period = {}
        if iso_ini and iso_fin:
            for oid, o in self.data_orders.items():
                d_iso = o.get("Fecha_iso") or dmy_to_iso(o.get("Fecha", ""))
                if d_iso and iso_ini <= d_iso <= iso_fin:
                    orders_period[oid] = o

        # Método de pago
        pago_cnt = {}
        for o in orders_period.values():
            mp = str(o.get("Metodo_pago", "—"))
            pago_cnt[mp] = pago_cnt.get(mp, 0) + 1

        # Descuentos
        total_desc = 0.0
        n_con_desc = 0
        for o in orders_period.values():
            for pid, pi in o.get("Productos", {}).items():
                da = float(pi.get("Descuento_monto", 0) or 0)
                if da > 0:
                    total_desc += da
                    n_con_desc += 1
        # fallback: from order_items in DB
        if total_desc == 0:
            try:
                ids_q = ",".join(f"'{oid}'" for oid in orders_period.keys())
                if ids_q:
                    rows_d = self.db.conn.execute(
                        f"SELECT SUM(discount_amount) as s, "
                        f"COUNT(CASE WHEN discount_amount>0 THEN 1 END) as c "
                        f"FROM order_items WHERE order_id IN ({ids_q})"
                    ).fetchone()
                    if rows_d:
                        total_desc = float(rows_d["s"] or 0)
                        n_con_desc = int(rows_d["c"] or 0)
            except Exception:
                log_exc("_tbl_row")

        # Corte detallado de productos (desde DB para tener descuentos)
        corte_prods = {}
        try:
            ids_q = ",".join(f"'{oid}'" for oid in orders_period.keys())
            if ids_q:
                corte_rows = self.db.conn.execute(
                    f"SELECT product_id, SUM(quantity) as qty, "
                    f"SUM(amount) as total_amt, "
                    f"SUM(discount_amount) as total_disc "
                    f"FROM order_items WHERE order_id IN ({ids_q}) "
                    f"GROUP BY product_id ORDER BY qty DESC"
                ).fetchall()
                for cr in corte_rows:
                    pid = str(cr["product_id"])
                    p   = self.data_products.get(pid)
                    nm  = f"{p[2]} ({p[5]})" if p and p[5] else (p[2] if p else pid)
                    sku = p[0] if p else "—"
                    corte_prods[pid] = {
                        "sku": str(sku), "name": nm,
                        "qty": int(cr["qty"]),
                        "amount": float(cr["total_amt"] or 0),
                        "disc":   float(cr["total_disc"] or 0),
                    }
        except Exception:
            log_exc("_tbl_row")

        # ── construir PDF ─────────────────────────────────────────────────────
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        _rpt_name = f"reporte_analisis_{ts}.pdf"

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.set_margins(12, 12, 12)
        pdf.core_fonts_encoding = "windows-1252"
        W = 186   # usable width

        # ══════════════ PÁGINA 1: PORTADA + RESUMEN ══════════════════════════
        pdf.add_page()

        # Encabezado portada
        pdf.set_fill_color(*C_HEAD)
        pdf.rect(0, 0, 210, 28, "F")
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_y(6)
        pdf.cell(0, 8, "ORTOPEDIA BIOMED", align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, sf(f"Reporte de Análisis de Ventas  |  {fi_str}  —  {ff_str}"),
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # ── KPIs tarjetas (2 filas x 3 cols) ─────────────────────────────────
        pdf.set_text_color(*C_DARK)
        kpi_w = W / 3
        kpi_h = 22

        def _kpi_card(pdf, x, y, title, value, color):
            pdf.set_fill_color(*C_LIGHT)
            pdf.rect(x, y, kpi_w - 2, kpi_h, "F")
            pdf.set_draw_color(226, 232, 240)
            pdf.rect(x, y, kpi_w - 2, kpi_h, "D")
            pdf.set_xy(x, y + 2)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*C_GRAY)
            pdf.cell(kpi_w - 2, 5, sf(title), align="C")
            pdf.set_xy(x, y + 8)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*color)
            pdf.cell(kpi_w - 2, 8, sf(value), align="C")
            pdf.set_text_color(*C_DARK)

        row1_y = pdf.get_y()
        _kpi_card(pdf, 12,              row1_y, "VENTA TOTAL (c/IVA)",
                  f"$ {total:,.2f}", C_GREEN)
        _kpi_card(pdf, 12 + kpi_w,      row1_y, "VENTA SIN IVA",
                  f"$ {sin_iva:,.2f}", C_BLUE)
        _kpi_card(pdf, 12 + kpi_w * 2,  row1_y, "IVA COBRADO",
                  f"$ {iva:,.2f}", C_GRAY)

        row2_y = row1_y + kpi_h + 3
        _kpi_card(pdf, 12,              row2_y, "GANANCIA BRUTA",
                  f"$ {ganancia:,.2f}", C_PURPLE)
        _kpi_card(pdf, 12 + kpi_w,      row2_y, "COSTO PRODUCTOS",
                  f"$ {costo_sin:,.2f}", C_RED)
        _kpi_card(pdf, 12 + kpi_w * 2,  row2_y, "MARGEN BRUTO",
                  f"{margen_pct:.1f}%", C_WARN)

        pdf.set_y(row2_y + kpi_h + 5)

        # ── Indicadores operativos ────────────────────────────────────────────
        _sec_title(pdf, "  INDICADORES OPERATIVOS")
        op_cols = [("Órdenes",        str(n),                      C_DARK),
                   ("Ticket prom.",   f"$ {ticket:,.2f}",          C_BLUE),
                   ("Desc. totales",  f"$ {total_desc:,.2f}",      C_RED),
                   ("Líneas c/desc.", str(n_con_desc),              C_WARN)]
        col_w2 = W / 4
        for j, (lbl, val, col) in enumerate(op_cols):
            x_op = 12 + j * col_w2
            y_op = pdf.get_y()
            pdf.set_xy(x_op, y_op)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*C_GRAY)
            pdf.cell(col_w2, 5, sf(lbl), align="C")
            pdf.set_xy(x_op, y_op + 5)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*col)
            pdf.cell(col_w2, 7, sf(val), align="C")
        pdf.set_text_color(*C_DARK)
        pdf.ln(17)

        # Método de pago
        _sep(pdf)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_GRAY)
        pdf.cell(0, 5, "Método de pago:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for mp, cnt in sorted(pago_cnt.items(), key=lambda x: -x[1]):
            pdf.set_text_color(*C_DARK)
            pdf.cell(40, 5, sf(mp))
            pdf.set_text_color(*C_BLUE)
            pdf.cell(0, 5, str(cnt) + " ventas", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*C_DARK)
        pdf.ln(3)

        # ══════════════ SECCIÓN: TOP PRODUCTOS ═══════════════════════════════
        _sec_title(pdf, "  TOP PRODUCTOS — Por ingreso bruto")
        top_rev = sorted(d.get("por_cantidad", []),
                         key=lambda x: x["revenue"], reverse=True)[:15]
        _tbl_header(pdf, ["SKU","Producto","Pzas","P.Unit.","Ingreso"],
                    [22, 90, 16, 30, 28])
        for i, p in enumerate(top_rev):
            _tbl_row(pdf,
                     [p["sku"], p["name"][:48], p["qty"],
                      f"$ {p['price']:,.2f}", f"$ {p['revenue']:,.2f}"],
                     [22, 90, 16, 30, 28], i,
                     aligns=["C","L","C","R","R"])

        pdf.ln(4)
        _sec_title(pdf, "  TOP PRODUCTOS — Por unidades vendidas")
        top_qty = sorted(d.get("por_cantidad", []),
                         key=lambda x: x["qty"], reverse=True)[:15]
        _tbl_header(pdf, ["SKU","Producto","Pzas","Ingreso"],
                    [22, 104, 16, 44])
        for i, p in enumerate(top_qty):
            _tbl_row(pdf,
                     [p["sku"], p["name"][:55], p["qty"],
                      f"$ {p['revenue']:,.2f}"],
                     [22, 104, 16, 44], i,
                     aligns=["C","L","C","R"])

        # ══════════════ SECCIÓN: CORTE / DETALLE PRODUCTOS ═══════════════════
        pdf.add_page()
        _sec_title(pdf, "  CORTE — DETALLE DE PRODUCTOS VENDIDOS")
        W6 = [22, 82, 16, 24, 22, 20]
        _tbl_header(pdf,
                    ["SKU","Producto","Pzas","Importe","Desc.","Neto"],
                    W6)
        grand_amt  = 0.0
        grand_disc = 0.0
        for i, cp in enumerate(corte_prods.values()):
            neto = cp["amount"] - cp["disc"]
            grand_amt  += cp["amount"]
            grand_disc += cp["disc"]
            _tbl_row(pdf,
                     [cp["sku"], cp["name"][:44], cp["qty"],
                      f"$ {cp['amount']:,.2f}",
                      f"$ {cp['disc']:,.2f}" if cp["disc"] else "—",
                      f"$ {neto:,.2f}"],
                     W6, i, aligns=["C","L","C","R","R","R"])

        # Totales del corte
        grand_neto = grand_amt - grand_disc
        pdf.set_fill_color(*C_HEAD)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(sum(W6[:4]), 6, sf(f"  TOTAL  Importe: $ {grand_amt:,.2f}"),
                 fill=True, align="L")
        pdf.cell(W6[4], 6, sf(f"$ {grand_disc:,.2f}"), fill=True, align="R")
        pdf.cell(W6[5], 6, sf(f"$ {grand_neto:,.2f}"), fill=True, align="R")
        pdf.ln()
        pdf.set_text_color(*C_DARK)
        pdf.ln(4)

        # ══════════════ SECCIÓN: CLIENTES ════════════════════════════════════
        _sec_title(pdf, "  TOP CLIENTES")
        cli_sorted = sorted(d.get("Cliente", {}).items(),
                            key=lambda x: -x[1]["ventas"])[:20]
        _tbl_header(pdf, ["Cliente","Ventas","Órdenes","Ticket prom."],
                    [80, 38, 28, 40])
        for i, (cname, cd) in enumerate(cli_sorted):
            _tbl_row(pdf,
                     [cname, f"$ {cd['ventas']:,.2f}",
                      cd["n"], f"$ {cd['ticket']:,.2f}"],
                     [80, 38, 28, 40], i,
                     aligns=["L","R","C","R"])

        pdf.ln(4)

        # ══════════════ SECCIÓN: USUARIOS ════════════════════════════════════
        _sec_title(pdf, "  VENTAS POR USUARIO / VENDEDOR")
        usr_sorted = sorted(d.get("Usuario", {}).items(),
                            key=lambda x: -x[1]["ventas"])
        _tbl_header(pdf, ["Vendedor","Ventas","Órdenes","Ticket prom."],
                    [80, 38, 28, 40])
        for i, (uname, ud) in enumerate(usr_sorted):
            _tbl_row(pdf,
                     [uname, f"$ {ud['ventas']:,.2f}",
                      ud["n"], f"$ {ud['ticket']:,.2f}"],
                     [80, 38, 28, 40], i,
                     aligns=["L","R","C","R"])

        pdf.ln(4)

        # ══════════════ SECCIÓN: DÍA Y HORA ══════════════════════════════════
        _sec_title(pdf, "  VENTAS POR DÍA DE SEMANA")
        dia_data = d.get("Día", {})
        _tbl_header(pdf, ["Día","Ventas","Órdenes","Ticket prom."],
                    [50, 50, 40, 46])
        for i, (dia, dd) in enumerate(dia_data.items()):
            _tbl_row(pdf,
                     [dia, f"$ {dd['ventas']:,.2f}",
                      dd["n"], f"$ {dd['ticket']:,.2f}"],
                     [50, 50, 40, 46], i,
                     aligns=["L","R","C","R"])

        pdf.ln(3)
        _sec_title(pdf, "  VENTAS POR HORA DEL DÍA")
        hora_data = d.get("Hora", {})
        _tbl_header(pdf, ["Hora","Ventas","Órdenes","Ticket prom."],
                    [40, 54, 38, 54])
        for i, (hora, hd) in enumerate(hora_data.items()):
            _tbl_row(pdf,
                     [hora, f"$ {hd['ventas']:,.2f}",
                      hd["n"], f"$ {hd['ticket']:,.2f}"],
                     [40, 54, 38, 54], i,
                     aligns=["L","R","C","R"])

        pdf.ln(4)

        # ══════════════ SECCIÓN: CATEGORÍA Y MARCA ═══════════════════════════
        _sec_title(pdf, "  VENTAS POR CATEGORÍA")
        cat_data = d.get("Categoría", {})
        _tbl_header(pdf, ["Categoría","Ventas","% del total","Órdenes"],
                    [70, 42, 38, 36])
        total_v = sum(v["ventas"] for v in cat_data.values()) or 1
        for i, (cat, cd) in enumerate(
                sorted(cat_data.items(), key=lambda x: -x[1]["ventas"])):
            pct = cd["ventas"] / total_v * 100
            _tbl_row(pdf,
                     [cat, f"$ {cd['ventas']:,.2f}", f"{pct:.1f}%", cd["n"]],
                     [70, 42, 38, 36], i,
                     aligns=["L","R","C","C"])

        pdf.ln(3)
        _sec_title(pdf, "  VENTAS POR MARCA")
        marca_data = d.get("Marca", {})
        total_m = sum(v["ventas"] for v in marca_data.values()) or 1
        _tbl_header(pdf, ["Marca","Ventas","% del total","Órdenes"],
                    [70, 42, 38, 36])
        for i, (marca, md) in enumerate(
                sorted(marca_data.items(), key=lambda x: -x[1]["ventas"])):
            pct = md["ventas"] / total_m * 100
            _tbl_row(pdf,
                     [marca, f"$ {md['ventas']:,.2f}", f"{pct:.1f}%", md["n"]],
                     [70, 42, 38, 36], i,
                     aligns=["L","R","C","C"])

        # ══════════════ PÁGINA DE GRÁFICAS ════════════════════════════════════
        if _MPL and getattr(self, "_an_charts", None):
            import io
            pdf.add_page()
            _sec_title(pdf, "  GRÁFICAS DE VENTAS")
            chart_order = ["Usuario","Cliente","Día","Hora","Categoría","Marca"]
            img_w = (W - 4) / 2   # 2 por fila
            img_h = 65
            col_idx = 0
            row_y   = pdf.get_y() + 2
            for key in chart_order:
                if key not in self._an_charts:
                    continue
                fig, canvas, _ = self._an_charts[key]
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=110,
                            bbox_inches="tight", facecolor=fig.get_facecolor())
                buf.seek(0)
                x_img = 12 + col_idx * (img_w + 4)
                try:
                    pdf.image(buf, x=x_img, y=row_y,
                              w=img_w, h=img_h)
                except Exception:
                    log_exc("_kpi_card")
                col_idx += 1
                if col_idx == 2:
                    col_idx = 0
                    row_y += img_h + 4
                    if row_y + img_h > 270:
                        pdf.add_page()
                        _sec_title(pdf, "  GRÁFICAS DE VENTAS (cont.)")
                        row_y = pdf.get_y() + 2

        # ══════════════ PIE DE PÁGINA ══════════════════════════════════════════
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*C_GRAY)

        # ── guardar en Descargas y abrir ──────────────────────────────────────
        out = self._pdf_save_and_open(pdf, _rpt_name)
        messagebox.showinfo("Reporte generado",
                            f"PDF guardado en Descargas:\n{os.path.basename(out)}")

    def _render_charts(self):
        if not _MPL or not getattr(self, "_an_charts", None):
            return

        BAR_COLORS = ["#2563EB","#059669","#D97706","#DC2626","#7C3AED",
                      "#0891B2","#B45309","#0F172A","#1E40AF","#065F46"]
        PIE_COLORS = ["#2563EB","#059669","#D97706","#DC2626","#7C3AED",
                      "#0891B2","#B45309","#9F1239","#065F46","#1E3A8A"]

        for key, (fig, canvas, chart_type) in self._an_charts.items():
            fig.clear()
            data = (self._an_data or {}).get(key, {})

            if chart_type == "bar":
                ax = fig.add_subplot(111)
                ax.set_facecolor("#F8FAFC")
                if data:
                    names  = list(data.keys())
                    values = [d["ventas"] for d in data.values()]
                    clrs   = (BAR_COLORS * (len(values) // len(BAR_COLORS) + 1))[:len(values)]
                    bars   = ax.bar(names, values, color=clrs,
                                    edgecolor="white", linewidth=0.8, width=0.6)
                    max_v  = max(values) if values else 1
                    ax.set_ylim(0, max_v * 1.22)
                    for bar, val in zip(bars, values):
                        ax.text(bar.get_x() + bar.get_width() / 2,
                                bar.get_height() + max_v * 0.02,
                                f"${val:,.0f}",
                                ha="center", va="bottom", fontsize=9, color="#0F172A")
                    ax.yaxis.set_major_formatter(
                        mticker.FuncFormatter(lambda x, _: f"${x/1000:.1f}k" if x >= 1000 else f"${x:.0f}"))
                    ax.tick_params(axis="x", labelsize=10, rotation=30)
                    ax.tick_params(axis="y", labelsize=10)
                else:
                    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center",
                            transform=ax.transAxes, fontsize=14, color="#64748B")
                ax.set_title(f"Ventas por {key}", fontsize=13, fontweight="bold",
                             pad=12, color="#0F172A")
                for sp in ["top", "right"]:
                    ax.spines[sp].set_visible(False)
                ax.spines["left"].set_color("#E2E8F0")
                ax.spines["bottom"].set_color("#E2E8F0")
                fig.tight_layout(pad=1.8)

            elif chart_type == "pie":
                ax = fig.add_subplot(111)
                ax.set_facecolor(BG_PANEL)
                if data:
                    labels = list(data.keys())
                    values = [d["ventas"] for d in data.values()]
                    clrs   = (PIE_COLORS * (len(values) // len(PIE_COLORS) + 1))[:len(values)]
                    wedges, texts, autotexts = ax.pie(
                        values, labels=labels, colors=clrs,
                        autopct="%1.1f%%", pctdistance=0.75,
                        textprops={"fontsize": 10},
                        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
                        startangle=140)
                    for at in autotexts:
                        at.set_fontsize(9)
                        at.set_color("white")
                        at.set_fontweight("bold")
                else:
                    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center",
                            transform=ax.transAxes, fontsize=14, color="#64748B")
                ax.set_title(f"Ventas por {key}", fontsize=13, fontweight="bold",
                             pad=12, color="#0F172A")
                fig.tight_layout(pad=1.8)

            elif chart_type == "summary":
                ax = fig.add_subplot(111)
                ax.axis("off")
                ax.set_facecolor(BG_PANEL)
                d = self._an_data
                if d and d.get("n", 0) > 0:
                    sin_iva      = d["total"] / 1.16
                    iva          = d["total"] - sin_iva
                    costo_sin    = d.get("costo", 0.0)
                    costo_con    = costo_sin * 1.16

                    def _row(y, lbl, val, lbl_col="#64748B", val_col="#0F172A",
                             lbl_size=10, val_size=11, bold=False):
                        weight = "bold" if bold else "normal"
                        ax.text(0.04, y, lbl, ha="left", va="center",
                                transform=ax.transAxes,
                                fontsize=lbl_size, color=lbl_col)
                        ax.text(0.96, y, val, ha="right", va="center",
                                transform=ax.transAxes,
                                fontsize=val_size, fontweight=weight, color=val_col)

                    def _sep(y):
                        ax.axhline(y=y, xmin=0.02, xmax=0.98,
                                   color="#E2E8F0", linewidth=1.0)

                    ganancia_bruta = sin_iva - costo_sin

                    # Título
                    ax.text(0.5, 0.97, "RESUMEN DEL PERÍODO",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=11, fontweight="bold", color="#64748B")

                    _sep(0.92)

                    # Ventas
                    ax.text(0.5, 0.88, "VENTAS",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=9, fontweight="bold", color="#94A3B8")
                    _row(0.82, "Con IVA",  f"$ {d['total']:,.2f}",
                         val_col="#059669", val_size=13, bold=True)
                    _row(0.75, "Sin IVA",  f"$ {sin_iva:,.2f}",
                         val_col="#059669", val_size=12)
                    _row(0.68, "IVA (16%)", f"$ {iva:,.2f}",
                         val_col="#64748B", val_size=10)

                    _sep(0.63)

                    # Ganancia bruta
                    ax.text(0.5, 0.59, "GANANCIA BRUTA",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=9, fontweight="bold", color="#94A3B8")
                    _row(0.52, "Ventas sin IVA − Costo sin IVA",
                         f"$ {ganancia_bruta:,.2f}",
                         val_col="#7C3AED", val_size=13, bold=True)

                    _sep(0.46)

                    # Costo
                    ax.text(0.5, 0.42, "COSTO PRODUCTOS VENDIDOS",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=9, fontweight="bold", color="#94A3B8")
                    _row(0.36, "Sin IVA",  f"$ {costo_sin:,.2f}",
                         val_col="#DC2626", val_size=12)
                    _row(0.29, "Con IVA",  f"$ {costo_con:,.2f}",
                         val_col="#DC2626", val_size=13, bold=True)

                    _sep(0.23)

                    # Órdenes y ticket
                    ax.text(0.5, 0.19, "OPERACIONES",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=9, fontweight="bold", color="#94A3B8")
                    _row(0.13, "Órdenes",        f"{d['n']}",
                         val_col="#0F172A", val_size=12, bold=True)
                    _row(0.06, "Ticket promedio", f"$ {d['ticket']:,.2f}",
                         val_col="#2563EB", val_size=11)

                    for spine in ax.spines.values():
                        spine.set_visible(True)
                        spine.set_color("#E2E8F0")
                        spine.set_linewidth(0.6)
                else:
                    ax.text(0.5, 0.5, "Sin datos en el período",
                            ha="center", va="center", transform=ax.transAxes,
                            fontsize=14, color="#64748B")
                fig.tight_layout(pad=2.0)

            canvas.draw()

    # ══════════════════════════════════════════════════════════════════════════
    # CHECADOR
    # ══════════════════════════════════════════════════════════════════════════
    def opcion_checador(self):
        self._current_screen = self.opcion_checador
        sw, sh = self.screen_width, self.screen_height

        # Cancelar reloj anterior y activar flag
        self._chk_running = True
        if hasattr(self, "_chk_clock_id") and self._chk_clock_id:
            try:
                self.root.after_cancel(self._chk_clock_id)
            except Exception:
                log_exc("opcion_checador")
        self._chk_clock_id = None

        self.frame_checador = tk.Frame(self.root, bg=BG_MAIN)
        self.frame_checador.place(x=int(sw * 0.1), y=0,
                                  width=int(sw * 0.9), height=sh)
        pw = int(sw * 0.9)
        hh = int(sh * 0.07)

        self._header(self.frame_checador, "Checador",
                     subtitle="Control de asistencia")

        today = datetime.now().strftime("%d/%m/%Y")
        gap   = int(sh * 0.010)

        # Content area boundaries
        cy = hh + gap
        ch = sh - cy - gap

        # Column widths
        lx = int(pw * 0.012)
        lw = int(pw * 0.435)
        rx = lx + lw + gap
        rw = pw - rx - int(pw * 0.012)

        # ── LEFT: employee grid ────────────────────────────────────────────
        emp_panel = tk.Frame(self.frame_checador, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        emp_panel.place(x=lx, y=cy, width=lw, height=ch)

        # Header of employee panel
        ep_hdr = tk.Frame(emp_panel, bg=BG_PANEL)
        ep_hdr.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(ep_hdr, text="USUARIOS", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Frame(emp_panel, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(emp_panel,
                 text="  Doble clic en el nombre para registrar entrada / salida",
                 bg=BG_PANEL, fg=TXT_GRAY, font=("Arial", 8),
                 anchor="w").pack(fill="x", padx=10, pady=(4, 8))

        # Scrollable grid container
        emp_canvas = tk.Canvas(emp_panel, bg=BG_PANEL, highlightthickness=0)
        emp_vsb    = ttk.Scrollbar(emp_panel, orient="vertical",
                                   command=emp_canvas.yview)
        emp_canvas.configure(yscrollcommand=emp_vsb.set)
        emp_vsb.pack(side="right", fill="y")
        emp_canvas.pack(fill="both", expand=True)

        emp_grid_frame = tk.Frame(emp_canvas, bg=BG_PANEL)
        _egf_id = emp_canvas.create_window((0, 0), window=emp_grid_frame, anchor="nw")

        def _on_egf_configure(e):
            emp_canvas.configure(scrollregion=emp_canvas.bbox("all"))
        def _on_ecanvas_configure(e):
            emp_canvas.itemconfig(_egf_id, width=e.width)
        emp_grid_frame.bind("<Configure>", _on_egf_configure)
        emp_canvas.bind("<Configure>",     _on_ecanvas_configure)

        # Fetch employees below Gerente (access_level > 1), activos, omitir "prueba"
        emp_list = [
            (r["username"], r["id"], r["pin"])
            for r in self.db.get_users_full()
            if int(r["access_level"]) > 1
            and int(r["activo"] if r["activo"] is not None else 1) == 1
            and r["username"].strip().lower() != "prueba"
        ]

        def _is_active(uid):
            row = self.db.conn.execute(
                "SELECT tipo FROM checadas WHERE user_id=? AND date=? ORDER BY id DESC LIMIT 1",
                (uid, today)).fetchone()
            return row is not None and row["tipo"] == "entrada"

        def _render_emp_grid():
            for w in emp_grid_frame.winfo_children():
                w.destroy()

            COLS = 2
            for idx, (name, uid, pin) in enumerate(emp_list):
                r, c = divmod(idx, COLS)
                active = _is_active(uid)

                # Color scheme
                if active:
                    card_bg  = "#DCFCE7"
                    brd_col  = "#86EFAC"
                    dot_col  = "#16A34A"
                    status   = "● En turno"
                    st_col   = "#15803D"
                else:
                    card_bg  = "#F8FAFC"
                    brd_col  = "#CBD5E1"
                    dot_col  = "#94A3B8"
                    status   = "○ Fuera"
                    st_col   = TXT_GRAY

                cell = tk.Frame(emp_grid_frame, bg=card_bg,
                                highlightbackground=brd_col,
                                highlightthickness=2, cursor="hand2")
                cell.grid(row=r, column=c, padx=8, pady=6, sticky="nsew")
                emp_grid_frame.grid_columnconfigure(c, weight=1)

                tk.Label(cell, text="⬤", bg=card_bg, fg=dot_col,
                         font=("Arial", 12)).pack(pady=(14, 2))
                tk.Label(cell, text=name, bg=card_bg, fg=TXT_MAIN,
                         font=("Arial", 13, "bold"), wraplength=140).pack(pady=2)
                tk.Label(cell, text=status, bg=card_bg, fg=st_col,
                         font=("Arial", 9)).pack(pady=(0, 14))

                def _dbl(event, _uid=uid, _name=name, _pin=pin):
                    _pin_dialog(_uid, _name, _pin)

                for w in [cell] + list(cell.winfo_children()):
                    w.bind("<Double-Button-1>", _dbl)

        def _pin_dialog(uid, name, correct_pin):
            """PIN confirmation popup for check-in / check-out."""
            active = _is_active(uid)
            action = "salida" if active else "entrada"
            act_lbl = "Registrar Salida" if active else "Registrar Entrada"
            act_col = DANGER if active else SUCCESS

            dw, dh = 330, 390
            sx = self.root.winfo_x() + (self.root.winfo_width()  - dw) // 2
            sy = self.root.winfo_y() + (self.root.winfo_height() - dh) // 2

            dlg = tk.Toplevel(self.root)
            dlg.title("Registro de asistencia")
            dlg.resizable(False, False)
            dlg.geometry(f"{dw}x{dh}+{sx}+{sy}")
            dlg.configure(bg=BG_PANEL)
            dlg.transient(self.root)
            if platform.system() != "Linux":
                dlg.overrideredirect(True)
            dlg.grab_set()
            dlg.lift()
            dlg.focus_force()

            # Shadow border
            outer = tk.Frame(dlg, bg=BORDER, highlightbackground=BORDER,
                             highlightthickness=1)
            outer.place(x=0, y=0, width=dw, height=dh)

            inner = tk.Frame(outer, bg=BG_PANEL)
            inner.place(x=1, y=1, width=dw-2, height=dh-2)

            # Close button
            close_btn = tk.Label(inner, text="✕", bg=BG_PANEL, fg=TXT_GRAY,
                                 font=("Arial", 13), cursor="hand2")
            close_btn.place(relx=1.0, x=-28, y=8)
            close_btn.bind("<Button-1>", lambda _e: dlg.destroy())

            # Mini digital clock
            mini_clk = tk.Label(inner, text="", bg=BG_PANEL, fg=PRIMARY,
                                font=("Courier", 20, "bold"))
            mini_clk.place(x=0, y=8, width=dw-2)

            def _tick_dlg():
                try:
                    mini_clk.config(text=datetime.now().strftime("%H : %M : %S"))
                    dlg.after(1000, _tick_dlg)
                except tk.TclError:
                    pass
            _tick_dlg()

            # Dot + name
            dot_c = DANGER if active else SUCCESS
            tk.Label(inner, text="⬤", bg=BG_PANEL, fg=dot_c,
                     font=("Arial", 18)).place(x=0, y=62, width=dw-2)
            tk.Label(inner, text=name, bg=BG_PANEL, fg=TXT_MAIN,
                     font=("Arial", 17, "bold")).place(x=0, y=90, width=dw-2)
            tk.Label(inner, text=act_lbl, bg=BG_PANEL, fg=act_col,
                     font=("Arial", 11, "bold")).place(x=0, y=120, width=dw-2)

            tk.Frame(inner, bg=BORDER, height=1).place(x=20, y=148,
                                                        width=dw-42)
            tk.Label(inner, text="Ingresa tu PIN", bg=BG_PANEL, fg=TXT_GRAY,
                     font=("Arial", 10)).place(x=0, y=158, width=dw-2)

            pin_var = tk.StringVar()
            pin_entry = tk.Entry(inner, textvariable=pin_var, show="●",
                                 font=("Arial", 22, "bold"), justify="center",
                                 relief="flat", bg=BG_MAIN, fg=TXT_MAIN,
                                 insertbackground=PRIMARY,
                                 highlightbackground=BORDER, highlightthickness=1)
            pin_entry.place(x=36, y=186, width=dw-74, height=52)
            pin_entry.focus_force()

            err_lbl = tk.Label(inner, text="", bg=BG_PANEL, fg=DANGER,
                               font=("Arial", 10))
            err_lbl.place(x=0, y=246, width=dw-2)

            def _validar(event=None):
                entered = pin_var.get().strip()
                if entered == correct_pin:
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.db.conn.execute(
                        "INSERT INTO checadas(user_id,username,tipo,timestamp,date)"
                        " VALUES(?,?,?,?,?)",
                        (uid, name, action, ts, today))
                    self.db.conn.commit()
                    dlg.destroy()
                    _render_emp_grid()
                    _refresh_activity()
                else:
                    err_lbl.config(text="PIN incorrecto")
                    pin_var.set("")
                    pin_entry.focus_force()

            pin_entry.bind("<Return>", _validar)

            btn_frame = tk.Frame(inner, bg=BG_PANEL)
            btn_frame.place(x=24, y=290, width=dw-50)

            self._btn(btn_frame, act_lbl, _validar,
                      bg=act_col, font_size=12
                      ).pack(fill="x", ipady=8)
            self._btn(btn_frame, "Cancelar", dlg.destroy,
                      bg=TXT_GRAY, font_size=11
                      ).pack(fill="x", ipady=5, pady=(8, 0))

        _render_emp_grid()

        # ── RIGHT: clock + activity + notes ───────────────────────────────

        # ── Clock ─────────────────────────────────────────────────────────
        clk_h = int(ch * 0.20)
        clk_panel = tk.Frame(self.frame_checador, bg=BG_SIDEBAR,
                             highlightbackground="#334155", highlightthickness=1)
        clk_panel.place(x=rx, y=cy, width=rw, height=clk_h)

        DIAS_FULL  = ["Lunes","Martes","Miércoles","Jueves",
                      "Viernes","Sábado","Domingo"]
        MESES_FULL = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                      "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

        date_lbl = tk.Label(clk_panel, text="", bg=BG_SIDEBAR, fg="#64748B",
                            font=("Arial", 10))
        date_lbl.pack(pady=(8, 0))

        clk_lbl = tk.Label(clk_panel, text="00:00:00",
                           bg=BG_SIDEBAR, fg="#F1F5F9",
                           font=("Courier", int(clk_h * 0.42), "bold"))
        clk_lbl.pack(expand=True)

        def _tick():
            if not getattr(self, "_chk_running", False):
                return
            try:
                now = datetime.now()
                clk_lbl.config(text=now.strftime("%H:%M:%S"))
                date_lbl.config(
                    text=f"{DIAS_FULL[now.weekday()]}  "
                         f"{now.day} de {MESES_FULL[now.month-1]} {now.year}")
            except Exception:
                self._chk_running = False
                return
            self._chk_clock_id = self.root.after(1000, _tick)
        _tick()

        # ── Activity ──────────────────────────────────────────────────────
        act_y = cy + clk_h + gap
        act_h = int(ch * 0.40)
        act_panel = tk.Frame(self.frame_checador, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        act_panel.place(x=rx, y=act_y, width=rw, height=act_h)

        tk.Label(act_panel, text="ACTIVIDAD DEL DÍA", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=12, pady=(8, 0))
        tk.Frame(act_panel, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(4,0))

        act_inner = tk.Frame(act_panel, bg=BG_PANEL)
        act_inner.pack(fill="both", expand=True, padx=6, pady=4)

        act_list = tk.Listbox(act_inner, bg=BG_PANEL, fg=TXT_MAIN,
                              font=("Arial", 10), relief="flat",
                              selectbackground="#EFF6FF",
                              activestyle="none",
                              highlightthickness=0, bd=0)
        act_sb = ttk.Scrollbar(act_inner, orient="vertical",
                               command=act_list.yview)
        act_list.config(yscrollcommand=act_sb.set)
        act_sb.pack(side="right", fill="y")
        act_list.pack(fill="both", expand=True)

        def _refresh_activity():
            act_list.delete(0, tk.END)
            # Caja
            try:
                caja_st = self.db.conn.execute(
                    "SELECT value FROM app_state WHERE key='caja'").fetchone()
                caja_hr = self.db.conn.execute(
                    "SELECT value FROM app_state WHERE key='caja_hora'").fetchone()
                caja_mn = self.db.conn.execute(
                    "SELECT value FROM app_state WHERE key='efectivo'").fetchone()
                if caja_st and caja_st["value"] == "Abierta":
                    hr_txt = caja_hr["value"] if caja_hr else "—"
                    try:
                        mn_fmt = f"$ {float(caja_mn['value']):,.2f}" if caja_mn else "—"
                    except Exception:
                        mn_fmt = "—"
                    act_list.insert(tk.END,
                        f"🏪  Caja abierta   {hr_txt}   ({mn_fmt})")
                    act_list.itemconfig(tk.END, fg=SUCCESS)
            except Exception:
                log_exc("_refresh_activity")
            # Check-ins / check-outs
            rows = self.db.conn.execute(
                "SELECT username, tipo, timestamp FROM checadas"
                " WHERE date=? ORDER BY id DESC",
                (today,)).fetchall()
            for r in rows:
                icon  = "🟢" if r["tipo"] == "entrada" else "🔴"
                lbl   = "Entrada" if r["tipo"] == "entrada" else "Salida"
                line  = f"{icon}  {r['username']}  —  {lbl}   {r['timestamp']}"
                col   = "#15803D" if r["tipo"] == "entrada" else DANGER
                act_list.insert(tk.END, line)
                act_list.itemconfig(tk.END, fg=col)

        _refresh_activity()

        # ── Notes ─────────────────────────────────────────────────────────
        nts_y = act_y + act_h + gap
        nts_h = cy + ch - nts_y
        nts_panel = tk.Frame(self.frame_checador, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        nts_panel.place(x=rx, y=nts_y, width=rw, height=nts_h)

        # ── Header ────────────────────────────────────────────────────────────
        nts_hdr = tk.Frame(nts_panel, bg=BG_PANEL)
        nts_hdr.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(nts_hdr, text="NOTAS Y PENDIENTES", bg=BG_PANEL, fg=TXT_GRAY,
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Frame(nts_panel, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(4, 0))

        # Leyenda de colores
        leg = tk.Frame(nts_panel, bg=BG_PANEL)
        leg.pack(fill="x", padx=10, pady=(3, 0))
        tk.Label(leg, text="📝 Nota", bg=BG_PANEL, fg=PRIMARY,
                 font=("Arial", 8)).pack(side="left", padx=(0, 12))
        tk.Label(leg, text="⏳ Pendiente", bg=BG_PANEL, fg=WARNING,
                 font=("Arial", 8)).pack(side="left")

        # ── Lista ─────────────────────────────────────────────────────────────
        nts_inner = tk.Frame(nts_panel, bg=BG_PANEL)
        nts_inner.pack(fill="both", expand=True, padx=6, pady=(4, 0))

        nts_list = tk.Listbox(nts_inner, bg=BG_PANEL, fg=TXT_MAIN,
                              font=("Arial", 10), relief="flat",
                              selectbackground="#EFF6FF",
                              activestyle="none",
                              highlightthickness=0, bd=0)
        nts_sb = ttk.Scrollbar(nts_inner, orient="vertical",
                               command=nts_list.yview)
        nts_list.config(yscrollcommand=nts_sb.set)
        nts_sb.pack(side="right", fill="y")
        nts_list.pack(fill="both", expand=True)

        # ── Entrada de texto ──────────────────────────────────────────────────
        inp_frame = tk.Frame(nts_panel, bg=BG_PANEL)
        inp_frame.pack(fill="x", padx=8, pady=(4, 8))

        note_var   = tk.StringVar()
        note_entry = tk.Entry(inp_frame, textvariable=note_var,
                              font=("Arial", 10), relief="flat",
                              bg=BG_MAIN, fg=TXT_MAIN,
                              insertbackground=PRIMARY,
                              highlightbackground=BORDER, highlightthickness=1)
        note_entry.pack(fill="x", ipady=5, pady=(0, 4))

        # ── Botones de acción ─────────────────────────────────────────────────
        btn_row = tk.Frame(inp_frame, bg=BG_PANEL)
        btn_row.pack(fill="x")

        def _insert_item(tipo):
            txt = note_var.get().strip()
            if not txt:
                note_entry.focus_set()
                return
            ts     = datetime.now().strftime("%H:%M")
            dt     = datetime.now().strftime("%d/%m/%Y")
            author = self.usuario
            self.db.conn.execute(
                "INSERT INTO notas_checador(autor,texto,timestamp,date,tipo)"
                " VALUES(?,?,?,?,?)",
                (author, txt, ts, dt, tipo))
            self.db.conn.commit()
            icon = "📝" if tipo == "nota" else "⏳"
            line = f"{icon} [{ts}] {author}: {txt}"
            nts_list.insert(0, line)
            # Color por tipo
            color = PRIMARY if tipo == "nota" else WARNING
            nts_list.itemconfig(0, fg=color)
            note_var.set("")
            note_entry.focus_set()

        def _del_note():
            sel = nts_list.curselection()
            if not sel:
                return
            idx = sel[0]
            dt  = datetime.now().strftime("%d/%m/%Y")
            rows_ids = self.db.conn.execute(
                "SELECT id FROM notas_checador WHERE date=? ORDER BY id DESC",
                (dt,)).fetchall()
            if idx < len(rows_ids):
                self.db.conn.execute("DELETE FROM notas_checador WHERE id=?",
                                     (rows_ids[idx]["id"],))
                self.db.conn.commit()
            nts_list.delete(idx)

        note_entry.bind("<Return>", lambda e: _insert_item("nota"))

        self._btn(btn_row, "📝  Nota", lambda: _insert_item("nota"),
                  bg=PRIMARY, font_size=10
                  ).pack(side="left", ipadx=8, ipady=4)
        self._btn(btn_row, "⏳  Pendiente", lambda: _insert_item("pendiente"),
                  bg=WARNING, font_size=10
                  ).pack(side="left", padx=(6, 0), ipadx=8, ipady=4)
        self._btn(btn_row, "✕  Eliminar", _del_note,
                  bg=DANGER, font_size=10
                  ).pack(side="right", ipadx=8, ipady=4)

        # ── Cargar entradas de hoy (más recientes primero) ────────────────────
        dt_today  = datetime.now().strftime("%d/%m/%Y")
        note_rows = self.db.conn.execute(
            "SELECT autor, texto, timestamp, tipo FROM notas_checador"
            " WHERE date=? ORDER BY id DESC",
            (dt_today,)).fetchall()
        for nr in note_rows:
            tipo  = nr["tipo"] if nr["tipo"] else "nota"
            icon  = "📝" if tipo == "nota" else "⏳"
            color = PRIMARY if tipo == "nota" else WARNING
            line  = f"{icon} [{nr['timestamp']}] {nr['autor']}: {nr['texto']}"
            nts_list.insert(tk.END, line)
            nts_list.itemconfig(tk.END, fg=color)


if __name__ == "__main__":
    root = tk.Tk()
    app  = PuntoDeVenta(root)
    root.mainloop()
