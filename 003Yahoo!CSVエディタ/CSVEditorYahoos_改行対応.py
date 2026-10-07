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
import shutil
import csv
from datetime import datetime
import gc
import sys
import uuid
import re
import threading
import queue
# ログ設定
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(message)s')
SCRIPT_DIR = Path(__file__).resolve().parent
SPEC_CSV_PATH = SCRIPT_DIR / "specification_yh.csv"
SPEC_FIELDS = ["item_name", "mall_name", "required", "format", "description", "search_target"]
STOCK_COLUMNS = ["code", "sub-code", "quantity", "allow-overdraft", "stock-close"]
YAHOO_IMAGE_COLUMN = "item-image-urls"
YAHOO_MAX_IMAGE_URLS = 21
class CSVEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Editor / Yahoo!ショッピング版")
        self.df = None
        self.spec_df = None
        self.current_row = 0
        self.file_path = ""
        self.column_list = []
        self.selected_rows = []
        self.entry_rows_per_column = []
        self.image_cache = {}
        self.image_cache_map = {}
        self.is_modified = False
        self.is_stock_modified = False
        self.save_timer = None
        self.info_window = None
        self.settings_window = None
        self.stock_window = None
        self.cache_dir = SCRIPT_DIR / "cache" / "images_full"
        self.cache_map_file = SCRIPT_DIR / "cache" / "cache.json"
        self.cache_max_size_mb = 100
        self.copy_and_edit = True
        self.append_selection = True
        self.navigate_selected_only = False
        self.code_copy_delimiter = " "
        self.stock_mode = False
        self.stock_data = []
        self.stock_file_path = None
        self.select_shortcut_key = "F1"
        self.active_dialogs = set()
        self.next_button = None
        self.prev_button = None
        self.navigation_mode_button = None
        self.focus_before_image_hover = None
        self.image_manage_window = None
        self.image_manage_canvas = None
        self.image_manage_scrollable_frame = None
        self.image_manage_entries = []
        self.image_manage_photos = []
        self.image_bulk_item_vars = {}
        self.image_bulk_url_var = None
        self.image_bulk_scope_var = None
        self.image_find_text = None
        self.image_replace_text = None
        self.image_cache_progress_var = None
        self.image_cache_progress_label = None
        self.cache_task_running = False
        self.cache_task_queue = queue.Queue()
        self.subwindow_mousewheel_targets = {}
        self.subwindow_mousewheel_bound = False
        # チェックボックスウィジェットを保持するリストを追加
        self.check_widgets = []
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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    def replace_with_column_vars(self, text: str, row_idx: int) -> str:
        def replacer(match):
            col_name = match.group(1).strip()
            if col_name in self.df.columns:
                val = self.df.iloc[row_idx].get(col_name)
                return str(val) if pd.notna(val) else ""
            else:
                logging.warning(f"カラム '{col_name}' が存在しません（行 {row_idx}）")
                return match.group(0)
        pattern = r'%([^%]+)%'
        return re.sub(pattern, replacer, text)
    def copy_stock_text_to_clipboard(self, text, is_name=False):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        label = "サブコード名" if is_name else "サブコード"
        message = f"{label}: {text} をクリップボードにコピーしました。"
        if self.stock_window:
            self.stock_window.title(f"在庫管理 - {message}")
            self.root.after(3000, lambda: self.stock_window.title("在庫管理") if self.stock_window else None)
        else:
            logging.info(message)
    def show_message(self, title, message, msg_type="info"):
        dialog_key = (message, msg_type)
        if dialog_key in self.active_dialogs:
            logging.debug(f"同一のダイアログが既に表示されています: {message}, タイプ: {msg_type}")
            return
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
        tk.Button(dialog, text="OK", command=lambda: [self.active_dialogs.discard(dialog_key), dialog.destroy()], font=("Meiryo", 9)).pack(pady=5)
        self.active_dialogs.add(dialog_key)
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
            self.spec_df.to_csv(SPEC_CSV_PATH, index=False, encoding='shift-jis', lineterminator='\n', quoting=csv.QUOTE_ALL)
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
                self.entry_rows_per_column = settings.get("entry_rows_per_column", [2] * self.num_columns)
                self.cache_max_size_mb = max(1, settings.get("cache_max_size_mb", 100))
                self.copy_and_edit = settings.get("copy_and_edit", True)
                self.append_selection = settings.get("append_selection", True)
                self.navigate_selected_only = settings.get("navigate_selected_only", False)
                self.code_copy_delimiter = settings.get("code_copy_delimiter", " ")
                self.stock_mode = settings.get("stock_mode", False)
                self.select_shortcut_key = settings.get("select_shortcut_key", "F1")
                self.last_selected_columns = settings.get("last_selected_columns", None)
                self.selected_columns = self.selected_columns[:self.num_columns] + [None] * max(0, self.num_columns - len(self.selected_columns))
                self.checked_columns = self.checked_columns[:self.num_columns] + [False] * max(0, self.num_columns - len(self.checked_columns))
                self.entry_rows_per_column = self.entry_rows_per_column[:self.num_columns] + [2] * max(0, self.num_columns - len(self.entry_rows_per_column))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"設定ファイルの読み込みに失敗しました: {str(e)}。デフォルト設定を適用します。")
            self.num_columns = 3
            self.selected_columns = [None] * self.num_columns
            self.checked_columns = [False] * self.num_columns
            self.search_text = ""
            self.file_path = ""
            self.entry_rows_per_column = [2] * self.num_columns
            self.cache_max_size_mb = 100
            self.copy_and_edit = True
            self.append_selection = True
            self.navigate_selected_only = False
            self.code_copy_delimiter = " "
            self.stock_mode = False
            self.select_shortcut_key = "F1"
            self.last_selected_columns = None
    def save_settings(self):
        settings = {
            "num_columns": self.num_columns,
            "selected_columns": self.selected_columns,
            "checked_columns": self.checked_columns,
            "search_text": self.search_var.get() if hasattr(self, "search_var") else self.search_text,
            "file_path": self.file_path,
            "entry_rows_per_column": self.entry_rows_per_column,
            "cache_max_size_mb": self.cache_max_size_mb,
            "copy_and_edit": self.copy_edit_var.get() if hasattr(self, "copy_edit_var") else self.copy_and_edit,
            "append_selection": self.append_selection_var.get() if hasattr(self, "append_selection_var") else self.append_selection,
            "navigate_selected_only": self.navigate_selected_only,
            "code_copy_delimiter": self.code_copy_delimiter,
            "select_shortcut_key": self.select_shortcut_key,
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
                self.current_row = data.get("current_row", 0)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logging.warning(f"選択状態ファイルの読み込みに失敗しました: {str(e)}。デフォルトを適用します。")
            self.selected_rows = []
            self.current_row = 0
        if self.df is not None:
            if len(self.selected_rows) != len(self.df):
                self.selected_rows = [False] * len(self.df)
            if self.current_row >= len(self.df):
                self.current_row = 0
    def save_selected_rows(self):
        try:
            data = {"selected_rows": self.selected_rows, "current_row": self.current_row}
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
        files.sort(key=lambda x: x[1])
        for cache_file, mtime, size in files:
            if total_size > max_size_bytes:
                try:
                    cache_file.unlink()
                    total_size -= size
                    for url, path in list(self.image_cache_map.items()):
                        if path == str(cache_file):
                            del self.image_cache_map[url]
                except Exception as e:
                    logging.warning(f"キャッシュファイルの削除に失敗しました: {str(e)}")
        self.save_image_cache_map()
        if len(self.image_cache) > 100:
            keys = list(self.image_cache.keys())[:len(self.image_cache) - 100]
            for key in keys:
                del self.image_cache[key]
            gc.collect()
    def clear_cache(self):
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.image_cache_map.clear()
            self.image_cache.clear()
            self.save_image_cache_map()
            gc.collect()
            self.show_message("成功", "キャッシュをクリアしました。")
        except Exception as e:
            self.show_message("エラー", f"キャッシュのクリアに失敗しました: {str(e)}", msg_type="error")
            logging.error(f"キャッシュクリアエラー: {str(e)}")
    def find_existing_stock_csv(self, directory):
        matching_files = []
        for csv_file in directory.glob("quantity*.csv"):
            try:
                df = pd.read_csv(csv_file, encoding='shift-jis')
                if list(df.columns) == STOCK_COLUMNS:
                    stats = csv_file.stat()
                    matching_files.append((csv_file, stats.st_mtime))
            except Exception as e:
                logging.warning(f"CSVファイルの読み込みに失敗: {csv_file}, エラー: {str(e)}")
                continue
        if matching_files:
            matching_files.sort(key=lambda x: x[1], reverse=True)
            return str(matching_files[0][0])
        return None
    def load_stock_data(self):
        if not self.stock_file_path or not Path(self.stock_file_path).exists():
            self.stock_data = []
            return
        try:
            df = pd.read_csv(self.stock_file_path, encoding='shift-jis', dtype=str)
            if list(df.columns) != STOCK_COLUMNS:
                logging.warning(f"在庫CSVのカラムが一致しません: {self.stock_file_path}")
                self.stock_data = []
                return
            df['sub-code'] = df['sub-code'].fillna("")
            self.stock_data = df.values.tolist()
            logging.info(f"在庫データを読み込みました: {self.stock_file_path}, 件数: {len(self.stock_data)}")
        except Exception as e:
            logging.error(f"在庫データの読み込みに失敗しました: {str(e)}")
            self.show_message("エラー", f"在庫データの読み込みに失敗しました: {str(e)}", msg_type="error")
            self.stock_data = []
    def create_stock_csv(self):
        if not self.stock_mode or not self.file_path:
            self.stock_file_path = None
            self.stock_data = []
            return
        try:
            file_dir = Path(self.file_path).parent
            existing_csv = self.find_existing_stock_csv(file_dir)
            if existing_csv:
                self.stock_file_path = existing_csv
                self.load_stock_data()
                logging.info(f"既存の在庫CSVを使用: {self.stock_file_path}")
                return
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            self.stock_file_path = str(file_dir / f"quantity{timestamp}.csv")
            pd.DataFrame(columns=STOCK_COLUMNS).to_csv(
                self.stock_file_path, index=False, encoding='shift-jis', lineterminator='\n', quoting=csv.QUOTE_ALL
            )
            self.stock_data = []
            logging.info(f"新しい在庫CSVを作成しました: {self.stock_file_path}")
        except Exception as e:
            self.show_message("エラー", f"在庫CSVの作成に失敗しました: {str(e)}", msg_type="error")
            logging.error(f"在庫CSV作成エラー: {str(e)}")
            self.stock_file_path = None
            self.stock_data = []
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
        tk.Button(cache_frame, text="サムネキャッシュ", command=self.cache_thumbnail_images, font=("Meiryo", 9)).grid(row=1, column=0, padx=5, sticky="ew")
        tk.Button(cache_frame, text="全画像キャッシュ", command=self.cache_all_images, font=("Meiryo", 9)).grid(row=1, column=1, padx=5, sticky="ew")
        cache_frame.grid_columnconfigure(0, weight=1)
        cache_frame.grid_columnconfigure(1, weight=1)
        cache_frame.grid_columnconfigure(2, weight=1)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(cache_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        self.progress_label = tk.Label(cache_frame, text="0/0", font=("Meiryo", 9))
        self.progress_label.grid(row=3, column=0, columnspan=3)
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
            self.append_selection_button.config(text=f"検索選択: {state_text}", relief=relief)

    def toggle_append_selection_setting(self):
        self.append_selection = not self.append_selection
        if hasattr(self, "append_selection_var"):
            self.append_selection_var.set(self.append_selection)
        self.update_append_selection_button()
        self.update_select_button_text()
        self.save_settings()

    def get_yahoo_image_urls_from_row(self, row):
        if self.df is None or YAHOO_IMAGE_COLUMN not in self.df.columns:
            return []
        value = self.df.iloc[row].get(YAHOO_IMAGE_COLUMN, "")
        if pd.isna(value):
            return []
        return [url.strip() for url in str(value).split(";") if url.strip()]

    def get_cache_path_for_url(self, url):
        if url in self.image_cache_map:
            mapped_path = Path(self.image_cache_map[url])
            if mapped_path.parent == self.cache_dir:
                return mapped_path
        cache_key = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.jpg"

    def cache_image_url(self, url):
        if not url:
            return False
        cache_path = self.get_cache_path_for_url(url)
        if cache_path.exists():
            self.image_cache_map[url] = str(cache_path)
            return True
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            response = requests.get(url, stream=True, timeout=8)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(str(cache_path), "JPEG")
            self.image_cache_map[url] = str(cache_path)
            self.save_image_cache_map()
            self.cleanup_cache()
            return True
        except Exception as e:
            logging.warning(f"画像キャッシュ失敗: URL={url}, {str(e)}")
            return False

    def collect_yahoo_image_urls(self, thumbnail_only=False):
        if self.df is None or YAHOO_IMAGE_COLUMN not in self.df.columns:
            return []
        urls = []
        seen = set()
        for row in range(len(self.df)):
            row_urls = self.get_yahoo_image_urls_from_row(row)
            if thumbnail_only:
                row_urls = row_urls[:1]
            for url in row_urls:
                if url and url not in seen:
                    urls.append(url)
                    seen.add(url)
        return urls

    def cache_thumbnail_images(self):
        self.cache_yahoo_images(thumbnail_only=True)

    def cache_all_images(self):
        self.cache_yahoo_images(thumbnail_only=False)

    def cache_yahoo_images(self, thumbnail_only=False):
        if self.df is None or YAHOO_IMAGE_COLUMN not in self.df.columns:
            self.show_message("警告", "データフレームが読み込まれていないか、item-image-urlsカラムが存在しません。")
            return
        if self.cache_task_running:
            self.show_message("警告", "画像キャッシュを実行中です。完了までお待ちください。")
            return
        urls = self.collect_yahoo_image_urls(thumbnail_only=thumbnail_only)
        if not urls:
            self.show_message("警告", "キャッシュ対象の画像がありません。")
            return
        label = "サムネキャッシュ" if thumbnail_only else "全画像キャッシュ"
        self.start_image_cache_task(
            urls,
            label,
            progress_var=self.progress_var,
            progress_label=self.progress_label,
            refresh_on_done=False,
        )

    def start_image_cache_task(self, urls, label, progress_var=None, progress_label=None, refresh_on_done=False):
        if self.cache_task_running:
            self.show_message("警告", "画像キャッシュを実行中です。完了までお待ちください。")
            return
        total = len(urls)
        self.cache_task_running = True
        while not self.cache_task_queue.empty():
            try:
                self.cache_task_queue.get_nowait()
            except queue.Empty:
                break
        if progress_var:
            progress_var.set(0)
        if progress_label:
            progress_label.config(text=f"0/{total}")
        self.root.config(cursor="wait")
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.config(cursor="wait")
        if self.image_manage_window and self.image_manage_window.winfo_exists():
            self.image_manage_window.config(cursor="wait")

        def worker():
            failed = 0
            for index, url in enumerate(urls, 1):
                if not self.cache_image_url(url):
                    failed += 1
                self.cache_task_queue.put(("progress", index, total))
            self.cache_task_queue.put(("done", failed, total, label, refresh_on_done))

        threading.Thread(target=worker, daemon=True).start()
        self.poll_image_cache_task(progress_var, progress_label)

    def poll_image_cache_task(self, progress_var=None, progress_label=None):
        try:
            while True:
                message = self.cache_task_queue.get_nowait()
                if message[0] == "progress":
                    _, processed, total = message
                    if progress_var:
                        progress_var.set((processed / total) * 100)
                    if progress_label:
                        progress_label.config(text=f"{processed}/{total}")
                elif message[0] == "done":
                    _, failed, total, label, refresh_on_done = message
                    self.cache_task_running = False
                    self.root.config(cursor="")
                    if self.settings_window and self.settings_window.winfo_exists():
                        self.settings_window.config(cursor="")
                    if self.image_manage_window and self.image_manage_window.winfo_exists():
                        self.image_manage_window.config(cursor="")
                    if refresh_on_done and self.image_manage_window and self.image_manage_window.winfo_exists():
                        self.refresh_image_manage_window(save_before=False)
                    self.show_message("成功", f"{label}が完了しました。失敗: {failed}件")
                    return
        except queue.Empty:
            pass
        if self.cache_task_running:
            self.root.after(100, lambda: self.poll_image_cache_task(progress_var, progress_label))
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
            self.save_settings()
            self.cleanup_cache()
            if prev_shortcut != self.select_shortcut_key:
                self.update_shortcut_binding(prev_shortcut)
            self.show_message("成功", "設定を保存しました。")
            self.update_select_button_text()
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

        # チェックが入っているカラムを取得
        checked_cols = [self.selected_columns[i] for i in range(self.num_columns)
                       if self.checked_columns[i] and self.selected_columns[i] is not None]

        if not checked_cols:
            self.show_message("警告", "チェックされているカラムがありません。")
            return

        selected_rows = [i for i, selected in enumerate(self.selected_rows) if selected]
        if not selected_rows:
            self.show_message("警告", "選択中の行がありません。")
            return

        values_list = []
        for row_idx in selected_rows:
            row_values = []
            for col in checked_cols:
                val = self.df.iloc[row_idx][col]
                row_values.append(str(val) if pd.notna(val) else "")
            values_list.append(row_values)

        # 出力処理
        if len(checked_cols) == 1:
            # 単一カラム → 設定の区切り文字で連結
            flat_values = [row[0] for row in values_list]
            result = self.code_copy_delimiter.join(flat_values)
            label = checked_cols[0]
        else:
            # 複数カラム → 商品ごとに1行、タブ区切り
            result = "\n".join("\t".join(row) for row in values_list)
            label = f"{len(checked_cols)}カラム（{', '.join(checked_cols)}）"

        self.root.clipboard_clear()
        self.root.clipboard_append(result)

        message = f"{label}: {len(selected_rows)}件 をクリップボードにコピーしました。"
        self.show_message("成功", message)
    def parse_subcode(self, subcode_str):
        if pd.isna(subcode_str) or not subcode_str.strip():
            return [("", "")]
        subcodes = subcode_str.split('&')
        result = []
        for sc in subcodes:
            if '=' in sc:
                name, code = sc.rsplit('=', 1)
                name = name.replace('#', ' ').strip()
                result.append((name, code))
            else:
                result.append(("", ""))
        return result
    def schedule_save_stock_csv(self):
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(2000, self.save_stock_csv)
    def save_stock_csv(self):
        if not self.stock_data or not self.stock_file_path or not self.is_stock_modified:
            self.save_timer = None
            return
        try:
            df = pd.DataFrame(self.stock_data, columns=STOCK_COLUMNS)
            df['sub-code'] = df['sub-code'].fillna("")
            df.to_csv(self.stock_file_path, index=False, encoding='shift-jis', lineterminator='\n', quoting=csv.QUOTE_ALL)
            logging.info(f"在庫CSVを保存しました: {self.stock_file_path}")
            self.is_stock_modified = False
        except Exception as e:
            self.show_message("エラー", f"在庫CSVの保存に失敗しました: {str(e)}", msg_type="error")
            logging.error(f"在庫CSV保存エラー: {str(e)}")
        self.save_timer = None
    def update_stock_data(self, subcode_idx, quantity=None, overdraft=None, stock_close=None):
        if self.df is None or self.current_row >= len(self.df):
            logging.debug("データフレームが無効または行インデックスが範囲外です")
            return
        code = str(self.df.iloc[self.current_row]['code']) if 'code' in self.df.columns and pd.notna(self.df.iloc[self.current_row]['code']) else ""
        if not code:
            logging.debug(f"コードが無効: code={code}")
            return
        subcode_pairs = self.parse_subcode(self.df.iloc[self.current_row].get('sub-code', ""))
        if subcode_idx >= len(subcode_pairs):
            logging.debug(f"サブコードインデックスが範囲外: {subcode_idx}")
            return
        subcode = subcode_pairs[subcode_idx][1]
        existing_idx = None
        for i, row in enumerate(self.stock_data):
            if row[0] == code and row[1] == subcode:
                existing_idx = i
                break
        if quantity is not None and quantity.strip():
            try:
                quantity_val = str(quantity)
                if existing_idx is not None:
                    if (str(self.stock_data[existing_idx][2]) != quantity_val or
                        (overdraft is not None and str(self.stock_data[existing_idx][3]) != str(overdraft)) or
                        (stock_close is not None and str(self.stock_data[existing_idx][4]) != str(stock_close))):
                        self.stock_data[existing_idx][2] = quantity_val
                        if overdraft is not None:
                            self.stock_data[existing_idx][3] = str(overdraft)
                        if stock_close is not None:
                            self.stock_data[existing_idx][4] = str(stock_close)
                        self.is_stock_modified = True
                        self.schedule_save_stock_csv()
                else:
                    self.stock_data.append([
                        code, subcode, quantity_val,
                        str(overdraft) if overdraft is not None else "0",
                        str(stock_close) if stock_close is not None else "0"
                    ])
                    self.is_stock_modified = True
                    self.schedule_save_stock_csv()
            except Exception as e:
                self.show_message("エラー", f"在庫データ更新エラー: {str(e)}", msg_type="error")
        elif quantity is not None and not quantity.strip():
            if existing_idx is not None and self.stock_data[existing_idx][2] != "0":
                self.stock_data[existing_idx][2] = "0"
                self.is_stock_modified = True
                self.schedule_save_stock_csv()
        elif existing_idx is not None and (overdraft is not None or stock_close is not None):
            if overdraft is not None and str(self.stock_data[existing_idx][3]) != str(overdraft):
                self.stock_data[existing_idx][3] = str(overdraft)
                self.is_stock_modified = True
            if stock_close is not None and str(self.stock_data[existing_idx][4]) != str(stock_close):
                self.stock_data[existing_idx][4] = str(stock_close)
                self.is_stock_modified = True
            if self.is_stock_modified:
                self.schedule_save_stock_csv()
    def save_stock_entries(self):
        if not self.stock_mode or not self.stock_entries:
            return
        code = str(self.df.iloc[self.current_row]['code']) if 'code' in self.df.columns and pd.notna(self.df.iloc[self.current_row]['code']) else ""
        subcode_pairs = self.parse_subcode(self.df.iloc[self.current_row].get('sub-code', ""))
        for idx, (quantity_entry, overdraft_var, stock_close_var) in enumerate(self.stock_entries):
            if idx >= len(subcode_pairs):
                continue
            subcode = subcode_pairs[idx][1]
            if not code:
                continue
            quantity = quantity_entry.get().strip()
            self.update_stock_data(idx, quantity=quantity, overdraft=overdraft_var.get(), stock_close=stock_close_var.get())
    def toggle_stock_mode(self):
        self.stock_mode = not self.stock_mode
        if self.stock_mode:
            self.create_stock_csv()
            self.open_stock_window()
        else:
            self.close_stock_window()
        self.save_settings()
        self.create_column_frames(self.num_columns)
        self.update_display()
        self.stock_button.config(text="在庫" if not self.stock_mode else "通常")
    def open_stock_window(self):
        if self.stock_window is not None:
            self.stock_window.lift()
            return
        self.stock_window = tk.Toplevel(self.root)
        self.stock_window.title("在庫管理")
        self.stock_window.geometry("800x400")
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 400
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 200
        self.stock_window.geometry(f"+{x}+{y}")
        self.stock_window.transient(self.root)
        self.stock_window.resizable(True, True)
        self.stock_window.protocol("WM_DELETE_WINDOW", self.close_stock_window)
        self.stock_canvas_frame = tk.Frame(self.stock_window)
        self.stock_canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.stock_canvas = tk.Canvas(self.stock_canvas_frame)
        scrollbar = tk.Scrollbar(self.stock_canvas_frame, orient="vertical", command=self.stock_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stock_canvas.configure(yscrollcommand=scrollbar.set)
        self.stock_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.stock_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        scrollbar.bind("<MouseWheel>", self.on_mouse_wheel)
        self.stock_inner_frame = tk.Frame(self.stock_canvas)
        self.stock_canvas.create_window((0, 0), window=self.stock_inner_frame, anchor="nw")
        self.stock_inner_frame.bind("<Configure>", lambda e: self.stock_canvas.configure(scrollregion=self.stock_canvas.bbox("all")))
        self.update_display()
    def close_stock_window(self):
        if self.stock_window:
            self.save_stock_entries()
            self.stock_window.destroy()
            self.stock_window = None
            self.stock_canvas_frame = None
            self.stock_canvas = None
            self.stock_inner_frame = None
            self.stock_entries = []
            self.stock_mode = False
            self.stock_button.config(text="在庫")
            self.save_settings()
            self.update_display()
    def invert_selection(self):
        if self.df is None:
            return
        self.selected_rows = [not selected for selected in self.selected_rows]
        self.row_check_var.set(self.selected_rows[self.current_row])
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
        frame_csv_top = tk.Frame(frame_csv)
        frame_csv_top.pack(fill=tk.X)
        tk.Label(frame_csv_top, text="CSV選択", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        tk.Entry(frame_csv_top, textvariable=self.path_var, width=40, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame_csv_top, text="参照", command=self.load_csv, font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.stock_button = tk.Button(frame_csv_top, text="在庫", command=self.toggle_stock_mode, font=("Meiryo", 9))
        self.stock_button.pack(side=tk.LEFT, padx=5)
        tk.Button(frame_csv_top, text="設定", command=self.open_settings, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        frame_csv_bottom = tk.Frame(frame_csv)
        frame_csv_bottom.pack(fill=tk.X, pady=5)
        tk.Label(frame_csv_bottom, text="設定選択", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.column_settings_path_var = tk.StringVar()
        tk.Entry(frame_csv_bottom, textvariable=self.column_settings_path_var, width=40, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame_csv_bottom, text="参照", command=self.load_column_settings, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Button(frame_csv_bottom, text="保存", command=self.save_column_settings, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
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
        next_btn = tk.Button(frame_num_cols, text="次へ", font=("Meiryo", 9), width=4, height=1,
                             command=self.next_row)
        next_btn.pack(side=tk.LEFT, padx=2)
        next_btn.bind("<Shift-Button-1>", lambda e: self.next_row(shift_pressed=True))
        self.next_button = next_btn
        prev_btn = tk.Button(frame_num_cols, text="戻る", font=("Meiryo", 9), width=4, height=1,
                             command=self.prev_row)
        prev_btn.pack(side=tk.LEFT, padx=2)
        prev_btn.bind("<Shift-Button-1>", lambda e: self.prev_row(shift_pressed=True))
        self.prev_button = prev_btn
        self.search_result_var = tk.StringVar(value="検索結果: 0")
        tk.Label(frame_num_cols, textvariable=self.search_result_var, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.select_button = tk.Button(frame_num_cols, text="追加" if self.append_selection else "選択", command=self.select_matching_rows, font=("Meiryo", 9))
        self.select_button.pack(side=tk.LEFT, padx=5)
        tk.Button(frame_num_cols, text="クリア", command=self.clear_search, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_num_cols, text="先頭", command=self.go_to_first_row, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        frame_replace = tk.Frame(edit_frame)
        frame_replace.pack(fill=tk.X, pady=2)
        tk.Label(frame_replace, text="選択", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.row_check_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_replace, variable=self.row_check_var, command=self.toggle_row_check, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Button(frame_replace, text="全選択", command=self.select_all_rows, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="全解除", command=self.clear_rows, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.find_text = Text(frame_replace, height=2, width=20, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.find_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(frame_replace, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.replace_text = Text(frame_replace, height=2, width=20, font=("Meiryo", 9), borderwidth=1, relief="sunken")
        self.replace_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(frame_replace, text="置換", command=self.perform_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="追加", command=self.append_text, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="クリア", command=self.clear_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_replace, text="末尾", command=self.go_to_last_row, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
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
        self.image_canvas.bind("<Button-1>", self.toggle_row_check)
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
        tk.Button(self.image_frame, text="画像", command=self.show_image_manage_window, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=5)
        self.navigation_mode_button = tk.Button(self.image_frame, command=self.toggle_navigation_mode, font=("Meiryo", 9))
        self.navigation_mode_button.pack(side=tk.LEFT, padx=5)
        self.update_navigation_mode_button()
        self.column_frame_container = tk.Frame(main_frame)
        self.column_frame_container.pack(fill=tk.X)
        self.column_frames = []
        self.column_combos = []
        self.entries = []
        self.check_vars = []
        self.check_widgets = [] # チェックボックスウィジェットを保持
        self.create_column_frames(self.num_columns)
        self.update_display()
        self.root.bind(f"<{self.select_shortcut_key}>", self.toggle_row_check_shortcut)
        self.root.bind("<Control-Up>", self.prev_row)
        self.root.bind("<Control-Down>", self.next_row)
    def toggle_row_check_shortcut(self, event=None):
        if self.df is not None and self.current_row < len(self.df):
            self.row_check_var.set(not self.row_check_var.get())
            self.toggle_row_check()
        return "break"
    def update_shortcut_binding(self, prev_shortcut):
        self.root.unbind(f"<{prev_shortcut}>")
        self.root.bind(f"<{self.select_shortcut_key}>", self.toggle_row_check_shortcut)
    def toggle_navigation_mode(self):
        self.navigate_selected_only = not self.navigate_selected_only
        self.update_navigation_mode_button()
        self.save_settings()
    def update_navigation_mode_button(self):
        if hasattr(self, 'navigation_mode_button') and self.navigation_mode_button:
            if self.navigate_selected_only:
                self.navigation_mode_button.config(text="選択中", relief=tk.SUNKEN)
            else:
                self.navigation_mode_button.config(text="全商品", relief=tk.RAISED)
    def get_navigation_target_rows(self, selected_only=False):
        if self.df is None:
            return []
        if selected_only or self.navigate_selected_only:
            return [i for i, sel in enumerate(self.selected_rows) if sel]
        return list(range(len(self.df)))
    def get_next_target_row_after_current(self, target_rows):
        if not target_rows:
            return None
        for row in target_rows:
            if row > self.current_row:
                return row
        return target_rows[0]
    def get_prev_target_row_before_current(self, target_rows):
        if not target_rows:
            return None
        for row in reversed(target_rows):
            if row < self.current_row:
                return row
        return target_rows[-1]
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
            self.prev_row(shift_pressed=shift_pressed)
        elif event.keysym == "Right":
            self.next_row(shift_pressed=shift_pressed)
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
        if widget:
            if self.stock_mode and self.stock_canvas:
                if (widget == self.stock_canvas or
                    str(widget.winfo_parent()) == str(self.stock_canvas) or
                    isinstance(widget, tk.Scrollbar) and widget.winfo_parent() == str(self.stock_canvas_frame)):
                    self.stock_canvas.yview_scroll(-1 * (event.delta // 120), "units")
                    return "break"
            if widget == self.image_canvas:
                shift_pressed = (event.state & 0x1) != 0
                if event.delta > 0:
                    self.prev_row(shift_pressed=shift_pressed)
                elif event.delta < 0:
                    self.next_row(shift_pressed=shift_pressed)
                return "break"
        return "break"
    def next_row(self, event=None, shift_pressed=False):
        if self.df is None or len(self.df) == 0:
            return
        self.save_all_entries()
        self.save_stock_entries()
        self.save_image_manage_entries()
        search_text = self.search_var.get().strip()
        checked_cols = [self.selected_columns[i] for i in range(self.num_columns) if self.checked_columns[i] and self.selected_columns[i]]
        target_rows = self.get_navigation_target_rows(selected_only=shift_pressed)
        if not target_rows:
            return
        current_idx_in_target = target_rows.index(self.current_row) if self.current_row in target_rows else -1
        if current_idx_in_target == -1:
            self.current_row = self.get_next_target_row_after_current(target_rows)
        else:
            if search_text and checked_cols:
                search_terms = search_text.split()
                for idx in range(current_idx_in_target + 1, len(target_rows)):
                    row = target_rows[idx]
                    if all(term.lower() in str(self.df.iloc[row].get(col, "")).lower() for col in checked_cols for term in search_terms):
                        self.current_row = row
                        break
                else:
                    self.show_message("情報", "これ以上一致する行がありません。")
            else:
                next_idx = (current_idx_in_target + 1) % len(target_rows)
                self.current_row = target_rows[next_idx]
        self.update_display()
        self.save_selected_rows()
        self.update_search_result_count(checked_cols, search_text)
    def prev_row(self, event=None, shift_pressed=False):
        if self.df is None or len(self.df) == 0:
            return
        self.save_all_entries()
        self.save_stock_entries()
        self.save_image_manage_entries()
        search_text = self.search_var.get().strip()
        checked_cols = [self.selected_columns[i] for i in range(self.num_columns) if self.checked_columns[i] and self.selected_columns[i]]
        target_rows = self.get_navigation_target_rows(selected_only=shift_pressed)
        if not target_rows:
            return
        current_idx_in_target = target_rows.index(self.current_row) if self.current_row in target_rows else -1
        if current_idx_in_target == -1:
            self.current_row = self.get_prev_target_row_before_current(target_rows)
        else:
            if search_text and checked_cols:
                search_terms = search_text.split()
                for idx in range(current_idx_in_target - 1, -1, -1):
                    row = target_rows[idx]
                    if all(term.lower() in str(self.df.iloc[row].get(col, "")).lower() for col in checked_cols for term in search_terms):
                        self.current_row = row
                        break
                else:
                    self.show_message("情報", "これ以上一致する行がありません。")
            else:
                prev_idx = (current_idx_in_target - 1) if current_idx_in_target > 0 else len(target_rows) - 1
                self.current_row = target_rows[prev_idx]
        self.update_display()
        self.save_selected_rows()
        self.update_search_result_count(checked_cols, search_text)
    def update_search_result_count(self, checked_cols, search_text):
        if not search_text or not checked_cols:
            self.search_result_var.set("検索結果: 0")
            return
        search_terms = search_text.split()
        match_count = sum(
            1 for row in range(len(self.df))
            if all(term.lower() in str(self.df.iloc[row].get(col, "")).lower() for col in checked_cols for term in search_terms)
        )
        self.search_result_var.set(f"検索結果: {match_count}")
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
        self.save_stock_entries()
        self.save_image_manage_entries()
        if self.is_stock_modified:
            self.save_stock_csv()
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
            self.save_timer = None
        if self.df is not None and not self.file_path:
            if self.show_confirm("警告", "CSVファイルが指定されていません。保存しますか？"):
                self.file_path = filedialog.asksaveasfilename(filetypes=[("CSV files", "*.csv")], defaultextension=".csv")
        self.save_csv()
        self.save_image_cache_map()
        self.save_settings()
        self.save_selected_rows()
        if self.info_window:
            self.info_window.destroy()
        if self.settings_window:
            self.settings_window.destroy()
        if self.stock_window:
            self.stock_window.destroy()
        self.root.destroy()
    def toggle_row_check(self, event=None):
        if self.df is not None and self.current_row < len(self.df):
            self.selected_rows[self.current_row] = not self.selected_rows[self.current_row]
            self.row_check_var.set(self.selected_rows[self.current_row])
            if self.navigate_selected_only and not self.selected_rows[self.current_row]:
                next_row = self.get_next_target_row_after_current(self.get_navigation_target_rows(selected_only=True))
                if next_row is not None:
                    self.current_row = next_row
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()
    def select_all_rows(self):
        if self.df is not None:
            self.selected_rows = [True] * len(self.df)
            self.row_check_var.set(True)
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()
    def clear_rows(self):
        if self.df is not None:
            self.selected_rows = [False] * len(self.df)
            self.row_check_var.set(False)
            self.update_selected_count()
            self.save_selected_rows()
            self.update_display()
    def select_matching_rows(self):
        if self.df is None:
            return
        search_text = self.search_var.get().strip()
        if not search_text:
            self.show_message("警告", "検索文字列を入力してください。")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        if not checked_cols:
            self.show_message("警告", "カラムを指定してください。")
            return
        if not self.append_selection:
            self.selected_rows = [False] * len(self.df)
        search_terms = search_text.split()
        match_count = 0
        for row in range(len(self.df)):
            match = True
            for col in checked_cols:
                value = str(self.df.iloc[row][col]) if pd.notna(self.df.iloc[row][col]) else ""
                match = match and all(term.lower() in value.lower() for term in search_terms)
                if not match:
                    break
            if match:
                self.selected_rows[row] = True
                match_count += 1
        self.search_result_var.set(f"検索結果: {match_count}")
        self.update_selected_count()
        self.save_selected_rows()
        self.update_display()
    def update_selected_count(self):
        count = sum(self.selected_rows)
        total = len(self.df) if self.df is not None else 0
        self.selected_count_var.set(f"選択中 {count:05d}/{total:05d}")
    def clear_search(self):
        self.search_var.set("")
        self.search_result_var.set("検索結果: 0")
    def clear_replace(self):
        self.find_text.delete("1.0", tk.END)
        self.replace_text.delete("1.0", tk.END)
    def get_text_widget_value(self, widget):
        return widget.get("1.0", "end-1c")
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
        find_text_raw = self.get_text_widget_value(self.find_text)
        replace_text_raw = self.get_text_widget_value(self.replace_text)
        if find_text_raw == "":
            self.show_message("警告", "検索文字列を入力してください。")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        checked_rows = [i for i, selected in enumerate(self.selected_rows) if selected]
        if not checked_cols or not checked_rows:
            self.show_message("警告", "置換対象の行またはカラムを選んでください。")
            return
        has_var_find = '%' in find_text_raw
        has_var_replace = '%' in replace_text_raw
        modified = False
        for row in checked_rows:
            find_text = self.replace_with_column_vars(find_text_raw, row) if has_var_find else find_text_raw
            replace_text = self.replace_with_column_vars(replace_text_raw, row) if has_var_replace else replace_text_raw
            for col in checked_cols:
                value = str(self.df.iloc[row][col]) if pd.notna(self.df.iloc[row][col]) else ""
                new_value = value.replace(find_text, replace_text)
                if new_value != value:
                    self.df.at[row, col] = new_value
                    modified = True
        if modified:
            self.is_modified = True
            self.schedule_save_csv()
            self.update_display()
    def append_text(self):
        if self.df is None:
            return
        prefix_raw = self.get_text_widget_value(self.find_text)
        suffix_raw = self.get_text_widget_value(self.replace_text)
        if prefix_raw == "" and suffix_raw == "":
            self.show_message("警告", "追加する文字列を入力してください。")
            return
        checked_cols = [self.selected_columns[i] for i, checked in enumerate(self.checked_columns) if checked and self.selected_columns[i]]
        checked_rows = [i for i, selected in enumerate(self.selected_rows) if selected]
        if not checked_cols or not checked_rows:
            self.show_message("警告", "追加対象の行またはカラムを選んでください。")
            return
        has_var_prefix = '%' in prefix_raw
        has_var_suffix = '%' in suffix_raw
        modified = False
        for row in checked_rows:
            prefix = self.replace_with_column_vars(prefix_raw, row) if has_var_prefix else prefix_raw
            suffix = self.replace_with_column_vars(suffix_raw, row) if has_var_suffix else suffix_raw
            for col in checked_cols:
                value = str(self.df.iloc[row][col]) if pd.notna(self.df.iloc[row][col]) else ""
                new_value = (prefix + value) if prefix else value
                new_value = (new_value + suffix) if suffix else new_value
                if new_value != value:
                    self.df.at[row, col] = new_value
                    modified = True
        if modified:
            self.is_modified = True
            self.schedule_save_csv()
            self.update_display()
    def update_combobox_values(self):
        selected_cols = [col for col in self.selected_columns if col is not None]
        available_cols = self.column_list.copy()
        for i, combo in enumerate(self.column_combos):
            current_selection = self.selected_columns[i]
            combo_available = [col for col in self.column_list if col not in selected_cols or col == current_selection]
            combo['values'] = combo_available
            if current_selection in combo_available:
                combo.set(current_selection)
            elif combo_available:
                for col in self.column_list:
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
        self.check_widgets = [] # チェックボックスウィジェットを保持（初期化）
        self.num_columns = num_columns
        if len(self.selected_columns) < num_columns:
            used_cols = [col for col in self.selected_columns if col is not None]
            new_cols = [col for col in self.column_list if col not in used_cols][:num_columns - len(self.selected_columns)]
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
            # チェックボックス作成時に背景色を設定
            chk = tk.Checkbutton(frame, variable=check_var,
                                 command=lambda idx=i: self.toggle_check(idx),
                                 font=("Meiryo", 9),
                                 bg="#c8ebd4" if self.checked_columns[i] else "SystemButtonFace")
            chk.pack(side=tk.LEFT)
            chk.pack(side=tk.LEFT)
            self.check_vars.append(check_var)
            self.check_widgets.append(chk) # チェックボックスをリストに保持
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
            # フレームの背景色を設定
            if self.checked_columns[i]:
                frame.configure(bg="#c8ebd4")
            else:
                frame.configure(bg="SystemButtonFace")
        self.update_combobox_values()
        self.update_display()
    def set_focused_entry(self, index):
        self.focused_entry_index = index
        self.update_char_count()
    def update_char_count(self):
        if self.df is not None and self.current_row < len(self.df):
            entry = self.entries[self.focused_entry_index]
            text = self.get_text_widget_value(entry)
            try:
                byte_count = len(text.encode('shift-jis'))
                self.char_count_var.set(f"文字数 半角 {byte_count:05d}")
            except UnicodeEncodeError:
                self.char_count_var.set("文字数 半角 エラー")
    def toggle_check(self, index):
        self.checked_columns[index] = self.check_vars[index].get()
        frame = self.column_frames[index]
        chk = self.check_widgets[index] # 保持したチェックボックスを使用
        if self.checked_columns[index]:
            frame.configure(bg="#c8ebd4")
            chk.configure(bg="#c8ebd4") # チェックボックス自体の背景も同じ色に
        else:
            frame.configure(bg="SystemButtonFace")
            chk.configure(bg="SystemButtonFace")
    def copy_to_clipboard(self, index):
        value = self.get_text_widget_value(self.entries[index])
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
                try:
                    self.df = pd.read_csv(self.file_path, encoding='shift-jis', dtype=str)
                except UnicodeDecodeError:
                    encoding = self.detect_encoding(self.file_path)
                    if encoding:
                        try:
                            self.df = pd.read_csv(self.file_path, encoding=encoding, dtype=str)
                        except Exception as e:
                            if not auto:
                                self.show_message("エラー", f"CSVの読み込みに失敗しました: {str(e)}", msg_type="error")
                            return
                    else:
                        if not auto:
                            self.show_message("エラー", "エンコーディングを検出できませんでした。")
                            return
                except Exception as e:
                    if not auto:
                        self.show_message("エラー", f"CSVの読み込みに失敗しました: {str(e)}", msg_type="error")
                    return
                self.column_list = list(self.df.columns)
                if auto and self.last_selected_columns:
                    self.selected_columns = self.last_selected_columns
                else:
                    self.selected_columns = [None] * self.num_columns
                    for i in range(min(self.num_columns, len(self.column_list))):
                        self.selected_columns[i] = self.column_list[i]
                if len(self.selected_rows) != len(self.df):
                    self.selected_rows = [False] * len(self.df)
                self.image_cache.clear()
                gc.collect()
                if self.stock_mode:
                    self.create_stock_csv()
                    self.open_stock_window()
                self.create_column_frames(self.num_columns)
                self.load_selected_rows()
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
            self.is_modified = True
            self.schedule_save_csv()
            self.update_combobox_values()
            self.update_display()
    def update_display(self):
        if self.df is None or self.current_row >= len(self.df):
            return
        for i, entry in enumerate(self.entries):
            entry.delete("1.0", tk.END)
            if self.selected_columns[i]:
                value = self.df.iloc[self.current_row][self.selected_columns[i]]
                entry.insert("1.0", str(value) if pd.notna(value) else "")
        self.row_check_var.set(self.selected_rows[self.current_row])
        image_border_color = "#00ee00" if self.selected_rows[self.current_row] else "#eeeeee"
        self.image_canvas.config(highlightbackground=image_border_color, highlightcolor=image_border_color)
        if self.stock_mode and self.stock_inner_frame:
            for widget in self.stock_inner_frame.winfo_children():
                widget.destroy()
            self.stock_entries = []
            code = str(self.df.iloc[self.current_row]['code']) if 'code' in self.df.columns and pd.notna(self.df.iloc[self.current_row]['code']) else ""
            subcode_pairs = self.parse_subcode(self.df.iloc[self.current_row].get('sub-code', ""))
            headers = ["サブコード名", "サブコード", "在庫", "超過注文", "クローズ"]
            for j, header in enumerate(headers):
                tk.Label(self.stock_inner_frame, text=header, font=("Meiryo", 9), borderwidth=1, relief="solid", width=20 if j in [0, 1] else 10, anchor="w").grid(row=0, column=j, sticky="nsew")
            for i, (subcode_name, subcode) in enumerate(subcode_pairs):
                row = i + 1
                display_name = subcode_name if subcode_name else "なし"
                display_subcode = subcode if subcode else "なし"
                subcode_name_label = tk.Label(self.stock_inner_frame, text=display_name, font=("Meiryo", 9), borderwidth=1, relief="solid", anchor="w")
                subcode_name_label.grid(row=row, column=0, sticky="nsew")
                subcode_name_label.bind("<Button-1>", lambda e, txt=display_name: self.copy_stock_text_to_clipboard(txt, is_name=True))
                subcode_label = tk.Label(self.stock_inner_frame, text=display_subcode, font=("Meiryo", 9), borderwidth=1, relief="solid", anchor="w")
                subcode_label.grid(row=row, column=1, sticky="nsew")
                subcode_label.bind("<Button-1>", lambda e, txt=display_subcode: self.copy_stock_text_to_clipboard(txt, is_name=False))
                quantity_entry = tk.Entry(self.stock_inner_frame, font=("Meiryo", 9), width=10, borderwidth=1, relief="solid")
                quantity_entry.grid(row=row, column=2, sticky="nsew")
                overdraft_var = tk.StringVar(value="0")
                overdraft_menu = ttk.OptionMenu(self.stock_inner_frame, overdraft_var, "0", "0", "1")
                overdraft_menu.grid(row=row, column=3, sticky="nsew")
                stock_close_var = tk.StringVar(value="0")
                stock_close_menu = ttk.OptionMenu(self.stock_inner_frame, stock_close_var, "0", "0", "1")
                stock_close_menu.grid(row=row, column=4, sticky="nsew")
                for stock_row in self.stock_data:
                    if stock_row[0] == code and stock_row[1] == subcode:
                        quantity_entry.insert(0, str(stock_row[2]))
                        overdraft_var.set(str(stock_row[3]))
                        stock_close_var.set(str(stock_row[4]))
                        break
                def handle_focus_out(event, idx=i, entry=quantity_entry, overdraft=overdraft_var, stock_close=stock_close_var):
                    try:
                        self.root.update_idletasks()
                        qty = entry.get().strip()
                        self.update_stock_data(idx, quantity=qty, overdraft=overdraft.get(), stock_close=stock_close.get())
                        self.save_stock_entries()
                    except tk.TclError as e:
                        logging.warning(f"フォーカスアウトエラー: {str(e)}")
                def handle_quantity_wheel(event, idx=i, entry=quantity_entry):
                    try:
                        current_qty = entry.get().strip()
                        qty = int(current_qty) if current_qty.isdigit() else 0
                        if event.delta > 0:
                            qty += 1
                        elif event.delta < 0 and qty > 0:
                            qty -= 1
                        entry.delete(0, tk.END)
                        entry.insert(0, str(qty))
                        self.update_stock_data(idx, quantity=str(qty), overdraft=overdraft_var.get(), stock_close=stock_close_var.get())
                    except tk.TclError as e:
                        logging.warning(f"ホイール操作エラー: {str(e)}")
                    return "break"
                def handle_overdraft_wheel(event, idx=i, var=overdraft_var):
                    try:
                        current = var.get()
                        new_value = "1" if event.delta > 0 else "0"
                        if current != new_value:
                            var.set(new_value)
                            self.update_stock_data(idx, overdraft=new_value)
                    except tk.TclError as e:
                        logging.warning(f"超過注文ホイールエラー: {str(e)}")
                    return "break"
                def handle_stock_close_wheel(event, idx=i, var=stock_close_var):
                    try:
                        current = var.get()
                        new_value = "1" if event.delta > 0 else "0"
                        if current != new_value:
                            var.set(new_value)
                            self.update_stock_data(idx, stock_close=new_value)
                    except tk.TclError as e:
                        logging.warning(f"クローズホイールエラー: {str(e)}")
                    return "break"
                subcode_name_label.bind("<MouseWheel>", self.on_mouse_wheel)
                subcode_label.bind("<MouseWheel>", self.on_mouse_wheel)
                quantity_entry.bind("<FocusOut>", handle_focus_out)
                quantity_entry.bind("<MouseWheel>", handle_quantity_wheel)
                overdraft_menu.bind("<MouseWheel>", handle_overdraft_wheel)
                stock_close_menu.bind("<MouseWheel>", handle_stock_close_wheel)
                overdraft_var.trace("w", lambda *args, idx=i: self.update_stock_data(idx, overdraft=overdraft_var.get()))
                stock_close_var.trace("w", lambda *args, idx=i: self.update_stock_data(idx, stock_close=stock_close_var.get()))
                quantity_entry.bind("<Tab>", lambda e, idx=i: self.handle_tab(idx))
                quantity_entry.bind("<Return>", lambda e, idx=i: self.handle_tab(idx))
                self.stock_entries.append((quantity_entry, overdraft_var, stock_close_var))
            for j in range(len(headers)):
                self.stock_inner_frame.grid_columnconfigure(j, weight=1)
        self.image_canvas.delete("all")
        if YAHOO_IMAGE_COLUMN not in self.df.columns:
            self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
        else:
            value = self.df.iloc[self.current_row][YAHOO_IMAGE_COLUMN]
            if pd.isna(value):
                self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
            else:
                urls = [url.strip() for url in str(value).split(";") if url.strip()]
                if not urls:
                    self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
                else:
                    first_url = urls[0]
                    cache_path = self.get_cache_path_for_url(first_url)
                    if first_url in self.image_cache:
                        self.display_image(self.image_cache[first_url])
                    elif cache_path.exists():
                        try:
                            img = Image.open(cache_path)
                            img.thumbnail((200, 200))
                            self.image_cache[first_url] = img
                            self.display_image(img)
                        except Exception as e:
                            logging.warning(f"キャッシュ画像読み込み失敗: {first_url}, {e}")
                            self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
                    else:
                        try:
                            if self.cache_image_url(first_url):
                                img = Image.open(cache_path)
                                img.thumbnail((200, 200))
                                self.image_cache[first_url] = img
                                self.display_image(img)
                            else:
                                self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
                        except Exception as e:
                            logging.warning(f"画像取得エラー: URL={first_url}, {e}")
                            self.image_canvas.create_text(100, 100, text="画像なし", font=("Meiryo", 9))
        self.update_char_count()
        self.update_selected_count()
        self.update_search_result_count(
            [self.selected_columns[i] for i in range(self.num_columns) if self.checked_columns[i] and self.selected_columns[i]],
            self.search_var.get().strip()
        )
        if self.image_manage_window and self.image_manage_window.winfo_exists():
            self.refresh_image_manage_window(save_before=False)
    def display_image(self, img):
        self.photo = ImageTk.PhotoImage(img)
        x = max(0, (200 - img.width) // 2)
        y = max(0, (200 - img.height) // 2)
        self.image_canvas.create_image(x, y, image=self.photo, anchor="nw")

    def cell_has_value(self, value):
        return pd.notna(value) and str(value).strip() != ""

    def get_cached_thumbnail_photo(self, url, size=100):
        if not url:
            return None
        cache_path = self.get_cache_path_for_url(url)
        if not cache_path.exists():
            return None
        try:
            img = Image.open(cache_path)
            img.thumbnail((size, size))
            return ImageTk.PhotoImage(img)
        except Exception as e:
            logging.warning(f"キャッシュ画像読み込み失敗: URL={url}, {e}")
            return None

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
        if pointer_widget in (self.image_find_text, self.image_replace_text):
            return None
        for window, canvas in list(self.subwindow_mousewheel_targets.items()):
            if not window or not canvas or not window.winfo_exists() or not canvas.winfo_exists():
                self.subwindow_mousewheel_targets.pop(window, None)
                continue
            if self.pointer_inside_widget(window):
                delta = -1 * int(event.delta / 120) if event.delta else 0
                if delta:
                    canvas.yview_scroll(delta, "units")
                return "break"
        return None

    def on_image_manage_mousewheel(self, event):
        if self.image_manage_canvas:
            delta = -1 * int(event.delta / 120) if event.delta else 0
            if delta:
                self.image_manage_canvas.yview_scroll(delta, "units")
        return "break"

    def show_image_manage_window(self):
        if self.df is None:
            self.show_message("警告", "CSVを読み込んでください。")
            return
        if YAHOO_IMAGE_COLUMN not in self.df.columns:
            self.show_message("警告", "item-image-urlsカラムが存在しません。")
            return
        if self.image_manage_window is None or not self.image_manage_window.winfo_exists():
            self.image_manage_window = tk.Toplevel(self.root)
            self.image_manage_window.title("画像管理")
            self.image_manage_window.geometry("1100x720")
            x = self.root.winfo_x() + self.root.winfo_width() // 2 - 550
            y = self.root.winfo_y() + self.root.winfo_height() // 2 - 360
            self.image_manage_window.geometry(f"+{x}+{y}")
            self.image_manage_window.transient(self.root)
            self.image_manage_window.resizable(True, True)
            self.image_manage_window.protocol("WM_DELETE_WINDOW", self.close_image_manage_window)

            top_frame = tk.Frame(self.image_manage_window)
            top_frame.pack(fill=tk.X, padx=8, pady=6)
            tk.Button(top_frame, text="この商品の画像をキャッシュ", command=self.cache_current_row_images, font=("Meiryo", 9)).pack(side=tk.LEFT)
            self.image_bulk_url_var = tk.BooleanVar(value=False)
            tk.Checkbutton(top_frame, text="URL", variable=self.image_bulk_url_var, command=lambda: self.set_image_bulk_item_vars("url", self.image_bulk_url_var.get()), font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(10, 2))
            self.image_bulk_scope_var = tk.StringVar(value="既存選択")
            scope_combo = ttk.Combobox(top_frame, textvariable=self.image_bulk_scope_var, values=["既存選択", "すべて選択"], state="readonly", width=10, font=("Meiryo", 9))
            scope_combo.pack(side=tk.LEFT, padx=(4, 5))
            scope_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_image_bulk_checks())
            self.image_find_text = Text(top_frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
            self.image_find_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            tk.Label(top_frame, text="→", font=("Meiryo", 9)).pack(side=tk.LEFT)
            self.image_replace_text = Text(top_frame, height=2, width=18, font=("Meiryo", 9), borderwidth=1, relief="sunken")
            self.image_replace_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            tk.Button(top_frame, text="置換", command=self.apply_image_bulk_replace, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="追加", command=self.apply_image_bulk_append, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="削除", command=self.apply_image_bulk_delete, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
            tk.Button(top_frame, text="クリア", command=self.clear_image_manage_edit_texts, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=2)
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
        if not self.image_manage_window or not self.image_manage_window.winfo_exists():
            return
        if save_before:
            self.save_image_manage_entries()
        for widget in self.image_manage_scrollable_frame.winfo_children():
            widget.destroy()
        self.image_manage_entries = []
        self.image_manage_photos = []
        self.image_bulk_item_vars = {}
        code = self.df.iloc[self.current_row].get("code", "") if "code" in self.df.columns else self.current_row + 1
        self.image_manage_window.title(f"画像管理: {code}")

        urls = self.get_yahoo_image_urls_from_row(self.current_row)
        padded_urls = (urls + [""] * YAHOO_MAX_IMAGE_URLS)[:YAHOO_MAX_IMAGE_URLS]
        image_area = ttk.LabelFrame(self.image_manage_scrollable_frame, text="item-image-urls 商品画像URL", padding=6)
        image_area.grid(row=0, column=0, sticky="nsew", padx=8, pady=6)
        for index, url in enumerate(padded_urls):
            row = index // 3
            col = index % 3
            frame = ttk.LabelFrame(image_area, text=f"画像 {index + 1}", padding=5)
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            image_area.grid_columnconfigure(col, weight=1)
            thumb = tk.Canvas(frame, width=100, height=100, bg="white", highlightthickness=1, highlightbackground="#cccccc")
            thumb.grid(row=0, column=0, rowspan=2, padx=(0, 6))
            photo = self.get_cached_thumbnail_photo(url, size=100)
            if photo:
                self.image_manage_photos.append(photo)
                thumb.create_image(50, 50, image=photo)
            else:
                thumb.create_text(50, 50, text="未キャッシュ", font=("Meiryo", 9), fill="#666666")
            var = tk.BooleanVar(value=self.get_initial_image_bulk_check("url", url))
            self.image_bulk_item_vars[("url", index)] = var
            tk.Checkbutton(frame, text="URL", variable=var, font=("Meiryo", 9)).grid(row=0, column=1, sticky="w")
            entry = tk.Entry(frame, font=("Meiryo", 9), width=36)
            entry.grid(row=1, column=1, sticky="ew")
            entry.insert(0, url)
            frame.grid_columnconfigure(1, weight=1)
            self.image_manage_entries.append((index, entry))

    def save_image_manage_entries(self):
        if self.df is None or not self.image_manage_entries:
            return
        changed = False
        urls = [entry.get().strip() for _, entry in sorted(self.image_manage_entries, key=lambda item: item[0])]
        urls = [url for url in urls if url]
        new_value = ";".join(urls)
        current = self.df.iloc[self.current_row].get(YAHOO_IMAGE_COLUMN, "") if YAHOO_IMAGE_COLUMN in self.df.columns else ""
        current = str(current) if pd.notna(current) else ""
        if new_value != current:
            self.df.at[self.current_row, YAHOO_IMAGE_COLUMN] = new_value
            changed = True
        if changed:
            self.is_modified = True
            self.schedule_save_csv()

    def get_initial_image_bulk_check(self, target_type, value):
        checked = self.image_bulk_url_var.get()
        if not checked:
            return False
        if self.image_bulk_scope_var and self.image_bulk_scope_var.get() == "すべて選択":
            return True
        return self.cell_has_value(value)

    def set_image_bulk_item_vars(self, target_type, value):
        if target_type != "url":
            return
        for key, var in self.image_bulk_item_vars.items():
            kind = key[0]
            if kind != "url":
                continue
            if not value:
                var.set(False)
                continue
            if self.image_bulk_scope_var and self.image_bulk_scope_var.get() == "既存選択":
                if kind == "url":
                    _, index = key
                    entry = next((entry for idx, entry in self.image_manage_entries if idx == index), None)
                    var.set(bool(entry and entry.get().strip()))
            else:
                var.set(True)

    def refresh_image_bulk_checks(self):
        if self.image_bulk_url_var:
            self.set_image_bulk_item_vars("url", self.image_bulk_url_var.get())

    def get_image_bulk_targets(self):
        targets = []
        for key, var in self.image_bulk_item_vars.items():
            if not var.get():
                continue
            if key[0] == "url":
                _, index = key
                entry = next((entry for idx, entry in self.image_manage_entries if idx == index), None)
                if entry:
                    targets.append(("url", entry))
        return targets

    def apply_image_bulk_replace(self):
        self.apply_image_bulk_edit("replace")

    def apply_image_bulk_append(self):
        self.apply_image_bulk_edit("append")

    def apply_image_bulk_delete(self):
        self.apply_image_bulk_edit("delete")

    def apply_image_bulk_edit(self, mode):
        targets = self.get_image_bulk_targets()
        if not targets:
            self.show_message("警告", "URLを選択してください。")
            return
        left_text = self.get_text_widget_value(self.image_find_text) if self.image_find_text else ""
        right_text = self.get_text_widget_value(self.image_replace_text) if self.image_replace_text else ""
        if mode == "replace" and not left_text:
            self.show_message("警告", "検索文字列を入力してください。")
            return
        if mode == "append" and not left_text and not right_text:
            self.show_message("警告", "追加する文字列を入力してください。")
            return
        for kind, widget in targets:
            value = widget.get()
            if mode == "replace":
                new_value = value.replace(left_text, right_text)
            elif mode == "delete":
                new_value = ""
            else:
                if not value:
                    continue
                new_value = f"{left_text}{value}{right_text}"
            widget.delete(0, tk.END)
            widget.insert(0, new_value)
        self.save_image_manage_entries()
        self.refresh_image_manage_window(save_before=False)

    def clear_image_manage_edit_texts(self):
        if self.image_find_text:
            self.image_find_text.delete("1.0", tk.END)
        if self.image_replace_text:
            self.image_replace_text.delete("1.0", tk.END)

    def cache_current_row_images(self):
        self.save_image_manage_entries()
        if self.cache_task_running:
            self.show_message("警告", "画像キャッシュを実行中です。完了までお待ちください。")
            return
        urls = self.get_yahoo_image_urls_from_row(self.current_row)
        if not urls:
            self.show_message("警告", "キャッシュ対象の画像がありません。")
            return
        self.start_image_cache_task(
            urls,
            "この商品の画像キャッシュ",
            progress_var=self.image_cache_progress_var,
            progress_label=self.image_cache_progress_label,
            refresh_on_done=True,
        )

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
            self.image_bulk_item_vars = {}
            self.image_bulk_url_var = None
            self.image_bulk_scope_var = None
            self.image_find_text = None
            self.image_replace_text = None
            self.image_cache_progress_var = None
            self.image_cache_progress_label = None
    def handle_tab(self, subcode_idx):
        if subcode_idx + 1 < len(self.stock_entries):
            next_entry = self.stock_entries[subcode_idx + 1][0]
            if next_entry.winfo_exists():
                next_entry.focus_set()
        return "break"
    def update_csv(self, index):
        if self.df is None or self.current_row >= len(self.df) or not self.selected_columns[index]:
            return
        new_value = self.get_text_widget_value(self.entries[index])
        old_value = self.df.iloc[self.current_row][self.selected_columns[index]]
        if pd.isna(old_value):
            old_value = ""
        else:
            old_value = str(old_value)
        if new_value != old_value:
            self.df.at[self.current_row, self.selected_columns[index]] = new_value
            self.is_modified = True
            self.schedule_save_csv()
    def save_all_entries(self):
        for i in range(self.num_columns):
            self.update_csv(i)
    def schedule_save_csv(self):
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(2000, self.save_csv)
    def save_csv(self):
        if not self.is_modified or not self.file_path or self.df is None:
            self.save_timer = None
            return
        try:
            self.df.to_csv(
                self.file_path,
                index=False,
                encoding='shift-jis',
                lineterminator='\n',
                quoting=csv.QUOTE_ALL
            )
            logging.info(f"CSVを保存しました: {self.file_path}")
            self.is_modified = False
        except Exception as e:
            self.show_message("エラー", f"CSVの保存に失敗しました: {str(e)}", msg_type="error")
            logging.error(f"CSV保存エラー: {str(e)}")
        self.save_timer = None
    def go_to_first_row(self):
        if self.df is not None and len(self.df) > 0:
            self.save_all_entries()
            self.save_stock_entries()
            self.current_row = 0
            self.update_display()
            self.save_selected_rows()
    def go_to_last_row(self):
        if self.df is not None and len(self.df) > 0:
            self.save_all_entries()
            self.save_stock_entries()
            self.current_row = len(self.df) - 1
            self.update_display()
            self.save_selected_rows()
    def save_column_settings(self):
        file_path = filedialog.asksaveasfilename(filetypes=[("CSV files", "*.csv")], defaultextension=".csv")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([self.num_columns] + self.selected_columns)
            self.column_settings_path_var.set(file_path)
    def load_column_settings(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                row = next(reader)
                num_columns = int(row[0])
                selected_columns = row[1:] if len(row) > 1 else []
                selected_columns += [None] * (num_columns - len(selected_columns))
            self.save_all_entries()
            if self.is_modified:
                self.save_csv()
            self.num_columns = num_columns
            self.selected_columns = selected_columns
            self.create_column_frames(self.num_columns)
            self.update_combobox_values()
            self.update_display()
            self.column_settings_path_var.set(file_path)
if __name__ == "__main__":
    root = tk.Tk()
    app = CSVEditor(root)
    root.mainloop()
