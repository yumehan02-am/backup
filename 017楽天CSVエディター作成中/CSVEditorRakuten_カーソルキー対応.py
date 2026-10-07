import json
import logging
import tkinter as tk
from tkinter import filedialog, ttk, Text
import pandas as pd
import os
import chardet
from PIL import Image, ImageTk
import requests
from io import BytesIO
import hashlib
from pathlib import Path
import time
import shutil
import csv
import gc
import uuid
import threading
import queue
import re

# ログ設定
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(message)s')

SPEC_CSV_PATH = Path(__file__).with_name("specification_rakuten.csv")
SPEC_FIELDS = ["item_name", "mall_name", "required", "format", "description", "search_target"]
PRODUCT_ID_COLUMN = "商品管理番号（商品URL）"
SKU_ID_COLUMN = "SKU管理番号"
OPTION_TYPE_COLUMN = "選択肢タイプ"
OPTION_NAME_COLUMN = "商品オプション項目名"
OPTION_REQUIRED_COLUMN = "商品オプション選択必須"
PARENT_HINT_COLUMNS = [
    "商品番号",
    "商品名",
    "ジャンルID",
    "商品画像パス1",
    "PC用商品説明文",
    "スマートフォン用商品説明文",
    "PC用販売説明文",
    "バリエーション項目キー定義",
    "バリエーション項目名定義",
]
ITEM_CAT_COLUMNS = ["コントロールカラム", PRODUCT_ID_COLUMN, "商品名", "表示先カテゴリ", "優先度", "URL", "1ページ複数形式"]

class RakutenCSVEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Editor / 楽天版")
        self.df = None
        self.item_cat_df = None
        self.spec_df = None
        self.csv_kind = "unknown"
        self.csv_encoding = "cp932"
        self.item_cat_encoding = "cp932"
        self.current_product_idx = 0
        self.product_groups = []
        self.product_group_info = []
        self.item_cat_groups = {}
        self.row_to_product_idx = {}
        self.selected_product_count = 0
        self.file_path = ""
        self.item_cat_file_path = ""
        self.column_list = []
        self.selected_rows = []
        self.entry_rows_per_column = []
        self.image_cache = {}
        self.image_cache_order = []
        self.image_cache_map = {}
        self.cache_progress_queue = queue.Queue()
        self.cache_thread = None
        self.cache_thumb_button = None
        self.cache_all_button = None
        self.cache_running_label = "画像キャッシュ"
        self.memory_image_cache_limit = 300
        self.is_modified = False
        self.item_cat_is_modified = False
        self.save_timer = None
        self.item_cat_save_timer = None
        self.info_window = None
        self.settings_window = None
        self.cache_dir = Path("cache/images")
        self.cache_map_file = Path("cache/cache.json")
        self.cache_max_size_mb = 100
        self.cache_max_days = 60
        self.copy_and_edit = True
        self.append_selection = True
        self.code_copy_delimiter = " "
        self.select_shortcut_key = "F1"
        self.shop_url = ""
        self.option_grid_window = None
        self.category_grid_window = None
        self.category_canvas = None
        self.category_scrollable_frame = None
        self.category_entries = []
        self.category_button = None
        self.option_button = None
        self.option_column_var = None
        self.option_find_text = None
        self.option_replace_text = None
        self.option_bulk_column_check_vars = {}
        self.option_display_columns = []
        self.category_find_text = None
        self.category_replace_text = None
        self.category_bulk_column_check_vars = {}
        self.image_manage_window = None
        self.image_manage_canvas = None
        self.image_manage_scrollable_frame = None
        self.image_manage_entries = []
        self.image_manage_photos = []
        self.image_bulk_url_var = None
        self.image_bulk_alt_var = None
        self.image_bulk_scope_var = None
        self.image_bulk_item_vars = {}
        self.image_cache_progress_var = None
        self.image_cache_progress_label = None
        self.image_find_text = None
        self.image_replace_text = None
        self.sku_grid_window = None
        self.sku_canvas = None
        self.sku_scrollable_frame = None
        self.current_sku_column = None
        self.sku_column_var = None
        self.sku_main_menu_button = None
        self.sku_main_menu = None
        self.sku_main_popup = None
        self.sku_main_popup_canvas = None
        self.sku_main_popup_frame = None
        self.sku_main_popup_click_bind_id = None
        self.sku_main_popup_row_widgets = {}
        self.sku_main_column_check_vars = {}
        self.sku_column_check_vars = {}
        self.sku_bulk_column_check_vars = {}
        self.sku_column_selector_frame = None
        self.sku_display_columns = []
        self.sku_find_text = None
        self.sku_replace_text = None
        self.show_option_window = False
        self.navigate_selected_only = False
        self.next_button = None
        self.prev_button = None
        self.navigation_mode_button = None
        self.focus_before_image_hover = None
        self.subwindow_mousewheel_targets = {}
        self.subwindow_mousewheel_bound = False
        self.subwindow_selected_count_vars = []
        self.load_settings()
        self.load_selected_rows()
        self.load_specification()
        self.selected_rows = [False] * len(self.df) if self.df is not None else []
        self.focused_entry_index = 0
        self.search_result_count = 0
        self.setup_gui()
        self.load_image_cache_map()
        if self.file_path and os.path.isfile(self.file_path):
            self.load_csv(self.file_path, auto=True)
        if self.item_cat_file_path and os.path.isfile(self.item_cat_file_path):
            self.load_item_cat_csv(self.item_cat_file_path, auto=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def show_message(self, title, message, msg_type="info"):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog_width = 300
        dialog_height = 150
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        tk.Label(dialog, text=message, wraplength=250, padx=10, pady=10, font=("Meiryo", 9)).pack(expand=True)
        tk.Button(dialog, text="OK", command=dialog.destroy, font=("Meiryo", 9)).pack(pady=5)
        self.root.wait_window(dialog)

    def show_confirm(self, title, message):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog_width = 300
        dialog_height = 150
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        tk.Label(dialog, text=message, wraplength=250, padx=10, pady=10, font=("Meiryo", 9)).pack(expand=True)
        result = tk.BooleanVar(value=False)
        tk.Button(dialog, text="はい", command=lambda: [result.set(True), dialog.destroy()], font=("Meiryo", 9)).pack(side=tk.LEFT, padx=20, pady=5)
        tk.Button(dialog, text="いいえ", command=lambda: [result.set(False), dialog.destroy()], font=("Meiryo", 9)).pack(side=tk.RIGHT, padx=20, pady=5)
        self.root.wait_window(dialog)
        return result.get()

    def load_specification(self):
        try:
            self.spec_df = pd.read_csv(SPEC_CSV_PATH, encoding='shift-jis')
            if not all(col in self.spec_df.columns for col in SPEC_FIELDS):
                logging.warning("仕様CSVのカラムが不足しています。デフォルトを生成します。")
                self.spec_df = pd.DataFrame(columns=SPEC_FIELDS)
                self.spec_df.to_csv(SPEC_CSV_PATH, index=False, encoding='shift-jis', lineterminator='\n', quoting=csv.QUOTE_ALL)
        except FileNotFoundError:
            logging.info("仕様CSVが見つかりません。新規作成します。")
            self.spec_df = pd.DataFrame(columns=SPEC_FIELDS)
            try:
                self.spec_df.to_csv(SPEC_CSV_PATH, index=False, encoding='shift-jis', lineterminator='\n', quoting=csv.QUOTE_ALL)
            except Exception as e:
                logging.error(f"仕様CSVの作成に失敗しました: {str(e)}")
        except Exception as e:
            logging.error(f"仕様CSVの読み込みに失敗しました: {str(e)}")
            self.spec_df = pd.DataFrame(columns=SPEC_FIELDS)

    def load_settings(self):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.num_columns = max(1, settings.get("num_columns", 3))
                self.selected_columns = settings.get("selected_columns", [None] * self.num_columns)
                self.checked_columns = settings.get("checked_columns", [False] * self.num_columns)
                self.search_text = settings.get("search_text", "")
                self.file_path = settings.get("file_path", "")
                self.item_cat_file_path = settings.get("item_cat_file_path", "")
                self.entry_rows_per_column = settings.get("entry_rows_per_column", [2] * self.num_columns)
                self.cache_max_size_mb = max(1, settings.get("cache_max_size_mb", 100))
                self.cache_max_days = max(1, settings.get("cache_max_days", 60))
                self.copy_and_edit = settings.get("copy_and_edit", True)
                self.append_selection = settings.get("append_selection", True)
                self.code_copy_delimiter = settings.get("code_copy_delimiter", " ")
                self.select_shortcut_key = settings.get("select_shortcut_key", "F1")
                self.shop_url = settings.get("shop_url", "")
                self.navigate_selected_only = settings.get("navigate_selected_only", False)
                self.last_selected_columns = settings.get("last_selected_columns", None)
                self.selected_columns = self.selected_columns[:self.num_columns] + [None] * max(0, self.num_columns - len(self.selected_columns))
                self.checked_columns = self.checked_columns[:self.num_columns] + [False] * max(0, self.num_columns - len(self.checked_columns))
                self.entry_rows_per_column = self.entry_rows_per_column[:self.num_columns] + [2] * max(0, self.num_columns - len(self.entry_rows_per_column))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"設定ファイルの読み込みに失敗しました: {str(e)}。デフォルト設定を適用します。")
            self.num_columns = 3
            self.column_list = []
            self.selected_columns = [None] * self.num_columns
            self.checked_columns = [False] * self.num_columns
            self.search_text = ""
            self.file_path = ""
            self.item_cat_file_path = ""
            self.entry_rows_per_column = [2] * self.num_columns
            self.cache_max_size_mb = 100
            self.cache_max_days = 60
            self.copy_and_edit = True
            self.append_selection = True
            self.code_copy_delimiter = " "
            self.select_shortcut_key = "F1"
            self.shop_url = ""
            self.navigate_selected_only = False
            self.last_selected_columns = None

    def save_settings(self):
        settings = {
            "num_columns": self.num_columns,
            "selected_columns": self.selected_columns,
            "checked_columns": self.checked_columns,
            "search_text": self.search_var.get() if hasattr(self, "search_var") else self.search_text,
            "file_path": self.file_path,
            "item_cat_file_path": self.item_cat_file_path,
            "entry_rows_per_column": self.entry_rows_per_column,
            "cache_max_size_mb": self.cache_max_size_mb,
            "cache_max_days": self.cache_max_days,
            "copy_and_edit": self.copy_edit_var.get() if hasattr(self, "copy_edit_var") else self.copy_and_edit,
            "append_selection": self.append_selection_var.get() if hasattr(self, "append_selection_var") else self.append_selection,
            "code_copy_delimiter": self.code_copy_delimiter,
            "select_shortcut_key": self.select_shortcut_key,
            "shop_url": self.shop_url_var.get() if hasattr(self, "shop_url_var") else self.shop_url,
            "navigate_selected_only": self.navigate_selected_only,
            "last_selected_columns": self.selected_columns
        }
        try:
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except (OSError, IOError) as e:
            logging.error(f"設定ファイルの保存に失敗しました: {str(e)}")

    def load_selected_rows(self):
        try:
            with open("selected_rows.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.selected_rows = data.get("selected_rows", [])
                self.current_product_idx = data.get("current_product_idx", 0)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logging.warning(f"選択状態ファイルの読み込みに失敗しました: {str(e)}。デフォルトを適用します。")
            self.selected_rows = []
            self.current_product_idx = 0
        if self.df is not None:
            if len(self.selected_rows) != len(self.df):
                self.selected_rows = [False] * len(self.df)
            if self.current_product_idx >= len(self.product_groups):
                self.current_product_idx = 0

    def save_selected_rows(self):
        try:
            data = {
                "selected_rows": self.selected_rows,
                "current_product_idx": self.current_product_idx
            }
            with open("selected_rows.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, IOError) as e:
            logging.error(f"選択状態ファイルの保存に失敗しました: {str(e)}")

    def load_image_cache_map(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.cache_map_file.exists():
            try:
                with open(self.cache_map_file, "r", encoding="utf-8") as f:
                    self.image_cache_map = json.load(f)
            except Exception as e:
                logging.warning(f"キャッシュマップの読み込みに失敗しました: {str(e)}")
                self.image_cache_map = {}
        else:
            self.image_cache_map = {}
        self.cleanup_cache()

    def save_image_cache_map(self):
        try:
            with open(self.cache_map_file, "w", encoding="utf-8") as f:
                json.dump(self.image_cache_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"キャッシュマップの保存に失敗しました: {str(e)}")

    def cleanup_cache(self):
        current_time = time.time()
        total_size = 0
        files = []
        try:
            for cache_file in self.cache_dir.glob("*.jpg"):
                stats = cache_file.stat()
                mtime = stats.st_mtime
                size = stats.st_size
                files.append((cache_file, mtime, size))
                total_size += size
        except Exception as e:
            logging.error(f"キャッシュディレクトリの走査に失敗しました: {str(e)}")
            return
        max_size_bytes = self.cache_max_size_mb * 1024 * 1024
        max_age_seconds = self.cache_max_days * 86400
        files.sort(key=lambda x: x[1])
        for cache_file, mtime, size in files:
            if total_size > max_size_bytes or (current_time - mtime) > max_age_seconds:
                try:
                    cache_file.unlink()
                    total_size -= size
                    for url, path in list(self.image_cache_map.items()):
                        if path == str(cache_file):
                            del self.image_cache_map[url]
                except Exception as e:
                    logging.warning(f"キャッシュファイルの削除に失敗しました: {str(e)}")
        self.save_image_cache_map()
        self.trim_memory_image_cache()
        gc.collect()

    def clear_cache(self):
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.image_cache_map.clear()
            self.image_cache.clear()
            self.image_cache_order.clear()
            self.save_image_cache_map()
            gc.collect()
            self.show_message("成功", "キャッシュをクリアしました。")
        except Exception as e:
            self.show_message("エラー", f"キャッシュのクリアに失敗しました: {str(e)}", msg_type="error")

    def remember_memory_image(self, url, photo):
        self.image_cache[url] = photo
        if url in self.image_cache_order:
            self.image_cache_order.remove(url)
        self.image_cache_order.append(url)
        self.trim_memory_image_cache()

    def trim_memory_image_cache(self):
        while len(self.image_cache_order) > self.memory_image_cache_limit:
            old_url = self.image_cache_order.pop(0)
            self.image_cache.pop(old_url, None)

    def bind_subwindow_mousewheel(self, window, canvas):
        if not window or not canvas:
            return
        self.subwindow_mousewheel_targets[window] = canvas
        if not self.subwindow_mousewheel_bound:
            self.root.bind_all("<MouseWheel>", self.on_any_subwindow_mousewheel, add="+")
            self.subwindow_mousewheel_bound = True

    def unbind_subwindow_mousewheel(self, window):
        if window:
            self.subwindow_mousewheel_targets.pop(window, None)
        if not self.subwindow_mousewheel_targets and self.subwindow_mousewheel_bound:
            self.root.unbind_all("<MouseWheel>")
            self.subwindow_mousewheel_bound = False

    def pointer_inside_widget(self, widget):
        if not widget or not widget.winfo_exists():
            return False
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        wx = widget.winfo_rootx()
        wy = widget.winfo_rooty()
        return wx <= x <= wx + widget.winfo_width() and wy <= y <= wy + widget.winfo_height()

    def on_any_subwindow_mousewheel(self, event):
        pointer_widget = self.root.winfo_containing(event.x_root, event.y_root)
        if self.is_pointer_over_subwindow_edit_text(pointer_widget):
            return None
        for window, canvas in list(self.subwindow_mousewheel_targets.items()):
            if not window or not canvas or not window.winfo_exists() or not canvas.winfo_exists():
                self.subwindow_mousewheel_targets.pop(window, None)
                continue
            if self.pointer_inside_widget(window):
                return self.scroll_subwindow_canvas(event, canvas)
        return None

    def is_pointer_over_subwindow_edit_text(self, widget):
        if not widget:
            return False
        edit_widgets = [
            getattr(self, attr, None)
            for attr in (
                "option_find_text",
                "option_replace_text",
                "sku_find_text",
                "sku_replace_text",
                "category_find_text",
                "category_replace_text",
                "image_find_text",
                "image_replace_text",
            )
        ]
        return any(target is not None and widget == target for target in edit_widgets)

    def scroll_subwindow_canvas(self, event, canvas):
        delta = -1 * int(event.delta / 120) if event.delta else 0
        if delta == 0:
            return "break"
        if event.state & 0x1:
            try:
                canvas.xview_scroll(delta, "units")
            except tk.TclError:
                pass
        else:
            canvas.yview_scroll(delta, "units")
        return "break"

    def open_settings(self):
        if self.settings_window is not None:
            self.settings_window.lift()
            return
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("設定")
        self.settings_window.geometry("540x420")
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 270
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 210
        self.settings_window.geometry(f"+{x}+{y}")
        self.settings_window.transient(self.root)
        self.settings_window.resizable(True, False)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings_window)
        style = ttk.Style()
        style.configure("TLabelFrame", borderwidth=2, relief="groove")
        main_frame = tk.Frame(self.settings_window)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        operation_frame = ttk.LabelFrame(main_frame, text="操作設定", padding=5)
        operation_frame.pack(fill=tk.X, pady=5)
        self.copy_edit_var = tk.BooleanVar(value=self.copy_and_edit)
        self.copy_edit_button = tk.Button(operation_frame, command=self.toggle_copy_edit_setting, font=("Meiryo", 9), width=28)
        self.copy_edit_button.pack(anchor="w", pady=2)
        self.update_copy_edit_button()
        self.append_selection_var = tk.BooleanVar(value=self.append_selection)
        self.append_selection_button = tk.Button(operation_frame, command=self.toggle_append_selection_setting, font=("Meiryo", 9), width=28)
        self.append_selection_button.pack(anchor="w", pady=2)
        self.update_append_selection_button()
        shop_url_frame = tk.Frame(operation_frame)
        shop_url_frame.pack(fill=tk.X, pady=2)
        tk.Label(shop_url_frame, text="店舗URL:", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.shop_url_var = tk.StringVar(value=self.shop_url)
        tk.Entry(shop_url_frame, textvariable=self.shop_url_var, width=30, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        code_copy_frame = tk.Frame(operation_frame)
        code_copy_frame.pack(fill=tk.X, pady=2)
        tk.Label(code_copy_frame, text="選択値コピー区切り文字:", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.code_copy_delimiter_var = tk.StringVar(value=self.code_copy_delimiter)
        delimiter_display = ["半角スペース", "タブ", "改行", "セミコロン", "コロン"]
        delimiter_values = [" ", "\t", "\n", ";", ":"]
        self.delimiter_map = dict(zip(delimiter_display, delimiter_values))
        self.reverse_delimiter_map = dict(zip(delimiter_values, delimiter_display))
        current_display = self.reverse_delimiter_map.get(self.code_copy_delimiter, "半角スペース")
        self.code_copy_delimiter_var.set(current_display)
        ttk.Combobox(code_copy_frame, textvariable=self.code_copy_delimiter_var, values=delimiter_display, state="readonly", width=15, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        shortcut_frame = tk.Frame(operation_frame)
        shortcut_frame.pack(fill=tk.X, pady=2)
        tk.Label(shortcut_frame, text="商品選択キー:", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.shortcut_var = tk.StringVar(value=self.select_shortcut_key)
        shortcut_keys = [f"F{i}" for i in range(1, 13)]
        ttk.Combobox(shortcut_frame, textvariable=self.shortcut_var, values=shortcut_keys, state="readonly", width=15, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        cache_frame = ttk.LabelFrame(main_frame, text="キャッシュ設定", padding=5)
        cache_frame.pack(fill=tk.X, pady=5)
        tk.Label(cache_frame, text="キャッシュ容量上限 (MB):", font=("Meiryo", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.cache_size_var = tk.StringVar(value=str(self.cache_max_size_mb))
        tk.Entry(cache_frame, textvariable=self.cache_size_var, width=10, font=("Meiryo", 9)).grid(row=0, column=1, sticky="e")
        tk.Button(cache_frame, text="キャッシュクリア", command=self.clear_cache, font=("Meiryo", 9)).grid(row=0, column=2, padx=5)
        self.cache_thumb_button = tk.Button(cache_frame, text="サムネキャッシュ", command=self.cache_thumbnail_images, font=("Meiryo", 9))
        self.cache_thumb_button.grid(row=1, column=0, padx=5, sticky="ew")
        self.cache_all_button = tk.Button(cache_frame, text="全画像キャッシュ", command=self.cache_all_images, font=("Meiryo", 9))
        self.cache_all_button.grid(row=1, column=1, padx=5, sticky="ew")
        cache_frame.grid_columnconfigure(0, weight=1)
        cache_frame.grid_columnconfigure(1, weight=1)
        cache_frame.grid_columnconfigure(2, weight=1)
        cache_frame.grid_columnconfigure(3, weight=1)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(cache_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=2, column=0, columnspan=4, sticky="ew", pady=5)
        self.progress_label = tk.Label(cache_frame, text="0/0", font=("Meiryo", 9))
        self.progress_label.grid(row=3, column=0, columnspan=4)
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        tk.Button(button_frame, text="適用", command=self.apply_settings, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="閉じる", command=self.close_settings_window, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)

    def update_copy_edit_button(self):
        if hasattr(self, "copy_edit_button") and self.copy_edit_button.winfo_exists():
            state_text = "ON" if self.copy_and_edit else "OFF"
            relief = tk.SUNKEN if self.copy_and_edit else tk.RAISED
            self.copy_edit_button.config(text=f"CSVコピー操作: {state_text}", relief=relief)

    def toggle_copy_edit_setting(self):
        self.copy_and_edit = not self.copy_and_edit
        if hasattr(self, "copy_edit_var"):
            self.copy_edit_var.set(self.copy_and_edit)
        self.update_copy_edit_button()
        self.save_settings()

    def update_append_selection_button(self):
        if hasattr(self, "append_selection_button") and self.append_selection_button.winfo_exists():
            state_text = "追加" if self.append_selection else "置換"
            relief = tk.SUNKEN if self.append_selection else tk.RAISED
            self.append_selection_button.config(text=f"商品検索選択: {state_text}", relief=relief)

    def toggle_append_selection_setting(self):
        self.append_selection = not self.append_selection
        if hasattr(self, "append_selection_var"):
            self.append_selection_var.set(self.append_selection)
        self.update_append_selection_button()
        self.update_select_button_text()
        self.save_settings()

    def cache_thumbnail_images(self):
        self.cache_images(thumbnail_only=True)

    def cache_all_images(self):
        self.cache_images(thumbnail_only=False)

    def cache_images(self, thumbnail_only=True):
        cache_label = "サムネキャッシュ" if thumbnail_only else "全画像キャッシュ"
        if self.cache_thread and self.cache_thread.is_alive():
            self.show_message("情報", f"{self.cache_running_label}は実行中です。")
            return
        if self.df is None or '商品画像パス1' not in self.df.columns:
            self.show_message("警告", "データフレームが読み込まれていないか、商品画像パス1カラムが存在しません。")
            return
        if hasattr(self, "shop_url_var"):
            self.shop_url = self.shop_url_var.get().strip()
        if not self.shop_url:
            self.show_message("警告", "店舗URLが設定されていません。")
            return

        image_urls = []
        for group in self.product_groups:
            for url in self.get_group_image_urls(group, thumbnail_only=thumbnail_only):
                if url not in image_urls:
                    image_urls.append(url)

        total_images = len(image_urls)
        if total_images == 0:
            self.show_message("警告", "キャッシュ対象の画像がありません。")
            return
        self.cache_running_label = cache_label

        while not self.cache_progress_queue.empty():
            try:
                self.cache_progress_queue.get_nowait()
            except queue.Empty:
                break

        self.root.config(cursor="wait")
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.config(cursor="wait")
        if self.cache_thumb_button and self.cache_thumb_button.winfo_exists():
            self.cache_thumb_button.config(state=tk.DISABLED)
        if self.cache_all_button and self.cache_all_button.winfo_exists():
            self.cache_all_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.progress_label.config(text=f"0/{total_images}")
        self.root.update_idletasks()

        self.cache_thread = threading.Thread(
            target=self.cache_images_worker,
            args=(image_urls,),
            daemon=True
        )
        self.cache_thread.start()
        self.root.after(100, self.poll_image_cache_progress)

    def cache_images_worker(self, image_urls):
        total_images = len(image_urls)
        processed = 0
        failed = 0
        saved_since_flush = 0
        for url in image_urls:
            try:
                cache_key = hashlib.md5(url.encode()).hexdigest()
                cache_path = self.cache_dir / f"{cache_key}.jpg"
                if url not in self.image_cache and not (url in self.image_cache_map and cache_path.exists()):
                    response = requests.get(url, stream=True, timeout=5)
                    if response.status_code != 200:
                        failed += 1
                        logging.warning(f"画像取得失敗: URL={url}, ステータス={response.status_code}")
                    else:
                        response.raise_for_status()
                        img = Image.open(BytesIO(response.content))
                        img.thumbnail((200, 200))
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")
                        img.save(str(cache_path), "JPEG")
                        self.image_cache_map[url] = str(cache_path)
                        saved_since_flush += 1
                        if saved_since_flush >= 20:
                            self.save_image_cache_map()
                            saved_since_flush = 0
            except Exception as e:
                failed += 1
                logging.warning(f"画像処理エラー: URL={url}, {str(e)}")
            processed += 1
            self.cache_progress_queue.put(("progress", processed, total_images, failed))

        self.save_image_cache_map()
        self.cleanup_cache()
        self.cache_progress_queue.put(("done", processed, total_images, failed))

    def poll_image_cache_progress(self):
        done = False
        processed = 0
        total_images = 0
        failed = 0

        while True:
            try:
                message = self.cache_progress_queue.get_nowait()
            except queue.Empty:
                break
            kind, processed, total_images, failed = message
            if total_images:
                try:
                    self.progress_var.set((processed / total_images) * 100)
                    if self.progress_label and self.progress_label.winfo_exists():
                        self.progress_label.config(text=f"{processed}/{total_images} 失敗:{failed}")
                except tk.TclError:
                    pass
            if kind == "done":
                done = True

        if not done:
            self.root.after(100, self.poll_image_cache_progress)
            return

        self.root.config(cursor="")
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.config(cursor="")
        if self.cache_all_button and self.cache_all_button.winfo_exists():
            self.cache_all_button.config(state=tk.NORMAL)
        if self.cache_thumb_button and self.cache_thumb_button.winfo_exists():
            self.cache_thumb_button.config(state=tk.NORMAL)
        if failed:
            self.show_message("完了", f"{self.cache_running_label}が完了しました。失敗: {failed}件")
        else:
            self.show_message("成功", f"{self.cache_running_label}が完了しました。")

    def build_rakuten_image_url(self, image_path):
        if not self.cell_has_value(image_path):
            return None
        path = str(image_path).strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        shop_url = self.shop_url.strip().strip("/")
        path = path.lstrip("/")
        if path.startswith("cabinet/"):
            return f"https://image.rakuten.co.jp/{shop_url}/{path}"
        return f"https://image.rakuten.co.jp/{shop_url}/cabinet/{path}"

    def get_group_image_urls(self, group, thumbnail_only=False):
        urls = []
        parent_row = self.get_parent_row(group)
        if thumbnail_only:
            image_columns = ["商品画像パス1"]
        else:
            image_columns = [f"商品画像パス{i}" for i in range(1, 21)]
            image_columns.append("白背景画像パス")
        for col in image_columns:
            if col in self.df.columns:
                url = self.build_rakuten_image_url(self.df.iloc[parent_row].get(col))
                if url:
                    urls.append(url)
        if not thumbnail_only and "SKU画像パス" in self.df.columns:
            for row in group:
                url = self.build_rakuten_image_url(self.df.iloc[row].get("SKU画像パス"))
                if url:
                    urls.append(url)
        return urls

    def apply_settings(self):
        try:
            max_size = float(self.cache_size_var.get())
            if max_size < 1:
                raise ValueError("キャッシュ容量は1MB以上でなければなりません。")
            self.cache_max_size_mb = max_size
            self.copy_and_edit = self.copy_edit_var.get()
            self.append_selection = self.append_selection_var.get()
            selected_delimiter = self.code_copy_delimiter_var.get()
            self.code_copy_delimiter = self.delimiter_map.get(selected_delimiter, " ")
            prev_shortcut = self.select_shortcut_key
            self.select_shortcut_key = self.shortcut_var.get()
            self.shop_url = self.shop_url_var.get().strip()
            self.save_settings()
            self.cleanup_cache()
            if prev_shortcut != self.select_shortcut_key:
                self.update_shortcut_binding(prev_shortcut)
            self.show_message("成功", "設定を保存しました。")
            self.update_select_button_text()
            self.update_copy_edit_button()
            self.update_append_selection_button()
        except ValueError as e:
            self.show_message("エラー", f"無効な入力です: {str(e)}", msg_type="error")

    def close_settings_window(self):
        if self.settings_window:
            self.settings_window.destroy()
            self.settings_window = None

    def update_select_button_text(self):
        if hasattr(self, 'select_button'):
            self.select_button.config(text="追加" if self.append_selection else "選択")

    def copy_code_to_clipboard(self):
        if self.df is None:
            self.show_message("警告", "データが読み込まれていません。")
            return
        checked_cols = [
            self.selected_columns[i]
            for i in range(self.num_columns)
            if self.checked_columns[i] and self.selected_columns[i]
        ]
        if not checked_cols:
            self.show_message("警告", "チェックされているカラムがありません。")
            return

        target_rows = []
        if self.csv_kind == "item-cat":
            target_rows = [i for i, selected in enumerate(self.selected_rows) if selected]
        else:
            for rows in self.product_groups:
                if any(self.selected_rows[row] for row in rows):
                    target_rows.append(self.get_parent_row(rows))
        if not target_rows:
            self.show_message("警告", "選択中の商品がありません。")
            return

        values_list = []
        for row_idx in target_rows:
            row_values = []
            for col in checked_cols:
                val = self.df.iloc[row_idx].get(col, "")
                row_values.append(str(val) if pd.notna(val) else "")
            values_list.append(row_values)

        if len(checked_cols) == 1:
            result = self.code_copy_delimiter.join(row[0] for row in values_list)
            label = checked_cols[0]
        else:
            result = "\n".join("\t".join(row) for row in values_list)
            label = f"{len(checked_cols)}カラム（{', '.join(checked_cols)}）"
        self.root.clipboard_clear()
        self.root.clipboard_append(result)
        self.show_message("成功", f"{label}: {len(target_rows)}件 をクリップボードにコピーしました。")

    def replace_with_column_vars(self, text, row_idx):
        def replacer(match):
            col_name = match.group(1).strip()
            if col_name in self.df.columns:
                val = self.df.iloc[row_idx].get(col_name)
                return str(val) if pd.notna(val) else ""
            logging.warning(f"カラム '{col_name}' が存在しません（行: {row_idx}）")
            return match.group(0)
        return re.sub(r"%([^%]+)%", replacer, text)

    def cell_has_value(self, value):
        return pd.notna(value) and str(value).strip() != ""

    def row_has_any_value(self, row_idx, columns):
        return any(
            col in self.df.columns and self.cell_has_value(self.df.iloc[row_idx].get(col))
            for col in columns
        )

    def is_option_row(self, row_idx):
        if self.product_group_info:
            product_idx = self.row_to_product_idx.get(row_idx)
            if product_idx is not None:
                return row_idx in self.product_group_info[product_idx]["option_rows"]
        option_cols = [OPTION_TYPE_COLUMN, OPTION_NAME_COLUMN, OPTION_REQUIRED_COLUMN]
        option_cols.extend(f"商品オプション選択肢{i}" for i in range(1, 101))
        return self.row_has_any_value(row_idx, option_cols)

    def is_sku_row(self, row_idx):
        if self.product_group_info:
            product_idx = self.row_to_product_idx.get(row_idx)
            if product_idx is not None:
                return row_idx in self.product_group_info[product_idx]["sku_rows"]
        sku_cols = [SKU_ID_COLUMN, "システム連携用SKU番号", "在庫数", "通常購入販売価格"]
        sku_cols.extend(f"バリエーション項目キー{i}" for i in range(1, 7))
        sku_cols.extend(f"バリエーション項目選択肢{i}" for i in range(1, 7))
        return self.row_has_any_value(row_idx, sku_cols)

    def is_parent_row(self, row_idx):
        if self.row_has_any_value(row_idx, PARENT_HINT_COLUMNS):
            return True
        return not self.is_option_row(row_idx) and not self.is_sku_row(row_idx)

    def get_parent_row(self, group):
        if self.product_group_info:
            product_idx = self.row_to_product_idx.get(group[0])
            if product_idx is not None:
                return self.product_group_info[product_idx]["parent_row"]
        for row in group:
            if self.is_parent_row(row):
                return row
        return group[0]

    def summarize_product_group(self, group):
        if self.product_group_info:
            product_idx = self.row_to_product_idx.get(group[0])
            if product_idx is not None:
                return self.product_group_info[product_idx]["summary"]
        if self.csv_kind == "item-cat":
            parent_row = self.get_parent_row(group)
            code = self.df.iloc[parent_row].get(PRODUCT_ID_COLUMN, "") if PRODUCT_ID_COLUMN in self.df.columns else ""
            return f"商品管理番号: {code} / カテゴリ行: {len(group)}"
        option_count = sum(1 for row in group if self.is_option_row(row))
        sku_count = sum(1 for row in group if self.is_sku_row(row))
        parent_row = self.get_parent_row(group)
        code = self.df.iloc[parent_row].get(PRODUCT_ID_COLUMN, "") if PRODUCT_ID_COLUMN in self.df.columns else ""
        return f"商品管理番号: {code} / 親SKU: 1 / オプション: {option_count} / 子SKU: {sku_count} / 行数: {len(group)}"

    def detect_csv_kind(self):
        if not self.column_list:
            return "unknown"
        if all(col in self.column_list for col in ITEM_CAT_COLUMNS) and "表示先カテゴリ" in self.column_list:
            return "item-cat"
        if SKU_ID_COLUMN in self.column_list or OPTION_TYPE_COLUMN in self.column_list or "商品画像パス1" in self.column_list:
            return "normal-item"
        return "unknown"

    def is_option_column(self, column):
        return (
            column in {OPTION_TYPE_COLUMN, OPTION_NAME_COLUMN, OPTION_REQUIRED_COLUMN}
            or column.startswith("商品オプション選択肢")
        )

    def is_sku_column(self, column):
        sku_exact_columns = {
            SKU_ID_COLUMN,
            "システム連携用SKU番号",
            "通常購入販売価格",
            "表示価格",
            "二重価格文言管理番号",
            "注文受付数",
            "再入荷お知らせボタン",
            "のし対応",
            "在庫数",
            "在庫戻しフラグ",
            "在庫切れ時の注文受付",
            "在庫あり時納期管理番号",
            "在庫切れ時納期管理番号",
            "在庫あり時出荷リードタイム",
            "在庫切れ時出荷リードタイム",
            "配送リードタイム",
            "SKU倉庫指定",
            "配送方法セット管理番号",
            "送料",
            "送料区分1",
            "送料区分2",
            "個別送料",
            "地域別個別送料管理番号",
            "単品配送設定使用",
            "海外配送管理番号",
            "カタログID",
            "カタログIDなしの理由",
            "セット商品用カタログID",
            "SKU画像タイプ",
            "SKU画像パス",
            "SKU画像名（ALT）",
            "定期購入販売価格",
            "定期用初回価格",
        }
        return (
            column in sku_exact_columns
            or (column.startswith("バリエーション項目キー") and not column.endswith("定義"))
            or column.startswith("バリエーション項目選択肢")
            or column.startswith("商品属性（")
            or column.startswith("自由入力行（")
        )

    def is_parent_column(self, column):
        if self.csv_kind == "item-cat":
            return True
        return not self.is_option_column(column) and not self.is_sku_column(column)

    def get_parent_columns(self):
        return [col for col in self.column_list if self.is_parent_column(col)]

    def group_products(self):
        if self.df is None or PRODUCT_ID_COLUMN not in self.df.columns:
            return []
        groups = []
        current_group = []
        current_code = None

        for row_idx, row in self.df.iterrows():
            code = row.get(PRODUCT_ID_COLUMN)
            if self.cell_has_value(code):
                code = str(code).strip()
                if current_group and code != current_code:
                    groups.append(current_group)
                    current_group = []
                current_code = code
            elif current_code is None and current_group:
                groups.append(current_group)
                current_group = []

            if current_code is not None or self.cell_has_value(code):
                current_group.append(row_idx)

        if current_group:
            groups.append(current_group)
        return groups

    def build_product_group_info(self):
        self.product_group_info = []
        self.row_to_product_idx = {}
        if self.df is None:
            return

        option_cols = [
            col for col in [OPTION_TYPE_COLUMN, OPTION_NAME_COLUMN, OPTION_REQUIRED_COLUMN]
            if col in self.df.columns
        ]
        option_cols.extend(col for col in (f"商品オプション選択肢{i}" for i in range(1, 101)) if col in self.df.columns)

        sku_cols = [
            col for col in [SKU_ID_COLUMN, "システム連携用SKU番号", "在庫数", "通常購入販売価格"]
            if col in self.df.columns
        ]
        sku_cols.extend(col for col in (f"バリエーション項目キー{i}" for i in range(1, 7)) if col in self.df.columns)
        sku_cols.extend(col for col in (f"バリエーション項目選択肢{i}" for i in range(1, 7)) if col in self.df.columns)

        parent_hint_cols = [col for col in PARENT_HINT_COLUMNS if col in self.df.columns]

        for product_idx, group in enumerate(self.product_groups):
            for row in group:
                self.row_to_product_idx[row] = product_idx

            option_rows = []
            sku_rows = []
            parent_row = group[0]
            parent_row_found = False

            for row in group:
                row_data = self.df.iloc[row]
                is_option = any(self.cell_has_value(row_data.get(col)) for col in option_cols)
                is_sku = any(self.cell_has_value(row_data.get(col)) for col in sku_cols)
                has_parent_hint = any(self.cell_has_value(row_data.get(col)) for col in parent_hint_cols)
                if is_option:
                    option_rows.append(row)
                if is_sku:
                    sku_rows.append(row)
                if has_parent_hint and not parent_row_found:
                    parent_row = row
                    parent_row_found = True

            code = self.df.iloc[parent_row].get(PRODUCT_ID_COLUMN, "") if PRODUCT_ID_COLUMN in self.df.columns else ""
            if self.csv_kind == "item-cat":
                summary = f"商品管理番号: {code} / カテゴリ行: {len(group)}"
            else:
                summary = f"商品管理番号: {code} / 親SKU: 1 / オプション: {len(option_rows)} / 子SKU: {len(sku_rows)} / 行数: {len(group)}"
            self.product_group_info.append({
                "parent_row": parent_row,
                "option_rows": set(option_rows),
                "sku_rows": set(sku_rows),
                "summary": summary,
            })

    def reset_selection_count(self):
        if not self.product_groups:
            self.selected_product_count = 0
            return
        self.selected_product_count = sum(
            1 for rows in self.product_groups
            if any(self.selected_rows[row] for row in rows)
        )

    def toggle_option_window(self):
        if self.option_grid_window and self.option_grid_window.winfo_exists():
            self.close_option_grid()
        else:
            self.show_option_window = True
            self.create_option_grid()
        self.update_option_button_state()

    def update_option_button_state(self):
        if hasattr(self, "option_button") and self.option_button:
            relief = tk.SUNKEN if self.show_option_window else tk.RAISED
            self.option_button.config(relief=relief)

    def get_option_columns(self):
        columns = [OPTION_TYPE_COLUMN, OPTION_NAME_COLUMN, OPTION_REQUIRED_COLUMN]
        columns.extend(f"商品オプション選択肢{i}" for i in range(1, 101))
        return [col for col in columns if col in self.column_list]

    def get_selected_product_indices(self):
        return [
            idx for idx, rows in enumerate(self.product_groups)
            if any(self.selected_rows[row] for row in rows)
        ]

    def get_product_rows_by_kind(self, product_indices, row_kind):
        rows = []
        for idx in product_indices:
            group = self.product_groups[idx]
            if row_kind == "option":
                rows.extend(row for row in group if self.is_option_row(row))
            elif row_kind == "sku":
                rows.extend(row for row in group if self.is_sku_row(row))
            else:
                rows.append(self.get_parent_row(group))
        return rows

    def apply_bulk_edit_to_rows(self, rows, columns, find_text="", replace_text="", prefix="", suffix="", mode="replace"):
        changed = 0
        has_var_find = "%" in find_text
        has_var_replace = "%" in replace_text
        has_var_prefix = "%" in prefix
        has_var_suffix = "%" in suffix
        for row_idx in rows:
            find_value = self.replace_with_column_vars(find_text, row_idx) if has_var_find else find_text
            replace_value = self.replace_with_column_vars(replace_text, row_idx) if has_var_replace else replace_text
            prefix_value = self.replace_with_column_vars(prefix, row_idx) if has_var_prefix else prefix
            suffix_value = self.replace_with_column_vars(suffix, row_idx) if has_var_suffix else suffix
            for col in columns:
                if col not in self.df.columns:
                    continue
                value = str(self.df.iloc[row_idx][col]) if pd.notna(self.df.iloc[row_idx][col]) else ""
                if mode == "replace":
                    new_value = value.replace(find_value, replace_value)
                else:
                    if not value:
                        continue
                    new_value = (prefix_value + value) if prefix_value else value
                    new_value = (new_value + suffix_value) if suffix_value else new_value
                if new_value != value:
                    self.df.at[row_idx, col] = new_value
                    changed += 1
        if changed:
            self.is_modified = True
            self.schedule_save_csv()
        return changed

    def apply_bulk_edit_to_item_cat_rows(self, rows, columns, find_text="", replace_text="", prefix="", suffix="", mode="replace"):
        if self.item_cat_df is None:
            return 0
        changed = 0
        for row_idx in rows:
            for col in columns:
                if col not in self.item_cat_df.columns:
                    continue
                value = str(self.item_cat_df.iloc[row_idx][col]) if pd.notna(self.item_cat_df.iloc[row_idx][col]) else ""
                if mode == "replace":
                    new_value = value.replace(find_text, replace_text)
                else:
                    if not value:
                        continue
                    new_value = (prefix + value) if prefix else value
                    new_value = (new_value + suffix) if suffix else new_value
                if new_value != value:
                    self.item_cat_df.at[row_idx, col] = new_value
                    changed += 1
        if changed:
            self.item_cat_is_modified = True
            self.build_item_cat_groups()
            self.schedule_save_item_cat_csv()
        return changed

    def create_subwindow_edit_bar(self, parent, column_var, columns, find_attr, replace_attr, replace_command, append_command, column_command=None):
        frame = ttk.LabelFrame(parent, text="選択中商品へ一括編集", padding=5)
        frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(frame, text="列", font=("Meiryo", 9)).pack(side=tk.LEFT)
        combo = ttk.Combobox(frame, textvariable=column_var, values=columns, state="readonly", width=28, font=("Meiryo", 9))
        combo.pack(side=tk.LEFT, padx=5)
        if column_command:
            combo.bind("<<ComboboxSelected>>", column_command)
        setattr(self, find_attr, Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken"))
        getattr(self, find_attr).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(frame, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
        setattr(self, replace_attr, Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken"))
        getattr(self, replace_attr).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame, text="置換", command=replace_command, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="追加", command=append_command, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)

    def create_sku_edit_bar(self, parent):
        frame = ttk.LabelFrame(parent, text="選択中商品へ一括編集", padding=5)
        frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.add_subwindow_selected_count_label(frame)
        tk.Label(frame, text="対象: チェック列", font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.sku_find_text = Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.sku_find_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(frame, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.sku_replace_text = Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.sku_replace_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame, text="置換", command=self.apply_sku_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="追加", command=self.apply_sku_append, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="クリア", command=lambda: self.clear_subwindow_edit_texts("sku_find_text", "sku_replace_text"), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)

    def create_checked_columns_edit_bar(self, parent, find_attr, replace_attr, replace_command, append_command):
        frame = ttk.LabelFrame(parent, text="選択中商品へ一括編集", padding=5)
        frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.add_subwindow_selected_count_label(frame)
        tk.Label(frame, text="対象: チェック列", font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(0, 5))
        setattr(self, find_attr, Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken"))
        getattr(self, find_attr).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(frame, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
        setattr(self, replace_attr, Text(frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken"))
        getattr(self, replace_attr).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame, text="置換", command=replace_command, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="追加", command=append_command, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="クリア", command=lambda: self.clear_subwindow_edit_texts(find_attr, replace_attr), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)

    def clear_subwindow_edit_texts(self, find_attr, replace_attr):
        find_widget = getattr(self, find_attr, None)
        replace_widget = getattr(self, replace_attr, None)
        if find_widget:
            find_widget.delete("1.0", tk.END)
        if replace_widget:
            replace_widget.delete("1.0", tk.END)

    def get_selected_product_count_text(self):
        total = len(self.product_groups) if self.product_groups else 0
        return f"選択中 {self.selected_product_count}/{total}"

    def add_subwindow_selected_count_label(self, parent):
        var = tk.StringVar(value=self.get_selected_product_count_text())
        self.subwindow_selected_count_vars.append(var)
        tk.Label(parent, textvariable=var, font=("Meiryo", 9), width=16, anchor="w").pack(side=tk.LEFT, padx=(0, 8))

    def update_subwindow_selected_count_labels(self):
        text = self.get_selected_product_count_text()
        alive_vars = []
        for var in self.subwindow_selected_count_vars:
            try:
                var.set(text)
                alive_vars.append(var)
            except tk.TclError:
                pass
        self.subwindow_selected_count_vars = alive_vars

    def apply_option_replace(self):
        self.apply_subwindow_edit("option", "replace")

    def apply_option_append(self):
        self.apply_subwindow_edit("option", "append")

    def apply_sku_replace(self):
        self.apply_subwindow_edit("sku", "replace")

    def apply_sku_append(self):
        self.apply_subwindow_edit("sku", "append")

    def apply_category_replace(self):
        self.apply_category_edit("replace")

    def apply_category_append(self):
        self.apply_category_edit("append")

    def apply_category_edit(self, mode):
        if self.item_cat_df is None:
            return
        self.save_category_entries()
        columns = [
            col for col, var in self.category_bulk_column_check_vars.items()
            if var.get() and col in self.item_cat_df.columns
        ]
        if not columns:
            self.show_message("警告", "対象列を選択してください。")
            return
        product_indices = self.get_selected_product_indices()
        if not product_indices:
            self.show_message("警告", "メインウィンドウで商品を選択してください。")
            return
        rows = []
        for product_idx in product_indices:
            parent_row = self.get_parent_row(self.product_groups[product_idx])
            code_value = self.df.iloc[parent_row].get(PRODUCT_ID_COLUMN) if PRODUCT_ID_COLUMN in self.df.columns else ""
            code = str(code_value).strip() if self.cell_has_value(code_value) else ""
            rows.extend(self.item_cat_groups.get(code, []))
        if not rows:
            self.show_message("警告", "対象カテゴリ行がありません。")
            return
        left_text = self.category_find_text.get("1.0", tk.END).rstrip("\n") if self.category_find_text else ""
        right_text = self.category_replace_text.get("1.0", tk.END).rstrip("\n") if self.category_replace_text else ""
        if mode == "replace":
            if not left_text.strip():
                self.show_message("警告", "検索文字列を入力してください。")
                return
            changed = self.apply_bulk_edit_to_item_cat_rows(rows, columns, find_text=left_text, replace_text=right_text, mode="replace")
        else:
            if not left_text.strip() and not right_text.strip():
                self.show_message("警告", "追加する文字列を入力してください。")
                return
            changed = self.apply_bulk_edit_to_item_cat_rows(rows, columns, prefix=left_text, suffix=right_text, mode="append")
        self.refresh_category_table()
        self.show_message("完了", f"{changed}件を更新しました。")

    def apply_subwindow_edit(self, row_kind, mode):
        if self.df is None:
            return
        if row_kind == "option":
            self.save_option_entries()
            columns = self.get_checked_option_bulk_columns()
            find_widget = self.option_find_text
            replace_widget = self.option_replace_text
        else:
            self.save_sku_entries()
            columns = [
                col for col in self.sku_display_columns
                if self.sku_bulk_column_check_vars.get(col) is not None and self.sku_bulk_column_check_vars[col].get()
            ]
            find_widget = self.sku_find_text
            replace_widget = self.sku_replace_text
        if not columns:
            self.show_message("警告", "対象列を選択してください。")
            return
        product_indices = self.get_selected_product_indices()
        if not product_indices:
            self.show_message("警告", "メインウィンドウで商品を選択してください。")
            return
        rows = self.get_product_rows_by_kind(product_indices, row_kind)
        if not rows:
            self.show_message("警告", "対象行がありません。")
            return
        left_text = find_widget.get("1.0", tk.END).rstrip("\n") if find_widget else ""
        right_text = replace_widget.get("1.0", tk.END).rstrip("\n") if replace_widget else ""
        if mode == "replace":
            if not left_text.strip():
                self.show_message("警告", "検索文字列を入力してください。")
                return
            changed = self.apply_bulk_edit_to_rows(rows, columns, find_text=left_text, replace_text=right_text, mode="replace")
        else:
            if not left_text.strip() and not right_text.strip():
                self.show_message("警告", "追加する文字列を入力してください。")
                return
            changed = self.apply_bulk_edit_to_rows(rows, columns, prefix=left_text, suffix=right_text, mode="append")
        self.update_display()
        self.show_message("完了", f"{changed}件を更新しました。")

    def get_checked_option_bulk_columns(self):
        columns = []
        for col, var in self.option_bulk_column_check_vars.items():
            if not var.get():
                continue
            if col == "商品オプション選択肢":
                columns.extend(
                    choice_col for choice_col in (f"商品オプション選択肢{i}" for i in range(1, 101))
                    if choice_col in self.df.columns
                )
            elif col in self.df.columns:
                columns.append(col)
        return columns

    def create_option_grid(self):
        if self.df is None or self.current_product_idx >= len(self.product_groups):
            self.show_option_window = False
            self.update_option_button_state()
            return
        self.show_option_window = True
        if self.option_grid_window is None:
            self.option_grid_window = tk.Toplevel(self.root)
            self.option_grid_window.title("オプション編集")
            self.option_grid_window.geometry("900x420")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 450
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 200
            self.option_grid_window.geometry(f"+{x}+{y}")
            self.option_grid_window.transient(self.root)
            self.option_grid_window.resizable(True, True)
            self.option_grid_window.protocol("WM_DELETE_WINDOW", self.close_option_grid)
            self.option_column_var = None
            self.create_checked_columns_edit_bar(
                self.option_grid_window,
                "option_find_text",
                "option_replace_text",
                self.apply_option_replace,
                self.apply_option_append
            )
            option_body_frame = tk.Frame(self.option_grid_window)
            option_body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.option_canvas = tk.Canvas(option_body_frame)
            self.option_scrollbar = tk.Scrollbar(option_body_frame, orient="vertical", command=self.option_canvas.yview)
            self.option_h_scrollbar = tk.Scrollbar(option_body_frame, orient="horizontal", command=self.option_canvas.xview)
            self.option_scrollable_frame = tk.Frame(self.option_canvas)
            self.option_scrollable_frame.bind("<Configure>", lambda e: self.option_canvas.configure(scrollregion=self.option_canvas.bbox("all")))
            self.option_canvas.create_window((0, 0), window=self.option_scrollable_frame, anchor="nw")
            self.option_canvas.configure(yscrollcommand=self.option_scrollbar.set, xscrollcommand=self.option_h_scrollbar.set)
            self.option_canvas.grid(row=0, column=0, sticky="nsew")
            self.option_scrollbar.grid(row=0, column=1, sticky="ns")
            self.option_h_scrollbar.grid(row=1, column=0, sticky="ew")
            option_body_frame.grid_rowconfigure(0, weight=1)
            option_body_frame.grid_columnconfigure(0, weight=1)
            self.bind_subwindow_mousewheel(self.option_grid_window, self.option_canvas)
            tk.Button(self.option_grid_window, text="閉じる", command=self.close_option_grid, font=("Meiryo", 9)).pack(pady=5)
        else:
            for widget in self.option_scrollable_frame.winfo_children():
                widget.destroy()
        group = self.product_groups[self.current_product_idx]
        option_rows = []
        for row in group:
            if self.is_option_row(row):
                option_rows.append(row)
        headers = ["選択肢タイプ", "商品オプション項目名", "商品オプション選択肢", "商品オプション選択必須"]
        self.option_display_columns = headers
        for j, header in enumerate(headers):
            header_frame = tk.Frame(self.option_scrollable_frame, borderwidth=1, relief="solid")
            header_frame.grid(row=0, column=j, sticky="nsew")
            var = self.option_bulk_column_check_vars.get(header)
            if var is None:
                var = tk.BooleanVar(value=False)
                self.option_bulk_column_check_vars[header] = var
            tk.Checkbutton(header_frame, variable=var, font=("Meiryo", 8)).pack(side=tk.LEFT)
            tk.Label(header_frame, text=header, font=("Meiryo", 9), width=24, anchor="w").pack(side=tk.LEFT)
        self.option_entries = []
        for i, row in enumerate(option_rows):
            grid_row = i + 1
            entries = []
            type_entry = tk.Entry(self.option_scrollable_frame, font=("Meiryo", 9))
            type_entry.grid(row=grid_row, column=0, sticky="nsew")
            type_entry.insert(0, str(self.df.iloc[row]['選択肢タイプ']) if pd.notna(self.df.iloc[row]['選択肢タイプ']) else "")
            type_entry.bind("<FocusOut>", lambda event, idx=row: self.update_option_entry(idx))
            entries.append(type_entry)
            name_entry = tk.Entry(self.option_scrollable_frame, font=("Meiryo", 9))
            name_entry.grid(row=grid_row, column=1, sticky="nsew")
            name_entry.insert(0, str(self.df.iloc[row]['商品オプション項目名']) if pd.notna(self.df.iloc[row]['商品オプション項目名']) else "")
            name_entry.bind("<FocusOut>", lambda event, idx=row: self.update_option_entry(idx))
            entries.append(name_entry)
            choices = []
            for col in [f'商品オプション選択肢{k}' for k in range(1, 101)]:
                if col in self.df.columns and pd.notna(self.df.iloc[row][col]):
                    choices.append(str(self.df.iloc[row][col]))
            choice_text = tk.Text(self.option_scrollable_frame, font=("Meiryo", 9), height=1, width=30)
            choice_text.grid(row=grid_row, column=2, sticky="nsew")
            choice_text.insert("1.0", "\n".join(choices) if choices else "")
            choice_text.bind("<FocusOut>", lambda event, idx=row: self.update_option_entry(idx))
            entries.append(choice_text)
            must_entry = tk.Entry(self.option_scrollable_frame, font=("Meiryo", 9))
            must_entry.grid(row=grid_row, column=3, sticky="nsew")
            must_entry.insert(0, str(self.df.iloc[row]['商品オプション選択必須']) if pd.notna(self.df.iloc[row]['商品オプション選択必須']) else "")
            must_entry.bind("<FocusOut>", lambda event, idx=row: self.update_option_entry(idx))
            entries.append(must_entry)
            self.option_entries.append((row, entries))
        for j in range(len(headers)):
            self.option_scrollable_frame.grid_columnconfigure(j, weight=1)
        self.option_scrollable_frame.grid_columnconfigure(1, weight=2)
        self.option_scrollable_frame.grid_columnconfigure(2, weight=2)

    def update_option_entry(self, row_idx):
        if self.df is None or not self.option_entries:
            return
        for row, (type_entry, name_entry, choice_text, must_entry) in self.option_entries:
            if row == row_idx:
                type_val = type_entry.get().strip()
                name_val = name_entry.get().strip()
                choice_val = choice_text.get("1.0", tk.END).strip()
                must_val = must_entry.get().strip()
                self.df.at[row_idx, '選択肢タイプ'] = type_val if type_val else ""
                self.df.at[row_idx, '商品オプション項目名'] = name_val if name_val else ""
                choices = choice_val.split("\n") if choice_val else []
                for i, choice in enumerate(choices, 1):
                    col_name = f'商品オプション選択肢{i}'
                    if col_name in self.df.columns:
                        self.df.at[row_idx, col_name] = choice.strip() if choice.strip() else ""
                for i in range(len(choices) + 1, 101):
                    col_name = f'商品オプション選択肢{i}'
                    if col_name in self.df.columns:
                        self.df.at[row_idx, col_name] = ""
                self.df.at[row_idx, '商品オプション選択必須'] = must_val if must_val else ""
                self.is_modified = True
                self.schedule_save_csv()
                break

    def close_option_grid(self):
        if self.option_grid_window:
            self.unbind_subwindow_mousewheel(self.option_grid_window)
            self.option_grid_window.destroy()
            self.option_grid_window = None
            self.option_entries = []
            self.option_column_var = None
            self.option_find_text = None
            self.option_replace_text = None
            self.option_bulk_column_check_vars = {}
        self.show_option_window = False
        self.update_option_button_state()

    def get_category_edit_columns(self):
        if self.item_cat_df is None:
            return []
        preferred = ["コントロールカラム", PRODUCT_ID_COLUMN, "表示先カテゴリ", "優先度", "URL", "1ページ複数形式"]
        columns = [col for col in preferred if col in self.item_cat_df.columns]
        columns.extend(col for col in self.item_cat_df.columns if col not in columns)
        return columns

    def show_category_grid(self):
        if self.item_cat_df is None:
            self.show_message("警告", "カテゴリCSVを追加読込してください。")
            return
        code = self.get_current_product_code()
        if not code:
            self.show_message("警告", "現在商品の商品管理番号が取得できません。")
            return
        if self.category_grid_window is None or not self.category_grid_window.winfo_exists():
            self.category_grid_window = tk.Toplevel(self.root)
            self.category_grid_window.geometry("900x380")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 450
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 210
            self.category_grid_window.geometry(f"+{x}+{y}")
            self.category_grid_window.transient(self.root)
            self.category_grid_window.resizable(True, True)
            self.category_grid_window.protocol("WM_DELETE_WINDOW", self.close_category_grid)
            self.create_checked_columns_edit_bar(
                self.category_grid_window,
                "category_find_text",
                "category_replace_text",
                self.apply_category_replace,
                self.apply_category_append
            )
            category_action_frame = tk.Frame(self.category_grid_window)
            category_action_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
            tk.Button(category_action_frame, text="行追加", command=self.add_category_row, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=4)
            body_frame = tk.Frame(self.category_grid_window)
            body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.category_canvas = tk.Canvas(body_frame)
            v_scrollbar = tk.Scrollbar(body_frame, orient="vertical", command=self.category_canvas.yview)
            h_scrollbar = tk.Scrollbar(body_frame, orient="horizontal", command=self.category_canvas.xview)
            self.category_scrollable_frame = tk.Frame(self.category_canvas)
            self.category_scrollable_frame.bind("<Configure>", lambda e: self.category_canvas.configure(scrollregion=self.category_canvas.bbox("all")))
            self.category_canvas.create_window((0, 0), window=self.category_scrollable_frame, anchor="nw")
            self.category_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            self.category_canvas.grid(row=0, column=0, sticky="nsew")
            v_scrollbar.grid(row=0, column=1, sticky="ns")
            h_scrollbar.grid(row=1, column=0, sticky="ew")
            body_frame.grid_rowconfigure(0, weight=1)
            body_frame.grid_columnconfigure(0, weight=1)
            self.bind_subwindow_mousewheel(self.category_grid_window, self.category_canvas)
            tk.Button(self.category_grid_window, text="閉じる", command=self.close_category_grid, font=("Meiryo", 9)).pack(pady=5)
        self.refresh_category_table()

    def refresh_category_table(self, save_before=True):
        if self.item_cat_df is None or not self.category_scrollable_frame:
            return
        if save_before:
            self.save_category_entries()
        for widget in self.category_scrollable_frame.winfo_children():
            widget.destroy()
        code = self.get_current_product_code()
        rows = self.item_cat_groups.get(code, [])
        self.category_grid_window.title(f"カテゴリ編集: {code} ({len(rows)}行)")
        columns = self.get_category_edit_columns()
        if not rows:
            tk.Label(
                self.category_scrollable_frame,
                text="この商品のカテゴリ行はitem-cat内に見つかりません。",
                font=("Meiryo", 10),
                padx=12,
                pady=12
            ).grid(row=0, column=0, sticky="w")
            self.category_entries = []
            return
        tk.Label(self.category_scrollable_frame, text="行操作", font=("Meiryo", 9), borderwidth=1, relief="solid", width=16).grid(row=0, column=0, sticky="nsew")
        for j, col in enumerate(columns):
            header_frame = tk.Frame(self.category_scrollable_frame, borderwidth=1, relief="solid")
            header_frame.grid(row=0, column=j + 1, sticky="nsew")
            var = self.category_bulk_column_check_vars.get(col)
            if var is None:
                var = tk.BooleanVar(value=False)
                self.category_bulk_column_check_vars[col] = var
            tk.Checkbutton(header_frame, variable=var, font=("Meiryo", 8)).pack(side=tk.LEFT)
            tk.Label(header_frame, text=col, font=("Meiryo", 9), width=24, anchor="w").pack(side=tk.LEFT)
        self.category_entries = []
        for i, row in enumerate(rows):
            grid_row = i + 1
            op_frame = tk.Frame(self.category_scrollable_frame, borderwidth=1, relief="solid")
            op_frame.grid(row=grid_row, column=0, sticky="nsew")
            tk.Label(op_frame, text=str(i + 1), font=("Meiryo", 9), width=3).pack(side=tk.LEFT)
            tk.Button(op_frame, text="▲", command=lambda idx=i: self.move_category_row(idx, -1), font=("Meiryo", 8), width=2).pack(side=tk.LEFT)
            tk.Button(op_frame, text="▼", command=lambda idx=i: self.move_category_row(idx, 1), font=("Meiryo", 8), width=2).pack(side=tk.LEFT)
            tk.Button(op_frame, text="削除", command=lambda idx=i: self.delete_category_row(idx), font=("Meiryo", 8), width=4).pack(side=tk.LEFT)
            for j, col in enumerate(columns):
                entry = tk.Entry(self.category_scrollable_frame, font=("Meiryo", 9), width=24)
                entry.grid(row=grid_row, column=j + 1, sticky="nsew")
                value = str(self.item_cat_df.iloc[row][col]) if pd.notna(self.item_cat_df.iloc[row][col]) else ""
                entry.insert(0, value)
                entry.bind("<FocusOut>", lambda event, r=row, c=col: self.update_category_entry(r, c))
                self.category_entries.append((row, col, entry))
        for j in range(len(columns) + 1):
            self.category_scrollable_frame.grid_columnconfigure(j, weight=1)

    def update_category_entry(self, row, column):
        if self.item_cat_df is None or not self.category_entries:
            return
        for r, c, entry in self.category_entries:
            if r == row and c == column:
                value = entry.get().strip()
                self.item_cat_df.at[row, column] = value
                self.item_cat_is_modified = True
                self.build_item_cat_groups()
                self.schedule_save_item_cat_csv()
                break

    def save_category_entries(self):
        if self.item_cat_df is None or not self.category_entries:
            return
        changed = False
        for row, column, entry in self.category_entries:
            value = entry.get().strip()
            current_value = str(self.item_cat_df.iloc[row][column]) if pd.notna(self.item_cat_df.iloc[row][column]) else ""
            if value != current_value:
                self.item_cat_df.at[row, column] = value
                changed = True
        if changed:
            self.item_cat_is_modified = True
            self.build_item_cat_groups()
            self.schedule_save_item_cat_csv()

    def get_current_category_rows(self):
        code = self.get_current_product_code()
        return list(self.item_cat_groups.get(code, []))

    def mark_item_cat_changed(self):
        self.item_cat_is_modified = True
        self.build_item_cat_groups()
        self.schedule_save_item_cat_csv()
        self.category_entries = []
        self.refresh_category_table(save_before=False)

    def add_category_row(self):
        if self.item_cat_df is None:
            return
        self.save_category_entries()
        code = self.get_current_product_code()
        if not code:
            self.show_message("警告", "現在商品の商品管理番号が取得できません。")
            return
        new_row = {col: "" for col in self.item_cat_df.columns}
        if "コントロールカラム" in self.item_cat_df.columns:
            new_row["コントロールカラム"] = "n"
        if PRODUCT_ID_COLUMN in self.item_cat_df.columns:
            new_row[PRODUCT_ID_COLUMN] = code
        self.item_cat_df.loc[len(self.item_cat_df)] = new_row
        self.mark_item_cat_changed()

    def delete_category_row(self, row_position):
        if self.item_cat_df is None:
            return
        self.save_category_entries()
        rows = self.get_current_category_rows()
        if row_position < 0 or row_position >= len(rows):
            return
        row_idx = rows[row_position]
        if not self.show_confirm("確認", "このカテゴリ行を削除しますか？"):
            return
        self.item_cat_df = self.item_cat_df.drop(index=row_idx).reset_index(drop=True)
        self.mark_item_cat_changed()

    def move_category_row(self, row_position, direction):
        if self.item_cat_df is None:
            return
        self.save_category_entries()
        rows = self.get_current_category_rows()
        target_position = row_position + direction
        if row_position < 0 or row_position >= len(rows) or target_position < 0 or target_position >= len(rows):
            return
        row_a = rows[row_position]
        row_b = rows[target_position]
        order = list(self.item_cat_df.index)
        pos_a = order.index(row_a)
        pos_b = order.index(row_b)
        order[pos_a], order[pos_b] = order[pos_b], order[pos_a]
        self.item_cat_df = self.item_cat_df.loc[order].reset_index(drop=True)
        self.mark_item_cat_changed()

    def close_category_grid(self):
        if self.category_grid_window:
            self.save_category_entries()
            self.unbind_subwindow_mousewheel(self.category_grid_window)
            self.category_grid_window.destroy()
            self.category_grid_window = None
            self.category_canvas = None
            self.category_scrollable_frame = None
            self.category_entries = []
            self.category_find_text = None
            self.category_replace_text = None
            self.category_bulk_column_check_vars = {}

    def get_cached_thumbnail_photo(self, url, size=100):
        if not url:
            return None
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.jpg"
        if url in self.image_cache_map and cache_path.exists():
            try:
                img = Image.open(cache_path)
                img.thumbnail((size, size))
                photo = ImageTk.PhotoImage(img)
                return photo
            except Exception as e:
                logging.warning(f"画像キャッシュ読み込み失敗: URL={url}, {e}")
        return None

    def cache_single_image(self, url, label=None, refresh=True):
        if not url:
            self.show_message("警告", "画像URLがありません。")
            return False
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_key = hashlib.md5(url.encode()).hexdigest()
            cache_path = self.cache_dir / f"{cache_key}.jpg"
            response = requests.get(url, stream=True, timeout=8)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            img.thumbnail((200, 200))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(str(cache_path), "JPEG")
            self.image_cache_map[url] = str(cache_path)
            photo = ImageTk.PhotoImage(img)
            self.remember_memory_image(url, photo)
            self.save_image_cache_map()
            if refresh and self.image_manage_window and self.image_manage_window.winfo_exists():
                self.refresh_image_manage_window()
            return True
        except Exception as e:
            self.show_message("エラー", f"{label or '画像'}のキャッシュに失敗しました: {str(e)}", msg_type="error")
            return False

    def get_current_image_items(self):
        items = []
        if self.df is None or self.current_product_idx >= len(self.product_groups):
            return items
        group = self.product_groups[self.current_product_idx]
        parent_row = self.get_parent_row(group)
        for i in range(1, 21):
            path_col = f"商品画像パス{i}"
            alt_col = f"商品画像名（ALT）{i}"
            if path_col in self.df.columns or alt_col in self.df.columns:
                items.append({
                    "kind": "parent",
                    "row": parent_row,
                    "title": f"商品画像 {i}",
                    "path_col": path_col,
                    "alt_col": alt_col,
                })
        if "白背景画像パス" in self.df.columns:
            items.append({
                "kind": "parent",
                "row": parent_row,
                "title": "白背景画像",
                "path_col": "白背景画像パス",
                "alt_col": None,
            })
        for sku_index, row in enumerate([r for r in group if self.is_sku_row(r)], 1):
            if "SKU画像パス" in self.df.columns or "SKU画像名（ALT）" in self.df.columns:
                sku_code = self.df.iloc[row].get(SKU_ID_COLUMN, "") if SKU_ID_COLUMN in self.df.columns else ""
                title = f"SKU画像 {sku_index}"
                if self.cell_has_value(sku_code):
                    title += f" / {sku_code}"
                items.append({
                    "kind": "sku",
                    "row": row,
                    "title": title,
                    "path_col": "SKU画像パス",
                    "alt_col": "SKU画像名（ALT）",
                })
        return items

    def show_image_manage_window(self):
        if self.df is None:
            self.show_message("警告", "CSVを読み込んでください。")
            return
        if self.image_manage_window is None or not self.image_manage_window.winfo_exists():
            self.image_manage_window = tk.Toplevel(self.root)
            self.image_manage_window.geometry("1100x720")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 550
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 360
            self.image_manage_window.geometry(f"+{x}+{y}")
            self.image_manage_window.transient(self.root)
            self.image_manage_window.resizable(True, True)
            self.image_manage_window.protocol("WM_DELETE_WINDOW", self.close_image_manage_window)
            top_frame = tk.Frame(self.image_manage_window)
            top_frame.pack(fill=tk.X, padx=8, pady=6)
            tk.Button(top_frame, text="この商品の画像をキャッシュ", command=self.cache_current_product_images, font=("Meiryo", 9)).pack(side=tk.LEFT)
            self.image_bulk_url_var = tk.BooleanVar(value=False)
            self.image_bulk_alt_var = tk.BooleanVar(value=True)
            tk.Checkbutton(top_frame, text="URL", variable=self.image_bulk_url_var, command=lambda: self.set_image_bulk_item_vars("url", self.image_bulk_url_var.get()), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(10, 2))
            tk.Checkbutton(top_frame, text="ALT", variable=self.image_bulk_alt_var, command=lambda: self.set_image_bulk_item_vars("alt", self.image_bulk_alt_var.get()), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            self.image_bulk_scope_var = tk.StringVar(value="既存選択")
            ttk.Combobox(top_frame, textvariable=self.image_bulk_scope_var, values=["既存選択", "すべて選択"], state="readonly", width=10, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(4, 5))
            self.image_find_text = Text(top_frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
            self.image_find_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            tk.Label(top_frame, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
            self.image_replace_text = Text(top_frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
            self.image_replace_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            tk.Button(top_frame, text="置換", command=self.apply_image_bulk_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="追加", command=self.apply_image_bulk_append, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="削除", command=self.apply_image_bulk_delete, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="クリア", command=lambda: self.clear_subwindow_edit_texts("image_find_text", "image_replace_text"), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="閉じる", command=self.close_image_manage_window, font=("Meiryo", 9)).pack(side=tk.RIGHT)
            progress_frame = tk.Frame(self.image_manage_window)
            progress_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
            self.image_cache_progress_var = tk.DoubleVar(value=0)
            ttk.Progressbar(progress_frame, variable=self.image_cache_progress_var, maximum=100).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
            self.image_cache_progress_label = tk.Label(progress_frame, text="0/0", font=("Meiryo", 9), width=12)
            self.image_cache_progress_label.pack(side=tk.LEFT)
            body_frame = tk.Frame(self.image_manage_window)
            body_frame.pack(fill=tk.BOTH, expand=True)
            self.image_manage_canvas = tk.Canvas(body_frame)
            v_scrollbar = tk.Scrollbar(body_frame, orient="vertical", command=self.image_manage_canvas.yview)
            self.image_manage_scrollable_frame = tk.Frame(self.image_manage_canvas)
            self.image_manage_scrollable_frame.bind("<Configure>", lambda e: self.image_manage_canvas.configure(scrollregion=self.image_manage_canvas.bbox("all")))
            self.image_manage_canvas.create_window((0, 0), window=self.image_manage_scrollable_frame, anchor="nw")
            self.image_manage_canvas.configure(yscrollcommand=v_scrollbar.set)
            self.image_manage_canvas.grid(row=0, column=0, sticky="nsew")
            v_scrollbar.grid(row=0, column=1, sticky="ns")
            body_frame.grid_rowconfigure(0, weight=1)
            body_frame.grid_columnconfigure(0, weight=1)
            self.bind_subwindow_mousewheel(self.image_manage_window, self.image_manage_canvas)
        self.refresh_image_manage_window()

    def refresh_image_manage_window(self, save_before=True):
        if not self.image_manage_window or not self.image_manage_window.winfo_exists() or not self.image_manage_scrollable_frame:
            return
        if save_before:
            self.save_image_manage_entries()
        for widget in self.image_manage_scrollable_frame.winfo_children():
            widget.destroy()
        self.image_manage_entries = []
        self.image_manage_photos = []
        self.image_bulk_item_vars = {}
        code = self.get_current_product_code()
        self.image_manage_window.title(f"画像管理: {code}")
        items = self.get_current_image_items()
        if not items:
            tk.Label(self.image_manage_scrollable_frame, text="画像関連カラムがありません。", font=("Meiryo", 10), padx=12, pady=12).grid(row=0, column=0, sticky="w")
            return
        for index, item in enumerate(items):
            row = index // 2
            col = index % 2
            frame = ttk.LabelFrame(self.image_manage_scrollable_frame, text=item["title"], padding=6)
            frame.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            self.image_manage_scrollable_frame.grid_columnconfigure(col, weight=1)
            thumb = tk.Canvas(frame, width=100, height=100, bg="white", highlightthickness=1, highlightbackground="#cccccc")
            thumb.grid(row=0, column=0, rowspan=4, padx=(0, 8), pady=2)
            path_value = self.df.iloc[item["row"]].get(item["path_col"], "") if item["path_col"] in self.df.columns else ""
            url = self.build_rakuten_image_url(path_value)
            photo = self.get_cached_thumbnail_photo(url, size=100)
            if photo:
                self.image_manage_photos.append(photo)
                thumb.create_image(50, 50, image=photo)
            else:
                thumb.create_text(50, 50, text="未キャッシュ", font=("Meiryo", 9), fill="#666666")
            url_checked = self.get_initial_image_bulk_check("url", path_value)
            url_var = tk.BooleanVar(value=url_checked)
            self.image_bulk_item_vars[(item["row"], item["path_col"])] = url_var
            url_header = tk.Frame(frame)
            url_header.grid(row=0, column=1, sticky="ew")
            tk.Checkbutton(url_header, variable=url_var, font=("Meiryo", 8)).pack(side=tk.LEFT)
            tk.Label(url_header, text="URL", font=("Meiryo", 9)).pack(side=tk.LEFT)
            path_entry = tk.Entry(frame, font=("Meiryo", 9), width=48)
            path_entry.grid(row=1, column=1, sticky="ew")
            path_entry.insert(0, str(path_value) if pd.notna(path_value) else "")
            alt_entry = None
            if item["alt_col"] and item["alt_col"] in self.df.columns:
                alt_value = self.df.iloc[item["row"]].get(item["alt_col"], "")
                alt_checked = self.get_initial_image_bulk_check("alt", alt_value)
                alt_var = tk.BooleanVar(value=alt_checked)
                self.image_bulk_item_vars[(item["row"], item["alt_col"])] = alt_var
                alt_header = tk.Frame(frame)
                alt_header.grid(row=2, column=1, sticky="ew", pady=(4, 0))
                tk.Checkbutton(alt_header, variable=alt_var, font=("Meiryo", 8)).pack(side=tk.LEFT)
                tk.Label(alt_header, text="ALT", font=("Meiryo", 9)).pack(side=tk.LEFT)
                alt_entry = tk.Entry(frame, font=("Meiryo", 9), width=48)
                alt_entry.grid(row=3, column=1, sticky="ew")
                alt_entry.insert(0, str(alt_value) if pd.notna(alt_value) else "")
            frame.grid_columnconfigure(1, weight=1)
            self.image_manage_entries.append((item["row"], item["path_col"], path_entry, item["alt_col"], alt_entry))

    def save_image_manage_entries(self):
        if self.df is None or not self.image_manage_entries:
            return
        changed = False
        for row, path_col, path_entry, alt_col, alt_entry in self.image_manage_entries:
            if path_col in self.df.columns:
                value = path_entry.get().strip()
                current = str(self.df.iloc[row][path_col]) if pd.notna(self.df.iloc[row][path_col]) else ""
                if value != current:
                    self.df.at[row, path_col] = value
                    changed = True
            if alt_col and alt_entry and alt_col in self.df.columns:
                value = alt_entry.get().strip()
                current = str(self.df.iloc[row][alt_col]) if pd.notna(self.df.iloc[row][alt_col]) else ""
                if value != current:
                    self.df.at[row, alt_col] = value
                    changed = True
        if changed:
            self.is_modified = True
            self.schedule_save_csv()

    def get_image_bulk_targets(self):
        targets = []
        seen = set()
        for key, var in self.image_bulk_item_vars.items():
            row, col = key
            if var.get() and col in self.df.columns and key not in seen:
                targets.append(key)
                seen.add(key)
        return targets

    def get_initial_image_bulk_check(self, target_type, value):
        if target_type == "url":
            checked = self.image_bulk_url_var.get() if self.image_bulk_url_var else False
        else:
            checked = self.image_bulk_alt_var.get() if self.image_bulk_alt_var else False
        if not checked:
            return False
        scope = self.image_bulk_scope_var.get() if self.image_bulk_scope_var else "既存選択"
        if scope == "すべて選択":
            return True
        return self.cell_has_value(value)

    def set_image_bulk_item_vars(self, target_type, value):
        for (row, col), var in self.image_bulk_item_vars.items():
            is_alt = "ALT" in col
            if target_type == "alt" and not is_alt:
                continue
            if target_type == "url" and is_alt:
                continue
            if not value:
                var.set(False)
                continue
            if self.image_bulk_scope_var and self.image_bulk_scope_var.get() == "既存選択":
                current = self.df.iloc[row].get(col) if col in self.df.columns else ""
                var.set(self.cell_has_value(current))
                continue
            if target_type == "alt" and is_alt:
                var.set(value)
            elif target_type == "url" and not is_alt:
                var.set(value)

    def apply_image_bulk_replace(self):
        self.apply_image_bulk_edit("replace")

    def apply_image_bulk_append(self):
        self.apply_image_bulk_edit("append")

    def apply_image_bulk_delete(self):
        self.apply_image_bulk_edit("delete")

    def apply_image_bulk_edit(self, mode):
        if self.df is None:
            return
        self.save_image_manage_entries()
        targets = self.get_image_bulk_targets()
        if not targets:
            self.show_message("警告", "URLまたはALTを選択してください。")
            return
        left_text = self.image_find_text.get("1.0", tk.END).rstrip("\n") if self.image_find_text else ""
        right_text = self.image_replace_text.get("1.0", tk.END).rstrip("\n") if self.image_replace_text else ""
        if mode == "replace" and not left_text.strip():
            self.show_message("警告", "検索文字列を入力してください。")
            return
        if mode == "append" and not left_text.strip() and not right_text.strip():
            self.show_message("警告", "追加する文字列を入力してください。")
            return
        changed = 0
        for row, col in targets:
            value = str(self.df.iloc[row][col]) if pd.notna(self.df.iloc[row][col]) else ""
            if mode == "replace":
                new_value = value.replace(left_text, right_text)
            elif mode == "delete":
                new_value = ""
            else:
                if not value:
                    continue
                new_value = (left_text + value) if left_text else value
                new_value = (new_value + right_text) if right_text else new_value
            if new_value != value:
                self.df.at[row, col] = new_value
                changed += 1
        if changed:
            self.is_modified = True
            self.schedule_save_csv()
            self.image_manage_entries = []
            self.refresh_image_manage_window(save_before=False)
        self.show_message("完了", f"{changed}件を更新しました。")

    def cache_current_product_images(self):
        if not self.shop_url:
            self.show_message("警告", "店舗URLが設定されていません。")
            return
        self.save_image_manage_entries()
        urls = []
        for item in self.get_current_image_items():
            path_value = self.df.iloc[item["row"]].get(item["path_col"], "") if item["path_col"] in self.df.columns else ""
            url = self.build_rakuten_image_url(path_value)
            if url:
                urls.append((url, item["title"]))
        if not urls:
            self.show_message("警告", "キャッシュ対象の画像がありません。")
            return
        failed = 0
        total = len(urls)
        if self.image_cache_progress_var:
            self.image_cache_progress_var.set(0)
        if self.image_cache_progress_label:
            self.image_cache_progress_label.config(text=f"0/{total}")
        self.root.update_idletasks()
        for index, (url, title) in enumerate(urls, 1):
            if not self.cache_single_image(url, title, refresh=False):
                failed += 1
            if self.image_cache_progress_var:
                self.image_cache_progress_var.set((index / total) * 100)
            if self.image_cache_progress_label:
                self.image_cache_progress_label.config(text=f"{index}/{total}")
            self.root.update_idletasks()
        self.refresh_image_manage_window()
        self.show_message("完了", f"この商品の画像キャッシュが完了しました。失敗: {failed}件")

    def close_image_manage_window(self):
        if self.image_manage_window:
            self.save_image_manage_entries()
            self.unbind_subwindow_mousewheel(self.image_manage_window)
            self.image_manage_window.destroy()
            self.image_manage_window = None
            self.image_manage_canvas = None
            self.image_manage_scrollable_frame = None
            self.image_manage_entries = []
            self.image_manage_photos = []
            self.image_bulk_url_var = None
            self.image_bulk_alt_var = None
            self.image_bulk_scope_var = None
            self.image_bulk_item_vars = {}
            self.image_cache_progress_var = None
            self.image_cache_progress_label = None
            self.image_find_text = None
            self.image_replace_text = None

    def get_sku_columns(self):
        return [col for col in self.column_list if self.is_sku_column(col)]

    def update_sku_main_column_values(self):
        if not self.sku_main_menu_button:
            return
        sku_columns = self.get_sku_columns()
        previous_checked = {
            col for col, var in self.sku_main_column_check_vars.items()
            if var.get()
        }
        self.sku_main_column_check_vars = {}
        if self.sku_main_menu is None:
            self.sku_main_menu = tk.Menu(self.root, tearoff=False)
        self.sku_main_menu.delete(0, tk.END)
        if not sku_columns:
            self.sku_main_menu_button.config(text="SKU列: なし", state=tk.DISABLED)
            self.close_sku_main_popup()
            return
        if not previous_checked:
            default_col = SKU_ID_COLUMN if SKU_ID_COLUMN in sku_columns else sku_columns[0]
            previous_checked = {default_col}
        for col in sku_columns:
            var = tk.BooleanVar(value=col in previous_checked)
            self.sku_main_column_check_vars[col] = var
        self.sku_main_menu_button.config(state=tk.NORMAL)
        self.update_sku_main_menu_label()

    def toggle_sku_main_popup(self):
        if self.sku_main_popup and self.sku_main_popup.winfo_exists():
            self.close_sku_main_popup()
        else:
            self.open_sku_main_popup()

    def open_sku_main_popup(self):
        if not self.sku_main_menu_button or not self.sku_main_column_check_vars:
            return
        self.close_sku_main_popup()
        x = self.sku_main_menu_button.winfo_rootx()
        y = self.sku_main_menu_button.winfo_rooty() + self.sku_main_menu_button.winfo_height()
        self.sku_main_popup = tk.Toplevel(self.root)
        self.sku_main_popup.title("SKU列選択")
        self.sku_main_popup.geometry(f"420x360+{x}+{y}")
        self.sku_main_popup.transient(self.root)
        self.sku_main_popup.resizable(True, True)
        self.sku_main_popup.protocol("WM_DELETE_WINDOW", self.close_sku_main_popup)
        self.sku_main_popup.lift()
        self.sku_main_popup.attributes("-topmost", True)
        self.sku_main_popup.after(100, lambda: self.sku_main_popup.attributes("-topmost", False) if self.sku_main_popup and self.sku_main_popup.winfo_exists() else None)

        container = tk.Frame(self.sku_main_popup, borderwidth=1, relief="solid")
        container.pack(fill=tk.BOTH, expand=True)
        list_frame = tk.Frame(container)
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.sku_main_popup_canvas = tk.Canvas(list_frame, highlightthickness=0, bg="#f3f4f6")
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.sku_main_popup_canvas.yview)
        self.sku_main_popup_frame = tk.Frame(self.sku_main_popup_canvas, bg="#f3f4f6")
        self.sku_main_popup_frame.bind(
            "<Configure>",
            lambda event: self.sku_main_popup_canvas.configure(scrollregion=self.sku_main_popup_canvas.bbox("all"))
        )
        self.sku_main_popup_canvas.create_window((0, 0), window=self.sku_main_popup_frame, anchor="nw")
        self.sku_main_popup_canvas.configure(yscrollcommand=scrollbar.set)
        self.sku_main_popup_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        button_frame = tk.Frame(container)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(button_frame, text="確定", command=self.confirm_sku_main_popup, font=("Meiryo", 9)).pack(padx=6, pady=5)
        self.populate_sku_main_popup()
        self.sku_main_popup.bind("<Escape>", lambda event: self.close_sku_main_popup())
        self.sku_main_popup.bind("<MouseWheel>", self.on_sku_main_popup_mousewheel)
        self.sku_main_popup_canvas.bind("<MouseWheel>", self.on_sku_main_popup_mousewheel)
        self.sku_main_popup_frame.bind("<MouseWheel>", self.on_sku_main_popup_mousewheel)
        self.root.after(1, self.bind_sku_main_popup_close_click)

    def bind_sku_main_popup_close_click(self):
        if not self.sku_main_popup or not self.sku_main_popup.winfo_exists():
            return
        self.sku_main_popup_click_bind_id = self.root.bind(
            "<Button-1>",
            self.on_sku_main_popup_root_click,
            add="+"
        )

    def populate_sku_main_popup(self):
        if not getattr(self, "sku_main_popup_frame", None):
            return
        for widget in self.sku_main_popup_frame.winfo_children():
            widget.destroy()
        self.sku_main_popup_row_widgets = {}
        for col, var in self.sku_main_column_check_vars.items():
            row = tk.Frame(self.sku_main_popup_frame, borderwidth=0)
            row.pack(fill=tk.X, padx=3, pady=1)
            cb = tk.Checkbutton(
                row,
                variable=var,
                command=lambda c=col: self.on_sku_main_popup_column_toggle(c),
                font=("Meiryo", 9),
                takefocus=False
            )
            cb.pack(side=tk.LEFT, padx=(6, 2))
            label = tk.Label(row, text=col, anchor="w", font=("Meiryo", 9))
            label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), pady=3)
            self.sku_main_popup_row_widgets[col] = (row, cb, label)
            for widget in (row, cb, label):
                widget.bind("<MouseWheel>", self.on_sku_main_popup_mousewheel)
                widget.bind("<Enter>", lambda event, c=col: self.set_sku_main_popup_row_style(c, hover=True))
                widget.bind("<Leave>", lambda event, c=col: self.set_sku_main_popup_row_style(c, hover=False))
            row.bind("<Button-1>", lambda event, c=col: self.toggle_sku_main_popup_column(c))
            label.bind("<Button-1>", lambda event, c=col: self.toggle_sku_main_popup_column(c))
            self.set_sku_main_popup_row_style(col)

    def toggle_sku_main_popup_column(self, col):
        var = self.sku_main_column_check_vars.get(col)
        if not var:
            return
        var.set(not var.get())
        self.on_sku_main_popup_column_toggle(col)

    def on_sku_main_popup_column_toggle(self, col):
        self.on_sku_main_column_check()
        self.set_sku_main_popup_row_style(col)

    def set_sku_main_popup_row_style(self, col, hover=False):
        widgets = self.sku_main_popup_row_widgets.get(col)
        var = self.sku_main_column_check_vars.get(col)
        if not widgets or not var:
            return
        row, cb, label = widgets
        if hover:
            bg = "#dbeafe"
        elif var.get():
            bg = "white"
        else:
            bg = "#f3f4f6"
        row.config(bg=bg)
        cb.config(bg=bg, activebackground="#dbeafe", selectcolor="white")
        label.config(bg=bg)

    def on_sku_main_popup_mousewheel(self, event):
        if not self.sku_main_popup or not self.sku_main_popup.winfo_exists() or not self.sku_main_popup_canvas:
            return
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        popup_x = self.sku_main_popup.winfo_rootx()
        popup_y = self.sku_main_popup.winfo_rooty()
        popup_w = self.sku_main_popup.winfo_width()
        popup_h = self.sku_main_popup.winfo_height()
        if popup_x <= x <= popup_x + popup_w and popup_y <= y <= popup_y + popup_h:
            self.sku_main_popup_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_sku_main_popup_root_click(self, event):
        if not self.sku_main_popup or not self.sku_main_popup.winfo_exists():
            return
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        popup_x = self.sku_main_popup.winfo_rootx()
        popup_y = self.sku_main_popup.winfo_rooty()
        popup_w = self.sku_main_popup.winfo_width()
        popup_h = self.sku_main_popup.winfo_height()
        button_x = self.sku_main_menu_button.winfo_rootx()
        button_y = self.sku_main_menu_button.winfo_rooty()
        button_w = self.sku_main_menu_button.winfo_width()
        button_h = self.sku_main_menu_button.winfo_height()
        in_popup = popup_x <= x <= popup_x + popup_w and popup_y <= y <= popup_y + popup_h
        in_button = button_x <= x <= button_x + button_w and button_y <= y <= button_y + button_h
        if in_popup or in_button:
            return
        self.close_sku_main_popup()

    def close_sku_main_popup(self):
        if self.sku_main_popup_click_bind_id:
            self.root.unbind("<Button-1>", self.sku_main_popup_click_bind_id)
            self.sku_main_popup_click_bind_id = None
        if self.sku_main_popup and self.sku_main_popup.winfo_exists():
            self.sku_main_popup.destroy()
        self.sku_main_popup = None
        self.sku_main_popup_canvas = None
        self.sku_main_popup_frame = None

    def confirm_sku_main_popup(self):
        self.close_sku_main_popup()
        self.open_sku_grid_from_main()

    def update_sku_main_menu_label(self):
        if not self.sku_main_menu_button:
            return
        selected = self.get_checked_sku_main_columns()
        if not selected:
            self.sku_main_menu_button.config(text="SKU列: 未選択")
        elif len(selected) == 1:
            self.sku_main_menu_button.config(text=f"SKU列: {selected[0]}")
        else:
            self.sku_main_menu_button.config(text=f"SKU列: {len(selected)}項目")

    def get_checked_sku_main_columns(self):
        return [
            col for col, var in self.sku_main_column_check_vars.items()
            if var.get()
        ]

    def on_sku_main_column_check(self, keep_menu_open=False):
        selected = self.get_checked_sku_main_columns()
        self.sku_display_columns = selected
        if selected:
            self.current_sku_column = selected[0]
        self.update_sku_main_menu_label()
        if self.sku_grid_window and self.sku_grid_window.winfo_exists():
            self.show_sku_grid()
        if self.sku_main_popup and self.sku_main_popup.winfo_exists():
            for col in self.sku_main_popup_row_widgets:
                self.set_sku_main_popup_row_style(col)

    def open_sku_grid_from_main(self):
        if self.df is None:
            self.show_message("警告", "CSVを読み込んでください。")
            return
        columns = self.get_checked_sku_main_columns()
        if not columns:
            sku_columns = self.get_sku_columns()
            if not sku_columns:
                self.show_message("警告", "SKU関連カラムが見つかりません。")
                return
            self.show_message("警告", "SKU列メニューで表示するカラムを選択してください。")
            return
        self.sku_display_columns = columns
        self.current_sku_column = columns[0]
        self.update_sku_main_menu_label()
        self.show_sku_grid()

    def open_sku_column_selector(self):
        if self.df is None:
            self.show_message("警告", "CSVを読み込んでください。")
            return
        sku_columns = self.get_sku_columns()
        if not sku_columns:
            self.show_message("警告", "SKU関連カラムが見つかりません。")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("SKU編集カラム選択")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog_width = 360
        dialog_height = 130
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        tk.Label(dialog, text="編集するSKUカラム", font=("Meiryo", 9)).pack(padx=10, pady=(12, 4), anchor="w")
        column_var = tk.StringVar(value=SKU_ID_COLUMN if SKU_ID_COLUMN in sku_columns else sku_columns[0])
        ttk.Combobox(dialog, textvariable=column_var, values=sku_columns, state="readonly", width=42, font=("Meiryo", 9)).pack(padx=10, fill=tk.X)

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="開く", command=lambda: [dialog.destroy(), self.show_sku_grid(column_var.get())], font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="閉じる", command=dialog.destroy, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)

    def show_sku_grid(self, column=None):
        if self.df is None or self.current_product_idx >= len(self.product_groups):
            return
        if column:
            self.current_sku_column = column
            if column not in self.sku_display_columns:
                self.sku_display_columns.append(column)
        elif not self.sku_display_columns:
            self.sku_display_columns = self.get_checked_sku_main_columns()
            if not self.sku_display_columns:
                if self.sku_grid_window is None or not self.sku_grid_window.winfo_exists():
                    return
        if not self.current_sku_column and self.sku_display_columns:
            self.current_sku_column = self.sku_display_columns[0]
        if self.sku_grid_window is None or not self.sku_grid_window.winfo_exists():
            self.sku_grid_window = tk.Toplevel(self.root)
            self.sku_grid_window.geometry("800x600")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 400
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 300
            self.sku_grid_window.geometry(f"+{x}+{y}")
            self.sku_grid_window.transient(self.root)
            self.sku_grid_window.resizable(True, True)
            self.sku_grid_window.protocol("WM_DELETE_WINDOW", self.close_sku_grid)
            self.sku_column_var = None
            self.create_sku_edit_bar(self.sku_grid_window)
            self.sku_column_selector_frame = None
            sku_body_frame = tk.Frame(self.sku_grid_window)
            sku_body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.sku_canvas = tk.Canvas(sku_body_frame)
            v_scrollbar = tk.Scrollbar(sku_body_frame, orient="vertical", command=self.sku_canvas.yview)
            h_scrollbar = tk.Scrollbar(sku_body_frame, orient="horizontal", command=self.sku_canvas.xview)
            self.sku_scrollable_frame = tk.Frame(self.sku_canvas)
            self.sku_scrollable_frame.bind("<Configure>", lambda e: self.sku_canvas.configure(scrollregion=self.sku_canvas.bbox("all")))
            self.sku_canvas.create_window((0, 0), window=self.sku_scrollable_frame, anchor="nw")
            self.sku_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            self.sku_canvas.grid(row=0, column=0, sticky="nsew")
            v_scrollbar.grid(row=0, column=1, sticky="ns")
            h_scrollbar.grid(row=1, column=0, sticky="ew")
            sku_body_frame.grid_rowconfigure(0, weight=1)
            sku_body_frame.grid_columnconfigure(0, weight=1)
            self.bind_subwindow_mousewheel(self.sku_grid_window, self.sku_canvas)
            tk.Button(self.sku_grid_window, text="閉じる", command=self.close_sku_grid, font=("Meiryo", 9)).pack(pady=5)
        else:
            pass
        self.sku_grid_window.title(f"SKU編集: {len(self.sku_display_columns)}項目")
        self.refresh_sku_column_selector()
        self.refresh_sku_table()

    def refresh_sku_column_selector(self):
        if not self.sku_column_selector_frame:
            return
        for widget in self.sku_column_selector_frame.winfo_children():
            widget.destroy()
        sku_columns = self.get_sku_columns()
        self.sku_column_check_vars = {}
        for i, col in enumerate(sku_columns):
            main_var = self.sku_main_column_check_vars.get(col)
            var = tk.BooleanVar(value=col in self.sku_display_columns or (main_var.get() if main_var else False))
            self.sku_column_check_vars[col] = var
            cb = tk.Checkbutton(
                self.sku_column_selector_frame,
                text=col,
                variable=var,
                command=self.on_sku_column_check,
                font=("Meiryo", 8)
            )
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=4, pady=1)

    def on_sku_column_check(self):
        self.save_sku_entries()
        self.sku_display_columns = [
            col for col, var in self.sku_column_check_vars.items()
            if var.get()
        ]
        if not self.sku_display_columns and self.current_sku_column:
            self.sku_display_columns = [self.current_sku_column]
            if self.current_sku_column in self.sku_column_check_vars:
                self.sku_column_check_vars[self.current_sku_column].set(True)
        for col, main_var in self.sku_main_column_check_vars.items():
            main_var.set(col in self.sku_display_columns)
        self.update_sku_main_menu_label()
        self.refresh_sku_table()

    def refresh_sku_table(self):
        if not self.sku_scrollable_frame:
            return
        for widget in self.sku_scrollable_frame.winfo_children():
            widget.destroy()
        group = self.product_groups[self.current_product_idx]
        sku_rows = [row for row in group if self.is_sku_row(row)]
        if not self.sku_display_columns:
            tk.Label(
                self.sku_scrollable_frame,
                text="SKU列メニューで表示するカラムを選択してください。",
                font=("Meiryo", 10),
                padx=12,
                pady=12
            ).grid(row=0, column=0, sticky="w")
            self.sku_entries = []
            return
        tk.Label(self.sku_scrollable_frame, text="SKU行", font=("Meiryo", 9), borderwidth=1, relief="solid", width=10).grid(row=0, column=0, sticky="nsew")
        for j, header in enumerate(self.sku_display_columns):
            header_frame = tk.Frame(self.sku_scrollable_frame, borderwidth=1, relief="solid")
            header_frame.grid(row=0, column=j + 1, sticky="nsew")
            var = self.sku_bulk_column_check_vars.get(header)
            if var is None:
                var = tk.BooleanVar(value=False)
                self.sku_bulk_column_check_vars[header] = var
            tk.Checkbutton(
                header_frame,
                variable=var,
                font=("Meiryo", 8)
            ).pack(side=tk.LEFT)
            tk.Label(header_frame, text=header, font=("Meiryo", 9), width=24, anchor="w").pack(side=tk.LEFT)
        self.sku_entries = []
        for i, row in enumerate(sku_rows):
            grid_row = i + 1
            tk.Label(self.sku_scrollable_frame, text=f"SKU {i+1}", font=("Meiryo", 9), borderwidth=1, relief="solid", width=10).grid(row=grid_row, column=0, sticky="nsew")
            for j, col in enumerate(self.sku_display_columns):
                entry = tk.Entry(self.sku_scrollable_frame, font=("Meiryo", 9), width=24)
                entry.grid(row=grid_row, column=j + 1, sticky="nsew")
                value = str(self.df.iloc[row][col]) if pd.notna(self.df.iloc[row][col]) else ""
                entry.insert(0, value)
                entry.bind("<FocusOut>", lambda event, r=row, c=col: self.update_sku_entry(r, c))
                self.sku_entries.append((row, col, entry))
        for j in range(len(self.sku_display_columns) + 1):
            self.sku_scrollable_frame.grid_columnconfigure(j, weight=1)

    def update_sku_entry(self, row, column):
        if self.df is None or not self.sku_entries:
            return
        for r, c, entry in self.sku_entries:
            if r == row and c == column:
                value = entry.get().strip()
                self.df.at[row, column] = value
                self.is_modified = True
                self.schedule_save_csv()
                break

    def save_sku_entries(self):
        if self.df is None or not self.sku_entries:
            return
        for row, column, entry in self.sku_entries:
            value = entry.get().strip()
            current_value = str(self.df.iloc[row][column]) if pd.notna(self.df.iloc[row][column]) else ""
            if value != current_value:
                self.df.at[row, column] = value
                self.is_modified = True
        if self.is_modified:
            self.schedule_save_csv()

    def close_sku_grid(self):
        if self.sku_grid_window:
            self.unbind_subwindow_mousewheel(self.sku_grid_window)
            self.sku_grid_window.destroy()
            self.sku_grid_window = None
            self.sku_canvas = None
            self.sku_scrollable_frame = None
            self.sku_entries = []
            self.current_sku_column = None
            self.sku_column_var = None
            self.sku_find_text = None
            self.sku_replace_text = None
            self.sku_column_selector_frame = None
            self.sku_column_check_vars = {}

    def invert_selection(self):
        if self.df is None:
            return
        for i, rows in enumerate(self.product_groups):
            if any(self.selected_rows[row] for row in rows):
                for row in rows:
                    self.selected_rows[row] = False
            else:
                for row in rows:
                    self.selected_rows[row] = True
        self.row_check_var.set(any(self.selected_rows[row] for row in self.product_groups[self.current_product_idx]))
        self.reset_selection_count()
        self.update_selected_count()
        self.save_selected_rows()
        self.update_display()

    def setup_gui(self):
        style = ttk.Style()
        style.configure("TLabelFrame", borderwidth=2, relief="groove")
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        frame_csv = ttk.LabelFrame(main_frame, text="読込", padding=5)
        frame_csv.pack(fill=tk.X, pady=5)
        frame_csv.grid_columnconfigure(0, weight=1)
        frame_csv.grid_columnconfigure(1, weight=1)

        csv_cell = tk.Frame(frame_csv)
        csv_cell.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=2)
        csv_cell.grid_columnconfigure(1, weight=1)
        tk.Label(csv_cell, text="CSV選択", font=("Meiryo", 9), width=10, anchor="w").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar()
        tk.Entry(csv_cell, textvariable=self.path_var, width=34, font=("Meiryo", 9)).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(csv_cell, text="参照", command=self.load_csv, font=("Meiryo", 9)).grid(row=0, column=2)
        tk.Button(csv_cell, text="設定", command=self.open_settings, font=("Meiryo", 9)).grid(row=0, column=3, padx=(5, 0))

        settings_cell = tk.Frame(frame_csv)
        settings_cell.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=2)
        settings_cell.grid_columnconfigure(1, weight=1)
        tk.Label(settings_cell, text="設定選択", font=("Meiryo", 9), width=10, anchor="w").grid(row=0, column=0, sticky="w")
        self.column_settings_path_var = tk.StringVar()
        tk.Entry(settings_cell, textvariable=self.column_settings_path_var, width=34, font=("Meiryo", 9)).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(settings_cell, text="参照", command=self.load_column_settings, font=("Meiryo", 9)).grid(row=0, column=2)
        tk.Button(settings_cell, text="保存", command=self.save_column_settings, font=("Meiryo", 9)).grid(row=0, column=3, padx=(5, 0))

        item_cat_cell = tk.Frame(frame_csv)
        item_cat_cell.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=2)
        item_cat_cell.grid_columnconfigure(1, weight=1)
        tk.Label(item_cat_cell, text="カテゴリCSV", font=("Meiryo", 9), width=10, anchor="w").grid(row=0, column=0, sticky="w")
        self.item_cat_path_var = tk.StringVar(value=self.item_cat_file_path)
        tk.Entry(item_cat_cell, textvariable=self.item_cat_path_var, width=34, font=("Meiryo", 9)).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(item_cat_cell, text="追加読込", command=self.load_item_cat_csv, font=("Meiryo", 9)).grid(row=0, column=2)
        tk.Frame(frame_csv).grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=2)
        edit_frame = ttk.LabelFrame(main_frame, text="編集", padding=5)
        edit_frame.pack(fill=tk.X, pady=5)
        frame_num_cols = tk.Frame(edit_frame)
        frame_num_cols.pack(fill=tk.X, pady=2)
        tk.Label(frame_num_cols, text="カラム", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.num_cols_var = tk.StringVar(value=str(self.num_columns))
        num_cols_entry = tk.Entry(frame_num_cols, textvariable=self.num_cols_var, width=5, font=("Meiryo", 9))
        num_cols_entry.pack(side=tk.LEFT, padx=5)
        num_cols_entry.bind("<MouseWheel>", self.on_num_cols_wheel)
        tk.Button(frame_num_cols, text="適用", command=self.update_column_frames, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Label(frame_num_cols, text="行数", font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.entry_rows_var = tk.StringVar(value=str(max(self.entry_rows_per_column) if self.entry_rows_per_column else 2))
        entry_rows_entry = tk.Entry(frame_num_cols, textvariable=self.entry_rows_var, width=5, font=("Meiryo", 9))
        entry_rows_entry.pack(side=tk.LEFT, padx=5)
        entry_rows_entry.bind("<MouseWheel>", self.on_entry_rows_wheel)
        tk.Button(frame_num_cols, text="適用", command=self.apply_entry_rows, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Label(frame_num_cols, text="移動", font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar(value=self.search_text)
        tk.Entry(frame_num_cols, textvariable=self.search_var, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        next_btn = tk.Button(frame_num_cols, text="Next", command=self.next_product, font=("Meiryo", 9), width=5, height=1)
        next_btn.pack(side=tk.LEFT, padx=2)
        next_btn.bind("<Shift-Button-1>", lambda e: self.next_product(shift_pressed=True))
        self.next_button = next_btn
        prev_btn = tk.Button(frame_num_cols, text="Prev", command=self.prev_product, font=("Meiryo", 9), width=5, height=1)
        prev_btn.pack(side=tk.LEFT, padx=2)
        prev_btn.bind("<Shift-Button-1>", lambda e: self.prev_product(shift_pressed=True))
        self.prev_button = prev_btn
        self.search_result_var = tk.StringVar(value="検索結果: 0")
        tk.Label(frame_num_cols, textvariable=self.search_result_var, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.select_button = tk.Button(frame_num_cols, text="追加" if self.append_selection else "選択", command=self.select_matching_products, font=("Meiryo", 9))
        self.select_button.pack(side=tk.LEFT, padx=5)
        tk.Button(frame_num_cols, text="クリア", command=self.clear_search, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_num_cols, text="先頭", command=self.go_to_first_product, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        frame_replace = tk.Frame(edit_frame)
        frame_replace.pack(fill=tk.X, pady=2)
        tk.Label(frame_replace, text="選択", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.row_check_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_replace, variable=self.row_check_var, command=self.toggle_product_check, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Button(frame_replace, text="全選択", command=self.select_all_products, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="全解除", command=self.clear_products, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.find_text = Text(frame_replace, height=2, width=20, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.find_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(frame_replace, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.replace_text = Text(frame_replace, height=2, width=20, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.replace_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame_replace, text="置換", command=self.perform_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="追加", command=self.append_text, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="クリア", command=self.clear_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="末尾", command=self.go_to_last_product, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        window_frame = ttk.LabelFrame(main_frame, text="ウィンドウ", padding=5)
        window_frame.pack(fill=tk.X, pady=5)
        self.option_button = tk.Button(window_frame, text="オプション編集", command=self.toggle_option_window, font=("Meiryo", 9))
        self.option_button.pack(side=tk.LEFT, padx=5)
        self.update_option_button_state()
        self.category_button = tk.Button(window_frame, text="カテゴリ編集", command=self.show_category_grid, font=("Meiryo", 9))
        self.category_button.pack(side=tk.LEFT, padx=5)
        tk.Button(window_frame, text="画像", command=self.show_image_manage_window, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(window_frame, text="SKU編集", command=self.open_sku_grid_from_main, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.sku_main_menu_button = tk.Button(window_frame, text="SKU列: 未読込", command=self.toggle_sku_main_popup, relief=tk.RAISED, font=("Meiryo", 9), width=24)
        self.sku_main_menu_button.pack(side=tk.LEFT, padx=5)
        self.sku_main_menu = tk.Menu(self.root, tearoff=False)
        display_frame = ttk.LabelFrame(main_frame, text="表示", padding=5)
        display_frame.pack(fill=tk.X, pady=5)
        self.image_frame = tk.Frame(display_frame)
        self.image_frame.pack(fill=tk.X)
        tk.Label(self.image_frame, text="サムネ画像", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.image_canvas = tk.Canvas(
            self.image_frame,
            width=200,
            height=200,
            bg="white",
            highlightthickness=2,
            highlightcolor="#eeeeee",
            cursor="arrow"
        )
        self.image_canvas.pack(side=tk.LEFT, padx=5)
        self.image_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.image_canvas.bind("<Button-1>", self.toggle_product_check)
        self.image_canvas.bind("<Enter>", self.on_image_canvas_enter)
        self.image_canvas.bind("<Leave>", self.on_image_canvas_leave)
        self.image_canvas.bind("<Left>", self.on_image_arrow_key)
        self.image_canvas.bind("<Right>", self.on_image_arrow_key)
        self.image_canvas.bind("<Shift-Left>", self.on_image_arrow_key)
        self.image_canvas.bind("<Shift-Right>", self.on_image_arrow_key)
        self.selected_count_var = tk.StringVar(value="選択中 00000/00000")
        tk.Label(self.image_frame, textvariable=self.selected_count_var, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=10)
        tk.Button(self.image_frame, text="選択反転", command=self.invert_selection, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.char_count_var = tk.StringVar(value="文字数 半角 00000")
        tk.Label(self.image_frame, textvariable=self.char_count_var, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=10)
        tk.Button(self.image_frame, text="選択値コピー", command=self.copy_code_to_clipboard, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=10)
        self.navigation_mode_button = tk.Button(self.image_frame, command=self.toggle_navigation_mode, font=("Meiryo", 9))
        self.navigation_mode_button.pack(side=tk.LEFT, padx=5)
        self.update_navigation_mode_button()
        self.product_info_frame = tk.Frame(display_frame)
        self.product_info_frame.pack(fill=tk.X, pady=(4, 0))
        self.product_structure_var = tk.StringVar(value="商品構成: 未読込")
        tk.Label(
            self.product_info_frame,
            textvariable=self.product_structure_var,
            font=("Meiryo", 9),
            anchor="w",
            width=120
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.column_frame_container = tk.Frame(main_frame)
        self.column_frame_container.pack(fill=tk.X)
        self.column_frames = []
        self.column_combos = []
        self.entries = []
        self.check_vars = []
        self.create_column_frames(self.num_columns)
        self.update_display()
        self.root.bind(f"<{self.select_shortcut_key}>", self.toggle_product_check_shortcut)
        self.root.bind("<Control-Up>", self.prev_product)
        self.root.bind("<Control-Down>", self.next_product)

    def toggle_product_check_shortcut(self, event=None):
        if self.df is not None and self.current_product_idx < len(self.product_groups):
            self.row_check_var.set(not self.row_check_var.get())
            self.toggle_product_check()
        return "break"

    def update_shortcut_binding(self, prev_shortcut):
        self.root.unbind(f"<{prev_shortcut}>")
        self.root.bind(f"<{self.select_shortcut_key}>", self.toggle_product_check_shortcut)

    def toggle_navigation_mode(self):
        self.navigate_selected_only = not self.navigate_selected_only
        self.update_navigation_mode_button()
        self.save_settings()

    def update_navigation_mode_button(self):
        if hasattr(self, "navigation_mode_button") and self.navigation_mode_button:
            if self.navigate_selected_only:
                self.navigation_mode_button.config(text="選択のみ", relief=tk.SUNKEN)
            else:
                self.navigation_mode_button.config(text="全商品", relief=tk.RAISED)

    def get_navigation_target_products(self, selected_only=False):
        if self.df is None:
            return []
        if selected_only or self.navigate_selected_only:
            return [
                idx for idx, rows in enumerate(self.product_groups)
                if any(self.selected_rows[row] for row in rows)
            ]
        return list(range(len(self.product_groups)))

    def is_pointer_over_image_canvas(self):
        widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        return widget == self.image_canvas

    def on_image_canvas_enter(self, event=None):
        current_focus = self.root.focus_get()
        if current_focus != self.image_canvas:
            self.focus_before_image_hover = current_focus
        self.image_canvas.config(cursor="hand2")
        self.image_canvas.focus_set()

    def on_image_canvas_leave(self, event=None):
        self.image_canvas.config(cursor="arrow")
        if self.root.focus_get() == self.image_canvas:
            previous_focus = self.focus_before_image_hover
            if previous_focus and previous_focus.winfo_exists():
                previous_focus.focus_set()
        self.focus_before_image_hover = None

    def on_image_arrow_key(self, event):
        if not self.is_pointer_over_image_canvas():
            return None
        shift_pressed = (event.state & 0x1) != 0
        if event.keysym == "Left":
            self.prev_product(shift_pressed=shift_pressed)
        elif event.keysym == "Right":
            self.next_product(shift_pressed=shift_pressed)
        return "break"

    def on_num_cols_wheel(self, event):
        widget = event.widget
        if widget == self.root.winfo_containing(event.x_root, event.y_root):
            try:
                current = int(self.num_cols_var.get())
                if event.delta > 0:
                    self.num_cols_var.set(str(current + 1))
                elif event.delta < 0 and current > 1:
                    self.num_cols_var.set(str(current - 1))
                self.update_column_frames()
            except ValueError:
                pass
        return "break"

    def on_entry_rows_wheel(self, event):
        widget = event.widget
        if widget == self.root.winfo_containing(event.x_root, event.y_root):
            try:
                current = int(self.entry_rows_var.get())
                if event.delta > 0:
                    self.entry_rows_var.set(str(current + 1))
                elif event.delta < 0 and current > 1:
                    self.entry_rows_var.set(str(current - 1))
                self.apply_entry_rows()
            except ValueError:
                pass
        return "break"

    def on_mouse_wheel(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget == self.image_canvas:
            shift_pressed = (event.state & 0x1) != 0
            if event.delta > 0:
                self.prev_product(shift_pressed=shift_pressed)
            elif event.delta < 0:
                self.next_product(shift_pressed=shift_pressed)
            return "break"
        return "break"

    def show_column_info(self, index):
        column = self.selected_columns[index] if index < len(self.selected_columns) else None
        if self.info_window is None:
            self.info_window = tk.Toplevel(self.root)
            self.info_window.title(f"カラム仕様: {column or '未選択'}")
            self.info_window.geometry("400x300")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 200
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 150
            self.info_window.geometry(f"+{x}+{y}")
            self.info_window.transient(self.root)
            self.info_window.resizable(True, True)
            self.info_window.protocol("WM_DELETE_WINDOW", self.close_info_window)
            self.info_text = tk.Text(self.info_window, wrap=tk.WORD, height=15, width=50, font=("Meiryo", 9))
            self.info_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            self.info_text.config(state='normal')
            tk.Button(self.info_window, text="閉じる", command=self.close_info_window, font=("Meiryo", 9)).pack(pady=5)
        else:
            self.info_window.title(f"カラム仕様: {column or '未選択'}")
            self.info_text.config(state='normal')
            self.info_text.delete("1.0", tk.END)
        if not column:
            self.info_text.insert(tk.END, "")
        else:
            if self.spec_df is not None and not self.spec_df.empty and column in self.spec_df['item_name'].values:
                spec = self.spec_df[self.spec_df['item_name'] == column].iloc[0]
                info = (
                    f"項目名: {spec['item_name'] or ''}\n"
                    f"管理画面項目名: {spec['mall_name'] or ''}\n"
                    f"形式: {spec['format'] or ''}\n"
                    f"説明: {spec['description'] or ''}\n"
                )
                self.info_text.insert(tk.END, info)
            else:
                self.info_text.insert(tk.END, "")
        self.info_text.config(state='disabled')

    def close_info_window(self):
        if self.info_window:
            self.info_window.destroy()
            self.info_window = None

    def on_closing(self):
        self.save_all_entries()
        self.save_category_entries()
        self.save_image_manage_entries()
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
            self.save_timer = None
        if self.item_cat_save_timer:
            self.root.after_cancel(self.item_cat_save_timer)
            self.item_cat_save_timer = None
        if self.df is not None and not self.file_path:
            if self.show_confirm("警告", "CSVファイルが指定されていません。保存しますか？"):
                self.file_path = filedialog.asksaveasfilename(filetypes=[("CSV files", "*.csv")], defaultextension=".csv")
        self.save_csv()
        self.save_item_cat_csv()
        self.save_image_cache_map()
        self.save_settings()
        self.save_selected_rows()
        if self.info_window:
            self.info_window.destroy()
        if self.settings_window:
            self.settings_window.destroy()
        if self.option_grid_window:
            self.option_grid_window.destroy()
        if self.category_grid_window:
            self.category_grid_window.destroy()
        if self.image_manage_window:
            self.image_manage_window.destroy()
        if self.sku_grid_window:
            self.save_sku_entries()
            self.sku_grid_window.destroy()
        self.root.destroy()

    def toggle_product_check(self, event=None):
        if self.df is not None and self.current_product_idx < len(self.product_groups):
            group = self.product_groups[self.current_product_idx]
            was_selected = any(self.selected_rows[row] for row in group)
            new_state = not was_selected
            for row in group:
                self.selected_rows[row] = new_state
            if new_state and not was_selected:
                self.selected_product_count += 1
            elif was_selected and not new_state:
                self.selected_product_count = max(0, self.selected_product_count - 1)
            self.row_check_var.set(new_state)
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()

    def select_all_products(self):
        if self.df is not None:
            for rows in self.product_groups:
                for row in rows:
                    self.selected_rows[row] = True
            self.selected_product_count = len(self.product_groups)
            self.row_check_var.set(True)
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()

    def clear_products(self):
        if self.df is not None:
            self.selected_rows = [False] * len(self.df)
            self.selected_product_count = 0
            self.row_check_var.set(False)
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()

    def select_matching_products(self):
        if self.df is None:
            return
        search_text = self.search_var.get().strip()
        if not search_text:
            self.show_message("警告", "検索文字列を入力してください。")
            self.search_result_var.set("検索結果: 0")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        if not checked_cols:
            self.show_message("警告", "カラムを指定してください。")
            self.search_result_var.set("検索結果: 0")
            return
        if not self.append_selection:
            self.selected_rows = [False] * len(self.df)
            self.selected_product_count = 0
        search_terms = search_text.split()
        match_count = 0
        for idx, rows in enumerate(self.product_groups):
            parent_row = self.get_parent_row(rows)
            match = True
            for col in checked_cols:
                value = str(self.df.iloc[parent_row][col]) if pd.notna(self.df.iloc[parent_row][col]) else ""
                match = match and all(term.lower() in value.lower() for term in search_terms)
                if not match:
                    break
            if match:
                was_selected = any(self.selected_rows[row] for row in rows)
                for row in rows:
                    self.selected_rows[row] = True
                if not was_selected:
                    self.selected_product_count += 1
                match_count += 1
        self.search_result_var.set(f"検索結果: {match_count}")
        self.update_selected_count()
        self.save_selected_rows()
        self.update_display()

    def update_selected_count(self):
        total = len(self.product_groups) if self.product_groups else 0
        self.selected_count_var.set(f"選択中 {self.selected_product_count:05d}/{total:05d}")
        self.update_subwindow_selected_count_labels()

    def clear_search(self):
        self.search_var.set("")
        self.search_result_var.set("検索結果: 0")

    def clear_replace(self):
        self.find_text.delete("1.0", tk.END)
        self.replace_text.delete("1.0", tk.END)

    def apply_entry_rows(self):
        try:
            rows = int(self.entry_rows_var.get())
            if rows < 1:
                raise ValueError("行数は1以上でなければなりません。")
            for i in range(self.num_columns):
                if self.checked_columns[i]:
                    self.entry_rows_per_column[i] = rows
            self.save_all_entries()
            self.create_column_frames(self.num_columns)
            self.save_settings()
        except ValueError as e:
            self.show_message("エラー", f"無効な入力です: {str(e)}", msg_type="error")

    def perform_replace(self):
        if self.df is None:
            return
        find_text = self.find_text.get("1.0", tk.END).rstrip('\n')
        replace_text = self.replace_text.get("1.0", tk.END).rstrip('\n')
        if not find_text.strip():
            self.show_message("警告", "検索文字列を入力してください。")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        checked_groups = {i for i, rows in enumerate(self.product_groups) if any(self.selected_rows[row] for row in rows)}
        if not checked_cols or not checked_groups:
            self.show_message("警告", "置換対象の商品またはカラムを選んでください。")
            return
        has_var_find = "%" in find_text
        has_var_replace = "%" in replace_text
        for idx in checked_groups:
            parent_row = self.get_parent_row(self.product_groups[idx])
            find_value = self.replace_with_column_vars(find_text, parent_row) if has_var_find else find_text
            replace_value = self.replace_with_column_vars(replace_text, parent_row) if has_var_replace else replace_text
            for col in checked_cols:
                value = str(self.df.iloc[parent_row][col]) if pd.notna(self.df.iloc[parent_row][col]) else ""
                new_value = value.replace(find_value, replace_value)
                self.df.at[parent_row, col] = new_value
        self.is_modified = True
        self.schedule_save_csv()
        self.update_display()

    def append_text(self):
        if self.df is None:
            return
        prefix = self.find_text.get("1.0", tk.END).rstrip('\n')
        suffix = self.replace_text.get("1.0", tk.END).rstrip('\n')
        if not prefix.strip() and not suffix.strip():
            self.show_message("警告", "検索文字列を入力してください。")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        checked_groups = {i for i, rows in enumerate(self.product_groups) if any(self.selected_rows[row] for row in rows)}
        if not checked_cols or not checked_groups:
            self.show_message("警告", "追加対象の商品またはカラムを選んでください。")
            return
        has_var_prefix = "%" in prefix
        has_var_suffix = "%" in suffix
        for idx in checked_groups:
            parent_row = self.get_parent_row(self.product_groups[idx])
            prefix_value = self.replace_with_column_vars(prefix, parent_row) if has_var_prefix else prefix
            suffix_value = self.replace_with_column_vars(suffix, parent_row) if has_var_suffix else suffix
            for col in checked_cols:
                value = str(self.df.iloc[parent_row][col]) if pd.notna(self.df.iloc[parent_row][col]) else ""
                new_value = (prefix_value + value) if prefix_value else value
                new_value = (new_value + suffix_value) if suffix_value else new_value
                self.df.at[parent_row, col] = new_value
        self.is_modified = True
        self.schedule_save_csv()
        self.update_display()

    def go_to_first_product(self):
        if self.df is None or not self.product_groups:
            return
        self.save_all_entries()
        if self.show_option_window:
            self.save_option_entries()
        if self.sku_grid_window:
            self.save_sku_entries()
        if self.category_grid_window:
            self.save_category_entries()
        if self.image_manage_window:
            self.save_image_manage_entries()
        self.current_product_idx = 0
        self.update_display()
        self.save_selected_rows()

    def go_to_last_product(self):
        if self.df is None or not self.product_groups:
            return
        self.save_all_entries()
        if self.show_option_window:
            self.save_option_entries()
        if self.sku_grid_window:
            self.save_sku_entries()
        self.current_product_idx = len(self.product_groups) - 1
        self.update_display()
        self.save_selected_rows()

    def save_column_settings(self):
        file_path = filedialog.asksaveasfilename(
            filetypes=[("JSON files", "*.json")],
            defaultextension=".json"
        )
        if not file_path:
            return
        settings = {
            "num_columns": self.num_columns,
            "selected_columns": self.selected_columns,
            "checked_columns": self.checked_columns,
            "entry_rows_per_column": self.entry_rows_per_column,
            "sku_selected_columns": self.get_checked_sku_main_columns(),
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            self.column_settings_path_var.set(file_path)
            self.show_message("成功", "表示カラム設定を保存しました。")
        except Exception as e:
            self.show_message("エラー", f"表示カラム設定の保存に失敗しました: {str(e)}", msg_type="error")

    def load_column_settings(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self.num_columns = max(1, int(settings.get("num_columns", self.num_columns)))
            self.selected_columns = settings.get("selected_columns", self.selected_columns)
            self.checked_columns = settings.get("checked_columns", self.checked_columns)
            self.entry_rows_per_column = settings.get("entry_rows_per_column", self.entry_rows_per_column)
            has_sku_selected_columns = "sku_selected_columns" in settings
            sku_selected_columns = settings.get("sku_selected_columns", [])
            self.selected_columns = self.selected_columns[:self.num_columns] + [None] * max(0, self.num_columns - len(self.selected_columns))
            self.checked_columns = self.checked_columns[:self.num_columns] + [False] * max(0, self.num_columns - len(self.checked_columns))
            self.entry_rows_per_column = self.entry_rows_per_column[:self.num_columns] + [2] * max(0, self.num_columns - len(self.entry_rows_per_column))
            self.num_cols_var.set(str(self.num_columns))
            if self.entry_rows_per_column:
                self.entry_rows_var.set(str(max(self.entry_rows_per_column)))
            self.create_column_frames(self.num_columns)
            if has_sku_selected_columns:
                self.apply_sku_column_settings(sku_selected_columns)
            self.column_settings_path_var.set(file_path)
            self.save_settings()
            self.show_message("成功", "表示カラム設定を読み込みました。")
        except Exception as e:
            self.show_message("エラー", f"表示カラム設定の読み込みに失敗しました: {str(e)}", msg_type="error")

    def apply_sku_column_settings(self, sku_selected_columns):
        if not self.sku_main_column_check_vars:
            self.update_sku_main_column_values()
        selected = [col for col in sku_selected_columns if col in self.sku_main_column_check_vars]
        for col, var in self.sku_main_column_check_vars.items():
            var.set(col in selected)
        self.sku_display_columns = selected
        self.current_sku_column = selected[0] if selected else None
        self.update_sku_main_menu_label()
        if self.sku_grid_window and self.sku_grid_window.winfo_exists():
            self.show_sku_grid()

    def update_combobox_values(self):
        selected_cols = [col for col in self.selected_columns if col is not None]
        available_cols = self.get_parent_columns()
        self.update_sku_main_column_values()
        for i, combo in enumerate(self.column_combos):
            current_selection = self.selected_columns[i]
            combo_available = [col for col in available_cols if col not in selected_cols or col == current_selection]
            combo['values'] = combo_available
            if current_selection in combo_available:
                combo.set(current_selection)
            elif combo_available:
                for col in available_cols:
                    if col not in selected_cols:
                        combo.set(col)
                        self.selected_columns[i] = col
                        selected_cols.append(col)
                        break
                else:
                    combo.set("")
                    self.selected_columns[i] = None
            else:
                combo.set("")
                self.selected_columns[i] = None
            combo['state'] = 'readonly' if combo_available else 'disabled'

    def create_column_frames(self, num_columns):
        for frame in self.column_frames:
            frame.destroy()
        self.column_frames = []
        self.column_combos = []
        self.entries = []
        self.check_vars = []
        self.num_columns = num_columns
        if len(self.selected_columns) < num_columns:
            used_cols = [col for col in self.selected_columns if col is not None]
            new_cols = [col for col in self.get_parent_columns() if col not in used_cols][:num_columns - len(self.selected_columns)]
            self.selected_columns.extend([None] * (num_columns - len(self.selected_columns)))
            for i in range(len(self.selected_columns) - len(new_cols), len(self.selected_columns)):
                if new_cols:
                    self.selected_columns[i] = new_cols.pop(0)
        else:
            self.selected_columns = self.selected_columns[:num_columns]
        self.checked_columns = self.checked_columns[:num_columns] + [False] * max(0, num_columns - len(self.checked_columns))
        self.entry_rows_per_column = self.entry_rows_per_column[:num_columns] + [2] * max(0, num_columns - len(self.entry_rows_per_column))
        for i in range(num_columns):
            frame = tk.Frame(self.column_frame_container)
            frame.pack(fill=tk.X, pady=5)
            self.column_frames.append(frame)
            check_var = tk.BooleanVar(value=self.checked_columns[i])
            tk.Checkbutton(frame, variable=check_var, command=lambda idx=i: self.toggle_check(idx), font=("Meiryo", 9)).pack(side=tk.LEFT)
            self.check_vars.append(check_var)
            combo = ttk.Combobox(frame, state="readonly", width=20, font=("Meiryo", 9))
            combo.pack(side=tk.LEFT, padx=5)
            self.column_combos.append(combo)
            combo.bind("<<ComboboxSelected>>", lambda event, idx=i: self.on_column_select(idx))
            tk.Button(frame, text="?", width=2, command=lambda idx=i: self.show_column_info(idx), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(5, 2))
            tk.Button(frame, text="%", width=2, command=lambda idx=i: self.copy_column_variable_to_clipboard(idx), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(0, 5))
            entry = Text(frame, height=self.entry_rows_per_column[i], width=40, font=("Meiryo", 9), borderwidth=1, relief="sunken")
            entry.bind("<FocusOut>", lambda event, idx=i: self.update_csv(idx))
            entry.bind("<FocusIn>", lambda event, idx=i: self.set_focused_entry(idx))
            entry.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
            self.entries.append(entry)
            tk.Button(frame, text="コピー", command=lambda idx=i: self.copy_to_clipboard(idx), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.update_combobox_values()
        self.update_display()

    def set_focused_entry(self, index):
        self.focused_entry_index = index
        self.update_char_count()

    def update_char_count(self):
        if self.df is not None and self.current_product_idx < len(self.product_groups):
            entry = self.entries[self.focused_entry_index]
            text = entry.get("1.0", tk.END).rstrip('\n')
            try:
                byte_count = len(text.encode('shift-jis'))
                self.char_count_var.set(f"文字数 半角 {byte_count:05d}")
            except UnicodeEncodeError:
                self.char_count_var.set("文字数 半角 エラー")

    def toggle_check(self, index):
        self.checked_columns[index] = self.check_vars[index].get()

    def copy_to_clipboard(self, index):
        value = self.entries[index].get("1.0", tk.END).rstrip('\n')
        self.root.clipboard_clear()
        self.root.clipboard_append(value)

    def copy_column_variable_to_clipboard(self, index):
        column = self.selected_columns[index] if index < len(self.selected_columns) else None
        if not column:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(f"%{column}%")

    def update_column_frames(self):
        try:
            num_columns = int(self.num_cols_var.get())
            if num_columns < 1:
                raise ValueError("カラム数は1以上でなければなりません。")
            self.save_all_entries()
            self.create_column_frames(num_columns)
            self.save_settings()
        except ValueError as e:
            self.show_message("エラー", f"無効な入力です: {str(e)}", msg_type="error")

    def detect_encoding(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                return result['encoding']
        except Exception as e:
            logging.error(f"エンコーディング検出に失敗しました: {str(e)}")
            return None

    def load_item_cat_csv(self, file_path=None, auto=False):
        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            source_path = Path(file_path)
            if self.copy_and_edit and not auto:
                copy_file_path = source_path.with_stem(f"fix_{source_path.stem}")
                shutil.copy2(file_path, copy_file_path)
                self.item_cat_file_path = str(copy_file_path)
                self.show_message("情報", f"カテゴリCSVのコピーを作成しました: {self.item_cat_file_path}")
            else:
                self.item_cat_file_path = file_path

            read_errors = []
            encodings = ["cp932", "shift-jis", "utf-8-sig"]
            detected_encoding = self.detect_encoding(self.item_cat_file_path)
            if detected_encoding:
                encodings.append(detected_encoding)
            for encoding in dict.fromkeys(encodings):
                try:
                    self.item_cat_df = pd.read_csv(self.item_cat_file_path, encoding=encoding, dtype=str)
                    self.item_cat_encoding = encoding
                    break
                except Exception as e:
                    read_errors.append(f"{encoding}: {e}")
            else:
                if not auto:
                    self.show_message("エラー", "カテゴリCSVの読み込みに失敗しました:\n" + "\n".join(read_errors[-3:]), msg_type="error")
                return

            missing = [col for col in [PRODUCT_ID_COLUMN, "表示先カテゴリ"] if col not in self.item_cat_df.columns]
            if missing:
                self.item_cat_df = None
                self.item_cat_file_path = ""
                if not auto:
                    self.show_message("警告", "item-cat CSVではない可能性があります。\n不足カラム: " + ", ".join(missing))
                return

            self.build_item_cat_groups()
            self.item_cat_is_modified = False
            if hasattr(self, "item_cat_path_var"):
                self.item_cat_path_var.set(self.item_cat_file_path)
            self.save_settings()
            if self.category_grid_window and self.category_grid_window.winfo_exists():
                self.show_category_grid()
            if not auto:
                self.show_message("成功", f"カテゴリCSVを読み込みました。\n商品数: {len(self.item_cat_groups)}")
        except Exception as e:
            if not auto:
                self.show_message("エラー", f"カテゴリCSVの読み込みに失敗しました: {str(e)}", msg_type="error")

    def build_item_cat_groups(self):
        self.item_cat_groups = {}
        if self.item_cat_df is None or PRODUCT_ID_COLUMN not in self.item_cat_df.columns:
            return
        for row_idx, row in self.item_cat_df.iterrows():
            code = row.get(PRODUCT_ID_COLUMN)
            if self.cell_has_value(code):
                self.item_cat_groups.setdefault(str(code).strip(), []).append(row_idx)

    def get_current_product_code(self):
        if self.df is None or self.current_product_idx >= len(self.product_groups):
            return ""
        group = self.product_groups[self.current_product_idx]
        parent_row = self.get_parent_row(group)
        if PRODUCT_ID_COLUMN not in self.df.columns:
            return ""
        value = self.df.iloc[parent_row].get(PRODUCT_ID_COLUMN)
        return str(value).strip() if self.cell_has_value(value) else ""

    def load_csv(self, file_path=None, auto=False):
        if not file_path:
            file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                if self.copy_and_edit and not auto:
                    file_path_obj = Path(file_path)
                    copy_file_path = file_path_obj.with_stem(f"fix_{file_path_obj.stem}")
                    shutil.copy2(file_path, copy_file_path)
                    self.file_path = str(copy_file_path)
                    self.show_message("情報", f"コピーを作成しました: {self.file_path}")
                else:
                    self.file_path = file_path
                self.path_var.set(self.file_path)
                read_errors = []
                encodings = ["cp932", "shift-jis", "utf-8-sig"]
                detected_encoding = self.detect_encoding(self.file_path)
                if detected_encoding:
                    encodings.append(detected_encoding)
                for encoding in dict.fromkeys(encodings):
                    try:
                        self.df = pd.read_csv(self.file_path, encoding=encoding, dtype=str)
                        self.csv_encoding = encoding
                        break
                    except Exception as e:
                        read_errors.append(f"{encoding}: {e}")
                else:
                    if not auto:
                        self.show_message("エラー", "CSVの読み込みに失敗しました:\n" + "\n".join(read_errors[-3:]), msg_type="error")
                    return
                self.column_list = list(self.df.columns)
                self.csv_kind = self.detect_csv_kind()
                self.product_groups = self.group_products()
                self.build_product_group_info()
                self.selected_columns = [None] * self.num_columns
                available_cols = self.get_parent_columns()
                if auto and self.last_selected_columns:
                    restored = [
                        col if col in self.column_list else None
                        for col in self.last_selected_columns[:self.num_columns]
                    ]
                    self.selected_columns = restored + [None] * max(0, self.num_columns - len(restored))
                else:
                    for i in range(min(self.num_columns, len(available_cols))):
                        self.selected_columns[i] = available_cols[i]
                if len(self.selected_rows) != len(self.df):
                    self.selected_rows = [False] * len(self.df)
                self.image_cache.clear()
                self.image_cache_order.clear()
                gc.collect()
                self.create_column_frames(self.num_columns)
                self.load_selected_rows()
                self.reset_selection_count()
                self.save_settings()
                self.save_selected_rows()
                self.update_display()
                self.update_selected_count()
                self.update_char_count()
            except Exception as e:
                if not auto:
                    self.show_message("エラー", f"CSVの読み込みに失敗しました: {str(e)}", msg_type="error")

    def on_column_select(self, index):
        if self.column_list:
            self.save_all_entries()
            new_selection = self.column_combos[index].get()
            self.selected_columns[index] = new_selection if new_selection else None
            if new_selection and self.is_sku_column(new_selection):
                self.show_sku_grid(new_selection)
            else:
                self.close_sku_grid()
            self.is_modified = True
            self.schedule_save_csv()
            self.update_combobox_values()
            self.update_display()

    def update_display(self):
        if self.df is None or self.current_product_idx >= len(self.product_groups):
            return
        group = self.product_groups[self.current_product_idx]
        parent_row = self.get_parent_row(group)
        for i, entry in enumerate(self.entries):
            entry.delete("1.0", tk.END)
            if self.selected_columns[i]:
                value = str(self.df.iloc[parent_row][self.selected_columns[i]]) if pd.notna(self.df.iloc[parent_row][self.selected_columns[i]]) else ""
                entry.insert("1.0", value)
        selected = any(self.selected_rows[row] for row in group)
        self.row_check_var.set(selected)
        if hasattr(self, "product_structure_var"):
            self.product_structure_var.set(self.summarize_product_group(group))
        image_border_color = "#00ee00" if selected else "#eeeeee"
        self.image_canvas.config(highlightbackground=image_border_color, highlightcolor=image_border_color)
        self.image_canvas.delete("all")
        if '商品画像パス1' in self.df.columns and self.shop_url:
            value = self.df.iloc[parent_row]['商品画像パス1']
            url = self.build_rakuten_image_url(value)
            if url:
                try:
                    cache_key = hashlib.md5(url.encode()).hexdigest()
                    cache_path = self.cache_dir / f"{cache_key}.jpg"
                    if url in self.image_cache:
                        self.photo = self.image_cache[url]
                    elif str(cache_path) in self.image_cache_map.get(url, "") and cache_path.exists():
                        img = Image.open(cache_path)
                        img.thumbnail((200, 200))
                        self.photo = ImageTk.PhotoImage(img)
                        self.remember_memory_image(url, self.photo)
                    else:
                        response = requests.get(url, stream=True, timeout=3)
                        if response.status_code != 200:
                            logging.warning(f"画像取得失敗: URL={url}, ステータス={response.status_code}")
                            return
                        response.raise_for_status()
                        img = Image.open(BytesIO(response.content))
                        img.thumbnail((200, 200))
                        img.save(str(cache_path), "JPEG")
                        self.image_cache_map[url] = str(cache_path)
                        self.save_image_cache_map()
                        self.cleanup_cache()
                        self.photo = ImageTk.PhotoImage(img)
                        self.remember_memory_image(url, self.photo)
                    self.image_canvas.create_image(100, 100, image=self.photo)
                except Exception as e:
                    logging.warning(f"画像処理エラー: URL={url}, {str(e)}")
        self.update_char_count()
        if self.show_option_window:
            self.create_option_grid()
        if self.category_grid_window and self.category_grid_window.winfo_exists():
            self.refresh_category_table()
        if self.image_manage_window and self.image_manage_window.winfo_exists():
            self.refresh_image_manage_window()
        if self.sku_grid_window and self.sku_display_columns:
            self.show_sku_grid()

    def save_all_entries(self):
        if self.df is not None and self.current_product_idx < len(self.product_groups):
            parent_row = self.get_parent_row(self.product_groups[self.current_product_idx])
            for i, entry in enumerate(self.entries):
                if self.selected_columns[i]:
                    new_value = entry.get("1.0", tk.END).rstrip('\n')
                    current_value = str(self.df.iloc[parent_row][self.selected_columns[i]]) if pd.notna(self.df.iloc[parent_row][self.selected_columns[i]]) else ""
                    if new_value != current_value:
                        self.df.at[parent_row, self.selected_columns[i]] = new_value
                        self.is_modified = True
        if self.is_modified:
            self.schedule_save_csv()

    def update_csv(self, index):
        if self.df is not None and self.selected_columns[index] and self.current_product_idx < len(self.product_groups):
            parent_row = self.get_parent_row(self.product_groups[self.current_product_idx])
            new_value = self.entries[index].get("1.0", tk.END).rstrip('\n')
            current_value = str(self.df.iloc[parent_row][self.selected_columns[index]]) if pd.notna(self.df.iloc[parent_row][self.selected_columns[index]]) else ""
            if new_value != current_value:
                self.df.at[parent_row, self.selected_columns[index]] = new_value
                self.is_modified = True
                self.schedule_save_csv()
            self.update_char_count()

    def schedule_save_csv(self):
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(2000, self.save_csv)

    def schedule_save_item_cat_csv(self):
        if self.item_cat_save_timer:
            self.root.after_cancel(self.item_cat_save_timer)
        self.item_cat_save_timer = self.root.after(2000, self.save_item_cat_csv)

    def save_csv(self):
        if self.df is not None and self.file_path and self.is_modified:
            try:
                self.root.config(cursor="wait")
                self.root.update_idletasks()
                df_to_save = self.df.copy()
                df_to_save.to_csv(
                    self.file_path,
                    index=False,
                    encoding=self.csv_encoding or 'cp932',
                    lineterminator='\n',
                    quoting=csv.QUOTE_ALL
                )
                self.is_modified = False
            except Exception as e:
                self.show_message("エラー", f"CSVの保存に失敗しました: {str(e)}", msg_type="error")
                logging.error(f"CSV保存エラー: {str(e)}")
            finally:
                self.root.config(cursor="")
        self.save_timer = None

    def save_item_cat_csv(self):
        if self.item_cat_df is not None and self.item_cat_file_path and self.item_cat_is_modified:
            try:
                self.root.config(cursor="wait")
                self.root.update_idletasks()
                self.item_cat_df.to_csv(
                    self.item_cat_file_path,
                    index=False,
                    encoding=self.item_cat_encoding or 'cp932',
                    lineterminator='\n',
                    quoting=csv.QUOTE_ALL
                )
                self.item_cat_is_modified = False
            except Exception as e:
                self.show_message("エラー", f"カテゴリCSVの保存に失敗しました: {str(e)}", msg_type="error")
                logging.error(f"カテゴリCSV保存エラー: {str(e)}")
            finally:
                self.root.config(cursor="")
        self.item_cat_save_timer = None

    def next_product(self, event=None, shift_pressed=False):
        self.navigate_product(direction=1, selected_only=shift_pressed)

    def prev_product(self, event=None, shift_pressed=False):
        self.navigate_product(direction=-1, selected_only=shift_pressed)

    def navigate_product(self, direction=1, selected_only=False):
        if self.df is None or not self.product_groups:
            return
        self.save_all_entries()
        if self.show_option_window:
            self.save_option_entries()
        if self.sku_grid_window:
            self.save_sku_entries()

        target_products = self.get_navigation_target_products(selected_only=selected_only)
        if not target_products:
            return

        search_text = self.search_var.get().strip()
        checked_cols = [
            self.selected_columns[i]
            for i in range(self.num_columns)
            if self.checked_columns[i] and self.selected_columns[i]
        ]

        if search_text and not checked_cols:
            self.show_message("Warning", "Select a search column.")
            return

        if self.current_product_idx in target_products:
            current_target_idx = target_products.index(self.current_product_idx)
        else:
            current_target_idx = -1 if direction > 0 else 0

        def product_matches(product_idx):
            if not search_text:
                return True
            parent_row = self.get_parent_row(self.product_groups[product_idx])
            terms = search_text.split()
            for col in checked_cols:
                value = str(self.df.iloc[parent_row][col]) if pd.notna(self.df.iloc[parent_row][col]) else ""
                if all(term.lower() in value.lower() for term in terms):
                    return True
            return False

        if search_text:
            match_count = sum(1 for idx in target_products if product_matches(idx))
            self.search_result_var.set(f"Search results: {match_count}")
        else:
            self.search_result_var.set("Search results: 0")

        total = len(target_products)
        for offset in range(1, total + 1):
            next_target_idx = (current_target_idx + direction * offset) % total
            product_idx = target_products[next_target_idx]
            if product_matches(product_idx):
                self.current_product_idx = product_idx
                break

        self.update_display()
        self.save_selected_rows()

    def save_option_entries(self):
        if self.df is None or not self.option_entries:
            return
        for row_idx, (type_entry, name_entry, choice_text, must_entry) in self.option_entries:
            type_val = type_entry.get().strip()
            name_val = name_entry.get().strip()
            choice_val = choice_text.get("1.0", tk.END).strip()
            must_val = must_entry.get().strip()
            self.df.at[row_idx, '選択肢タイプ'] = type_val if type_val else ""
            self.df.at[row_idx, '商品オプション項目名'] = name_val if name_val else ""
            choices = choice_val.split("\n") if choice_val else []
            for i, choice in enumerate(choices, 1):
                col_name = f'商品オプション選択肢{i}'
                if col_name in self.df.columns:
                    self.df.at[row_idx, col_name] = choice.strip() if choice.strip() else ""
            for i in range(len(choices) + 1, 101):
                col_name = f'商品オプション選択肢{i}'
                if col_name in self.df.columns:
                    self.df.at[row_idx, col_name] = ""
            self.df.at[row_idx, '商品オプション選択必須'] = must_val if must_val else ""
            self.is_modified = True
            self.schedule_save_csv()

if __name__ == "__main__":
    root = tk.Tk()
    app = RakutenCSVEditor(root)
    root.mainloop()
