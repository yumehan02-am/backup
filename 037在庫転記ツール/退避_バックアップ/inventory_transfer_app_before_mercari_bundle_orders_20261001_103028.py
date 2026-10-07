# -*- coding: utf-8 -*-
"""
Inventory transfer assistant prototype.

This tool imports zaiko Robot master CSV files and order CSV files, expands
set products, and presents copy-ready quantity rows for manual Excel entry.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import unicodedata
import urllib.request
import webbrowser
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from textwrap import wrap
from tkinter import BOTH, BOTTOM, CENTER, E, END, HORIZONTAL, LEFT, RIGHT, TOP, W, X, Y, BooleanVar, Button, Canvas, DoubleVar, Entry, Frame, Label, Listbox, Scrollbar, StringVar, Text, Tk, Toplevel, filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


APP_TITLE = "在庫転記ツール MVP"
DB_NAME = "inventory_transfer.db"
QUANTITY_MULTIPLIER_MARKER = "【単品数量】"

MALL_RAKUTEN = "楽天"
MALL_YAHOO = "Yahoo"
MALL_AMAZON = "Amazon"
MALL_MERCARI = "メルカリShops"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_text() -> str:
    return date.today().isoformat()


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def stock_alert_status_label(row: object) -> str:
    try:
        status = clean(row["status"])
        remaining = row["remaining_quantity"]
    except Exception:
        status = clean(getattr(row, "status", ""))
        remaining = getattr(row, "remaining_quantity", None)
    if status == "missing_label" or remaining is None:
        return "未検出"
    try:
        remaining_int = int(float(clean(remaining)))
    except ValueError:
        remaining_int = 0
    if remaining_int < 0:
        return "不足"
    if remaining_int == 0:
        return "在庫0"
    return "低在庫"


def stock_alert_status_rank(row: object) -> int:
    label = stock_alert_status_label(row)
    return {"不足": 0, "在庫0": 1, "低在庫": 2, "未検出": 3}.get(label, 9)


def should_create_stock_alert(remaining: int, min_stock: int) -> bool:
    if min_stock < 0:
        if remaining == 0:
            return False
        return remaining <= abs(min_stock)
    return remaining <= min_stock


def transfer_pattern_raw_tokens(pattern: str) -> list[str]:
    return [token.strip() for token in re.split(r"[,、\s]+", clean(pattern)) if token.strip()]


def transfer_pattern_blank_count(token: str) -> int:
    lower = clean(token).lower()
    if lower in {"t", "tab", "_", "-"}:
        return 1
    match = re.fullmatch(r"(?:t|tab)(\d+)", lower)
    if not match:
        return 0
    try:
        return max(0, int(match.group(1)))
    except ValueError:
        return 0


def compress_transfer_pattern_tokens(tokens: list[str]) -> list[str]:
    compressed: list[str] = []
    blank_count = 0

    def flush_blank() -> None:
        nonlocal blank_count
        if blank_count == 1:
            compressed.append("t")
        elif blank_count > 1:
            compressed.append(f"t{blank_count}")
        blank_count = 0

    for token in tokens:
        count = transfer_pattern_blank_count(token)
        if count:
            blank_count += count
            continue
        flush_blank()
        compressed.append(token)
    flush_blank()
    return compressed


def excel_column_to_index(value: object, default: int = 1) -> int:
    text = clean(value).upper()
    if not text:
        return default
    if text.isdigit():
        return max(1, int(text))
    text = re.sub(r"[^A-Z]", "", text)
    if not text:
        return default
    index = 0
    for char in text:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return max(1, index)

def excel_index_to_column(index: int) -> str:
    index = max(1, int(index))
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters

def normalize_excel_start_col(value: object) -> str:
    return excel_index_to_column(excel_column_to_index(value, 1))


class ExcelReadOnlyError(RuntimeError):
    pass


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    """Read Japanese CSVs with common encodings."""
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="cp932", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


JAN_COLUMNS = (
    "JAN",
    "JANコード",
    "JANｺｰﾄﾞ",
    "商品JAN",
    "商品JANコード",
    "バーコード",
    "Barcode",
    "barcode",
)


def normalize_jan_code(value: object) -> str:
    text = clean(value).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return re.sub(r"\D", "", text)


def row_jan_code(row: dict[str, str]) -> str:
    for column in JAN_COLUMNS:
        value = normalize_jan_code(row.get(column))
        if value:
            return value
    return ""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_rakuten_image_url(shop_url: str, image_path: str) -> str:
    path = clean(image_path)
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    shop = clean(shop_url).strip("/")
    if shop.startswith("http://") or shop.startswith("https://"):
        shop = shop.rstrip("/").split("/")[-1]
    if not shop:
        return ""
    path = path.lstrip("/")
    if path.startswith("cabinet/"):
        return f"https://image.rakuten.co.jp/{shop}/{path}"
    return f"https://image.rakuten.co.jp/{shop}/cabinet/{path}"


def normalize_windows_path(path: str) -> str:
    value = clean(path).replace("/", "\\")
    if value.startswith("\\\\"):
        return "\\\\" + "\\".join(part for part in value[2:].split("\\") if part)
    return os.path.normpath(value) if value else ""


def thumbnail_cache_path(base_dir: Path, url: str) -> Path:
    digest = hashlib.md5(clean(url).encode("utf-8")).hexdigest()
    return base_dir / "cache" / "thumbs" / f"{digest}.jpg"


class AppDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def create_backup(self, backup_dir: Path, label: str) -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^0-9A-Za-z_-]+", "_", clean(label)) or "backup"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"inventory_transfer_{safe_label}_{timestamp}.db"
        self.conn.commit()
        with sqlite3.connect(str(backup_path)) as backup_conn:
            self.conn.backup(backup_conn)
        return backup_path

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                product_code TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                rakuten_parent_code TEXT,
                jan_code TEXT NOT NULL DEFAULT '',
                is_set INTEGER NOT NULL DEFAULT 0,
                inventory_file_path TEXT NOT NULL DEFAULT '',
                inventory_sheet_name TEXT NOT NULL DEFAULT '',
                auto_write_confirmed INTEGER NOT NULL DEFAULT 0,
                thumbnail_url TEXT NOT NULL DEFAULT '',
                source_file TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY,
                variant_code TEXT NOT NULL UNIQUE,
                product_code TEXT NOT NULL,
                is_set INTEGER NOT NULL DEFAULT 0,
                color TEXT NOT NULL DEFAULT '',
                size TEXT NOT NULL DEFAULT '',
                jan_code TEXT NOT NULL DEFAULT '',
                color_order INTEGER,
                size_order INTEGER,
                source_file TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mall_skus (
                id INTEGER PRIMARY KEY,
                variant_code TEXT NOT NULL,
                mall TEXT NOT NULL,
                sku TEXT NOT NULL,
                mall_color TEXT NOT NULL DEFAULT '',
                mall_size TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                source_file TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (mall, sku, variant_code)
            );

            CREATE INDEX IF NOT EXISTS idx_mall_skus_lookup
                ON mall_skus (mall, sku);

            CREATE TABLE IF NOT EXISTS sku_resolution_rules (
                id INTEGER PRIMARY KEY,
                mall TEXT NOT NULL,
                source_sku TEXT NOT NULL,
                child_variant_code TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE (mall, source_sku, child_variant_code)
            );

            CREATE INDEX IF NOT EXISTS idx_sku_resolution_rules_lookup
                ON sku_resolution_rules (mall, source_sku, enabled);

            CREATE TABLE IF NOT EXISTS set_components (
                id INTEGER PRIMARY KEY,
                parent_variant_code TEXT NOT NULL,
                child_variant_code TEXT NOT NULL,
                component_quantity INTEGER NOT NULL,
                source_file TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE (parent_variant_code, child_variant_code)
            );

            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY,
                batch_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS import_files (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                UNIQUE (batch_id, file_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_import_files_batch
                ON import_files (batch_id);

            CREATE TABLE IF NOT EXISTS import_lines (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                file_id INTEGER NOT NULL,
                file_name TEXT NOT NULL DEFAULT '',
                source_row INTEGER NOT NULL,
                source_order_id TEXT NOT NULL DEFAULT '',
                source_mall TEXT NOT NULL,
                source_sku TEXT NOT NULL,
                source_sub_code TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL,
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_import_lines_batch
                ON import_lines (batch_id);

            CREATE INDEX IF NOT EXISTS idx_import_lines_duplicate_check
                ON import_lines (batch_id, source_mall, source_order_id, source_sku, source_sub_code);

            CREATE TABLE IF NOT EXISTS unresolved_items (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                file_id INTEGER,
                file_name TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                source_order_id TEXT NOT NULL DEFAULT '',
                source_mall TEXT NOT NULL,
                source_sku TEXT NOT NULL,
                source_sub_code TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                candidates_json TEXT NOT NULL DEFAULT '[]',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_unresolved_items_batch
                ON unresolved_items (batch_id);

            CREATE INDEX IF NOT EXISTS idx_unresolved_items_batch_reason
                ON unresolved_items (batch_id, reason);

            CREATE TABLE IF NOT EXISTS transfer_tasks (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                color TEXT NOT NULL,
                sizes_json TEXT NOT NULL,
                quantities_json TEXT NOT NULL,
                previous_quantities_json TEXT NOT NULL DEFAULT '',
                total_quantity INTEGER NOT NULL,
                applied_quantity_multiplier INTEGER NOT NULL DEFAULT 1,
                aggregation_round INTEGER NOT NULL DEFAULT 1,
                task_kind TEXT NOT NULL DEFAULT 'initial',
                sort_order INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_required INTEGER NOT NULL DEFAULT 0,
                retry_reason TEXT NOT NULL DEFAULT '',
                copied_at TEXT,
                skipped_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_transfer_tasks_batch
                ON transfer_tasks (batch_id);

            CREATE INDEX IF NOT EXISTS idx_transfer_tasks_batch_sort
                ON transfer_tasks (batch_id, sort_order);

            CREATE TABLE IF NOT EXISTS aggregation_snapshots (
                batch_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (batch_id, product_code, color, size)
            );

            CREATE INDEX IF NOT EXISTS idx_aggregation_snapshots_batch
                ON aggregation_snapshots (batch_id);

            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_warnings_category
                ON warnings (category);

            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                task_id INTEGER,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                color TEXT NOT NULL,
                size TEXT NOT NULL,
                remaining_quantity INTEGER,
                min_stock_quantity INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL DEFAULT 'low',
                inventory_file_path TEXT NOT NULL DEFAULT '',
                inventory_sheet_name TEXT NOT NULL DEFAULT '',
                cell_address TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_stock_alerts_batch
                ON stock_alerts (batch_id);

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_copy_settings (
                product_code TEXT PRIMARY KEY,
                copy_title TEXT NOT NULL DEFAULT '',
                title_tabs INTEGER NOT NULL DEFAULT 0,
                color_gap_tabs INTEGER NOT NULL DEFAULT 0,
                tail_tabs INTEGER NOT NULL DEFAULT 0,
                append_date INTEGER NOT NULL DEFAULT 1,
                transfer_pattern TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_user_settings (
                product_code TEXT PRIMARY KEY,
                inventory_file_path TEXT NOT NULL DEFAULT '',
                inventory_sheet_name TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT NOT NULL DEFAULT '',
                auto_write_confirmed INTEGER NOT NULL DEFAULT 0,
                quantity_multiplier INTEGER NOT NULL DEFAULT 1,
                min_stock_quantity INTEGER NOT NULL DEFAULT 3,
                excel_start_col TEXT NOT NULL DEFAULT '',
                manual_input INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_transfer_pages (
                id INTEGER PRIMARY KEY,
                product_code TEXT NOT NULL,
                page_name TEXT NOT NULL DEFAULT '',
                page_order INTEGER NOT NULL DEFAULT 1,
                inventory_file_path TEXT NOT NULL DEFAULT '',
                inventory_sheet_name TEXT NOT NULL DEFAULT '',
                excel_start_col TEXT NOT NULL DEFAULT '',
                copy_title TEXT NOT NULL DEFAULT '',
                title_tabs INTEGER NOT NULL DEFAULT 0,
                color_gap_tabs INTEGER NOT NULL DEFAULT 0,
                tail_tabs INTEGER NOT NULL DEFAULT 0,
                append_date INTEGER NOT NULL DEFAULT 1,
                transfer_pattern TEXT NOT NULL DEFAULT '',
                quantity_multiplier INTEGER NOT NULL DEFAULT 1,
                auto_write_confirmed INTEGER NOT NULL DEFAULT 0,
                title_date_add_only INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(product_code, page_order)
            );

            CREATE TABLE IF NOT EXISTS variant_user_settings (
                variant_code TEXT PRIMARY KEY,
                color TEXT NOT NULL DEFAULT '',
                size TEXT NOT NULL DEFAULT '',
                color_order INTEGER,
                size_order INTEGER,
                sold_out INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._migrate_schema()
        self.conn.commit()

    def _migrate_schema(self) -> None:
        self._migrate_transfer_tasks_allow_duplicates()
        product_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(products)").fetchall()}
        if "inventory_file_path" not in product_columns:
            self.conn.execute("ALTER TABLE products ADD COLUMN inventory_file_path TEXT NOT NULL DEFAULT ''")
        if "inventory_sheet_name" not in product_columns:
            self.conn.execute("ALTER TABLE products ADD COLUMN inventory_sheet_name TEXT NOT NULL DEFAULT ''")
        if "auto_write_confirmed" not in product_columns:
            self.conn.execute("ALTER TABLE products ADD COLUMN auto_write_confirmed INTEGER NOT NULL DEFAULT 0")
        if "thumbnail_url" not in product_columns:
            self.conn.execute("ALTER TABLE products ADD COLUMN thumbnail_url TEXT NOT NULL DEFAULT ''")
        if "jan_code" not in product_columns:
            self.conn.execute("ALTER TABLE products ADD COLUMN jan_code TEXT NOT NULL DEFAULT ''")
        variant_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(variants)").fetchall()}
        if "jan_code" not in variant_columns:
            self.conn.execute("ALTER TABLE variants ADD COLUMN jan_code TEXT NOT NULL DEFAULT ''")
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(import_lines)").fetchall()}
        if "file_name" not in columns:
            self.conn.execute("ALTER TABLE import_lines ADD COLUMN file_name TEXT NOT NULL DEFAULT ''")
        if "raw_json" not in columns:
            self.conn.execute("ALTER TABLE import_lines ADD COLUMN raw_json TEXT NOT NULL DEFAULT '{}'")
        if "source_order_id" not in columns:
            self.conn.execute("ALTER TABLE import_lines ADD COLUMN source_order_id TEXT NOT NULL DEFAULT ''")
        unresolved_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(unresolved_items)").fetchall()}
        if "source_order_id" not in unresolved_columns:
            self.conn.execute("ALTER TABLE unresolved_items ADD COLUMN source_order_id TEXT NOT NULL DEFAULT ''")
        copy_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(product_copy_settings)").fetchall()}
        if "transfer_pattern" not in copy_columns:
            self.conn.execute("ALTER TABLE product_copy_settings ADD COLUMN transfer_pattern TEXT NOT NULL DEFAULT ''")
        user_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(product_user_settings)").fetchall()}
        if "quantity_multiplier" not in user_columns:
            self.conn.execute("ALTER TABLE product_user_settings ADD COLUMN quantity_multiplier INTEGER NOT NULL DEFAULT 1")
        if "min_stock_quantity" not in user_columns:
            self.conn.execute("ALTER TABLE product_user_settings ADD COLUMN min_stock_quantity INTEGER NOT NULL DEFAULT 3")
        if "excel_start_col" not in user_columns:
            self.conn.execute("ALTER TABLE product_user_settings ADD COLUMN excel_start_col TEXT NOT NULL DEFAULT ''")
        if "manual_input" not in user_columns:
            self.conn.execute("ALTER TABLE product_user_settings ADD COLUMN manual_input INTEGER NOT NULL DEFAULT 0")
        variant_user_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(variant_user_settings)").fetchall()}
        if "sold_out" not in variant_user_columns:
            self.conn.execute("ALTER TABLE variant_user_settings ADD COLUMN sold_out INTEGER NOT NULL DEFAULT 0")
        page_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(product_transfer_pages)").fetchall()}
        if "quantity_multiplier" not in page_columns:
            self.conn.execute("ALTER TABLE product_transfer_pages ADD COLUMN quantity_multiplier INTEGER NOT NULL DEFAULT 1")
        if "title_date_add_only" not in page_columns:
            self.conn.execute("ALTER TABLE product_transfer_pages ADD COLUMN title_date_add_only INTEGER NOT NULL DEFAULT 0")
        task_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(transfer_tasks)").fetchall()}
        if "applied_quantity_multiplier" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN applied_quantity_multiplier INTEGER NOT NULL DEFAULT 1")
        if "previous_quantities_json" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN previous_quantities_json TEXT NOT NULL DEFAULT ''")
        if "aggregation_round" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN aggregation_round INTEGER NOT NULL DEFAULT 1")
        if "task_kind" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN task_kind TEXT NOT NULL DEFAULT 'initial'")
        if "retry_required" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN retry_required INTEGER NOT NULL DEFAULT 0")
        if "retry_reason" not in task_columns:
            self.conn.execute("ALTER TABLE transfer_tasks ADD COLUMN retry_reason TEXT NOT NULL DEFAULT ''")
        if self.get_setting("stock_min_default_migrated_v1", "0") != "1":
            self.conn.execute("UPDATE product_user_settings SET min_stock_quantity = 3 WHERE min_stock_quantity = 0")
            self.set_setting("stock_min_default_migrated_v1", "1")
        if self.get_setting("user_settings_migrated_v1", "0") != "1":
            self._migrate_existing_user_settings()
            self.set_setting("user_settings_migrated_v1", "1")
        if self.get_setting("page_multiplier_model_migrated_v1", "0") != "1":
            self.sync_current_task_quantity_multipliers()
            self.set_setting("page_multiplier_model_migrated_v1", "1")

    def _migrate_transfer_tasks_allow_duplicates(self) -> None:
        sql_row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'transfer_tasks'"
        ).fetchone()
        if not sql_row or "UNIQUE (batch_id, product_code, color)" not in clean(sql_row["sql"]):
            return
        self.conn.executescript(
            """
            CREATE TABLE transfer_tasks_new (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                color TEXT NOT NULL,
                sizes_json TEXT NOT NULL,
                quantities_json TEXT NOT NULL,
                previous_quantities_json TEXT NOT NULL DEFAULT '',
                total_quantity INTEGER NOT NULL,
                applied_quantity_multiplier INTEGER NOT NULL DEFAULT 1,
                aggregation_round INTEGER NOT NULL DEFAULT 1,
                task_kind TEXT NOT NULL DEFAULT 'initial',
                sort_order INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                copied_at TEXT,
                skipped_at TEXT
            );

            INSERT INTO transfer_tasks_new(
                id, batch_id, product_code, product_name, color, sizes_json, quantities_json,
                previous_quantities_json, total_quantity, applied_quantity_multiplier, aggregation_round, task_kind, sort_order, status, copied_at, skipped_at
            )
            SELECT
                id, batch_id, product_code, product_name, color, sizes_json, quantities_json,
                '', total_quantity, applied_quantity_multiplier, 1, 'initial', sort_order, status, copied_at, skipped_at
            FROM transfer_tasks;

            DROP TABLE transfer_tasks;
            ALTER TABLE transfer_tasks_new RENAME TO transfer_tasks;
            CREATE INDEX IF NOT EXISTS idx_transfer_tasks_batch
                ON transfer_tasks (batch_id);
            CREATE INDEX IF NOT EXISTS idx_transfer_tasks_batch_sort
                ON transfer_tasks (batch_id, sort_order);
            """
        )

    def _migrate_existing_user_settings(self) -> None:
        now = now_text()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO product_user_settings(
                product_code, inventory_file_path, inventory_sheet_name, thumbnail_url, auto_write_confirmed, quantity_multiplier, min_stock_quantity, excel_start_col, updated_at
            )
            SELECT product_code, inventory_file_path, inventory_sheet_name, thumbnail_url, auto_write_confirmed, 1, 3, '', ?
            FROM products
            WHERE inventory_file_path <> '' OR inventory_sheet_name <> '' OR thumbnail_url <> '' OR auto_write_confirmed <> 0
            """,
            (now,),
        )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO variant_user_settings(
                variant_code, color, size, color_order, size_order, updated_at
            )
            SELECT variant_code, color, size, color_order, size_order, ?
            FROM variants
            """,
            (now,),
        )

    def warn(self, category: str, message: str, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO warnings(category, message, detail, created_at) VALUES (?, ?, ?, ?)",
            (category, message, detail, now_text()),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return clean(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.conn.commit()

    def date_format_options(self) -> dict[str, str]:
        return {
            "yyyy/mm/dd": "%Y/%m/%d",
            "yyyy-mm-dd": "%Y-%m-%d",
            "yyyy年m月d日": "",
            "m/d": "",
            "mm/dd": "%m/%d",
        }

    def transfer_date_text(self) -> str:
        key = self.get_setting("transfer_date_format", "yyyy/mm/dd")
        now = datetime.now()
        if key == "yyyy年m月d日":
            return f"{now.year}年{now.month}月{now.day}日"
        if key == "m/d":
            return f"{now.month}/{now.day}"
        fmt = self.date_format_options().get(key, "%Y/%m/%d")
        return now.strftime(fmt or "%Y/%m/%d")

    def get_product_copy_settings(self, product_code: str, default_title: str = "") -> dict[str, object]:
        row = self.conn.execute(
            "SELECT * FROM product_copy_settings WHERE product_code = ?",
            (product_code,),
        ).fetchone()
        if row:
            return {
                "copy_title": clean(row["copy_title"]),
                "title_tabs": int(row["title_tabs"]),
                "color_gap_tabs": int(row["color_gap_tabs"]),
                "tail_tabs": int(row["tail_tabs"]),
                "append_date": bool(row["append_date"]),
                "transfer_pattern": clean(row["transfer_pattern"]),
            }
        return {
            "copy_title": self.get_setting("default_copy_title", default_title),
            "title_tabs": self._setting_int("default_title_tabs", 0),
            "color_gap_tabs": self._setting_int("default_color_gap_tabs", 1),
            "tail_tabs": self._setting_int("default_tail_tabs", 2),
            "append_date": self.get_setting("default_append_date", "1") != "0",
            "transfer_pattern": self.get_setting("default_transfer_pattern", ""),
        }

    def _setting_int(self, key: str, default: int = 0) -> int:
        try:
            return int(float(clean(self.get_setting(key, str(default))) or default))
        except ValueError:
            return default

    def save_product_copy_settings(
        self,
        product_code: str,
        copy_title: str,
        title_tabs: int,
        color_gap_tabs: int,
        tail_tabs: int,
        append_date: bool,
        transfer_pattern: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO product_copy_settings(
                product_code, copy_title, title_tabs, color_gap_tabs, tail_tabs, append_date, transfer_pattern, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_code) DO UPDATE SET
                copy_title = excluded.copy_title,
                title_tabs = excluded.title_tabs,
                color_gap_tabs = excluded.color_gap_tabs,
                tail_tabs = excluded.tail_tabs,
                append_date = excluded.append_date,
                transfer_pattern = excluded.transfer_pattern,
                updated_at = excluded.updated_at
            """,
            (
                product_code,
                copy_title,
                title_tabs,
                color_gap_tabs,
                tail_tabs,
                1 if append_date else 0,
                clean(transfer_pattern),
                now_text(),
            ),
        )
        self.conn.commit()

    def ensure_default_transfer_page(self, product_code: str) -> None:
        existing = self.conn.execute(
            "SELECT id FROM product_transfer_pages WHERE product_code = ? ORDER BY page_order LIMIT 1",
            (product_code,),
        ).fetchone()
        if existing:
            return
        link = self.product_inventory_link(product_code)
        copy = self.get_product_copy_settings(product_code, "ネット")
        self.save_product_transfer_page(
            product_code,
            page_id=None,
            page_name="ページ1",
            page_order=1,
            inventory_file_path=link["inventory_file_path"],
            inventory_sheet_name=link["inventory_sheet_name"],
            excel_start_col=link["excel_start_col"],
            copy_title=str(copy["copy_title"]),
            title_tabs=int(copy["title_tabs"]),
            color_gap_tabs=int(copy["color_gap_tabs"]),
            tail_tabs=int(copy["tail_tabs"]),
            append_date=bool(copy["append_date"]),
            transfer_pattern=str(copy["transfer_pattern"]),
            quantity_multiplier=1,
            auto_write_confirmed=self.product_auto_write_confirmed(product_code),
            title_date_add_only=False,
            sync_legacy=False,
        )

    def product_transfer_pages(self, product_code: str) -> list[sqlite3.Row]:
        self.ensure_default_transfer_page(product_code)
        return self.conn.execute(
            "SELECT * FROM product_transfer_pages WHERE product_code = ? ORDER BY page_order, id",
            (product_code,),
        ).fetchall()

    def save_product_transfer_page(
        self,
        product_code: str,
        page_id: int | None,
        page_name: str,
        page_order: int,
        inventory_file_path: str,
        inventory_sheet_name: str,
        excel_start_col: str,
        copy_title: str,
        title_tabs: int,
        color_gap_tabs: int,
        tail_tabs: int,
        append_date: bool,
        transfer_pattern: str,
        quantity_multiplier: int = 1,
        auto_write_confirmed: bool = False,
        title_date_add_only: bool = False,
        sync_legacy: bool = True,
    ) -> int:
        multiplier = self._normalize_quantity_multiplier(quantity_multiplier)
        if page_id:
            self.conn.execute(
                """
                UPDATE product_transfer_pages
                SET page_name = ?, page_order = ?, inventory_file_path = ?, inventory_sheet_name = ?,
                    excel_start_col = ?, copy_title = ?, title_tabs = ?, color_gap_tabs = ?,
                    tail_tabs = ?, append_date = ?, transfer_pattern = ?, quantity_multiplier = ?, auto_write_confirmed = ?,
                    title_date_add_only = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    clean(page_name) or f"ページ{page_order}",
                    max(1, int(page_order)),
                    normalize_windows_path(inventory_file_path),
                    str(inventory_sheet_name or ""),
                    normalize_excel_start_col(excel_start_col),
                    clean(copy_title),
                    max(0, int(title_tabs)),
                    max(0, int(color_gap_tabs)),
                    max(0, int(tail_tabs)),
                    1 if append_date else 0,
                    clean(transfer_pattern),
                    multiplier,
                    1 if auto_write_confirmed else 0,
                    1 if title_date_add_only else 0,
                    now_text(),
                    page_id,
                ),
            )
            saved_id = int(page_id)
        else:
            self.conn.execute(
                """
                INSERT INTO product_transfer_pages(
                    product_code, page_name, page_order, inventory_file_path, inventory_sheet_name, excel_start_col,
                    copy_title, title_tabs, color_gap_tabs, tail_tabs, append_date, transfer_pattern, quantity_multiplier,
                    auto_write_confirmed, title_date_add_only, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_code,
                    clean(page_name) or f"ページ{page_order}",
                    max(1, int(page_order)),
                    normalize_windows_path(inventory_file_path),
                    str(inventory_sheet_name or ""),
                    normalize_excel_start_col(excel_start_col),
                    clean(copy_title),
                    max(0, int(title_tabs)),
                    max(0, int(color_gap_tabs)),
                    max(0, int(tail_tabs)),
                    1 if append_date else 0,
                    clean(transfer_pattern),
                    multiplier,
                    1 if auto_write_confirmed else 0,
                    1 if title_date_add_only else 0,
                    now_text(),
                ),
            )
            saved_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.conn.commit()
        if sync_legacy and int(page_order) == 1:
            self.update_product_inventory_link(product_code, inventory_file_path, inventory_sheet_name, excel_start_col)
            self.save_product_copy_settings(product_code, copy_title, title_tabs, color_gap_tabs, tail_tabs, append_date, transfer_pattern)
            self.set_product_auto_write_confirmed(product_code, auto_write_confirmed)
        return saved_id

    def delete_product_transfer_page(self, page_id: int) -> None:
        row = self.conn.execute("SELECT product_code FROM product_transfer_pages WHERE id = ?", (page_id,)).fetchone()
        if not row:
            return
        count = self.conn.execute(
            "SELECT COUNT(*) AS count FROM product_transfer_pages WHERE product_code = ?",
            (row["product_code"],),
        ).fetchone()["count"]
        if int(count) <= 1:
            return
        self.conn.execute("DELETE FROM product_transfer_pages WHERE id = ?", (page_id,))
        self.conn.commit()

    def delete_product_data(self, product_code: str) -> dict[str, int]:
        code = clean(product_code)
        if not code:
            return {}
        product = self.conn.execute("SELECT product_code FROM products WHERE product_code = ?", (code,)).fetchone()
        if not product:
            return {}
        variants = [
            clean(row["variant_code"])
            for row in self.conn.execute("SELECT variant_code FROM variants WHERE product_code = ?", (code,)).fetchall()
        ]
        counts: dict[str, int] = {}

        def delete(sql: str, params: tuple[object, ...] = ()) -> int:
            cur = self.conn.execute(sql, params)
            return int(cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0)

        if variants:
            placeholders = ",".join("?" for _ in variants)
            counts["set_components"] = delete(
                f"DELETE FROM set_components WHERE parent_variant_code IN ({placeholders}) OR child_variant_code IN ({placeholders})",
                tuple(variants + variants),
            )
            counts["mall_skus"] = delete(f"DELETE FROM mall_skus WHERE variant_code IN ({placeholders})", tuple(variants))
            counts["variant_user_settings"] = delete(f"DELETE FROM variant_user_settings WHERE variant_code IN ({placeholders})", tuple(variants))
            counts["sku_resolution_rules"] = delete(f"DELETE FROM sku_resolution_rules WHERE child_variant_code IN ({placeholders})", tuple(variants))
        else:
            counts["set_components"] = 0
            counts["mall_skus"] = 0
            counts["variant_user_settings"] = 0
            counts["sku_resolution_rules"] = 0
        counts["variants"] = delete("DELETE FROM variants WHERE product_code = ?", (code,))
        counts["product_transfer_pages"] = delete("DELETE FROM product_transfer_pages WHERE product_code = ?", (code,))
        counts["product_copy_settings"] = delete("DELETE FROM product_copy_settings WHERE product_code = ?", (code,))
        counts["product_user_settings"] = delete("DELETE FROM product_user_settings WHERE product_code = ?", (code,))
        counts["transfer_tasks"] = delete("DELETE FROM transfer_tasks WHERE product_code = ?", (code,))
        counts["aggregation_snapshots"] = delete("DELETE FROM aggregation_snapshots WHERE product_code = ?", (code,))
        counts["stock_alerts"] = delete("DELETE FROM stock_alerts WHERE product_code = ?", (code,))
        counts["products"] = delete("DELETE FROM products WHERE product_code = ?", (code,))
        self.conn.commit()
        return counts

    def products_for_settings(self, search: str = "", is_set: int | None = None) -> list[sqlite3.Row]:
        like = f"%{search.strip()}%"
        type_sql = "" if is_set is None else " AND p.is_set = ?"
        type_params: tuple[object, ...] = () if is_set is None else (is_set,)
        if search.strip():
            return self.conn.execute(
                f"""
                SELECT p.product_code, p.display_name, p.rakuten_parent_code, p.jan_code, p.is_set,
                       COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path,
                       COALESCE(NULLIF(pus.inventory_sheet_name, ''), p.inventory_sheet_name) AS inventory_sheet_name,
                       COALESCE(NULLIF(pus.thumbnail_url, ''), p.thumbnail_url) AS thumbnail_url,
                       COALESCE(pus.auto_write_confirmed, p.auto_write_confirmed, 0) AS auto_write_confirmed,
                       COALESCE(pus.quantity_multiplier, 1) AS quantity_multiplier,
                       COALESCE(pus.min_stock_quantity, 3) AS min_stock_quantity,
                       COALESCE(NULLIF(pus.excel_start_col, ''), 'A') AS excel_start_col,
                       COALESCE(pus.manual_input, 0) AS manual_input
                FROM products p
                LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
                WHERE (p.product_code LIKE ? OR p.display_name LIKE ? OR p.rakuten_parent_code LIKE ? OR p.jan_code LIKE ?)
                {type_sql}
                ORDER BY p.display_name, p.product_code
                """,
                (like, like, like, like, *type_params),
            ).fetchall()
        return self.conn.execute(
            f"""
            SELECT p.product_code, p.display_name, p.rakuten_parent_code, p.jan_code, p.is_set,
                   COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path,
                   COALESCE(NULLIF(pus.inventory_sheet_name, ''), p.inventory_sheet_name) AS inventory_sheet_name,
                   COALESCE(NULLIF(pus.thumbnail_url, ''), p.thumbnail_url) AS thumbnail_url,
                   COALESCE(pus.auto_write_confirmed, p.auto_write_confirmed, 0) AS auto_write_confirmed,
                   COALESCE(pus.quantity_multiplier, 1) AS quantity_multiplier,
                   COALESCE(pus.min_stock_quantity, 3) AS min_stock_quantity,
                   COALESCE(NULLIF(pus.excel_start_col, ''), 'A') AS excel_start_col,
                   COALESCE(pus.manual_input, 0) AS manual_input
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE 1 = 1 {type_sql}
            ORDER BY p.display_name, p.product_code
            """,
            type_params,
        ).fetchall()

    def product_for_settings(self, product_code: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT p.product_code, p.display_name, p.rakuten_parent_code, p.jan_code, p.is_set,
                   COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path,
                   COALESCE(NULLIF(pus.inventory_sheet_name, ''), p.inventory_sheet_name) AS inventory_sheet_name,
                   COALESCE(NULLIF(pus.thumbnail_url, ''), p.thumbnail_url) AS thumbnail_url,
                   COALESCE(pus.auto_write_confirmed, p.auto_write_confirmed, 0) AS auto_write_confirmed,
                   COALESCE(pus.quantity_multiplier, 1) AS quantity_multiplier,
                   COALESCE(pus.min_stock_quantity, 3) AS min_stock_quantity,
                   COALESCE(NULLIF(pus.excel_start_col, ''), 'A') AS excel_start_col,
                   COALESCE(pus.manual_input, 0) AS manual_input
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE p.product_code = ?
            """,
            (product_code,),
        ).fetchone()

    def set_components_for_product(self, product_code: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT
                pv.variant_code AS parent_variant_code,
                COALESCE(NULLIF(pvus.color, ''), pv.color) AS parent_color,
                COALESCE(NULLIF(pvus.size, ''), pv.size) AS parent_size,
                sc.child_variant_code,
                cv.product_code AS child_product_code,
                COALESCE(cp.display_name, cv.product_code, '') AS child_product_name,
                COALESCE(NULLIF(cvus.color, ''), cv.color, '') AS child_color,
                COALESCE(NULLIF(cvus.size, ''), cv.size, '') AS child_size,
                sc.component_quantity
            FROM variants pv
            LEFT JOIN variant_user_settings pvus ON pvus.variant_code = pv.variant_code
            LEFT JOIN set_components sc ON sc.parent_variant_code = pv.variant_code
            LEFT JOIN variants cv ON cv.variant_code = sc.child_variant_code
            LEFT JOIN variant_user_settings cvus ON cvus.variant_code = cv.variant_code
            LEFT JOIN products cp ON cp.product_code = cv.product_code
            WHERE pv.product_code = ?
            ORDER BY COALESCE(pvus.color_order, pv.color_order), parent_color,
                     COALESCE(pvus.size_order, pv.size_order), parent_size,
                     sc.child_variant_code
            """,
            (product_code,),
        ).fetchall()

    def products_with_thumbnail_urls(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT p.product_code, p.display_name,
                   COALESCE(NULLIF(pus.thumbnail_url, ''), p.thumbnail_url) AS thumbnail_url
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE COALESCE(NULLIF(pus.thumbnail_url, ''), p.thumbnail_url) <> ''
            ORDER BY p.display_name, p.product_code
            """
        ).fetchall()

    def update_product_settings(
        self,
        product_code: str,
        display_name: str,
        rakuten_parent_code: str,
        jan_code: str,
        inventory_file_path: str,
        inventory_sheet_name: str,
        thumbnail_url: str,
        quantity_multiplier: int = 1,
        min_stock_quantity: int = 0,
        excel_start_col: str = "A",
        manual_input: bool = False,
    ) -> None:
        self.conn.execute(
            """
            UPDATE products
            SET display_name = ?,
                rakuten_parent_code = ?,
                jan_code = ?,
                updated_at = ?
            WHERE product_code = ?
            """,
            (
                display_name,
                rakuten_parent_code,
                normalize_jan_code(jan_code),
                now_text(),
                product_code,
            ),
        )
        self.upsert_product_user_settings(
            product_code,
            inventory_file_path,
            inventory_sheet_name,
            thumbnail_url,
            self.product_auto_write_confirmed(product_code),
            quantity_multiplier,
            min_stock_quantity,
            excel_start_col,
            manual_input,
        )
        self.conn.commit()

    def upsert_product_user_settings(
        self,
        product_code: str,
        inventory_file_path: str | None = None,
        inventory_sheet_name: str | None = None,
        thumbnail_url: str | None = None,
        auto_write_confirmed: bool | None = None,
        quantity_multiplier: int | None = None,
        min_stock_quantity: int | None = None,
        excel_start_col: str | None = None,
        manual_input: bool | None = None,
    ) -> None:
        current = self.conn.execute(
            "SELECT * FROM product_user_settings WHERE product_code = ?",
            (product_code,),
        ).fetchone()
        file_path = normalize_windows_path(inventory_file_path) if inventory_file_path is not None else (clean(current["inventory_file_path"]) if current else "")
        sheet_name = str(inventory_sheet_name or "") if inventory_sheet_name is not None else (str(current["inventory_sheet_name"] or "") if current else "")
        thumb = clean(thumbnail_url) if thumbnail_url is not None else (clean(current["thumbnail_url"]) if current else "")
        auto_flag = (1 if auto_write_confirmed else 0) if auto_write_confirmed is not None else (int(current["auto_write_confirmed"]) if current else 0)
        multiplier = self._normalize_quantity_multiplier(
            quantity_multiplier if quantity_multiplier is not None else (current["quantity_multiplier"] if current and "quantity_multiplier" in current.keys() else 1)
        )
        min_stock = self._parse_min_stock_int(
            min_stock_quantity if min_stock_quantity is not None else (current["min_stock_quantity"] if current and "min_stock_quantity" in current.keys() else 3)
        )
        start_col = normalize_excel_start_col(excel_start_col) if excel_start_col is not None else (clean(current["excel_start_col"]) if current and "excel_start_col" in current.keys() else "")
        manual_flag = (1 if manual_input else 0) if manual_input is not None else (int(current["manual_input"]) if current and "manual_input" in current.keys() else 0)
        self.conn.execute(
            """
            INSERT INTO product_user_settings(
                product_code, inventory_file_path, inventory_sheet_name, thumbnail_url, auto_write_confirmed, quantity_multiplier, min_stock_quantity, excel_start_col, manual_input, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_code) DO UPDATE SET
                inventory_file_path = excluded.inventory_file_path,
                inventory_sheet_name = excluded.inventory_sheet_name,
                thumbnail_url = excluded.thumbnail_url,
                auto_write_confirmed = excluded.auto_write_confirmed,
                quantity_multiplier = excluded.quantity_multiplier,
                min_stock_quantity = excluded.min_stock_quantity,
                excel_start_col = excluded.excel_start_col,
                manual_input = excluded.manual_input,
                updated_at = excluded.updated_at
            """,
            (
                product_code,
                file_path,
                sheet_name,
                thumb,
                auto_flag,
                multiplier,
                min_stock,
                start_col,
                manual_flag,
                now_text(),
            ),
        )

    def _normalize_quantity_multiplier(self, value: object) -> int:
        try:
            multiplier = int(float(clean(value)))
        except (TypeError, ValueError):
            multiplier = 1
        return max(1, multiplier)

    def _parse_min_stock_int(self, value: object) -> int:
        try:
            return int(float(clean(value) or 0))
        except (TypeError, ValueError):
            return 0

    def product_quantity_multiplier(self, product_code: str) -> int:
        return 1

    def product_min_stock_quantity(self, product_code: str) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(pus.min_stock_quantity, 3) AS min_stock_quantity
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE p.product_code = ?
            """,
            (product_code,),
        ).fetchone()
        return self._parse_min_stock_int(row["min_stock_quantity"] if row else 3)

    def save_stock_alert(
        self,
        task_id: int | None,
        product_code: str,
        product_name: str,
        color: str,
        size: str,
        remaining_quantity: int | None,
        min_stock_quantity: int,
        status: str,
        inventory_file_path: str,
        inventory_sheet_name: str,
        cell_address: str,
        message: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO stock_alerts(
                batch_id, task_id, product_code, product_name, color, size,
                remaining_quantity, min_stock_quantity, status, inventory_file_path,
                inventory_sheet_name, cell_address, message, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.active_batch_id(),
                task_id,
                product_code,
                product_name,
                color,
                size,
                remaining_quantity,
                min_stock_quantity,
                status,
                inventory_file_path,
                inventory_sheet_name,
                cell_address,
                message,
                now_text(),
            ),
        )
        self.conn.commit()

    def stock_alert_rows(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM stock_alerts
            WHERE batch_id = ?
            ORDER BY created_at DESC, product_name, color, size
            """,
            (self.active_batch_id(),),
        ).fetchall()

    def clear_stock_alerts(self) -> None:
        self.conn.execute("DELETE FROM stock_alerts WHERE batch_id = ?", (self.active_batch_id(),))
        self.conn.commit()

    def delete_stock_alerts(self, alert_ids: list[int]) -> int:
        valid_ids = []
        for alert_id in alert_ids:
            try:
                value = int(alert_id)
            except (TypeError, ValueError):
                continue
            if value > 0:
                valid_ids.append(value)
        if not valid_ids:
            return 0
        placeholders = ",".join("?" for _ in valid_ids)
        cursor = self.conn.execute(
            f"DELETE FROM stock_alerts WHERE batch_id = ? AND id IN ({placeholders})",
            [self.active_batch_id(), *valid_ids],
        )
        self.conn.commit()
        return int(cursor.rowcount or 0)

    def bulk_update_min_stock_quantity(self, product_codes: list[str], min_stock_quantity: int) -> int:
        min_stock = self._parse_min_stock_int(min_stock_quantity)
        updated = 0
        for product_code in product_codes:
            code = clean(product_code)
            if not code:
                continue
            self.upsert_product_user_settings(code, min_stock_quantity=min_stock)
            updated += 1
        self.conn.commit()
        return updated

    def set_product_min_stock_quantity(self, product_code: str, min_stock_quantity: int) -> None:
        self.upsert_product_user_settings(
            product_code,
            min_stock_quantity=self._parse_min_stock_int(min_stock_quantity),
        )
        self.conn.commit()

    def _strip_quantity_marker(self, product_name: str) -> str:
        return clean(product_name).replace(QUANTITY_MULTIPLIER_MARKER, "")

    def _apply_quantity_marker(self, product_name: str, quantity_multiplier: int) -> str:
        base_name = self._strip_quantity_marker(product_name)
        if self._normalize_quantity_multiplier(quantity_multiplier) == 1:
            return base_name
        return f"{base_name}{QUANTITY_MULTIPLIER_MARKER}"

    def sync_current_task_quantity_multipliers(self, product_code: str | None = None) -> int:
        batch_id = self.active_batch_id()
        if product_code:
            rows = self.conn.execute(
                "SELECT * FROM transfer_tasks WHERE batch_id = ? AND product_code = ?",
                (batch_id, product_code),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM transfer_tasks WHERE batch_id = ?",
                (batch_id,),
            ).fetchall()
        updated = 0
        for row in rows:
            target_multiplier = self.product_quantity_multiplier(row["product_code"])
            applied_multiplier = self._normalize_quantity_multiplier(row["applied_quantity_multiplier"])
            new_name = self._apply_quantity_marker(row["product_name"], target_multiplier)
            if target_multiplier == applied_multiplier and new_name == row["product_name"]:
                continue
            quantities = json.loads(row["quantities_json"])
            new_quantities: list[str] = []
            total = 0
            for qty_text in quantities:
                qty_text = clean(qty_text)
                if not qty_text:
                    new_quantities.append("")
                    continue
                try:
                    current_qty = int(float(qty_text))
                except ValueError:
                    new_quantities.append(qty_text)
                    continue
                if applied_multiplier > 1 and current_qty % applied_multiplier == 0:
                    base_qty = current_qty // applied_multiplier
                else:
                    base_qty = current_qty
                new_qty = base_qty * target_multiplier
                new_quantities.append("" if new_qty == 0 else str(new_qty))
                total += new_qty
            previous_quantities = json.loads(row["previous_quantities_json"] or "[]")
            new_previous_quantities: list[str] = []
            for qty_text in previous_quantities:
                qty_text = clean(qty_text)
                if not qty_text:
                    new_previous_quantities.append("")
                    continue
                try:
                    current_qty = int(float(qty_text))
                except ValueError:
                    new_previous_quantities.append(qty_text)
                    continue
                if applied_multiplier > 1 and current_qty % applied_multiplier == 0:
                    base_qty = current_qty // applied_multiplier
                else:
                    base_qty = current_qty
                new_qty = base_qty * target_multiplier
                new_previous_quantities.append("" if new_qty == 0 else str(new_qty))
            self.conn.execute(
                """
                UPDATE transfer_tasks
                SET product_name = ?,
                    quantities_json = ?,
                    previous_quantities_json = ?,
                    total_quantity = ?,
                    applied_quantity_multiplier = ?
                WHERE id = ?
                """,
                (
                    new_name,
                    json.dumps(new_quantities, ensure_ascii=False),
                    json.dumps(new_previous_quantities, ensure_ascii=False),
                    total,
                    target_multiplier,
                    row["id"],
                ),
            )
            updated += 1
        if updated:
            self.conn.commit()
        return updated

    def product_inventory_link(self, product_code: str) -> dict[str, str]:
        row = self.conn.execute(
            """
            SELECT COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path,
                   COALESCE(NULLIF(pus.inventory_sheet_name, ''), p.inventory_sheet_name) AS inventory_sheet_name,
                   COALESCE(NULLIF(pus.excel_start_col, ''), 'A') AS excel_start_col
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE p.product_code = ?
            """,
            (product_code,),
        ).fetchone()
        if not row:
            return {"inventory_file_path": "", "inventory_sheet_name": "", "excel_start_col": "A"}
        return {
            "inventory_file_path": clean(row["inventory_file_path"]),
            "inventory_sheet_name": clean(row["inventory_sheet_name"]),
            "excel_start_col": normalize_excel_start_col(row["excel_start_col"]),
        }

    def product_auto_write_confirmed(self, product_code: str) -> bool:
        row = self.conn.execute(
            """
            SELECT COALESCE(pus.auto_write_confirmed, p.auto_write_confirmed, 0) AS auto_write_confirmed
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE p.product_code = ?
            """,
            (product_code,),
        ).fetchone()
        return bool(row and row["auto_write_confirmed"])

    def product_manual_input(self, product_code: str) -> bool:
        row = self.conn.execute(
            """
            SELECT COALESCE(pus.manual_input, 0) AS manual_input
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE p.product_code = ?
            """,
            (product_code,),
        ).fetchone()
        return bool(row and row["manual_input"])

    def set_product_auto_write_confirmed(self, product_code: str, confirmed: bool) -> None:
        self.upsert_product_user_settings(product_code, auto_write_confirmed=confirmed)
        self.conn.commit()

    def update_product_inventory_file(self, product_code: str, inventory_file_path: str) -> None:
        self.upsert_product_user_settings(product_code, inventory_file_path=inventory_file_path)
        self.conn.commit()

    def update_product_inventory_link(
        self,
        product_code: str,
        inventory_file_path: str,
        inventory_sheet_name: str,
        excel_start_col: str | None = None,
    ) -> None:
        self.upsert_product_user_settings(
            product_code,
            inventory_file_path=inventory_file_path,
            inventory_sheet_name=inventory_sheet_name,
            excel_start_col=excel_start_col,
        )
        self.conn.commit()

    def preview_inventory_path_replace(self, old_text: str, new_text: str, limit: int = 5) -> tuple[int, list[tuple[str, str, str]]]:
        old_text = normalize_windows_path(old_text)
        new_text = normalize_windows_path(new_text)
        if not old_text:
            return 0, []
        product_rows = self.conn.execute(
            """
            SELECT p.product_code, p.display_name,
                   COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) <> ''
              AND instr(COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path), ?) > 0
            ORDER BY p.display_name, p.product_code
            """,
            (old_text,),
        ).fetchall()
        page_rows = self.conn.execute(
            """
            SELECT p.product_code, p.display_name, ptp.page_name, ptp.inventory_file_path
            FROM product_transfer_pages ptp
            LEFT JOIN products p ON p.product_code = ptp.product_code
            WHERE ptp.inventory_file_path <> ''
              AND instr(ptp.inventory_file_path, ?) > 0
            ORDER BY COALESCE(p.display_name, ptp.product_code), ptp.page_order, ptp.id
            """,
            (old_text,),
        ).fetchall()
        samples: list[tuple[str, str, str]] = []
        combined: list[tuple[str, str]] = []
        for row in product_rows:
            name = clean(row["display_name"]) or clean(row["product_code"])
            combined.append((name, clean(row["inventory_file_path"])))
        for row in page_rows:
            name = clean(row["display_name"]) or clean(row["product_code"])
            page_name = clean(row["page_name"])
            if page_name:
                name = f"{name} / {page_name}"
            combined.append((name, clean(row["inventory_file_path"])))
        for name, before in combined[:limit]:
            after = normalize_windows_path(before.replace(old_text, new_text))
            samples.append((name, before, after))
        return len(combined), samples

    def replace_inventory_paths(self, old_text: str, new_text: str) -> int:
        old_text = normalize_windows_path(old_text)
        new_text = normalize_windows_path(new_text)
        if not old_text:
            return 0
        product_rows = self.conn.execute(
            """
            SELECT p.product_code,
                   COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) AS inventory_file_path
            FROM products p
            LEFT JOIN product_user_settings pus ON pus.product_code = p.product_code
            WHERE COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path) <> ''
              AND instr(COALESCE(NULLIF(pus.inventory_file_path, ''), p.inventory_file_path), ?) > 0
            """,
            (old_text,),
        ).fetchall()
        page_rows = self.conn.execute(
            """
            SELECT id, inventory_file_path
            FROM product_transfer_pages
            WHERE inventory_file_path <> ''
              AND instr(inventory_file_path, ?) > 0
            """,
            (old_text,),
        ).fetchall()
        count = len(product_rows) + len(page_rows)
        if count:
            for row in product_rows:
                before = clean(row["inventory_file_path"])
                after = normalize_windows_path(before.replace(old_text, new_text))
                self.upsert_product_user_settings(row["product_code"], inventory_file_path=after)
            for row in page_rows:
                before = clean(row["inventory_file_path"])
                after = normalize_windows_path(before.replace(old_text, new_text))
                self.conn.execute(
                    "UPDATE product_transfer_pages SET inventory_file_path = ?, updated_at = ? WHERE id = ?",
                    (after, now_text(), row["id"]),
                )
            self.conn.commit()
        return int(count)

    def variants_for_product(self, product_code: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT v.variant_code, v.product_code, v.is_set,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size,
                   v.jan_code,
                   COALESCE(vus.color_order, v.color_order) AS color_order,
                   COALESCE(vus.size_order, v.size_order) AS size_order,
                   COALESCE(vus.sold_out, 0) AS sold_out,
                   GROUP_CONCAT(ms.mall || ':' || ms.sku, ' / ') AS mall_skus
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            LEFT JOIN mall_skus ms ON ms.variant_code = v.variant_code AND ms.enabled = 1
            WHERE v.product_code = ?
            GROUP BY v.variant_code
            ORDER BY color_order, color, size_order, size, v.variant_code
            """,
            (product_code,),
        ).fetchall()

    def variant_grid_for_product(self, product_code: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size,
                   MIN(COALESCE(vus.color_order, v.color_order)) AS color_order,
                   MIN(COALESCE(vus.size_order, v.size_order)) AS size_order
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.product_code = ?
            GROUP BY COALESCE(NULLIF(vus.color, ''), v.color), COALESCE(NULLIF(vus.size, ''), v.size)
            ORDER BY color_order, color, size_order, size
            """,
            (product_code,),
        ).fetchall()

    def update_variant_settings(
        self,
        variant_code: str,
        color: str,
        size: str,
        jan_code: str,
        color_order: int,
        size_order: int,
        sold_out: bool = False,
    ) -> None:
        self.conn.execute(
            """
            UPDATE variants
            SET jan_code = ?,
                updated_at = ?
            WHERE variant_code = ?
            """,
            (normalize_jan_code(jan_code), now_text(), variant_code),
        )
        self.conn.execute(
            """
            INSERT INTO variant_user_settings(variant_code, color, size, color_order, size_order, sold_out, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(variant_code) DO UPDATE SET
                color = excluded.color,
                size = excluded.size,
                color_order = excluded.color_order,
                size_order = excluded.size_order,
                sold_out = excluded.sold_out,
                updated_at = excluded.updated_at
            """,
            (variant_code, color, size, color_order, size_order, 1 if sold_out else 0, now_text()),
        )
        self.conn.commit()

    def variant_sold_out_keys(self, product_code: str) -> set[tuple[str, str]]:
        rows = self.conn.execute(
            """
            SELECT COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.product_code = ? AND COALESCE(vus.sold_out, 0) = 1
            """,
            (product_code,),
        ).fetchall()
        return {(clean(row["color"]), clean(row["size"])) for row in rows}

    def is_variant_sold_out(self, product_code: str, color: str, size: str) -> bool:
        return (clean(color), clean(size)) in self.variant_sold_out_keys(product_code)

    def set_variant_sold_out_by_product_color_size(self, product_code: str, color: str, size: str) -> tuple[str, str]:
        target_color = clean(color)
        target_size = clean(size)
        rows = self.conn.execute(
            """
            SELECT v.variant_code,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size,
                   COALESCE(vus.color_order, v.color_order) AS color_order,
                   COALESCE(vus.size_order, v.size_order) AS size_order
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.product_code = ?
            """,
            (product_code,),
        ).fetchall()
        matches = [row for row in rows if clean(row["color"]) == target_color and clean(row["size"]) == target_size]
        if len(matches) == 0:
            return "not_found", ""
        if len(matches) > 1:
            return "multiple", ", ".join(clean(row["variant_code"]) for row in matches[:5])
        row = matches[0]
        self.conn.execute(
            """
            INSERT INTO variant_user_settings(variant_code, color, size, color_order, size_order, sold_out, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(variant_code) DO UPDATE SET
                color = excluded.color,
                size = excluded.size,
                color_order = excluded.color_order,
                size_order = excluded.size_order,
                sold_out = 1,
                updated_at = excluded.updated_at
            """,
            (
                row["variant_code"],
                target_color,
                target_size,
                row["color_order"],
                row["size_order"],
                now_text(),
            ),
        )
        self.conn.commit()
        return "updated", clean(row["variant_code"])

    def product_color_order(self, product_code: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   MIN(COALESCE(vus.color_order, v.color_order)) AS color_order,
                   COUNT(*) AS variant_count
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.product_code = ?
            GROUP BY COALESCE(NULLIF(vus.color, ''), v.color)
            ORDER BY color_order, color
            """,
            (product_code,),
        ).fetchall()

    def move_product_color(self, product_code: str, color: str, direction: int) -> None:
        colors = self.product_color_order(product_code)
        idx = next((i for i, row in enumerate(colors) if row["color"] == color), None)
        if idx is None:
            return
        target_idx = idx + direction
        if target_idx < 0 or target_idx >= len(colors):
            return
        current = colors[idx]
        target = colors[target_idx]
        current_order = int(current["color_order"] or idx + 1)
        target_order = int(target["color_order"] or target_idx + 1)
        self.set_product_color_order_value(product_code, current["color"], target_order)
        self.set_product_color_order_value(product_code, target["color"], current_order)
        self.conn.commit()

    def save_product_color_order(self, product_code: str, colors: list[str]) -> None:
        for index, color in enumerate(colors, start=1):
            self.set_product_color_order_value(product_code, color, index)
        self.conn.commit()

    def set_product_color_order_value(self, product_code: str, color: str, color_order: int) -> None:
        rows = self.conn.execute(
            """
            SELECT v.variant_code,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS effective_color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS effective_size,
                   COALESCE(vus.size_order, v.size_order) AS effective_size_order
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.product_code = ?
            """,
            (product_code,),
        ).fetchall()
        for row in rows:
            if clean(row["effective_color"]) != clean(color):
                continue
            self.conn.execute(
                """
                INSERT INTO variant_user_settings(variant_code, color, size, color_order, size_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(variant_code) DO UPDATE SET
                    color = excluded.color,
                    size = excluded.size,
                    color_order = excluded.color_order,
                    size_order = excluded.size_order,
                    updated_at = excluded.updated_at
                """,
                (
                    row["variant_code"],
                    clean(row["effective_color"]),
                    clean(row["effective_size"]),
                    color_order,
                    row["effective_size_order"],
                    now_text(),
                ),
            )

    def import_rakuten_normal_item_images(self, path: Path, shop_url: str) -> tuple[int, int, int]:
        rows = read_csv_dicts(path)
        image_by_code: dict[str, str] = {}
        for row in rows:
            rakuten_code = clean(row.get("商品管理番号（商品URL）"))
            if not rakuten_code or rakuten_code in image_by_code:
                continue
            image_path = clean(row.get("商品画像パス1")) or clean(row.get("SKU画像パス")) or clean(row.get("白背景画像パス"))
            image_url = build_rakuten_image_url(shop_url, image_path)
            if image_url:
                image_by_code[rakuten_code] = image_url

        updated = 0
        missing = 0
        for rakuten_code, image_url in image_by_code.items():
            rows = self.conn.execute(
                """
                SELECT product_code
                FROM products
                WHERE rakuten_parent_code = ? OR product_code = ?
                """,
                (rakuten_code, rakuten_code),
            ).fetchall()
            if rows:
                for product in rows:
                    self.upsert_product_user_settings(product["product_code"], thumbnail_url=image_url)
                updated += len(rows)
            else:
                missing += 1
        self.conn.commit()
        return len(image_by_code), updated, missing

    def active_batch_id(self) -> int:
        today = today_text()
        row = self.conn.execute(
            "SELECT id FROM import_batches WHERE batch_date = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (today,),
        ).fetchone()
        if row:
            return int(row["id"])
        self.conn.execute("UPDATE import_batches SET status = 'closed' WHERE status = 'active'")
        cur = self.conn.execute(
            "INSERT INTO import_batches(batch_date, created_at, status) VALUES (?, ?, 'active')",
            (today, now_text()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def import_zr_item(self, path: Path) -> int:
        rows = read_csv_dicts(path)
        count = 0
        self.conn.execute("DELETE FROM mall_skus WHERE source_file LIKE 'zr_item%'")
        self.conn.execute("DELETE FROM variants WHERE source_file LIKE 'zr_item%'")
        for row in rows:
            product_code = clean(row.get("コード(更新時使用)"))
            if not product_code:
                continue
            display_name = clean(row.get("商品名")) or product_code
            is_set = 1 if clean(row.get("セット商品フラグ")) == "1" else 0
            rakuten_parent = clean(row.get("楽天商品管理番号(URL)")) or clean(row.get("楽天商品番号"))
            jan_code = row_jan_code(row)
            self.conn.execute(
                """
                INSERT INTO products(product_code, display_name, rakuten_parent_code, jan_code, is_set, source_file, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_code) DO UPDATE SET
                    display_name = excluded.display_name,
                    rakuten_parent_code = excluded.rakuten_parent_code,
                    jan_code = CASE WHEN excluded.jan_code <> '' THEN excluded.jan_code ELSE products.jan_code END,
                    is_set = excluded.is_set,
                    source_file = excluded.source_file,
                    updated_at = excluded.updated_at
                """,
                (product_code, display_name, rakuten_parent, jan_code, is_set, path.name, now_text()),
            )
            if not is_set and clean(row.get("規格設定(有/無)")) == "設定無し":
                self._insert_single_sku_product_variant(row, product_code, path.name)
            count += 1
        self.conn.commit()
        return count

    def _insert_single_sku_product_variant(self, row: dict[str, str], product_code: str, source_file: str) -> None:
        jan_code = row_jan_code(row)
        self.conn.execute(
            """
            INSERT INTO variants(variant_code, product_code, is_set, color, size, jan_code, color_order, size_order, source_file, updated_at)
            VALUES (?, ?, 0, '', '', ?, 1, 1, ?, ?)
            ON CONFLICT(variant_code) DO UPDATE SET
                product_code = excluded.product_code,
                is_set = excluded.is_set,
                color = excluded.color,
                size = excluded.size,
                jan_code = CASE WHEN excluded.jan_code <> '' THEN excluded.jan_code ELSE variants.jan_code END,
                color_order = excluded.color_order,
                size_order = excluded.size_order,
                source_file = excluded.source_file,
                updated_at = excluded.updated_at
            """,
            (product_code, product_code, jan_code, source_file, now_text()),
        )
        sku_specs = [
            (MALL_RAKUTEN, ["楽天システム連携用SKU番号", "楽天SKU管理番号", "楽天商品番号", "楽天商品管理番号(URL)"], "楽天on/off"),
            (MALL_YAHOO, ["Yahoo!コード"], "Yahoo!on/off"),
            (MALL_AMAZON, ["Amazonコード"], "Amazonon/off"),
            (MALL_MERCARI, ["メルカリ商品管理コード"], "メルカリon/off"),
        ]
        for mall, columns, onoff_col in sku_specs:
            sku = next((clean(row.get(col)) for col in columns if clean(row.get(col))), product_code)
            enabled = 1 if clean(row.get(onoff_col)) != "0" else 0
            self.conn.execute(
                """
                INSERT OR IGNORE INTO mall_skus(variant_code, mall, sku, mall_color, mall_size, enabled, source_file, updated_at)
                VALUES (?, ?, ?, '', '', ?, ?, ?)
                """,
                (product_code, mall, sku, enabled, source_file, now_text()),
            )

    def import_zr_select(self, path: Path) -> int:
        rows = read_csv_dicts(path)
        count = 0
        per_product_color_seen: dict[str, dict[str, int]] = defaultdict(dict)
        per_product_size_seen: dict[str, dict[str, int]] = defaultdict(dict)

        self.conn.execute("DELETE FROM mall_skus WHERE source_file NOT LIKE 'zr_item%'")
        for row in rows:
            variant_code = clean(row.get("コード(更新時使用)"))
            product_code = clean(row.get("親商品コード(新規登録時使用)"))
            if not variant_code or not product_code:
                continue
            is_set = 1 if clean(row.get("セット商品フラグ(閲覧用)")) == "1" else 0
            color = clean(row.get("楽天項目1"))
            size = clean(row.get("楽天項目2"))
            jan_code = row_jan_code(row)
            if color not in per_product_color_seen[product_code]:
                per_product_color_seen[product_code][color] = len(per_product_color_seen[product_code]) + 1
            if size not in per_product_size_seen[product_code]:
                per_product_size_seen[product_code][size] = len(per_product_size_seen[product_code]) + 1
            color_order = per_product_color_seen[product_code][color]
            size_order = per_product_size_seen[product_code][size]
            self.conn.execute(
                """
                INSERT INTO variants(variant_code, product_code, is_set, color, size, jan_code, color_order, size_order, source_file, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(variant_code) DO UPDATE SET
                    product_code = excluded.product_code,
                    is_set = excluded.is_set,
                    color = excluded.color,
                    size = excluded.size,
                    jan_code = CASE WHEN excluded.jan_code <> '' THEN excluded.jan_code ELSE variants.jan_code END,
                    color_order = excluded.color_order,
                    size_order = excluded.size_order,
                    source_file = excluded.source_file,
                    updated_at = excluded.updated_at
                """,
                (variant_code, product_code, is_set, color, size, jan_code, color_order, size_order, path.name, now_text()),
            )
            self._insert_mall_sku(row, variant_code, MALL_RAKUTEN, "楽天システム連携用SKU番号", "楽天項目1", "楽天項目2", "楽天on/off", path.name)
            self._insert_mall_sku(row, variant_code, MALL_YAHOO, "Yahoo!コード", "Yahoo!項目1", "Yahoo!項目2", "Yahoo!on/off", path.name)
            self._insert_mall_sku(row, variant_code, MALL_AMAZON, "Amazonコード", "Amazon項目1", "Amazon項目2", "Amazonon/off", path.name)
            self._insert_mall_sku(row, variant_code, MALL_MERCARI, "メルカリ商品管理コード", "メルカリ項目1", "メルカリ項目2", "メルカリon/off", path.name)
            count += 1
        self._record_duplicate_sku_warnings()
        self.conn.commit()
        return count

    def _insert_mall_sku(
        self,
        row: dict[str, str],
        variant_code: str,
        mall: str,
        sku_col: str,
        color_col: str,
        size_col: str,
        onoff_col: str,
        source_file: str,
    ) -> None:
        sku = clean(row.get(sku_col))
        if not sku:
            return
        enabled = 1 if clean(row.get(onoff_col)) != "0" else 0
        self.conn.execute(
            """
            INSERT OR IGNORE INTO mall_skus(variant_code, mall, sku, mall_color, mall_size, enabled, source_file, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (variant_code, mall, sku, clean(row.get(color_col)), clean(row.get(size_col)), enabled, source_file, now_text()),
        )

    def _record_duplicate_sku_warnings(self) -> None:
        rows = self.conn.execute(
            """
            SELECT mall, sku, COUNT(DISTINCT variant_code) AS cnt, GROUP_CONCAT(DISTINCT variant_code) AS variants
            FROM mall_skus
            GROUP BY mall, sku
            HAVING cnt > 1
            """
        ).fetchall()
        for row in rows:
            self.warn(
                "duplicate_sku",
                f"{row['mall']} SKUが複数バリエーションに紐づいています: {row['sku']}",
                clean(row["variants"]),
            )

    def import_parent_contents(self, path: Path) -> int:
        rows = read_csv_dicts(path)
        self.conn.execute("DELETE FROM set_components")
        count = 0
        for row in rows:
            parent = clean(row.get("親商品コード"))
            child = clean(row.get("子商品コード"))
            try:
                qty = int(float(clean(row.get("セット数")) or "0"))
            except ValueError:
                qty = 0
            if not parent or not child or qty <= 0:
                self.warn("bad_set_component", "セット構成行を取り込めませんでした", json.dumps(row, ensure_ascii=False))
                continue
            self.conn.execute(
                """
                INSERT INTO set_components(parent_variant_code, child_variant_code, component_quantity, source_file, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(parent_variant_code, child_variant_code) DO UPDATE SET
                    component_quantity = excluded.component_quantity,
                    source_file = excluded.source_file,
                    updated_at = excluded.updated_at
                """,
                (parent, child, qty, path.name, now_text()),
            )
            count += 1
        self.conn.commit()
        return count

    def import_order_file(self, path: Path, file_type: str) -> tuple[int, int, int]:
        batch_id = self.active_batch_id()
        digest = file_hash(path)
        existing = self.conn.execute(
            "SELECT id FROM import_files WHERE batch_id = ? AND file_hash = ?",
            (batch_id, digest),
        ).fetchone()
        if existing:
            raise ValueError("このファイルは本日の集計にすでに読み込まれています。")

        rows = read_csv_dicts(path)
        normalized: list[tuple[int, str, str, str, str, int, str]] = []
        bad_rows: list[tuple[int, str, str]] = []
        bad_count = 0
        skipped_count = 0
        for idx, row in enumerate(rows, start=2):
            raw_json = json.dumps(row, ensure_ascii=False)
            try:
                if file_type == "mall_order":
                    item = self._normalize_mall_order(row)
                elif file_type == "mercari_order":
                    item = self._normalize_mercari_order(row)
                else:
                    raise ValueError(f"unknown file_type: {file_type}")
                order_id, mall, sku, sub_code, qty = item
                duplicate_key = (mall, order_id, sku, sub_code)
                if order_id and self.import_line_exists(batch_id, mall, order_id, sku, sub_code):
                    skipped_count += 1
                    continue
                normalized.append((idx, order_id, mall, sku, sub_code, qty, raw_json))
            except ValueError as exc:
                if str(exc) == "SKIP_UNPAID_MERCARI":
                    skipped_count += 1
                    continue
                bad_count += 1
                bad_rows.append((idx, str(exc), raw_json))
                self.warn("bad_order_line", str(exc), f"{path.name}:{idx}")

        cur = self.conn.execute(
            """
            INSERT INTO import_files(batch_id, file_name, file_path, file_type, file_hash, imported_at, row_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, path.name, str(path), file_type, digest, now_text(), len(normalized)),
        )
        file_id = int(cur.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO import_lines(batch_id, file_id, file_name, source_row, source_order_id, source_mall, source_sku, source_sub_code, quantity, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (batch_id, file_id, path.name, source_row, order_id, mall, sku, sub_code, qty, raw_json, now_text())
                for source_row, order_id, mall, sku, sub_code, qty, raw_json in normalized
            ],
        )
        self.conn.executemany(
            """
            INSERT INTO unresolved_items(batch_id, file_id, file_name, source_row, source_mall, source_sku, source_sub_code, quantity, reason, candidates_json, raw_json, created_at)
            VALUES (?, ?, ?, ?, '', '', '', 0, ?, '[]', ?, ?)
            """,
            [(batch_id, file_id, path.name, source_row, reason, raw_json, now_text()) for source_row, reason, raw_json in bad_rows],
        )
        self.conn.commit()
        return len(normalized), bad_count, skipped_count

    def import_line_exists(self, batch_id: int, mall: str, order_id: str, sku: str, sub_code: str) -> bool:
        if not order_id:
            return False
        row = self.conn.execute(
            """
            SELECT 1
            FROM import_lines
            WHERE batch_id = ?
              AND source_mall = ?
              AND source_order_id = ?
              AND source_sku = ?
              AND source_sub_code = ?
            LIMIT 1
            """,
            (batch_id, mall, order_id, sku, sub_code),
        ).fetchone()
        return bool(row)

    def _normalize_mall_order(self, row: dict[str, str]) -> tuple[str, str, str, str, int]:
        order_id = clean(row.get("受注番号")) or clean(row.get("注文番号")) or clean(row.get("order_id"))
        mall = clean(row.get("モール"))
        item_code = clean(row.get("商品番号"))
        sub_code = clean(row.get("商品番号サブ"))
        qty = self._parse_qty(row.get("販売個数"))
        if mall == MALL_RAKUTEN:
            sku = self._best_order_sku(mall, item_code, sub_code, prefer_sub=False)
        elif mall == MALL_YAHOO:
            sku = self._best_order_sku(mall, item_code, sub_code, prefer_sub=True)
        elif mall == MALL_AMAZON:
            sku = item_code
        else:
            raise ValueError(f"未知のモールです: {mall}")
        if not sku:
            raise ValueError(f"SKUが空です: {mall}")
        return order_id, mall, sku, sub_code, qty

    def _best_order_sku(self, mall: str, item_code: str, sub_code: str, prefer_sub: bool) -> str:
        candidates = [sub_code, item_code] if prefer_sub else [item_code, sub_code]
        for candidate in candidates:
            if not candidate:
                continue
            if self._sku_exists_for_order(mall, candidate):
                return candidate
        return (sub_code or item_code) if prefer_sub else (item_code or sub_code)

    def _sku_exists_for_order(self, mall: str, sku: str) -> bool:
        if not sku:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM mall_skus WHERE mall = ? AND sku = ? AND enabled = 1 LIMIT 1",
            (mall, sku),
        ).fetchone()
        if row:
            return True
        row = self.conn.execute(
            "SELECT 1 FROM sku_resolution_rules WHERE mall = ? AND source_sku = ? AND enabled = 1 LIMIT 1",
            (mall, sku),
        ).fetchone()
        return bool(row)

    def _normalize_mercari_order(self, row: dict[str, str]) -> tuple[str, str, str, str, int]:
        if not clean(row.get("buyer_name")):
            raise ValueError("SKIP_UNPAID_MERCARI")
        order_id = clean(row.get("order_id"))
        sku = clean(row.get("original_product_id"))
        qty = self._parse_qty(row.get("quantity"))
        if not sku:
            raise ValueError("メルカリ original_product_id が空です")
        return order_id, MALL_MERCARI, sku, "", qty

    def _parse_qty(self, value: object) -> int:
        try:
            qty = int(float(clean(value)))
        except ValueError as exc:
            raise ValueError(f"数量が数値ではありません: {value}") from exc
        if qty <= 0:
            raise ValueError(f"数量が0以下です: {value}")
        return qty

    def build_transfer_tasks(self) -> tuple[int, int]:
        batch_id = self.active_batch_id()
        self.conn.execute(
            "DELETE FROM unresolved_items WHERE batch_id = ? AND reason IN ('SKU未登録', 'SKU重複')",
            (batch_id,),
        )
        agg: dict[tuple[str, str, str], int] = defaultdict(int)
        unmatched = 0

        lines = self.conn.execute(
            "SELECT * FROM import_lines WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        for line in lines:
            variants = self.conn.execute(
                """
                SELECT DISTINCT variant_code
                FROM mall_skus
                WHERE mall = ? AND sku = ? AND enabled = 1
                """,
                (line["source_mall"], line["source_sku"]),
            ).fetchall()
            if len(variants) != 1:
                resolution_rows = self.sku_resolution_rules(line["source_mall"], line["source_sku"])
                if resolution_rows:
                    for rule in resolution_rows:
                        self._add_single_variant(agg, rule["child_variant_code"], int(line["quantity"]) * int(rule["quantity"]))
                else:
                    unmatched += 1
                    reason = "SKU未登録" if len(variants) == 0 else "SKU重複"
                    candidates = self._sku_candidates(line["source_mall"], line["source_sku"])
                    self._save_unresolved_line(line, reason, candidates)
                    self.warn(
                        "unmatched_order_sku",
                        f"SKUを一意に照合できません: {line['source_mall']} / {line['source_sku']}",
                        f"matches={len(variants)}",
                    )
                continue
            self._add_variant_quantity(agg, variants[0]["variant_code"], int(line["quantity"]))

        self._ensure_snapshot_from_existing_tasks(batch_id)
        previous_snapshot = self._snapshot_rows(batch_id)
        delta_agg = self._delta_agg_from_snapshot(batch_id, agg)
        aggregation_round = self.next_aggregation_round(batch_id) if delta_agg else 1
        self._create_tasks_from_agg(batch_id, delta_agg, previous_snapshot, aggregation_round)
        self._save_aggregation_snapshot(batch_id, agg)
        self.conn.commit()
        task_count = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM transfer_tasks WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["cnt"]
        return int(task_count), unmatched

    def next_aggregation_round(self, batch_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(aggregation_round), 0) AS max_round FROM transfer_tasks WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        next_round = int(row["max_round"] or 0) + 1
        if next_round > 3:
            raise RuntimeError("集計回は3回までです。受注データをリセットするか、現在の未処理分を処理してから再集計してください。")
        return next_round

    def _snapshot_rows(self, batch_id: int) -> dict[tuple[str, str, str], int]:
        rows = self.conn.execute(
            """
            SELECT product_code, color, size, quantity
            FROM aggregation_snapshots
            WHERE batch_id = ?
            """,
            (batch_id,),
        ).fetchall()
        return {
            (clean(row["product_code"]), clean(row["color"]), clean(row["size"])): int(row["quantity"])
            for row in rows
        }

    def snapshot_quantities_for_product(self, product_code: str) -> dict[tuple[str, str], int]:
        batch_id = self.active_batch_id()
        rows = self.conn.execute(
            """
            SELECT color, size, quantity
            FROM aggregation_snapshots
            WHERE batch_id = ? AND product_code = ?
            """,
            (batch_id, product_code),
        ).fetchall()
        multiplier = self.product_quantity_multiplier(product_code)
        return {
            (clean(row["color"]), clean(row["size"])): int(row["quantity"]) * multiplier
            for row in rows
        }

    def _ensure_snapshot_from_existing_tasks(self, batch_id: int) -> None:
        if self._snapshot_rows(batch_id):
            return
        task_rows = self.conn.execute(
            "SELECT * FROM transfer_tasks WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        if not task_rows:
            return
        snapshot: dict[tuple[str, str, str], int] = defaultdict(int)
        for row in task_rows:
            try:
                sizes = json.loads(row["sizes_json"] or "[]")
                quantities = json.loads(row["quantities_json"] or "[]")
            except json.JSONDecodeError:
                continue
            multiplier = max(1, int(row["applied_quantity_multiplier"] or 1))
            for size, quantity in zip(sizes, quantities):
                text = clean(quantity)
                if not text:
                    continue
                try:
                    qty = int(float(text))
                except ValueError:
                    continue
                snapshot[(row["product_code"], row["color"], clean(size))] += max(0, qty // multiplier)
        self._save_aggregation_snapshot(batch_id, snapshot)

    def _delta_agg_from_snapshot(
        self,
        batch_id: int,
        current: dict[tuple[str, str, str], int],
    ) -> dict[tuple[str, str, str], int]:
        previous = self._snapshot_rows(batch_id)
        if not previous:
            return defaultdict(int, current)
        delta: dict[tuple[str, str, str], int] = defaultdict(int)
        for key, qty in current.items():
            diff = int(qty) - int(previous.get(key, 0))
            if diff > 0:
                delta[key] = diff
        return delta

    def _save_aggregation_snapshot(self, batch_id: int, agg: dict[tuple[str, str, str], int]) -> None:
        now = now_text()
        self.conn.execute("DELETE FROM aggregation_snapshots WHERE batch_id = ?", (batch_id,))
        for (product_code, color, size), qty in agg.items():
            self.conn.execute(
                """
                INSERT INTO aggregation_snapshots(batch_id, product_code, color, size, quantity, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (batch_id, product_code, color, size, int(qty), now),
            )

    def _sku_candidates(self, mall: str, sku: str) -> list[dict[str, str]]:
        rows = self.conn.execute(
            """
                SELECT ms.variant_code, v.product_code, p.display_name,
                       COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                       COALESCE(NULLIF(vus.size, ''), v.size) AS size
                FROM mall_skus ms
                LEFT JOIN variants v ON v.variant_code = ms.variant_code
                LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
                LEFT JOIN products p ON p.product_code = v.product_code
                WHERE ms.mall = ? AND ms.sku = ? AND ms.enabled = 1
                ORDER BY p.display_name, COALESCE(vus.color_order, v.color_order), COALESCE(vus.size_order, v.size_order)
            """,
            (mall, sku),
        ).fetchall()
        return [
            {
                "variant_code": clean(row["variant_code"]),
                "product_code": clean(row["product_code"]),
                "product_name": clean(row["display_name"]),
                "color": clean(row["color"]),
                "size": clean(row["size"]),
            }
            for row in rows
        ]

    def sku_resolution_rules(self, mall: str, sku: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM sku_resolution_rules
            WHERE mall = ? AND source_sku = ? AND enabled = 1
            ORDER BY id
            """,
            (mall, sku),
        ).fetchall()

    def save_sku_resolution_rules(
        self,
        mall: str,
        source_sku: str,
        rows: list[tuple[str, int]],
        note: str = "",
    ) -> None:
        mall = clean(mall)
        source_sku = clean(source_sku)
        if not mall or not source_sku:
            raise ValueError("モールとSKUが空です。")
        if not rows:
            raise ValueError("展開先SKUを1件以上追加してください。")
        now = now_text()
        self.conn.execute(
            "UPDATE sku_resolution_rules SET enabled = 0, updated_at = ? WHERE mall = ? AND source_sku = ?",
            (now, mall, source_sku),
        )
        for child_variant_code, qty in rows:
            variant_code = clean(child_variant_code)
            quantity = max(1, int(qty))
            exists = self.conn.execute(
                "SELECT 1 FROM variants WHERE variant_code = ?",
                (variant_code,),
            ).fetchone()
            if not exists:
                raise ValueError(f"子SKUが存在しません: {variant_code}")
            self.conn.execute(
                """
                INSERT INTO sku_resolution_rules(mall, source_sku, child_variant_code, quantity, enabled, note, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(mall, source_sku, child_variant_code) DO UPDATE SET
                    quantity = excluded.quantity,
                    enabled = 1,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (mall, source_sku, variant_code, quantity, clean(note), now),
            )
        self.conn.commit()

    def _save_unresolved_line(self, line: sqlite3.Row, reason: str, candidates: list[dict[str, str]]) -> None:
        self.conn.execute(
            """
            INSERT INTO unresolved_items(
                batch_id, file_id, file_name, source_row, source_order_id, source_mall, source_sku,
                source_sub_code, quantity, reason, candidates_json, raw_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                line["batch_id"],
                line["file_id"],
                line["file_name"],
                line["source_row"],
                line["source_order_id"],
                line["source_mall"],
                line["source_sku"],
                line["source_sub_code"],
                line["quantity"],
                reason,
                json.dumps(candidates, ensure_ascii=False),
                line["raw_json"],
                now_text(),
            ),
        )

    def _add_variant_quantity(self, agg: dict[tuple[str, str, str], int], variant_code: str, qty: int) -> None:
        components = self.conn.execute(
            "SELECT child_variant_code, component_quantity FROM set_components WHERE parent_variant_code = ?",
            (variant_code,),
        ).fetchall()
        if components:
            for component in components:
                self._add_single_variant(agg, component["child_variant_code"], qty * int(component["component_quantity"]))
        else:
            self._add_single_variant(agg, variant_code, qty)

    def _add_single_variant(self, agg: dict[tuple[str, str, str], int], variant_code: str, qty: int) -> None:
        row = self.conn.execute(
            """
            SELECT v.product_code,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.variant_code = ?
            """,
            (variant_code,),
        ).fetchone()
        if not row:
            self.warn("missing_child_variant", f"バリエーションが見つかりません: {variant_code}")
            return
        agg[(row["product_code"], row["color"], row["size"])] += qty

    def _create_tasks_from_agg(
        self,
        batch_id: int,
        agg: dict[tuple[str, str, str], int],
        previous_snapshot: dict[tuple[str, str, str], int] | None = None,
        aggregation_round: int = 1,
    ) -> None:
        previous_snapshot = previous_snapshot or {}
        grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        for (product_code, color, size), qty in agg.items():
            grouped[(product_code, color)][size] = grouped[(product_code, color)].get(size, 0) + qty

        row = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM transfer_tasks WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        sort_order = int(row["max_order"] or 0) + 1
        for product_code in sorted({key[0] for key in grouped}):
            product = self.conn.execute(
                "SELECT display_name FROM products WHERE product_code = ?",
                (product_code,),
            ).fetchone()
            product_name = product["display_name"] if product else product_code
            quantity_multiplier = self.product_quantity_multiplier(product_code)
            if quantity_multiplier != 1:
                product_name = self._apply_quantity_marker(product_name, quantity_multiplier)
            product_had_previous = any(key[0] == product_code for key in previous_snapshot)
            colors = self.conn.execute(
                """
                SELECT COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                       MIN(COALESCE(vus.color_order, v.color_order)) AS color_order
                FROM variants v
                LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
                WHERE v.product_code = ?
                GROUP BY COALESCE(NULLIF(vus.color, ''), v.color)
                ORDER BY color_order, color
                """,
                (product_code,),
            ).fetchall()
            sizes = self.conn.execute(
                """
                SELECT COALESCE(NULLIF(vus.size, ''), v.size) AS size,
                       MIN(COALESCE(vus.size_order, v.size_order)) AS size_order
                FROM variants v
                LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
                WHERE v.product_code = ?
                GROUP BY COALESCE(NULLIF(vus.size, ''), v.size)
                ORDER BY size_order, size
                """,
                (product_code,),
            ).fetchall()
            size_names = [clean(row["size"]) for row in sizes]
            for color_row in colors:
                color = clean(color_row["color"])
                qmap = grouped.get((product_code, color), {})
                if not qmap:
                    continue
                quantities: list[str] = []
                previous_quantities: list[str] = []
                total = 0
                for size in size_names:
                    qty = int(qmap.get(size, 0)) * quantity_multiplier
                    quantities.append("" if qty == 0 else str(qty))
                    total += qty
                    previous_qty = int(previous_snapshot.get((product_code, color, size), 0)) * quantity_multiplier
                    previous_quantities.append("" if previous_qty == 0 else str(previous_qty))
                if total == 0:
                    continue
                color_had_previous = any(key[0] == product_code and key[1] == color for key in previous_snapshot)
                if aggregation_round <= 1:
                    task_kind = "initial"
                elif color_had_previous:
                    task_kind = "delta"
                elif product_had_previous:
                    task_kind = "new"
                else:
                    task_kind = "new"
                self.conn.execute(
                    """
                    INSERT INTO transfer_tasks(batch_id, product_code, product_name, color, sizes_json, quantities_json, previous_quantities_json, total_quantity, applied_quantity_multiplier, aggregation_round, task_kind, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        product_code,
                        product_name,
                        color,
                        json.dumps(size_names, ensure_ascii=False),
                        json.dumps(quantities, ensure_ascii=False),
                        json.dumps(previous_quantities, ensure_ascii=False),
                        total,
                        quantity_multiplier,
                        aggregation_round,
                        task_kind,
                        sort_order,
                    ),
                )
                sort_order += 1

    def task_rows(self) -> list[sqlite3.Row]:
        batch_id = self.active_batch_id()
        return self.conn.execute(
            "SELECT * FROM transfer_tasks WHERE batch_id = ? ORDER BY sort_order",
            (batch_id,),
        ).fetchall()

    def task_rows_for_pdf(self, ordered_task_ids: list[int] | None = None) -> list[sqlite3.Row]:
        rows = self.task_rows()
        if ordered_task_ids is None:
            return rows
        by_id = {int(row["id"]): row for row in rows}
        ordered: list[sqlite3.Row] = []
        for task_id in ordered_task_ids:
            row = by_id.get(int(task_id))
            if row is None:
                continue
            ordered.append(row)
        return ordered

    def mark_task(self, task_id: int, status: str) -> None:
        if status == "copied":
            self.conn.execute(
                "UPDATE transfer_tasks SET status = 'copied', retry_required = 0, retry_reason = '', copied_at = ? WHERE id = ?",
                (now_text(), task_id),
            )
        elif status == "skipped":
            self.conn.execute(
                "UPDATE transfer_tasks SET status = 'skipped', retry_required = 0, retry_reason = '', skipped_at = ? WHERE id = ?",
                (now_text(), task_id),
            )
        elif status == "pending":
            self.conn.execute(
                "UPDATE transfer_tasks SET status = 'pending', retry_required = 0, retry_reason = '', copied_at = NULL, skipped_at = NULL WHERE id = ?",
                (task_id,),
            )
        self.conn.commit()

    def mark_task_retry_required(self, task_id: int, reason: str) -> None:
        self.conn.execute(
            "UPDATE transfer_tasks SET status = 'pending', retry_required = 1, retry_reason = ?, copied_at = NULL, skipped_at = NULL WHERE id = ?",
            (clean(reason), task_id),
        )
        self.conn.commit()

    def pending_retry_required_count(self) -> int:
        batch_id = self.active_batch_id()
        row = self.conn.execute(
            "SELECT COUNT(*) AS count FROM transfer_tasks WHERE batch_id = ? AND status = 'pending' AND retry_required <> 0",
            (batch_id,),
        ).fetchone()
        return int(row["count"] if row else 0)

    def pending_task_count(self) -> int:
        batch_id = self.active_batch_id()
        row = self.conn.execute(
            "SELECT COUNT(*) AS count FROM transfer_tasks WHERE batch_id = ? AND status = 'pending'",
            (batch_id,),
        ).fetchone()
        return int(row["count"] if row else 0)

    def move_transfer_color(self, product_code: str, color: str, direction: int) -> None:
        batch_id = self.active_batch_id()
        rows = self.conn.execute(
            """
            SELECT id, color, sort_order
            FROM transfer_tasks
            WHERE batch_id = ? AND product_code = ?
            ORDER BY sort_order
            """,
            (batch_id, product_code),
        ).fetchall()
        idx = next((i for i, row in enumerate(rows) if row["color"] == color), None)
        if idx is None:
            self.move_product_color(product_code, color, direction)
            return
        target_idx = idx + direction
        if target_idx < 0 or target_idx >= len(rows):
            return
        current = rows[idx]
        target = rows[target_idx]
        self.conn.execute(
            "UPDATE transfer_tasks SET sort_order = ? WHERE id = ?",
            (target["sort_order"], current["id"]),
        )
        self.conn.execute(
            "UPDATE transfer_tasks SET sort_order = ? WHERE id = ?",
            (current["sort_order"], target["id"]),
        )
        self.conn.commit()
        self.move_product_color(product_code, color, direction)

    def summary(self) -> dict[str, int]:
        batch_id = self.active_batch_id()
        values = {}
        for name, sql in {
            "products": "SELECT COUNT(*) AS cnt FROM products",
            "variants": "SELECT COUNT(*) AS cnt FROM variants",
            "mall_skus": "SELECT COUNT(*) AS cnt FROM mall_skus",
            "set_components": "SELECT COUNT(*) AS cnt FROM set_components",
            "import_files": "SELECT COUNT(*) AS cnt FROM import_files WHERE batch_id = ?",
            "import_lines": "SELECT COUNT(*) AS cnt FROM import_lines WHERE batch_id = ?",
            "transfer_tasks": "SELECT COUNT(*) AS cnt FROM transfer_tasks WHERE batch_id = ?",
            "unresolved_items": "SELECT COUNT(*) AS cnt FROM unresolved_items WHERE batch_id = ?",
            "warnings": "SELECT COUNT(*) AS cnt FROM warnings",
        }.items():
            if name in {"import_files", "import_lines", "transfer_tasks", "unresolved_items"}:
                row = self.conn.execute(sql, (batch_id,)).fetchone()
            else:
                row = self.conn.execute(sql).fetchone()
            values[name] = int(row["cnt"])
        return values

    def reset_master_data(self) -> None:
        self.conn.execute("DELETE FROM mall_skus")
        self.conn.execute("DELETE FROM set_components")
        self.conn.execute("DELETE FROM variants")
        self.conn.execute("DELETE FROM products")
        self.conn.execute("DELETE FROM warnings WHERE category IN ('duplicate_sku', 'bad_set_component', 'missing_child_variant')")
        self.conn.commit()

    def reset_user_settings(self) -> None:
        self.conn.execute("DELETE FROM product_user_settings")
        self.conn.execute("DELETE FROM variant_user_settings")
        self.conn.execute("DELETE FROM product_copy_settings")
        self.conn.execute("DELETE FROM sku_resolution_rules")
        self.conn.commit()

    def reset_current_order_data(self) -> None:
        batch_id = self.active_batch_id()
        self.conn.execute("DELETE FROM transfer_tasks WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM aggregation_snapshots WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM stock_alerts WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM unresolved_items WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM import_lines WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM import_files WHERE batch_id = ?", (batch_id,))
        self.conn.execute("DELETE FROM warnings WHERE category IN ('bad_order_line', 'unmatched_order_sku')")
        self.conn.commit()

    def unresolved_rows_for_pdf(self) -> list[dict[str, str]]:
        batch_id = self.active_batch_id()
        rows = self.conn.execute(
            """
            SELECT file_name, source_row, source_mall, source_sku, quantity, reason, candidates_json, raw_json
            FROM unresolved_items
            WHERE batch_id = ?
            ORDER BY reason, file_name, source_row
            """,
            (batch_id,),
        ).fetchall()
        result: list[dict[str, str]] = []
        for row in rows:
            raw = self._loads_json_object(row["raw_json"])
            candidates = self._loads_json_list(row["candidates_json"])
            product_name = clean(raw.get("注文商品名")) or clean(raw.get("product_name"))
            options = clean(raw.get("商品備考"))
            if not options:
                color = clean(raw.get("バリエーション項目選択肢1")) or clean(raw.get("メルカリ項目1"))
                size = clean(raw.get("バリエーション項目選択肢2")) or clean(raw.get("メルカリ項目2"))
                options = " / ".join(part for part in [color, size] if part)
            if candidates:
                options = "候補: " + " / ".join(
                    f"{clean(c.get('product_name'))} {clean(c.get('color'))} {clean(c.get('size'))}".strip()
                    for c in candidates
                )
            qty = str(row["quantity"] or clean(raw.get("販売個数")) or clean(raw.get("quantity")) or "")
            result.append(
                {
                    "reason": clean(row["reason"]),
                    "mall": clean(row["source_mall"]) or clean(raw.get("モール")) or "不明",
                    "sku": clean(row["source_sku"]) or clean(raw.get("商品番号")) or clean(raw.get("original_product_id")),
                    "quantity": qty,
                    "product_name": product_name or "(商品名なし)",
                    "options": options.replace("\r\n", " / ").replace("\n", " / "),
                    "source": f"{row['file_name']}:{row['source_row']}",
                }
            )
        return result

    def _loads_json_object(self, text: str) -> dict[str, str]:
        try:
            value = json.loads(text or "{}")
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _loads_json_list(self, text: str) -> list[dict[str, str]]:
        try:
            value = json.loads(text or "[]")
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []

    def _export_rows_pdf(
        self,
        output_dir: Path,
        file_prefix: str,
        title_text: str,
        task_rows: list[object],
        unresolved: list[dict[str, str]],
    ) -> Path:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / f"{file_prefix}.pdf"
        pdf_font = self.register_pdf_font(pdfmetrics, UnicodeCIDFont, TTFont)
        pdf_font_size = self.pdf_font_size()
        pdf_table_font_size = max(5, pdf_font_size - 1)
        show_status = self.get_setting("pdf_show_status", "1") != "0"
        if show_status and task_rows and not any(clean(row["status"]) for row in task_rows):
            show_status = False
        show_order = self.get_setting("pdf_show_order", "1") != "0"
        show_color_total = self.get_setting("pdf_show_color_total", "1") != "0"
        styles = getSampleStyleSheet()
        normal = ParagraphStyle(
            "JapaneseNormal",
            parent=styles["Normal"],
            fontName=pdf_font,
            fontSize=pdf_font_size,
            leading=pdf_font_size + 2,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        title = ParagraphStyle(
            "JapaneseTitle",
            parent=normal,
            fontSize=pdf_font_size + 7,
            leading=pdf_font_size + 10,
            spaceAfter=6,
        )
        heading = ParagraphStyle(
            "JapaneseHeading",
            parent=normal,
            fontSize=pdf_font_size + 3,
            leading=pdf_font_size + 6,
            spaceBefore=8,
            spaceAfter=4,
        )
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=16 * mm,
            bottomMargin=10 * mm,
        )
        story = [
            Paragraph(title_text, title),
            Paragraph(f"出力日時: {now_text()}", normal),
            Spacer(1, 4 * mm),
        ]

        story.append(Paragraph("集計済み転記データ", heading))
        if task_rows:
            headers: list[str] = []
            widths: list[float] = []
            if show_status:
                headers.append("状態")
                widths.append(12 * mm)
            if show_order:
                headers.append("順")
                widths.append(9 * mm)
            maker_width = self.pdf_column_width_mm("pdf_width_maker_mm", 20, 8, 60)
            product_width = self.pdf_column_width_mm("pdf_width_product_mm", 60, 20, 100)
            color_width = self.pdf_column_width_mm("pdf_width_color_mm", 35, 10, 60)
            total_width = self.pdf_column_width_mm("pdf_width_total_mm", 10, 8, 30)
            adjustable_widths = [maker_width, product_width, color_width]
            if show_color_total:
                adjustable_widths.append(total_width)
            base_width_mm = sum(width / mm for width in widths)
            max_adjustable_width = max(1, 190 - base_width_mm - 58)
            requested_adjustable_width = sum(adjustable_widths)
            if requested_adjustable_width > max_adjustable_width:
                scale = max_adjustable_width / requested_adjustable_width
                adjustable_widths = [width * scale for width in adjustable_widths]
            maker_width, product_width, color_width = adjustable_widths[:3]
            if show_color_total:
                total_width = adjustable_widths[3]
            headers.extend(["メーカー", "商品名", "カラー"])
            widths.extend([maker_width * mm, product_width * mm, color_width * mm])
            if show_color_total:
                headers.append("小計")
                widths.append(total_width * mm)
            headers.append("サイズ／数量")
            fixed_width = sum(widths)
            widths.append(max(58 * mm, 190 * mm - fixed_width))
            data = [headers]
            product_boundary_rows: list[int] = []
            previous_product_key = None
            for row in task_rows:
                sizes = json.loads(row["sizes_json"])
                quantities = json.loads(row["quantities_json"])
                status = {"pending": "未", "copied": "済", "skipped": "スキップ"}.get(row["status"], row["status"])
                if self.pdf_row_is_copied(row):
                    quantities = [f"✓{clean(qty)}" if clean(qty) else "" for qty in quantities]
                maker, product_name = self._split_maker_product_name(row["product_name"])
                product_key = (maker, product_name)
                if previous_product_key is not None and product_key != previous_product_key:
                    product_boundary_rows.append(len(data))
                previous_product_key = product_key
                row_data = []
                if show_status:
                    row_data.append(status)
                if show_order:
                    row_data.append(str(row["sort_order"]))
                row_data.extend([
                    self._pdf_para(maker, normal),
                    self._pdf_para(product_name, normal),
                    self._pdf_para(row["color"], normal),
                ])
                if show_color_total:
                    row_data.append(str(row["total_quantity"]))
                row_data.append(self._pdf_size_quantity_table(sizes, quantities, normal, pdf_font, pdf_font_size, widths[-1]))
                data.append(row_data)
            boundary_styles = [
                ("LINEABOVE", (0, row_index), (-1, row_index), 1.0, colors.black)
                for row_index in product_boundary_rows
            ]
            boundary_styles.extend([
                ("LEFTPADDING", (-1, 1), (-1, -1), 0),
                ("RIGHTPADDING", (-1, 1), (-1, -1), 0),
            ])
            story.append(self._pdf_table(data, widths, pdf_font, pdf_table_font_size, boundary_styles))
        else:
            story.append(Paragraph("集計済み転記データはありません。", normal))

        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("未確定・入力不備データ", heading))
        if unresolved:
            data = [["理由", "モール", "SKU", "数量", "商品名", "選択肢/候補", "元データ"]]
            for row in unresolved:
                data.append(
                    [
                        self._pdf_para(row["reason"], normal),
                        row["mall"],
                        self._pdf_para(row["sku"], normal),
                        row["quantity"],
                        self._pdf_para(row["product_name"], normal),
                        self._pdf_para(row["options"], normal),
                        self._pdf_para(row["source"], normal),
                    ]
                )
            story.append(self._pdf_table(data, [24 * mm, 18 * mm, 30 * mm, 10 * mm, 42 * mm, 48 * mm, 20 * mm], pdf_font, pdf_table_font_size))
        else:
            story.append(Paragraph("未確定・入力不備データはありません。", normal))

        doc.build(story, canvasmaker=self._pdf_page_number_canvasmaker(pdf_font, pdf_font_size))
        return pdf_path

    def export_temporary_order_pdf(self, output_dir: Path, files: list[tuple[Path, str]]) -> tuple[Path, int, int]:
        agg: dict[tuple[str, str, str], int] = defaultdict(int)
        unresolved: list[dict[str, str]] = []
        ok_count = 0
        seen_keys: set[tuple[str, str, str, str]] = set()
        for path, file_type in files:
            current_file_seen_keys: set[tuple[str, str, str, str]] = set()
            rows = read_csv_dicts(path)
            for source_row, row in enumerate(rows, start=2):
                raw_json = json.dumps(row, ensure_ascii=False)
                try:
                    if file_type == "mall_order":
                        order_id, mall, sku, sub_code, qty = self._normalize_mall_order(row)
                    elif file_type == "mercari_order":
                        order_id, mall, sku, sub_code, qty = self._normalize_mercari_order(row)
                    else:
                        raise ValueError(f"unknown file_type: {file_type}")
                    duplicate_key = (mall, order_id, sku, sub_code)
                    if order_id and duplicate_key in seen_keys and duplicate_key not in current_file_seen_keys:
                        continue
                    if order_id:
                        seen_keys.add(duplicate_key)
                        current_file_seen_keys.add(duplicate_key)
                except ValueError as exc:
                    if str(exc) == "SKIP_UNPAID_MERCARI":
                        continue
                    unresolved.append(
                        self.temporary_unresolved_row(
                            path.name,
                            source_row,
                            "",
                            "",
                            0,
                            str(exc),
                            raw_json,
                            [],
                        )
                    )
                    continue

                variants = self.conn.execute(
                    """
                    SELECT DISTINCT variant_code
                    FROM mall_skus
                    WHERE mall = ? AND sku = ? AND enabled = 1
                    """,
                    (mall, sku),
                ).fetchall()
                if len(variants) != 1:
                    resolution_rows = self.sku_resolution_rules(mall, sku)
                    if resolution_rows:
                        for rule in resolution_rows:
                            self.add_temp_single_variant_quantity(
                                agg,
                                rule["child_variant_code"],
                                qty * int(rule["quantity"]),
                                unresolved,
                                path.name,
                                source_row,
                                mall,
                                sku,
                                raw_json,
                            )
                    else:
                        reason = "SKU未登録" if len(variants) == 0 else "SKU重複"
                        unresolved.append(
                            self.temporary_unresolved_row(
                                path.name,
                                source_row,
                                mall,
                                sku,
                                qty,
                                reason,
                                raw_json,
                                self._sku_candidates(mall, sku),
                            )
                        )
                    continue
                self.add_temp_variant_quantity(agg, variants[0]["variant_code"], qty, unresolved, path.name, source_row, mall, sku, raw_json)
                ok_count += 1

        task_rows = self.create_temp_task_rows(agg)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = self._export_rows_pdf(
            output_dir,
            f"一時集計リスト_{stamp}",
            f"一時集計リスト {stamp}",
            task_rows,
            unresolved,
        )
        return pdf_path, len(task_rows), len(unresolved)

    def temporary_unresolved_row(
        self,
        file_name: str,
        source_row: int,
        mall: str,
        sku: str,
        quantity: int,
        reason: str,
        raw_json: str,
        candidates: list[dict[str, str]],
    ) -> dict[str, str]:
        raw = self._loads_json_object(raw_json)
        product_name = clean(raw.get("注文商品名")) or clean(raw.get("product_name"))
        options = clean(raw.get("商品備考"))
        if not options:
            color = clean(raw.get("バリエーション項目選択肢1")) or clean(raw.get("メルカリ項目1"))
            size = clean(raw.get("バリエーション項目選択肢2")) or clean(raw.get("メルカリ項目2"))
            options = " / ".join(part for part in [color, size] if part)
        if candidates:
            options = "候補: " + " / ".join(
                f"{clean(c.get('product_name'))} {clean(c.get('color'))} {clean(c.get('size'))}".strip()
                for c in candidates
            )
        qty = str(quantity or clean(raw.get("販売個数")) or clean(raw.get("quantity")) or "")
        return {
            "reason": clean(reason),
            "mall": clean(mall) or clean(raw.get("モール")) or "不明",
            "sku": clean(sku) or clean(raw.get("商品番号")) or clean(raw.get("original_product_id")),
            "quantity": qty,
            "product_name": product_name or "(商品名なし)",
            "options": options.replace("\r\n", " / ").replace("\n", " / "),
            "source": f"{file_name}:{source_row}",
        }

    def add_temp_variant_quantity(
        self,
        agg: dict[tuple[str, str, str], int],
        variant_code: str,
        qty: int,
        unresolved: list[dict[str, str]],
        file_name: str,
        source_row: int,
        mall: str,
        sku: str,
        raw_json: str,
    ) -> None:
        components = self.conn.execute(
            "SELECT child_variant_code, component_quantity FROM set_components WHERE parent_variant_code = ?",
            (variant_code,),
        ).fetchall()
        if components:
            for component in components:
                self.add_temp_single_variant_quantity(
                    agg,
                    component["child_variant_code"],
                    qty * int(component["component_quantity"]),
                    unresolved,
                    file_name,
                    source_row,
                    mall,
                    sku,
                    raw_json,
                )
        else:
            self.add_temp_single_variant_quantity(agg, variant_code, qty, unresolved, file_name, source_row, mall, sku, raw_json)

    def add_temp_single_variant_quantity(
        self,
        agg: dict[tuple[str, str, str], int],
        variant_code: str,
        qty: int,
        unresolved: list[dict[str, str]],
        file_name: str,
        source_row: int,
        mall: str,
        sku: str,
        raw_json: str,
    ) -> None:
        row = self.conn.execute(
            """
            SELECT v.product_code,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size
            FROM variants v
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.variant_code = ?
            """,
            (variant_code,),
        ).fetchone()
        if not row:
            unresolved.append(self.temporary_unresolved_row(file_name, source_row, mall, sku, qty, f"子SKU未登録: {variant_code}", raw_json, []))
            return
        agg[(row["product_code"], row["color"], row["size"])] += qty

    def create_temp_task_rows(self, agg: dict[tuple[str, str, str], int]) -> list[dict[str, object]]:
        grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        for (product_code, color, size), qty in agg.items():
            grouped[(product_code, color)][size] = grouped[(product_code, color)].get(size, 0) + qty
        task_rows: list[dict[str, object]] = []
        sort_order = 1
        for product_code in sorted({key[0] for key in grouped}):
            product = self.conn.execute(
                "SELECT display_name FROM products WHERE product_code = ?",
                (product_code,),
            ).fetchone()
            product_name = product["display_name"] if product else product_code
            quantity_multiplier = self.product_quantity_multiplier(product_code)
            if quantity_multiplier != 1:
                product_name = self._apply_quantity_marker(product_name, quantity_multiplier)
            colors = self.conn.execute(
                """
                SELECT COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                       MIN(COALESCE(vus.color_order, v.color_order)) AS color_order
                FROM variants v
                LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
                WHERE v.product_code = ?
                GROUP BY COALESCE(NULLIF(vus.color, ''), v.color)
                ORDER BY color_order, color
                """,
                (product_code,),
            ).fetchall()
            sizes = self.conn.execute(
                """
                SELECT COALESCE(NULLIF(vus.size, ''), v.size) AS size,
                       MIN(COALESCE(vus.size_order, v.size_order)) AS size_order
                FROM variants v
                LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
                WHERE v.product_code = ?
                GROUP BY COALESCE(NULLIF(vus.size, ''), v.size)
                ORDER BY size_order, size
                """,
                (product_code,),
            ).fetchall()
            size_names = [clean(row["size"]) for row in sizes]
            for color_row in colors:
                color = clean(color_row["color"])
                qmap = grouped.get((product_code, color), {})
                if not qmap:
                    continue
                quantities: list[str] = []
                total = 0
                for size in size_names:
                    qty = int(qmap.get(size, 0)) * quantity_multiplier
                    quantities.append("" if qty == 0 else str(qty))
                    total += qty
                if total == 0:
                    continue
                task_rows.append(
                    {
                        "id": sort_order,
                        "product_code": product_code,
                        "product_name": product_name,
                        "color": color,
                        "sizes_json": json.dumps(size_names, ensure_ascii=False),
                        "quantities_json": json.dumps(quantities, ensure_ascii=False),
                        "total_quantity": total,
                        "sort_order": sort_order,
                        "status": "pending",
                    }
                )
                sort_order += 1
        return task_rows

    def export_summary_pdf(self, output_dir: Path, ordered_task_ids: list[int] | None = None) -> Path:
        batch_id = self.active_batch_id()
        batch = self.conn.execute("SELECT batch_date FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        batch_date = batch["batch_date"] if batch else today_text()
        return self._export_rows_pdf(
            output_dir,
            f"出荷集計リスト_{batch_date}",
            f"出荷集計リスト {batch_date}",
            self.task_rows_for_pdf(ordered_task_ids),
            self.unresolved_rows_for_pdf(),
        )

    def pdf_row_is_copied(self, row: object) -> bool:
        try:
            status = clean(row["status"])
        except Exception:
            status = clean(getattr(row, "status", ""))
        return status in {"copied", "済"}

    def export_stock_alerts_pdf(self, output_dir: Path, rows: list[sqlite3.Row]) -> Path:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = output_dir / f"在庫アラート一覧_{stamp}.pdf"
        pdf_font = self.register_pdf_font(pdfmetrics, UnicodeCIDFont, TTFont)
        pdf_font_size = self.pdf_font_size()
        table_font_size = max(7, pdf_font_size - 1)
        styles = getSampleStyleSheet()
        normal = ParagraphStyle(
            "StockAlertNormal",
            parent=styles["Normal"],
            fontName=pdf_font,
            fontSize=pdf_font_size,
            leading=pdf_font_size + 2,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        title = ParagraphStyle(
            "StockAlertTitle",
            parent=normal,
            fontSize=pdf_font_size + 7,
            leading=pdf_font_size + 10,
            spaceAfter=6,
        )
        right = ParagraphStyle(
            "StockAlertRight",
            parent=normal,
            alignment=TA_RIGHT,
        )
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=16 * mm,
            bottomMargin=10 * mm,
        )
        output_time = datetime.now().strftime("%Y/%m/%d %H:%M")
        story = [
            Paragraph(f"在庫アラート一覧 {output_time}", title),
            Spacer(1, 3 * mm),
        ]
        data: list[list[object]] = [["商品名", "カラー", "サイズ", "残数"]]
        product_boundary_rows: list[int] = []
        previous_product = None
        for row in rows:
            product_name = clean(row["product_name"])
            if previous_product is not None and product_name != previous_product:
                product_boundary_rows.append(len(data))
            previous_product = product_name
            remaining = "" if row["remaining_quantity"] is None else str(row["remaining_quantity"])
            data.append(
                [
                    self._pdf_para(product_name, normal),
                    self._pdf_para(row["color"], normal),
                    self._pdf_para(row["size"], normal),
                    Paragraph(remaining, right),
                ]
            )
        if len(data) == 1:
            story.append(Paragraph("在庫アラートはありません。", normal))
        else:
            extra_styles = [
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ]
            extra_styles.extend(
                ("LINEABOVE", (0, row_index), (-1, row_index), 1.0, colors.black)
                for row_index in product_boundary_rows
            )
            story.append(
                self._pdf_table(
                    data,
                    [86 * mm, 38 * mm, 42 * mm, 20 * mm],
                    pdf_font,
                    table_font_size,
                    extra_styles,
                )
            )

        doc.build(story, canvasmaker=self._pdf_page_number_canvasmaker(pdf_font, pdf_font_size))
        return pdf_path

    def _pdf_page_number_canvasmaker(self, pdf_font: str, pdf_font_size: int):
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas as reportlab_canvas

        class NumberedCanvas(reportlab_canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total_pages = max(1, len(self._saved_page_states))
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self._draw_page_number(total_pages)
                    reportlab_canvas.Canvas.showPage(self)
                reportlab_canvas.Canvas.save(self)

            def _draw_page_number(self, total_pages: int) -> None:
                page_width, page_height = self._pagesize
                text = f"{self._pageNumber}/{total_pages}"
                self.saveState()
                if total_pages > 1:
                    font_size = max(10, int(pdf_font_size * 1.5))
                    padding_x = 2.5 * mm
                    padding_y = 1.5 * mm
                    text_width = pdfmetrics.stringWidth(text, pdf_font, font_size)
                    box_width = text_width + padding_x * 2
                    box_height = font_size + padding_y * 2
                    right = page_width - 10 * mm
                    top = page_height - 5 * mm
                    self.setFillColor(colors.black)
                    self.rect(right - box_width, top - box_height, box_width, box_height, stroke=0, fill=1)
                    self.setFillColor(colors.white)
                    self.setFont(pdf_font, font_size)
                    baseline = top - padding_y - font_size * 0.78
                    self.drawRightString(right - padding_x, baseline, text)
                    self.drawRightString(right - padding_x - 0.25, baseline, text)
                else:
                    self.setFillColor(colors.black)
                    self.setFont(pdf_font, max(7, pdf_font_size))
                    self.drawRightString(page_width - 10 * mm, page_height - 7 * mm, text)
                self.restoreState()

        return NumberedCanvas

    def pdf_font_options(self) -> dict[str, tuple[str, str]]:
        return {
            "HeiseiKakuGo-W5": ("cid", "HeiseiKakuGo-W5"),
            "HeiseiMin-W3": ("cid", "HeiseiMin-W3"),
            "メイリオ": ("ttf", r"C:\Windows\Fonts\meiryo.ttc"),
            "游ゴシック": ("ttf", r"C:\Windows\Fonts\YuGothM.ttc"),
            "游明朝": ("ttf", r"C:\Windows\Fonts\YuMincho-Regular.ttc"),
            "MS ゴシック": ("ttf", r"C:\Windows\Fonts\msgothic.ttc"),
            "MS 明朝": ("ttf", r"C:\Windows\Fonts\msmincho.ttc"),
            "BIZ UDPゴシック": ("ttf", r"C:\Windows\Fonts\BIZ-UDGothicR.ttc"),
        }

    def register_pdf_font(self, pdfmetrics, UnicodeCIDFont, TTFont) -> str:
        font_label = self.get_setting("pdf_font_name", "メイリオ")
        options = self.pdf_font_options()
        kind, value = options.get(font_label, options["HeiseiKakuGo-W5"])
        if kind == "cid":
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(value))
                return value
            except Exception:
                pass
        else:
            font_path = Path(value)
            font_name = "PDF_" + re.sub(r"[^A-Za-z0-9_]", "_", font_label)
            try:
                if font_path.exists():
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                    return font_name
            except Exception:
                pass
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        return "HeiseiKakuGo-W5"

    def pdf_font_name(self) -> str:
        font_name = self.get_setting("pdf_font_name", "メイリオ")
        return font_name if font_name in self.pdf_font_options() else "HeiseiKakuGo-W5"

    def pdf_font_size(self) -> int:
        try:
            size = int(float(clean(self.get_setting("pdf_font_size", "10"))))
        except ValueError:
            size = 10
        return min(14, max(6, size))

    def pdf_column_width_mm(self, key: str, default: float, minimum: float, maximum: float) -> float:
        try:
            value = float(clean(self.get_setting(key, str(default))))
        except ValueError:
            value = default
        return min(maximum, max(minimum, value))

    def _split_maker_product_name(self, product_name: object) -> tuple[str, str]:
        value = clean(product_name)
        if "／" not in value:
            return "", value
        maker, name = value.split("／", 1)
        return clean(maker), clean(name)

    def _pdf_para(self, text: object, style) -> object:
        from reportlab.platypus import Paragraph

        value = clean(text)
        if len(value) > 180:
            value = value[:177] + "..."
        escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(escaped, style)

    def _pdf_size_quantity_table(self, sizes: list[object], quantities: list[object], style, font_name: str, font_size: int, available_width: float) -> object:
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import Table, TableStyle

        row_count = max(len(sizes), len(quantities))
        data = []
        for index in range(row_count):
            size = sizes[index] if index < len(sizes) else ""
            qty = quantities[index] if index < len(quantities) else ""
            data.append([self._pdf_para(size, style), clean(qty) or "--"])
        if not data:
            data = [["", ""]]
        table_width = max(34 * mm, available_width)
        qty_width = min(12 * mm, table_width * 0.28)
        size_width = table_width - qty_width
        table = Table(data, colWidths=[size_width, qty_width], hAlign="LEFT")
        commands = [
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#E5E7EB")]),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]
        if len(data) > 1:
            commands.append(("LINEBELOW", (0, 0), (-1, -2), 0.35, colors.HexColor("#D1D5DB")))
        table.setStyle(
            TableStyle(commands)
        )
        return table

    def _pdf_table(
        self,
        data: list[list[object]],
        widths: list[float],
        font_name: str,
        font_size: int,
        extra_styles: list[tuple] | None = None,
    ) -> object:
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        table = Table(data, colWidths=widths, repeatRows=1)
        commands = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9CA3AF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if extra_styles:
            commands.extend(extra_styles)
        table.setStyle(
            TableStyle(commands)
        )
        return table


@dataclass
class TaskView:
    id: int
    product_code: str
    product_name: str
    color: str
    sizes: list[str]
    quantities: list[str]
    previous_quantities: list[str]
    total: int
    status: str
    aggregation_round: int = 1
    task_kind: str = "initial"
    retry_required: bool = False
    retry_reason: str = ""
    source_task_ids: list[int] | None = None


@dataclass
class WriteCandidate:
    row: int
    col: int
    start_row: int
    start_col: int
    values: list[list[object]]
    formulas: list[list[object]]
    island: tuple[int, int, int, int] | None = None


class TransferWindow:
    def __init__(
        self,
        root: Tk,
        db: AppDB,
        base_dir: Path,
        on_task_change=None,
        start_task_id: int | None = None,
        auto_skip_done: bool = True,
        task_ids: list[int] | None = None,
    ) -> None:
        self.root = root
        self.db = db
        self.base_dir = base_dir
        self.on_task_change = on_task_change
        self.auto_skip_done = auto_skip_done
        self.allowed_ids = set(task_ids) if task_ids is not None else None
        self.ordered_task_ids = list(task_ids) if task_ids is not None else None
        self.bulk_color_gap_var = BooleanVar(value=False)
        self.copy_title_var = StringVar()
        self.title_tabs_var = StringVar(value="0")
        self.color_gap_tabs_var = StringVar(value="0")
        self.tail_tabs_var = StringVar(value="0")
        self.append_date_var = BooleanVar(value=True)
        self.transfer_pattern_var = StringVar()
        self.transfer_pattern_preview_var = StringVar()
        self.title_date_add_only_var = BooleanVar(value=False)
        self.loading_copy_settings = False
        self.loaded_copy_settings_product = ""
        self.loaded_inventory_product = ""
        self.loaded_page_product = ""
        self.transfer_pages: list[sqlite3.Row] = []
        self.transfer_page_index = 0
        self.transfer_page_var = StringVar(value="")
        self.inventory_file_var = StringVar()
        self.inventory_sheet_var = StringVar()
        self.excel_start_col_var = StringVar(value="A")
        self.min_stock_quantity_var = StringVar(value="3")
        self.loading_min_stock_quantity = False
        self.auto_write_confirmed_var = BooleanVar(value=False)
        saved_copy_mode = self.db.get_setting("transfer_copy_mode", "color")
        self.copy_mode = saved_copy_mode if saved_copy_mode in {"color", "all"} else "color"
        self.copy_mode_var = StringVar(value=self.copy_mode_button_text())
        saved_grid_wrap = self.db.get_setting("transfer_quantity_grid_wrap", "0")
        self.quantity_grid_wrap = saved_grid_wrap == "1"
        self.quantity_grid_wrap_var = StringVar(value=self.quantity_grid_wrap_button_text())
        self.quantity_grid_font_size = self.clamped_quantity_grid_font_size(
            self.db.get_setting("transfer_quantity_grid_font_size", "11")
        )
        self.quantity_grid_font_var = StringVar(value=f"{self.quantity_grid_font_size}pt")
        self.grid_reflow_after_id = None
        self.pending_excel_product_code = ""
        self.pending_excel_page_id = 0
        self.manual_notice_product_code = ""
        self.completed_transfer_pages: set[tuple[str, int]] = set()
        self.transfer_finished = False
        self.end_notice_shown = False
        self.candidate_highlight = None
        self.excel_transfer_button_var = StringVar()
        self.auto_write_button = None
        self.window = Toplevel(root)
        self.window.title("転記画面")
        self.window.geometry("1080x650")
        task_rows = list(db.task_rows())
        if self.ordered_task_ids is None:
            ordered_rows = task_rows
        else:
            row_by_id = {int(row["id"]): row for row in task_rows}
            ordered_rows = [row_by_id[task_id] for task_id in self.ordered_task_ids if task_id in row_by_id]
        self.tasks = [self._row_to_task(row) for row in ordered_rows]
        self.index = self._index_for_task(start_task_id)

        self.title_var = StringVar()
        self.target_var = StringVar()
        self.progress_var = StringVar()

        info_group = ttk.LabelFrame(self.window, text="転記対象")
        info_group.pack(fill=X, padx=12, pady=(12, 8))
        Label(info_group, textvariable=self.title_var, font=("", 14), bg="#FFFFFF", anchor=W).pack(fill=X, padx=8, pady=(6, 2))
        Label(info_group, textvariable=self.target_var, font=("", 11), bg="#FFFFFF", anchor=W).pack(fill=X, padx=8, pady=2)
        self.progress_label = Label(info_group, textvariable=self.progress_var, fg="#555555", bg="#FFFFFF", anchor=W)
        self.progress_label.pack(fill=X, padx=8, pady=(2, 6))

        file_group = ttk.LabelFrame(self.window, text="転記先ファイル")
        file_group.pack(fill=X, padx=12, pady=(0, 8))
        file_row1 = Frame(file_group)
        file_row1.pack(fill=X, padx=8, pady=(8, 3))
        file_row2 = Frame(file_group)
        file_row2.pack(fill=X, padx=8, pady=(0, 8))
        Label(file_row1, text="ファイル", width=8, anchor=W).pack(side=LEFT)
        Entry(file_row1, textvariable=self.inventory_file_var, width=78).pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        Button(file_row1, text="参照", command=self.browse_inventory_file, width=8).pack(side=LEFT, padx=4)
        Button(file_row1, text="開く", command=self.open_inventory_file, width=8).pack(side=LEFT, padx=(4, 0))
        Label(file_row2, text="シート名", width=8, anchor=W).pack(side=LEFT)
        Entry(file_row2, textvariable=self.inventory_sheet_var, width=32).pack(side=LEFT, padx=(0, 8))
        Label(file_row2, text="開始列").pack(side=LEFT, padx=(0, 4))
        Entry(file_row2, textvariable=self.excel_start_col_var, width=5).pack(side=LEFT, padx=(0, 8))
        Label(file_row2, textvariable=self.transfer_page_var, fg="#374151").pack(side=LEFT, padx=(0, 8))
        Label(file_row2, text="最低在庫").pack(side=LEFT, padx=(0, 4))
        min_stock_entry = Entry(file_row2, textvariable=self.min_stock_quantity_var, width=5, justify=RIGHT)
        min_stock_entry.pack(side=LEFT, padx=(0, 8))
        min_stock_entry.bind("<FocusOut>", lambda _event: self.save_current_min_stock_quantity())
        min_stock_entry.bind("<Return>", lambda _event: self.save_current_min_stock_quantity())
        self.auto_write_button = Button(file_row2, text="自動OK 未確認", command=self.toggle_auto_write_confirmed, width=14)
        self.auto_write_button.pack(side=RIGHT, padx=(8, 0))

        grid_group = ttk.LabelFrame(self.window, text="コピーされる数量行")
        grid_group.pack(fill=BOTH, expand=True, padx=12, pady=(0, 8))
        grid_control_row = Frame(grid_group)
        grid_control_row.pack(fill=X, padx=8, pady=(6, 0))
        Button(grid_control_row, textvariable=self.quantity_grid_wrap_var, command=self.toggle_quantity_grid_wrap, width=12).pack(side=LEFT, padx=(0, 6))
        Button(grid_control_row, text="A-", command=lambda: self.change_quantity_grid_font_size(-1), width=4).pack(side=LEFT, padx=(0, 4))
        Button(grid_control_row, text="A+", command=lambda: self.change_quantity_grid_font_size(1), width=4).pack(side=LEFT, padx=(0, 6))
        Label(grid_control_row, textvariable=self.quantity_grid_font_var, fg="#555555").pack(side=LEFT)
        self.grid_canvas = Canvas(grid_group, height=110, highlightthickness=0)
        self.grid_scrollbar = Scrollbar(grid_group, orient=HORIZONTAL, command=self.grid_canvas.xview)
        self.grid_y_scrollbar = Scrollbar(grid_group, orient="vertical", command=self.grid_canvas.yview)
        self.grid_canvas.configure(xscrollcommand=self.grid_scrollbar.set, yscrollcommand=self.grid_y_scrollbar.set)
        self.grid_canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=(8, 0), pady=(8, 0))
        self.grid_scrollbar.pack(fill=X, padx=8, pady=(0, 8))
        self.grid_frame = Frame(self.grid_canvas)
        self.grid_window_id = self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self.update_grid_scrollregion)
        self.grid_canvas.bind("<Configure>", self.on_grid_canvas_configure)
        self.apply_quantity_grid_display_mode()

        format_group = ttk.LabelFrame(self.window, text="Excel転記ルール")
        format_group.pack(fill=X, padx=12, pady=(0, 8))
        format_row1 = Frame(format_group)
        format_row1.pack(fill=X, padx=8, pady=(8, 3))
        Label(format_row1, text="タイトル").pack(side=LEFT, padx=(0, 4))
        Entry(format_row1, textvariable=self.copy_title_var, width=18).pack(side=LEFT, padx=(0, 8))
        Label(format_row1, text="転記パターン").pack(side=LEFT, padx=(0, 4))
        self.transfer_pattern_entry = Entry(format_row1, textvariable=self.transfer_pattern_var, width=70)
        self.transfer_pattern_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        Button(format_row1, text="t,", command=lambda: self.insert_transfer_pattern_text("t,"), width=5).pack(side=LEFT, padx=(0, 4))
        Button(format_row1, text="確認", command=self.update_transfer_pattern_preview, width=8).pack(side=LEFT)
        Label(format_group, textvariable=self.transfer_pattern_preview_var, anchor=W, fg="#374151", wraplength=1000).pack(fill=X, padx=8, pady=(0, 8))

        manual_group = ttk.LabelFrame(self.window, text="手動コピー")
        if self.db.get_setting("transfer_show_manual_copy", "0") == "1":
            manual_group.pack(fill=X, padx=12, pady=(0, 8))
        Button(manual_group, textvariable=self.copy_mode_var, command=self.toggle_copy_mode, width=12).pack(side=RIGHT, padx=(6, 8), pady=8)
        Button(manual_group, text="コピーして次へ", command=self.copy_by_mode_and_next, width=16, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=RIGHT, padx=6, pady=8)
        Button(manual_group, text="日時コピー", command=self.copy_today, width=10).pack(side=RIGHT, padx=6, pady=8)

        action_group = ttk.LabelFrame(self.window, text="操作")
        action_group.pack(fill=X, padx=12, pady=(0, 12))
        Button(action_group, text="Excelを開く", command=lambda: self.open_inventory_file(move_to_candidate=True), width=10, bg="#FEF3C7", activebackground="#FDE68A").pack(side=LEFT, padx=(8, 6), pady=8)
        Button(action_group, textvariable=self.excel_transfer_button_var, command=self.write_excel_and_next, width=24, bg="#DBEAFE", activebackground="#BFDBFE").pack(side=LEFT, padx=6, pady=8)
        Button(action_group, text="閉じる", command=self.close_transfer_window, width=10).pack(side=RIGHT, padx=8, pady=8)
        self.window.protocol("WM_DELETE_WINDOW", self.close_transfer_window)
        Button(action_group, text="記入欄増設", command=self.extend_inventory_island, width=10, bg="#E0F2FE", activebackground="#BAE6FD").pack(side=RIGHT, padx=6, pady=8)
        Button(action_group, text="商品設定", command=self.open_current_product_settings, width=10).pack(side=RIGHT, padx=6, pady=8)
        Button(action_group, text="前へ", command=self.browse_prev_task, width=8).pack(side=RIGHT, padx=6, pady=8)
        Button(action_group, text="次へ", command=self.browse_next_task, width=8).pack(side=RIGHT, padx=6, pady=8)
        Button(action_group, text="スキップ", command=self.skip_task, width=10).pack(side=RIGHT, padx=6, pady=8)
        self.update_excel_transfer_button()
        self.setup_copy_setting_autosave()
        self._skip_done_forward()
        self.render()

    def _row_to_task(self, row: sqlite3.Row) -> TaskView:
        return TaskView(
            id=int(row["id"]),
            product_code=row["product_code"],
            product_name=row["product_name"],
            color=row["color"],
            sizes=json.loads(row["sizes_json"]),
            quantities=json.loads(row["quantities_json"]),
            previous_quantities=json.loads(row["previous_quantities_json"] or "[]"),
            total=int(row["total_quantity"]),
            status=row["status"],
            aggregation_round=int(row["aggregation_round"] if "aggregation_round" in row.keys() else 1),
            task_kind=clean(row["task_kind"] if "task_kind" in row.keys() else "initial") or "initial",
            retry_required=bool(int(row["retry_required"] if "retry_required" in row.keys() else 0)),
            retry_reason=clean(row["retry_reason"] if "retry_reason" in row.keys() else ""),
            source_task_ids=[int(row["id"])],
        )

    def source_task_ids_for_items(self, items: list[TaskView]) -> list[int]:
        ids: list[int] = []
        seen: set[int] = set()
        for item in items:
            for task_id in item.source_task_ids or ([item.id] if item.id > 0 else []):
                if task_id > 0 and task_id not in seen:
                    ids.append(task_id)
                    seen.add(task_id)
        return ids

    def update_local_task_state(
        self,
        task_ids: list[int],
        status: str,
        retry_required: bool = False,
        retry_reason: str = "",
    ) -> None:
        target_ids = set(task_ids)
        if not target_ids:
            return
        for item in self.tasks:
            if item.id in target_ids:
                item.status = status
                item.retry_required = retry_required
                item.retry_reason = retry_reason

    def display_tasks_for_product(self, task: TaskView) -> list[TaskView]:
        sold_tasks: dict[str, TaskView] = {}
        for item in self.tasks:
            if item.product_code != task.product_code:
                continue
            existing = sold_tasks.get(item.color)
            if existing is None:
                sold_tasks[item.color] = item
                continue
            size_order = list(existing.sizes)
            for size in item.sizes:
                if size not in size_order:
                    size_order.append(size)
            current_by_size = defaultdict(int)
            previous_by_size = defaultdict(int)
            source_ids = list(existing.source_task_ids or [])
            source_ids.extend(item.source_task_ids or [])
            for source in (existing, item):
                for size, qty in zip(source.sizes, source.quantities):
                    current_by_size[size] += self.safe_int(qty, 0)
                for size, qty in zip(source.sizes, source.previous_quantities):
                    previous_by_size[size] = max(previous_by_size[size], self.safe_int(qty, 0))
            quantities = ["" if current_by_size[size] == 0 else str(current_by_size[size]) for size in size_order]
            previous_quantities = ["" if previous_by_size[size] == 0 else str(previous_by_size[size]) for size in size_order]
            existing.sizes = size_order
            existing.quantities = quantities
            existing.previous_quantities = previous_quantities
            existing.total = sum(current_by_size.values())
            existing.source_task_ids = source_ids
        variants = self.db.variant_grid_for_product(task.product_code)
        if not variants:
            return [item for item in self.tasks if item.product_code == task.product_code]

        grouped: dict[str, list[str]] = {}
        for row in variants:
            color = clean(row["color"])
            grouped.setdefault(color, []).append(clean(row["size"]))

        display_tasks: list[TaskView] = []
        for color, sizes in grouped.items():
            sold = sold_tasks.get(color)
            qty_by_size = {}
            if sold:
                qty_by_size = {size: qty for size, qty in zip(sold.sizes, sold.quantities)}
            display_tasks.append(
                TaskView(
                    id=sold.id if sold else -1,
                    product_code=task.product_code,
                    product_name=task.product_name,
                    color=color,
                    sizes=sizes,
                    quantities=[qty_by_size.get(size, "") for size in sizes],
                    previous_quantities=sold.previous_quantities if sold else [],
                    total=sold.total if sold else 0,
                    status=sold.status if sold else "no_sales",
                    aggregation_round=sold.aggregation_round if sold else 1,
                    task_kind=sold.task_kind if sold else "initial",
                    source_task_ids=sold.source_task_ids if sold else [],
                )
            )
        return display_tasks

    def _first_pending_index(self) -> int:
        for i, task in enumerate(self.tasks):
            if task.status == "pending":
                return i
        return 0

    def _index_for_task(self, task_id: int | None) -> int:
        if task_id is not None:
            for i, task in enumerate(self.tasks):
                if task.id == task_id:
                    return i
        return self._first_pending_index()

    def current_task(self) -> TaskView | None:
        if not self.tasks:
            return None
        self.index = max(0, min(self.index, len(self.tasks) - 1))
        return self.tasks[self.index]

    def is_manual_input_task(self, task: TaskView | None = None) -> bool:
        task = task or self.current_task()
        return bool(task and self.db.product_manual_input(task.product_code))

    def update_grid_scrollregion(self, event=None) -> None:
        if hasattr(self, "grid_canvas"):
            self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))

    def set_progress_text(self, text: str, alert: bool = False) -> None:
        self.progress_var.set(text)
        if hasattr(self, "progress_label"):
            self.progress_label.configure(fg="#DC2626" if alert else "#555555")

    def update_grid_canvas_height(self, event=None) -> None:
        if hasattr(self, "grid_canvas") and hasattr(self, "grid_window_id"):
            if getattr(self, "quantity_grid_wrap", False):
                self.grid_canvas.itemconfigure(self.grid_window_id, height=0)
            else:
                self.grid_canvas.itemconfigure(self.grid_window_id, height=max(100, self.grid_canvas.winfo_height()))

    def on_grid_canvas_configure(self, event=None) -> None:
        self.update_grid_canvas_height(event)
        self.apply_quantity_grid_display_mode()
        if getattr(self, "quantity_grid_wrap", False):
            if getattr(self, "grid_reflow_after_id", None):
                self.window.after_cancel(self.grid_reflow_after_id)
            self.grid_reflow_after_id = self.window.after(120, self.render)

    def clamped_quantity_grid_font_size(self, value: object) -> int:
        try:
            size = int(float(clean(value) or "11"))
        except ValueError:
            size = 11
        return min(18, max(8, size))

    def quantity_grid_wrap_button_text(self) -> str:
        return "表示: 折返" if self.quantity_grid_wrap else "表示: 一行"

    def apply_quantity_grid_display_mode(self) -> None:
        if not hasattr(self, "grid_canvas") or not hasattr(self, "grid_scrollbar"):
            return
        if self.quantity_grid_wrap:
            self.grid_scrollbar.pack_forget()
            if not self.grid_y_scrollbar.winfo_ismapped():
                self.grid_y_scrollbar.pack(side=RIGHT, fill=Y, padx=(0, 8), pady=(8, 0))
            self.grid_canvas.configure(xscrollcommand="", yscrollcommand=self.grid_y_scrollbar.set)
            width = max(100, self.grid_canvas.winfo_width())
            self.grid_canvas.itemconfigure(self.grid_window_id, width=width)
            self.grid_canvas.xview_moveto(0)
        else:
            self.grid_y_scrollbar.pack_forget()
            self.grid_canvas.itemconfigure(self.grid_window_id, width=0)
            self.grid_canvas.configure(xscrollcommand=self.grid_scrollbar.set, yscrollcommand="")
            self.grid_canvas.yview_moveto(0)
            if not self.grid_scrollbar.winfo_ismapped():
                self.grid_scrollbar.pack(fill=X, padx=8, pady=(0, 8))

    def toggle_quantity_grid_wrap(self) -> None:
        self.quantity_grid_wrap = not self.quantity_grid_wrap
        self.db.set_setting("transfer_quantity_grid_wrap", "1" if self.quantity_grid_wrap else "0")
        self.quantity_grid_wrap_var.set(self.quantity_grid_wrap_button_text())
        self.apply_quantity_grid_display_mode()
        self.render()

    def change_quantity_grid_font_size(self, delta: int) -> None:
        self.quantity_grid_font_size = self.clamped_quantity_grid_font_size(self.quantity_grid_font_size + delta)
        self.db.set_setting("transfer_quantity_grid_font_size", str(self.quantity_grid_font_size))
        self.quantity_grid_font_var.set(f"{self.quantity_grid_font_size}pt")
        self.render()

    def quantity_grid_columns_per_line(self) -> int:
        canvas_width = self.grid_canvas.winfo_width() if hasattr(self, "grid_canvas") else 0
        font_size = max(8, getattr(self, "quantity_grid_font_size", 11))
        cell_px = max(78, font_size * 8)
        available = max(120, canvas_width - 100)
        return max(1, int(available // cell_px))

    def render(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        if self.transfer_finished:
            self.title_var.set("転記リスト完了")
            self.target_var.set("表示中のリストは最後まで処理しました")
            self.set_progress_text(f"{len(self.tasks)} / {len(self.tasks)}    状態: 完了")
            self.excel_transfer_button_var.set("完了")
            Label(
                self.grid_frame,
                text="転記対象リストの終端です。\n在庫アラートなどを確認し、作業が終わったら閉じるを押してください。",
                bg="#FFFFFF",
                fg="#374151",
                justify=LEFT,
                padx=16,
                pady=16,
            ).grid(row=0, column=0, sticky="nsew")
            self.grid_frame.update_idletasks()
            self.update_grid_scrollregion()
            return
        task = self.current_task()
        if not task:
            self.title_var.set("転記タスクがありません")
            self.target_var.set("")
            self.set_progress_text("")
            return
        self.title_var.set(f"商品名: {task.product_name}")
        self.target_var.set(f"対象カラー: {task.color} / 合計 {task.total}")
        self.load_transfer_page_for_task(task)
        progress = f"{self.index + 1} / {len(self.tasks)}    状態: {task.status}"
        page_progress = self.transfer_page_progress_text()
        if page_progress:
            progress += f"    {page_progress}"
        if self.is_manual_input_task(task):
            progress += "    手動入力対象"
        self.set_progress_text(progress)
        self.load_auto_write_confirmed_for_task(task)
        self.load_min_stock_quantity_for_task(task)
        self.update_excel_transfer_button()
        if self.is_manual_input_task(task) and self.manual_notice_product_code != task.product_code:
            self.manual_notice_product_code = task.product_code
            self.window.after(100, lambda: messagebox.showinfo(
                "手動入力対象",
                "この商品は手動入力対象です。\nExcelを開いて手入力し、完了後に「手入力完了して次へ」を押してください。",
                parent=self.window,
            ))
        if self.on_task_change:
            self.on_task_change(task.id)

        product_tasks = self.display_tasks_for_product(task)
        header_bg = "#F9FAFB"
        line_color = "#E5E7EB"
        highlight_bg = "#DCFCE7"
        highlight_qty_bg = "#BBF7D0"
        label_font = ("", self.quantity_grid_font_size)
        qty_font = ("", self.quantity_grid_font_size, "bold")
        cells: list[tuple[str, str, str, bool]] = []
        for color_task in product_tasks:
            is_target = self.copy_mode == "all" or color_task.id == task.id
            for size, qty in zip(color_task.sizes, color_task.quantities):
                cells.append((color_task.color, size, qty, is_target))
        columns_per_line = self.quantity_grid_columns_per_line() if self.quantity_grid_wrap else max(1, len(cells))
        for start in range(0, len(cells), columns_per_line):
            line_index = start // columns_per_line
            base_row = line_index * 3
            bottom_pad = 8 if self.quantity_grid_wrap and start + columns_per_line < len(cells) else 0
            Label(self.grid_frame, text="カラー", width=10, relief="solid", bd=1, highlightbackground=line_color, bg=header_bg, font=label_font).grid(row=base_row, column=0, sticky="nsew")
            Label(self.grid_frame, text="サイズ", width=10, relief="solid", bd=1, highlightbackground=line_color, bg=header_bg, font=label_font).grid(row=base_row + 1, column=0, sticky="nsew")
            Label(self.grid_frame, text="数量", width=10, relief="solid", bd=1, highlightbackground=line_color, bg=header_bg, font=label_font).grid(row=base_row + 2, column=0, sticky="nsew", pady=(0, bottom_pad))
            for col, (color, size, qty, is_target) in enumerate(cells[start:start + columns_per_line], start=1):
                cell_bg = highlight_bg if is_target else "#FFFFFF"
                qty_bg = highlight_qty_bg if is_target else "#FFFFFF"
                Label(self.grid_frame, text=color, width=12, relief="solid", bd=1, bg=cell_bg, font=label_font).grid(row=base_row, column=col, sticky="nsew")
                Label(self.grid_frame, text=size, width=12, relief="solid", bd=1, bg=cell_bg, anchor=W, font=label_font).grid(row=base_row + 1, column=col, sticky="nsew")
                Label(self.grid_frame, text=qty, width=12, relief="solid", bd=1, bg=qty_bg, font=qty_font).grid(row=base_row + 2, column=col, sticky="nsew", pady=(0, bottom_pad))
        self.grid_frame.update_idletasks()
        self.apply_quantity_grid_display_mode()
        self.update_grid_scrollregion()

    def current_transfer_page(self) -> sqlite3.Row | None:
        if not self.transfer_pages:
            return None
        self.transfer_page_index = max(0, min(self.transfer_page_index, len(self.transfer_pages) - 1))
        return self.transfer_pages[self.transfer_page_index]

    def has_multiple_transfer_pages(self) -> bool:
        return len(self.transfer_pages) > 1

    def transfer_page_target_label(self) -> str:
        if self.has_multiple_transfer_pages() and self.transfer_page_index < len(self.transfer_pages) - 1:
            return "次ページへ"
        return "次商品へ"

    def transfer_page_progress_text(self) -> str:
        if not self.has_multiple_transfer_pages():
            return ""
        page = self.current_transfer_page()
        page_name = clean(page["page_name"] if page else "")
        suffix = f": {page_name}" if page_name else ""
        return f"複数設定 {self.transfer_page_index + 1}/{len(self.transfer_pages)}{suffix}"

    def mark_current_transfer_page_completed(self, task: TaskView) -> None:
        page = self.current_transfer_page()
        page_id = int(page["id"]) if page else 0
        if page_id:
            self.completed_transfer_pages.add((task.product_code, page_id))

    def has_completed_transfer_page(self, product_code: str) -> bool:
        return any(code == product_code for code, _page_id in self.completed_transfer_pages)

    def load_transfer_page_for_task(self, task: TaskView) -> None:
        if self.loaded_page_product != task.product_code:
            self.transfer_pages = self.db.product_transfer_pages(task.product_code)
            self.transfer_page_index = 0
            self.loaded_page_product = task.product_code
            self.loaded_copy_settings_product = ""
            self.loaded_inventory_product = ""
        page = self.current_transfer_page()
        if not page:
            return
        self.loading_copy_settings = True
        try:
            self.copy_title_var.set(str(page["copy_title"]))
            self.title_tabs_var.set(str(page["title_tabs"]))
            self.color_gap_tabs_var.set(str(page["color_gap_tabs"]))
            self.tail_tabs_var.set(str(page["tail_tabs"]))
            self.append_date_var.set(bool(page["append_date"]))
            self.transfer_pattern_var.set(str(page["transfer_pattern"]))
            self.inventory_file_var.set(str(page["inventory_file_path"]))
            self.inventory_sheet_var.set(str(page["inventory_sheet_name"]))
            self.excel_start_col_var.set(str(page["excel_start_col"] or "A"))
            self.title_date_add_only_var.set(bool(page["title_date_add_only"] if "title_date_add_only" in page.keys() else 0))
            self.transfer_page_var.set(f"ページ {self.transfer_page_index + 1}/{len(self.transfer_pages)}: {page['page_name']}")
        finally:
            self.loading_copy_settings = False
        self.update_transfer_pattern_preview()

    def load_copy_settings_for_task(self, task: TaskView) -> None:
        self.load_transfer_page_for_task(task)

    def setup_copy_setting_autosave(self) -> None:
        for variable in [
            self.copy_title_var,
            self.title_tabs_var,
            self.color_gap_tabs_var,
            self.tail_tabs_var,
            self.append_date_var,
            self.transfer_pattern_var,
        ]:
            variable.trace_add("write", self.auto_save_copy_settings)

    def auto_save_copy_settings(self, *_args) -> None:
        if self.loading_copy_settings:
            return
        task = self.current_task()
        if not task:
            return
        self.save_current_transfer_page(task)
        self.update_transfer_pattern_preview()

    def load_inventory_file_for_task(self, task: TaskView) -> None:
        self.load_transfer_page_for_task(task)

    def save_current_transfer_page(self, task: TaskView | None = None) -> None:
        task = task or self.current_task()
        page = self.current_transfer_page()
        if not task or not page:
            return
        page_id = int(page["id"])
        self.db.save_product_transfer_page(
            task.product_code,
            page_id,
            str(page["page_name"]),
            int(page["page_order"]),
            self.inventory_file_var.get(),
            self.inventory_sheet_var.get(),
            self.excel_start_col_var.get(),
            self.copy_title_var.get().strip(),
            self.parse_tab_count(self.title_tabs_var.get()),
            self.parse_tab_count(self.color_gap_tabs_var.get()),
            self.parse_tab_count(self.tail_tabs_var.get()),
            self.append_date_var.get(),
            self.transfer_pattern_var.get().strip(),
            int(page["quantity_multiplier"] or 1),
            self.auto_write_confirmed_var.get(),
            False,
        )
        self.transfer_pages = self.db.product_transfer_pages(task.product_code)

    def load_auto_write_confirmed_for_task(self, task: TaskView) -> None:
        confirmed = self.db.product_auto_write_confirmed(task.product_code)
        self.auto_write_confirmed_var.set(confirmed)
        self.update_auto_write_button()

    def load_min_stock_quantity_for_task(self, task: TaskView) -> None:
        self.loading_min_stock_quantity = True
        try:
            self.min_stock_quantity_var.set(str(self.db.product_min_stock_quantity(task.product_code)))
        finally:
            self.loading_min_stock_quantity = False

    def save_current_min_stock_quantity(self) -> bool:
        if self.loading_min_stock_quantity:
            return True
        task = self.current_task()
        if not task:
            return True
        try:
            min_stock = int(float(clean(self.min_stock_quantity_var.get()) or "0"))
        except ValueError:
            min_stock = self.db.product_min_stock_quantity(task.product_code)
            self.min_stock_quantity_var.set(str(min_stock))
            messagebox.showerror("入力エラー", "最低在庫数は数値で入力してください。", parent=self.window)
            self.bring_to_front()
            return False
        self.db.set_product_min_stock_quantity(task.product_code, min_stock)
        self.min_stock_quantity_var.set(str(min_stock))
        return True

    def toggle_auto_write_confirmed(self) -> None:
        task = self.current_task()
        if not task:
            return
        confirmed = not self.auto_write_confirmed_var.get()
        self.auto_write_confirmed_var.set(confirmed)
        self.db.set_product_auto_write_confirmed(task.product_code, confirmed)
        self.save_current_transfer_page(task)
        self.update_auto_write_button()
        label = "自動書き込み確認済み" if confirmed else "自動書き込み未確認"
        self.progress_var.set(f"{self.index + 1} / {len(self.tasks)}    状態: {label}")

    def update_auto_write_button(self) -> None:
        if not self.auto_write_button:
            return
        if self.auto_write_confirmed_var.get():
            self.auto_write_button.configure(text="自動OK 確認済", bg="#BBF7D0", activebackground="#86EFAC")
        else:
            self.auto_write_button.configure(text="自動OK 未確認", bg="#FED7AA", activebackground="#FDBA74")

    def copy_and_next(self) -> None:
        if self.transfer_finished:
            messagebox.showinfo("転記リスト完了", "表示中のリストは最後まで処理済みです。", parent=self.window)
            self.bring_to_front()
            return
        task = self.current_task()
        if not task:
            return
        copy_text = "\t".join(task.quantities)
        self.window.clipboard_clear()
        self.window.clipboard_append(copy_text)
        source_task_ids = self.source_task_ids_for_items([task])
        for task_id in source_task_ids:
            if task_id > 0:
                self.db.mark_task(task_id, "copied")
        self.update_local_task_state(source_task_ids, "copied")
        task.status = "copied"
        task.retry_required = False
        task.retry_reason = ""
        self.next_task()

    def copy_mode_button_text(self) -> str:
        return "カラーごと" if self.copy_mode == "all" else "全体"

    def toggle_copy_mode(self) -> None:
        if self.copy_mode == "color":
            self.copy_mode = "all"
        else:
            self.copy_mode = "color"
        self.db.set_setting("transfer_copy_mode", self.copy_mode)
        self.copy_mode_var.set(self.copy_mode_button_text())
        self.render()

    def next_transfer_page(self) -> None:
        task = self.current_task()
        if not task or self.transfer_page_index >= len(self.transfer_pages) - 1:
            return
        self.save_current_transfer_page(task)
        self.transfer_page_index += 1
        self.load_transfer_page_for_task(task)
        self.render()

    def prev_transfer_page(self) -> None:
        task = self.current_task()
        if not task or self.transfer_page_index <= 0:
            return
        self.save_current_transfer_page(task)
        self.transfer_page_index -= 1
        self.load_transfer_page_for_task(task)
        self.render()

    def copy_by_mode_and_next(self) -> None:
        if self.copy_mode == "all":
            self.copy_product_and_next()
        else:
            self.copy_and_next()

    def copy_product_and_next(self) -> None:
        if self.transfer_finished:
            messagebox.showinfo("転記リスト完了", "表示中のリストは最後まで処理済みです。", parent=self.window)
            self.bring_to_front()
            return
        task = self.current_task()
        if not task:
            return
        product_tasks = self.display_tasks_for_product(task)
        values: list[str] = []
        for item in product_tasks:
            values.extend(item.quantities)
        copy_text = "\t".join(values)
        self.window.clipboard_clear()
        self.window.clipboard_append(copy_text)
        source_task_ids = self.source_task_ids_for_items(product_tasks)
        for item in product_tasks:
            for task_id in item.source_task_ids or ([item.id] if item.id > 0 else []):
                if task_id > 0:
                    self.db.mark_task(task_id, "copied")
            item.status = "copied"
            item.retry_required = False
            item.retry_reason = ""
        self.update_local_task_state(source_task_ids, "copied")
        self._move_to_next_product(task.product_code)

    def build_product_transfer_values(self, product_tasks: list[TaskView], product_code: str) -> list[str]:
        return self.build_product_transfer_values_for_quantities(
            product_tasks,
            product_code,
            self.flatten_product_quantities(product_tasks, "current"),
            save_settings=True,
        )

    def build_previous_product_transfer_values(self, product_tasks: list[TaskView], product_code: str) -> list[str]:
        return self.build_product_transfer_values_for_quantities(
            product_tasks,
            product_code,
            self.flatten_product_quantities(product_tasks, "previous"),
            save_settings=False,
        )

    def build_product_transfer_values_for_quantities(
        self,
        product_tasks: list[TaskView],
        product_code: str,
        quantity_values: list[str],
        save_settings: bool = False,
    ) -> list[str]:
        quantity_values = self.apply_current_page_quantity_multiplier(quantity_values)
        title = self.copy_title_var.get().strip()
        title_tabs = self.parse_tab_count(self.title_tabs_var.get())
        color_gap_tabs = self.parse_tab_count(self.color_gap_tabs_var.get())
        tail_tabs = self.parse_tab_count(self.tail_tabs_var.get())
        transfer_pattern = self.transfer_pattern_var.get().strip()
        if save_settings:
            self.db.save_product_copy_settings(
                product_code,
                title,
                title_tabs,
                color_gap_tabs,
                tail_tabs,
                self.append_date_var.get(),
                transfer_pattern,
            )
        if transfer_pattern:
            return self.values_from_transfer_pattern(transfer_pattern, quantity_values, title)
        values: list[str] = [title] if title else []
        values.extend([""] * title_tabs)
        quantity_index = 0
        for index, item in enumerate(product_tasks):
            count = len(item.quantities)
            values.extend(quantity_values[quantity_index : quantity_index + count])
            quantity_index += count
            if index < len(product_tasks) - 1:
                values.extend([""] * color_gap_tabs)
        values.extend([""] * tail_tabs)
        if self.append_date_var.get():
            values.append(self.db.transfer_date_text())
        return values

    def current_page_quantity_multiplier(self) -> int:
        page = self.current_transfer_page()
        try:
            return max(1, int(float(clean(page["quantity_multiplier"] if page else 1) or "1")))
        except (TypeError, ValueError):
            return 1

    def apply_current_page_quantity_multiplier(self, values: list[str]) -> list[str]:
        multiplier = self.current_page_quantity_multiplier()
        if multiplier == 1:
            return list(values)
        multiplied: list[str] = []
        for value in values:
            text = clean(value)
            if not text:
                multiplied.append("")
                continue
            try:
                qty = int(float(text))
            except ValueError:
                multiplied.append(text)
                continue
            multiplied.append("" if qty == 0 else str(qty * multiplier))
        return multiplied

    def flatten_product_quantities(self, product_tasks: list[TaskView], mode: str = "current") -> list[str]:
        values: list[str] = []
        for item in product_tasks:
            if mode == "previous":
                previous = list(item.previous_quantities)
                if len(previous) < len(item.sizes):
                    previous.extend([""] * (len(item.sizes) - len(previous)))
                values.extend(previous[: len(item.sizes)])
            else:
                values.extend(item.quantities)
        return values

    def transfer_pattern_tokens(self, pattern: str) -> list[str]:
        return transfer_pattern_raw_tokens(pattern)

    def insert_transfer_pattern_text(self, text: str) -> None:
        entry = getattr(self, "transfer_pattern_entry", None)
        current = self.transfer_pattern_var.get()
        if not entry:
            self.transfer_pattern_var.set(current + text)
            self.update_transfer_pattern_preview()
            return
        try:
            index = entry.index("insert")
        except Exception:
            index = len(current)
        self.transfer_pattern_var.set(current[:index] + text + current[index:])
        entry.icursor(index + len(text))
        entry.focus_set()
        self.update_transfer_pattern_preview()

    def values_from_transfer_pattern(self, pattern: str, quantities: list[str], title: str) -> list[str]:
        values: list[str] = []
        for token in self.transfer_pattern_tokens(pattern):
            lower = token.lower()
            blank_count = transfer_pattern_blank_count(token)
            if blank_count:
                values.extend([""] * blank_count)
            elif lower in {"title", "ttl", "タイトル"}:
                values.append(title)
            elif lower in {"d", "date", "日付"}:
                values.append(self.db.transfer_date_text())
            else:
                try:
                    quantity_index = int(float(token)) - 1
                except ValueError:
                    values.append("")
                    continue
                values.append(quantities[quantity_index] if 0 <= quantity_index < len(quantities) else "")
        return values

    def transfer_value_roles(self, product_tasks: list[TaskView]) -> list[tuple[str, int | None]]:
        title = self.copy_title_var.get().strip()
        title_tabs = self.parse_tab_count(self.title_tabs_var.get())
        color_gap_tabs = self.parse_tab_count(self.color_gap_tabs_var.get())
        tail_tabs = self.parse_tab_count(self.tail_tabs_var.get())
        transfer_pattern = self.transfer_pattern_var.get().strip()
        quantity_count = len(self.flatten_product_quantities(product_tasks))
        roles: list[tuple[str, int | None]] = []
        if transfer_pattern:
            for token in self.transfer_pattern_tokens(transfer_pattern):
                lower = token.lower()
                blank_count = transfer_pattern_blank_count(token)
                if blank_count:
                    roles.extend([("blank", None)] * blank_count)
                elif lower in {"title", "ttl", "タイトル"}:
                    roles.append(("title", None))
                elif lower in {"d", "date", "日付"}:
                    roles.append(("date", None))
                else:
                    try:
                        quantity_index = int(float(token)) - 1
                    except ValueError:
                        quantity_index = -1
                    if 0 <= quantity_index < quantity_count:
                        roles.append(("quantity", quantity_index))
                    else:
                        roles.append(("blank", None))
            return roles
        if title:
            roles.append(("title", None))
        roles.extend([("blank", None)] * title_tabs)
        quantity_index = 0
        for color_index, item in enumerate(product_tasks):
            for _size in item.sizes:
                roles.append(("quantity", quantity_index))
                quantity_index += 1
            if color_index < len(product_tasks) - 1:
                roles.extend([("blank", None)] * color_gap_tabs)
        roles.extend([("blank", None)] * tail_tabs)
        if self.append_date_var.get():
            roles.append(("date", None))
        return roles

    def is_nonzero_quantity_text(self, value: object) -> bool:
        text = clean(value)
        if not text:
            return False
        try:
            return int(float(text)) != 0
        except ValueError:
            return True

    def current_page_has_transfer_quantity(self, product_tasks: list[TaskView]) -> bool:
        quantities = self.apply_current_page_quantity_multiplier(self.flatten_product_quantities(product_tasks))
        for role, index in self.transfer_value_roles(product_tasks):
            if role != "quantity" or index is None:
                continue
            if 0 <= index < len(quantities) and self.is_nonzero_quantity_text(quantities[index]):
                return True
        return False

    def update_transfer_pattern_preview(self, *_args) -> None:
        task = self.current_task()
        pattern = self.transfer_pattern_var.get().strip()
        if not task or not pattern:
            self.transfer_pattern_preview_var.set("転記パターン未設定: 従来のTab設定を使用します。")
            return
        quantities = self.apply_current_page_quantity_multiplier(self.flatten_product_quantities(self.display_tasks_for_product(task)))
        title = self.copy_title_var.get().strip()
        labels: list[str] = []
        blank_count = 0

        def flush_blank() -> None:
            nonlocal blank_count
            if blank_count == 1:
                labels.append("空")
            elif blank_count > 1:
                labels.append(f"空x{blank_count}")
            blank_count = 0

        for token in self.transfer_pattern_tokens(pattern):
            lower = token.lower()
            count = transfer_pattern_blank_count(token)
            if count:
                blank_count += count
                continue
            flush_blank()
            if lower in {"title", "ttl", "タイトル"}:
                labels.append(title or "タイトル")
            elif lower in {"d", "date", "日付"}:
                labels.append(self.db.transfer_date_text())
            else:
                try:
                    quantity_index = int(float(token))
                except ValueError:
                    labels.append("?")
                    continue
                value = quantities[quantity_index - 1] if 1 <= quantity_index <= len(quantities) else ""
                labels.append(f"数量{quantity_index}:{value}")
        flush_blank()
        self.transfer_pattern_preview_var.set("プレビュー: " + " | ".join(labels))

    def write_excel_and_next(self) -> None:
        if self.transfer_finished:
            self.window.destroy()
            return
        task = self.current_task()
        if not task:
            return
        if not self.save_current_min_stock_quantity():
            return
        page = self.current_transfer_page()
        page_id = int(page["id"]) if page else 0
        if self.is_excel_confirm_mode() and self.pending_excel_product_code == task.product_code and self.pending_excel_page_id == page_id:
            self.finish_confirmed_excel_transfer(task)
            return
        product_tasks = self.display_tasks_for_product(task)
        if not self.current_page_has_transfer_quantity(product_tasks):
            skipped_index = self.transfer_page_index
            if self.advance_to_next_transfer_page_with_quantity(task, product_tasks, move_to_candidate=True):
                return
            if skipped_index > 0 and self.has_completed_transfer_page(task.product_code):
                self.mark_product_tasks_copied_and_move_next(task, product_tasks)
                return
            messagebox.showwarning(
                "転記対象なし",
                "この商品の転記ページに数量がある設定が見つかりませんでした。\n転記パターンとページ設定を確認してください。",
                parent=self.window,
            )
            self.bring_to_front()
            return
        if self.is_manual_input_task(task):
            self.complete_manual_input_and_next(task)
            return
        target_path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.inventory_sheet_var.get()
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        if not target_path:
            messagebox.showwarning("転記先未設定", "現在商品の転記先Excelファイルを指定してください。", parent=self.window)
            self.bring_to_front()
            return
        self.save_current_transfer_page(task)
        if not os.path.exists(target_path):
            messagebox.showerror("ファイルなし", f"転記先ファイルが見つかりません。\n{target_path}", parent=self.window)
            self.bring_to_front()
            return
        values = self.build_product_transfer_values(product_tasks, task.product_code)
        previous_values = self.build_previous_product_transfer_values(product_tasks, task.product_code)
        roles = self.transfer_value_roles(product_tasks)
        alert_context = {
            "task": task,
            "product_tasks": product_tasks,
            "target_path": target_path,
            "sheet_name": sheet_name,
        }
        try:
            result = self.write_values_to_active_excel(
                target_path,
                values,
                save_and_close=not self.is_excel_confirm_mode(),
                sheet_name=sheet_name,
                previous_values=previous_values,
                roles=roles,
                task=task,
                alert_context=alert_context,
            )
        except ExcelReadOnlyError as exc:
            self.mark_read_only_retry_and_move_next(task, target_path, str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Excel転記エラー", str(exc), parent=self.window)
            self.bring_to_front()
            return
        if result == "skipped":
            source_task_ids = self.source_task_ids_for_items(product_tasks)
            for item in product_tasks:
                for task_id in item.source_task_ids or ([item.id] if item.id > 0 else []):
                    if task_id > 0:
                        self.db.mark_task(task_id, "skipped")
                item.status = "skipped"
                item.retry_required = False
                item.retry_reason = ""
            self.update_local_task_state(source_task_ids, "skipped")
            self._move_to_next_product(task.product_code)
            self.bring_to_front_delayed()
            return
        if self.is_excel_confirm_mode():
            self.pending_excel_product_code = task.product_code
            self.pending_excel_page_id = page_id
            self.update_excel_transfer_button()
            self.set_progress_text(f"{self.index + 1} / {len(self.tasks)}    状態: 転記済み・在庫確認待ち", alert=True)
            self.bring_to_front()
            return
        self.mark_current_transfer_page_completed(task)
        self.complete_excel_transfer_and_open_next(task, product_tasks)

    def complete_manual_input_and_next(self, task: TaskView) -> None:
        if not messagebox.askyesno(
            "手動入力確認",
            f"このページを手動入力済みにして{self.transfer_page_target_label()}進みますか？",
            parent=self.window,
        ):
            self.bring_to_front()
            return
        self.pending_excel_product_code = ""
        self.pending_excel_page_id = 0
        product_tasks = self.display_tasks_for_product(task)
        self.mark_current_transfer_page_completed(task)
        self.complete_excel_transfer_and_open_next(task, product_tasks, move_next_to_candidate=True)

    def mark_product_tasks_copied_and_move_next(self, task: TaskView, product_tasks: list[TaskView]) -> None:
        source_task_ids = self.source_task_ids_for_items(product_tasks)
        for item in product_tasks:
            for task_id in item.source_task_ids or ([item.id] if item.id > 0 else []):
                if task_id > 0:
                    self.db.mark_task(task_id, "copied")
            item.status = "copied"
            item.retry_required = False
            item.retry_reason = ""
        self.update_local_task_state(source_task_ids, "copied")
        self.completed_transfer_pages = {
            key for key in self.completed_transfer_pages if key[0] != task.product_code
        }
        self._move_to_next_product(task.product_code)
        self.bring_to_front_delayed()

    def advance_to_next_transfer_page_with_quantity(
        self,
        task: TaskView,
        product_tasks: list[TaskView],
        move_to_candidate: bool = True,
    ) -> bool:
        while self.transfer_page_index < len(self.transfer_pages) - 1:
            self.transfer_page_index += 1
            self.loaded_copy_settings_product = ""
            self.loaded_inventory_product = ""
            self.load_transfer_page_for_task(task)
            if not self.current_page_has_transfer_quantity(product_tasks):
                continue
            if self.current_transfer_page():
                self.open_inventory_file(show_error=False, move_to_candidate=move_to_candidate)
            self.render()
            return True
        return False

    def finish_confirmed_excel_transfer(self, task: TaskView) -> None:
        target_path = normalize_windows_path(self.inventory_file_var.get())
        try:
            self.save_active_excel_and_close(target_path, self.inventory_sheet_var.get())
        except ExcelReadOnlyError as exc:
            self.mark_read_only_retry_and_move_next(task, target_path, str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Excel保存エラー", str(exc), parent=self.window)
            self.bring_to_front()
            return
        product_tasks = self.display_tasks_for_product(task)
        self.pending_excel_product_code = ""
        self.pending_excel_page_id = 0
        self.mark_current_transfer_page_completed(task)
        self.update_excel_transfer_button()
        self.complete_excel_transfer_and_open_next(task, product_tasks, move_next_to_candidate=True)

    def complete_excel_transfer_and_open_next(
        self,
        task: TaskView,
        product_tasks: list[TaskView],
        move_next_to_candidate: bool = False,
    ) -> None:
        if self.transfer_page_index < len(self.transfer_pages) - 1:
            if self.advance_to_next_transfer_page_with_quantity(task, product_tasks, move_to_candidate=True):
                return
        self.mark_product_tasks_copied_and_move_next(task, product_tasks)
        next_task = self.current_task()
        if next_task and next_task.product_code != task.product_code and next_task.status == "pending":
            self.open_inventory_file(show_error=False, move_to_candidate=move_next_to_candidate)

    def is_excel_confirm_mode(self) -> bool:
        return self.db.get_setting("excel_transfer_mode", "auto") == "confirm"

    def update_excel_transfer_button(self) -> None:
        task = self.current_task()
        page = self.current_transfer_page()
        page_id = int(page["id"]) if page else 0
        target_label = self.transfer_page_target_label()
        if task and self.is_manual_input_task(task):
            self.excel_transfer_button_var.set(f"手入力完了して{target_label}")
        elif self.is_excel_confirm_mode() and task and self.pending_excel_product_code == task.product_code and self.pending_excel_page_id == page_id:
            self.excel_transfer_button_var.set(f"確認後 保存して{target_label}")
        elif self.is_excel_confirm_mode():
            if self.has_multiple_transfer_pages():
                self.excel_transfer_button_var.set("このページを転記して確認")
            else:
                self.excel_transfer_button_var.set("Excelへ転記して確認")
        else:
            if self.has_multiple_transfer_pages():
                self.excel_transfer_button_var.set(f"このページを転記して{target_label}")
            else:
                self.excel_transfer_button_var.set("Excelへ転記して次へ")

    def excel_write_value_for_role(self, value: str, role: tuple[str, int | None]) -> object:
        if role[0] == "date":
            today = date.today()
            return (today - date(1899, 12, 30)).days
        return value

    def write_values_to_active_excel(
        self,
        target_path: str,
        values: list[str],
        save_and_close: bool = True,
        sheet_name: str = "",
        previous_values: list[str] | None = None,
        roles: list[tuple[str, int | None]] | None = None,
        task: TaskView | None = None,
        alert_context: dict[str, object] | None = None,
    ) -> str:
        workbook, selection, excel = self.active_excel_workbook_and_selection(target_path, sheet_name, self.excel_start_col_var.get())
        self.clear_candidate_highlight()
        start_cell = selection.Cells(1, 1)
        row = start_cell.Row
        start_col = start_cell.Column
        roles = roles or [("unknown", None)] * len(values)
        previous_values = previous_values or []
        if self.should_try_title_date_only_add():
            add_result = self.try_title_date_only_add_overwrite(workbook, start_cell, values, roles, excel)
            if add_result == "added":
                self.capture_stock_alerts_if_enabled(workbook, start_cell, values, roles, alert_context)
                if save_and_close:
                    workbook.Save()
                    workbook.Close(SaveChanges=True)
                else:
                    self.bring_to_front()
                return "written"
        self.ensure_excel_row_is_writable(workbook.Worksheets(start_cell.Worksheet.Name), row, start_col, roles)
        if self.should_try_same_day_add(previous_values, roles):
            add_result = self.try_same_day_add_overwrite(workbook, start_cell, values, previous_values, roles, task)
            if add_result == "added":
                self.capture_stock_alerts_if_enabled(workbook, start_cell, values, roles, alert_context)
                if save_and_close:
                    workbook.Save()
                    workbook.Close(SaveChanges=True)
                else:
                    self.bring_to_front()
                return "written"
            if add_result == "skipped":
                if save_and_close:
                    workbook.Close(SaveChanges=False)
                else:
                    self.bring_to_front()
                return "skipped"
        for offset, value in enumerate(values):
            if clean(value):
                role = roles[offset] if offset < len(roles) else ("unknown", None)
                cell = workbook.Worksheets(start_cell.Worksheet.Name).Cells(row, start_col + offset)
                if self.db.get_setting("excel_overwrite_existing", "0") != "1" and clean(cell.Value):
                    continue
                if role[0] == "date":
                    cell.Value2 = self.excel_write_value_for_role(value, role)
                    cell.NumberFormatLocal = "m月d日"
                else:
                    cell.Value = self.excel_write_value_for_role(value, role)
        self.capture_stock_alerts_if_enabled(workbook, start_cell, values, roles, alert_context)
        if save_and_close:
            workbook.Save()
            workbook.Close(SaveChanges=True)
        else:
            self.bring_to_front()
        return "written"

    def protected_row_keywords(self) -> list[str]:
        text = self.db.get_setting("excel_protected_row_keywords", "確保")
        keywords = [clean(item) for item in re.split(r"[,、\n]+", text) if clean(item)]
        if "確保" not in keywords:
            keywords.append("確保")
        return keywords

    def row_has_protected_title_keyword(self, title_value: object) -> bool:
        title_text = clean(title_value)
        if not title_text:
            return False
        return any(keyword in title_text for keyword in self.protected_row_keywords())

    def is_red_font_color(self, color_value: object) -> bool:
        try:
            color_int = int(float(color_value))
        except (TypeError, ValueError):
            return False
        if color_int < 0:
            return False
        red = color_int % 256
        green = (color_int // 256) % 256
        blue = (color_int // 65536) % 256
        return red >= 160 and green <= 100 and blue <= 100

    def excel_cell_is_red(self, cell) -> bool:
        for attr in ("DisplayFormat", ""):
            try:
                font = cell.DisplayFormat.Font if attr else cell.Font
                if self.is_red_font_color(font.Color):
                    return True
            except Exception:
                continue
        return False

    def excel_row_has_red_quantity_value(self, worksheet, row: int, start_col: int, roles: list[tuple[str, int | None]]) -> bool:
        for offset, role in enumerate(roles):
            if role[0] != "quantity":
                continue
            cell = worksheet.Cells(row, start_col + offset)
            if clean(cell.Value) and self.excel_cell_is_red(cell):
                return True
        return False

    def ensure_excel_row_is_writable(self, worksheet, row: int, start_col: int, roles: list[tuple[str, int | None]]) -> None:
        title_offsets = [index for index, role in enumerate(roles) if role[0] == "title"]
        for offset in title_offsets:
            if self.row_has_protected_title_keyword(worksheet.Cells(row, start_col + offset).Value):
                raise RuntimeError("選択中の行は書き込み禁止行です。タイトル列に禁止キーワードが含まれています。別の開始セルを選択してください。")
        if self.excel_row_has_red_quantity_value(worksheet, row, start_col, roles):
            raise RuntimeError("選択中の行は書き込み禁止行です。赤字の予定数と思われるセルがあります。別の開始セルを選択してください。")

    def capture_stock_alerts_if_enabled(
        self,
        workbook,
        start_cell,
        values: list[str],
        roles: list[tuple[str, int | None]],
        alert_context: dict[str, object] | None,
    ) -> None:
        if self.db.get_setting("stock_alert_enabled", "0") != "1" or not alert_context:
            return
        task = alert_context.get("task")
        product_tasks = alert_context.get("product_tasks")
        if not isinstance(task, TaskView) or not isinstance(product_tasks, list):
            return
        min_stock = self.db.product_min_stock_quantity(task.product_code)
        worksheet = workbook.Worksheets(start_cell.Worksheet.Name)
        start_row = int(start_cell.Row)
        start_col = int(start_cell.Column)
        labels = self.stock_alert_labels()
        label_row = self.find_stock_remaining_row(worksheet, start_row, start_col, labels)
        if not label_row:
            self.db.save_stock_alert(
                task.id if task.id > 0 else None,
                task.product_code,
                task.product_name,
                "",
                "",
                None,
                min_stock,
                "missing_label",
                clean(alert_context.get("target_path")),
                clean(alert_context.get("sheet_name")),
                "",
                f"残数ラベルが見つかりません: {','.join(labels)}",
            )
            return
        quantity_meta = self.quantity_metadata(product_tasks)
        for offset, role in enumerate(roles):
            if role[0] != "quantity" or role[1] is None:
                continue
            quantity_index = int(role[1])
            if quantity_index >= len(quantity_meta):
                continue
            color, size = quantity_meta[quantity_index]
            if self.db.is_variant_sold_out(task.product_code, color, size):
                continue
            cell = worksheet.Cells(label_row, start_col + offset)
            remaining = self.quantity_number(cell.Value)
            if should_create_stock_alert(remaining, min_stock):
                status = "negative" if remaining < 0 else "low"
                message = "在庫残数がマイナスです" if remaining < 0 else "最低在庫数以下です"
                self.db.save_stock_alert(
                    task.id if task.id > 0 else None,
                    task.product_code,
                    task.product_name,
                    color,
                    size,
                    remaining,
                    min_stock,
                    status,
                    clean(alert_context.get("target_path")),
                    clean(alert_context.get("sheet_name")),
                    self.excel_cell_address(cell),
                    message,
                )

    def stock_alert_labels(self) -> list[str]:
        labels = [
            clean(label)
            for label in re.split(r"[,、\n]+", self.db.get_setting("stock_alert_labels", "残数"))
            if clean(label)
        ]
        return labels or ["残数"]

    def excel_cell_address(self, cell) -> str:
        try:
            address = cell.Address
            if callable(address):
                return clean(address(False, False))
            return clean(str(address).replace("$", ""))
        except Exception:
            try:
                return f"{excel_index_to_column(int(cell.Column))}{int(cell.Row)}"
            except Exception:
                return ""

    def find_stock_remaining_row(self, worksheet, start_row: int, start_col: int, labels: list[str]) -> int:
        label_set = {label.strip() for label in labels}
        found_row = 0
        for row in range(start_row, start_row + 30):
            for col in range(max(1, start_col - 2), start_col + 3):
                if clean(worksheet.Cells(row, col).Value) in label_set:
                    found_row = row
        return found_row

    def quantity_metadata(self, product_tasks: list[TaskView]) -> list[tuple[str, str]]:
        meta: list[tuple[str, str]] = []
        for item in product_tasks:
            for size in item.sizes:
                meta.append((item.color, size))
        return meta

    def should_try_same_day_add(self, previous_values: list[str], roles: list[tuple[str, int | None]]) -> bool:
        if self.db.get_setting("excel_same_day_title_add", "0") != "1":
            return False
        if self.db.get_setting("excel_same_day_add_mode", "previous") != "previous":
            return False
        quantity_positions = [index for index, role in enumerate(roles) if role[0] == "quantity"]
        if not quantity_positions:
            return False
        if not any(self.quantity_number(previous_values[index] if index < len(previous_values) else "") != 0 for index in quantity_positions):
            return False
        return any(role[0] == "title" for role in roles) and any(role[0] == "date" for role in roles)

    def should_try_title_date_only_add(self) -> bool:
        if self.db.get_setting("excel_same_day_title_add", "0") != "1":
            return False
        return self.db.get_setting("excel_same_day_add_mode", "previous") == "title_date"

    def try_title_date_only_add_overwrite(
        self,
        workbook,
        start_cell,
        values: list[str],
        roles: list[tuple[str, int | None]],
        excel=None,
    ) -> str:
        worksheet = workbook.Worksheets(start_cell.Worksheet.Name)
        start_row = int(start_cell.Row)
        start_col = int(start_cell.Column)
        add_start_col = start_col
        target_row = self.find_title_date_add_row_at_or_above(worksheet, start_row, start_col, values, roles, 5)
        if not target_row and excel is not None:
            try:
                candidate = self.detect_write_candidate_cell(worksheet, excel, self.excel_start_col_var.get())
                candidate.row = self.adjust_candidate_after_red_marker(worksheet, candidate.row, candidate.col, candidate.island)
                target_row = self.find_title_date_add_row_in_candidate_range(worksheet, candidate, values, roles)
                if target_row:
                    add_start_col = candidate.col
            except Exception:
                target_row = 0
        if not target_row:
            return "not_found"
        self.ensure_excel_row_is_writable(worksheet, target_row, add_start_col, roles)
        self.add_values_to_excel_row(worksheet, target_row, add_start_col, values, roles)
        return "added"

    def find_title_date_add_row_at_or_above(
        self,
        worksheet,
        start_row: int,
        start_col: int,
        values: list[str],
        roles: list[tuple[str, int | None]],
        search_rows: int,
    ) -> int:
        return self.find_title_date_add_row_in_rows(
            worksheet,
            start_col,
            range(start_row, max(0, start_row - search_rows - 1), -1),
            values,
            roles,
        )

    def find_title_date_add_row_in_candidate_range(
        self,
        worksheet,
        candidate: WriteCandidate,
        values: list[str],
        roles: list[tuple[str, int | None]],
    ) -> int:
        if not candidate.values:
            return 0
        range_end_row = candidate.start_row + len(candidate.values) - 1
        scan_start = min(candidate.row - 1, range_end_row)
        if scan_start < candidate.start_row:
            return 0
        return self.find_title_date_add_row_in_rows(
            worksheet,
            candidate.col,
            range(scan_start, candidate.start_row - 1, -1),
            values,
            roles,
        )

    def find_title_date_add_row_in_rows(
        self,
        worksheet,
        start_col: int,
        rows,
        values: list[str],
        roles: list[tuple[str, int | None]],
    ) -> int:
        title_positions = [index for index, role in enumerate(roles) if role[0] == "title"]
        date_positions = [index for index, role in enumerate(roles) if role[0] == "date"]
        quantity_positions = [index for index, role in enumerate(roles) if role[0] == "quantity"]
        if not title_positions or not date_positions or not quantity_positions:
            return 0
        title_pos = title_positions[0]
        date_pos = date_positions[-1]
        expected_title = clean(values[title_pos] if title_pos < len(values) else "")
        if not expected_title:
            return 0
        for target_row in rows:
            row_title = clean(worksheet.Cells(target_row, start_col + title_pos).Value)
            if row_title != expected_title:
                continue
            if not self.is_today_excel_value(worksheet.Cells(target_row, start_col + date_pos).Value):
                continue
            return int(target_row)
        return 0

    def add_values_to_excel_row(
        self,
        worksheet,
        target_row: int,
        start_col: int,
        values: list[str],
        roles: list[tuple[str, int | None]],
    ) -> None:
        for offset, role in enumerate(roles):
            if role[0] != "quantity":
                continue
            current_delta = self.quantity_number(values[offset] if offset < len(values) else "")
            if current_delta == 0:
                continue
            cell = worksheet.Cells(target_row, start_col + offset)
            cell.Value = self.quantity_number(cell.Value) + current_delta

    def try_same_day_add_overwrite(
        self,
        workbook,
        start_cell,
        values: list[str],
        previous_values: list[str],
        roles: list[tuple[str, int | None]],
        task: TaskView | None,
    ) -> str:
        worksheet = workbook.Worksheets(start_cell.Worksheet.Name)
        start_row = int(start_cell.Row)
        start_col = int(start_cell.Column)
        search_rows = max(1, self.safe_int(self.db.get_setting("excel_same_day_search_rows", "10"), 10))
        title_positions = [index for index, role in enumerate(roles) if role[0] == "title"]
        date_positions = [index for index, role in enumerate(roles) if role[0] == "date"]
        quantity_positions = [index for index, role in enumerate(roles) if role[0] == "quantity"]
        if not title_positions or not date_positions or not quantity_positions:
            return "not_found"
        title_pos = title_positions[0]
        date_pos = date_positions[-1]
        expected_title = clean(values[title_pos] if title_pos < len(values) else "")
        found_title_date = False
        for target_row in range(start_row - 1, max(0, start_row - search_rows - 1), -1):
            row_title = clean(worksheet.Cells(target_row, start_col + title_pos).Value)
            if row_title != expected_title:
                continue
            if not self.is_today_excel_value(worksheet.Cells(target_row, start_col + date_pos).Value):
                continue
            found_title_date = True
            if not self.excel_quantities_match_previous(worksheet, target_row, start_col, quantity_positions, previous_values):
                self.handle_same_day_add_failure(
                    "本日同タイトル行は見つかりましたが、Excel上の数量が前回集計数量と一致しません。",
                    task,
                )
                return "skipped" if self.db.get_setting("excel_same_day_missing_action", "confirm") == "skip" else "not_found"
            for offset in quantity_positions:
                current_delta = self.quantity_number(values[offset] if offset < len(values) else "")
                if current_delta == 0:
                    continue
                previous_qty = self.quantity_number(previous_values[offset] if offset < len(previous_values) else "")
                worksheet.Cells(target_row, start_col + offset).Value = previous_qty + current_delta
            return "added"
        if not found_title_date:
            self.handle_same_day_add_failure(
                f"候補セルの上 {search_rows} 行以内に、本日かつ同タイトルの行が見つかりません。",
                task,
            )
            return "skipped" if self.db.get_setting("excel_same_day_missing_action", "confirm") == "skip" else "not_found"
        return "not_found"

    def excel_quantities_match_previous(
        self,
        worksheet,
        target_row: int,
        start_col: int,
        quantity_positions: list[int],
        previous_values: list[str],
    ) -> bool:
        for offset in quantity_positions:
            excel_qty = self.quantity_number(worksheet.Cells(target_row, start_col + offset).Value)
            previous_qty = self.quantity_number(previous_values[offset] if offset < len(previous_values) else "")
            if excel_qty != previous_qty:
                return False
        return True

    def handle_same_day_add_failure(self, message: str, task: TaskView | None) -> None:
        product = f"{task.product_name} / {task.color}" if task else ""
        detail = f"{product}\n{message}".strip()
        self.db.warn("same_day_add_skipped", message, product)
        self.db.conn.commit()
        if self.db.get_setting("excel_same_day_missing_action", "confirm") == "skip":
            self.progress_var.set(f"同日加算スキップ: {product}")
            return
        raise RuntimeError(detail)

    def quantity_number(self, value: object) -> int:
        text = clean(value)
        if not text:
            return 0
        try:
            return int(float(str(text).replace(",", "")))
        except ValueError:
            return 0

    def safe_int(self, value: object, default: int = 0) -> int:
        try:
            return int(float(clean(value)))
        except ValueError:
            return default

    def is_today_excel_value(self, value: object) -> bool:
        if value is None:
            return False
        today = date.today()
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            try:
                return date(int(value.year), int(value.month), int(value.day)) == today
            except Exception:
                pass
        text = clean(value)
        if not text:
            return False
        normalized = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        parts = [int(part) for part in re.findall(r"\d+", normalized)]
        if len(parts) >= 3:
            year, month, day = parts[0], parts[1], parts[2]
            if year < 100:
                year += 2000
            return (year, month, day) == (today.year, today.month, today.day)
        if len(parts) == 2:
            month, day = parts[0], parts[1]
            return (month, day) == (today.month, today.day)
        return False

    def active_excel_workbook_and_selection(self, target_path: str, sheet_name: str = "", excel_start_col: str = "A"):
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Excel直接転記には pywin32 が必要です。") from exc
        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception as exc:
            raise RuntimeError("Excelが起動していません。転記先Excelを開き、開始セルを選択してから実行してください。") from exc
        workbook = excel.ActiveWorkbook
        selection = excel.Selection
        if workbook is None or selection is None:
            raise RuntimeError("Excelで転記開始セルを選択してから実行してください。")
        active_path = normalize_windows_path(clean(workbook.FullName))
        if os.path.normcase(active_path) != os.path.normcase(target_path):
            raise RuntimeError(
                "Excelで開いているファイルが現在商品の転記先と一致しません。\n"
                f"現在商品の転記先: {target_path}\n"
                f"Excelで選択中: {active_path}"
            )
        if self.workbook_is_read_only(workbook):
            self.close_workbook_without_save(workbook)
            raise ExcelReadOnlyError("読み取り専用のため転記できませんでした。後ほど再試行してください。")
        if sheet_name:
            worksheet = self.resolve_excel_worksheet(workbook, sheet_name)
            worksheet.Activate()
            selection = excel.Selection
        self.scroll_excel_to_start_col(excel, excel_start_col)
        return workbook, selection, excel

    def save_active_excel_and_close(self, target_path: str, sheet_name: str = "") -> None:
        workbook, _selection, _excel = self.active_excel_workbook_and_selection(target_path, sheet_name, self.excel_start_col_var.get())
        workbook.Save()
        workbook.Close(SaveChanges=True)

    def select_write_candidate_cell(self) -> None:
        task = self.current_task()
        if not task:
            messagebox.showwarning("商品なし", "現在表示中の商品がありません。", parent=self.window)
            self.bring_to_front()
            return
        if clean(self.transfer_pattern_var.get()):
            if not messagebox.askyesno(
                "転記パターン上書き確認",
                "入力済みの転記パターンがあります。\n自動取得すると現在の転記パターンを上書きします。\n続行しますか？",
                parent=self.window,
            ):
                self.bring_to_front()
                return
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.inventory_sheet_var.get()
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        if not path:
            messagebox.showwarning("ファイル未設定", "転記先ファイルを指定してください。", parent=self.window)
            self.bring_to_front()
            return
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"転記先ファイルが見つかりません。\n{path}", parent=self.window)
            self.bring_to_front()
            return
        try:
            workbook, worksheet, excel = self.open_target_workbook(path, sheet_name, self.excel_start_col_var.get())
            candidate = self.detect_write_candidate_cell(worksheet, excel, self.excel_start_col_var.get())
            row, col = candidate.row, candidate.col
            row = self.adjust_candidate_after_red_marker(worksheet, row, col, candidate.island)
            candidate.row = row
            product_tasks = self.display_tasks_for_product(task)
            roles = self.transfer_value_roles(product_tasks)
            self.ensure_excel_row_is_writable(worksheet, row, col, roles)
            workbook.Activate()
            worksheet.Activate()
            worksheet.Cells(row, col).Select()
            excel.ActiveWindow.ScrollRow = max(1, row - 8)
            excel.ActiveWindow.ScrollColumn = max(1, col - 3)
            self.save_current_transfer_page(task)
            self.auto_detect_and_save_copy_rule(task, candidate)
            self.show_candidate_cell_after_select(excel, worksheet, row, col)
        except Exception as exc:
            messagebox.showerror("書き込み行候補エラー", str(exc), parent=self.window)
            self.bring_to_front()

    def extend_inventory_island(self) -> None:
        task = self.current_task()
        if not task:
            messagebox.showwarning("商品なし", "現在表示中の商品がありません。", parent=self.window)
            self.bring_to_front()
            return
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.inventory_sheet_var.get()
        start_col_text = normalize_excel_start_col(self.excel_start_col_var.get())
        self.excel_start_col_var.set(start_col_text)
        if not path:
            messagebox.showwarning("ファイル未設定", "転記先Excelファイルを指定してください。", parent=self.window)
            self.bring_to_front()
            return
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"転記先Excelファイルが見つかりません。\n{path}", parent=self.window)
            self.bring_to_front()
            return
        if not messagebox.askyesno(
            "記入欄増設",
            "指定開始列の一番下の記入欄ブロックを複製して、その直下に新しい記入欄を追加します。\n"
            "既に空の記入欄がある場合もさらに追加されます。\n\n実行しますか？",
            parent=self.window,
        ):
            self.bring_to_front()
            return
        try:
            workbook, worksheet, excel = self.open_target_workbook(path, sheet_name, start_col_text)
            start_cell = self.extend_inventory_island_on_sheet(worksheet, excel, start_col_text)
            workbook.Activate()
            worksheet.Activate()
            start_cell.Select()
            excel.ActiveWindow.ScrollRow = max(1, int(start_cell.Row) - 8)
            excel.ActiveWindow.ScrollColumn = max(1, int(start_cell.Column) - 3)
            try:
                excel.CutCopyMode = False
            except Exception:
                pass
            self.bring_excel_to_front(excel)
            self.progress_var.set(f"{self.index + 1} / {len(self.tasks)}    状態: 記入欄を増設しました")
        except Exception as exc:
            messagebox.showerror("記入欄増設", str(exc), parent=self.window)
            self.bring_to_front()

    def extend_inventory_island_on_sheet(self, worksheet, excel, excel_start_col: str):
        used = worksheet.UsedRange
        used_start_row = int(used.Row)
        used_end_row = used_start_row + int(used.Rows.Count) - 1
        used_start_col = int(used.Column)
        used_end_col = used_start_col + int(used.Columns.Count) - 1
        target_col = excel_column_to_index(excel_start_col, 1)
        scan_start_col = max(used_start_col, target_col)
        scan_end_col = min(used_end_col, max(target_col + 120, scan_start_col + 20))
        if scan_start_col > scan_end_col:
            raise RuntimeError("指定開始列の周辺に記入欄ブロックを検出できませんでした。")
        values, formulas = self.range_values_and_formulas(worksheet, used_start_row, scan_start_col, used_end_row, scan_end_col)
        islands = self.left_target_islands(values, used_start_row, scan_start_col, target_col)
        if not islands:
            raise RuntimeError("指定開始列の一番下の記入欄ブロックを検出できませんでした。")
        source_island = max(islands, key=lambda item: (item[2], item[1], -item[0]))
        title_col, total_row, shipment_total_row, island_end_col = source_island
        residual_row = self.find_residual_row_after_footer(worksheet, shipment_total_row, title_col)
        if not residual_row:
            raise RuntimeError("コピー元の残数行を検出できませんでした。")
        previous_residual_row = self.find_previous_residual_row_for_island(worksheet, islands, source_island)
        if not previous_residual_row:
            raise RuntimeError("コピー範囲の起点となる前ブロックの残数行を検出できませんでした。")
        copy_start_row = previous_residual_row + 1
        copy_end_row = residual_row
        if copy_start_row > copy_end_row:
            raise RuntimeError("記入欄ブロックのコピー範囲を特定できませんでした。")
        paste_start_row = residual_row + 1
        source_range = worksheet.Range(
            worksheet.Cells(copy_start_row, title_col),
            worksheet.Cells(copy_end_row, island_end_col),
        )
        destination = worksheet.Cells(paste_start_row, title_col)
        source_range.Copy(Destination=destination)
        row_offset = paste_start_row - copy_start_row
        new_copy_start_row = copy_start_row + row_offset
        new_total_row = total_row + row_offset
        new_shipment_total_row = shipment_total_row + row_offset
        new_residual_row = residual_row + row_offset
        inherited_row = self.find_inherited_stock_row(worksheet, new_copy_start_row, new_total_row, title_col, island_end_col)
        if inherited_row:
            self.clear_inbound_rows_for_new_island(worksheet, inherited_row + 1, new_total_row - 1, title_col, island_end_col)
        self.clear_shipment_rows_for_new_island(worksheet, new_total_row + 1, new_shipment_total_row - 1, title_col, island_end_col)
        start_row = self.first_writable_row_after_total(worksheet, new_total_row + 1, new_shipment_total_row - 1, title_col, island_end_col)
        return worksheet.Cells(start_row or max(new_total_row + 1, new_copy_start_row), title_col)

    def find_residual_row_after_footer(self, worksheet, footer_row: int, title_col: int) -> int:
        labels = set(self.stock_alert_labels())
        for row in range(max(1, footer_row), footer_row + 8):
            for col in range(max(1, title_col - 2), title_col + 3):
                if clean(worksheet.Cells(row, col).Value) in labels:
                    return row
        return 0

    def find_previous_residual_row_for_island(
        self,
        worksheet,
        islands: list[tuple[int, int, int, int]],
        source_island: tuple[int, int, int, int],
    ) -> int:
        title_col, total_row, _shipment_total_row, _island_end_col = source_island
        previous = [
            island
            for island in islands
            if island[0] == title_col and island[2] < total_row
        ]
        if previous:
            _prev_title_col, _prev_total_row, prev_shipment_total_row, _prev_end_col = max(previous, key=lambda item: item[2])
            residual_row = self.find_residual_row_after_footer(worksheet, prev_shipment_total_row, title_col)
            if residual_row:
                return residual_row
        labels = set(self.stock_alert_labels())
        for row in range(total_row - 1, max(0, total_row - 400), -1):
            for col in range(max(1, title_col - 2), title_col + 3):
                if clean(worksheet.Cells(row, col).Value) in labels:
                    return row
        return 0

    def find_inherited_stock_row(self, worksheet, start_row: int, total_row: int, title_col: int, end_col: int) -> int:
        for row in range(total_row - 1, start_row - 1, -1):
            label = clean(worksheet.Cells(row, title_col).Value)
            formula_count, checked_count = self.excel_row_formula_counts(worksheet, row, title_col + 1, end_col)
            if self.is_inherited_stock_label(label) and formula_count:
                return row
            if checked_count and formula_count >= max(3, math.ceil(checked_count * 0.6)):
                return row
        return 0

    def excel_row_formula_counts(self, worksheet, row: int, start_col: int, end_col: int) -> tuple[int, int]:
        formula_count = 0
        checked_count = 0
        for col in range(start_col, end_col + 1):
            checked_count += 1
            if self.excel_cell_has_formula(worksheet.Cells(row, col)):
                formula_count += 1
        return formula_count, checked_count

    def is_inherited_stock_label(self, label: str) -> bool:
        text = clean(label)
        if not text or "確認" in text or "追加" in text:
            return False
        return text in {"在庫", "残数", "残在庫", "現在庫", "前在庫", "前残", "前回残", "前回残数"}

    def clear_inbound_rows_for_new_island(self, worksheet, start_row: int, end_row: int, title_col: int, end_col: int) -> None:
        retry_cells = []
        for row in range(start_row, end_row + 1):
            title_cell = worksheet.Cells(row, title_col)
            if not self.excel_cell_has_formula(title_cell):
                title_cell.Value = "追加"
                if clean(title_cell.Value) != "追加":
                    retry_cells.append((row, title_col, "追加"))
            for col in range(title_col + 1, end_col + 1):
                cell = worksheet.Cells(row, col)
                if not self.excel_cell_has_formula(cell):
                    cell.ClearContents()
                    if clean(cell.Value) != "":
                        retry_cells.append((row, col, ""))
        self.verify_cleared_cells(worksheet, retry_cells, "入荷記入欄")

    def clear_shipment_rows_for_new_island(self, worksheet, start_row: int, end_row: int, title_col: int, end_col: int) -> None:
        retry_cells = []
        for row in range(start_row, end_row + 1):
            for col in range(title_col, end_col + 1):
                cell = worksheet.Cells(row, col)
                if not self.excel_cell_has_formula(cell):
                    cell.ClearContents()
                    if clean(cell.Value) != "":
                        retry_cells.append((row, col, ""))
        self.verify_cleared_cells(worksheet, retry_cells, "出荷記入欄")

    def verify_cleared_cells(self, worksheet, retry_cells: list[tuple[int, int, str]], area_name: str) -> None:
        if not retry_cells:
            return
        failed = []
        for row, col, expected in retry_cells:
            cell = worksheet.Cells(row, col)
            if self.excel_cell_has_formula(cell):
                continue
            if expected:
                cell.Value = expected
            else:
                cell.ClearContents()
            if clean(cell.Value) != expected:
                failed.append(worksheet.Cells(row, col).Address(False, False))
        if failed:
            preview = ", ".join(failed[:10])
            more = "" if len(failed) <= 10 else f" ほか{len(failed) - 10}件"
            raise RuntimeError(f"{area_name}の消去確認で値が残っているセルがあります: {preview}{more}")

    def first_writable_row_after_total(self, worksheet, start_row: int, end_row: int, title_col: int, end_col: int) -> int:
        for row in range(start_row, end_row + 1):
            for col in range(title_col, end_col + 1):
                if not self.excel_cell_has_formula(worksheet.Cells(row, col)):
                    return row
        return 0

    def excel_cell_has_formula(self, cell) -> bool:
        try:
            return bool(cell.HasFormula)
        except Exception:
            return clean(getattr(cell, "Formula", "")).startswith("=")

    def adjust_candidate_after_red_marker(self, worksheet, row: int, col: int, island: tuple[int, int, int, int] | None) -> int:
        if not island:
            return row
        _title_col, _header_row, footer_row, island_end_col = island
        if row >= footer_row:
            return row
        if self.excel_row_has_red_value_in_columns(worksheet, row, col, island_end_col):
            return min(row + 1, footer_row - 1)
        return row

    def excel_row_has_red_value_in_columns(self, worksheet, row: int, start_col: int, end_col: int) -> bool:
        for col in range(start_col, end_col + 1):
            cell = worksheet.Cells(row, col)
            if clean(cell.Value) and self.excel_cell_is_red(cell):
                return True
        return False

    def open_target_workbook(self, path: str, sheet_name: str = "", excel_start_col: str = "A"):
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Excel操作には pywin32 が必要です。") from exc
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = True
        workbook = None
        normalized_path = os.path.normcase(normalize_windows_path(path))
        for book in excel.Workbooks:
            if os.path.normcase(normalize_windows_path(clean(book.FullName))) == normalized_path:
                workbook = book
                break
        if workbook is None:
            workbook = excel.Workbooks.Open(path, UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, Notify=False)
        if sheet_name:
            worksheet = self.resolve_excel_worksheet(workbook, sheet_name)
        else:
            worksheet = workbook.ActiveSheet
        workbook.Activate()
        worksheet.Activate()
        self.scroll_excel_to_start_col(excel, excel_start_col)
        return workbook, worksheet, excel

    def resolve_excel_worksheet(self, workbook, sheet_name: str):
        if not str(sheet_name).strip():
            return workbook.ActiveSheet
        try:
            return workbook.Worksheets(sheet_name)
        except Exception:
            pass
        wanted = str(sheet_name).strip()
        if wanted:
            try:
                for index in range(1, int(workbook.Worksheets.Count) + 1):
                    worksheet = workbook.Worksheets(index)
                    if str(worksheet.Name).strip() == wanted:
                        return worksheet
            except Exception:
                pass
        raise RuntimeError(f"指定シートが見つかりません: {sheet_name}")

    def scroll_excel_to_start_col(self, excel, excel_start_col: str = "A") -> None:
        try:
            active_window = excel.ActiveWindow
            current_row = max(1, int(active_window.ScrollRow))
            active_window.ScrollColumn = excel_column_to_index(excel_start_col, 1)
            active_window.ScrollRow = current_row
        except Exception:
            pass

    def detect_write_candidate_cell(self, worksheet, excel, excel_start_col: str = "") -> WriteCandidate:
        used = worksheet.UsedRange
        used_start_row = used.Row
        used_start_col = used.Column
        used_end_row = used_start_row + used.Rows.Count - 1
        used_end_col = used_start_col + used.Columns.Count - 1

        if excel_start_col:
            self.scroll_excel_to_start_col(excel, excel_start_col)
        visible = excel.ActiveWindow.VisibleRange
        visible_start_row = visible.Row
        visible_end_row = visible.Row + visible.Rows.Count - 1
        visible_end_col = visible.Column + visible.Columns.Count - 1
        target_col = excel_column_to_index(excel_start_col, visible.Column) if excel_start_col else visible.Column

        start_row = max(used_start_row, visible_start_row - 40)
        end_row = min(used_end_row, visible_end_row + 80)
        start_col = max(used_start_col, target_col)
        end_col = min(used_end_col, max(visible_end_col, target_col + 24, 20))
        values, formulas = self.range_values_and_formulas(worksheet, start_row, start_col, end_row, end_col)
        visible_values = values
        visible_formulas = formulas
        visible_range_start_row = start_row
        visible_candidate = self.detect_left_island_candidate_in_range(values, formulas, start_row, start_col, target_col, require_lower_context=True)
        visible_left_islands = self.left_target_islands(values, start_row, start_col, target_col)

        upper_blocks, bottom_blocks = self.write_candidate_search_blocks(used_start_row, used_end_row, visible_start_row)
        blank_lower_candidate: WriteCandidate | None = None
        for block_start, block_end in bottom_blocks:
            values, formulas = self.range_values_and_formulas(worksheet, block_start, start_col, block_end, end_col)
            candidate = self.detect_left_island_candidate_in_range(values, formulas, block_start, start_col, target_col)
            if candidate:
                if visible_candidate and visible_candidate.row > candidate.row:
                    return visible_candidate
                if candidate.island and not self.island_has_real_shipment_rows(values, formulas, block_start, start_col, candidate.island):
                    if blank_lower_candidate is None:
                        blank_lower_candidate = candidate
                    continue
                if (
                    blank_lower_candidate
                    and candidate.row < blank_lower_candidate.row
                    and block_start < blank_lower_candidate.start_row - 260
                ):
                    continue
                return candidate

        if visible_candidate:
            return visible_candidate
        if blank_lower_candidate:
            return blank_lower_candidate

        for block_start, block_end in upper_blocks:
            values, formulas = self.range_values_and_formulas(worksheet, block_start, start_col, block_end, end_col)
            candidate = self.detect_left_island_candidate_in_range(values, formulas, block_start, start_col, target_col)
            if candidate:
                return candidate

        candidate = self.detect_candidate_from_totals(visible_values, visible_formulas, visible_range_start_row, start_col)
        if candidate:
            end_col_for_candidate = start_col + len(visible_values[0]) - 1 if visible_values else start_col
            if self.is_writable_candidate_row(visible_values, visible_formulas, visible_range_start_row, candidate[0], candidate[1], start_col, end_col_for_candidate):
                return WriteCandidate(candidate[0], candidate[1], visible_range_start_row, start_col, visible_values, visible_formulas, None)
        raise RuntimeError("表示範囲周辺で書き込み候補を検出できませんでした。手動で開始セルを選択してください。")

    def write_candidate_search_blocks(
        self,
        used_start_row: int,
        used_end_row: int,
        visible_start_row: int,
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        block_size = 260
        overlap = 60
        upper_blocks: list[tuple[int, int]] = []
        bottom_blocks: list[tuple[int, int]] = []

        end_row = max(used_start_row, visible_start_row - 1)
        while end_row >= used_start_row:
            start_row = max(used_start_row, end_row - block_size + 1)
            upper_blocks.append((start_row, end_row))
            if start_row == used_start_row:
                break
            end_row = start_row + overlap - 1

        bottom_end = used_end_row
        while bottom_end >= used_start_row:
            bottom_start = max(used_start_row, bottom_end - block_size + 1)
            block = (bottom_start, bottom_end)
            if block not in upper_blocks and block not in bottom_blocks:
                bottom_blocks.append(block)
            if bottom_start == used_start_row:
                break
            bottom_end = bottom_start + overlap - 1
        return upper_blocks, bottom_blocks

    def detect_left_island_candidate_in_range(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
        target_col: int,
        require_lower_context: bool = False,
    ) -> WriteCandidate | None:
        islands = self.left_target_islands(values, start_row, start_col, target_col)
        if not islands:
            return None
        target_islands = self.candidate_island_window(values, formulas, start_row, start_col, islands)
        used_islands = [
            island
            for island in target_islands
            if self.island_has_used_rows(values, formulas, start_row, start_col, island)
        ]
        if require_lower_context and not used_islands:
            return None
        island = used_islands[-1] if used_islands else target_islands[-1]
        if require_lower_context and used_islands and island == target_islands[-1]:
            return None
        title_col, header_row, footer_row, island_end_col = island
        try:
            candidate_row = self.find_candidate_row_with_islands(
                values,
                formulas,
                start_row,
                title_col,
                start_col,
                header_row,
                footer_row,
                island_end_col,
                target_islands,
            )
        except RuntimeError:
            candidate_row = self.find_candidate_row_before_trailing_reserved_row(
                values,
                formulas,
                start_row,
                title_col,
                start_col,
                header_row,
                footer_row,
                island_end_col,
                target_islands,
            )
            if not candidate_row:
                return None
        if not self.is_writable_candidate_row(values, formulas, start_row, candidate_row, title_col, start_col, island_end_col):
            try:
                current_index = target_islands.index(island)
            except ValueError:
                current_index = -1
            for lower_island in target_islands[current_index + 1:]:
                lower_title_col, lower_header_row, lower_footer_row, lower_end_col = lower_island
                try:
                    lower_candidate_row = self.find_candidate_row_with_islands(
                        values,
                        formulas,
                        start_row,
                        lower_title_col,
                        start_col,
                        lower_header_row,
                        lower_footer_row,
                        lower_end_col,
                        target_islands,
                    )
                except RuntimeError:
                    lower_candidate_row = self.find_candidate_row_before_trailing_reserved_row(
                        values,
                        formulas,
                        start_row,
                        lower_title_col,
                        start_col,
                        lower_header_row,
                        lower_footer_row,
                        lower_end_col,
                        target_islands,
                    )
                if lower_candidate_row and self.is_writable_candidate_row(
                    values,
                    formulas,
                    start_row,
                    lower_candidate_row,
                    lower_title_col,
                    start_col,
                    lower_end_col,
                ):
                    return WriteCandidate(lower_candidate_row, lower_title_col, start_row, start_col, values, formulas, lower_island)
            return None
        return WriteCandidate(candidate_row, title_col, start_row, start_col, values, formulas, island)

    def candidate_island_window(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
        islands: list[tuple[int, int, int, int]],
    ) -> list[tuple[int, int, int, int]]:
        base_window = islands[-3:]
        trailing_blank_count = 0
        for island in reversed(islands):
            if self.island_has_used_rows(values, formulas, start_row, start_col, island):
                break
            trailing_blank_count += 1
        if trailing_blank_count < 2:
            return base_window

        for index in range(len(islands) - trailing_blank_count - 1, -1, -1):
            island = islands[index]
            if self.island_has_used_rows(values, formulas, start_row, start_col, island):
                return islands[index:]
        return base_window

    def left_target_islands(
        self,
        values: list[list[object]],
        start_row: int,
        start_col: int,
        target_col: int,
    ) -> list[tuple[int, int, int, int]]:
        islands = self.detect_visible_islands(values, start_row, start_col)
        if not islands:
            return []
        candidates = [island for island in islands if island[0] >= target_col]
        if not candidates:
            return []
        left_col = min(island[0] for island in candidates)
        left_islands = [island for island in candidates if island[0] <= left_col + 2]
        return sorted(left_islands, key=lambda item: (item[1], item[0]))

    def find_candidate_row_with_islands(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        title_col: int,
        start_col: int,
        header_row: int,
        footer_row: int,
        island_end_col: int,
        islands: list[tuple[int, int, int, int]],
    ) -> int:
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        search_start = header_index + 1
        for row_index in range(header_index + 1, footer_index):
            if clean(values[row_index][title_index]) in {"総数", "総在庫"}:
                search_start = row_index + 1
        last_used = search_start - 1
        for row_index in range(search_start, footer_index):
            if self.is_candidate_blocked_row(values, start_row, start_row + row_index):
                continue
            if self.is_protected_title_row_in_values(values, start_row, start_row + row_index, title_col, start_col):
                continue
            if any(
                self.has_direct_cell_value(values, formulas, row_index, col_index)
                for col_index in range(title_index, end_index + 1)
            ):
                last_used = row_index
        candidate_index = last_used + 1
        while candidate_index < footer_index and self.is_protected_title_row_in_values(values, start_row, start_row + candidate_index, title_col, start_col):
            candidate_index += 1
        if candidate_index < footer_index:
            return start_row + candidate_index

        lower_islands = [
            island
            for island in islands
            if island[1] > header_row
        ]
        if lower_islands:
            planned_candidate = self.find_candidate_row_before_trailing_planned_rows(
                values,
                formulas,
                start_row,
                title_col,
                start_col,
                header_row,
                footer_row,
                island_end_col,
            )
            if planned_candidate and not any(
                self.island_has_real_shipment_rows(values, formulas, start_row, start_col, island)
                for island in self.representative_lower_islands(lower_islands)
            ):
                return planned_candidate
            next_title_col, next_header_row, next_footer_row, next_end_col = lower_islands[0]
            return self.find_candidate_row_with_islands(
                values,
                formulas,
                start_row,
                next_title_col,
                start_col,
                next_header_row,
                next_footer_row,
                next_end_col,
                islands,
            )
        raise RuntimeError("現在の島は満杯ですが、下の空き島を検出できませんでした。手動で開始セルを選択してください。")

    def find_candidate_row_before_trailing_reserved_row(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        title_col: int,
        start_col: int,
        header_row: int,
        footer_row: int,
        island_end_col: int,
        islands: list[tuple[int, int, int, int]],
    ) -> int:
        if any(island[1] > header_row for island in islands):
            return 0
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        if footer_index - 1 <= header_index:
            return 0
        reserved_start = footer_index - 1
        while reserved_start > header_index:
            row = start_row + reserved_start
            if self.is_candidate_blocked_row(values, start_row, row):
                break
            if self.is_protected_title_row_in_values(values, start_row, row, title_col, start_col):
                break
            has_direct_value = any(
                self.has_direct_cell_value(values, formulas, reserved_start, col_index)
                for col_index in range(title_index, end_index + 1)
            )
            if not has_direct_value:
                break
            reserved_start -= 1
        if reserved_start == footer_index - 1:
            return 0
        blank_end = reserved_start
        blank_start = blank_end
        while blank_start > header_index:
            row = start_row + blank_start
            if self.is_writable_candidate_row(values, formulas, start_row, row, title_col, start_col, island_end_col):
                blank_start -= 1
                continue
            break
        first_blank = blank_start + 1
        if blank_end - first_blank + 1 < 3:
            return 0
        return start_row + first_blank

    def find_candidate_row_before_trailing_planned_rows(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        title_col: int,
        start_col: int,
        header_row: int,
        footer_row: int,
        island_end_col: int,
    ) -> int:
        bounds = self.trailing_planned_blank_bounds(
            values,
            formulas,
            start_row,
            title_col,
            start_col,
            header_row,
            footer_row,
            island_end_col,
        )
        if not bounds:
            return 0
        first_blank_row, _planned_start_row = bounds
        return first_blank_row

    def representative_lower_islands(
        self,
        islands: list[tuple[int, int, int, int]],
    ) -> list[tuple[int, int, int, int]]:
        representatives: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for island in islands:
            title_col, header_row, footer_row, _island_end_col = island
            key = (title_col, footer_row)
            if key not in representatives or header_row > representatives[key][1]:
                representatives[key] = island
        return sorted(representatives.values(), key=lambda item: (item[1], item[0]))

    def island_has_real_shipment_rows(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
        island: tuple[int, int, int, int],
    ) -> bool:
        title_col, header_row, footer_row, island_end_col = island
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        search_start = header_index + 1
        for row_index in range(header_index + 1, footer_index):
            if clean(values[row_index][title_index]) in {"総数", "総在庫"}:
                search_start = row_index + 1
        bounds = self.trailing_planned_blank_bounds(
            values,
            formulas,
            start_row,
            title_col,
            start_col,
            header_row,
            footer_row,
            island_end_col,
        )
        planned_start_index = (bounds[1] - start_row) if bounds else footer_index
        for row_index in range(search_start, min(footer_index, planned_start_index)):
            if self.is_candidate_blocked_row(values, start_row, start_row + row_index):
                continue
            if self.is_protected_title_row_in_values(values, start_row, start_row + row_index, title_col, start_col):
                continue
            if any(
                self.has_direct_cell_value(values, formulas, row_index, col_index)
                for col_index in range(title_index, end_index + 1)
            ):
                return True
        return False

    def trailing_planned_blank_bounds(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        title_col: int,
        start_col: int,
        header_row: int,
        footer_row: int,
        island_end_col: int,
    ) -> tuple[int, int] | None:
        title_index = title_col - start_col
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        if footer_index - 1 <= header_index:
            return None
        planned_start_index = 0
        row_index = footer_index - 1
        while row_index > header_index:
            row = start_row + row_index
            if self.is_candidate_blocked_row(values, start_row, row):
                break
            if self.is_protected_title_row_in_values(values, start_row, row, title_col, start_col):
                break
            if not clean(values[row_index][title_index]):
                break
            planned_start_index = row_index
            row_index -= 1
        if not planned_start_index:
            return None
        blank_end = planned_start_index - 1
        if blank_end <= header_index:
            return None
        if not self.is_writable_candidate_row(values, formulas, start_row, start_row + blank_end, title_col, start_col, island_end_col):
            return None
        blank_start = blank_end
        while blank_start > header_index:
            row = start_row + blank_start
            if self.is_writable_candidate_row(values, formulas, start_row, row, title_col, start_col, island_end_col):
                blank_start -= 1
                continue
            break
        return start_row + blank_start + 1, start_row + planned_start_index

    def auto_detect_and_save_copy_rule(self, task: TaskView, candidate: WriteCandidate) -> None:
        product_tasks = self.display_tasks_for_product(task)
        if not product_tasks or not candidate.island:
            return
        rule = self.infer_copy_rule_from_candidate(candidate, product_tasks)
        if not rule:
            self.set_progress_text(f"{self.index + 1} / {len(self.tasks)}    状態: 候補セル確定済み・転記待ち（転記ルール自動取得なし）")
            return
        title = self.copy_title_var.get().strip() or self.db.get_setting("default_copy_title", "ネット")
        title_tabs, color_gap_tabs, tail_tabs, append_date, transfer_pattern = rule
        self.loading_copy_settings = True
        try:
            self.copy_title_var.set(title)
            self.title_tabs_var.set(str(title_tabs))
            self.color_gap_tabs_var.set(str(color_gap_tabs))
            self.tail_tabs_var.set(str(tail_tabs))
            self.append_date_var.set(append_date)
            self.transfer_pattern_var.set(transfer_pattern)
        finally:
            self.loading_copy_settings = False
        self.save_current_transfer_page(task)
        self.loaded_copy_settings_product = task.product_code
        self.update_transfer_pattern_preview()
        self.set_progress_text(
            f"{self.index + 1} / {len(self.tasks)}    状態: 候補セル確定済み・転記待ち / 転記ルール自動取得 "
            f"タイトル後{title_tabs} / カラー間{color_gap_tabs} / 末尾{tail_tabs}"
        )

    def infer_copy_rule_from_candidate(
        self,
        candidate: WriteCandidate,
        product_tasks: list[TaskView],
    ) -> tuple[int, int, int, bool, str] | None:
        if not candidate.island:
            return None
        title_col, header_row, footer_row, island_end_col = candidate.island
        row_index = candidate.row - candidate.start_row
        title_index = title_col - candidate.start_col
        end_index = island_end_col - candidate.start_col
        if row_index < 0 or row_index >= len(candidate.values):
            return None
        search_start_index = header_row - candidate.start_row + 1
        footer_index = footer_row - candidate.start_row
        for scan_index in range(search_start_index, max(search_start_index, footer_index)):
            if clean(candidate.values[scan_index][title_index]) in {"総数", "総在庫"}:
                search_start_index = scan_index + 1

        date_col = self.detect_date_column_for_rule(candidate, search_start_index, row_index, title_index + 1, end_index)
        quantity_end_index = (date_col - candidate.start_col - 1) if date_col else end_index
        if quantity_end_index < title_index + 1:
            return None

        writable_indexes = [
            col_index
            for col_index in range(title_index + 1, quantity_end_index + 1)
            if self.is_writable_quantity_column(candidate, row_index, col_index, header_row)
        ]
        expected_counts = [len(item.quantities) for item in product_tasks]
        expected_total = sum(expected_counts)
        if not writable_indexes:
            return None
        if expected_total > 0:
            writable_indexes = writable_indexes[: min(expected_total, len(writable_indexes))]
        transfer_pattern = self.build_transfer_pattern_from_columns(
            candidate,
            title_index,
            quantity_end_index,
            writable_indexes,
            date_col - candidate.start_col if date_col else None,
        )

        groups: list[list[int]] = []
        position = 0
        for count in expected_counts:
            group = writable_indexes[position : position + count]
            if len(group) != count:
                title_tabs = max(0, writable_indexes[0] - title_index - 1)
                tail_base_index = (date_col - candidate.start_col) if date_col else quantity_end_index + 1
                tail_tabs = max(0, tail_base_index - writable_indexes[-1] - 1)
                return title_tabs, 0, tail_tabs, bool(date_col), transfer_pattern
            groups.append(group)
            position += count
        if not groups or not groups[0]:
            title_tabs = max(0, writable_indexes[0] - title_index - 1)
            tail_base_index = (date_col - candidate.start_col) if date_col else quantity_end_index + 1
            tail_tabs = max(0, tail_base_index - writable_indexes[-1] - 1)
            return title_tabs, 0, tail_tabs, bool(date_col), transfer_pattern

        title_tabs = groups[0][0] - title_index - 1
        gaps = [
            groups[index][0] - groups[index - 1][-1] - 1
            for index in range(1, len(groups))
            if groups[index] and groups[index - 1]
        ]
        color_gap_tabs = gaps[0] if gaps else 0
        if any(gap != color_gap_tabs for gap in gaps):
            color_gap_tabs = 0

        date_index = date_col - candidate.start_col if date_col else None
        tail_base_index = date_index if date_index is not None else quantity_end_index + 1
        tail_tabs = max(0, tail_base_index - groups[-1][-1] - 1)
        return max(0, title_tabs), max(0, color_gap_tabs), tail_tabs, bool(date_col), transfer_pattern

    def build_transfer_pattern_from_columns(
        self,
        candidate: WriteCandidate,
        title_index: int,
        quantity_end_index: int,
        writable_indexes: list[int],
        date_index: int | None,
    ) -> str:
        writable_map = {col_index: str(position + 1) for position, col_index in enumerate(writable_indexes)}
        tokens = ["title"]
        end_index = date_index if date_index is not None else quantity_end_index
        for col_index in range(title_index + 1, end_index + 1):
            if date_index is not None and col_index == date_index:
                tokens.append("d")
            elif col_index in writable_map:
                tokens.append(writable_map[col_index])
            else:
                tokens.append("t")
        return ",".join(compress_transfer_pattern_tokens(tokens))

    def detect_date_column_for_rule(
        self,
        candidate: WriteCandidate,
        search_start_index: int,
        candidate_row_index: int,
        from_index: int,
        to_index: int,
    ) -> int | None:
        best_col_index = None
        best_count = 0
        for col_index in range(from_index, to_index + 1):
            if self.is_formula_cell(candidate.formulas, candidate_row_index, col_index):
                continue
            count = 0
            for row_index in range(search_start_index, candidate_row_index):
                if self.is_formula_cell(candidate.formulas, row_index, col_index):
                    continue
                if self.looks_like_excel_date(candidate.values[row_index][col_index]):
                    count += 1
            if count > best_count:
                best_count = count
                best_col_index = col_index
        if best_col_index is None or best_count == 0:
            return None
        return candidate.start_col + best_col_index

    def is_writable_quantity_column(
        self,
        candidate: WriteCandidate,
        row_index: int,
        col_index: int,
        header_row: int,
    ) -> bool:
        if self.is_formula_cell(candidate.formulas, row_index, col_index):
            return False
        header_start = max(0, header_row - candidate.start_row - 2)
        header_end = min(len(candidate.values) - 1, header_row - candidate.start_row + 2)
        for header_index in range(header_start, header_end + 1):
            label = clean(candidate.values[header_index][col_index])
            if label in {"計", "合計", "総数", "総在庫", "出荷数", "残数"}:
                return False
        return True

    def is_formula_cell(self, formulas: list[list[object]], row_index: int, col_index: int) -> bool:
        if row_index < 0 or row_index >= len(formulas):
            return False
        if col_index < 0 or col_index >= len(formulas[row_index]):
            return False
        return clean(formulas[row_index][col_index]).startswith("=")

    def looks_like_excel_date(self, value: object) -> bool:
        if isinstance(value, datetime):
            return True
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return 30000 <= number <= 60000

    def range_values_and_formulas(
        self,
        worksheet,
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
    ) -> tuple[list[list[object]], list[list[object]]]:
        row_count = max(1, end_row - start_row + 1)
        col_count = max(1, end_col - start_col + 1)
        excel_range = worksheet.Range(worksheet.Cells(start_row, start_col), worksheet.Cells(end_row, end_col))
        values = self.normalized_used_range_values(excel_range.Value, row_count, col_count)
        formulas = self.normalized_used_range_values(excel_range.Formula, row_count, col_count)
        return values, formulas

    def range_values(self, worksheet, start_row: int, start_col: int, end_row: int, end_col: int) -> list[list[object]]:
        row_count = max(1, end_row - start_row + 1)
        col_count = max(1, end_col - start_col + 1)
        raw_values = worksheet.Range(worksheet.Cells(start_row, start_col), worksheet.Cells(end_row, end_col)).Value
        return self.normalized_used_range_values(raw_values, row_count, col_count)

    def select_current_island(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
    ) -> tuple[int, int, int, int] | None:
        islands = self.detect_visible_islands(values, start_row, start_col)
        if not islands:
            return None
        used_islands = [island for island in islands if self.island_has_used_rows(values, formulas, start_row, start_col, island)]
        if used_islands:
            # The lowest used island is the current island. Upper islands are never reused.
            return max(used_islands, key=lambda item: (item[1], -item[0]))
        return min(islands, key=lambda item: (item[1], item[0]))

    def detect_visible_islands(
        self,
        values: list[list[object]],
        start_row: int,
        start_col: int,
    ) -> list[tuple[int, int, int, int]]:
        islands: list[tuple[int, int, int, int]] = []
        islands.extend(self.detect_total_based_islands(values, start_row, start_col))
        for row_index, row_values in enumerate(values):
            label_cols = [
                start_col + col_index
                for col_index, value in enumerate(row_values)
                if clean(value) in {"カラー", "サイズ"}
            ]
            for title_col in label_cols:
                header_row = start_row + row_index
                footer_row = self.find_footer_row(values, start_row, row_index + 1, title_col, start_col)
                if footer_row:
                    island_end_col = self.detect_island_end_col(row_values, start_col, title_col)
                    islands.append((title_col, header_row, footer_row, island_end_col))
        # If multiple labels are found for the same vertical island, keep the leftmost one.
        unique: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for island in islands:
            _title_col, header_row, footer_row, _end_col = island
            key = (header_row, footer_row)
            if key not in unique or island[0] < unique[key][0]:
                unique[key] = island
        return list(unique.values())

    def detect_total_based_islands(
        self,
        values: list[list[object]],
        start_row: int,
        start_col: int,
    ) -> list[tuple[int, int, int, int]]:
        islands: list[tuple[int, int, int, int]] = []
        for row_index, row_values in enumerate(values):
            total_indexes = [
                col_index
                for col_index, value in enumerate(row_values)
                if clean(value) in {"総数", "総在庫"}
            ]
            if not total_indexes:
                continue
            for position, total_index in enumerate(total_indexes):
                footer_row = self.find_footer_row(values, start_row, row_index + 1, start_col + total_index, start_col)
                if not footer_row:
                    continue
                if position + 1 < len(total_indexes):
                    end_col = start_col + total_indexes[position + 1] - 1
                else:
                    end_col = self.detect_total_based_island_end_col(values, row_index, total_index, start_col)
                islands.append((start_col + total_index, start_row + row_index, footer_row, end_col))
        return islands

    def detect_total_based_island_end_col(
        self,
        values: list[list[object]],
        total_row_index: int,
        total_index: int,
        start_col: int,
    ) -> int:
        end_index = total_index
        for col_index in range(total_index + 1, len(values[total_row_index])):
            has_any_value = False
            for row_index in range(max(0, total_row_index - 8), min(len(values), total_row_index + 4)):
                if clean(values[row_index][col_index]):
                    has_any_value = True
                    break
            if has_any_value:
                end_index = col_index
        return start_col + end_index

    def detect_island_end_col(self, row_values: list[object], start_col: int, title_col: int) -> int:
        title_index = title_col - start_col
        for col_index in range(title_index + 1, len(row_values)):
            if clean(row_values[col_index]) in {"カラー", "サイズ"}:
                return start_col + col_index - 1
        return start_col + len(row_values) - 1

    def island_has_used_rows(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
        island: tuple[int, int, int, int],
    ) -> bool:
        title_col, header_row, footer_row, island_end_col = island
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        search_start = header_index + 1
        for row_index in range(header_index + 1, footer_index):
            if clean(values[row_index][title_index]) in {"総数", "総在庫"}:
                search_start = row_index + 1
        for row_index in range(search_start, footer_index):
            if self.is_candidate_blocked_row(values, start_row, start_row + row_index):
                continue
            if self.is_protected_title_row_in_values(values, start_row, start_row + row_index, title_col, start_col):
                continue
            if any(
                self.has_direct_cell_value(values, formulas, row_index, col_index)
                for col_index in range(title_index, end_index + 1)
            ):
                return True
        return False

    def island_has_protected_title_rows(
        self,
        values: list[list[object]],
        start_row: int,
        start_col: int,
        island: tuple[int, int, int, int],
    ) -> bool:
        title_col, header_row, footer_row, _island_end_col = island
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        title_index = title_col - start_col
        search_start = header_index + 1
        for row_index in range(header_index + 1, footer_index):
            if clean(values[row_index][title_index]) in {"総数", "総在庫"}:
                search_start = row_index + 1
        for row_index in range(search_start, footer_index):
            if self.is_protected_title_row_in_values(values, start_row, start_row + row_index, title_col, start_col):
                return True
        return False

    def find_footer_row(
        self,
        values: list[list[object]],
        start_row: int,
        from_index: int,
        title_col: int,
        start_col: int,
    ) -> int:
        title_index = title_col - start_col
        for row_index in range(from_index, len(values)):
            label = clean(values[row_index][title_index])
            if label == "出荷数":
                return start_row + row_index
        return 0

    def find_candidate_row(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        title_col: int,
        start_col: int,
        header_row: int,
        footer_row: int,
        island_end_col: int,
    ) -> int:
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        header_index = header_row - start_row
        footer_index = footer_row - start_row
        search_start = header_index + 1
        for row_index in range(header_index + 1, footer_index):
            if clean(values[row_index][title_index]) in {"総数", "総在庫"}:
                search_start = row_index + 1
        last_used = search_start - 1
        for row_index in range(search_start, footer_index):
            if self.is_candidate_blocked_row(values, start_row, start_row + row_index):
                continue
            if self.is_protected_title_row_in_values(values, start_row, start_row + row_index, title_col, start_col):
                continue
            if any(
                self.has_direct_cell_value(values, formulas, row_index, col_index)
                for col_index in range(title_index, end_index + 1)
            ):
                last_used = row_index
        candidate_index = last_used + 1
        while candidate_index < footer_index and self.is_protected_title_row_in_values(values, start_row, start_row + candidate_index, title_col, start_col):
            candidate_index += 1
        if candidate_index >= footer_index:
            next_island = self.next_lower_island(values, formulas, start_row, start_col, header_row)
            if next_island:
                next_title_col, next_header_row, next_footer_row, next_end_col = next_island
                return self.find_candidate_row(values, formulas, start_row, next_title_col, start_col, next_header_row, next_footer_row, next_end_col)
            raise RuntimeError("現在の島は満杯ですが、下の空き島を検出できませんでした。手動で開始セルを選択してください。")
        return start_row + candidate_index

    def next_lower_island(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
        current_header_row: int,
    ) -> tuple[int, int, int, int] | None:
        lower_islands = [
            island
            for island in self.detect_visible_islands(values, start_row, start_col)
            if island[1] > current_header_row
        ]
        if not lower_islands:
            return None
        return min(lower_islands, key=lambda item: (item[1], item[0]))

    def detect_candidate_from_totals(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        start_col: int,
    ) -> tuple[int, int] | None:
        for row_index, row_values in enumerate(values):
            for col_index, value in enumerate(row_values):
                if clean(value) != "出荷数":
                    continue
                title_col = start_col + col_index
                for candidate_index in range(row_index - 1, -1, -1):
                    if self.is_candidate_blocked_row(values, start_row, start_row + candidate_index):
                        continue
                    if self.is_protected_title_row_in_values(values, start_row, start_row + candidate_index, title_col, start_col):
                        continue
                    if any(
                        self.has_direct_cell_value(values, formulas, candidate_index, candidate_col_index)
                        for candidate_col_index in range(len(values[candidate_index]))
                    ):
                        target_index = candidate_index + 1
                        while target_index < row_index and self.is_protected_title_row_in_values(values, start_row, start_row + target_index, title_col, start_col):
                            target_index += 1
                        return start_row + target_index, title_col
                return start_row + row_index, title_col
        return None

    def has_direct_cell_value(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        row_index: int,
        col_index: int,
    ) -> bool:
        if row_index < 0 or row_index >= len(values):
            return False
        if col_index < 0 or col_index >= len(values[row_index]):
            return False
        value = clean(values[row_index][col_index])
        if not value:
            return False
        formula = ""
        if row_index < len(formulas) and col_index < len(formulas[row_index]):
            formula = clean(formulas[row_index][col_index])
        return not formula.startswith("=")

    def is_writable_candidate_row(
        self,
        values: list[list[object]],
        formulas: list[list[object]],
        start_row: int,
        row: int,
        title_col: int,
        start_col: int,
        island_end_col: int,
    ) -> bool:
        row_index = row - start_row
        title_index = title_col - start_col
        end_index = island_end_col - start_col
        if row_index < 0 or row_index >= len(values):
            return False
        if self.is_candidate_blocked_row(values, start_row, row):
            return False
        if self.is_protected_title_row_in_values(values, start_row, row, title_col, start_col):
            return False
        for col_index in range(max(0, title_index), min(len(values[row_index]) - 1, end_index) + 1):
            if self.has_direct_cell_value(values, formulas, row_index, col_index):
                return False
        return True

    def normalized_used_range_values(self, raw_values: object, row_count: int, col_count: int) -> list[list[object]]:
        if row_count == 1 and col_count == 1:
            return [[raw_values]]
        if row_count == 1:
            return [list(raw_values)]
        if col_count == 1:
            return [[value] for value in raw_values]
        return [list(row) for row in raw_values]

    def is_candidate_blocked_row(self, values: list[list[object]], start_row: int, row: int) -> bool:
        blocked_words = ("カラー", "サイズ", "初回", "総数", "総在庫", "出荷数", "残数", "合計")
        row_index = row - start_row
        if row_index < 0 or row_index >= len(values):
            return False
        for cell_value in values[row_index]:
            value = clean(cell_value)
            if not value:
                continue
            if any(word in value for word in blocked_words):
                return True
        return False

    def is_protected_title_row_in_values(
        self,
        values: list[list[object]],
        start_row: int,
        row: int,
        title_col: int,
        start_col: int,
    ) -> bool:
        row_index = row - start_row
        title_index = title_col - start_col
        if row_index < 0 or row_index >= len(values):
            return False
        if title_index < 0 or title_index >= len(values[row_index]):
            return False
        return self.row_has_protected_title_keyword(values[row_index][title_index])

    def browse_inventory_file(self) -> None:
        task = self.current_task()
        if not task:
            return
        initial_dir = self.db.get_setting("inventory_network_folder", "") or self.db.get_setting("last_inventory_file_dir", "") or str(Path.home())
        path = filedialog.askopenfilename(
            parent=self.window,
            initialdir=initial_dir,
            title="転記先Excelファイルを選択",
            filetypes=[("Excel", "*.xls *.xlsx *.xlsm"), ("All files", "*.*")],
        )
        self.bring_to_front()
        if not path:
            return
        normalized = normalize_windows_path(path)
        self.inventory_file_var.set(normalized)
        self.save_current_transfer_page(task)
        self.db.set_setting("last_inventory_file_dir", str(Path(normalized).parent))

    def bring_to_front(self) -> None:
        self.window.lift()
        self.window.focus_force()
        self.window.attributes("-topmost", True)
        self.window.after(200, lambda: self.window.attributes("-topmost", False))

    def close_transfer_window(self) -> None:
        self.clear_candidate_highlight()
        self.window.destroy()

    def bring_to_front_delayed(self) -> None:
        self.window.after(300, self.bring_to_front)
        self.window.after(1000, self.bring_to_front)

    def bring_excel_to_front(self, excel) -> None:
        try:
            self.window.attributes("-topmost", False)
        except Exception:
            pass
        try:
            excel.Visible = True
            excel.Application.Activate()
        except Exception:
            pass
        try:
            import win32con
            import win32gui

            hwnd = int(excel.Hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        except Exception:
            pass
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            caption = clean(getattr(excel, "Caption", "")) or "Microsoft Excel"
            shell.AppActivate(caption)
        except Exception:
            pass

    def keep_excel_front_for_candidate(self, excel) -> None:
        def activate_excel() -> None:
            try:
                self.window.attributes("-topmost", False)
            except Exception:
                pass
            self.bring_excel_to_front(excel)

        activate_excel()
        try:
            self.window.after(250, activate_excel)
            self.window.after(1100, activate_excel)
        except Exception:
            pass

    def bring_active_excel_to_front(self) -> None:
        try:
            import win32com.client
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception:
            return
        self.bring_excel_to_front(excel)

    def candidate_confirm_mode(self) -> str:
        mode = self.db.get_setting("candidate_confirm_mode", "focus_excel")
        return mode if mode in {"focus_excel", "highlight_cell"} else "focus_excel"

    def clear_candidate_highlight(self) -> None:
        info = self.candidate_highlight
        self.candidate_highlight = None
        if not info:
            return
        try:
            cell = info["cell"]
            cell.Interior.Pattern = info["pattern"]
            cell.Interior.Color = info["color"]
        except Exception:
            pass

    def highlight_candidate_cell(self, worksheet, row: int, col: int) -> None:
        self.clear_candidate_highlight()
        try:
            cell = worksheet.Cells(row, col)
            self.candidate_highlight = {
                "cell": cell,
                "pattern": cell.Interior.Pattern,
                "color": cell.Interior.Color,
            }
            cell.Interior.Color = 15203548  # RGB(220, 252, 231)
        except Exception:
            self.candidate_highlight = None

    def show_candidate_cell_after_select(self, excel, worksheet, row: int, col: int) -> None:
        if self.candidate_confirm_mode() == "highlight_cell":
            self.highlight_candidate_cell(worksheet, row, col)
            self.bring_to_front()
        else:
            self.clear_candidate_highlight()
            self.keep_excel_front_for_candidate(excel)

    def open_inventory_file(self, show_error: bool = True, move_to_candidate: bool = False) -> bool:
        if move_to_candidate:
            task_for_skip = self.current_task()
            if task_for_skip:
                product_tasks_for_skip = self.display_tasks_for_product(task_for_skip)
                if (
                    not self.current_page_has_transfer_quantity(product_tasks_for_skip)
                    and self.advance_to_next_transfer_page_with_quantity(
                        task_for_skip,
                        product_tasks_for_skip,
                        move_to_candidate=True,
                    )
                ):
                    return True
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.inventory_sheet_var.get()
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        task = self.current_task()
        if task and path:
            self.save_current_transfer_page(task)
        if not path:
            if show_error:
                messagebox.showwarning("ファイル未設定", "転記先ファイルを指定してください。", parent=self.window)
                self.bring_to_front()
            return False
        if not os.path.exists(path):
            if show_error:
                messagebox.showerror("ファイルなし", f"転記先ファイルが見つかりません。\n{path}", parent=self.window)
                self.bring_to_front()
            return False
        try:
            workbook, worksheet, excel = self.open_excel_sheet(path, sheet_name, self.excel_start_col_var.get())
            if self.workbook_is_read_only(workbook):
                self.bring_excel_to_front(excel)
                self.close_workbook_without_save(workbook)
                reason = "読み取り専用のため転記できませんでした。後ほど再試行してください。"
                if task:
                    self.mark_read_only_retry_and_move_next(task, path, reason)
                elif show_error:
                    messagebox.showwarning("読み取り専用", f"{reason}\n{path}", parent=self.window)
                    self.bring_to_front()
                return False
            if move_to_candidate and task:
                candidate = self.detect_write_candidate_cell(worksheet, excel, self.excel_start_col_var.get())
                row, col = candidate.row, candidate.col
                row = self.adjust_candidate_after_red_marker(worksheet, row, col, candidate.island)
                product_tasks = self.display_tasks_for_product(task)
                roles = self.transfer_value_roles(product_tasks)
                if self.should_try_title_date_only_add():
                    values = self.build_product_transfer_values_for_quantities(
                        product_tasks,
                        task.product_code,
                        self.flatten_product_quantities(product_tasks),
                        save_settings=False,
                    )
                    add_row = self.find_title_date_add_row_in_candidate_range(worksheet, candidate, values, roles)
                    if add_row:
                        row = add_row
                self.ensure_excel_row_is_writable(worksheet, row, col, roles)
                workbook.Activate()
                worksheet.Activate()
                worksheet.Cells(row, col).Select()
                excel.ActiveWindow.ScrollRow = max(1, row - 8)
                excel.ActiveWindow.ScrollColumn = max(1, col - 3)
                self.save_current_transfer_page(task)
            if move_to_candidate and task:
                self.show_candidate_cell_after_select(excel, worksheet, row, col)
            else:
                self.bring_excel_to_front(excel)
            return True
        except Exception as exc:
            if show_error:
                messagebox.showerror("ファイルを開けません", f"{exc}\n{path}", parent=self.window)
                self.bring_to_front()
            return False

    def open_excel_sheet(self, path: str, sheet_name: str, excel_start_col: str = "A"):
        return self.open_target_workbook(path, sheet_name, excel_start_col)

    def workbook_is_read_only(self, workbook) -> bool:
        try:
            return bool(workbook.ReadOnly)
        except Exception:
            return False

    def close_workbook_without_save(self, workbook) -> None:
        try:
            workbook.Close(SaveChanges=False)
        except Exception:
            pass

    def move_retry_product_to_end(self, product_code: str) -> bool:
        retry_tasks = [item for item in self.tasks if item.product_code == product_code]
        if not retry_tasks:
            return False
        remaining_tasks = [item for item in self.tasks if item.product_code != product_code]
        self.tasks = remaining_tasks + retry_tasks
        if remaining_tasks:
            self.index = min(self.index, len(remaining_tasks) - 1)
            self._skip_done_forward()
            return True
        self.index = 0
        return False

    def mark_read_only_retry_and_move_next(self, task: TaskView, path: str, reason: str) -> None:
        product_tasks = self.display_tasks_for_product(task)
        source_task_ids = self.source_task_ids_for_items(product_tasks)
        for item in product_tasks:
            for task_id in item.source_task_ids or ([item.id] if item.id > 0 else []):
                if task_id > 0:
                    self.db.mark_task_retry_required(task_id, reason)
            item.status = "pending"
            item.retry_required = True
            item.retry_reason = reason
        self.update_local_task_state(source_task_ids, "pending", True, reason)
        messagebox.showwarning(
            "読み取り専用",
            f"{task.product_name}\n\n{reason}\n他の人が在庫表を編集中の可能性があります。\n\n{path}",
            parent=self.window,
        )
        self.pending_excel_product_code = ""
        self.pending_excel_page_id = 0
        if self.move_retry_product_to_end(task.product_code):
            self.render()
        else:
            self.finish_transfer_list()
        self.bring_to_front_delayed()

    def parse_tab_count(self, value: str) -> int:
        try:
            return max(0, int(float(clean(value) or "0")))
        except ValueError:
            return 0

    def copy_today(self) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(self.db.transfer_date_text())

    def open_current_product_settings(self) -> None:
        task = self.current_task()
        if not task:
            messagebox.showwarning("商品なし", "現在表示中の商品がありません。", parent=self.window)
            self.bring_to_front()
            return
        self.save_current_transfer_page(task)
        ProductSettingsWindow(
            self.root,
            self.db,
            self.base_dir,
            initial_product_code=task.product_code,
            on_close=lambda code=task.product_code: self.refresh_after_product_settings(code),
        )

    def refresh_after_product_settings(self, product_code: str) -> None:
        try:
            window_exists = self.window.winfo_exists()
        except Exception:
            return
        if not window_exists:
            return
        task = self.current_task()
        if not task or task.product_code != product_code:
            return
        current_page = self.current_transfer_page()
        current_page_id = int(current_page["id"]) if current_page else 0
        self.loaded_page_product = ""
        self.load_transfer_page_for_task(task)
        if current_page_id:
            for index, page in enumerate(self.transfer_pages):
                if int(page["id"]) == current_page_id:
                    self.transfer_page_index = index
                    self.load_transfer_page_for_task(task)
                    break
        self.load_auto_write_confirmed_for_task(task)
        self.load_min_stock_quantity_for_task(task)
        self.render()
        self.bring_to_front()

    def reload_tasks(self, keep_task_id: int | None = None) -> None:
        task_rows = list(self.db.task_rows())
        if self.ordered_task_ids is None:
            ordered_rows = task_rows
        else:
            row_by_id = {int(row["id"]): row for row in task_rows}
            ordered_rows = [row_by_id[task_id] for task_id in self.ordered_task_ids if task_id in row_by_id]
        self.tasks = [self._row_to_task(row) for row in ordered_rows]
        self.index = self._index_for_task(keep_task_id)
        self._skip_done_forward()
        self.render()

    def open_color_order_options(self) -> None:
        task = self.current_task()
        if not task:
            return
        original_task_id = task.id
        window = Toplevel(self.window)
        window.title("カラー順変更")
        window.geometry("360x360")
        Label(window, text=task.product_name, anchor=W).pack(fill=X, padx=10, pady=(10, 4))
        color_list = Listbox(window, height=10)
        color_list.pack(fill=BOTH, expand=True, padx=10, pady=6)

        def load_colors(select_color: str | None = None) -> None:
            color_list.delete(0, END)
            product_tasks = self.display_tasks_for_product(task)
            for item in product_tasks:
                color_list.insert(END, item.color)
            if select_color:
                for i in range(color_list.size()):
                    if color_list.get(i) == select_color:
                        color_list.selection_set(i)
                        color_list.see(i)
                        break

        def move(direction: int) -> None:
            selected = color_list.curselection()
            if not selected:
                return
            index = selected[0]
            target_index = index + direction
            if target_index < 0 or target_index >= color_list.size():
                return
            colors = [color_list.get(i) for i in range(color_list.size())]
            colors[index], colors[target_index] = colors[target_index], colors[index]
            color_list.delete(0, END)
            for color in colors:
                color_list.insert(END, color)
            color_list.selection_clear(0, END)
            color_list.selection_set(target_index)
            color_list.see(target_index)

        def save_and_close() -> None:
            colors = [color_list.get(i) for i in range(color_list.size())]
            self.db.save_product_color_order(task.product_code, colors)
            self.reload_tasks(keep_task_id=original_task_id)
            window.destroy()

        buttons = Frame(window)
        buttons.pack(fill=X, padx=10, pady=(0, 10))
        Button(buttons, text="上へ", command=lambda: move(-1), width=10).pack(side=LEFT, padx=(0, 6))
        Button(buttons, text="下へ", command=lambda: move(1), width=10).pack(side=LEFT, padx=6)
        Button(buttons, text="保存して閉じる", command=save_and_close, width=12).pack(side=RIGHT)
        load_colors(task.color)

    def _move_to_next_product(self, product_code: str) -> None:
        next_index = None
        for i in range(self.index + 1, len(self.tasks)):
            if self.tasks[i].product_code != product_code:
                if self.auto_skip_done and self.tasks[i].status in {"copied", "skipped"}:
                    continue
                next_index = i
                break
        if next_index is None:
            self.finish_transfer_list()
            return
        else:
            self.index = next_index
        self._skip_done_forward()
        if self.auto_skip_done and self.current_task() and self.current_task().status in {"copied", "skipped"}:
            self.finish_transfer_list()
            return
        self.render()

    def next_task(self) -> None:
        if self.index < len(self.tasks) - 1:
            self.index += 1
        else:
            task = self.current_task()
            if task and task.status in {"copied", "skipped"}:
                self.finish_transfer_list()
                return
        self._skip_done_forward()
        if self.auto_skip_done and self.current_task() and self.current_task().status in {"copied", "skipped"}:
            self.finish_transfer_list()
            return
        self.render()

    def browse_next_task(self) -> None:
        self.transfer_finished = False
        if self.index < len(self.tasks) - 1:
            self.index += 1
        self.render()

    def browse_prev_task(self) -> None:
        self.transfer_finished = False
        if self.index > 0:
            self.index -= 1
        self.render()

    def _skip_done_forward(self) -> None:
        if not self.auto_skip_done:
            return
        while self.index < len(self.tasks) - 1 and self.tasks[self.index].status in {"copied", "skipped"}:
            self.index += 1

    def prev_task(self) -> None:
        if self.index > 0:
            self.index -= 1
            task = self.current_task()
            if task:
                self.db.mark_task(task.id, "pending")
                task.status = "pending"
                task.retry_required = False
                task.retry_reason = ""
        self.render()

    def skip_task(self) -> None:
        if self.transfer_finished:
            messagebox.showinfo("転記リスト完了", "表示中のリストは最後まで処理済みです。", parent=self.window)
            self.bring_to_front()
            return
        task = self.current_task()
        if task:
            self.db.mark_task(task.id, "skipped")
            task.status = "skipped"
            task.retry_required = False
            task.retry_reason = ""
        self.next_task()

    def finish_transfer_list(self) -> None:
        self.transfer_finished = True
        self.pending_excel_product_code = ""
        self.pending_excel_page_id = 0
        if self.on_task_change:
            try:
                self.on_task_change(0)
            except Exception:
                pass
        self.render()
        if not self.end_notice_shown:
            self.end_notice_shown = True
            self.window.after(100, self.show_transfer_finished_notice)

    def show_transfer_finished_notice(self) -> None:
        if not self.window.winfo_exists():
            return
        dialog = Toplevel(self.window)
        dialog.title("転記リスト完了")
        dialog.transient(self.window)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        Label(
            dialog,
            text="表示中の転記リストは最後まで処理しました。",
            padx=22,
            pady=16,
            justify=LEFT,
        ).pack(fill=BOTH)
        Button(dialog, text="OK", command=dialog.destroy, width=10).pack(pady=(0, 14))
        dialog.update_idletasks()
        x = self.window.winfo_rootx() + max(40, (self.window.winfo_width() - dialog.winfo_width()) // 2)
        y = self.window.winfo_rooty() + max(40, (self.window.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        dialog.lift()
        dialog.focus_force()
        dialog.wait_window()
        if self.window.winfo_exists():
            self.bring_to_front()


class ProductSettingsWindow:
    def __init__(self, root: Tk, db: AppDB, base_dir: Path, initial_product_code: str = "", on_close=None) -> None:
        self.db = db
        self.base_dir = base_dir
        self.initial_product_code = initial_product_code
        self.on_close = on_close
        self.window = Toplevel(root)
        self.window.title("商品設定")
        self.window.geometry("1120x790")
        self.products: list[sqlite3.Row] = []
        self.current_product_code = ""
        self.current_variant_code = ""
        self.product_mode = "single"
        self.product_setting_filter = "all"
        self.loading_product = False
        self.photo = None

        self.search_var = StringVar()
        self.product_code_var = StringVar()
        self.display_name_var = StringVar()
        self.rakuten_code_var = StringVar()
        self.jan_code_var = StringVar()
        self.product_url_var = StringVar()
        self.inventory_file_var = StringVar()
        self.sheet_name_var = StringVar()
        self.excel_start_col_var = StringVar(value="A")
        self.thumbnail_url_var = StringVar()
        self.quantity_multiplier_var = StringVar(value="1")
        self.min_stock_quantity_var = StringVar(value="3")
        self.auto_write_confirmed_var = BooleanVar(value=False)
        self.manual_input_var = BooleanVar(value=False)
        self.bulk_min_stock_quantity_var = StringVar(value="3")
        self.variant_code_var = StringVar()
        self.variant_color_var = StringVar()
        self.variant_size_var = StringVar()
        self.variant_jan_code_var = StringVar()
        self.variant_sold_out_var = BooleanVar(value=False)
        self.variant_color_order_var = StringVar()
        self.variant_size_order_var = StringVar()
        self.set_notice_var = StringVar()
        self.copy_title_var = StringVar()
        self.title_tabs_var = StringVar(value="0")
        self.color_gap_tabs_var = StringVar(value="0")
        self.tail_tabs_var = StringVar(value="0")
        self.append_date_var = BooleanVar(value=True)
        self.transfer_pattern_var = StringVar()
        self.transfer_pattern_preview_var = StringVar()
        self.title_date_add_only_var = BooleanVar(value=False)
        self.transfer_page_select_var = StringVar()
        self.transfer_page_name_var = StringVar(value="ページ1")
        self.transfer_pages: list[sqlite3.Row] = []
        self.current_transfer_page_id = 0
        self.loading_transfer_page = False
        self.image_status_var = StringVar(value="商品を選択してください")
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        self._build_ui()
        if self.initial_product_code:
            row = self.db.conn.execute("SELECT is_set FROM products WHERE product_code = ?", (self.initial_product_code,)).fetchone()
            if row and int(row["is_set"]):
                self.product_mode = "set"
        self.update_product_mode_buttons()
        self.refresh_products()
        if self.initial_product_code:
            self.select_product(self.initial_product_code)

    def _build_ui(self) -> None:
        body = Frame(self.window)
        body.pack(fill=BOTH, expand=True, padx=10, pady=10)

        left = ttk.LabelFrame(body, text="商品一覧")
        left.pack(side=LEFT, fill=BOTH, padx=(0, 10))
        mode_row = Frame(left)
        mode_row.pack(fill=X, padx=8, pady=(8, 4))
        self.single_mode_button = Button(mode_row, text="単品商品", command=lambda: self.set_product_mode("single"), relief="sunken")
        self.single_mode_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        self.set_mode_button = Button(mode_row, text="セット商品", command=lambda: self.set_product_mode("set"), relief="raised")
        self.set_mode_button.pack(side=LEFT, fill=X, expand=True, padx=(4, 0))

        search_row = Frame(left)
        search_row.pack(fill=X, padx=8, pady=(0, 6))
        Label(search_row, text="検索:").pack(side=LEFT)
        Entry(search_row, textvariable=self.search_var, width=24).pack(side=LEFT, fill=X, expand=True, padx=(4, 6))
        Button(search_row, text="検索", command=self.refresh_products, width=8).pack(side=LEFT, padx=(0, 4))
        Button(search_row, text="クリア", command=self.clear_product_search, width=8).pack(side=LEFT)
        bulk_row = Frame(left)
        bulk_row.pack(fill=X, padx=8, pady=(0, 6))
        Button(bulk_row, text="選択", command=self.select_visible_products, width=6).pack(side=LEFT, padx=(0, 4))
        Button(bulk_row, text="解除", command=self.clear_visible_product_selection, width=6).pack(side=LEFT, padx=(0, 8))
        Label(bulk_row, text="最低在庫").pack(side=LEFT)
        Entry(bulk_row, textvariable=self.bulk_min_stock_quantity_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(4, 6))
        Button(bulk_row, text="選択商品へ一括設定", command=self.bulk_set_min_stock_quantity, width=18).pack(side=LEFT)
        self.product_setting_filter_button = Button(bulk_row, text="全商品", command=self.toggle_product_setting_filter, width=8)
        self.product_setting_filter_button.pack(side=LEFT, padx=(6, 0))
        Button(bulk_row, text="更新", command=self.refresh_products, width=6).pack(side=LEFT, padx=(4, 0))

        columns = ("code", "name")
        product_tree_frame = Frame(left)
        product_tree_frame.pack(fill=BOTH, expand=True)
        self.product_tree = ttk.Treeview(product_tree_frame, columns=columns, show="headings", height=24, selectmode="extended")
        product_scroll = Scrollbar(product_tree_frame, orient="vertical", command=self.product_tree.yview)
        self.product_tree.configure(yscrollcommand=product_scroll.set)
        for col, text, width in [
            ("code", "商品コード", 115),
            ("name", "商品名", 365),
        ]:
            self.product_tree.heading(col, text=text)
            self.product_tree.column(col, width=width, anchor=W)
        self.product_tree.pack(side=LEFT, fill=BOTH, expand=True)
        product_scroll.pack(side=RIGHT, fill=Y)
        self.product_tree.bind("<<TreeviewSelect>>", self.on_product_selected)

        notebook = ttk.Notebook(body)
        notebook.pack(side=LEFT, fill=BOTH, expand=True)
        self.detail_notebook = notebook

        basic_tab = Frame(notebook)
        variant_tab = Frame(notebook)
        set_tab = Frame(notebook)
        self.basic_tab = basic_tab
        self.variant_tab = variant_tab
        self.set_tab = set_tab
        notebook.add(basic_tab, text="商品基本情報")
        notebook.add(variant_tab, text="子SKU・並び順")
        notebook.add(set_tab, text="セット構成")

        basic_left = ttk.LabelFrame(basic_tab, text="商品情報")
        basic_left.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)
        basic_top = Frame(basic_left)
        basic_top.pack(fill=X, padx=8, pady=8)
        form = Frame(basic_top)
        form.pack(side=LEFT, fill=X, expand=True)
        self._form_row(form, "商品コード", self.product_code_var, 0, readonly=True, width=44)
        self._form_row(form, "商品名", self.display_name_var, 1, width=44)
        self._form_row(form, "楽天URLコード", self.rakuten_code_var, 2, width=44)
        self._form_row(form, "商品URL", self.product_url_var, 3, width=44)
        self._form_row(form, "JANコード", self.jan_code_var, 4, width=44)
        Label(form, text="最低在庫数", width=14, anchor=W).grid(row=5, column=0, sticky=W, pady=3)
        Entry(form, textvariable=self.min_stock_quantity_var, width=12, justify=RIGHT).grid(row=5, column=1, sticky=W, pady=3)
        ttk.Checkbutton(form, text="手動入力対象", variable=self.manual_input_var).grid(row=6, column=1, sticky=W, pady=3)

        image_panel = Frame(basic_top)
        image_panel.pack(side=LEFT, padx=(10, 0), pady=2)
        image_preview = Frame(image_panel, width=150, height=150, relief="solid", bd=1, bg="#FFFFFF")
        image_preview.pack()
        image_preview.pack_propagate(False)
        self.image_label = Label(image_preview, textvariable=self.image_status_var, bg="#FFFFFF", anchor=CENTER, justify=CENTER, wraplength=130)
        self.image_label.pack(fill=BOTH, expand=True)
        Button(image_panel, text="楽天ページを開く", command=self.open_product_url, width=16).pack(fill=X, pady=(6, 0))

        inventory_group = ttk.LabelFrame(basic_left, text="在庫Excelリンク")
        inventory_group.pack(fill=X, padx=8, pady=(6, 8))
        self.inventory_group = inventory_group
        Label(inventory_group, text="転記ページ", width=14, anchor=W).grid(row=0, column=0, sticky=W, pady=3)
        self.transfer_page_combo = ttk.Combobox(inventory_group, textvariable=self.transfer_page_select_var, width=24, state="readonly")
        self.transfer_page_combo.grid(row=0, column=1, sticky=W, pady=3)
        self.transfer_page_combo.bind("<<ComboboxSelected>>", self.on_transfer_page_selected)
        Button(inventory_group, text="追加", command=self.add_transfer_page, width=6).grid(row=0, column=2, padx=2, sticky=W)
        Button(inventory_group, text="複製", command=self.duplicate_transfer_page, width=6).grid(row=0, column=3, padx=2, sticky=W)
        Button(inventory_group, text="削除", command=self.delete_transfer_page, width=6).grid(row=0, column=4, padx=2, sticky=W)
        self._form_row(inventory_group, "ページ名", self.transfer_page_name_var, 1, width=48)
        self._form_row(inventory_group, "在庫Excel", self.inventory_file_var, 2, width=48)
        Button(inventory_group, text="参照", command=self.choose_inventory_file, width=6).grid(row=2, column=2, padx=2, sticky=W)
        Button(inventory_group, text="開く", command=self.open_inventory_file, width=6).grid(row=2, column=3, padx=2, sticky=W)
        self._form_row(inventory_group, "シート名", self.sheet_name_var, 3, width=48)
        self._form_row(inventory_group, "開始列", self.excel_start_col_var, 4, width=12)
        Button(inventory_group, text="候補セル", command=self.open_transfer_candidate_cell, width=8).grid(row=4, column=2, padx=2, sticky=W)
        Button(inventory_group, text="記入欄増設", command=self.extend_inventory_island_from_settings, width=10, bg="#E0F2FE", activebackground="#BAE6FD").grid(row=4, column=3, padx=2, sticky=W)
        Label(inventory_group, text="記入数量倍率", width=14, anchor=W).grid(row=5, column=0, sticky=W, pady=3)
        Entry(inventory_group, textvariable=self.quantity_multiplier_var, width=12, justify=RIGHT).grid(row=5, column=1, sticky=W, pady=3)
        Label(inventory_group, text="自動OK", width=14, anchor=W).grid(row=6, column=0, sticky=W, pady=3)
        self.auto_write_button = Button(inventory_group, text="自動OK 未確認", command=self.toggle_auto_write_confirmed, width=16)
        self.auto_write_button.grid(row=6, column=1, sticky=W, pady=3)
        rule_group = ttk.LabelFrame(basic_left, text="Excel転記ルール")
        rule_group.pack(fill=BOTH, expand=True, padx=8, pady=(6, 8))
        self.rule_group = rule_group
        rule_row1 = Frame(rule_group)
        rule_row1.pack(fill=X, padx=8, pady=(8, 3))
        Label(rule_row1, text="タイトル").pack(side=LEFT, padx=(0, 4))
        Entry(rule_row1, textvariable=self.copy_title_var, width=14).pack(side=LEFT, padx=(0, 8))
        Label(rule_row1, text="タイトル後Tab").pack(side=LEFT, padx=(0, 4))
        Entry(rule_row1, textvariable=self.title_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(0, 8))
        Label(rule_row1, text="カラー間Tab").pack(side=LEFT, padx=(0, 4))
        Entry(rule_row1, textvariable=self.color_gap_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(0, 8))
        Label(rule_row1, text="末尾Tab").pack(side=LEFT, padx=(0, 4))
        Entry(rule_row1, textvariable=self.tail_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(0, 8))
        ttk.Checkbutton(rule_row1, text="日付追加", variable=self.append_date_var).pack(side=LEFT)
        helper_row = Frame(rule_group)
        helper_row.pack(fill=X, padx=8, pady=(0, 3))
        for token in ["t,"] + [f"{number}," for number in range(10)]:
            Button(
                helper_row,
                text=token,
                command=lambda value=token: self.insert_transfer_pattern_text(value),
                width=3,
            ).pack(side=LEFT, padx=(0, 2))
        Button(helper_row, text="削除", command=self.delete_transfer_pattern_token_before_cursor, width=5).pack(side=LEFT, padx=(4, 0))
        rule_row2 = Frame(rule_group)
        rule_row2.pack(fill=X, padx=8, pady=(0, 3))
        Label(rule_row2, text="転記パターン").pack(side=LEFT, padx=(0, 4))
        self.transfer_pattern_entry = Entry(rule_row2, textvariable=self.transfer_pattern_var, width=42)
        self.transfer_pattern_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        Button(rule_row2, text="取得", command=self.auto_detect_transfer_pattern, width=7, bg="#FED7AA", activebackground="#FDBA74").pack(side=LEFT, padx=(0, 6))
        Button(rule_row2, text="確認", command=self.update_transfer_pattern_preview, width=7).pack(side=LEFT)
        preview_frame = Frame(rule_group)
        preview_frame.pack(fill=X, padx=8, pady=(0, 8))
        self.transfer_pattern_preview_text = Text(preview_frame, height=4, wrap="word", bg="#FFFFFF", fg="#374151", relief="solid", bd=1)
        preview_scroll = Scrollbar(preview_frame, orient="vertical", command=self.transfer_pattern_preview_text.yview)
        self.transfer_pattern_preview_text.configure(yscrollcommand=preview_scroll.set, state="disabled")
        self.transfer_pattern_preview_text.pack(side=LEFT, fill=X, expand=True)
        preview_scroll.pack(side=RIGHT, fill=Y)
        color_order_group = ttk.LabelFrame(rule_group, text="カラー順")
        color_order_group.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))
        color_order_body = Frame(color_order_group)
        color_order_body.pack(fill=BOTH, expand=True, padx=8, pady=6)
        self.rule_color_listbox = Listbox(color_order_body, height=4, exportselection=False)
        self.rule_color_listbox.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        color_order_buttons = Frame(color_order_body)
        color_order_buttons.pack(side=LEFT, fill=Y)
        Button(color_order_buttons, text="上へ", command=lambda: self.move_rule_color_order(-1), width=8).pack(anchor=W, pady=(0, 4))
        Button(color_order_buttons, text="下へ", command=lambda: self.move_rule_color_order(1), width=8).pack(anchor=W)
        Label(
            basic_left,
            text="セット商品は在庫Excelへ直接転記しません。セット構成タブで子商品への展開内容を確認してください。",
            justify=LEFT,
            fg="#92400E",
            bg="#FEF3C7",
            wraplength=720,
        ).pack(fill=X, padx=8, pady=(0, 8))
        self.set_product_hint = basic_left.pack_slaves()[-1]
        danger_row = Frame(basic_left)
        danger_row.pack(fill=X, padx=8, pady=(0, 8))
        Button(
            danger_row,
            text="商品データ削除",
            command=self.delete_current_product,
            width=16,
            bg="#B91C1C",
            fg="#FFFFFF",
            activebackground="#991B1B",
            activeforeground="#FFFFFF",
        ).pack(side=RIGHT)

        variant_list_group = ttk.LabelFrame(variant_tab, text="子SKU一覧")
        variant_list_group.pack(fill=BOTH, expand=True, padx=10, pady=(10, 6))
        variant_columns = ("variant", "color", "size", "jan", "sold_out", "color_order", "size_order", "mall_skus")
        variant_tree_frame = Frame(variant_list_group)
        variant_tree_frame.pack(fill=BOTH, expand=True)
        self.variant_tree = ttk.Treeview(variant_tree_frame, columns=variant_columns, show="headings", height=16)
        variant_scroll_y = Scrollbar(variant_tree_frame, orient="vertical", command=self.variant_tree.yview)
        variant_scroll_x = Scrollbar(variant_tree_frame, orient="horizontal", command=self.variant_tree.xview)
        self.variant_tree.configure(yscrollcommand=variant_scroll_y.set, xscrollcommand=variant_scroll_x.set)
        variant_defs = [
            ("variant", "子SKUコード", 170),
            ("color", "カラー", 150),
            ("size", "サイズ", 150),
            ("jan", "JAN", 130),
            ("sold_out", "完売", 55),
            ("color_order", "色順", 45),
            ("size_order", "サイズ順", 55),
            ("mall_skus", "モールSKU", 700),
        ]
        for col, text, width in variant_defs:
            self.variant_tree.heading(col, text=text)
            self.variant_tree.column(col, width=width, minwidth=width, anchor=W, stretch=False)
        self.variant_tree.grid(row=0, column=0, sticky="nsew")
        variant_scroll_y.grid(row=0, column=1, sticky="ns")
        variant_scroll_x.grid(row=1, column=0, sticky="ew")
        variant_tree_frame.grid_rowconfigure(0, weight=1)
        variant_tree_frame.grid_columnconfigure(0, weight=1)
        self.variant_tree.bind("<<TreeviewSelect>>", self.on_variant_selected)

        variant_edit_group = ttk.LabelFrame(variant_tab, text="選択中の子SKUを編集")
        variant_edit_group.pack(fill=X, padx=10, pady=(0, 10))
        self.variant_edit_group = variant_edit_group
        variant_form = Frame(variant_edit_group)
        variant_form.pack(side=LEFT, fill=X, padx=8, pady=8)
        self._form_row(variant_form, "子SKU", self.variant_code_var, 0, readonly=True, width=32)
        self._form_row(variant_form, "カラー", self.variant_color_var, 1, width=32)
        self._form_row(variant_form, "サイズ", self.variant_size_var, 2, width=32)
        self._form_row(variant_form, "JAN", self.variant_jan_code_var, 3, width=32)
        ttk.Checkbutton(variant_form, text="完売（在庫アラート除外）", variable=self.variant_sold_out_var).grid(row=4, column=1, sticky=W, pady=3)
        self._form_row(variant_form, "カラー順", self.variant_color_order_var, 5, width=32)
        self._form_row(variant_form, "サイズ順", self.variant_size_order_var, 6, width=32)
        variant_buttons = ttk.LabelFrame(variant_edit_group, text="操作")
        variant_buttons.pack(side=LEFT, fill=BOTH, expand=True, padx=8, pady=8)
        Button(variant_buttons, text="子SKU設定を保存", command=self.save_variant, width=24).pack(anchor=W, pady=(4, 8))
        Button(variant_buttons, text="このカラーを上へ", command=lambda: self.move_selected_color(-1), width=24).pack(anchor=W, pady=4)
        Button(variant_buttons, text="このカラーを下へ", command=lambda: self.move_selected_color(1), width=24).pack(anchor=W, pady=4)
        Label(
            variant_buttons,
            text="カラー順は同じカラーの全子SKUに反映されます。",
            justify=LEFT,
            fg="#555555",
            wraplength=260,
        ).pack(anchor=W, pady=(10, 4))

        set_info = ttk.LabelFrame(set_tab, text="セット商品について")
        set_info.pack(fill=X, padx=10, pady=(10, 6))
        Label(set_info, textvariable=self.set_notice_var, justify=LEFT, anchor=W, fg="#555555").pack(fill=X, padx=8, pady=8)

        set_list_group = ttk.LabelFrame(set_tab, text="セット構成一覧")
        set_list_group.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        set_columns = ("parent", "parent_color", "parent_size", "child_code", "child_product", "child_variant", "child_color", "child_size", "qty")
        set_tree_frame = Frame(set_list_group)
        set_tree_frame.pack(fill=BOTH, expand=True)
        self.set_tree = ttk.Treeview(set_tree_frame, columns=set_columns, show="headings", height=18)
        set_scroll = Scrollbar(set_tree_frame, orient="vertical", command=self.set_tree.yview)
        self.set_tree.configure(yscrollcommand=set_scroll.set)
        set_defs = [
            ("parent", "親SKU", 140),
            ("parent_color", "親カラー", 90),
            ("parent_size", "親サイズ", 120),
            ("child_code", "子商品コード", 110),
            ("child_product", "子商品", 240),
            ("child_variant", "子SKU", 140),
            ("child_color", "子カラー", 90),
            ("child_size", "子サイズ", 120),
            ("qty", "数", 45),
        ]
        for col, text, width in set_defs:
            self.set_tree.heading(col, text=text)
            self.set_tree.column(col, width=width, anchor=W)
        self.set_tree.pack(side=LEFT, fill=BOTH, expand=True)
        set_scroll.pack(side=RIGHT, fill=Y)
        Button(set_list_group, text="選択した子商品の設定を開く", command=self.open_selected_child_product, width=24).pack(anchor=E, padx=8, pady=(0, 8))
        self.update_product_mode_buttons()
        self.apply_product_type_view(None)

    def _form_row(self, parent: Frame, label: str, variable: StringVar, row: int, readonly: bool = False, width: int = 48) -> None:
        parent.columnconfigure(1, weight=1)
        Label(parent, text=label, width=14, anchor=W).grid(row=row, column=0, sticky=W, pady=3)
        state = "readonly" if readonly else "normal"
        Entry(parent, textvariable=variable, width=width, state=state).grid(row=row, column=1, sticky="ew", pady=3)

    def on_product_mode_changed(self, event=None) -> None:
        self.set_product_mode("set" if self.product_mode == "single" else "single")

    def set_product_mode(self, mode: str) -> None:
        if mode not in ("single", "set"):
            return
        if mode == self.product_mode and self.product_tree.get_children():
            return
        self.save_current_product_silent()
        self.product_mode = mode
        if self.product_mode == "set":
            self.product_setting_filter = "all"
        self.current_product_code = ""
        self.update_product_mode_buttons()
        self.update_product_setting_filter_button()
        self.refresh_products()
        self.apply_product_type_view(None)

    def update_product_mode_buttons(self) -> None:
        if not hasattr(self, "single_mode_button") or not hasattr(self, "set_mode_button"):
            return
        selected_bg = "#2563EB"
        selected_fg = "#FFFFFF"
        normal_bg = self.window.cget("bg")
        normal_fg = "#111827"
        for mode, button in (("single", self.single_mode_button), ("set", self.set_mode_button)):
            selected = mode == self.product_mode
            button.configure(
                relief="sunken" if selected else "raised",
                bg=selected_bg if selected else normal_bg,
                fg=selected_fg if selected else normal_fg,
                activebackground=selected_bg if selected else normal_bg,
                activeforeground=selected_fg if selected else normal_fg,
            )
        self.update_product_setting_filter_button()

    def toggle_product_setting_filter(self) -> None:
        order = ["all", "unset", "auto"]
        try:
            index = order.index(self.product_setting_filter)
        except ValueError:
            index = 0
        self.product_setting_filter = order[(index + 1) % len(order)]
        self.update_product_setting_filter_button()
        self.refresh_products()

    def update_product_setting_filter_button(self) -> None:
        button = getattr(self, "product_setting_filter_button", None)
        if not button:
            return
        labels = {"all": "全商品", "unset": "未設定", "auto": "自動OK"}
        colors = {
            "all": (self.window.cget("bg"), "#111827"),
            "unset": ("#FED7AA", "#111827"),
            "auto": ("#BBF7D0", "#111827"),
        }
        bg, fg = colors.get(self.product_setting_filter, colors["all"])
        button.configure(text=labels.get(self.product_setting_filter, "全商品"), bg=bg, fg=fg, activebackground=bg)

    def toggle_auto_write_confirmed(self) -> None:
        if not self.current_product_code:
            return
        confirmed = not self.auto_write_confirmed_var.get()
        self.auto_write_confirmed_var.set(confirmed)
        self.db.set_product_auto_write_confirmed(self.current_product_code, confirmed)
        self.save_current_transfer_page_silent()
        self.update_auto_write_button()

    def update_auto_write_button(self) -> None:
        if not hasattr(self, "auto_write_button"):
            return
        if self.auto_write_confirmed_var.get():
            self.auto_write_button.configure(text="自動OK 確認済", bg="#BBF7D0", activebackground="#86EFAC")
        else:
            self.auto_write_button.configure(text="自動OK 未確認", bg="#FED7AA", activebackground="#FDBA74")

    def apply_product_type_view(self, product: sqlite3.Row | None) -> None:
        is_set = bool(product and int(product["is_set"]))
        if is_set:
            self.inventory_group.pack_forget()
            self.rule_group.pack_forget()
            self.set_product_hint.pack(fill=X, padx=8, pady=(0, 8))
            self._show_detail_tab(self.set_tab, "セット構成")
            self._hide_detail_tab(self.variant_tab)
            self.detail_notebook.select(self.set_tab)
        else:
            self.set_product_hint.pack_forget()
            if not self.inventory_group.winfo_ismapped():
                self.inventory_group.pack(fill=X, padx=8, pady=(6, 8))
            if not self.rule_group.winfo_ismapped():
                self.rule_group.pack(fill=BOTH, expand=True, padx=8, pady=(6, 8))
            self._show_detail_tab(self.variant_tab, "子SKU・並び順")
            self._hide_detail_tab(self.set_tab)
            if self.detail_notebook.select() == str(self.set_tab):
                self.detail_notebook.select(self.basic_tab)

    def _show_detail_tab(self, tab: Frame, text: str) -> None:
        if str(tab) not in self.detail_notebook.tabs():
            self.detail_notebook.add(tab, text=text)

    def _hide_detail_tab(self, tab: Frame) -> None:
        if str(tab) in self.detail_notebook.tabs():
            self.detail_notebook.hide(tab)

    def refresh_products(self) -> None:
        if self.current_product_code and not self.loading_product:
            self.save_current_product_silent()
        keep_code = self.current_product_code
        self.products = self.db.products_for_settings(self.search_var.get(), 1 if self.product_mode == "set" else 0)
        if self.product_mode == "single":
            if self.product_setting_filter == "unset":
                self.products = [row for row in self.products if int(row["auto_write_confirmed"] or 0) == 0]
            elif self.product_setting_filter == "auto":
                self.products = [row for row in self.products if int(row["auto_write_confirmed"] or 0) != 0]
        self.product_tree.delete(*self.product_tree.get_children())
        for row in self.products:
            self.product_tree.insert(
                "",
                END,
                iid=row["product_code"],
                values=(
                    row["product_code"],
                    row["display_name"],
                ),
            )
        if keep_code and keep_code in self.product_tree.get_children():
            self.product_tree.selection_set(keep_code)
            self.product_tree.focus(keep_code)
        if self.initial_product_code and self.initial_product_code in self.product_tree.get_children():
            self.select_product(self.initial_product_code)

    def select_product(self, product_code: str) -> None:
        if product_code not in self.product_tree.get_children():
            return
        self.product_tree.selection_set(product_code)
        self.product_tree.focus(product_code)
        self.product_tree.see(product_code)
        self.on_product_selected()

    def clear_product_search(self) -> None:
        self.search_var.set("")
        self.refresh_products()

    def visible_product_ids(self) -> list[str]:
        return [str(iid) for iid in self.product_tree.get_children()]

    def select_visible_products(self) -> None:
        product_ids = self.visible_product_ids()
        if not product_ids:
            return
        self.product_tree.selection_set(product_ids)
        self.product_tree.focus(product_ids[0])
        self.product_tree.see(product_ids[0])
        self.on_product_selected()

    def clear_visible_product_selection(self) -> None:
        product_ids = self.visible_product_ids()
        if not product_ids:
            return
        self.product_tree.selection_remove(product_ids)

    def delete_current_product(self) -> None:
        code = clean(self.current_product_code)
        name = clean(self.display_name_var.get())
        if not code:
            messagebox.showwarning("商品未選択", "削除する商品を選択してください。", parent=self.window)
            return
        ok = messagebox.askyesno(
            "商品データ削除",
            f"商品データを削除します。\n\n"
            f"商品コード: {code}\n"
            f"商品名: {name}\n\n"
            "削除対象:\n"
            "・商品マスタ\n"
            "・子SKU、モールSKU\n"
            "・セット構成\n"
            "・商品別ユーザー設定、転記ページ、カラー/サイズ手修正\n"
            "・現在/過去の転記タスク、在庫アラート\n\n"
            "受注CSVの元データは削除しません。\n"
            "実行前にDBバックアップを作成します。\n\n"
            "本当に削除しますか？",
            parent=self.window,
        )
        if not ok:
            return
        try:
            backup_path = self.db.create_backup(self.base_dir / "退避_バックアップ", f"product_delete_{code}")
            counts = self.db.delete_product_data(code)
        except Exception as exc:
            messagebox.showerror("商品データ削除エラー", str(exc), parent=self.window)
            return
        self.current_product_code = ""
        self.current_variant_code = ""
        self.product_code_var.set("")
        self.display_name_var.set("")
        self.rakuten_code_var.set("")
        self.jan_code_var.set("")
        self.product_url_var.set("")
        self.inventory_file_var.set("")
        self.sheet_name_var.set("")
        self.thumbnail_url_var.set("")
        self.image_status_var.set("商品を選択してください")
        self.clear_image("商品を選択してください")
        self.refresh_products()
        deleted_summary = " / ".join(f"{key}:{value}" for key, value in counts.items() if value)
        messagebox.showinfo(
            "商品データ削除",
            f"商品データを削除しました。\n\nバックアップ: {backup_path}\n\n削除件数: {deleted_summary or '0'}",
            parent=self.window,
        )

    def bulk_set_min_stock_quantity(self) -> None:
        selected = list(self.product_tree.selection())
        if not selected:
            messagebox.showwarning("未選択", "最低在庫数を設定する商品を選択してください。", parent=self.window)
            return
        try:
            min_stock = int(float(self.bulk_min_stock_quantity_var.get().strip() or "3"))
        except ValueError:
            messagebox.showerror("入力エラー", "最低在庫数は数値で入力してください。", parent=self.window)
            return
        if not messagebox.askyesno("最低在庫数 一括設定", f"選択中の {len(selected)} 商品に最低在庫数 {min_stock} を設定します。実行しますか？", parent=self.window):
            return
        updated = self.db.bulk_update_min_stock_quantity(selected, min_stock)
        self.min_stock_quantity_var.set(str(min_stock))
        self.refresh_products()
        for product_code in selected:
            if product_code in self.product_tree.get_children():
                self.product_tree.selection_add(product_code)
        messagebox.showinfo("一括設定完了", f"{updated} 商品の最低在庫数を更新しました。", parent=self.window)

    def on_product_selected(self, event=None) -> None:
        selected = self.product_tree.selection()
        if not selected:
            return
        focused = self.product_tree.focus()
        product_code = focused if focused in selected else selected[0]
        if self.current_product_code and product_code != self.current_product_code:
            self.save_current_product_silent()
        product = self.db.product_for_settings(product_code)
        if not product:
            return
        self.loading_product = True
        self.current_product_code = product_code
        self.product_code_var.set(product["product_code"])
        self.display_name_var.set(product["display_name"])
        self.rakuten_code_var.set(product["rakuten_parent_code"])
        self.jan_code_var.set(product["jan_code"] if "jan_code" in product.keys() else "")
        self.inventory_file_var.set(product["inventory_file_path"])
        self.sheet_name_var.set(product["inventory_sheet_name"])
        self.excel_start_col_var.set(normalize_excel_start_col(product["excel_start_col"]))
        self.auto_write_confirmed_var.set(self.db.product_auto_write_confirmed(product_code))
        self.manual_input_var.set(bool(product["manual_input"] if "manual_input" in product.keys() else 0))
        self.thumbnail_url_var.set(product["thumbnail_url"])
        self.quantity_multiplier_var.set("1")
        self.min_stock_quantity_var.set(str(product["min_stock_quantity"] or 0))
        self.update_product_url()
        self.update_auto_write_button()
        self.apply_product_type_view(product)
        self.refresh_variants()
        self.refresh_rule_color_order()
        self.refresh_set_components()
        self.load_transfer_pages_for_current_product()
        self.load_cached_thumbnail()
        self.loading_product = False

    def refresh_variants(self) -> None:
        self.variant_tree.delete(*self.variant_tree.get_children())
        self.current_variant_code = ""
        self.variant_code_var.set("")
        self.variant_color_var.set("")
        self.variant_size_var.set("")
        self.variant_jan_code_var.set("")
        self.variant_sold_out_var.set(False)
        self.variant_color_order_var.set("")
        self.variant_size_order_var.set("")
        if not self.current_product_code:
            return
        for row in self.db.variants_for_product(self.current_product_code):
            self.variant_tree.insert(
                "",
                END,
                iid=row["variant_code"],
                values=(
                    row["variant_code"],
                    row["color"],
                    row["size"],
                    row["jan_code"] if "jan_code" in row.keys() else "",
                    "✓" if int(row["sold_out"] or 0) else "",
                    row["color_order"],
                    row["size_order"],
                    row["mall_skus"] or "",
                ),
            )

    def refresh_set_components(self) -> None:
        self.set_tree.delete(*self.set_tree.get_children())
        self.set_notice_var.set("")
        if not self.current_product_code:
            return
        product = next((row for row in self.products if row["product_code"] == self.current_product_code), None)
        if not product or not int(product["is_set"]):
            self.set_notice_var.set("単品商品ではセット構成は使用しません。")
            return
        rows = self.db.set_components_for_product(self.current_product_code)
        if not rows:
            self.set_notice_var.set("セット構成が登録されていません。受注時に未確定になる可能性があります。")
            return
        missing = 0
        for idx, row in enumerate(rows, start=1):
            if not clean(row["child_variant_code"]):
                missing += 1
            self.set_tree.insert(
                "",
                END,
                iid=str(idx),
                values=(
                    row["parent_variant_code"],
                    row["parent_color"],
                    row["parent_size"],
                    row["child_product_code"] or "",
                    row["child_product_name"] or "",
                    row["child_variant_code"] or "",
                    row["child_color"] or "",
                    row["child_size"] or "",
                    row["component_quantity"] or "",
                ),
            )
        note = f"このセット商品は {len(rows)} 行の構成で、受注時は子商品へ展開されます。"
        if missing:
            note += f" 子SKU未登録の構成が {missing} 行あります。"
        self.set_notice_var.set(note)

    def open_selected_child_product(self) -> None:
        selected = self.set_tree.selection()
        if not selected:
            messagebox.showwarning("未選択", "子商品を選択してください。", parent=self.window)
            return
        values = self.set_tree.item(selected[0], "values")
        if len(values) < 4 or not values[3]:
            messagebox.showwarning("子商品なし", "選択行に子商品コードがありません。", parent=self.window)
            return
        child_code = str(values[3])
        self.set_product_mode("single")
        self.search_var.set(child_code)
        self.refresh_products()
        if child_code in self.product_tree.get_children():
            self.select_product(child_code)
        else:
            messagebox.showwarning("子商品なし", f"単品商品一覧に子商品が見つかりません。\n{child_code}", parent=self.window)

    def parse_nonnegative_int(self, value: str, default: int = 0) -> int:
        try:
            return max(0, int(float(clean(value) or str(default))))
        except ValueError:
            return default

    def load_product_copy_settings(self) -> None:
        if not self.current_product_code:
            return
        settings = self.db.get_product_copy_settings(self.current_product_code, "ネット")
        self.copy_title_var.set(str(settings["copy_title"]))
        self.title_tabs_var.set(str(settings["title_tabs"]))
        self.color_gap_tabs_var.set(str(settings["color_gap_tabs"]))
        self.tail_tabs_var.set(str(settings["tail_tabs"]))
        self.append_date_var.set(bool(settings["append_date"]))
        self.transfer_pattern_var.set(str(settings["transfer_pattern"]))
        self.update_transfer_pattern_preview()

    def load_transfer_pages_for_current_product(self) -> None:
        if not self.current_product_code:
            return
        self.transfer_pages = self.db.product_transfer_pages(self.current_product_code)
        values = [f"{index + 1}: {row['page_name']}" for index, row in enumerate(self.transfer_pages)]
        self.transfer_page_combo.configure(values=values)
        if not self.transfer_pages:
            self.current_transfer_page_id = 0
            return
        self.load_transfer_page(self.transfer_pages[0])

    def load_transfer_page(self, page: sqlite3.Row) -> None:
        self.loading_transfer_page = True
        try:
            self.current_transfer_page_id = int(page["id"])
            index = next((i for i, row in enumerate(self.transfer_pages) if int(row["id"]) == self.current_transfer_page_id), 0)
            self.transfer_page_select_var.set(f"{index + 1}: {page['page_name']}")
            self.transfer_page_name_var.set(str(page["page_name"]))
            self.inventory_file_var.set(str(page["inventory_file_path"]))
            self.sheet_name_var.set(str(page["inventory_sheet_name"]))
            self.excel_start_col_var.set(str(page["excel_start_col"] or "A"))
            self.copy_title_var.set(str(page["copy_title"]))
            self.title_tabs_var.set(str(page["title_tabs"]))
            self.color_gap_tabs_var.set(str(page["color_gap_tabs"]))
            self.tail_tabs_var.set(str(page["tail_tabs"]))
            self.append_date_var.set(bool(page["append_date"]))
            self.transfer_pattern_var.set(str(page["transfer_pattern"]))
            self.quantity_multiplier_var.set(str(page["quantity_multiplier"] or 1))
            self.auto_write_confirmed_var.set(bool(page["auto_write_confirmed"]))
            self.title_date_add_only_var.set(bool(page["title_date_add_only"] if "title_date_add_only" in page.keys() else 0))
            self.update_auto_write_button()
            self.update_transfer_pattern_preview()
        finally:
            self.loading_transfer_page = False

    def on_transfer_page_selected(self, _event=None) -> None:
        if self.loading_transfer_page:
            return
        selected = self.transfer_page_select_var.get()
        try:
            index = int(selected.split(":", 1)[0]) - 1
        except ValueError:
            index = 0
        target_id = 0
        if 0 <= index < len(self.transfer_pages):
            target_id = int(self.transfer_pages[index]["id"])
        self.save_current_transfer_page_silent()
        if target_id:
            target = next((row for row in self.transfer_pages if int(row["id"]) == target_id), None)
            if target is not None:
                self.load_transfer_page(target)

    def save_current_transfer_page_silent(self) -> None:
        if self.loading_product or self.loading_transfer_page or not self.current_product_code or not self.current_transfer_page_id:
            return
        page_order = 1
        for index, row in enumerate(self.transfer_pages, start=1):
            if int(row["id"]) == self.current_transfer_page_id:
                page_order = int(row["page_order"] or index)
                break
        self.current_transfer_page_id = self.db.save_product_transfer_page(
            self.current_product_code,
            self.current_transfer_page_id,
            self.transfer_page_name_var.get().strip() or f"ページ{page_order}",
            page_order,
            self.inventory_file_var.get(),
            self.sheet_name_var.get(),
            self.excel_start_col_var.get(),
            self.copy_title_var.get().strip(),
            self.parse_nonnegative_int(self.title_tabs_var.get()),
            self.parse_nonnegative_int(self.color_gap_tabs_var.get()),
            self.parse_nonnegative_int(self.tail_tabs_var.get()),
            self.append_date_var.get(),
            self.transfer_pattern_var.get().strip(),
            self.parse_nonnegative_int(self.quantity_multiplier_var.get()) or 1,
            self.auto_write_confirmed_var.get(),
            False,
        )
        self.transfer_pages = self.db.product_transfer_pages(self.current_product_code)
        values = [f"{index + 1}: {row['page_name']}" for index, row in enumerate(self.transfer_pages)]
        self.transfer_page_combo.configure(values=values)
        for index, row in enumerate(self.transfer_pages):
            if int(row["id"]) == self.current_transfer_page_id:
                self.transfer_page_select_var.set(f"{index + 1}: {row['page_name']}")
                break

    def legacy_inventory_values_for_current_product(self) -> tuple[str, str, str]:
        if not self.current_product_code:
            return "", "", "A"
        current_order = 1
        current_page = None
        for index, row in enumerate(self.transfer_pages, start=1):
            if int(row["id"]) == self.current_transfer_page_id:
                current_page = row
                current_order = int(row["page_order"] or index)
                break
        if current_page is not None and current_order == 1:
            return (
                self.inventory_file_var.get().strip(),
                self.sheet_name_var.get(),
                self.excel_start_col_var.get().strip() or "A",
            )
        page1 = next((row for row in self.transfer_pages if int(row["page_order"] or 0) == 1), None)
        if page1 is not None:
            return (
                str(page1["inventory_file_path"]),
                str(page1["inventory_sheet_name"]),
                str(page1["excel_start_col"] or "A"),
            )
        product = self.db.product_for_settings(self.current_product_code)
        if product:
            return (
                str(product["inventory_file_path"]),
                str(product["inventory_sheet_name"]),
                str(product["excel_start_col"] or "A"),
            )
        return "", "", "A"

    def add_transfer_page(self) -> None:
        if not self.current_product_code:
            return
        self.save_current_transfer_page_silent()
        order = max([int(row["page_order"] or 0) for row in self.transfer_pages] or [0]) + 1
        page_id = self.db.save_product_transfer_page(
            self.current_product_code, None, f"ページ{order}", order, "", "", "A", "ネット", 0, 0, 0, True, "", 1, False, False
        )
        self.transfer_pages = self.db.product_transfer_pages(self.current_product_code)
        page = next((row for row in self.transfer_pages if int(row["id"]) == page_id), self.transfer_pages[-1])
        self.load_transfer_page(page)

    def duplicate_transfer_page(self) -> None:
        if not self.current_product_code:
            return
        self.save_current_transfer_page_silent()
        current = next((row for row in self.transfer_pages if int(row["id"]) == self.current_transfer_page_id), None)
        if not current:
            return
        order = max([int(row["page_order"] or 0) for row in self.transfer_pages] or [0]) + 1
        page_id = self.db.save_product_transfer_page(
            self.current_product_code, None, f"{current['page_name']} コピー", order,
            current["inventory_file_path"], current["inventory_sheet_name"], current["excel_start_col"],
            current["copy_title"], int(current["title_tabs"]), int(current["color_gap_tabs"]), int(current["tail_tabs"]),
            bool(current["append_date"]), current["transfer_pattern"], int(current["quantity_multiplier"] or 1), bool(current["auto_write_confirmed"]),
            False
        )
        self.transfer_pages = self.db.product_transfer_pages(self.current_product_code)
        page = next((row for row in self.transfer_pages if int(row["id"]) == page_id), self.transfer_pages[-1])
        self.load_transfer_page(page)

    def delete_transfer_page(self) -> None:
        if not self.current_transfer_page_id:
            return
        if len(self.transfer_pages) <= 1:
            messagebox.showwarning("削除不可", "転記ページは最低1つ必要です。", parent=self.window)
            return
        if not messagebox.askyesno("転記ページ削除", "現在の転記ページを削除しますか？", parent=self.window):
            return
        self.db.delete_product_transfer_page(self.current_transfer_page_id)
        self.load_transfer_pages_for_current_product()

    def save_product_copy_settings_silent(self) -> None:
        if not self.current_product_code:
            return
        if self.current_transfer_page_id:
            self.save_current_transfer_page_silent()
            return
        self.db.save_product_copy_settings(
            self.current_product_code,
            self.copy_title_var.get().strip(),
            self.parse_nonnegative_int(self.title_tabs_var.get()),
            self.parse_nonnegative_int(self.color_gap_tabs_var.get()),
            self.parse_nonnegative_int(self.tail_tabs_var.get()),
            self.append_date_var.get(),
            self.transfer_pattern_var.get().strip(),
        )

    def transfer_pattern_tokens(self) -> list[str]:
        return transfer_pattern_raw_tokens(self.transfer_pattern_var.get())

    def set_transfer_pattern_tokens(self, tokens: list[str]) -> None:
        self.transfer_pattern_var.set(",".join(tokens))
        self.update_transfer_pattern_preview()

    def append_transfer_pattern_token(self, token: str) -> None:
        tokens = self.transfer_pattern_tokens()
        tokens.append(token)
        self.set_transfer_pattern_tokens(tokens)

    def insert_transfer_pattern_text(self, text: str) -> None:
        entry = getattr(self, "transfer_pattern_entry", None)
        current = self.transfer_pattern_var.get()
        if not entry:
            self.transfer_pattern_var.set(current + text)
            self.update_transfer_pattern_preview()
            return
        try:
            index = entry.index("insert")
        except Exception:
            index = len(current)
        self.transfer_pattern_var.set(current[:index] + text + current[index:])
        entry.icursor(index + len(text))
        entry.focus_set()
        self.update_transfer_pattern_preview()

    def remove_last_transfer_pattern_token(self) -> None:
        tokens = self.transfer_pattern_tokens()
        if tokens:
            tokens.pop()
        self.set_transfer_pattern_tokens(tokens)

    def delete_transfer_pattern_token_before_cursor(self) -> None:
        entry = getattr(self, "transfer_pattern_entry", None)
        current = self.transfer_pattern_var.get()
        if not current:
            return
        try:
            index = entry.index("insert") if entry else len(current)
        except Exception:
            index = len(current)
        index = max(0, min(index, len(current)))
        if index <= 0:
            return
        search_pos = index - 2 if current[index - 1:index] == "," else index - 1
        if search_pos < 0:
            return
        start = current.rfind(",", 0, search_pos + 1) + 1
        end = index
        if end < len(current) and current[end:end + 1] == ",":
            end += 1
        elif end < len(current):
            next_comma = current.find(",", end)
            if next_comma >= 0:
                end = next_comma + 1
        self.transfer_pattern_var.set(current[:start] + current[end:])
        if entry:
            entry.icursor(start)
            entry.focus_set()
        self.update_transfer_pattern_preview()

    def transfer_pattern_quantity_labels(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        index = 1
        for task in self.product_tasks_for_pattern_detection():
            for size in task.sizes:
                labels[str(index)] = clean(size)
                index += 1
        return labels

    def compact_size_label(self, value: str) -> str:
        text = unicodedata.normalize("NFKC", clean(value))
        text = text.translate(str.maketrans({"М": "M", "м": "m"}))
        if len(text) <= 4:
            return text
        main_text = re.split(r"[（(]", text, maxsplit=1)[0].strip() or text
        match = re.match(r"(?:\d+\s*)?[A-Za-z]{1,4}", main_text)
        if not match:
            match = re.search(r"\d+\s*[A-Za-z]+|[A-Za-z]+\d+|[A-Za-z]+", main_text)
        if match:
            compact = match.group(0).replace(" ", "")
            return compact[:4]
        return main_text[:4]

    def update_transfer_pattern_preview(self) -> None:
        pattern = self.transfer_pattern_var.get().strip()
        if not pattern:
            self.set_transfer_pattern_preview_text("転記パターン未設定: 従来のTab設定を使用します。")
            return
        labels: list[str] = []
        quantity_labels = self.transfer_pattern_quantity_labels()
        blank_count = 0

        def flush_blank() -> None:
            nonlocal blank_count
            if blank_count == 1:
                labels.append("[空白]")
            elif blank_count > 1:
                labels.append(f"[空白x{blank_count}]")
            blank_count = 0

        for token in self.transfer_pattern_tokens():
            lower = token.lower()
            count = transfer_pattern_blank_count(token)
            if count:
                blank_count += count
                continue
            flush_blank()
            if lower in {"title", "ttl", "タイトル"}:
                label = "[タイトル]"
            elif lower in {"d", "date", "日付"}:
                label = "[日付]"
            elif token in quantity_labels:
                label = f"[{token}/{self.compact_size_label(quantity_labels[token])}]"
            elif token.isdigit():
                label = f"[{token}]"
            else:
                label = f"[{token}]"
            labels.append(label)
        flush_blank()
        self.set_transfer_pattern_preview_text(" ".join(labels))

    def set_transfer_pattern_preview_text(self, text: str) -> None:
        self.transfer_pattern_preview_var.set(text)
        preview = getattr(self, "transfer_pattern_preview_text", None)
        if not preview:
            return
        preview.configure(state="normal")
        preview.delete("1.0", END)
        preview.insert("1.0", text)
        preview.configure(state="disabled")

    def refresh_rule_color_order(self) -> None:
        if not hasattr(self, "rule_color_listbox"):
            return
        self.rule_color_listbox.delete(0, END)
        if not self.current_product_code:
            return
        for row in self.db.product_color_order(self.current_product_code):
            self.rule_color_listbox.insert(END, clean(row["color"]))

    def move_rule_color_order(self, direction: int) -> None:
        if not self.current_product_code:
            return
        selected = self.rule_color_listbox.curselection() if hasattr(self, "rule_color_listbox") else ()
        if not selected:
            messagebox.showwarning("カラー未選択", "移動するカラーを選択してください。", parent=self.window)
            return
        index = selected[0]
        color = clean(self.rule_color_listbox.get(index))
        if not color:
            return
        self.db.move_product_color(self.current_product_code, color, direction)
        self.refresh_variants()
        self.refresh_rule_color_order()
        new_index = max(0, min(self.rule_color_listbox.size() - 1, index + direction))
        if self.rule_color_listbox.size():
            self.rule_color_listbox.selection_set(new_index)
            self.rule_color_listbox.see(new_index)
        self.update_transfer_pattern_preview()

    def product_tasks_for_pattern_detection(self) -> list[TaskView]:
        if not self.current_product_code:
            return []
        rows = self.db.variant_grid_for_product(self.current_product_code)
        grouped: dict[str, list[str]] = {}
        for row in rows:
            color = clean(row["color"])
            grouped.setdefault(color, []).append(clean(row["size"]))
        product_name = self.display_name_var.get().strip()
        return [
            TaskView(
                id=-1,
                product_code=self.current_product_code,
                product_name=product_name,
                color=color,
                sizes=sizes,
                quantities=["" for _ in sizes],
                previous_quantities=[],
                total=0,
                status="settings",
                aggregation_round=1,
                task_kind="initial",
                source_task_ids=[],
            )
            for color, sizes in grouped.items()
        ]

    def auto_detect_transfer_pattern(self) -> None:
        if not self.current_product_code:
            messagebox.showwarning("商品未選択", "商品を選択してください。", parent=self.window)
            return
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        self.save_current_product_silent()
        product = next((row for row in self.products if row["product_code"] == self.current_product_code), None)
        if product and int(product["is_set"]):
            messagebox.showwarning("セット商品", "セット商品は在庫Excelへ直接転記しないため、転記パターンは取得しません。", parent=self.window)
            return
        if clean(self.transfer_pattern_var.get()):
            if not messagebox.askyesno(
                "転記パターン上書き確認",
                "入力済みの転記パターンがあります。\n自動取得すると現在の転記パターンを上書きします。\n続行しますか？",
                parent=self.window,
            ):
                self.window.lift()
                self.window.focus_force()
                return
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.sheet_name_var.get()
        if not path:
            messagebox.showwarning("ファイル未設定", "在庫Excelを指定してください。", parent=self.window)
            return
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"在庫Excelが見つかりません。\n{path}", parent=self.window)
            return
        product_tasks = self.product_tasks_for_pattern_detection()
        if not product_tasks:
            messagebox.showwarning("子SKUなし", "転記パターン取得に使う子SKU構成がありません。", parent=self.window)
            return
        helper = TransferWindow.__new__(TransferWindow)
        helper.db = self.db
        helper.base_dir = self.base_dir
        helper.window = self.window
        try:
            workbook, worksheet, excel = TransferWindow.open_target_workbook(helper, path, sheet_name, self.excel_start_col_var.get())
            candidate = TransferWindow.detect_write_candidate_cell(helper, worksheet, excel, self.excel_start_col_var.get())
            candidate.row = TransferWindow.adjust_candidate_after_red_marker(helper, worksheet, candidate.row, candidate.col, candidate.island)
            rule = TransferWindow.infer_copy_rule_from_candidate(helper, candidate, product_tasks)
            if not rule:
                raise RuntimeError("転記パターンを自動取得できませんでした。Excelの表示位置を記入したい島の近くにして再実行してください。")
            title_tabs, color_gap_tabs, tail_tabs, append_date, transfer_pattern = rule
            roles = self.roles_from_transfer_pattern_for_product_tasks(transfer_pattern, product_tasks)
            TransferWindow.ensure_excel_row_is_writable(helper, worksheet, candidate.row, candidate.col, roles)
            self.excel_start_col_var.set(excel_index_to_column(candidate.col))
            self.title_tabs_var.set(str(title_tabs))
            self.color_gap_tabs_var.set(str(color_gap_tabs))
            self.tail_tabs_var.set(str(tail_tabs))
            self.append_date_var.set(append_date)
            self.transfer_pattern_var.set(transfer_pattern)
            self.save_current_transfer_page_silent()
            self.update_transfer_pattern_preview()
            workbook.Activate()
            worksheet.Activate()
            worksheet.Cells(candidate.row, candidate.col).Select()
            excel.ActiveWindow.ScrollRow = max(1, candidate.row - 8)
            excel.ActiveWindow.ScrollColumn = max(1, candidate.col - 3)
            messagebox.showinfo(
                "取得完了",
                f"転記パターンを取得して保存しました。\nタイトル後Tab: {title_tabs}\nカラー間Tab: {color_gap_tabs}\n末尾Tab: {tail_tabs}",
                parent=self.window,
            )
            TransferWindow.bring_excel_to_front(helper, excel)
        except Exception as exc:
            messagebox.showerror("パターン自動取得エラー", str(exc), parent=self.window)
            self.window.lift()

    def open_transfer_candidate_cell(self) -> None:
        if not self.current_product_code:
            messagebox.showwarning("商品未選択", "商品を選択してください。", parent=self.window)
            return
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        self.save_current_product_silent()
        product = next((row for row in self.products if row["product_code"] == self.current_product_code), None)
        if product and int(product["is_set"]):
            messagebox.showwarning("セット商品", "セット商品は在庫Excelへ直接転記しないため、候補セル確認はできません。", parent=self.window)
            return
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.sheet_name_var.get()
        if not path:
            messagebox.showwarning("ファイル未設定", "在庫Excelを指定してください。", parent=self.window)
            return
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"在庫Excelが見つかりません。\n{path}", parent=self.window)
            return
        product_tasks = self.product_tasks_for_pattern_detection()
        if not product_tasks:
            messagebox.showwarning("子SKUなし", "候補セル確認に使う子SKU構成がありません。", parent=self.window)
            return
        helper = TransferWindow.__new__(TransferWindow)
        helper.db = self.db
        helper.base_dir = self.base_dir
        helper.window = self.window
        try:
            workbook, worksheet, excel = TransferWindow.open_target_workbook(helper, path, sheet_name, self.excel_start_col_var.get())
            candidate = TransferWindow.detect_write_candidate_cell(helper, worksheet, excel, self.excel_start_col_var.get())
            candidate.row = TransferWindow.adjust_candidate_after_red_marker(helper, worksheet, candidate.row, candidate.col, candidate.island)
            roles = self.roles_from_transfer_pattern_for_product_tasks(self.transfer_pattern_var.get(), product_tasks)
            TransferWindow.ensure_excel_row_is_writable(helper, worksheet, candidate.row, candidate.col, roles)
            workbook.Activate()
            worksheet.Activate()
            worksheet.Cells(candidate.row, candidate.col).Select()
            excel.ActiveWindow.ScrollRow = max(1, candidate.row - 8)
            excel.ActiveWindow.ScrollColumn = max(1, candidate.col - 3)
            TransferWindow.bring_excel_to_front(helper, excel)
        except Exception as exc:
            messagebox.showerror("候補セル確認エラー", str(exc), parent=self.window)
            self.window.lift()

    def extend_inventory_island_from_settings(self) -> None:
        if not self.current_product_code:
            messagebox.showwarning("商品未選択", "商品を選択してください。", parent=self.window)
            return
        self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
        self.save_current_product_silent()
        path = normalize_windows_path(self.inventory_file_var.get())
        sheet_name = self.sheet_name_var.get()
        start_col_text = self.excel_start_col_var.get()
        if not path:
            messagebox.showwarning("ファイル未設定", "在庫Excelを指定してください。", parent=self.window)
            return
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"在庫Excelが見つかりません。\n{path}", parent=self.window)
            return
        if not messagebox.askyesno(
            "記入欄増設",
            "指定開始列の一番下の記入欄ブロックを複製して、その直下に新しい記入欄を追加します。\n"
            "既に空の記入欄がある場合もさらに追加されます。\n\n実行しますか？",
            parent=self.window,
        ):
            self.window.lift()
            self.window.focus_force()
            return
        helper = TransferWindow.__new__(TransferWindow)
        helper.db = self.db
        helper.base_dir = self.base_dir
        helper.window = self.window
        try:
            workbook, worksheet, excel = TransferWindow.open_target_workbook(helper, path, sheet_name, start_col_text)
            start_cell = TransferWindow.extend_inventory_island_on_sheet(helper, worksheet, excel, start_col_text)
            workbook.Activate()
            worksheet.Activate()
            start_cell.Select()
            excel.ActiveWindow.ScrollRow = max(1, int(start_cell.Row) - 8)
            excel.ActiveWindow.ScrollColumn = max(1, int(start_cell.Column) - 3)
            try:
                excel.CutCopyMode = False
            except Exception:
                pass
            TransferWindow.bring_excel_to_front(helper, excel)
        except Exception as exc:
            messagebox.showerror("記入欄増設エラー", str(exc), parent=self.window)
            self.window.lift()

    def roles_from_transfer_pattern_for_product_tasks(self, pattern: str, product_tasks: list[TaskView]) -> list[tuple[str, int | None]]:
        quantity_count = sum(len(item.quantities) for item in product_tasks)
        roles: list[tuple[str, int | None]] = []
        for token in transfer_pattern_raw_tokens(pattern):
            lower = token.lower()
            blank_count = transfer_pattern_blank_count(token)
            if blank_count:
                roles.extend([("blank", None)] * blank_count)
            elif lower in {"title", "ttl", "タイトル"}:
                roles.append(("title", None))
            elif lower in {"d", "date", "日付"}:
                roles.append(("date", None))
            else:
                try:
                    quantity_index = int(float(token)) - 1
                except ValueError:
                    quantity_index = -1
                roles.append(("quantity", quantity_index) if 0 <= quantity_index < quantity_count else ("blank", None))
        return roles

    def load_cached_thumbnail(self) -> None:
        self.photo = None
        self.image_label.config(image="")
        url = self.thumbnail_url_var.get().strip()
        if not url:
            self.clear_image("サムネURLなし")
            return
        cache_path = thumbnail_cache_path(self.base_dir, url)
        if not cache_path.exists():
            self.clear_image("キャッシュ未作成")
            return
        try:
            self.show_image(url, cache_path.read_bytes(), True)
        except Exception:
            self.clear_image("表示失敗")

    def save_current_product_silent(self) -> None:
        if self.loading_product or not self.current_product_code:
            return
        product = next((row for row in self.products if row["product_code"] == self.current_product_code), None)
        is_set_product = bool(product and int(product["is_set"]))
        try:
            min_stock_quantity = 3 if is_set_product else int(float(self.min_stock_quantity_var.get().strip() or "3"))
        except ValueError:
            min_stock_quantity = 3
        legacy_inventory_file, legacy_sheet_name, legacy_start_col = self.legacy_inventory_values_for_current_product()
        self.db.update_product_settings(
            self.current_product_code,
            self.display_name_var.get().strip(),
            self.preferred_rakuten_url_code(self.current_product_code, self.rakuten_code_var.get().strip()),
            self.jan_code_var.get().strip(),
            "" if is_set_product else legacy_inventory_file,
            "" if is_set_product else legacy_sheet_name,
            self.thumbnail_url_var.get().strip(),
            1,
            min_stock_quantity,
            "A" if is_set_product else legacy_start_col,
            False if is_set_product else self.manual_input_var.get(),
        )
        if not is_set_product:
            self.db.set_product_auto_write_confirmed(self.current_product_code, self.auto_write_confirmed_var.get())
        if not is_set_product:
            self.save_current_transfer_page_silent()

    def preferred_rakuten_url_code(self, product_code: str, current_value: str) -> str:
        latest: tuple[float, str] | None = None
        for pattern in ("zr_item*.csv", "parent_item*.csv"):
            for path in self.base_dir.glob(pattern):
                rows = read_csv_dicts(path)
                for row in rows:
                    if clean(row.get("コード(更新時使用)")) != product_code:
                        continue
                    url_code = clean(row.get("楽天商品管理番号(URL)"))
                    if url_code and (latest is None or path.stat().st_mtime > latest[0]):
                        latest = (path.stat().st_mtime, url_code)
        return latest[1] if latest else current_value

    def close_window(self) -> None:
        self.save_current_product_silent()
        self.window.destroy()
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

    def on_variant_selected(self, event=None) -> None:
        selected = self.variant_tree.selection()
        if not selected:
            return
        values = self.variant_tree.item(selected[0], "values")
        self.current_variant_code = str(values[0])
        self.variant_code_var.set(str(values[0]))
        self.variant_color_var.set(str(values[1]))
        self.variant_size_var.set(str(values[2]))
        self.variant_jan_code_var.set(str(values[3]))
        self.variant_sold_out_var.set(clean(values[4]) == "✓")
        self.variant_color_order_var.set(str(values[5]))
        self.variant_size_order_var.set(str(values[6]))

    def update_product_url(self) -> None:
        self.product_url_var.set(self.build_product_url())

    def build_product_url(self) -> str:
        shop = self.db.get_setting("rakuten_shop_url", "").strip().strip("/")
        code = self.rakuten_code_var.get().strip().strip("/")
        if not shop or not code:
            return ""
        if shop.startswith("http://") or shop.startswith("https://"):
            shop = shop.rstrip("/").split("/")[-1]
        return f"https://item.rakuten.co.jp/{shop}/{code}/"

    def choose_inventory_file(self) -> None:
        initial_dir = self.db.get_setting("inventory_network_folder", "") or self.db.get_setting("last_inventory_file_dir", "") or str(self.base_dir)
        path = filedialog.askopenfilename(
            parent=self.window,
            initialdir=initial_dir,
            title="在庫Excelファイルを選択",
            filetypes=[("Excel", "*.xls *.xlsx *.xlsm"), ("All files", "*.*")],
        )
        self.window.lift()
        self.window.focus_force()
        if path:
            normalized = normalize_windows_path(path)
            self.inventory_file_var.set(normalized)
            self.db.set_setting("last_inventory_file_dir", str(Path(normalized).parent))
            self.save_current_product_silent()

    def open_inventory_file(self) -> None:
        path = normalize_windows_path(self.inventory_file_var.get())
        if not path:
            messagebox.showwarning("ファイル未設定", "在庫Excelファイルを指定してください。", parent=self.window)
            self.window.lift()
            self.window.focus_force()
            return
        self.save_current_product_silent()
        if not os.path.exists(path):
            messagebox.showerror("ファイルなし", f"在庫Excelファイルが見つかりません。\n{path}", parent=self.window)
            self.window.lift()
            self.window.focus_force()
            return
        try:
            self.excel_start_col_var.set(normalize_excel_start_col(self.excel_start_col_var.get()))
            helper = TransferWindow.__new__(TransferWindow)
            helper.db = self.db
            helper.base_dir = self.base_dir
            helper.window = self.window
            workbook, worksheet, excel = TransferWindow.open_target_workbook(
                helper,
                path,
                self.sheet_name_var.get(),
                self.excel_start_col_var.get(),
            )
            workbook.Activate()
            worksheet.Activate()
            TransferWindow.bring_excel_to_front(helper, excel)
        except Exception as exc:
            messagebox.showerror("ファイルを開けません", f"{exc}\n{path}", parent=self.window)
            self.window.lift()
            self.window.focus_force()

    def save_product(self) -> None:
        if not self.current_product_code:
            messagebox.showwarning("商品未選択", "商品を選択してください。", parent=self.window)
            return
        product = next((row for row in self.products if row["product_code"] == self.current_product_code), None)
        is_set_product = bool(product and int(product["is_set"]))
        try:
            quantity_multiplier = 1 if is_set_product else int(float(self.quantity_multiplier_var.get().strip() or "1"))
        except ValueError:
            messagebox.showerror("入力エラー", "記入数量倍率は1以上の数値で入力してください。", parent=self.window)
            return
        if quantity_multiplier < 1:
            messagebox.showerror("入力エラー", "記入数量倍率は1以上で入力してください。", parent=self.window)
            return
        try:
            min_stock_quantity = 3 if is_set_product else int(float(self.min_stock_quantity_var.get().strip() or "3"))
        except ValueError:
            messagebox.showerror("入力エラー", "最低在庫数は数値で入力してください。", parent=self.window)
            return
        legacy_inventory_file, legacy_sheet_name, legacy_start_col = self.legacy_inventory_values_for_current_product()
        self.db.update_product_settings(
            self.current_product_code,
            self.display_name_var.get().strip(),
            self.preferred_rakuten_url_code(self.current_product_code, self.rakuten_code_var.get().strip()),
            self.jan_code_var.get().strip(),
            "" if is_set_product else legacy_inventory_file,
            "" if is_set_product else legacy_sheet_name,
            self.thumbnail_url_var.get().strip(),
            1,
            min_stock_quantity,
            "A" if is_set_product else legacy_start_col,
            False if is_set_product else self.manual_input_var.get(),
        )
        if not is_set_product:
            self.db.set_product_auto_write_confirmed(self.current_product_code, self.auto_write_confirmed_var.get())
            self.save_current_transfer_page_silent()
        self.refresh_products()
        if self.current_product_code in self.product_tree.get_children():
            self.product_tree.selection_set(self.current_product_code)
            self.product_tree.focus(self.current_product_code)
        messagebox.showinfo("保存", "商品設定を保存しました。", parent=self.window)
        self.window.lift()
        self.window.focus_force()

    def save_variant(self) -> None:
        if not self.current_variant_code:
            messagebox.showwarning("子SKU未選択", "子SKUを選択してください。", parent=self.window)
            return
        try:
            color_order = int(float(self.variant_color_order_var.get().strip() or "0"))
            size_order = int(float(self.variant_size_order_var.get().strip() or "0"))
        except ValueError:
            messagebox.showerror("入力エラー", "カラー順とサイズ順は数値で入力してください。", parent=self.window)
            return
        self.db.update_variant_settings(
            self.current_variant_code,
            self.variant_color_var.get().strip(),
            self.variant_size_var.get().strip(),
            self.variant_jan_code_var.get().strip(),
            color_order,
            size_order,
            self.variant_sold_out_var.get(),
        )
        self.refresh_variants()
        self.refresh_rule_color_order()
        self.update_transfer_pattern_preview()
        if self.current_variant_code in self.variant_tree.get_children():
            self.variant_tree.selection_set(self.current_variant_code)
            self.variant_tree.focus(self.current_variant_code)
        messagebox.showinfo("保存", "子SKU設定を保存しました。", parent=self.window)
        self.window.lift()
        self.window.focus_force()

    def move_selected_color(self, direction: int) -> None:
        if not self.current_product_code:
            messagebox.showwarning("商品未選択", "商品を選択してください。", parent=self.window)
            return
        color = self.variant_color_var.get().strip()
        if not color:
            messagebox.showwarning("カラー未選択", "カラーを含む子SKUを選択してください。", parent=self.window)
            return
        self.db.move_product_color(self.current_product_code, color, direction)
        self.refresh_variants()
        self.refresh_rule_color_order()
        self.update_transfer_pattern_preview()

    def open_product_url(self) -> None:
        self.update_product_url()
        url = self.product_url_var.get()
        if not url:
            messagebox.showwarning("URLなし", "店舗URLと楽天URLコードを入力してください。", parent=self.window)
            return
        webbrowser.open(url)

    def load_thumbnail(self, from_saved: bool = False) -> None:
        if Image is None or ImageTk is None:
            self.clear_image("Pillow が未導入のため画像表示できません。楽天ページを開いて確認してください。")
            return
        self.update_product_url()
        saved_url = self.thumbnail_url_var.get().strip()
        product_url = self.product_url_var.get()
        if saved_url:
            cache_path = thumbnail_cache_path(self.base_dir, saved_url)
            if cache_path.exists():
                try:
                    self.show_image(saved_url, cache_path.read_bytes(), True)
                    return
                except Exception:
                    pass
        if not saved_url and not product_url:
            messagebox.showwarning("URLなし", "店舗URLと楽天URLコードを入力してください。", parent=self.window)
            return
        self.clear_image("サムネ取得中...")
        thread = threading.Thread(target=self._load_thumbnail_worker, args=(saved_url, product_url, from_saved), daemon=True)
        thread.start()

    def _load_thumbnail_worker(self, saved_url: str, product_url: str, from_saved: bool) -> None:
        try:
            image_url = saved_url or self.fetch_og_image(product_url)
            if not image_url:
                raise ValueError("商品ページからサムネURLを取得できませんでした。")
            data = self.fetch_bytes(image_url)
            self.window.after(0, lambda: self.show_image(image_url, data, from_saved))
        except Exception as exc:
            message = f"サムネ取得失敗:\n{exc}"
            self.window.after(0, lambda message=message: self.clear_image(message))

    def fetch_og_image(self, product_url: str) -> str:
        html = self.fetch_bytes(product_url).decode("utf-8", errors="ignore")
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return match.group(1).replace("&amp;", "&")
        return ""

    def fetch_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()

    def show_image(self, image_url: str, data: bytes, from_saved: bool) -> None:
        img = Image.open(BytesIO(data))
        img.thumbnail((145, 145))
        self.photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.photo, text="")
        if not from_saved:
            self.thumbnail_url_var.set(image_url)

    def clear_image(self, text: str) -> None:
        self.photo = None
        self.image_label.config(image="", text=text)


class FunctionSettingsWindow:
    def __init__(self, root: Tk, db: AppDB, base_dir: Path, on_master_reset=None) -> None:
        self.db = db
        self.base_dir = base_dir
        self.on_master_reset = on_master_reset
        self.window = Toplevel(root)
        self.window.title("機能設定")
        self.window.geometry("840x760")
        self.shop_url_var = StringVar(value=self.db.get_setting("rakuten_shop_url", ""))
        self.inventory_network_folder_var = StringVar(value=self.db.get_setting("inventory_network_folder", ""))
        self.order_csv_default_folder_var = StringVar(value=self.db.get_setting("order_csv_default_folder", ""))
        self.temp_pdf_watch_folder_var = StringVar(value=self.db.get_setting("temp_pdf_watch_folder", ""))
        self.temp_pdf_watch_interval_var = StringVar(value=self.db.get_setting("temp_pdf_watch_interval_seconds", "1"))
        self.auto_open_inventory_var = BooleanVar(value=self.db.get_setting("auto_open_inventory_on_bulk", "0") == "1")
        self.auto_open_pdf_var = BooleanVar(value=self.db.get_setting("auto_open_pdf_after_export", "1") != "0")
        self.temp_pdf_bring_front_var = BooleanVar(value=self.db.get_setting("temp_pdf_bring_front_after_open", "1") != "0")
        self.temp_pdf_open_print_dialog_var = BooleanVar(value=self.db.get_setting("temp_pdf_open_print_dialog_after_open", "0") == "1")
        self.temp_pdf_print_delay_var = StringVar(value=self.db.get_setting("temp_pdf_print_dialog_delay_seconds", "1.5"))
        self.pdf_retention_days_var = StringVar(value=self.db.get_setting("pdf_retention_days", "0"))
        self.pdf_font_name_var = StringVar(value=self.db.get_setting("pdf_font_name", "メイリオ"))
        self.pdf_font_size_var = StringVar(value=self.db.get_setting("pdf_font_size", "10"))
        self.pdf_show_status_var = BooleanVar(value=self.db.get_setting("pdf_show_status", "0") != "0")
        self.pdf_show_order_var = BooleanVar(value=self.db.get_setting("pdf_show_order", "0") != "0")
        self.pdf_show_color_total_var = BooleanVar(value=self.db.get_setting("pdf_show_color_total", "0") != "0")
        self.pdf_width_maker_var = StringVar(value=self.db.get_setting("pdf_width_maker_mm", "20"))
        self.pdf_width_product_var = StringVar(value=self.db.get_setting("pdf_width_product_mm", "60"))
        self.pdf_width_color_var = StringVar(value=self.db.get_setting("pdf_width_color_mm", "35"))
        self.pdf_width_total_var = StringVar(value=self.db.get_setting("pdf_width_total_mm", "10"))
        self.path_replace_from_var = StringVar(value=self.db.get_setting("inventory_path_replace_from", ""))
        self.path_replace_to_var = StringVar(value=self.db.get_setting("inventory_path_replace_to", ""))
        self.default_copy_title_var = StringVar(value=self.db.get_setting("default_copy_title", "ネット"))
        self.default_title_tabs_var = StringVar(value=self.db.get_setting("default_title_tabs", "0"))
        self.default_color_gap_tabs_var = StringVar(value=self.db.get_setting("default_color_gap_tabs", "1"))
        self.default_tail_tabs_var = StringVar(value=self.db.get_setting("default_tail_tabs", "2"))
        self.default_append_date_var = BooleanVar(value=self.db.get_setting("default_append_date", "1") != "0")
        self.transfer_date_format_var = StringVar(value=self.db.get_setting("transfer_date_format", "yyyy/mm/dd"))
        self.default_transfer_pattern_var = StringVar(value=self.db.get_setting("default_transfer_pattern", ""))
        self.excel_overwrite_var = BooleanVar(value=self.db.get_setting("excel_overwrite_existing", "0") == "1")
        self.excel_transfer_mode_var = StringVar(value=self.db.get_setting("excel_transfer_mode", "confirm"))
        self.excel_same_day_add_var = BooleanVar(value=self.db.get_setting("excel_same_day_title_add", "0") == "1")
        same_day_mode = self.db.get_setting("excel_same_day_add_mode", "previous")
        self.excel_same_day_add_mode_var = StringVar(value=same_day_mode if same_day_mode in {"previous", "title_date"} else "previous")
        self.excel_same_day_search_rows_var = StringVar(value=self.db.get_setting("excel_same_day_search_rows", "10"))
        self.excel_same_day_missing_action_var = StringVar(value=self.db.get_setting("excel_same_day_missing_action", "confirm"))
        self.excel_protected_row_keywords_var = StringVar(value=self.db.get_setting("excel_protected_row_keywords", "確保"))
        candidate_mode = self.db.get_setting("candidate_confirm_mode", "focus_excel")
        self.candidate_confirm_mode_var = StringVar(value=candidate_mode if candidate_mode in {"focus_excel", "highlight_cell"} else "focus_excel")
        self.stock_alert_enabled_var = BooleanVar(value=self.db.get_setting("stock_alert_enabled", "0") == "1")
        self.stock_alert_labels_var = StringVar(value=self.db.get_setting("stock_alert_labels", "残数"))
        self.transfer_show_manual_copy_var = BooleanVar(value=self.db.get_setting("transfer_show_manual_copy", "0") == "1")
        self.backup_before_reset_var = BooleanVar(value=self.db.get_setting("backup_before_reset", "1") != "0")
        self.rakuten_csv_status_var = StringVar(value=self.db.get_setting("rakuten_csv_status", "楽天商品CSVは未取込です。"))
        self.thumbnail_cache_status_var = StringVar(value=self.db.get_setting("thumbnail_cache_status", "サムネキャッシュは未実行です。"))
        self.thumbnail_cache_progress_var = DoubleVar(value=0)
        self.status_var = StringVar()
        self.window.protocol("WM_DELETE_WINDOW", self.save_all_and_close)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = Frame(self.window)
        outer.pack(fill=BOTH, expand=True)
        canvas = Canvas(outer, highlightthickness=0)
        self.settings_canvas = canvas
        y_scroll = Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=y_scroll.set)
        y_scroll.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        frame = Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=event.width))

        def on_mousewheel(event):
            delta = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
            if delta:
                canvas.yview_scroll(delta, "units")

        frame.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_mousewheel))
        frame.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        canvas.bind("<MouseWheel>", on_mousewheel)
        self.window.bind("<MouseWheel>", on_mousewheel)
        frame.configure(padx=14, pady=14)

        shop_group = ttk.LabelFrame(frame, text="楽天 店舗URL")
        shop_group.pack(fill=X, pady=(0, 12))
        Label(shop_group, text="店舗URL:").pack(side=LEFT, padx=(8, 4), pady=8)
        Entry(shop_group, textvariable=self.shop_url_var, width=45).pack(side=LEFT, padx=(0, 8), pady=8)

        csv_group = ttk.LabelFrame(frame, text="楽天商品CSV")
        csv_group.pack(fill=X, pady=(0, 12))
        csv_buttons = Frame(csv_group)
        csv_buttons.pack(fill=X, padx=8, pady=(8, 4))
        Button(csv_buttons, text="normal-item CSVを取り込む", command=self.import_rakuten_item_csv).pack(side=LEFT, padx=(0, 8))
        Button(csv_buttons, text="サムネキャッシュ", command=self.cache_thumbnails).pack(side=LEFT)
        ttk.Progressbar(csv_buttons, variable=self.thumbnail_cache_progress_var, maximum=100, length=220).pack(side=LEFT, padx=(8, 0), fill=X, expand=True)
        Label(csv_group, textvariable=self.rakuten_csv_status_var, justify=LEFT, fg="#374151", wraplength=680).pack(anchor=W, padx=8, pady=(0, 2))
        Label(csv_group, textvariable=self.thumbnail_cache_status_var, justify=LEFT, fg="#374151", wraplength=680).pack(anchor=W, padx=8, pady=(0, 6))
        Label(
            csv_group,
            text="normal-item CSVから 商品管理番号（商品URL） と 商品画像パス1 を読み取り、商品マスタのサムネURLを更新します。",
            wraplength=680,
            justify=LEFT,
            fg="#555555",
        ).pack(anchor=W, padx=8, pady=(0, 8))

        network_group = ttk.LabelFrame(frame, text="ネットワーク転記先")
        network_group.pack(fill=X, pady=(0, 12))
        row1 = Frame(network_group)
        row1.pack(fill=X, padx=8, pady=(8, 4))
        Label(row1, text="既定フォルダ:").pack(side=LEFT)
        Entry(row1, textvariable=self.inventory_network_folder_var, width=54).pack(side=LEFT, fill=X, expand=True, padx=(4, 6))
        Button(row1, text="参照", command=self.browse_inventory_network_folder).pack(side=LEFT, padx=(0, 4))
        row2 = Frame(network_group)
        row2.pack(fill=X, padx=8, pady=(0, 8))
        ttk.Checkbutton(
            row2,
            text="転記画面が全体モードのとき、コピーして次へ実行後に転記先Excelを開く",
            variable=self.auto_open_inventory_var,
        ).pack(side=LEFT)

        order_csv_group = ttk.LabelFrame(frame, text="受注CSV")
        order_csv_group.pack(fill=X, pady=(0, 12))
        order_csv_row = Frame(order_csv_group)
        order_csv_row.pack(fill=X, padx=8, pady=8)
        Label(order_csv_row, text="既定フォルダ:").pack(side=LEFT)
        Entry(order_csv_row, textvariable=self.order_csv_default_folder_var, width=54).pack(side=LEFT, fill=X, expand=True, padx=(4, 6))
        Button(order_csv_row, text="参照", command=self.browse_order_csv_default_folder).pack(side=LEFT)
        temp_pdf_watch_row = Frame(order_csv_group)
        temp_pdf_watch_row.pack(fill=X, padx=8, pady=(0, 8))
        Label(temp_pdf_watch_row, text="一時PDF監視フォルダ:").pack(side=LEFT)
        Entry(temp_pdf_watch_row, textvariable=self.temp_pdf_watch_folder_var, width=48).pack(side=LEFT, fill=X, expand=True, padx=(4, 6))
        Button(temp_pdf_watch_row, text="参照", command=self.browse_temp_pdf_watch_folder).pack(side=LEFT)
        temp_pdf_interval_row = Frame(order_csv_group)
        temp_pdf_interval_row.pack(fill=X, padx=8, pady=(0, 8))
        Label(temp_pdf_interval_row, text="監視間隔:").pack(side=LEFT)
        ttk.Combobox(
            temp_pdf_interval_row,
            textvariable=self.temp_pdf_watch_interval_var,
            values=("1", "2", "3", "5"),
            width=6,
            state="readonly",
            justify=RIGHT,
        ).pack(side=LEFT, padx=(4, 4))
        Label(temp_pdf_interval_row, text="秒", fg="#555555").pack(side=LEFT)

        replace_group = ttk.LabelFrame(frame, text="転記先パス一括置換")
        replace_group.pack(fill=X, pady=(0, 12))
        replace_row1 = Frame(replace_group)
        replace_row1.pack(fill=X, padx=8, pady=(8, 4))
        Label(replace_row1, text="置換前:", width=8, anchor=W).pack(side=LEFT)
        Entry(replace_row1, textvariable=self.path_replace_from_var, width=62).pack(side=LEFT, fill=X, expand=True)
        replace_row2 = Frame(replace_group)
        replace_row2.pack(fill=X, padx=8, pady=(0, 4))
        Label(replace_row2, text="置換後:", width=8, anchor=W).pack(side=LEFT)
        Entry(replace_row2, textvariable=self.path_replace_to_var, width=62).pack(side=LEFT, fill=X, expand=True)
        replace_row3 = Frame(replace_group)
        replace_row3.pack(fill=X, padx=8, pady=(0, 8))
        Button(replace_row3, text="対象件数を確認", command=self.preview_inventory_path_replace, width=14).pack(side=LEFT, padx=(0, 8))
        Button(replace_row3, text="前後入替", command=self.swap_inventory_path_replace_inputs, width=10).pack(side=LEFT, padx=(0, 8))
        Button(replace_row3, text="置換実行", command=self.execute_inventory_path_replace, width=12, bg="#FEE2E2", activebackground="#FECACA").pack(side=LEFT)
        Label(
            replace_group,
            text="商品設定に保存されている転記先Excelパスだけを置換します。Excelファイル自体は移動・コピーしません。",
            wraplength=680,
            justify=LEFT,
            fg="#555555",
        ).pack(anchor=W, padx=8, pady=(0, 8))

        rule_group = ttk.LabelFrame(frame, text="Excel転記ルール初期値")
        rule_group.pack(fill=X, pady=(0, 12))
        rule_row1 = Frame(rule_group)
        rule_row1.pack(fill=X, padx=8, pady=(8, 4))
        Label(rule_row1, text="タイトル").pack(side=LEFT)
        Entry(rule_row1, textvariable=self.default_copy_title_var, width=16).pack(side=LEFT, padx=(4, 10))
        Label(rule_row1, text="タイトル後Tab").pack(side=LEFT)
        Entry(rule_row1, textvariable=self.default_title_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(4, 10))
        Label(rule_row1, text="カラー間Tab").pack(side=LEFT)
        Entry(rule_row1, textvariable=self.default_color_gap_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(4, 10))
        Label(rule_row1, text="末尾Tab").pack(side=LEFT)
        Entry(rule_row1, textvariable=self.default_tail_tabs_var, width=4, justify=RIGHT).pack(side=LEFT, padx=(4, 10))
        rule_row2 = Frame(rule_group)
        rule_row2.pack(fill=X, padx=8, pady=(0, 4))
        ttk.Checkbutton(rule_row2, text="日付を末尾に追加", variable=self.default_append_date_var).pack(side=LEFT, padx=(0, 16))
        Label(rule_row2, text="日付形式").pack(side=LEFT, padx=(0, 4))
        ttk.Combobox(
            rule_row2,
            textvariable=self.transfer_date_format_var,
            values=list(self.db.date_format_options().keys()),
            width=14,
            state="readonly",
        ).pack(side=LEFT, padx=(0, 16))
        ttk.Checkbutton(rule_row2, text="Excel転記時に入力済みセルを上書きする", variable=self.excel_overwrite_var).pack(side=LEFT, padx=(0, 16))
        rule_row_pattern = Frame(rule_group)
        rule_row_pattern.pack(fill=X, padx=8, pady=(0, 8))
        Label(rule_row_pattern, text="転記パターン").pack(side=LEFT)
        Entry(rule_row_pattern, textvariable=self.default_transfer_pattern_var, width=74).pack(side=LEFT, fill=X, expand=True, padx=(4, 0))
        rule_row3 = Frame(rule_group)
        rule_row3.pack(fill=X, padx=8, pady=(0, 8))
        Label(rule_row3, text="Excel転記モード:").pack(side=LEFT, padx=(0, 8))
        ttk.Radiobutton(rule_row3, text="自動（転記して保存・次へ）", variable=self.excel_transfer_mode_var, value="auto").pack(side=LEFT, padx=(0, 14))
        ttk.Radiobutton(rule_row3, text="在庫確認（転記後に停止）", variable=self.excel_transfer_mode_var, value="confirm").pack(side=LEFT)
        rule_row4 = Frame(rule_group)
        rule_row4.pack(fill=X, padx=8, pady=(0, 4))
        ttk.Checkbutton(rule_row4, text="同日同タイトル行へ加算上書き", variable=self.excel_same_day_add_var).pack(side=LEFT, padx=(0, 14))
        Label(rule_row4, text="検索行数").pack(side=LEFT)
        Entry(rule_row4, textvariable=self.excel_same_day_search_rows_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(4, 14))
        Label(rule_row4, text="見つからない場合:").pack(side=LEFT, padx=(0, 6))
        ttk.Radiobutton(rule_row4, text="確認で停止", variable=self.excel_same_day_missing_action_var, value="confirm").pack(side=LEFT, padx=(0, 10))
        ttk.Radiobutton(rule_row4, text="スキップしてログ", variable=self.excel_same_day_missing_action_var, value="skip").pack(side=LEFT)
        rule_row4b = Frame(rule_group)
        rule_row4b.pack(fill=X, padx=8, pady=(0, 4))
        Label(rule_row4b, text="加算方式:").pack(side=LEFT, padx=(0, 8))
        ttk.Radiobutton(rule_row4b, text="前回数量一致で加算", variable=self.excel_same_day_add_mode_var, value="previous").pack(side=LEFT, padx=(0, 14))
        ttk.Radiobutton(rule_row4b, text="タイトル日時一致で加算", variable=self.excel_same_day_add_mode_var, value="title_date").pack(side=LEFT)
        rule_row5 = Frame(rule_group)
        rule_row5.pack(fill=X, padx=8, pady=(0, 8))
        Label(rule_row5, text="書き込み禁止行キーワード").pack(side=LEFT)
        Entry(rule_row5, textvariable=self.excel_protected_row_keywords_var, width=34).pack(side=LEFT, padx=(4, 8))
        Label(rule_row5, text="タイトル列のみ判定。例: 確保,予定", fg="#555555").pack(side=LEFT)
        rule_row6 = Frame(rule_group)
        rule_row6.pack(fill=X, padx=8, pady=(0, 8))
        Label(rule_row6, text="候補セル確認:").pack(side=LEFT, padx=(0, 8))
        ttk.Radiobutton(rule_row6, text="Excelへフォーカス", variable=self.candidate_confirm_mode_var, value="focus_excel").pack(side=LEFT, padx=(0, 14))
        ttk.Radiobutton(rule_row6, text="セルをカラー表示", variable=self.candidate_confirm_mode_var, value="highlight_cell").pack(side=LEFT, padx=(0, 10))
        Label(rule_row6, text="Excelへフォーカスは候補セル選択後に転記画面へ自動復帰しません。", fg="#555555").pack(side=LEFT)
        alert_group = ttk.LabelFrame(frame, text="在庫残数アラート")
        alert_group.pack(fill=X, pady=(0, 12))
        alert_row1 = Frame(alert_group)
        alert_row1.pack(fill=X, padx=8, pady=(8, 4))
        ttk.Checkbutton(alert_row1, text="Excel転記時に残数を確認する", variable=self.stock_alert_enabled_var).pack(side=LEFT, padx=(0, 14))
        Label(alert_row1, text="残数ラベル候補").pack(side=LEFT)
        Entry(alert_row1, textvariable=self.stock_alert_labels_var, width=34).pack(side=LEFT, padx=(4, 0))
        Label(alert_group, text="カンマ区切り。例: 残数,在庫残,現在庫", fg="#555555").pack(anchor=W, padx=8, pady=(0, 8))

        transfer_ui_group = ttk.LabelFrame(frame, text="転記画面表示")
        transfer_ui_group.pack(fill=X, pady=(0, 12))
        transfer_ui_row = Frame(transfer_ui_group)
        transfer_ui_row.pack(fill=X, padx=8, pady=8)
        ttk.Checkbutton(
            transfer_ui_row,
            text="転記画面に手動コピーを表示する",
            variable=self.transfer_show_manual_copy_var,
        ).pack(side=LEFT)

        pdf_group = ttk.LabelFrame(frame, text="PDF")
        pdf_group.pack(fill=X, pady=(0, 12))
        pdf_row1 = Frame(pdf_group)
        pdf_row1.pack(fill=X, padx=8, pady=(8, 4))
        Label(pdf_row1, text="フォント:").pack(side=LEFT)
        ttk.Combobox(
            pdf_row1,
            textvariable=self.pdf_font_name_var,
            values=list(self.db.pdf_font_options().keys()),
            width=22,
            state="readonly",
        ).pack(side=LEFT, padx=(4, 14))
        Label(pdf_row1, text="本文サイズ:").pack(side=LEFT)
        ttk.Combobox(
            pdf_row1,
            textvariable=self.pdf_font_size_var,
            values=["6", "7", "8", "9", "10", "11", "12", "13", "14"],
            width=5,
            state="readonly",
        ).pack(side=LEFT, padx=(4, 0))
        pdf_width_row = Frame(pdf_group)
        pdf_width_row.pack(fill=X, padx=8, pady=(0, 4))
        Label(pdf_width_row, text="カラム幅(mm):").pack(side=LEFT, padx=(0, 6))
        Label(pdf_width_row, text="メーカー").pack(side=LEFT)
        Entry(pdf_width_row, textvariable=self.pdf_width_maker_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(3, 10))
        Label(pdf_width_row, text="商品名").pack(side=LEFT)
        Entry(pdf_width_row, textvariable=self.pdf_width_product_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(3, 10))
        Label(pdf_width_row, text="カラー").pack(side=LEFT)
        Entry(pdf_width_row, textvariable=self.pdf_width_color_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(3, 10))
        Label(pdf_width_row, text="小計").pack(side=LEFT)
        Entry(pdf_width_row, textvariable=self.pdf_width_total_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(3, 10))
        Label(pdf_width_row, text="サイズ/数量は残り幅で自動", fg="#555555").pack(side=LEFT)
        ttk.Checkbutton(
            pdf_group,
            text="状態列を表示する",
            variable=self.pdf_show_status_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        ttk.Checkbutton(
            pdf_group,
            text="順列を表示する",
            variable=self.pdf_show_order_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        ttk.Checkbutton(
            pdf_group,
            text="カラーごとの小計列を表示する",
            variable=self.pdf_show_color_total_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        ttk.Checkbutton(
            pdf_group,
            text="PDF出力後に自動で開く",
            variable=self.auto_open_pdf_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        ttk.Checkbutton(
            pdf_group,
            text="一時PDFを開いたあと最前面にする",
            variable=self.temp_pdf_bring_front_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        ttk.Checkbutton(
            pdf_group,
            text="一時PDFを開いたあと印刷ダイアログを開く",
            variable=self.temp_pdf_open_print_dialog_var,
        ).pack(anchor=W, padx=8, pady=(0, 2))
        pdf_print_delay_row = Frame(pdf_group)
        pdf_print_delay_row.pack(fill=X, padx=8, pady=(0, 8))
        Label(pdf_print_delay_row, text="印刷ダイアログ待ち:").pack(side=LEFT)
        ttk.Combobox(
            pdf_print_delay_row,
            textvariable=self.temp_pdf_print_delay_var,
            values=("0.5", "1", "1.5", "2", "3", "5"),
            width=6,
            state="readonly",
            justify=RIGHT,
        ).pack(side=LEFT, padx=(4, 4))
        Label(pdf_print_delay_row, text="秒", fg="#555555").pack(side=LEFT)
        pdf_cleanup_row = Frame(pdf_group)
        pdf_cleanup_row.pack(fill=X, padx=8, pady=(0, 8))
        Label(pdf_cleanup_row, text="PDF保存日数:").pack(side=LEFT)
        Entry(pdf_cleanup_row, textvariable=self.pdf_retention_days_var, width=5, justify=RIGHT).pack(side=LEFT, padx=(4, 4))
        Label(pdf_cleanup_row, text="日（0で自動削除しない）", fg="#555555").pack(side=LEFT)

        reset_group = ttk.LabelFrame(frame, text="ユーザー設定リセット")
        reset_group.pack(fill=X, pady=(0, 12))
        Button(
            reset_group,
            text="マスタリセット",
            command=self.reset_master_data,
            width=24,
            bg="#FEE2E2",
            activebackground="#FECACA",
        ).pack(anchor=W, padx=8, pady=(8, 4))
        Button(
            reset_group,
            text="ユーザー設定オールリセット",
            command=self.reset_user_settings,
            width=24,
            bg="#EF4444",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
        ).pack(anchor=W, padx=8, pady=(0, 4))
        ttk.Checkbutton(
            reset_group,
            text="リセット前にDBバックアップを作成する",
            variable=self.backup_before_reset_var,
        ).pack(anchor=W, padx=8, pady=(2, 4))
        Button(
            reset_group,
            text="今すぐDBバックアップ",
            command=self.create_manual_user_settings_backup,
            width=24,
        ).pack(anchor=W, padx=8, pady=(0, 4))
        Label(
            reset_group,
            text="ユーザー設定リセットは、転記先Excel、シート名、サムネ、自動OK、記入数量倍率、カラー/サイズ手修正、色順/サイズ順、商品別転記ルールを初期化します。マスタリセットはCSV由来の商品・SKU・セット構成を削除し、ユーザー設定と受注データは残します。",
            wraplength=740,
            justify=LEFT,
            fg="#555555",
        ).pack(anchor=W, padx=8, pady=(0, 8))

        Button(frame, text="保存して閉じる", command=self.save_all_and_close, width=14).pack(anchor=E)

    def browse_inventory_network_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self.window,
            initialdir=self.inventory_network_folder_var.get() or str(Path.home()),
            title="転記先Excelの既定フォルダを選択",
        )
        self.window.lift()
        self.window.focus_force()
        if path:
            self.inventory_network_folder_var.set(normalize_windows_path(path))

    def browse_order_csv_default_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self.window,
            initialdir=self.order_csv_default_folder_var.get() or str(self.base_dir),
            title="受注CSVの既定フォルダを選択",
        )
        self.window.lift()
        self.window.focus_force()
        if path:
            self.order_csv_default_folder_var.set(normalize_windows_path(path))

    def browse_temp_pdf_watch_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self.window,
            initialdir=self.temp_pdf_watch_folder_var.get() or self.order_csv_default_folder_var.get() or str(self.base_dir),
            title="一時PDF監視フォルダを選択",
        )
        self.window.lift()
        self.window.focus_force()
        if path:
            self.temp_pdf_watch_folder_var.set(normalize_windows_path(path))

    def normalized_replace_inputs(self) -> tuple[str, str]:
        return normalize_windows_path(self.path_replace_from_var.get()), normalize_windows_path(self.path_replace_to_var.get())

    def preview_inventory_path_replace(self) -> None:
        old_text, new_text = self.normalized_replace_inputs()
        self.db.set_setting("inventory_path_replace_from", old_text)
        self.db.set_setting("inventory_path_replace_to", new_text)
        if not old_text:
            messagebox.showwarning("置換前未入力", "置換前のパスまたは文字列を入力してください。", parent=self.window)
            return
        count, samples = self.db.preview_inventory_path_replace(old_text, new_text)
        if count == 0:
            messagebox.showinfo("対象なし", "置換対象の転記先パスはありません。", parent=self.window)
            return
        lines = [f"対象: {count}件", "", "置換例:"]
        for name, before, after in samples:
            lines.append(f"・{name}")
            lines.append(f"  前: {before}")
            lines.append(f"  後: {after}")
        messagebox.showinfo("置換対象確認", "\n".join(lines), parent=self.window)

    def swap_inventory_path_replace_inputs(self) -> None:
        old_text = normalize_windows_path(self.path_replace_from_var.get())
        new_text = normalize_windows_path(self.path_replace_to_var.get())
        self.path_replace_from_var.set(new_text)
        self.path_replace_to_var.set(old_text)
        self.db.set_setting("inventory_path_replace_from", new_text)
        self.db.set_setting("inventory_path_replace_to", old_text)

    def execute_inventory_path_replace(self) -> None:
        old_text, new_text = self.normalized_replace_inputs()
        self.db.set_setting("inventory_path_replace_from", old_text)
        self.db.set_setting("inventory_path_replace_to", new_text)
        if not old_text:
            messagebox.showwarning("置換前未入力", "置換前のパスまたは文字列を入力してください。", parent=self.window)
            return
        count, samples = self.db.preview_inventory_path_replace(old_text, new_text)
        if count == 0:
            messagebox.showinfo("対象なし", "置換対象の転記先パスはありません。", parent=self.window)
            return
        sample_text = ""
        if samples:
            name, before, after = samples[0]
            sample_text = f"\n\n例: {name}\n前: {before}\n後: {after}"
        ok = messagebox.askyesno(
            "転記先パス一括置換",
            f"商品設定の転記先パス {count}件を置換します。\nこの操作はDB上のリンク先を書き換えます。実行しますか？{sample_text}",
            parent=self.window,
        )
        if not ok:
            return
        updated = self.db.replace_inventory_paths(old_text, new_text)
        messagebox.showinfo("置換完了", f"転記先パスを {updated}件 置換しました。", parent=self.window)

    def reset_user_settings(self) -> None:
        ok = messagebox.askyesno(
            "ユーザー設定オールリセット",
            "後から設定したユーザー設定を初期化します。\n"
            "転記先Excel、シート名、サムネ、自動OK、記入数量倍率、カラー/サイズ手修正、色順/サイズ順、商品別転記ルールが削除されます。\n"
            "CSVマスタ由来のデータは残ります。実行しますか？",
            parent=self.window,
        )
        if not ok:
            return
        backup_path = self.create_reset_backup("user_settings_reset")
        self.db.reset_user_settings()
        message = "ユーザー設定をリセットしました。"
        if backup_path:
            message += f"\nバックアップ: {backup_path}"
        messagebox.showinfo("リセット完了", message, parent=self.window)

    def reset_master_data(self) -> None:
        if self.on_master_reset:
            self.on_master_reset(parent=self.window, create_backup=self.backup_before_reset_var.get())
            return
        ok = messagebox.askyesno(
            "マスタリセット",
            "CSV由来の商品・子SKU・モールSKU・セット構成マスタを削除します。\n"
            "転記先Excel、サムネ、自動OK、カラー順、転記ルールなどのユーザー設定は残します。\n"
            "受注データも残します。実行しますか？",
            parent=self.window,
        )
        if not ok:
            return
        backup_path = self.create_reset_backup("master_reset")
        self.db.reset_master_data()
        message = "マスタデータをリセットしました。"
        if backup_path:
            message += f"\nバックアップ: {backup_path}"
        messagebox.showinfo("マスタリセット", message, parent=self.window)

    def create_reset_backup(self, label: str) -> Path | None:
        if not self.backup_before_reset_var.get():
            return None
        return self.db.create_backup(self.base_dir / "退避_バックアップ", label)

    def create_manual_user_settings_backup(self) -> None:
        try:
            backup_path = self.db.create_backup(self.base_dir / "退避_バックアップ", "manual_user_settings_backup")
            messagebox.showinfo("DBバックアップ", f"DBバックアップを作成しました。\n{backup_path}", parent=self.window)
        except Exception as exc:
            messagebox.showerror("DBバックアップエラー", str(exc), parent=self.window)

    def parse_int(self, value: str) -> int:
        try:
            return int(float(clean(value) or "0"))
        except ValueError:
            return 0

    def parse_float(self, value: str, default: float) -> float:
        try:
            return float(clean(value) or str(default))
        except ValueError:
            return default

    def save_pdf_width_setting(self, key: str, variable: StringVar, default: float, minimum: float, maximum: float) -> None:
        value = min(maximum, max(minimum, self.parse_float(variable.get(), default)))
        text = f"{value:g}"
        variable.set(text)
        self.db.set_setting(key, text)

    def save_all_and_close(self) -> None:
        self.db.set_setting("rakuten_shop_url", self.shop_url_var.get().strip())
        self.db.set_setting("inventory_network_folder", normalize_windows_path(self.inventory_network_folder_var.get()))
        self.db.set_setting("order_csv_default_folder", normalize_windows_path(self.order_csv_default_folder_var.get()))
        self.db.set_setting("temp_pdf_watch_folder", normalize_windows_path(self.temp_pdf_watch_folder_var.get()))
        self.db.set_setting("temp_pdf_watch_interval_seconds", self.temp_pdf_watch_interval_var.get() or "1")
        old_text, new_text = self.normalized_replace_inputs()
        self.db.set_setting("inventory_path_replace_from", old_text)
        self.db.set_setting("inventory_path_replace_to", new_text)
        self.db.set_setting("auto_open_inventory_on_bulk", "1" if self.auto_open_inventory_var.get() else "0")
        self.db.set_setting("default_copy_title", self.default_copy_title_var.get().strip())
        self.db.set_setting("default_title_tabs", str(max(0, self.parse_int(self.default_title_tabs_var.get()))))
        self.db.set_setting("default_color_gap_tabs", str(max(0, self.parse_int(self.default_color_gap_tabs_var.get()))))
        self.db.set_setting("default_tail_tabs", str(max(0, self.parse_int(self.default_tail_tabs_var.get()))))
        self.db.set_setting("default_append_date", "1" if self.default_append_date_var.get() else "0")
        date_format = self.transfer_date_format_var.get()
        if date_format not in self.db.date_format_options():
            date_format = "yyyy/mm/dd"
        self.db.set_setting("transfer_date_format", date_format)
        self.db.set_setting("default_transfer_pattern", self.default_transfer_pattern_var.get().strip())
        self.db.set_setting("excel_overwrite_existing", "1" if self.excel_overwrite_var.get() else "0")
        mode = self.excel_transfer_mode_var.get() if self.excel_transfer_mode_var.get() in {"auto", "confirm"} else "auto"
        self.db.set_setting("excel_transfer_mode", mode)
        self.db.set_setting("excel_same_day_title_add", "1" if self.excel_same_day_add_var.get() else "0")
        add_mode = self.excel_same_day_add_mode_var.get()
        self.db.set_setting("excel_same_day_add_mode", add_mode if add_mode in {"previous", "title_date"} else "previous")
        self.db.set_setting("excel_same_day_search_rows", str(max(1, self.parse_int(self.excel_same_day_search_rows_var.get()) or 10)))
        missing_action = self.excel_same_day_missing_action_var.get()
        self.db.set_setting("excel_same_day_missing_action", missing_action if missing_action in {"confirm", "skip"} else "confirm")
        self.db.set_setting("excel_protected_row_keywords", self.excel_protected_row_keywords_var.get().strip() or "確保")
        candidate_mode = self.candidate_confirm_mode_var.get()
        self.db.set_setting("candidate_confirm_mode", candidate_mode if candidate_mode in {"focus_excel", "highlight_cell"} else "focus_excel")
        self.db.set_setting("stock_alert_enabled", "1" if self.stock_alert_enabled_var.get() else "0")
        self.db.set_setting("stock_alert_labels", self.stock_alert_labels_var.get().strip() or "残数")
        self.db.set_setting("transfer_show_manual_copy", "1" if self.transfer_show_manual_copy_var.get() else "0")
        self.db.set_setting("pdf_font_name", self.pdf_font_name_var.get().strip() or "HeiseiKakuGo-W5")
        self.db.set_setting("pdf_font_size", str(min(14, max(6, self.parse_int(self.pdf_font_size_var.get()) or 8))))
        self.db.set_setting("pdf_show_status", "1" if self.pdf_show_status_var.get() else "0")
        self.db.set_setting("pdf_show_order", "1" if self.pdf_show_order_var.get() else "0")
        self.db.set_setting("pdf_show_color_total", "1" if self.pdf_show_color_total_var.get() else "0")
        self.save_pdf_width_setting("pdf_width_maker_mm", self.pdf_width_maker_var, 20, 8, 60)
        self.save_pdf_width_setting("pdf_width_product_mm", self.pdf_width_product_var, 60, 20, 100)
        self.save_pdf_width_setting("pdf_width_color_mm", self.pdf_width_color_var, 35, 10, 60)
        self.save_pdf_width_setting("pdf_width_total_mm", self.pdf_width_total_var, 10, 8, 30)
        self.db.set_setting("auto_open_pdf_after_export", "1" if self.auto_open_pdf_var.get() else "0")
        self.db.set_setting("temp_pdf_bring_front_after_open", "1" if self.temp_pdf_bring_front_var.get() else "0")
        self.db.set_setting("temp_pdf_open_print_dialog_after_open", "1" if self.temp_pdf_open_print_dialog_var.get() else "0")
        self.db.set_setting("temp_pdf_print_dialog_delay_seconds", self.temp_pdf_print_delay_var.get() or "1.5")
        self.db.set_setting("pdf_retention_days", str(max(0, self.parse_int(self.pdf_retention_days_var.get()))))
        self.db.set_setting("backup_before_reset", "1" if self.backup_before_reset_var.get() else "0")
        if hasattr(self, "settings_canvas"):
            self.settings_canvas.unbind_all("<MouseWheel>")
        self.window.destroy()

    def import_rakuten_item_csv(self) -> None:
        shop_url = self.shop_url_var.get().strip()
        if not shop_url:
            messagebox.showwarning("店舗URL未設定", "先に店舗URLを入力してください。", parent=self.window)
            self.window.lift()
            self.window.focus_force()
            return
        last_csv_path = self.db.get_setting("rakuten_normal_item_csv_path", "")
        initial_dir = str(Path(last_csv_path).parent) if last_csv_path else str(self.base_dir)
        path = filedialog.askopenfilename(
            parent=self.window,
            initialdir=initial_dir,
            title="楽天 normal-item CSVを選択",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        self.window.lift()
        self.window.focus_force()
        if not path:
            return
        try:
            self.db.set_setting("rakuten_shop_url", shop_url)
            found, updated, missing = self.db.import_rakuten_normal_item_images(Path(path), shop_url)
            message = (
                f"楽天商品CSV: {Path(path).name} / {now_text()}\n"
                f"画像URL検出: {found}件 / 商品マスタ更新: {updated}件 / 商品マスタ未照合: {missing}件"
            )
            self.rakuten_csv_status_var.set(message)
            self.status_var.set("楽天商品CSV取込完了")
            self.db.set_setting("rakuten_normal_item_csv_path", normalize_windows_path(path))
            self.db.set_setting("rakuten_csv_status", message)
        except Exception as exc:
            messagebox.showerror("楽天商品CSV取込エラー", str(exc), parent=self.window)
            self.window.lift()
            self.window.focus_force()

    def cache_thumbnails(self) -> None:
        if Image is None:
            messagebox.showerror("サムネキャッシュ", "Pillow が未導入のため画像キャッシュを作成できません。", parent=self.window)
            self.window.lift()
            self.window.focus_force()
            return
        products = self.db.products_with_thumbnail_urls()
        if not products:
            messagebox.showwarning("サムネキャッシュ", "サムネURLが登録された商品がありません。先に楽天商品CSVを取り込んでください。", parent=self.window)
            self.window.lift()
            self.window.focus_force()
            return
        self.thumbnail_cache_progress_var.set(0)
        self.status_var.set(f"サムネキャッシュ開始: {len(products)}件")
        thread = threading.Thread(target=self.cache_thumbnails_worker, args=(products,), daemon=True)
        thread.start()

    def cache_thumbnails_worker(self, products: list[sqlite3.Row]) -> None:
        cache_dir = self.base_dir / "cache" / "thumbs"
        cache_dir.mkdir(parents=True, exist_ok=True)
        total = len(products)
        ok = 0
        skipped = 0
        failed = 0
        for index, product in enumerate(products, start=1):
            url = clean(product["thumbnail_url"])
            cache_path = thumbnail_cache_path(self.base_dir, url)
            if cache_path.exists():
                skipped += 1
            else:
                try:
                    data = self.fetch_bytes(url)
                    img = Image.open(BytesIO(data))
                    img.thumbnail((300, 300))
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.save(cache_path, "JPEG", quality=85)
                    ok += 1
                except Exception:
                    failed += 1
            if index == total or index % 10 == 0:
                percent = index / total * 100 if total else 100
                self.window.after(
                    0,
                    lambda index=index, total=total, ok=ok, skipped=skipped, failed=failed, percent=percent: (
                        self.thumbnail_cache_progress_var.set(percent),
                        self.status_var.set(f"サムネキャッシュ中: {index}/{total} 保存{ok} 既存{skipped} 失敗{failed}"),
                        self.thumbnail_cache_status_var.set(f"処理中: {index}/{total} 保存{ok} 既存{skipped} 失敗{failed}"),
                    ),
                )
        def finish() -> None:
            message = f"サムネキャッシュ: {now_text()} / 対象{total}件 / 保存{ok} / 既存{skipped} / 失敗{failed}"
            self.thumbnail_cache_progress_var.set(100)
            self.thumbnail_cache_status_var.set(message)
            self.status_var.set("サムネキャッシュ完了")
            self.db.set_setting("thumbnail_cache_status", message)

        self.window.after(0, finish)

    def fetch_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()


class ResolutionRuleWindow:
    def __init__(self, root: Toplevel, db: AppDB, unresolved_row: sqlite3.Row, on_saved=None) -> None:
        self.db = db
        self.unresolved_row = unresolved_row
        self.on_saved = on_saved
        self.window = Toplevel(root)
        self.window.title("既存SKUへ分解登録")
        self.window.geometry("980x620")
        self.search_var = StringVar()
        self.qty_var = StringVar(value="1")
        self.note_var = StringVar()
        self.products: list[sqlite3.Row] = []
        self.variants: list[sqlite3.Row] = []
        self.rule_rows: list[tuple[str, int]] = []
        self._build_ui()
        self.load_existing_rules()
        self.search_products()

    def _build_ui(self) -> None:
        source_group = ttk.LabelFrame(self.window, text="未確定データ")
        source_group.pack(fill=X, padx=10, pady=(10, 8))
        raw = self.db._loads_json_object(self.unresolved_row["raw_json"])
        source_text = (
            f"理由: {self.unresolved_row['reason']}    "
            f"モール: {self.unresolved_row['source_mall'] or clean(raw.get('モール'))}    "
            f"SKU: {self.unresolved_row['source_sku']}    "
            f"数量: {self.unresolved_row['quantity'] or clean(raw.get('販売個数')) or clean(raw.get('quantity'))}\n"
            f"商品名: {clean(raw.get('注文商品名')) or clean(raw.get('product_name')) or '(商品名なし)'}"
        )
        Label(source_group, text=source_text, justify=LEFT, anchor=W).pack(fill=X, padx=8, pady=8)

        body = Frame(self.window)
        body.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

        product_group = ttk.LabelFrame(body, text="商品検索")
        product_group.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        search_row = Frame(product_group)
        search_row.pack(fill=X, padx=8, pady=8)
        Label(search_row, text="検索:").pack(side=LEFT)
        Entry(search_row, textvariable=self.search_var, width=28).pack(side=LEFT, fill=X, expand=True, padx=(4, 6))
        Button(search_row, text="検索", command=self.search_products, width=8).pack(side=LEFT)
        self.product_tree = ttk.Treeview(product_group, columns=("code", "name"), show="headings", height=12)
        self.product_tree.heading("code", text="商品コード")
        self.product_tree.heading("name", text="商品名")
        self.product_tree.column("code", width=130, anchor=W)
        self.product_tree.column("name", width=280, anchor=W)
        self.product_tree.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))
        self.product_tree.bind("<<TreeviewSelect>>", self.on_product_selected)

        variant_group = ttk.LabelFrame(body, text="子SKU選択")
        variant_group.pack(side=LEFT, fill=BOTH, expand=True)
        self.variant_tree = ttk.Treeview(variant_group, columns=("variant", "color", "size"), show="headings", height=12)
        for col, text, width in [("variant", "子SKU", 150), ("color", "カラー", 100), ("size", "サイズ", 130)]:
            self.variant_tree.heading(col, text=text)
            self.variant_tree.column(col, width=width, anchor=W)
        self.variant_tree.pack(fill=BOTH, expand=True, padx=8, pady=8)

        rule_group = ttk.LabelFrame(self.window, text="展開先")
        rule_group.pack(fill=X, padx=10, pady=(0, 8))
        add_row = Frame(rule_group)
        add_row.pack(fill=X, padx=8, pady=(8, 4))
        Label(add_row, text="数量:").pack(side=LEFT)
        Entry(add_row, textvariable=self.qty_var, width=6, justify=RIGHT).pack(side=LEFT, padx=(4, 8))
        Button(add_row, text="選択SKUを追加", command=self.add_selected_variant, width=14).pack(side=LEFT, padx=(0, 8))
        Label(add_row, text="メモ:").pack(side=LEFT)
        Entry(add_row, textvariable=self.note_var, width=42).pack(side=LEFT, fill=X, expand=True, padx=(4, 0))
        self.rule_tree = ttk.Treeview(rule_group, columns=("variant", "qty", "name"), show="headings", height=5)
        self.rule_tree.heading("variant", text="子SKU")
        self.rule_tree.heading("qty", text="数量")
        self.rule_tree.heading("name", text="商品/カラー/サイズ")
        self.rule_tree.column("variant", width=180, anchor=W)
        self.rule_tree.column("qty", width=60, anchor=E)
        self.rule_tree.column("name", width=560, anchor=W)
        self.rule_tree.pack(fill=X, padx=8, pady=(0, 4))
        rule_buttons = Frame(rule_group)
        rule_buttons.pack(fill=X, padx=8, pady=(0, 8))
        Button(rule_buttons, text="選択行を削除", command=self.remove_selected_rule, width=12).pack(side=LEFT)
        Button(rule_buttons, text="保存して再集計", command=self.save_rules, width=16, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=RIGHT, padx=(8, 0))
        Button(rule_buttons, text="閉じる", command=self.window.destroy, width=10).pack(side=RIGHT)

    def load_existing_rules(self) -> None:
        rows = self.db.sku_resolution_rules(self.unresolved_row["source_mall"], self.unresolved_row["source_sku"])
        self.rule_rows = [(row["child_variant_code"], int(row["quantity"])) for row in rows]
        self.refresh_rule_tree()

    def search_products(self) -> None:
        search = self.search_var.get().strip()
        like = f"%{search}%"
        if search:
            self.products = self.db.conn.execute(
                """
                SELECT product_code, display_name
                FROM products
                WHERE is_set = 0 AND (product_code LIKE ? OR display_name LIKE ? OR rakuten_parent_code LIKE ?)
                ORDER BY display_name, product_code
                LIMIT 300
                """,
                (like, like, like),
            ).fetchall()
        else:
            self.products = self.db.conn.execute(
                """
                SELECT product_code, display_name
                FROM products
                WHERE is_set = 0
                ORDER BY display_name, product_code
                LIMIT 300
                """
            ).fetchall()
        self.product_tree.delete(*self.product_tree.get_children())
        for row in self.products:
            self.product_tree.insert("", END, iid=row["product_code"], values=(row["product_code"], row["display_name"]))

    def on_product_selected(self, _event=None) -> None:
        selected = self.product_tree.selection()
        if not selected:
            return
        product_code = selected[0]
        self.variants = self.db.variants_for_product(product_code)
        self.variant_tree.delete(*self.variant_tree.get_children())
        for row in self.variants:
            self.variant_tree.insert("", END, iid=row["variant_code"], values=(row["variant_code"], row["color"], row["size"]))

    def add_selected_variant(self) -> None:
        selected = self.variant_tree.selection()
        if not selected:
            messagebox.showwarning("子SKU未選択", "追加する子SKUを選択してください。", parent=self.window)
            return
        try:
            qty = max(1, int(float(clean(self.qty_var.get()) or "1")))
        except ValueError:
            messagebox.showerror("数量エラー", "数量は1以上の数値で入力してください。", parent=self.window)
            return
        self.rule_rows.append((selected[0], qty))
        self.refresh_rule_tree()

    def remove_selected_rule(self) -> None:
        selected = self.rule_tree.selection()
        for index in sorted((int(iid) for iid in selected), reverse=True):
            if 0 <= index < len(self.rule_rows):
                self.rule_rows.pop(index)
        self.refresh_rule_tree()

    def refresh_rule_tree(self) -> None:
        self.rule_tree.delete(*self.rule_tree.get_children())
        for idx, (variant_code, qty) in enumerate(self.rule_rows):
            self.rule_tree.insert("", END, iid=str(idx), values=(variant_code, qty, self.variant_label(variant_code)))

    def variant_label(self, variant_code: str) -> str:
        row = self.db.conn.execute(
            """
            SELECT p.display_name,
                   COALESCE(NULLIF(vus.color, ''), v.color) AS color,
                   COALESCE(NULLIF(vus.size, ''), v.size) AS size
            FROM variants v
            LEFT JOIN products p ON p.product_code = v.product_code
            LEFT JOIN variant_user_settings vus ON vus.variant_code = v.variant_code
            WHERE v.variant_code = ?
            """,
            (variant_code,),
        ).fetchone()
        if not row:
            return ""
        return " / ".join(part for part in [clean(row["display_name"]), clean(row["color"]), clean(row["size"])] if part)

    def save_rules(self) -> None:
        try:
            self.db.save_sku_resolution_rules(
                self.unresolved_row["source_mall"],
                self.unresolved_row["source_sku"],
                self.rule_rows,
                self.note_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("保存エラー", str(exc), parent=self.window)
            return
        messagebox.showinfo("保存", "SKU解決ルールを保存しました。", parent=self.window)
        self.window.destroy()
        if self.on_saved:
            self.on_saved()


class MainApp:
    def __init__(self, root: Tk, db: AppDB, base_dir: Path) -> None:
        self.root = root
        self.db = db
        self.base_dir = base_dir
        self.status_var = StringVar()
        self.summary_var = StringVar()
        self.task_search_var = StringVar()
        self.task_product_sort = "asc"
        self.task_status_filter = {"pending", "copied", "skipped"}
        self.task_display_mode_var = StringVar(value="round")
        self.task_round_filter_var = StringVar(value="全")
        self.task_tree_iid_task_ids: dict[str, list[int]] = {}
        self.auto_skip_done_var = BooleanVar(value=self.db.get_setting("auto_skip_done", "1") != "0")
        self.temp_pdf_auto_enabled = self.db.get_setting("temp_pdf_auto_enabled", "0") == "1"
        self.temp_pdf_watch_after_id = None
        self.temp_pdf_watch_known_keys: set[str] = set()
        self.temp_pdf_watch_pending: dict[str, tuple[int, float, int]] = {}

        root.title(APP_TITLE)
        root.geometry("1040x630")
        self._build_ui()
        self.refresh_summary()
        self.update_temp_pdf_auto_button()
        if self.temp_pdf_auto_enabled:
            self.start_temp_pdf_watch(initial=True)

    def _build_ui(self) -> None:
        top = Frame(self.root)
        top.pack(side=TOP, fill=X, padx=12, pady=12)

        order_group = ttk.LabelFrame(top, text="受注CSV・集計")
        order_group.pack(side=LEFT, fill=Y, padx=(0, 10))
        order_row1 = Frame(order_group)
        order_row1.pack(fill=X, padx=8, pady=(8, 2))
        order_row2 = Frame(order_group)
        order_row2.pack(fill=X, padx=8, pady=(2, 8))
        Button(order_row1, text="受注CSV読込①", command=self.import_order_csv_auto, width=14, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=LEFT, padx=(0, 4))
        Button(order_row1, text="集計作成②", command=self.build_tasks, width=12, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=LEFT, padx=4)
        self.reset_order_button = Button(order_row1, text="リセット", command=self.reset_order_data, width=12)
        self.reset_order_button.pack(side=LEFT, padx=4)
        Button(order_row2, text="一時PDF", command=self.export_temporary_pdf, width=14, bg="#E0F2FE", activebackground="#BAE6FD").pack(side=LEFT, padx=(0, 4))
        Button(order_row2, text="PDF作成", command=self.export_summary_pdf, width=12, bg="#FDE68A", activebackground="#FCD34D").pack(side=LEFT, padx=4)
        self.temp_pdf_auto_button = Button(order_row2, text="PDF自動ON", command=self.toggle_temp_pdf_auto, width=12)
        self.temp_pdf_auto_button.pack(side=LEFT, padx=4)

        transfer_group = ttk.LabelFrame(top, text="転記")
        transfer_group.pack(side=LEFT, fill=Y, padx=(0, 10))
        transfer_row1 = Frame(transfer_group)
        transfer_row1.pack(fill=X, padx=8, pady=(8, 2))
        transfer_row2 = Frame(transfer_group)
        transfer_row2.pack(fill=X, padx=8, pady=(2, 8))
        Button(transfer_row1, text="転記画面③", command=self.open_transfer, width=12, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=LEFT, padx=(0, 8))
        ttk.Checkbutton(
            transfer_row1,
            text="【済】スキップ",
            variable=self.auto_skip_done_var,
            command=self.save_auto_skip_setting,
        ).pack(side=LEFT)
        Button(transfer_row2, text="未確定リスト", command=self.show_unresolved, width=12).pack(side=LEFT, padx=(0, 6))
        Button(transfer_row2, text="在庫アラート", command=self.show_stock_alerts, width=12, bg="#FEE2E2", activebackground="#FECACA").pack(side=LEFT)

        master_group = ttk.LabelFrame(top, text="マスタ")
        master_group.pack(side=LEFT, fill=Y, padx=(0, 10))
        Button(master_group, text="マスタ更新", command=self.import_masters_auto, width=12).pack(padx=8, pady=8)

        settings_group = ttk.LabelFrame(top, text="設定")
        settings_group.pack(side=LEFT, fill=Y)
        Button(settings_group, text="商品設定", command=self.open_product_settings, width=12).pack(anchor=W, padx=8, pady=(8, 2))
        Button(settings_group, text="機能設定", command=self.open_function_settings, width=12).pack(anchor=W, padx=8, pady=(2, 8))

        info_group = ttk.LabelFrame(self.root, text="状態")
        info_group.pack(fill=X, padx=12, pady=(0, 8))
        Label(info_group, textvariable=self.summary_var, justify=LEFT).pack(anchor=W, padx=8, pady=(6, 2))
        Label(info_group, textvariable=self.status_var, justify=LEFT, fg="#0f766e").pack(anchor=W, padx=8, pady=(0, 6))

        task_group = ttk.LabelFrame(self.root, text="取り込んだ受注の集計リスト")
        task_group.pack(fill=BOTH, expand=True, padx=12, pady=(0, 8))
        task_toolbar = Frame(task_group)
        task_toolbar.pack(fill=X, padx=8, pady=(8, 0))
        task_controls_row1 = Frame(task_toolbar)
        task_controls_row1.pack(fill=X)
        task_controls_row2 = Frame(task_toolbar)
        task_controls_row2.pack(fill=X, pady=(4, 0))
        Label(task_controls_row1, text="商品名検索:").pack(side=LEFT)
        Entry(task_controls_row1, textvariable=self.task_search_var, width=36).pack(side=LEFT, padx=(4, 8))
        Button(task_controls_row1, text="検索", command=self.refresh_task_list).pack(side=LEFT, padx=(0, 4))
        Button(task_controls_row1, text="クリア", command=self.clear_task_search).pack(side=LEFT)
        Label(task_controls_row1, text="  表示形式:").pack(side=LEFT, padx=(12, 4))
        ttk.Radiobutton(task_controls_row1, text="回別", variable=self.task_display_mode_var, value="round", command=self.refresh_task_list).pack(side=LEFT)
        ttk.Radiobutton(task_controls_row1, text="全体", variable=self.task_display_mode_var, value="total", command=self.refresh_task_list).pack(side=LEFT)
        Label(task_controls_row1, text="  表示回:").pack(side=LEFT, padx=(12, 4))
        self.task_round_filter_combo = ttk.Combobox(task_controls_row1, textvariable=self.task_round_filter_var, values=["全"], width=5, state="readonly")
        self.task_round_filter_combo.pack(side=LEFT)
        self.task_round_filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_task_list())
        Label(task_controls_row1, text="  表示:").pack(side=LEFT, padx=(12, 4))
        Button(task_controls_row1, text="未", command=lambda: self.set_task_status_filter({"pending"}), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row1, text="済", command=lambda: self.set_task_status_filter({"copied"}), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row1, text="ス", command=lambda: self.set_task_status_filter({"skipped"}), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row1, text="全", command=lambda: self.set_task_status_filter({"pending", "copied", "skipped"}), width=4).pack(side=LEFT, padx=2)
        Label(task_controls_row2, text="商品名順:").pack(side=LEFT)
        Button(task_controls_row2, text="昇", command=lambda: self.set_task_product_sort("asc"), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row2, text="降", command=lambda: self.set_task_product_sort("desc"), width=4).pack(side=LEFT, padx=2)
        Label(task_controls_row2, text="  選択:").pack(side=LEFT, padx=(18, 4))
        Button(task_controls_row2, text="全選択", command=self.select_all_tasks, width=8).pack(side=LEFT, padx=2)
        Button(task_controls_row2, text="全解除", command=self.clear_task_selection, width=8).pack(side=LEFT, padx=2)
        Label(task_controls_row2, text="  変更:").pack(side=LEFT, padx=(18, 4))
        Button(task_controls_row2, text="未", command=lambda: self.change_selected_task_status("pending"), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row2, text="済", command=lambda: self.change_selected_task_status("copied"), width=4).pack(side=LEFT, padx=2)
        Button(task_controls_row2, text="ス", command=lambda: self.change_selected_task_status("skipped"), width=4).pack(side=LEFT, padx=2)
        self.task_search_var.trace_add("write", lambda *_: self.refresh_task_list())
        columns = ("status", "round", "kind", "product", "color", "total", "sizes", "quantities")
        self.task_tree = ttk.Treeview(task_group, columns=columns, show="headings", selectmode="extended")
        headers = {
            "status": "状態",
            "round": "回",
            "kind": "区分",
            "product": "商品名",
            "color": "カラー",
            "total": "合計",
            "sizes": "サイズ順",
            "quantities": "数量",
        }
        widths = {"status": 105, "round": 45, "kind": 55, "product": 290, "color": 120, "total": 60, "sizes": 220, "quantities": 170}
        self.task_tree_base_widths = widths
        for col in columns:
            self.task_tree.heading(col, text=headers[col])
            self.task_tree.column(col, width=widths[col], anchor=W)
        self.task_tree.tag_configure("retry_required", foreground="#DC2626")
        self.task_tree.heading("product", command=self.toggle_task_product_sort)
        self.task_tree.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.task_tree.bind("<Double-1>", lambda event: self.open_transfer())

    def import_masters_auto(self) -> None:
        try:
            zr_item = self._find_one("zr_item*.csv")
            zr_select = self._find_one("zr_select*.csv")
            parent_contents = self._find_one("parent_contents*.csv")
            item_count = self.db.import_zr_item(zr_item)
            variant_count = self.db.import_zr_select(zr_select)
            component_count = self.db.import_parent_contents(parent_contents)
            self.status_var.set(
                f"マスタ取込完了: 商品 {item_count}件 / バリエーション {variant_count}件 / セット構成 {component_count}件"
            )
            self.refresh_summary()
        except Exception as exc:
            messagebox.showerror("マスタ取込エラー", str(exc))

    def _find_one(self, pattern: str) -> Path:
        matches = sorted(self.base_dir.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"{pattern} が見つかりません")
        return matches[-1]

    def import_mall_order(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=self.order_csv_initial_dir(),
            title="楽天/Yahoo/Amazon混在CSVを選択",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._import_order(Path(path), "mall_order")

    def import_mercari_order(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=self.order_csv_initial_dir(),
            title="メルカリShops CSVを選択",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._import_order(Path(path), "mercari_order")

    def import_order_csv_auto(self) -> None:
        paths = filedialog.askopenfilenames(
            initialdir=self.order_csv_initial_dir(),
            title="受注CSVを選択（複数可）",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not paths:
            return
        total_ok = 0
        total_bad = 0
        total_skipped = 0
        type_counts = defaultdict(int)
        imported_names: list[str] = []
        try:
            first_path = Path(paths[0])
            self.db.set_setting("last_order_csv_dir", normalize_windows_path(str(first_path.parent)))
            for path_text in paths:
                path = Path(path_text)
                file_type = self.detect_order_csv_type(path)
                ok, bad, skipped = self.db.import_order_file(path, file_type)
                total_ok += ok
                total_bad += bad
                total_skipped += skipped
                type_counts[file_type] += 1
                imported_names.append(path.name)
            type_text = " / ".join(
                part
                for part in [
                    f"受注ロボ {type_counts['mall_order']}件" if type_counts["mall_order"] else "",
                    f"メルカリ {type_counts['mercari_order']}件" if type_counts["mercari_order"] else "",
                ]
                if part
            )
            self.status_var.set(
                f"注文CSV取込完了: {len(imported_names)}ファイル ({type_text}) / 取込 {total_ok}行 / 警告 {total_bad}行 / 除外 {total_skipped}行"
            )
            self.refresh_summary()
        except Exception as exc:
            messagebox.showerror("注文CSV取込エラー", str(exc))

    def _import_order(self, path: Path, file_type: str) -> None:
        try:
            self.db.set_setting("last_order_csv_dir", normalize_windows_path(str(path.parent)))
            ok, bad, skipped = self.db.import_order_file(path, file_type)
            self.status_var.set(f"注文CSV取込完了: {path.name} / 取込 {ok}行 / 警告 {bad}行 / 除外 {skipped}行")
            self.refresh_summary()
        except Exception as exc:
            messagebox.showerror("注文CSV取込エラー", str(exc))

    def pdf_retention_days(self) -> int:
        try:
            return max(0, int(float(clean(self.db.get_setting("pdf_retention_days", "0")) or "0")))
        except ValueError:
            return 0

    def cleanup_old_pdfs_after_export(self) -> int:
        days = self.pdf_retention_days()
        if days <= 0:
            return 0
        cutoff = datetime.now().timestamp() - days * 86400
        deleted = 0
        for folder in (self.base_dir / "output" / "pdf", self.base_dir / "output" / "stock_alerts"):
            if not folder.exists():
                continue
            for path in folder.glob("*.pdf"):
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink()
                        deleted += 1
                except Exception as exc:
                    try:
                        self.db.warn("pdf_cleanup_failed", f"古いPDF削除失敗: {exc}", str(path))
                    except Exception:
                        pass
        return deleted

    def cleanup_old_pdfs_and_update_status(self) -> int:
        deleted = self.cleanup_old_pdfs_after_export()
        if deleted and hasattr(self, "status_var"):
            current = clean(self.status_var.get())
            suffix = f"古いPDFを削除しました: {deleted}件"
            self.status_var.set(f"{current} / {suffix}" if current else suffix)
        return deleted

    def open_temporary_pdf_after_export(self, pdf_path: Path) -> None:
        os.startfile(str(pdf_path))
        bring_front = self.db.get_setting("temp_pdf_bring_front_after_open", "1") != "0"
        print_dialog = self.db.get_setting("temp_pdf_open_print_dialog_after_open", "0") == "1"
        if bring_front or print_dialog:
            self.root.after(800, lambda path=Path(pdf_path): self.bring_pdf_window_to_front(path, print_dialog=print_dialog))

    def temp_pdf_print_dialog_delay_ms(self) -> int:
        try:
            seconds = float(clean(self.db.get_setting("temp_pdf_print_dialog_delay_seconds", "1.5")) or "1.5")
        except ValueError:
            seconds = 1.5
        seconds = min(max(seconds, 0.2), 10.0)
        return int(seconds * 1000)

    def bring_pdf_window_to_front(self, pdf_path: Path, print_dialog: bool = False, attempts: int = 8) -> bool:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            filename = pdf_path.name.lower()
            stem = pdf_path.stem.lower()
            found_hwnd = 0
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040

            enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_proc(hwnd, _lparam):
                nonlocal found_hwnd
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value.lower()
                if filename in title or stem in title:
                    found_hwnd = int(hwnd)
                    return False
                return True

            user32.EnumWindows(enum_proc_type(enum_proc), 0)
            if found_hwnd:
                user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                user32.SetWindowPos(found_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(found_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.BringWindowToTop(found_hwnd)
                user32.SetForegroundWindow(found_hwnd)
                if print_dialog:
                    delay_ms = self.temp_pdf_print_dialog_delay_ms()
                    self.root.after(delay_ms, lambda hwnd=found_hwnd: self.send_print_shortcut_to_window(hwnd))
                return True
        except Exception:
            pass
        if attempts > 0:
            self.root.after(500, lambda path=pdf_path: self.bring_pdf_window_to_front(path, print_dialog=print_dialog, attempts=attempts - 1))
        return False

    def send_print_shortcut_to_window(self, hwnd: int | None = None) -> None:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            if hwnd:
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            VK_CONTROL = 0x11
            VK_P = 0x50
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_P, 0, 0, 0)
            user32.keybd_event(VK_P, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def order_csv_initial_dir(self) -> str:
        for value in (
            self.db.get_setting("order_csv_default_folder", ""),
            self.db.get_setting("last_order_csv_dir", ""),
            str(self.base_dir),
        ):
            path = normalize_windows_path(value)
            if path and os.path.isdir(path):
                return path
        return str(self.base_dir)

    def detect_order_csv_type(self, path: Path) -> str:
        for encoding in ("utf-8-sig", "cp932", "utf-8"):
            try:
                with path.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    headers = {clean(name) for name in (reader.fieldnames or [])}
                break
            except UnicodeDecodeError:
                continue
        else:
            with path.open("r", encoding="cp932", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                headers = {clean(name) for name in (reader.fieldnames or [])}
        if "original_product_id" in headers or "buyer_name" in headers:
            return "mercari_order"
        return "mall_order"

    def detect_supported_temp_pdf_csv_type(self, path: Path) -> str | None:
        headers: set[str] = set()
        for encoding in ("utf-8-sig", "cp932", "utf-8"):
            try:
                with path.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    headers = {clean(name) for name in (reader.fieldnames or [])}
                break
            except UnicodeDecodeError:
                continue
            except OSError:
                return None
        if "original_product_id" in headers or "buyer_name" in headers:
            return "mercari_order"
        if {"モール", "商品番号", "販売個数"} <= headers:
            return "mall_order"
        return None

    def temp_pdf_watch_folder(self) -> Path | None:
        folder = normalize_windows_path(self.db.get_setting("temp_pdf_watch_folder", ""))
        if not folder:
            return None
        path = Path(folder)
        return path if path.is_dir() else None

    def temp_pdf_watch_interval_ms(self) -> int:
        try:
            seconds = float(clean(self.db.get_setting("temp_pdf_watch_interval_seconds", "1")) or "1")
        except ValueError:
            seconds = 1.0
        seconds = min(max(seconds, 1.0), 60.0)
        return int(seconds * 1000)

    def temp_pdf_file_key(self, path: Path) -> str:
        try:
            stat = path.stat()
            return f"{normalize_windows_path(str(path))}|{stat.st_mtime_ns}|{stat.st_size}"
        except OSError:
            return normalize_windows_path(str(path))

    def snapshot_temp_pdf_watch_files(self) -> set[str]:
        folder = self.temp_pdf_watch_folder()
        if not folder:
            return set()
        keys: set[str] = set()
        try:
            for path in folder.iterdir():
                if path.is_file() and path.suffix.lower() == ".csv":
                    keys.add(self.temp_pdf_file_key(path))
        except OSError:
            return set()
        return keys

    def update_temp_pdf_auto_button(self) -> None:
        if not hasattr(self, "temp_pdf_auto_button"):
            return
        if self.temp_pdf_auto_enabled:
            self.temp_pdf_auto_button.configure(text="PDF自動OFF", bg="#BBF7D0", activebackground="#86EFAC")
        else:
            self.temp_pdf_auto_button.configure(text="PDF自動ON", bg="#E5E7EB", activebackground="#D1D5DB")

    def toggle_temp_pdf_auto(self) -> None:
        if self.temp_pdf_auto_enabled:
            self.stop_temp_pdf_watch()
            self.status_var.set("一時PDF自動作成を停止しました。")
            return
        folder = self.temp_pdf_watch_folder()
        if not folder:
            messagebox.showwarning("監視フォルダ未設定", "機能設定で一時PDF監視フォルダを指定してください。", parent=self.root)
            return
        self.temp_pdf_auto_enabled = True
        self.db.set_setting("temp_pdf_auto_enabled", "1")
        self.start_temp_pdf_watch(initial=True)
        self.status_var.set(f"一時PDF自動作成: 監視中 / {folder}")

    def start_temp_pdf_watch(self, initial: bool = False) -> None:
        if initial:
            self.temp_pdf_watch_known_keys = self.snapshot_temp_pdf_watch_files()
            self.temp_pdf_watch_pending = {}
        self.update_temp_pdf_auto_button()
        if self.temp_pdf_watch_after_id is None:
            self.temp_pdf_watch_after_id = self.root.after(self.temp_pdf_watch_interval_ms(), self.poll_temp_pdf_watch_folder)

    def stop_temp_pdf_watch(self) -> None:
        self.temp_pdf_auto_enabled = False
        self.db.set_setting("temp_pdf_auto_enabled", "0")
        if self.temp_pdf_watch_after_id is not None:
            try:
                self.root.after_cancel(self.temp_pdf_watch_after_id)
            except Exception:
                pass
        self.temp_pdf_watch_after_id = None
        self.temp_pdf_watch_pending = {}
        self.update_temp_pdf_auto_button()

    def poll_temp_pdf_watch_folder(self) -> None:
        self.temp_pdf_watch_after_id = None
        if not self.temp_pdf_auto_enabled:
            self.update_temp_pdf_auto_button()
            return
        folder = self.temp_pdf_watch_folder()
        if not folder:
            self.stop_temp_pdf_watch()
            self.status_var.set("一時PDF自動作成を停止しました: 監視フォルダが見つかりません。")
            return
        try:
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() != ".csv":
                    continue
                key = self.temp_pdf_file_key(path)
                if key in self.temp_pdf_watch_known_keys:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                path_key = normalize_windows_path(str(path))
                previous = self.temp_pdf_watch_pending.get(path_key)
                stable_count = previous[2] + 1 if previous and previous[0] == stat.st_size and previous[1] == stat.st_mtime else 0
                if stable_count >= 1:
                    self.temp_pdf_watch_pending.pop(path_key, None)
                    self.temp_pdf_watch_known_keys.add(key)
                    file_type = self.detect_supported_temp_pdf_csv_type(path)
                    if file_type is None:
                        self.status_var.set(f"一時PDF自動作成: 対象外CSVを無視しました / {path.name}")
                        continue
                    pdf_path = self.export_temporary_pdf_from_paths([path], file_type=file_type, show_dialog=False)
                    if pdf_path:
                        self.status_var.set(f"一時PDF自動作成: {path.name} -> {pdf_path}")
                else:
                    self.temp_pdf_watch_pending[path_key] = (stat.st_size, stat.st_mtime, stable_count)
        except Exception as exc:
            self.status_var.set(f"一時PDF自動監視エラー: {exc}")
        self.temp_pdf_watch_after_id = self.root.after(self.temp_pdf_watch_interval_ms(), self.poll_temp_pdf_watch_folder)

    def export_temporary_pdf(self, file_type: str | None = None) -> None:
        title = "一時PDF用CSVを選択" if file_type is None else ("楽天/Yahoo/Amazon混在CSVを選択" if file_type == "mall_order" else "メルカリShops CSVを選択")
        paths = filedialog.askopenfilenames(
            initialdir=self.order_csv_initial_dir(),
            title=title,
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not paths:
            return
        self.export_temporary_pdf_from_paths([Path(path) for path in paths], file_type=file_type, show_dialog=True)

    def export_temporary_pdf_from_paths(self, paths: list[Path], file_type: str | None = None, show_dialog: bool = True) -> Path | None:
        try:
            files = [(Path(path), file_type or self.detect_order_csv_type(Path(path))) for path in paths]
            if files:
                self.db.set_setting("last_order_csv_dir", normalize_windows_path(str(files[0][0].parent)))
            output_dir = self.base_dir / "output" / "pdf"
            pdf_path, task_count, unresolved_count = self.db.export_temporary_order_pdf(output_dir, files)
            self.status_var.set(f"一時PDFを出力しました: 転記行 {task_count}件 / 未確定 {unresolved_count}件 / {pdf_path}")
            self.cleanup_old_pdfs_and_update_status()
            auto_open = self.db.get_setting("auto_open_pdf_after_export", "1") != "0"
            if auto_open:
                self.open_temporary_pdf_after_export(pdf_path)
            if auto_open:
                return pdf_path
            if not show_dialog:
                return pdf_path
            if unresolved_count:
                messagebox.showwarning(
                    "一時PDF出力",
                    f"一時PDFを出力しました。\n転記行: {task_count}件\n未確定: {unresolved_count}件\n\n{pdf_path}",
                )
            else:
                messagebox.showinfo("一時PDF出力", f"一時PDFを出力しました。\n転記行: {task_count}件\n{pdf_path}")
            return pdf_path
        except ModuleNotFoundError as exc:
            if show_dialog:
                messagebox.showerror("一時PDF出力エラー", f"PDF出力に必要なライブラリが見つかりません。\n{exc}")
            else:
                self.status_var.set(f"一時PDF自動作成エラー: {exc}")
        except Exception as exc:
            if show_dialog:
                messagebox.showerror("一時PDF出力エラー", str(exc))
            else:
                self.status_var.set(f"一時PDF自動作成エラー: {exc}")
        return None

    def build_tasks(self) -> None:
        try:
            tasks, unmatched = self.db.build_transfer_tasks()
            self.status_var.set(f"集計完了: 総転記タスク {tasks}件 / 未照合 {unmatched}行")
            self.refresh_summary()
            unresolved_count = self.db.summary()["unresolved_items"]
            if unresolved_count:
                messagebox.showwarning(
                    "未集計データがあります",
                    f"集計できなかった、または確認が必要な受注データが {unresolved_count} 件あります。\n未確定リストとPDFの未確定欄を確認してください。",
                )
        except Exception as exc:
            messagebox.showerror("集計エラー", str(exc))

    def reset_master_data(self, parent=None, create_backup: bool | None = None) -> None:
        if not messagebox.askyesno(
            "マスタリセット",
            "CSV由来の商品・子SKU・モールSKU・セット構成マスタを削除します。\n"
            "転記先Excel、サムネ、自動OK、カラー順、転記ルールなどのユーザー設定は残します。\n"
            "受注データも残します。実行しますか？",
            parent=parent or self.root,
        ):
            return
        backup_path = None
        if create_backup is None:
            create_backup = self.db.get_setting("backup_before_reset", "1") != "0"
        if create_backup:
            backup_path = self.db.create_backup(self.base_dir / "退避_バックアップ", "master_reset")
        self.db.reset_master_data()
        status = "マスタデータをリセットしました。"
        if backup_path:
            status += f" バックアップ: {backup_path}"
        self.status_var.set(status)
        self.refresh_summary()

    def reset_order_data(self) -> None:
        retry_count = self.db.pending_retry_required_count()
        pending_count = self.db.pending_task_count()
        if pending_count:
            if retry_count:
                message = (
                    f"未転記の商品が {pending_count} 件あります。\n"
                    f"そのうち {retry_count} 件は、読み取り専用などで転記できなかった要再試行の商品です。\n\n"
                    "クリアすると転記漏れになる可能性があります。続行しますか？"
                )
            else:
                message = (
                    f"未転記の商品が {pending_count} 件あります。\n\n"
                    "クリアすると転記漏れになる可能性があります。続行しますか？"
                )
            if not messagebox.askyesno("未転記があります", message):
                return
        if not messagebox.askyesno("受注データリセット", "現在日の読込ファイル・受注明細・集計結果・未確定リストを削除します。実行しますか？"):
            return
        self.set_order_reset_running(True)
        thread = threading.Thread(target=self.reset_order_data_worker, daemon=True)
        thread.start()

    def set_order_reset_running(self, running: bool) -> None:
        if hasattr(self, "reset_order_button"):
            self.reset_order_button.config(state="disabled" if running else "normal")
        self.status_var.set("受注データをリセット中です..." if running else "")

    def reset_order_data_worker(self) -> None:
        worker_db = None
        try:
            worker_db = AppDB(self.db.db_path)
            worker_db.reset_current_order_data()
            self.root.after(0, self.on_order_reset_finished)
        except Exception as exc:
            self.root.after(0, lambda exc=exc: self.on_order_reset_failed(exc))
        finally:
            if worker_db is not None:
                worker_db.close()

    def on_order_reset_finished(self) -> None:
        self.set_order_reset_running(False)
        self.status_var.set("現在日の受注データをリセットしました。")
        self.refresh_summary()

    def on_order_reset_failed(self, exc: Exception) -> None:
        self.set_order_reset_running(False)
        self.status_var.set("受注データのリセットに失敗しました。")
        messagebox.showerror("受注データリセットエラー", str(exc), parent=self.root)

    def export_summary_pdf(self) -> None:
        try:
            self.db.sync_current_task_quantity_multipliers()
            self.refresh_task_list()
            output_dir = self.base_dir / "output" / "pdf"
            if self.task_display_mode_var.get() == "total" or self.is_combined_round_view():
                pdf_rows = self.current_display_rows_for_pdf()
                title = "出荷集計リスト（合算表示）" if self.is_combined_round_view() else "出荷集計リスト（全体表示）"
                prefix = "summary_combined" if self.is_combined_round_view() else "summary_total"
                pdf_path = self.db._export_rows_pdf(output_dir, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}", title, pdf_rows, self.db.unresolved_rows_for_pdf())
            else:
                pdf_path = self.db.export_summary_pdf(output_dir, self.current_task_list_order_ids())
            self.status_var.set(f"PDFを出力しました: {pdf_path}")
            self.cleanup_old_pdfs_and_update_status()
            if self.db.get_setting("auto_open_pdf_after_export", "1") != "0":
                os.startfile(str(pdf_path))
            messagebox.showinfo("PDF出力", f"PDFを出力しました。\n{pdf_path}")
        except ModuleNotFoundError as exc:
            messagebox.showerror("PDF出力エラー", f"PDF出力に必要なライブラリが見つかりません。\n{exc}")
        except Exception as exc:
            messagebox.showerror("PDF出力エラー", str(exc))

    def open_transfer(self) -> None:
        visible_ids = self.visible_task_ids(include_done=not self.auto_skip_done_var.get())
        if hasattr(self, "task_tree") and self.db.task_rows() and not visible_ids:
            messagebox.showwarning("転記対象なし", "現在の検索条件に一致する転記対象がありません。")
            return
        if self.task_display_mode_var.get() == "total" and self.overall_view_has_copied_and_pending():
            if not messagebox.askyesno(
                "全体表示から転記",
                "全体表示内に転記済みの回と未転記の回が混在しています。\n"
                "Excel転記時は、本日同タイトル行への差分加算を優先します。\n"
                "続行しますか？",
            ):
                return
        TransferWindow(
            self.root,
            self.db,
            self.base_dir,
            on_task_change=self.select_task_in_list,
            start_task_id=self.selected_task_id(),
            auto_skip_done=self.auto_skip_done_var.get(),
            task_ids=visible_ids or None,
        )

    def overall_view_has_copied_and_pending(self) -> bool:
        if not hasattr(self, "task_tree"):
            return False
        all_rows = {int(row["id"]): row for row in self.db.task_rows()}
        for iid in self.task_tree.get_children():
            task_ids = self.task_tree_iid_task_ids.get(iid, [])
            statuses = {clean(all_rows[task_id]["status"]) for task_id in task_ids if task_id in all_rows}
            if "copied" in statuses and "pending" in statuses:
                return True
        return False

    def open_product_settings(self) -> None:
        ProductSettingsWindow(self.root, self.db, self.base_dir)

    def open_function_settings(self) -> None:
        FunctionSettingsWindow(self.root, self.db, self.base_dir, on_master_reset=self.reset_master_data)

    def save_auto_skip_setting(self) -> None:
        self.db.set_setting("auto_skip_done", "1" if self.auto_skip_done_var.get() else "0")

    def selected_task_id(self) -> int | None:
        if not hasattr(self, "task_tree"):
            return None
        selected = self.task_tree.selection()
        if not selected:
            return None
        ids = self.task_tree_iid_task_ids.get(selected[0], [])
        return ids[0] if ids else None

    def visible_task_ids(self, include_done: bool = True) -> list[int]:
        if not hasattr(self, "task_tree"):
            return []
        ids: list[int] = []
        for iid in self.task_tree.get_children():
            if not include_done:
                values = self.task_tree.item(iid, "values")
                if values and values[0] != "未":
                    continue
            try:
                ids.append(int(iid))
            except ValueError:
                pass
        return ids

    def current_task_list_order_ids(self) -> list[int]:
        if not hasattr(self, "task_tree"):
            return []
        ids: list[int] = []
        for iid in self.task_tree.get_children():
            try:
                ids.append(int(iid))
            except ValueError:
                pass
        return ids

    def visible_task_ids(self, include_done: bool = True) -> list[int]:
        if not hasattr(self, "task_tree"):
            return []
        statuses = {} if include_done else {int(row["id"]): row["status"] for row in self.db.task_rows()}
        ids: list[int] = []
        for iid in self.task_tree.get_children():
            for task_id in self.task_tree_iid_task_ids.get(iid, []):
                if include_done or statuses.get(task_id) == "pending":
                    ids.append(task_id)
        return ids

    def current_task_list_order_ids(self) -> list[int]:
        if not hasattr(self, "task_tree"):
            return []
        ids: list[int] = []
        for iid in self.task_tree.get_children():
            ids.extend(self.task_tree_iid_task_ids.get(iid, []))
        return ids

    def selected_task_round(self) -> int | None:
        value = clean(self.task_round_filter_var.get())
        if not value or value in {"全", "合"}:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def update_task_round_filter_options(self, rows: list[sqlite3.Row]) -> None:
        rounds = sorted({int(row["aggregation_round"]) for row in rows})
        values = ["全"] + [str(value) for value in rounds] + ["合"]
        if hasattr(self, "task_round_filter_combo"):
            self.task_round_filter_combo.configure(values=values)
        if self.task_round_filter_var.get() not in values:
            self.task_round_filter_var.set("全")

    def is_combined_round_view(self) -> bool:
        return clean(self.task_round_filter_var.get()) == "合"

    def filter_rows_by_selected_round(self, rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
        selected_round = self.selected_task_round()
        if selected_round is None:
            return rows
        return [row for row in rows if int(row["aggregation_round"]) == selected_round]

    def current_display_rows_for_pdf(self) -> list[dict[str, object]]:
        rows = list(self.db.task_rows())
        rows = self.filter_rows_by_selected_round(rows)
        if self.task_product_sort:
            rows.sort(key=lambda row: int(row["sort_order"]))
            rows.sort(key=lambda row: clean(row["product_name"]).lower(), reverse=self.task_product_sort == "desc")
        display_rows = self.overall_task_display_rows(rows, combined_only=self.is_combined_round_view()) if self.task_display_mode_var.get() == "total" or self.is_combined_round_view() else self.round_task_display_rows(rows)
        if self.task_display_mode_var.get() == "total" or self.is_combined_round_view():
            display_rows.sort(key=lambda row: int(row["sort_order"]))
            if self.task_product_sort:
                display_rows.sort(key=lambda row: clean(row["product_name"]).lower(), reverse=self.task_product_sort == "desc")
        visible_iids = set(self.task_tree.get_children()) if hasattr(self, "task_tree") else set()
        result: list[dict[str, object]] = []
        for display in display_rows:
            if display["iid"] not in visible_iids:
                continue
            result.append(
                {
                    "status": display["status_text"],
                    "sort_order": display["sort_order"],
                    "product_name": display["product_name"],
                    "color": display["color"],
                    "total_quantity": display["total_quantity"],
                    "sizes_json": json.dumps(display["sizes"], ensure_ascii=False),
                    "quantities_json": json.dumps(display["quantities"], ensure_ascii=False),
                }
            )
        return result

    def select_task_in_list(self, task_id: int) -> None:
        if not hasattr(self, "task_tree"):
            return
        iid = str(task_id)
        self.refresh_task_list(keep_selection=False)
        if iid in self.task_tree.get_children():
            self.task_tree.selection_set(iid)
            self.task_tree.focus(iid)
            self.task_tree.see(iid)

    def refresh_summary(self) -> None:
        summary = self.db.summary()
        batch_id = self.db.active_batch_id()
        self.summary_var.set(
            "\n".join(
                [
                    f"DB: {self.db.db_path}",
                    f"現在バッチ: {today_text()} (id={batch_id})",
                    f"商品: {summary['products']} / バリエーション: {summary['variants']} / モールSKU: {summary['mall_skus']} / セット構成: {summary['set_components']}",
                    f"読込ファイル: {summary['import_files']} / 読込明細: {summary['import_lines']} / 転記タスク: {summary['transfer_tasks']} / 未確定: {summary['unresolved_items']}",
                ]
            )
        )
        self.refresh_task_list()

    def refresh_task_list(self, keep_selection: bool = True) -> None:
        if not hasattr(self, "task_tree"):
            return
        selected = self.task_tree.selection()[0] if keep_selection and self.task_tree.selection() else None
        search = self.task_search_var.get().strip().lower()
        self.task_tree.delete(*self.task_tree.get_children())
        rows = list(self.db.task_rows())
        if self.task_product_sort:
            rows.sort(key=lambda row: int(row["sort_order"]))
            rows.sort(key=lambda row: clean(row["product_name"]).lower(), reverse=self.task_product_sort == "desc")
        for row in rows:
            if search and search not in clean(row["product_name"]).lower():
                continue
            if row["status"] not in self.task_status_filter:
                continue
            sizes = json.loads(row["sizes_json"])
            quantities = json.loads(row["quantities_json"])
            status = {"pending": "未", "copied": "済", "skipped": "スキップ"}.get(row["status"], row["status"])
            self.task_tree.insert(
                "",
                END,
                iid=str(row["id"]),
                values=(
                    status,
                    row["product_name"],
                    row["color"],
                    row["total_quantity"],
                    " / ".join(sizes),
                    " / ".join(q if q else "" for q in quantities),
                ),
            )
        if selected and selected in self.task_tree.get_children():
            self.task_tree.selection_set(selected)
            self.task_tree.focus(selected)
            self.task_tree.see(selected)

    def task_status_label(self, status: str) -> str:
        return {"pending": "未", "copied": "済", "skipped": "ス", "needs_review": "要"}.get(clean(status), clean(status))

    def task_kind_label(self, kind: str) -> str:
        return {"initial": "初", "delta": "差", "new": "新"}.get(clean(kind), clean(kind) or "初")

    def round_task_display_rows(self, rows: list[sqlite3.Row]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in rows:
            result.append(
                {
                    "iid": str(row["id"]),
                    "task_ids": [int(row["id"])],
                    "statuses": [clean(row["status"])],
                    "retry_required": bool(int(row["retry_required"] if "retry_required" in row.keys() else 0)),
                    "status_text": self.task_status_label(row["status"]),
                    "round_text": str(row["aggregation_round"]),
                    "kind_text": self.task_kind_label(row["task_kind"]),
                    "sort_order": int(row["sort_order"]),
                    "product_name": row["product_name"],
                    "color": row["color"],
                    "total_quantity": int(row["total_quantity"]),
                    "sizes": json.loads(row["sizes_json"]),
                    "quantities": json.loads(row["quantities_json"]),
                }
            )
        return result

    def overall_task_display_rows(self, rows: list[sqlite3.Row], combined_only: bool = False) -> list[dict[str, object]]:
        groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            groups[(row["product_code"], row["color"])].append(row)
        result: list[dict[str, object]] = []
        for index, ((product_code, color), group_rows) in enumerate(groups.items(), start=1):
            group_rows = sorted(group_rows, key=lambda row: (int(row["aggregation_round"]), int(row["sort_order"])))
            sizes = json.loads(group_rows[0]["sizes_json"])
            totals = [0 for _ in sizes]
            statuses: list[str] = []
            retry_required = False
            status_parts: list[str] = []
            kind_parts: list[str] = []
            task_ids: list[int] = []
            for row in group_rows:
                task_ids.append(int(row["id"]))
                statuses.append(clean(row["status"]))
                retry_required = retry_required or bool(int(row["retry_required"] if "retry_required" in row.keys() else 0))
                status_parts.append(f"{row['aggregation_round']}{self.task_status_label(row['status'])}")
                kind_parts.append(f"{row['aggregation_round']}{self.task_kind_label(row['task_kind'])}")
                quantities = json.loads(row["quantities_json"])
                for i, qty in enumerate(quantities[: len(totals)]):
                    if clean(qty):
                        try:
                            totals[i] += int(float(qty))
                        except ValueError:
                            pass
            quantities = ["" if qty == 0 else str(qty) for qty in totals]
            result.append(
                {
                    "iid": f"g:{product_code}:{color}:{index}",
                    "task_ids": task_ids,
                    "statuses": statuses,
                    "retry_required": retry_required,
                    "status_text": "" if combined_only else ",".join(status_parts),
                    "round_text": "" if combined_only else "全",
                    "kind_text": "" if combined_only else ",".join(kind_parts),
                    "sort_order": min(int(row["sort_order"]) for row in group_rows),
                    "product_name": group_rows[0]["product_name"],
                    "color": color,
                    "total_quantity": sum(totals),
                    "sizes": sizes,
                    "quantities": quantities,
                }
            )
        return result

    def refresh_task_list(self, keep_selection: bool = True) -> None:
        if not hasattr(self, "task_tree"):
            return
        selected = self.task_tree.selection()[0] if keep_selection and self.task_tree.selection() else None
        search = self.task_search_var.get().strip().lower()
        self.task_tree.delete(*self.task_tree.get_children())
        self.task_tree_iid_task_ids = {}
        rows = list(self.db.task_rows())
        self.update_task_round_filter_options(rows)
        rows = self.filter_rows_by_selected_round(rows)
        if self.task_product_sort:
            rows.sort(key=lambda row: int(row["sort_order"]))
            rows.sort(key=lambda row: clean(row["product_name"]).lower(), reverse=self.task_product_sort == "desc")
        combined_view = self.is_combined_round_view()
        self.configure_task_tree_columns_for_mode(combined_view)
        display_rows = self.overall_task_display_rows(rows, combined_only=combined_view) if self.task_display_mode_var.get() == "total" or combined_view else self.round_task_display_rows(rows)
        if self.task_display_mode_var.get() == "total" or combined_view:
            display_rows.sort(key=lambda row: int(row["sort_order"]))
            if self.task_product_sort:
                display_rows.sort(key=lambda row: clean(row["product_name"]).lower(), reverse=self.task_product_sort == "desc")
        for display in display_rows:
            if search and search not in clean(display["product_name"]).lower():
                continue
            if not set(display["statuses"]) & self.task_status_filter:
                continue
            self.task_tree_iid_task_ids[display["iid"]] = display["task_ids"]
            tags = ("retry_required",) if display.get("retry_required") else ()
            self.task_tree.insert(
                "",
                END,
                iid=display["iid"],
                values=(
                    display["status_text"],
                    display["round_text"],
                    display["kind_text"],
                    display["product_name"],
                    display["color"],
                    display["total_quantity"],
                    " / ".join(display["sizes"]),
                    " / ".join(q if q else "" for q in display["quantities"]),
                ),
                tags=tags,
            )
        if selected and selected in self.task_tree.get_children():
            self.task_tree.selection_set(selected)
            self.task_tree.focus(selected)
            self.task_tree.see(selected)

    def configure_task_tree_columns_for_mode(self, combined_view: bool) -> None:
        if not hasattr(self, "task_tree"):
            return
        widths = getattr(self, "task_tree_base_widths", {})
        for col in ("status", "round", "kind"):
            if combined_view:
                self.task_tree.column(col, width=0, minwidth=0, stretch=False)
                self.task_tree.heading(col, text="")
            else:
                self.task_tree.column(col, width=widths.get(col, 50), minwidth=20, stretch=True)
                self.task_tree.heading(col, text={"status": "状態", "round": "回", "kind": "区分"}[col])

    def clear_task_search(self) -> None:
        self.task_search_var.set("")
        self.refresh_task_list()

    def set_task_status_filter(self, statuses: set[str]) -> None:
        self.task_status_filter = set(statuses)
        self.refresh_task_list()

    def set_task_product_sort(self, direction: str) -> None:
        self.task_product_sort = direction
        self.refresh_task_list()

    def toggle_task_product_sort(self) -> None:
        self.set_task_product_sort("desc" if self.task_product_sort == "asc" else "asc")

    def select_all_tasks(self) -> None:
        if not hasattr(self, "task_tree"):
            return
        children = self.task_tree.get_children()
        if children:
            self.task_tree.selection_set(children)
            self.task_tree.focus(children[0])

    def clear_task_selection(self) -> None:
        if not hasattr(self, "task_tree"):
            return
        self.task_tree.selection_remove(self.task_tree.selection())

    def change_selected_task_status(self, status: str) -> None:
        if not hasattr(self, "task_tree"):
            return
        selected = list(self.task_tree.selection())
        if not selected:
            messagebox.showwarning("未選択", "状態を変更する集計リスト行を選択してください。")
            return
        status_label = {"pending": "未", "copied": "済", "skipped": "スキップ"}.get(status, status)
        task_ids: list[int] = []
        seen_task_ids: set[int] = set()
        for iid in selected:
            for task_id in self.task_tree_iid_task_ids.get(iid, []):
                if task_id not in seen_task_ids:
                    seen_task_ids.add(task_id)
                    task_ids.append(task_id)
        if not task_ids:
            messagebox.showwarning("未選択", "状態を変更できる集計リスト行がありません。")
            return
        if not messagebox.askyesno(
            "状態変更の確認",
            f"選択中の {len(selected)} 行、転記タスク {len(task_ids)} 件を「{status_label}」に変更します。\n実行しますか？",
            parent=self.root,
        ):
            return
        for task_id in task_ids:
            self.db.mark_task(task_id, status)
        self.refresh_summary()
        for iid in selected:
            if iid in self.task_tree.get_children():
                self.task_tree.selection_add(iid)
                self.task_tree.focus(iid)

    def show_unresolved(self) -> None:
        batch_id = self.db.active_batch_id()
        rows = self.db.conn.execute(
            """
            SELECT id, file_name, source_row, source_mall, source_sku, quantity, reason, candidates_json, raw_json
            FROM unresolved_items
            WHERE batch_id = ?
            ORDER BY reason, file_name, source_row
            """,
            (batch_id,),
        ).fetchall()
        window = Toplevel(self.root)
        window.title("未確定・入力不備リスト")
        window.geometry("980x460")
        columns = ("reason", "file", "row", "mall", "sku", "qty", "candidates")
        tree_frame = Frame(window)
        tree_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        y_scroll = Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scroll = Scrollbar(tree_frame, orient=HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        headings = {
            "reason": "理由",
            "file": "元ファイル",
            "row": "行",
            "mall": "モール",
            "sku": "SKU",
            "qty": "数量",
            "candidates": "候補/元データ",
        }
        widths = {"reason": 90, "file": 180, "row": 50, "mall": 90, "sku": 180, "qty": 50, "candidates": 330}
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=widths[col], anchor=W)
        x_scroll.pack(side=BOTTOM, fill=X)
        y_scroll.pack(side=RIGHT, fill=Y)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        for row in rows:
            candidates = self._format_candidates(row["candidates_json"], row["raw_json"])
            tree.insert(
                "",
                END,
                iid=str(row["id"]),
                values=(
                    row["reason"],
                    row["file_name"],
                    row["source_row"],
                    row["source_mall"],
                    row["source_sku"],
                    row["quantity"],
                    candidates,
                ),
            )
        button_row = Frame(window)
        button_row.pack(fill=X, padx=8, pady=(0, 8))
        Button(
            button_row,
            text="既存SKUへ分解登録",
            command=lambda: self.open_resolution_window(window, tree, rows),
            width=18,
        ).pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="閉じる", command=window.destroy).pack(side=LEFT)

    def sorted_stock_alert_rows(self, rows: list[sqlite3.Row], sort_mode: str = "status") -> list[sqlite3.Row]:
        groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            groups[clean(row["product_name"])].append(row)
        for group_rows in groups.values():
            group_rows.sort(key=lambda row: (stock_alert_status_rank(row), clean(row["color"]), clean(row["size"]), int(row["id"])))
        if sort_mode == "product":
            product_order = sorted(groups, key=lambda product: product.lower())
        else:
            product_order = sorted(
                groups,
                key=lambda product: (
                    min(stock_alert_status_rank(row) for row in groups[product]),
                    product.lower(),
                ),
            )
        sorted_rows: list[sqlite3.Row] = []
        for product in product_order:
            sorted_rows.extend(groups[product])
        return sorted_rows

    def product_tasks_for_stock_scan(self, product_code: str, product_name: str) -> list[TaskView]:
        variants = self.db.variant_grid_for_product(product_code)
        grouped: dict[str, list[str]] = {}
        for row in variants:
            color = clean(row["color"])
            grouped.setdefault(color, []).append(clean(row["size"]))
        tasks: list[TaskView] = []
        for color, sizes in grouped.items():
            tasks.append(
                TaskView(
                    id=-1,
                    product_code=product_code,
                    product_name=product_name,
                    color=color,
                    sizes=sizes,
                    quantities=[""] * len(sizes),
                    previous_quantities=[],
                    total=0,
                    status="scan",
                    source_task_ids=[],
                )
            )
        return tasks

    def roles_from_transfer_page_for_stock_scan(self, page: sqlite3.Row, product_tasks: list[TaskView]) -> list[tuple[str, int | None]]:
        pattern = clean(page["transfer_pattern"])
        quantity_count = sum(len(item.sizes) for item in product_tasks)
        roles: list[tuple[str, int | None]] = []
        if pattern:
            for token in transfer_pattern_raw_tokens(pattern):
                lower = token.lower()
                blank_count = transfer_pattern_blank_count(token)
                if blank_count:
                    roles.extend([("blank", None)] * blank_count)
                elif lower in {"title", "ttl", "タイトル"}:
                    roles.append(("title", None))
                elif lower in {"d", "date", "日付"}:
                    roles.append(("date", None))
                else:
                    try:
                        quantity_index = int(float(token)) - 1
                    except ValueError:
                        quantity_index = -1
                    roles.append(("quantity", quantity_index) if 0 <= quantity_index < quantity_count else ("blank", None))
            return roles
        if clean(page["copy_title"]):
            roles.append(("title", None))
        quantity_index = 0
        for color_index, item in enumerate(product_tasks):
            for _size in item.sizes:
                roles.append(("quantity", quantity_index))
                quantity_index += 1
            if color_index < len(product_tasks) - 1:
                roles.extend([("blank", None)] * int(page["color_gap_tabs"] or 0))
        if int(page["append_date"] or 0):
            roles.append(("date", None))
        return roles

    def stock_scan_targets(self) -> list[dict[str, object]]:
        targets: list[dict[str, object]] = []
        for product in self.db.products_for_settings("", is_set=0):
            product_code = clean(product["product_code"])
            product_name = clean(product["display_name"])
            product_tasks = self.product_tasks_for_stock_scan(product_code, product_name)
            if not product_tasks:
                continue
            metadata = []
            for item in product_tasks:
                for size in item.sizes:
                    metadata.append((item.color, size))
            sold_out_keys = self.db.variant_sold_out_keys(product_code)
            pages = []
            for page in self.db.product_transfer_pages(product_code):
                path = normalize_windows_path(page["inventory_file_path"])
                if not path:
                    continue
                pages.append(
                    {
                        "path": path,
                        "sheet": clean(page["inventory_sheet_name"]),
                        "start_col": normalize_excel_start_col(page["excel_start_col"] or "A"),
                        "roles": self.roles_from_transfer_page_for_stock_scan(page, product_tasks),
                    }
                )
            if pages:
                targets.append(
                    {
                        "product_code": product_code,
                        "product_name": product_name,
                        "min_stock": self.db.product_min_stock_quantity(product_code),
                        "metadata": metadata,
                        "sold_out_keys": sold_out_keys,
                        "pages": pages,
                    }
                )
        return targets

    def show_stock_alerts(self) -> None:
        rows = self.db.stock_alert_rows()
        window = Toplevel(self.root)
        window.title("在庫残数アラート")
        window.geometry("1040x460")
        sort_mode_var = StringVar(value="status")
        segment_values = ["全て", "不足", "在庫0", "低在庫"]
        segment_index_var = StringVar(value="0")
        segment_button_var = StringVar(value="表示: 全て")
        status_var = StringVar(value=f"現在のアラート: {len(rows)}件")
        scan_progress_var = DoubleVar(value=0)
        columns = ("status", "product", "color", "size", "remaining", "min", "cell", "message", "time")
        sort_row = Frame(window)
        sort_row.pack(fill=X, padx=8, pady=(8, 0))
        Label(sort_row, text="表示順:").pack(side=LEFT, padx=(0, 6))
        Button(sort_row, text="状態順", command=lambda: (sort_mode_var.set("status"), refresh_tree()), width=10).pack(side=LEFT, padx=(0, 4))
        Button(sort_row, text="商品名順", command=lambda: (sort_mode_var.set("product"), refresh_tree()), width=10).pack(side=LEFT, padx=(0, 8))
        Button(sort_row, textvariable=segment_button_var, command=lambda: toggle_segment(), width=12, bg="#E0F2FE", activebackground="#BAE6FD").pack(side=LEFT, padx=(0, 8))
        Label(sort_row, text="商品単位でまとまりを維持して並び替えます。", fg="#555555").pack(side=LEFT)
        ttk.Progressbar(sort_row, variable=scan_progress_var, maximum=100, length=220).pack(side=LEFT, fill=X, expand=True, padx=(12, 8))
        Label(sort_row, textvariable=status_var, fg="#374151").pack(side=RIGHT)
        tree_frame = Frame(window)
        tree_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        y_scroll = Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scroll = Scrollbar(tree_frame, orient=HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        headers = {
            "status": "状態",
            "product": "商品名",
            "color": "カラー",
            "size": "サイズ",
            "remaining": "残数",
            "min": "最低",
            "cell": "セル",
            "message": "内容",
            "time": "検出日時",
        }
        widths = {"status": 90, "product": 260, "color": 110, "size": 110, "remaining": 60, "min": 60, "cell": 70, "message": 220, "time": 140}
        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor=W)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        def current_segment_label() -> str:
            try:
                index = int(segment_index_var.get())
            except ValueError:
                index = 0
            return segment_values[index % len(segment_values)]

        def current_rows() -> list[sqlite3.Row]:
            segment = current_segment_label()
            if segment == "全て":
                filtered_rows = list(rows)
            else:
                filtered_rows = [row for row in rows if stock_alert_status_label(row) == segment]
            return self.sorted_stock_alert_rows(filtered_rows, sort_mode_var.get())

        def toggle_segment() -> None:
            try:
                index = int(segment_index_var.get())
            except ValueError:
                index = 0
            index = (index + 1) % len(segment_values)
            segment_index_var.set(str(index))
            segment_button_var.set(f"表示: {segment_values[index]}")
            refresh_tree()

        def refresh_tree() -> None:
            nonlocal rows
            tree.delete(*tree.get_children())
            display_rows = current_rows()
            for row in display_rows:
                tree.insert(
                    "",
                    END,
                    iid=str(row["id"]),
                    values=(
                        stock_alert_status_label(row),
                        row["product_name"],
                        row["color"],
                        row["size"],
                        "" if row["remaining_quantity"] is None else row["remaining_quantity"],
                        row["min_stock_quantity"],
                        row["cell_address"],
                        row["message"],
                        row["created_at"],
                    ),
                )
            segment = current_segment_label()
            if segment == "全て":
                status_var.set(f"現在のアラート: {len(display_rows)}件")
            else:
                status_var.set(f"現在のアラート: {len(display_rows)}件 / 全体 {len(rows)}件")

        def reload_rows() -> None:
            nonlocal rows
            rows = self.db.stock_alert_rows()
            refresh_tree()

        def selected_row() -> sqlite3.Row | None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("未選択", "Excelを開くアラート行を選択してください。", parent=window)
                return None
            alert_id = clean(selected[0])
            for row in rows:
                if clean(row["id"]) == alert_id:
                    return row
            messagebox.showwarning("未選択", "選択中のアラート行を確認できませんでした。", parent=window)
            return None

        def delete_selected_rows() -> None:
            selected = list(tree.selection())
            if not selected:
                messagebox.showwarning("未選択", "削除するアラート行を選択してください。", parent=window)
                return
            if not messagebox.askyesno("選択削除", f"選択中の {len(selected)} 件を在庫アラートから削除します。実行しますか？", parent=window):
                return
            deleted = self.db.delete_stock_alerts([int(alert_id) for alert_id in selected if clean(alert_id).isdigit()])
            reload_rows()
            status_var.set(f"選択削除しました: {deleted}件 / 現在の表示: {len(current_rows())}件 / 全体 {len(rows)}件")

        def mark_selected_as_sold_out() -> None:
            selected = list(tree.selection())
            if not selected:
                messagebox.showwarning("未選択", "完売にするアラート行を選択してください。", parent=window)
                return
            selected_ids = {clean(item) for item in selected}
            selected_rows = [row for row in rows if clean(row["id"]) in selected_ids]
            valid_rows = [row for row in selected_rows if clean(row["color"]) or clean(row["size"])]
            if not valid_rows:
                messagebox.showwarning("対象なし", "完売登録できるカラー・サイズ付きの行がありません。", parent=window)
                return
            if not messagebox.askyesno(
                "完売登録",
                f"選択中の {len(valid_rows)} 件を子SKU完売として登録し、在庫アラートから除外しますか？",
                parent=window,
            ):
                return
            updated_alert_ids: list[int] = []
            updated = 0
            not_found = 0
            multiple = 0
            details: list[str] = []
            updated_keys: set[tuple[str, str, str]] = set()
            for row in valid_rows:
                key = (clean(row["product_code"]), clean(row["color"]), clean(row["size"]))
                if key in updated_keys:
                    updated_alert_ids.append(int(row["id"]))
                    continue
                result, detail = self.db.set_variant_sold_out_by_product_color_size(*key)
                if result == "updated":
                    updated += 1
                    updated_keys.add(key)
                    updated_alert_ids.append(int(row["id"]))
                elif result == "multiple":
                    multiple += 1
                    details.append(f"複数一致: {row['product_name']} / {row['color']} / {row['size']} ({detail})")
                else:
                    not_found += 1
                    details.append(f"未検出: {row['product_name']} / {row['color']} / {row['size']}")
            if updated_alert_ids:
                self.db.delete_stock_alerts(updated_alert_ids)
            reload_rows()
            summary = f"完売登録: {updated}件 / 未検出: {not_found}件 / 複数一致: {multiple}件"
            status_var.set(f"{summary} / 現在の表示: {len(current_rows())}件 / 全体 {len(rows)}件")
            if details:
                messagebox.showwarning("完売登録結果", summary + "\n\n" + "\n".join(details[:10]), parent=window)
            else:
                messagebox.showinfo("完売登録結果", summary, parent=window)

        refresh_tree()
        button_row = Frame(window)
        button_row.pack(fill=X, padx=8, pady=(0, 8))
        Button(button_row, text="巡回チェック", command=lambda: self.run_stock_alert_scan(window, status_var, scan_progress_var, reload_rows), width=12, bg="#DBEAFE", activebackground="#BFDBFE").pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="Excelを開く", command=lambda: self.open_stock_alert_excel(window, selected_row()), width=12, bg="#FEF3C7", activebackground="#FDE68A").pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="完売✓", command=mark_selected_as_sold_out, width=10, bg="#DCFCE7", activebackground="#BBF7D0").pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="選択削除", command=delete_selected_rows, width=12, bg="#FEE2E2", activebackground="#FECACA").pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="CSV出力", command=lambda: self.export_stock_alerts_csv(window, current_rows()), width=12).pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="PDF出力", command=lambda: self.export_stock_alerts_pdf(window, current_rows()), width=12, bg="#FDE68A", activebackground="#FCD34D").pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="クリア", command=lambda: self.clear_stock_alerts_window(window), width=10).pack(side=LEFT, padx=(0, 8))
        Button(button_row, text="閉じる", command=window.destroy, width=10).pack(side=LEFT)

    def open_stock_alert_excel(self, parent: Toplevel, row: sqlite3.Row | None) -> None:
        if row is None:
            return
        path = normalize_windows_path(clean(row["inventory_file_path"]))
        if not path:
            messagebox.showwarning("Excelを開く", "このアラートにはExcelファイルの情報がありません。", parent=parent)
            return
        if not os.path.exists(path):
            messagebox.showerror("Excelを開く", f"Excelファイルが見つかりません。\n{path}", parent=parent)
            return
        try:
            import win32com.client
        except ImportError as exc:
            messagebox.showerror("Excelを開く", f"Excel操作には pywin32 が必要です。\n{exc}", parent=parent)
            return

        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            normalized_path = os.path.normcase(normalize_windows_path(path))
            workbook = None
            for book in excel.Workbooks:
                if os.path.normcase(normalize_windows_path(clean(book.FullName))) == normalized_path:
                    workbook = book
                    break
            if workbook is None:
                workbook = excel.Workbooks.Open(path)

            sheet_name = clean(row["inventory_sheet_name"])
            if sheet_name:
                worksheet = None
                for index in range(1, int(workbook.Worksheets.Count) + 1):
                    candidate = workbook.Worksheets(index)
                    if clean(candidate.Name) == sheet_name:
                        worksheet = candidate
                        break
                if worksheet is None:
                    raise RuntimeError(f"指定シートが見つかりません: {sheet_name}")
            else:
                worksheet = workbook.ActiveSheet

            workbook.Activate()
            worksheet.Activate()
            cell_address = clean(row["cell_address"])
            if cell_address:
                cell = worksheet.Range(cell_address)
                cell.Select()
                try:
                    excel.Goto(cell, True)
                except Exception:
                    pass
            self.bring_excel_app_to_front(excel)
        except Exception as exc:
            messagebox.showerror("Excelを開く", f"Excelを開けませんでした。\n{exc}", parent=parent)

    def bring_excel_app_to_front(self, excel) -> None:
        try:
            excel.Visible = True
            excel.Application.Activate()
        except Exception:
            pass
        try:
            import win32con
            import win32gui

            hwnd = int(excel.Hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        except Exception:
            pass
        try:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            caption = clean(getattr(excel, "Caption", "")) or "Microsoft Excel"
            shell.AppActivate(caption)
        except Exception:
            pass

    def export_stock_alerts_csv(self, parent: Toplevel, rows: list[sqlite3.Row] | None = None) -> None:
        rows = rows if rows is not None else self.sorted_stock_alert_rows(self.db.stock_alert_rows())
        if not rows:
            messagebox.showinfo("在庫アラート", "出力するアラートがありません。", parent=parent)
            return
        output_dir = self.base_dir / "output" / "stock_alerts"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"stock_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["状態", "商品コード", "商品名", "カラー", "サイズ", "残数", "最低在庫数", "ファイル", "シート", "セル", "内容", "検出日時"])
            for row in rows:
                writer.writerow([
                    stock_alert_status_label(row),
                    row["product_code"],
                    row["product_name"],
                    row["color"],
                    row["size"],
                    "" if row["remaining_quantity"] is None else row["remaining_quantity"],
                    row["min_stock_quantity"],
                    row["inventory_file_path"],
                    row["inventory_sheet_name"],
                    row["cell_address"],
                    row["message"],
                    row["created_at"],
                ])
        messagebox.showinfo("CSV出力", f"在庫アラートCSVを出力しました。\n{path}", parent=parent)

    def export_stock_alerts_pdf(self, parent: Toplevel, rows: list[sqlite3.Row] | None = None) -> None:
        rows = rows if rows is not None else self.sorted_stock_alert_rows(self.db.stock_alert_rows())
        if not rows:
            messagebox.showinfo("在庫アラート", "出力するアラートがありません。", parent=parent)
            return
        try:
            output_dir = self.base_dir / "output" / "stock_alerts"
            pdf_path = self.db.export_stock_alerts_pdf(output_dir, rows)
            self.cleanup_old_pdfs_and_update_status()
            if self.db.get_setting("auto_open_pdf_after_export", "1") != "0":
                os.startfile(str(pdf_path))
            messagebox.showinfo("PDF出力", f"在庫アラートPDFを出力しました。\n{pdf_path}", parent=parent)
        except ImportError as exc:
            messagebox.showerror("PDF出力エラー", f"PDF出力に必要なライブラリが見つかりません。\n{exc}", parent=parent)
        except Exception as exc:
            messagebox.showerror("PDF出力エラー", str(exc), parent=parent)

    def run_stock_alert_scan(self, parent: Toplevel, status_var: StringVar, progress_var: DoubleVar, on_finished=None) -> None:
        if not messagebox.askyesno(
            "在庫巡回チェック",
            "現在の在庫アラートをクリアして、登録済みExcelから巡回リストを作成します。\n実行しますか？",
            parent=parent,
        ):
            return
        targets = self.stock_scan_targets()
        if not targets:
            messagebox.showinfo("在庫巡回チェック", "巡回対象の在庫Excelが登録されていません。", parent=parent)
            return
        labels = [
            clean(label)
            for label in re.split(r"[,、\n]+", self.db.get_setting("stock_alert_labels", "残数"))
            if clean(label)
        ] or ["残数"]
        protected_keywords = self.db.get_setting("excel_protected_row_keywords", "確保")
        progress_var.set(0)
        status_var.set(f"巡回中: 0/{len(targets)} 商品")

        def worker() -> None:
            alerts: list[dict[str, object]] = []
            failures: list[str] = []
            try:
                import win32com.client
                try:
                    import pythoncom
                except Exception:
                    pythoncom = None
            except Exception as exc:
                parent.after(0, lambda: messagebox.showerror("在庫巡回チェック", f"Excel操作には pywin32 が必要です。\n{exc}", parent=parent))
                return

            if pythoncom:
                pythoncom.CoInitialize()
            excel = None
            try:
                excel = win32com.client.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                helper = TransferWindow.__new__(TransferWindow)
                helper.base_dir = self.base_dir
                helper.window = parent

                class ScanDB:
                    def get_setting(self, key, default=""):
                        if key == "excel_protected_row_keywords":
                            return protected_keywords
                        return default

                helper.db = ScanDB()
                for index, target in enumerate(targets, start=1):
                    percent = int(index / len(targets) * 100) if targets else 0
                    parent.after(0, lambda index=index, percent=percent: (status_var.set(f"巡回中: {index}/{len(targets)} 商品"), progress_var.set(percent)))
                    product_code = clean(target["product_code"])
                    product_name = clean(target["product_name"])
                    min_stock = int(target["min_stock"])
                    metadata = list(target["metadata"])
                    sold_out_keys = set(target.get("sold_out_keys") or set())
                    for page in target["pages"]:
                        path = clean(page["path"])
                        workbook = None
                        try:
                            if not os.path.exists(path):
                                raise RuntimeError("ファイルが見つかりません")
                            workbook = excel.Workbooks.Open(path, ReadOnly=True, UpdateLinks=0)
                            worksheet = TransferWindow.resolve_excel_worksheet(helper, workbook, clean(page["sheet"]))
                            workbook.Activate()
                            worksheet.Activate()
                            start_col_text = normalize_excel_start_col(page["start_col"])
                            TransferWindow.scroll_excel_to_start_col(helper, excel, start_col_text)
                            candidate = TransferWindow.detect_write_candidate_cell(helper, worksheet, excel, start_col_text)
                            candidate.row = TransferWindow.adjust_candidate_after_red_marker(helper, worksheet, candidate.row, candidate.col, candidate.island)
                            roles = list(page["roles"])
                            label_row = TransferWindow.find_stock_remaining_row(helper, worksheet, candidate.row, candidate.col, labels)
                            if not label_row:
                                alerts.append(
                                    {
                                        "product_code": product_code,
                                        "product_name": product_name,
                                        "color": "",
                                        "size": "",
                                        "remaining": None,
                                        "min_stock": min_stock,
                                        "status": "missing_label",
                                        "path": path,
                                        "sheet": clean(page["sheet"]),
                                        "cell": "",
                                        "message": f"残数ラベルが見つかりません: {','.join(labels)}",
                                    }
                                )
                                continue
                            for offset, role in enumerate(roles):
                                if role[0] != "quantity" or role[1] is None:
                                    continue
                                quantity_index = int(role[1])
                                if quantity_index >= len(metadata):
                                    continue
                                color, size = metadata[quantity_index]
                                if (clean(color), clean(size)) in sold_out_keys:
                                    continue
                                cell = worksheet.Cells(label_row, candidate.col + offset)
                                remaining = TransferWindow.quantity_number(helper, cell.Value)
                                if should_create_stock_alert(remaining, min_stock):
                                    alerts.append(
                                        {
                                            "product_code": product_code,
                                            "product_name": product_name,
                                            "color": color,
                                            "size": size,
                                            "remaining": remaining,
                                            "min_stock": min_stock,
                                            "status": "negative" if remaining < 0 else "low",
                                            "path": path,
                                            "sheet": clean(page["sheet"]),
                                            "cell": TransferWindow.excel_cell_address(helper, cell),
                                            "message": "在庫残数がマイナスです" if remaining < 0 else "最低在庫数以下です",
                                        }
                                    )
                        except Exception as exc:
                            failures.append(f"{product_name}: {exc}")
                        finally:
                            if workbook is not None:
                                try:
                                    workbook.Close(SaveChanges=False)
                                except Exception:
                                    pass
            finally:
                if excel is not None:
                    try:
                        excel.Quit()
                    except Exception:
                        pass
                if pythoncom:
                    pythoncom.CoUninitialize()
            parent.after(0, lambda: self.finish_stock_alert_scan(parent, status_var, progress_var, alerts, failures, on_finished))

        threading.Thread(target=worker, daemon=True).start()

    def finish_stock_alert_scan(self, parent: Toplevel, status_var: StringVar, progress_var: DoubleVar, alerts: list[dict[str, object]], failures: list[str], on_finished=None) -> None:
        self.db.clear_stock_alerts()
        for alert in alerts:
            self.db.save_stock_alert(
                None,
                clean(alert["product_code"]),
                clean(alert["product_name"]),
                clean(alert["color"]),
                clean(alert["size"]),
                alert["remaining"],
                int(alert["min_stock"]),
                clean(alert["status"]),
                clean(alert["path"]),
                clean(alert["sheet"]),
                clean(alert["cell"]),
                clean(alert["message"]),
            )
        progress_var.set(100)
        status_var.set(f"巡回完了: アラート {len(alerts)}件 / 失敗 {len(failures)}件")
        if on_finished:
            on_finished()
        status_var.set(f"巡回完了: アラート {len(alerts)}件 / 失敗 {len(failures)}件")
        parent.lift()
        parent.focus_force()
        if failures:
            message = "\n".join(failures[:8])
            if len(failures) > 8:
                message += f"\n...ほか {len(failures) - 8}件"
            messagebox.showwarning("在庫巡回チェック", f"巡回は完了しましたが、開けないExcelがありました。\n\n{message}", parent=parent)
        else:
            messagebox.showinfo("在庫巡回チェック", f"巡回チェックが完了しました。\nアラート: {len(alerts)}件", parent=parent)

    def clear_stock_alerts_window(self, parent: Toplevel) -> None:
        if not messagebox.askyesno("在庫アラートクリア", "現在日の在庫アラートを削除します。実行しますか？", parent=parent):
            return
        self.db.clear_stock_alerts()
        parent.destroy()
        self.show_stock_alerts()

    def open_resolution_window(self, parent: Toplevel, tree: ttk.Treeview, rows: list[sqlite3.Row]) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("未選択", "未確定リストの行を選択してください。", parent=parent)
            return
        row_id = int(selected[0])
        row = next((item for item in rows if int(item["id"]) == row_id), None)
        if row is None:
            messagebox.showerror("行なし", "選択行が見つかりません。", parent=parent)
            return
        ResolutionRuleWindow(parent, self.db, row, on_saved=lambda: self.after_resolution_saved(parent))

    def after_resolution_saved(self, parent: Toplevel) -> None:
        parent.destroy()
        try:
            tasks, unmatched = self.db.build_transfer_tasks()
            self.status_var.set(f"解決ルールを保存し再集計しました: 総転記タスク {tasks}件 / 未照合 {unmatched}行")
            self.refresh_summary()
            self.refresh_task_list()
        except Exception as exc:
            messagebox.showerror("再集計エラー", str(exc), parent=self.root)

    def _format_candidates(self, candidates_json: str, raw_json: str) -> str:
        try:
            candidates = json.loads(candidates_json or "[]")
        except json.JSONDecodeError:
            candidates = []
        if candidates:
            return " / ".join(
                f"{c.get('product_name', '')} {c.get('color', '')} {c.get('size', '')}".strip()
                for c in candidates
            )
        try:
            raw = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            raw = {}
        return " / ".join(f"{key}={value}" for key, value in raw.items() if clean(value))[:300]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    db = AppDB(base_dir / DB_NAME)
    root = Tk()
    MainApp(root, db, base_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
