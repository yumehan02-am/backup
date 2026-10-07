import csv
import hashlib
import json
import logging
import re
import shutil
import threading
import queue
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import chardet
import requests
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, simpledialog, ttk


SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = SCRIPT_DIR / "rpp_adjuster_settings.json"
WORK_STATE_PATH = SCRIPT_DIR / "rpp_adjuster_work_state.json"
OPERATION_SETTINGS_DIR = SCRIPT_DIR / "settings"
WORK_STATES_DIR = SCRIPT_DIR / "work_states"
CACHE_DIR = SCRIPT_DIR / "cache" / "images"
CACHE_MAP_PATH = SCRIPT_DIR / "cache" / "image_cache.json"
DEBUG_LOG_PATH = SCRIPT_DIR / "rpp_adjuster_debug.log"
CPC_MIN_VALUE = 20

REPORT_MARKER = "商品・キーワードCPCを設定される際にはここから上は行ごと削除してください"
CPC_OUTPUT_COLUMNS = ["コントロールカラム", "商品管理番号", "商品CPC"]
EXCLUDE_COLUMNS = ["コントロールカラム", "商品管理番号"]
PRODUCT_ID_COLUMN = "商品管理番号（商品URL）"
PRODUCT_NAME_COLUMN = "商品名"
MAIN_IMAGE_COLUMN = "商品画像パス1"
CATCH_COPY_COLUMN = "キャッチコピー"
ITEM_CSV_COLUMNS = [PRODUCT_ID_COLUMN, PRODUCT_NAME_COLUMN, MAIN_IMAGE_COLUMN, CATCH_COPY_COLUMN]

NUMERIC_COLUMNS = [
    "入札単価",
    "CTR(%)",
    "クリック数(合計)",
    "実績額(合計)",
    "CPC実績(合計)",
    "売上金額(合計720時間)",
    "売上件数(合計720時間)",
    "CVR(合計720時間)(%)",
    "ROAS(合計720時間)(%)",
    "注文獲得単価(合計720時間)",
]

DEFAULT_GRAPH_COLUMNS = [
    "クリック数(合計)",
    "実績額(合計)",
    "売上金額(合計720時間)",
    "ROAS(合計720時間)(%)",
]

NON_GRAPH_COLUMNS = {
    "コントロールカラム",
    "日付",
    "商品ページURL",
    "商品管理番号",
    "商品名",
    "キーワード",
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def debug_log(message: str):
    print(message, flush=True)
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def detect_encoding(path: Path) -> str:
    with open(path, "rb") as f:
        raw = f.read(20000)
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(encoding, errors="replace")
        except Exception:
            continue
        if any(marker in text for marker in ("商品管理番号", "商品CPC", "実績額", "コントロールカラム")):
            return encoding
    detected = chardet.detect(raw)
    encoding = detected.get("encoding")
    try:
        confidence = float(detected.get("confidence") or 0)
    except Exception:
        confidence = 0
    if not encoding or confidence < 0.6:
        return "cp932"
    return encoding


def read_csv_rows(path: Path, skiprows=0) -> list[dict]:
    encoding = detect_encoding(path)
    rows = []
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        for _ in range(skiprows):
            next(f, None)
        reader = csv.DictReader(f)
        for row in reader:
            if any(str(value or "").strip() for value in row.values()):
                rows.append({key: (value or "") for key, value in row.items()})
    return rows


def read_rpp_report(path: Path) -> list[dict]:
    encoding = detect_encoding(path)
    header_index = None
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        lines = []
        for i, line in enumerate(f):
            lines.append(line)
            if i > 100:
                break
    for i, line in enumerate(lines):
        if "商品管理番号" in line and "クリック数(合計)" in line:
            header_index = i
            break
    if header_index is None:
        raise ValueError(f"RPP実績CSVのヘッダー行が見つかりません: {path.name}")
    rows = read_csv_rows(path, skiprows=header_index)
    rows = [row for row in rows if str(row.get("商品管理番号", "")).strip()]
    return rows


def read_report_period(path: Path) -> str:
    encoding = detect_encoding(path)
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f)
        for index, row in enumerate(reader):
            if index > 30:
                break
            for value in row:
                text = str(value or "").strip()
                if text.startswith("集計期間"):
                    return text.split(":", 1)[1].strip() if ":" in text else text
    return ""


def report_period_sort_key(path: Path):
    period = read_report_period(path)
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", period)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return (0, year, month, day, path.name)
    return (1, int(path.stat().st_mtime), 0, 0, path.name)


def read_normal_csv(path: Path) -> list[dict]:
    return read_csv_rows(path)


def read_item_csv_map(path: Path, target_codes=None) -> dict:
    if not path or not path.exists():
        return {}
    target_codes = set(target_codes or [])
    encoding = detect_encoding(path)
    result = {}
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or PRODUCT_ID_COLUMN not in reader.fieldnames:
            return {}
        for row in reader:
            code = str(row.get(PRODUCT_ID_COLUMN, "")).strip()
            if not code or code in result:
                continue
            if target_codes and code not in target_codes:
                continue
            result[code] = {
                PRODUCT_ID_COLUMN: code,
                PRODUCT_NAME_COLUMN: row.get(PRODUCT_NAME_COLUMN, "") or "",
                MAIN_IMAGE_COLUMN: row.get(MAIN_IMAGE_COLUMN, "") or "",
                CATCH_COPY_COLUMN: row.get(CATCH_COPY_COLUMN, "") or "",
            }
    return result


def safe_number(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ""))
    except Exception:
        return default


@dataclass
class ProductState:
    code: str
    name: str = ""
    original_name: str = ""
    url: str = ""
    price: str = ""
    catch_copy: str = ""
    original_catch_copy: str = ""
    image_path: str = ""
    image_url: str = ""
    current_cpc: int | None = None
    new_cpc: int | None = None
    cpc_original_enabled: bool = False
    cpc_enabled: bool = False
    original_excluded: bool = False
    excluded: bool = False
    priority: bool = False
    already_excluded: str = "No"
    prev: dict = field(default_factory=dict)
    curr: dict = field(default_factory=dict)
    reports: list[dict] = field(default_factory=list)

    @property
    def output_cpc(self) -> int | None:
        return self.new_cpc if self.new_cpc is not None else self.current_cpc

    @property
    def cpc_changed(self) -> bool:
        return self.cpc_control is not None

    @property
    def cpc_control(self) -> str | None:
        if self.cpc_original_enabled and not self.cpc_enabled:
            return "d"
        if not self.cpc_original_enabled and self.cpc_enabled:
            return "n"
        if self.cpc_original_enabled and self.cpc_enabled and self.output_cpc is not None and self.output_cpc != self.current_cpc:
            return "u"
        return None

    @property
    def cpc_status(self) -> str:
        control = self.cpc_control
        if control == "n":
            return "新規"
        if control == "u":
            return "変更"
        if control == "d":
            return "削除"
        return "登録済" if self.cpc_original_enabled else ""

    @property
    def exclude_control(self) -> str | None:
        if self.original_excluded and not self.excluded:
            return "d"
        if not self.original_excluded and self.excluded:
            return "n"
        return None

    @property
    def exclude_status(self) -> str:
        control = self.exclude_control
        if control == "n":
            return "新規除外"
        if control == "d":
            return "解除予定"
        return "除外中" if self.original_excluded else ""


class RPPAdjuster:
    def __init__(self, root):
        self.root = root
        self.root.title("楽天RPP 調整ツール")
        self.root.geometry("700x820")
        self.root.minsize(560, 640)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.prev_report_path = tk.StringVar()
        self.curr_report_path = tk.StringVar()
        self.report_path_vars = [self.prev_report_path, self.curr_report_path]
        self.boost_path = tk.StringVar()
        self.exclude_path = tk.StringVar()
        self.item_csv_path = tk.StringVar()
        self.import_folder_path = tk.StringVar()
        self.shop_url_var = tk.StringVar()
        self.operation_setting_var = tk.StringVar()
        self.work_state_var = tk.StringVar()
        self.period_var = tk.StringVar(value="比較期間: -")
        self.cpc_status_var = tk.StringVar(value="")
        self.loaded_input_signature = None
        self.input_status_buttons = {}
        self.load_button = None
        self.export_buttons = []
        self.detail_window = None

        self.products: list[ProductState] = []
        self.filtered_indices: list[int] = []
        self.selected_product_indices: set[int] = set()
        self.current_index = 0
        self.sort_column = None
        self.sort_reverse = False
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar(value="商品名")
        self.search_source_var = tk.StringVar(value="先")
        self.search_choice_var = tk.StringVar()
        self.numeric_search_var = tk.StringVar()
        self.numeric_operator_var = tk.StringVar(value="以下")
        self.bulk_cpc_var = tk.StringVar()
        self.active_text_filter = None
        self.active_numeric_filter = None
        self.filter_conditions = []
        self.show_changed_only = tk.BooleanVar(value=False)
        self.show_excluded_only = tk.BooleanVar(value=False)
        self.selection_count_var = tk.StringVar(value="選択 0件")
        self.image_click_mode_var = tk.StringVar(value="select")
        self.output_all_var = tk.BooleanVar(value=False)
        self.cache_status_var = tk.StringVar(value="未実行")
        self.cache_progress_var = tk.DoubleVar(value=0)
        self.graph_columns = list(DEFAULT_GRAPH_COLUMNS)
        self.graph_column_vars = {}
        self.graph_metric_max_values = {}
        self.graph_window = None
        self.graph_resize_after_id = None
        self.compare_columns_frame = None
        self.settings_window = None
        self.operation_setting_combo = None
        self.work_state_combo = None
        self.cache_button = None
        self.cache_clear_button = None

        self.image_cache_map = {}
        self.image_queue = queue.Queue()
        self.image_photo = None
        self.image_url_cache = {}
        self.updating_tree_selection = False
        self.image_cache_running = False
        self.loading = False
        self.item_loading = False
        self.ignore_tree_select = False
        self.load_queue = queue.Queue()
        self.item_queue = queue.Queue()
        self.tree_render_after_id = None
        self.work_state_save_after_id = None
        self.restoring_work_state = False
        self.load_settings()
        self.load_image_cache_map()
        self.build_ui()
        self.auto_fill_files()
        self.trace_input_vars()
        self.update_io_state()
        self.root.after(200, self.auto_load_previous_work)

    def trace_input_vars(self):
        for var in self.report_path_vars + [self.boost_path, self.exclude_path, self.item_csv_path, self.import_folder_path, self.shop_url_var]:
            if not getattr(var, "_rpp_traced", False):
                var.trace_add("write", lambda *_: self.update_io_state())
                var._rpp_traced = True

    def add_report_path_var(self, value=""):
        var = tk.StringVar(value=value)
        self.report_path_vars.append(var)
        self.trace_input_vars()
        return var

    def load_settings(self):
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                report_paths = data.get("report_paths")
                if not isinstance(report_paths, list) or not report_paths:
                    report_paths = [data.get("prev_report_path", ""), data.get("curr_report_path", "")]
                for index, path in enumerate(report_paths):
                    if index < len(self.report_path_vars):
                        self.report_path_vars[index].set(str(path or ""))
                    else:
                        self.add_report_path_var(str(path or ""))
                self.boost_path.set(data.get("boost_path", ""))
                self.exclude_path.set(data.get("exclude_path", ""))
                self.item_csv_path.set(data.get("item_csv_path", ""))
                self.import_folder_path.set(data.get("import_folder_path", ""))
                self.shop_url_var.set(data.get("shop_url", ""))
                self.operation_setting_var.set(data.get("operation_setting", ""))
                self.work_state_var.set(data.get("work_state", ""))
                self.output_all_var.set(bool(data.get("output_all", False)))
                columns = data.get("graph_columns")
                if isinstance(columns, list) and columns:
                    self.graph_columns = [str(col) for col in columns]
            except Exception:
                logging.exception("設定読み込みに失敗しました")

    def save_settings(self):
        report_paths = [var.get() for var in self.report_path_vars if var.get().strip()]
        data = {
            "report_paths": report_paths,
            "prev_report_path": self.prev_report_path.get(),
            "curr_report_path": self.curr_report_path.get(),
            "boost_path": self.boost_path.get(),
            "exclude_path": self.exclude_path.get(),
            "item_csv_path": self.item_csv_path.get(),
            "import_folder_path": self.import_folder_path.get(),
            "shop_url": self.shop_url_var.get(),
            "operation_setting": self.operation_setting_var.get(),
            "work_state": self.work_state_var.get(),
            "graph_columns": list(self.graph_columns),
            "output_all": bool(self.output_all_var.get()),
        }
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_image_cache_map(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if CACHE_MAP_PATH.exists():
            try:
                self.image_cache_map = json.loads(CACHE_MAP_PATH.read_text(encoding="utf-8"))
            except Exception:
                self.image_cache_map = {}

    def save_image_cache_map(self):
        CACHE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_MAP_PATH.write_text(json.dumps(self.image_cache_map, ensure_ascii=False, indent=2), encoding="utf-8")

    def auto_load_previous_work(self):
        if self.products or self.loading or self.missing_required_inputs():
            return
        if not WORK_STATE_PATH.exists():
            return
        try:
            data = json.loads(WORK_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if data.get("input_signature") != list(self.input_signature()):
            self.status_var.set("前回と入力ファイルが違うため作業状態は復元しません")
            return
        self.load_all()

    def current_work_state_data(self):
        return {
            "input_signature": list(self.input_signature()),
            "current_code": self.current_product().code if self.current_product() else "",
            "sort_column": self.sort_column,
            "sort_reverse": self.sort_reverse,
            "selected_codes": [
                self.products[index].code
                for index in sorted(self.selected_product_indices)
                if 0 <= index < len(self.products)
            ],
            "products": {
                product.code: {
                    "name": product.name,
                    "catch_copy": product.catch_copy,
                    "text_loaded": bool(product.original_name or product.original_catch_copy or product.image_path),
                    "cpc_original_enabled": product.cpc_original_enabled,
                    "current_cpc": product.current_cpc,
                    "cpc_enabled": product.cpc_enabled,
                    "new_cpc": product.new_cpc,
                    "excluded": product.excluded,
                    "priority": product.priority,
                }
                for product in self.products
            },
        }

    def schedule_work_state_save(self):
        if self.restoring_work_state or not self.products or self.loaded_input_signature != self.input_signature():
            return
        if self.work_state_save_after_id:
            self.root.after_cancel(self.work_state_save_after_id)
        self.work_state_save_after_id = self.root.after(400, self.save_work_state)

    def save_work_state(self):
        self.work_state_save_after_id = None
        if not self.products or self.loaded_input_signature != self.input_signature():
            return
        try:
            WORK_STATE_PATH.write_text(json.dumps(self.current_work_state_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logging.exception("作業状態の保存に失敗しました")

    def restore_work_state(self, include_text=True):
        if not self.products or not WORK_STATE_PATH.exists():
            return False
        try:
            data = json.loads(WORK_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return False
        return self.apply_work_state_data(data, include_text=include_text)

    def apply_work_state_data(self, data, include_text=True):
        if not self.products:
            return False
        if data.get("input_signature") != list(self.input_signature()):
            return False
        states = data.get("products")
        if not isinstance(states, dict):
            return False
        self.restoring_work_state = True
        try:
            restored = 0
            for product in self.products:
                state = states.get(product.code)
                if not isinstance(state, dict):
                    continue
                if include_text and state.get("text_loaded"):
                    product.name = str(state.get("name", product.name))
                    product.catch_copy = str(state.get("catch_copy", product.catch_copy))
                has_cpc_base = "cpc_original_enabled" in state and "current_cpc" in state
                cpc_base_matches = (
                    bool(state.get("cpc_original_enabled")) == product.cpc_original_enabled
                    and (
                        (state.get("current_cpc") is None and product.current_cpc is None)
                        or int(safe_number(state.get("current_cpc"), product.current_cpc if product.current_cpc is not None else 0)) == product.current_cpc
                    )
                )
                legacy_false_over_registered = (
                    not has_cpc_base
                    and product.cpc_original_enabled
                    and state.get("cpc_enabled") is False
                )
                if (has_cpc_base and cpc_base_matches) or (not has_cpc_base and not legacy_false_over_registered):
                    product.cpc_enabled = bool(state.get("cpc_enabled", product.cpc_enabled))
                    new_cpc = state.get("new_cpc")
                    product.new_cpc = int(safe_number(new_cpc, 0)) if new_cpc is not None else None
                product.excluded = bool(state.get("excluded", product.excluded))
                product.priority = bool(state.get("priority", product.priority))
                restored += 1
            code_to_index = {product.code: index for index, product in enumerate(self.products)}
            selected_codes = data.get("selected_codes") or []
            self.selected_product_indices = {
                code_to_index[code]
                for code in selected_codes
                if code in code_to_index
            }
            if data.get("sort_column"):
                self.sort_column = data.get("sort_column")
                self.sort_reverse = bool(data.get("sort_reverse", False))
            current_code = data.get("current_code")
            if current_code in code_to_index:
                product_index = code_to_index[current_code]
                if product_index in self.filtered_indices:
                    self.current_index = self.filtered_indices.index(product_index)
            if restored:
                self.status_var.set(f"作業状態を復元しました: {restored}件")
            return bool(restored)
        finally:
            self.restoring_work_state = False

    def auto_fill_files(self):
        files = list(SCRIPT_DIR.glob("*.csv"))
        if not self.boost_path.get():
            boost = next((p for p in files if p.name.startswith("rpp_item_boost")), None)
            if boost:
                self.boost_path.set(str(boost))
        if not self.exclude_path.get():
            exclude = next((p for p in files if p.name.startswith("RPP_exclude_items")), None)
            if exclude:
                self.exclude_path.set(str(exclude))
        if not self.item_csv_path.get():
            item_csv = next((p for p in files if p.name.startswith("normal-item")), None)
            if item_csv:
                self.item_csv_path.set(str(item_csv))
        if not self.prev_report_path.get() or not self.curr_report_path.get():
            reports = sorted([p for p in files if p.name.startswith("rpp_item_reports")], key=report_period_sort_key)
            if len(reports) >= 2:
                self.prev_report_path.set(str(reports[-2]))
                self.curr_report_path.set(str(reports[-1]))

    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=6)

        load_group = ttk.LabelFrame(top, text="読込", padding=6)
        load_group.grid(row=0, column=0, sticky="ew")
        self.add_shortcut_button(load_group, 0, "実績1", self.prev_report_path, "report1")
        self.add_shortcut_button(load_group, 1, "実績2", self.curr_report_path, "report2")
        self.add_shortcut_button(load_group, 2, "CPC", self.boost_path, "boost")
        self.add_shortcut_button(load_group, 3, "除外", self.exclude_path, "exclude")
        self.add_shortcut_button(load_group, 4, "商品", self.item_csv_path, "item")
        self.load_button = tk.Button(load_group, text="読み込み", command=self.load_all, font=("Meiryo", 9), width=12)
        self.load_button.grid(row=0, column=5, padx=(6, 3), sticky="ew")
        tk.Button(load_group, text="更新", command=self.update_files_from_import_folder, font=("Meiryo", 9), width=10).grid(row=0, column=6, padx=(0, 3), sticky="ew")
        tk.Label(load_group, textvariable=self.period_var, font=("Meiryo", 9), anchor="w", fg="#444444").grid(row=1, column=0, columnspan=7, sticky="ew", padx=3, pady=(4, 0))
        load_group.grid_columnconfigure(7, weight=1)

        action_group = ttk.LabelFrame(top, text="操作", padding=6)
        action_group.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        export_group = ttk.LabelFrame(action_group, text="書き出し", padding=6)
        export_group.grid(row=0, column=0, sticky="w")
        self.export_buttons = [
            tk.Button(export_group, text="CPC CSV", command=self.export_cpc_csv, font=("Meiryo", 9), width=12),
            tk.Button(export_group, text="除外CSV", command=self.export_exclude_csv, font=("Meiryo", 9), width=12),
            tk.Button(export_group, text="商品CSV", command=self.export_item_csv, font=("Meiryo", 9), width=12),
        ]
        for column, button in enumerate(self.export_buttons):
            button.grid(row=0, column=column, padx=3, sticky="ew")

        settings_group = ttk.LabelFrame(action_group, text="設定", padding=6)
        settings_group.grid(row=0, column=1, sticky="w", padx=8)
        tk.Button(settings_group, text="設定", command=self.open_settings_window, font=("Meiryo", 9), width=10).grid(row=0, column=0, padx=3, sticky="ew")

        detail_group = ttk.LabelFrame(action_group, text="詳細", padding=6)
        detail_group.grid(row=0, column=3, sticky="e")
        tk.Button(detail_group, text="商品詳細", command=self.open_detail_window, font=("Meiryo", 9), width=9, bg="#9be7a8", activebackground="#86d995").grid(row=0, column=0, padx=3, sticky="ew")
        action_group.grid_columnconfigure(2, weight=1)
        top.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=8, pady=(0, 6))
        search_row = tk.Frame(toolbar)
        search_row.pack(anchor="w")
        filter_row = tk.Frame(toolbar)
        filter_row.pack(anchor="w", pady=(4, 0))
        tk.Label(search_row, text="検索項目", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.search_column_combo = ttk.Combobox(search_row, textvariable=self.search_column_var, font=("Meiryo", 9), width=24, state="readonly")
        self.search_column_combo.pack(side=tk.LEFT, padx=4)
        self.search_column_combo["values"] = ("商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "除外", "重点")
        self.search_column_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_search_input_ui())
        self.search_source_combo = ttk.Combobox(search_row, textvariable=self.search_source_var, font=("Meiryo", 9), width=5, state="readonly", values=("元", "先", "差"))
        self.search_source_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.search_source_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_search_input_ui())
        self.search_input_frame = tk.Frame(search_row)
        self.search_input_frame.pack(side=tk.LEFT)
        tk.Button(search_row, text="検索", command=self.run_search, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(search_row, text="解除", command=self.clear_search_filters, font=("Meiryo", 9), width=8).pack(side=tk.LEFT)
        tk.Checkbutton(filter_row, text="変更のみ", variable=self.show_changed_only, command=self.apply_filter, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Checkbutton(filter_row, text="除外のみ", variable=self.show_excluded_only, command=self.apply_filter, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=6)
        self.position_var = tk.StringVar(value="0/0")
        self.status_var = tk.StringVar(value="未読込")
        tk.Label(filter_row, textvariable=self.status_var, font=("Meiryo", 9), anchor="w").pack(side=tk.LEFT, padx=12)

        selection_bar = tk.Frame(self.root)
        selection_bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(selection_bar, textvariable=self.selection_count_var, font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        tk.Button(selection_bar, text="表示中を全選択", command=self.select_visible_products, font=("Meiryo", 9), width=14).pack(side=tk.LEFT, padx=3)
        tk.Button(selection_bar, text="選択解除", command=self.clear_product_selection, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=3)
        tk.Button(selection_bar, text="選択反転", command=self.invert_visible_selection, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=3)
        tk.Label(selection_bar, text="Shift/Ctrlで複数選択できます", font=("Meiryo", 8), fg="#666666").pack(side=tk.LEFT, padx=8)

        bulk_bar = ttk.LabelFrame(self.root, text="選択商品の一括操作", padding=5)
        bulk_bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(bulk_bar, text="CPC", font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Entry(bulk_bar, textvariable=self.bulk_cpc_var, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bulk_bar, text="CPC一括適用", command=self.apply_bulk_cpc, font=("Meiryo", 9), width=12).pack(side=tk.LEFT, padx=3)
        tk.Button(bulk_bar, text="CPC一括削除", command=self.delete_bulk_cpc, font=("Meiryo", 9), width=12).pack(side=tk.LEFT, padx=3)
        tk.Button(bulk_bar, text="除外ON", command=lambda: self.set_bulk_excluded(True), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=(12, 3))
        tk.Button(bulk_bar, text="除外OFF", command=lambda: self.set_bulk_excluded(False), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(bulk_bar, text="重点ON", command=lambda: self.set_bulk_priority(True), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=(12, 3))
        tk.Button(bulk_bar, text="重点OFF", command=lambda: self.set_bulk_priority(False), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)

        history_bar = ttk.LabelFrame(self.root, text="選別履歴", padding=5)
        history_bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.condition_listbox = tk.Listbox(history_bar, height=3, font=("Meiryo", 8), exportselection=False)
        self.condition_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.condition_listbox.config(width=42)
        history_scroll = tk.Scrollbar(history_bar, orient=tk.VERTICAL, command=self.condition_listbox.yview)
        history_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.condition_listbox.configure(yscrollcommand=history_scroll.set)
        tk.Button(history_bar, text="戻す", command=self.undo_last_condition, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=6)
        tk.Button(history_bar, text="クリア", command=self.reset_conditions_and_selection, font=("Meiryo", 9), width=6).pack(side=tk.LEFT)

        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        columns = ("code", "name", "priority", "cpc", "new_cpc", "exclude", "click_diff", "cost_total", "cost_diff", "sales_diff", "roas_curr")
        self.tree = ttk.Treeview(main, columns=columns, show="headings", height=24, selectmode="extended")
        headings = {
            "code": "商品管理番号",
            "name": "商品名",
            "priority": "重点",
            "cpc": "現CPC",
            "new_cpc": "新CPC",
            "exclude": "除外",
            "click_diff": "クリック差",
            "cost_total": "合算費用",
            "cost_diff": "費用差",
            "sales_diff": "売上差",
            "roas_curr": "ROAS",
        }
        widths = {"code": 130, "name": 330, "priority": 50, "cpc": 60, "new_cpc": 60, "exclude": 50, "click_diff": 70, "cost_total": 80, "cost_diff": 70, "sales_diff": 80, "roas_curr": 70}
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self.sort_tree_by(c))
            self.tree.column(col, width=widths[col], anchor="w" if col in ("code", "name") else "e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar = tk.Scrollbar(main, orient=tk.VERTICAL, command=self.tree.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar = tk.Scrollbar(main, orient=tk.HORIZONTAL, command=self.tree.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.name_var = tk.StringVar()
        self.catch_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.cpc_var = tk.StringVar()
        self.exclude_var = tk.BooleanVar()
        self.image_canvas = None
        self.image_click_mode_button = None
        self.name_entry = None
        self.catch_entry = None
        self.priority_button = None
        self.exclude_button = None
        self.metrics_text = None
        self.graph = None
        self.graph_inner = None

        self.root.bind("<Control-Up>", lambda event: self.prev_product())
        self.root.bind("<Control-Down>", lambda event: self.next_product())
        self.update_search_input_ui()

    def build_detail_content(self, parent):
        product = ttk.LabelFrame(parent, text="商品", padding=8)
        product.pack(fill=tk.X, padx=8, pady=8)
        self.image_canvas = tk.Canvas(product, width=180, height=180, bg="white", highlightthickness=3, highlightbackground="#f0f0f0", takefocus=True)
        self.image_canvas.grid(row=0, column=0, rowspan=5, padx=(0, 10), sticky="nw")
        self.image_canvas.bind("<MouseWheel>", self.on_image_wheel)
        self.image_canvas.bind("<Button-1>", self.on_image_click)
        self.image_canvas.bind("<Enter>", lambda _event: self.image_canvas.focus_set())
        self.image_canvas.bind("<Left>", lambda _event: self.prev_product())
        self.image_canvas.bind("<Right>", lambda _event: self.next_product())
        self.image_click_mode_button = tk.Button(product, command=self.toggle_image_click_mode, font=("Meiryo", 8), width=16)
        self.image_click_mode_button.grid(row=5, column=0, padx=(0, 10), pady=(4, 0), sticky="ew")
        self.priority_button = tk.Button(product, command=self.toggle_priority, font=("Meiryo", 8), width=16)
        self.priority_button.grid(row=6, column=0, padx=(0, 10), pady=(4, 0), sticky="ew")
        self.update_image_click_mode_button()
        nav_frame = tk.Frame(product)
        nav_frame.grid(row=0, column=1, sticky="ew")
        tk.Button(nav_frame, text="Prev", command=self.prev_product, font=("Meiryo", 9), width=6).pack(side=tk.LEFT)
        tk.Button(nav_frame, text="Next", command=self.next_product, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=4)
        tk.Button(nav_frame, text="楽天検索", command=self.open_rakuten_search, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(nav_frame, textvariable=self.position_var, font=("Meiryo", 9), width=10).pack(side=tk.LEFT)
        tk.Label(nav_frame, textvariable=self.code_var, font=("Meiryo", 10, "bold"), anchor="w").pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        name_frame = tk.Frame(product)
        name_frame.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        tk.Label(name_frame, text="商品名", font=("Meiryo", 8), width=8, anchor="w").pack(side=tk.LEFT)
        self.name_entry = tk.Entry(name_frame, textvariable=self.name_var, font=("Meiryo", 9))
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.name_entry.bind("<Control-a>", self.select_all_entry)
        self.name_entry.bind("<Control-A>", self.select_all_entry)
        catch_frame = tk.Frame(product)
        catch_frame.grid(row=2, column=1, sticky="ew", pady=(3, 0))
        tk.Label(catch_frame, text="キャッチ", font=("Meiryo", 8), width=8, anchor="w").pack(side=tk.LEFT)
        self.catch_entry = tk.Entry(catch_frame, textvariable=self.catch_var, font=("Meiryo", 9))
        self.catch_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.catch_entry.bind("<Control-a>", self.select_all_entry)
        self.catch_entry.bind("<Control-A>", self.select_all_entry)
        tk.Label(product, textvariable=self.url_var, font=("Meiryo", 8), fg="#336699", wraplength=430, justify=tk.LEFT, anchor="w").grid(row=3, column=1, sticky="ew")

        cpc_frame = tk.Frame(product)
        cpc_frame.grid(row=4, column=1, sticky="w", pady=8)
        tk.Label(cpc_frame, text="CPC", font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Button(cpc_frame, text="-5", command=lambda: self.adjust_cpc(-5), font=("Meiryo", 9), width=4).pack(side=tk.LEFT)
        tk.Button(cpc_frame, text="-1", command=lambda: self.adjust_cpc(-1), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=(2, 0))
        tk.Entry(cpc_frame, textvariable=self.cpc_var, font=("Meiryo", 10), width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(cpc_frame, text="+1", command=lambda: self.adjust_cpc(1), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=(2, 0))
        tk.Button(cpc_frame, text="+5", command=lambda: self.adjust_cpc(5), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(cpc_frame, text="適用", command=self.apply_cpc, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=6)
        tk.Button(cpc_frame, text="削除", command=self.delete_cpc, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(cpc_frame, textvariable=self.cpc_status_var, font=("Meiryo", 9), width=10, anchor="w").pack(side=tk.LEFT)
        self.exclude_button = tk.Button(cpc_frame, command=self.toggle_exclude, font=("Meiryo", 9), width=12)
        self.exclude_button.pack(side=tk.LEFT)
        product.grid_columnconfigure(1, weight=1)

        graph_frame = ttk.LabelFrame(parent, text="比較", padding=8)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.graph = tk.Canvas(graph_frame, bg="white", height=260, highlightthickness=0)
        graph_scroll = tk.Scrollbar(graph_frame, orient=tk.VERTICAL, command=self.graph.yview)
        graph_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.graph.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.graph.configure(yscrollcommand=graph_scroll.set)
        self.graph_inner = tk.Frame(self.graph, bg="white")
        self.graph_window = self.graph.create_window((0, 0), window=self.graph_inner, anchor="nw")
        self.graph_inner.bind("<Configure>", lambda _event: self.graph.configure(scrollregion=self.graph.bbox("all")))
        self.graph.bind("<Configure>", self.on_graph_configure)
        self.graph.bind("<MouseWheel>", self.on_graph_wheel)

    def open_detail_window(self):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.lift()
            if self.filtered_indices:
                self.show_product(self.current_index)
            return
        win = tk.Toplevel(self.root)
        win.title("商品詳細")
        win.geometry("760x760")
        win.minsize(620, 560)
        self.detail_window = win
        win.protocol("WM_DELETE_WINDOW", self.close_detail_window)
        self.build_detail_content(win)
        if self.filtered_indices:
            self.show_product(self.current_index)

    def close_detail_window(self):
        self.apply_current_text_edits()
        self.save_work_state()
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
        self.detail_window = None
        self.image_canvas = None
        self.image_click_mode_button = None
        self.priority_button = None
        self.name_entry = None
        self.catch_entry = None
        self.exclude_button = None
        self.metrics_text = None
        self.graph = None
        self.graph_inner = None
        self.graph_window = None
        self.graph_resize_after_id = None

    def close_app(self):
        self.apply_current_text_edits()
        self.save_settings()
        self.save_work_state()
        self.root.destroy()

    def select_all_entry(self, event):
        event.widget.select_range(0, tk.END)
        event.widget.icursor(tk.END)
        return "break"

    def selected_entry_text(self):
        entries = [self.name_entry, self.catch_entry]
        focus = self.root.focus_get()
        if focus in entries:
            entries = [focus] + [entry for entry in entries if entry is not focus]
        for entry in entries:
            if not entry:
                continue
            try:
                if entry.selection_present():
                    text = entry.selection_get().strip()
                    if text:
                        return text
            except tk.TclError:
                continue
        return ""

    def default_search_keyword(self):
        name = self.name_var.get().strip()
        if not name:
            return ""
        return name.split(" ", 1)[0].strip() or name[:30].strip()

    def open_rakuten_search(self):
        keyword = self.selected_entry_text() or self.default_search_keyword()
        if not keyword:
            messagebox.showinfo("楽天検索", "検索する文字列がありません。")
            return
        url = f"https://search.rakuten.co.jp/search/mall/{urllib.parse.quote(keyword)}/"
        webbrowser.open(url)
        self.status_var.set(f"楽天検索: {keyword}")


    def add_file_row(self, parent, row, label, var):
        tk.Label(parent, text=label, font=("Meiryo", 9), width=10, anchor="w").grid(row=row, column=0, sticky="w", pady=2)
        tk.Entry(parent, textvariable=var, font=("Meiryo", 9)).grid(row=row, column=1, sticky="ew", padx=4)
        tk.Button(parent, text="参照", command=lambda: self.select_file(var), font=("Meiryo", 9), width=8).grid(row=row, column=2, padx=2)

    def add_shortcut_button(self, parent, column, label, var, key):
        button = tk.Button(parent, text=label, command=lambda: self.select_file(var), font=("Meiryo", 9), width=10)
        button.grid(row=0, column=column, padx=3, sticky="ew")
        self.input_status_buttons[key] = button
        return button

    def required_input_items(self):
        reports = [
            (f"report{index + 1}", f"実績{index + 1}", var.get(), True)
            for index, var in enumerate(self.report_path_vars)
        ]
        return reports + [
            ("boost", "CPC", self.boost_path.get(), True),
            ("exclude", "除外", self.exclude_path.get(), True),
            ("item", "商品", self.item_csv_path.get(), True),
            ("shop_url", "店舗URL", self.shop_url_var.get(), False),
        ]

    def input_signature(self):
        return tuple(str(value or "").strip() for _, _, value, _ in self.required_input_items())

    def missing_required_inputs(self):
        missing = []
        report_values = [var.get().strip() for var in self.report_path_vars if var.get().strip()]
        if len(report_values) < 2:
            missing.append("実績CSV 2件以上")
        for _, label, value, must_exist in self.required_input_items():
            text = str(value or "").strip()
            if not text:
                missing.append(label)
            elif must_exist and not Path(text).exists():
                missing.append(f"{label}(不存在)")
        return missing

    def update_io_state(self):
        missing = self.missing_required_inputs()
        signature = self.input_signature()
        is_loaded = bool(self.products) and self.loaded_input_signature == signature
        colors = {
            "missing": "#f7c9c9",
            "ready": "#fff2b8",
            "loaded": "#c8ebd4",
        }
        for key, _label, value, must_exist in self.required_input_items():
            button = self.input_status_buttons.get(key)
            if not button:
                continue
            text = str(value or "").strip()
            if not text or (must_exist and not Path(text).exists()):
                bg = colors["missing"]
            elif is_loaded:
                bg = colors["loaded"]
            else:
                bg = colors["ready"]
            button.config(bg=bg, activebackground=bg)
        if self.load_button:
            self.load_button.config(state=tk.NORMAL if not missing and not self.loading else tk.DISABLED)
        for button in self.export_buttons:
            button.config(state=tk.NORMAL if is_loaded else tk.DISABLED)
        if missing:
            self.status_var.set("未設定: " + ", ".join(missing))
        elif not is_loaded:
            self.status_var.set("未読み込みの変更あり")

    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("設定")
        win.geometry("700x620")
        win.transient(self.root)
        self.settings_window = win
        win.protocol("WM_DELETE_WINDOW", lambda: self.close_settings_window(win))

        body = tk.Frame(win)
        buttons = tk.Frame(win)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        content_canvas = tk.Canvas(body, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=content_canvas.yview)
        content = tk.Frame(content_canvas)
        content_window = content_canvas.create_window((0, 0), window=content, anchor="nw")
        content_canvas.configure(yscrollcommand=content_scrollbar.set)
        content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_scrollregion(_event=None):
            content_canvas.configure(scrollregion=content_canvas.bbox("all"))

        def fit_content_width(event):
            content_canvas.itemconfigure(content_window, width=event.width)

        def scroll_settings(event):
            content_canvas.yview_scroll(-int(event.delta / 120), "units")

        def bind_settings_mousewheel(widget):
            widget.bind("<MouseWheel>", scroll_settings)
            for child in widget.winfo_children():
                bind_settings_mousewheel(child)

        content.bind("<Configure>", update_scrollregion)
        content_canvas.bind("<Configure>", fit_content_width)
        content_canvas.bind("<MouseWheel>", scroll_settings)
        content.bind("<MouseWheel>", scroll_settings)

        file_frame = ttk.LabelFrame(content, text="読み込みファイル", padding=8)
        file_frame.pack(fill=tk.X, padx=8, pady=8)
        self.build_settings_file_rows(file_frame)

        preset_frame = ttk.LabelFrame(content, text="操作設定", padding=6)
        preset_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(preset_frame, text="設定", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.operation_setting_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.operation_setting_var,
            values=self.list_operation_settings(),
            state="readonly",
            font=("Meiryo", 9),
            width=24,
        )
        self.operation_setting_combo.pack(side=tk.LEFT, padx=4)
        self.operation_setting_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_selected_operation_setting())
        tk.Button(preset_frame, text="読込", command=self.load_selected_operation_setting, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(preset_frame, text="上書き保存", command=self.save_current_operation_setting, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=3)
        tk.Button(preset_frame, text="名前を付けて保存", command=self.save_operation_setting_as, font=("Meiryo", 9), width=14).pack(side=tk.LEFT, padx=3)
        tk.Button(preset_frame, text="削除", command=self.delete_operation_setting, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)

        work_state_frame = ttk.LabelFrame(content, text="作業状態", padding=6)
        work_state_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(work_state_frame, text="状態", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.work_state_combo = ttk.Combobox(
            work_state_frame,
            textvariable=self.work_state_var,
            values=self.list_work_states(),
            state="readonly",
            font=("Meiryo", 9),
            width=24,
        )
        self.work_state_combo.pack(side=tk.LEFT, padx=4)
        self.work_state_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_selected_work_state())
        tk.Button(work_state_frame, text="読込", command=self.load_selected_work_state, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(work_state_frame, text="上書き保存", command=self.save_current_named_work_state, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=3)
        tk.Button(work_state_frame, text="名前を付けて保存", command=self.save_current_work_state_as, font=("Meiryo", 9), width=14).pack(side=tk.LEFT, padx=3)
        tk.Button(work_state_frame, text="削除", command=self.delete_named_work_state, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)

        export_frame = ttk.LabelFrame(content, text="出力", padding=6)
        export_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Checkbutton(
            export_frame,
            text="全項目を出力（完全入れ替え用）",
            variable=self.output_all_var,
            command=self.save_settings,
            font=("Meiryo", 9),
        ).pack(anchor="w")

        compare_frame = ttk.LabelFrame(content, text="比較列", padding=6)
        compare_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        compare_buttons = tk.Frame(compare_frame)
        compare_buttons.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        tk.Button(compare_buttons, text="全選択", command=lambda: self.set_all_comparison_columns(True), font=("Meiryo", 8), width=8).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(compare_buttons, text="全解除", command=lambda: self.set_all_comparison_columns(False), font=("Meiryo", 8), width=8).pack(side=tk.LEFT)
        self.compare_columns_frame = tk.Frame(compare_frame)
        self.compare_columns_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.rebuild_comparison_column_checks()

        cache_frame = ttk.LabelFrame(content, text="サムネキャッシュ", padding=8)
        cache_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.cache_button = tk.Button(cache_frame, text="サムネキャッシュ", command=self.cache_all_images, font=("Meiryo", 9), width=16)
        self.cache_button.grid(row=0, column=0, padx=4, sticky="w")
        self.cache_clear_button = tk.Button(cache_frame, text="キャッシュクリア", command=self.clear_image_cache, font=("Meiryo", 9), width=16)
        self.cache_clear_button.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Progressbar(cache_frame, variable=self.cache_progress_var, maximum=100).grid(row=0, column=2, padx=8, sticky="ew")
        tk.Label(cache_frame, textvariable=self.cache_status_var, font=("Meiryo", 9), anchor="w").grid(row=0, column=3, sticky="ew")
        cache_frame.grid_columnconfigure(2, weight=1)

        bind_settings_mousewheel(content)
        tk.Label(buttons, text="閉じると現在の比較列を画面に反映します", font=("Meiryo", 8), fg="#666666").pack(side=tk.LEFT)
        tk.Button(buttons, text="閉じる", command=lambda: self.close_settings_window(win), font=("Meiryo", 9), width=10).pack(side=tk.RIGHT)

    def build_settings_file_rows(self, file_frame):
        for child in file_frame.winfo_children():
            child.destroy()
        for row, var in enumerate(self.report_path_vars):
            self.add_file_row(file_frame, row, f"実績{row + 1}", var)
            state = tk.NORMAL if len(self.report_path_vars) > 2 else tk.DISABLED
            up_state = tk.NORMAL if row > 0 else tk.DISABLED
            down_state = tk.NORMAL if row < len(self.report_path_vars) - 1 else tk.DISABLED
            tk.Button(
                file_frame,
                text="－",
                command=lambda index=row: self.remove_report_file_row(file_frame, index),
                font=("Meiryo", 9),
                width=3,
                state=state,
            ).grid(row=row, column=3, padx=(0, 2))
            tk.Button(
                file_frame,
                text="↑",
                command=lambda index=row: self.move_report_file_row(file_frame, index, -1),
                font=("Meiryo", 9),
                width=3,
                state=up_state,
            ).grid(row=row, column=4, padx=(0, 2))
            tk.Button(
                file_frame,
                text="↓",
                command=lambda index=row: self.move_report_file_row(file_frame, index, 1),
                font=("Meiryo", 9),
                width=3,
                state=down_state,
            ).grid(row=row, column=5, padx=(0, 2))
        add_row = len(self.report_path_vars)
        tk.Button(file_frame, text="＋実績", command=lambda: self.add_report_file_row(file_frame), font=("Meiryo", 9), width=8).grid(row=add_row, column=2, padx=2, pady=(2, 4))
        base_row = add_row + 1
        self.add_file_row(file_frame, base_row, "CPC設定CSV", self.boost_path)
        self.add_file_row(file_frame, base_row + 1, "除外CSV", self.exclude_path)
        self.add_file_row(file_frame, base_row + 2, "商品CSV", self.item_csv_path)
        tk.Label(file_frame, text="店舗ID/URL", font=("Meiryo", 9), width=10, anchor="w").grid(row=base_row + 3, column=0, sticky="w", pady=2)
        tk.Entry(file_frame, textvariable=self.shop_url_var, font=("Meiryo", 9)).grid(row=base_row + 3, column=1, sticky="ew", padx=4)
        tk.Button(file_frame, text="読み込み", command=self.load_all, font=("Meiryo", 9), width=12).grid(row=base_row + 3, column=2, padx=2)
        tk.Label(file_frame, text="読込フォルダ", font=("Meiryo", 9), width=10, anchor="w").grid(row=base_row + 4, column=0, sticky="w", pady=2)
        tk.Entry(file_frame, textvariable=self.import_folder_path, font=("Meiryo", 9)).grid(row=base_row + 4, column=1, sticky="ew", padx=4)
        tk.Button(file_frame, text="参照", command=lambda: self.select_folder(self.import_folder_path), font=("Meiryo", 9), width=8).grid(row=base_row + 4, column=2, padx=2)
        tk.Button(file_frame, text="更新", command=self.update_files_from_import_folder, font=("Meiryo", 9), width=8).grid(row=base_row + 4, column=3, padx=2)
        file_frame.grid_columnconfigure(1, weight=1)

    def add_report_file_row(self, file_frame):
        self.add_report_path_var()
        self.build_settings_file_rows(file_frame)
        self.update_io_state()

    def remove_report_file_row(self, file_frame, index):
        if len(self.report_path_vars) <= 2:
            messagebox.showinfo("実績CSV", "実績CSVは2件以上必要です。")
            return
        if 0 <= index < len(self.report_path_vars):
            self.report_path_vars.pop(index)
            self.build_settings_file_rows(file_frame)
            self.save_settings()
            self.update_io_state()

    def move_report_file_row(self, file_frame, index, direction):
        target = index + direction
        if not (0 <= index < len(self.report_path_vars) and 0 <= target < len(self.report_path_vars)):
            return
        self.report_path_vars[index], self.report_path_vars[target] = self.report_path_vars[target], self.report_path_vars[index]
        self.build_settings_file_rows(file_frame)
        self.save_settings()
        self.update_io_state()

    def close_settings_window(self, win):
        self.apply_graph_column_settings(show_warning=False)
        self.compare_columns_frame = None
        self.settings_window = None
        win.destroy()
        self.work_state_combo = None

    def rebuild_comparison_column_checks(self):
        frame = self.compare_columns_frame
        if not frame:
            return
        for child in frame.winfo_children():
            child.destroy()
        previous_selected = {
            column for column, var in self.graph_column_vars.items() if var.get()
        } or set(self.graph_columns)
        self.graph_column_vars = {}
        for index, column in enumerate(self.get_graph_column_candidates()):
            var = tk.BooleanVar(value=column in previous_selected)
            self.graph_column_vars[column] = var
            tk.Checkbutton(frame, text=self.short_column_label(column), variable=var, font=("Meiryo", 8)).grid(
                row=index // 3, column=index % 3, sticky="w", padx=4, pady=1
            )
        for column in range(3):
            frame.grid_columnconfigure(column, weight=1)
        self.resize_settings_window_for_comparison_columns(len(self.graph_column_vars))

    def set_all_comparison_columns(self, selected):
        for var in self.graph_column_vars.values():
            var.set(selected)

    def resize_settings_window_for_comparison_columns(self, column_count):
        win = self.settings_window
        if not win:
            return
        rows = max(1, (column_count + 2) // 3)
        target_height = 500 + min(rows, 8) * 22
        max_height = max(620, win.winfo_screenheight() - 120)
        height = min(max(target_height, 620), max_height)
        width = 700
        win.geometry(f"{width}x{height}")

    def get_graph_column_candidates(self):
        candidates = []
        seen = set()
        for column in DEFAULT_GRAPH_COLUMNS:
            if column not in seen:
                seen.add(column)
                candidates.append(column)
        for product in self.products:
            for source in (product.reports or [product.prev, product.curr]):
                for column in source.keys():
                    if column in seen or column in NON_GRAPH_COLUMNS:
                        continue
                    if safe_number(source.get(column), None) is None:
                        continue
                    seen.add(column)
                    candidates.append(column)
        return candidates

    def normalize_graph_columns(self):
        candidates = self.get_graph_column_candidates()
        candidate_set = set(candidates)
        selected = [column for column in self.graph_columns if column in candidate_set]
        if not selected:
            selected = [column for column in DEFAULT_GRAPH_COLUMNS if column in candidate_set]
        self.graph_columns = selected or candidates

    def build_graph_metric_max_values(self):
        max_values = {}
        for column in self.get_graph_column_candidates():
            values = [
                abs(safe_number(report.get(column), 0))
                for product in self.products
                for report in (product.reports or [product.prev, product.curr])
                if safe_number(report.get(column), None) is not None
            ]
            max_values[column] = max(values + [1])
        self.graph_metric_max_values = max_values

    def operation_setting_path(self, name):
        safe_name = "".join(ch for ch in str(name or "").strip() if ch not in '\\/:*?"<>|')
        if not safe_name:
            return None
        return OPERATION_SETTINGS_DIR / f"{safe_name}.json"

    def list_operation_settings(self):
        OPERATION_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(path.stem for path in OPERATION_SETTINGS_DIR.glob("*.json"))

    def refresh_operation_setting_combo(self):
        if self.operation_setting_combo:
            self.operation_setting_combo["values"] = self.list_operation_settings()

    def current_operation_setting_data(self):
        return {
            "comparison_columns": [
                column for column, var in self.graph_column_vars.items() if var.get()
            ] or list(self.graph_columns)
        }

    def apply_operation_setting_data(self, data):
        columns = data.get("comparison_columns") or data.get("graph_columns")
        if not isinstance(columns, list) or not columns:
            return False
        self.graph_columns = [str(column) for column in columns]
        for column, var in self.graph_column_vars.items():
            var.set(column in self.graph_columns)
        product = self.current_product()
        if product:
            self.draw_graph(product)
        return True

    def load_selected_operation_setting(self):
        name = self.operation_setting_var.get()
        path = self.operation_setting_path(name)
        if not path or not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if self.apply_operation_setting_data(data):
                self.save_settings()
                self.status_var.set(f"操作設定を読み込みました: {name}")
                return True
        except Exception as e:
            messagebox.showerror("操作設定", f"設定の読み込みに失敗しました。\n{e}")
        return False

    def work_state_path(self, name):
        safe_name = "".join(ch for ch in str(name or "").strip() if ch not in '\\/:*?"<>|')
        if not safe_name:
            return None
        return WORK_STATES_DIR / f"{safe_name}.json"

    def list_work_states(self):
        WORK_STATES_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(path.stem for path in WORK_STATES_DIR.glob("*.json"))

    def refresh_work_state_combo(self):
        if self.work_state_combo:
            self.work_state_combo["values"] = self.list_work_states()

    def save_named_work_state(self, name):
        if not self.products:
            messagebox.showwarning("作業状態", "先にデータを読み込んでください。")
            return
        self.apply_current_text_edits()
        path = self.work_state_path(name)
        if not path:
            messagebox.showwarning("作業状態", "保存名を入力してください。")
            return
        WORK_STATES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.current_work_state_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.work_state_var.set(path.stem)
        self.refresh_work_state_combo()
        self.save_settings()
        self.status_var.set(f"作業状態を保存しました: {path.stem}")

    def save_current_work_state_as(self):
        name = simpledialog.askstring("作業状態", "保存名を入力してください。", parent=self.settings_window or self.root)
        if not name:
            return
        self.save_named_work_state(name.strip())

    def save_current_named_work_state(self):
        name = self.work_state_var.get().strip()
        if not name:
            self.save_current_work_state_as()
            return
        self.save_named_work_state(name)

    def load_selected_work_state(self):
        if not self.products:
            messagebox.showwarning("作業状態", "先にデータを読み込んでください。")
            return False
        name = self.work_state_var.get()
        path = self.work_state_path(name)
        if not path or not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("作業状態", f"作業状態の読み込みに失敗しました。\n{e}")
            return False
        if data.get("input_signature") != list(self.input_signature()):
            messagebox.showwarning("作業状態", "現在の入力ファイル構成と違うため読み込めません。")
            return False
        self.apply_current_text_edits()
        if self.apply_work_state_data(data, include_text=True):
            self.apply_filter()
            self.save_settings()
            self.save_work_state()
            self.status_var.set(f"作業状態を読み込みました: {path.stem}")
            return True
        messagebox.showwarning("作業状態", "読み込める作業状態がありません。")
        return False

    def delete_named_work_state(self):
        name = self.work_state_var.get()
        path = self.work_state_path(name)
        if not path or not path.exists():
            return
        if not messagebox.askyesno("作業状態", f"作業状態を削除しますか？\n{name}"):
            return
        path.unlink()
        self.work_state_var.set("")
        self.refresh_work_state_combo()
        self.save_settings()
        self.status_var.set("作業状態を削除しました")

    def save_current_operation_setting(self):
        name = self.operation_setting_var.get()
        if not name:
            self.save_operation_setting_as()
            return
        self.save_operation_setting(name)

    def save_operation_setting_as(self):
        name = simpledialog.askstring("操作設定", "設定名を入力してください。", parent=self.root)
        if not name:
            return
        self.operation_setting_var.set(name.strip())
        self.save_operation_setting(name.strip())

    def save_operation_setting(self, name):
        path = self.operation_setting_path(name)
        if not path:
            messagebox.showwarning("操作設定", "設定名を入力してください。")
            return
        OPERATION_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.current_operation_setting_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.refresh_operation_setting_combo()
        self.save_settings()
        self.status_var.set(f"操作設定を保存しました: {path.stem}")

    def delete_operation_setting(self):
        name = self.operation_setting_var.get()
        path = self.operation_setting_path(name)
        if not path or not path.exists():
            return
        if not messagebox.askyesno("操作設定", f"操作設定を削除しますか？\n{name}"):
            return
        path.unlink()
        self.operation_setting_var.set("")
        self.refresh_operation_setting_combo()
        self.save_settings()
        self.status_var.set("操作設定を削除しました")

    def short_column_label(self, column):
        return (
            column.replace("(合計720時間)", "720h")
            .replace("(合計12時間)", "12h")
            .replace("(合計)", "")
        )

    def format_metric_value(self, column, value, signed=False):
        sign = "+" if signed else ""
        if "(%)" in column or "ROAS" in column or "CTR" in column or "CVR" in column:
            return f"{value:{sign},.1f}"
        if any(keyword in column for keyword in ("金額", "実績額", "単価", "クリック数", "件数")):
            return f"{value:{sign},.0f}"
        return f"{value:{sign},.1f}"

    def apply_graph_column_settings(self, show_warning=True):
        selected = [column for column, var in self.graph_column_vars.items() if var.get()]
        if not selected:
            if show_warning:
                messagebox.showwarning("比較列", "比較列を1つ以上選択してください。")
            return
        self.graph_columns = selected
        self.save_settings()
        self.update_search_columns()
        product = self.current_product()
        if product:
            self.draw_graph(product)

    def select_file(self, var):
        path = filedialog.askopenfilename(initialdir=SCRIPT_DIR, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            var.set(path)
            self.save_settings()

    def select_folder(self, var):
        path = filedialog.askdirectory(initialdir=SCRIPT_DIR)
        if path:
            var.set(path)
            self.save_settings()

    def csv_header_text(self, path, max_lines=80):
        try:
            encoding = detect_encoding(path)
            lines = []
            with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
                for _ in range(max_lines):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
            return "\n".join(lines)
        except Exception:
            return ""

    def classify_import_csv(self, path):
        name = path.name.lower()
        generated_names = {
            "rpp_item_boost_adjusted.csv",
            "rpp_item_boost_all.csv",
            "rpp_exclude_items_adjusted.csv",
            "rpp_exclude_items_all.csv",
            "normal-item_name_catch_adjusted.csv",
        }
        if name in generated_names or "adjusted" in name:
            return None
        if name.startswith("rpp_item_reports"):
            return "report"
        if name.startswith("rpp_item_boost"):
            return "boost"
        if name.startswith("rpp_exclude_items"):
            return "exclude"
        if name.startswith("normal-item"):
            return "item"
        text = self.csv_header_text(path)
        if "商品・キーワードCPCを設定される際には" in text or ("クリック数(合計)" in text and "実績額(合計)" in text):
            return "report"
        if "商品CPC" in text:
            return "boost"
        if PRODUCT_ID_COLUMN in text and PRODUCT_NAME_COLUMN in text:
            return "item"
        if "コントロールカラム" in text and "商品管理番号" in text:
            return "exclude"
        return None

    def set_report_paths(self, paths):
        while len(self.report_path_vars) < len(paths):
            self.add_report_path_var()
        while len(self.report_path_vars) > max(2, len(paths)):
            self.report_path_vars.pop()
        for index, var in enumerate(self.report_path_vars):
            var.set(str(paths[index]) if index < len(paths) else "")

    def update_files_from_import_folder(self):
        folder_text = self.import_folder_path.get().strip()
        if not folder_text:
            messagebox.showwarning("更新", "読込フォルダを設定してください。")
            return
        folder = Path(folder_text)
        if not folder.exists() or not folder.is_dir():
            messagebox.showwarning("更新", "読込フォルダが見つかりません。")
            return
        classified = {"report": [], "boost": [], "exclude": [], "item": []}
        for path in sorted(folder.glob("*.csv")):
            kind = self.classify_import_csv(path)
            if kind in classified:
                classified[kind].append(path)
        reports = sorted(classified["report"], key=report_period_sort_key)
        if reports:
            self.set_report_paths(reports)
        if classified["boost"]:
            self.boost_path.set(str(max(classified["boost"], key=lambda p: (p.stat().st_mtime, p.name))))
        if classified["exclude"]:
            self.exclude_path.set(str(max(classified["exclude"], key=lambda p: (p.stat().st_mtime, p.name))))
        if classified["item"]:
            self.item_csv_path.set(str(max(classified["item"], key=lambda p: (p.stat().st_mtime, p.name))))
        self.save_settings()
        self.update_io_state()
        summary = [
            f"実績 {len(reports)}件",
            f"CPC {len(classified['boost'])}件",
            f"除外 {len(classified['exclude'])}件",
            f"商品 {len(classified['item'])}件",
        ]
        self.status_var.set("読込フォルダ更新: " + " / ".join(summary))
        if len(reports) < 2:
            messagebox.showwarning("更新", "実績CSVが2件未満です。\n" + "\n".join(summary))
        elif not classified["boost"] or not classified["exclude"] or not classified["item"]:
            messagebox.showinfo("更新", "一部のCSVが見つかりませんでした。\n" + "\n".join(summary))
        else:
            self.load_all()

    def load_all(self):
        if self.loading:
            messagebox.showinfo("読み込み", "読み込み中です。完了までお待ちください。")
            return
        missing = self.missing_required_inputs()
        if missing:
            messagebox.showwarning("読み込み", "未設定または存在しない項目があります。\n" + "\n".join(missing))
            self.update_io_state()
            return
        self.root.config(cursor="wait")
        self.loading = True
        self.update_io_state()
        self.status_var.set("CSVを読み込み中...")
        debug_log("load_all start")
        self.root.update_idletasks()

        paths = {
            "reports": [var.get() for var in self.report_path_vars if var.get().strip()],
            "boost": self.boost_path.get(),
            "exclude": self.exclude_path.get(),
            "item": self.item_csv_path.get(),
            "shop_url": self.shop_url_var.get(),
        }
        threading.Thread(target=self.load_all_worker, args=(paths,), daemon=True).start()
        self.root.after(100, self.poll_load_queue)

    def load_all_worker(self, paths):
        try:
            report_rows_list = []
            report_periods = []
            for index, report_path in enumerate(paths["reports"], start=1):
                debug_log(f"read report{index} start")
                path = Path(report_path)
                report_periods.append(read_report_period(path))
                rows = read_rpp_report(path)
                report_rows_list.append(rows)
                debug_log(f"read report{index} done rows={len(rows)}")
            debug_log("read boost csv start")
            boost = read_normal_csv(Path(paths["boost"])) if paths["boost"] else []
            debug_log(f"read boost csv done rows={len(boost)}")
            debug_log("read exclude csv start")
            exclude = read_normal_csv(Path(paths["exclude"])) if paths["exclude"] else []
            debug_log(f"read exclude csv done rows={len(exclude)}")
            debug_log("read item csv map start")
            item_map = read_item_csv_map(Path(paths["item"])) if paths["item"] else {}
            debug_log(f"read item csv map done rows={len(item_map)}")
            debug_log("build products start")
            products = self.build_products(report_rows_list, boost, exclude, item_map, paths["shop_url"])
            debug_log(f"build products done rows={len(products)}")
            self.load_queue.put(("done", products, report_periods))
        except Exception as e:
            logging.exception("読み込み失敗")
            debug_log(f"load_all error {e}")
            self.load_queue.put(("error", str(e)))

    def poll_load_queue(self):
        try:
            message = self.load_queue.get_nowait()
        except queue.Empty:
            if self.loading:
                self.root.after(100, self.poll_load_queue)
            return
        kind = message[0]
        self.loading = False
        self.root.config(cursor="")
        if kind == "error":
            self.status_var.set("読み込み失敗")
            self.update_io_state()
            messagebox.showerror("読み込みエラー", message[1])
            return
        self.products = message[1]
        self.build_graph_metric_max_values()
        self.loaded_input_signature = self.input_signature()
        report_periods = message[2] if len(message) > 2 else []
        if report_periods:
            labels = [f"実績{index + 1}: {period or '-'}" for index, period in enumerate(report_periods)]
            self.period_var.set("比較期間: " + " → ".join(labels))
        else:
            self.period_var.set("比較期間: -")
        self.save_settings()
        if not self.load_selected_operation_setting():
            self.normalize_graph_columns()
        self.update_search_columns()
        self.rebuild_comparison_column_checks()
        self.restore_work_state(include_text=True)
        debug_log("apply filter start")
        self.apply_filter()
        self.restore_work_state(include_text=True)
        self.refresh_tree()
        debug_log("apply filter queued")
        self.status_var.set(f"読込完了: {len(self.products)}商品")
        self.update_io_state()
        self.save_work_state()

    def load_item_info(self):
        if self.item_loading:
            messagebox.showinfo("商品情報読込", "商品情報を読み込み中です。")
            return
        if not self.products:
            messagebox.showwarning("商品情報読込", "先にRPPデータを読み込んでください。")
            return
        if not self.item_csv_path.get():
            messagebox.showwarning("商品情報読込", "商品CSVを指定してください。")
            return
        self.item_loading = True
        self.status_var.set("商品CSVを読み込み中...")
        debug_log("item info load start")
        target_codes = {p.code for p in self.products}
        path = self.item_csv_path.get()
        shop_url = self.shop_url_var.get()
        threading.Thread(target=self.load_item_info_worker, args=(path, target_codes, shop_url), daemon=True).start()
        self.root.after(100, self.poll_item_queue)

    def load_item_info_worker(self, path, target_codes, shop_url):
        try:
            debug_log("read item csv map start")
            item_map = read_item_csv_map(Path(path), target_codes=target_codes)
            debug_log(f"read item csv map done rows={len(item_map)}")
            self.item_queue.put(("done", item_map, shop_url))
        except Exception as e:
            debug_log(f"item info load error {e}")
            self.item_queue.put(("error", str(e)))

    def poll_item_queue(self):
        try:
            message = self.item_queue.get_nowait()
        except queue.Empty:
            if self.item_loading:
                self.root.after(100, self.poll_item_queue)
            return
        self.item_loading = False
        if message[0] == "error":
            self.status_var.set("商品CSV読み込み失敗")
            messagebox.showerror("商品CSV読み込みエラー", message[1])
            return
        _, item_map, shop_url = message
        updated = self.apply_item_info(item_map, shop_url)
        self.restore_work_state(include_text=True)
        self.status_var.set(f"商品情報読込完了: {updated}件")
        self.update_search_columns()
        self.apply_filter()
        self.save_work_state()

    def apply_item_info(self, item_map, shop_url):
        updated = 0
        for product in self.products:
            item = item_map.get(product.code)
            if not item:
                continue
            product.name = str(item.get(PRODUCT_NAME_COLUMN) or product.name or "")
            product.original_name = product.name
            product.catch_copy = str(item.get(CATCH_COPY_COLUMN) or "")
            product.original_catch_copy = product.catch_copy
            product.image_path = str(item.get(MAIN_IMAGE_COLUMN) or "")
            product.image_url = self.build_rakuten_image_url(product.image_path, shop_url)
            updated += 1
        return updated

    def collect_target_codes(self, report_rows_list, boost):
        codes = set()
        for rows in list(report_rows_list or []) + [boost]:
            for row in rows:
                code = str(row.get("商品管理番号", "")).strip()
                if code:
                    codes.add(code)
        return codes

    def get_item_csv_map(self, item_df):
        if not item_df:
            return {}
        result = {}
        for row in item_df:
            code = str(row.get(PRODUCT_ID_COLUMN, "")).strip()
            if code and code not in result:
                result[code] = row
        return result

    def build_rakuten_image_url(self, image_path, shop_url=None):
        path = str(image_path or "").strip()
        if not path:
            return ""
        if path.startswith(("http://", "https://")):
            return path
        shop = (shop_url if shop_url is not None else self.shop_url_var.get()).strip().strip("/")
        if "rakuten.co.jp/" in shop:
            shop = shop.split("rakuten.co.jp/", 1)[1].strip("/")
        if "/" in shop:
            shop = shop.split("/", 1)[0]
        if not shop:
            return ""
        if path.startswith("cabinet/"):
            return f"https://image.rakuten.co.jp/{shop}/{path}"
        return f"https://image.rakuten.co.jp/{shop}/cabinet/{path}"

    def build_products(self, report_rows_list, boost, exclude, item_map, shop_url=""):
        report_maps = [
            {str(row.get("商品管理番号", "")).strip(): row for row in rows if str(row.get("商品管理番号", "")).strip()}
            for rows in report_rows_list
        ]
        prev_map = report_maps[0] if report_maps else {}
        curr_map = report_maps[-1] if report_maps else {}
        boost_map = {str(row.get("商品管理番号", "")).strip(): row for row in boost if str(row.get("商品管理番号", "")).strip()}
        excluded_codes = {str(row.get("商品管理番号", "")).strip() for row in exclude if str(row.get("商品管理番号", "")).strip()}
        item_codes = set(item_map)
        if item_codes:
            codes = sorted(item_codes)
        else:
            codes = sorted(set().union(*[set(report_map) for report_map in report_maps], set(boost_map)))
        products = []
        for code in codes:
            b = boost_map.get(code, {})
            item = item_map.get(code, {})
            c = curr_map.get(code, {})
            p = prev_map.get(code, {})
            reports = [report_map.get(code, {}) for report_map in report_maps]
            cpc_text = str(b.get("商品CPC") or "").strip()
            current_cpc = int(safe_number(cpc_text, 0)) if cpc_text else None
            image_path = str(item.get(MAIN_IMAGE_COLUMN, "") or "")
            cpc_original_enabled = current_cpc is not None
            original_excluded = code in excluded_codes or str(b.get("除外登録済み商品", "")).lower() == "yes"
            products.append(ProductState(
                code=code,
                name=str(item.get(PRODUCT_NAME_COLUMN) or b.get("商品名") or ""),
                original_name=str(item.get(PRODUCT_NAME_COLUMN) or b.get("商品名") or ""),
                url=str(b.get("商品URL") or c.get("商品ページURL") or p.get("商品ページURL") or ""),
                price=str(b.get("価格") or ""),
                catch_copy=str(item.get(CATCH_COPY_COLUMN) or ""),
                original_catch_copy=str(item.get(CATCH_COPY_COLUMN) or ""),
                image_path=image_path,
                image_url=self.build_rakuten_image_url(image_path, shop_url),
                current_cpc=current_cpc,
                cpc_original_enabled=cpc_original_enabled,
                cpc_enabled=cpc_original_enabled,
                original_excluded=original_excluded,
                excluded=original_excluded,
                already_excluded=str(b.get("除外登録済み商品") or "No"),
                prev=p,
                curr=c,
                reports=reports,
            ))
        products.sort(key=lambda item: safe_number(item.curr.get("実績額(合計)", 0), 0), reverse=True)
        return products

    def update_search_columns(self):
        fixed = ["商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "CPC状態", "除外", "重点", "選択"]
        values = fixed + [col for col in self.graph_columns if col not in fixed]
        if hasattr(self, "search_column_combo"):
            self.search_column_combo["values"] = values
        if self.search_column_var.get() not in values:
            self.search_column_var.set("商品名")
        self.update_search_input_ui()

    def search_column_type(self, column):
        if column in ("除外", "重点", "選択"):
            return "choice"
        if column == "CPC状態":
            return "choice"
        if column in ("現CPC", "新CPC"):
            return "number"
        source = self.search_source_var.get()
        if source == "差":
            return "number"
        for product in self.products[:20]:
            for row in (product.reports or [product.prev, product.curr]):
                if column in row and safe_number(row.get(column), None) is not None:
                    return "number"
        return "text"

    def search_choice_values(self, column):
        if column == "除外":
            return ("除外ON", "除外OFF", "新規除外", "解除予定")
        if column == "選択":
            return ("選択ON", "選択OFF")
        if column == "重点":
            return ("重点ON", "重点OFF")
        if column == "CPC状態":
            return ("新規", "変更", "削除", "登録済", "未登録")
        return ("ON", "OFF")

    def update_search_input_ui(self):
        if not hasattr(self, "search_input_frame"):
            return
        for child in self.search_input_frame.winfo_children():
            child.destroy()
        column = self.search_column_var.get() or "商品名"
        column_type = self.search_column_type(column)
        if column in ("商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "CPC状態", "除外", "重点", "選択"):
            self.search_source_combo.config(state=tk.DISABLED)
        else:
            self.search_source_combo.config(state=tk.NORMAL)
        if column_type == "choice":
            values = self.search_choice_values(column)
            if self.search_choice_var.get() not in values:
                self.search_choice_var.set(values[0])
            ttk.Combobox(self.search_input_frame, textvariable=self.search_choice_var, font=("Meiryo", 9), width=12, state="readonly", values=values).pack(side=tk.LEFT, padx=4)
        elif column_type == "number":
            entry = tk.Entry(self.search_input_frame, textvariable=self.numeric_search_var, font=("Meiryo", 9), width=10)
            entry.pack(side=tk.LEFT, padx=(4, 4))
            entry.bind("<Return>", lambda _event: self.run_search())
            ttk.Combobox(self.search_input_frame, textvariable=self.numeric_operator_var, font=("Meiryo", 9), width=6, state="readonly", values=("以下", "以上", "未満", "より大", "等しい")).pack(side=tk.LEFT)
        else:
            entry = tk.Entry(self.search_input_frame, textvariable=self.search_var, font=("Meiryo", 9), width=22)
            entry.pack(side=tk.LEFT, padx=4)
            entry.bind("<Return>", lambda _event: self.run_search())

    def search_condition_column(self):
        column = self.search_column_var.get() or "商品名"
        if column in ("商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "CPC状態", "除外", "重点", "選択"):
            return column
        return f"{self.search_source_var.get()}:{column}"

    def run_search(self):
        column = self.search_condition_column()
        column_type = self.search_column_type(self.search_column_var.get() or "商品名")
        if column_type == "choice":
            value = self.search_choice_var.get()
            if not value:
                return
            self.filter_conditions.append(("choice", column, "=", value))
        elif column_type == "number":
            value_text = self.numeric_search_var.get().strip()
            if not value_text:
                return
            value = safe_number(value_text, None)
            if value is None:
                messagebox.showwarning("検索", "数値検索には数値を入力してください。")
                return
            self.filter_conditions.append(("numeric", column, self.numeric_operator_var.get(), value))
        else:
            value = self.search_var.get().strip()
            if not value:
                return
            self.filter_conditions.append(("text", column, "含む", value))
        self.update_condition_history()
        self.apply_filter()

    def clear_search_filters(self):
        self.search_var.set("")
        self.numeric_search_var.set("")
        self.search_choice_var.set("")
        self.active_text_filter = None
        self.active_numeric_filter = None
        self.filter_conditions.clear()
        self.update_condition_history()
        self.apply_filter()

    def update_condition_history(self):
        if not hasattr(self, "condition_listbox"):
            return
        self.condition_listbox.delete(0, tk.END)
        for condition in self.filter_conditions:
            self.condition_listbox.insert(tk.END, self.condition_to_text(condition))

    def condition_to_text(self, condition):
        kind, column, operator, value = condition
        if kind == "text":
            return f"{column}：{value}"
        if kind == "choice":
            return f"{column}：{value}"
        return f"{column}：{value:g}{operator}"

    def undo_last_condition(self):
        if self.filter_conditions:
            self.filter_conditions.pop()
            self.update_condition_history()
            self.apply_filter()

    def reset_conditions_and_selection(self):
        self.search_var.set("")
        self.numeric_search_var.set("")
        self.show_changed_only.set(False)
        self.show_excluded_only.set(False)
        self.filter_conditions.clear()
        self.update_condition_history()
        self.clear_product_selection()
        self.apply_filter()

    def product_column_value(self, product, column, product_index=None):
        if column == "商品名":
            return product.name
        if column == "商品管理番号":
            return product.code
        if column == "キャッチコピー":
            return product.catch_copy
        if column == "現CPC":
            return product.current_cpc if product.current_cpc is not None else ""
        if column == "新CPC":
            return product.output_cpc if product.output_cpc is not None else ""
        if column == "CPC状態":
            return product.cpc_status or ("登録済" if product.cpc_enabled else "未登録")
        if column == "除外":
            return product.exclude_status or ("除外ON" if product.excluded else "除外OFF")
        if column == "重点":
            return "重点ON" if product.priority else "重点OFF"
        if column == "選択":
            return "選択ON" if product_index in self.selected_product_indices else "選択OFF"
        if column.startswith("元:"):
            return product.prev.get(column[2:], "")
        if column.startswith("先:"):
            return product.curr.get(column[2:], "")
        if column.startswith("差:"):
            key = column[2:]
            return safe_number(product.curr.get(key, 0)) - safe_number(product.prev.get(key, 0))
        return product.curr.get(column, product.prev.get(column, ""))

    def matches_numeric_filter(self, value, operator, target):
        number = safe_number(value, None)
        if number is None:
            return False
        if operator == "以下":
            return number <= target
        if operator == "以上":
            return number >= target
        if operator == "未満":
            return number < target
        if operator == "より大":
            return number > target
        return number == target

    def apply_filter(self):
        self.filtered_indices = []
        for i, product in enumerate(self.products):
            condition_matched = True
            for kind, column, operator, target in self.filter_conditions:
                value = self.product_column_value(product, column, i)
                if kind == "text":
                    if str(target).lower() not in str(value or "").lower():
                        condition_matched = False
                        break
                elif kind == "choice":
                    if str(value) != str(target):
                        condition_matched = False
                        break
                elif not self.matches_numeric_filter(value, operator, target):
                    condition_matched = False
                    break
            if not condition_matched:
                continue
            if self.show_changed_only.get() and not product.cpc_changed:
                continue
            if self.show_excluded_only.get() and not product.excluded:
                continue
            self.filtered_indices.append(i)
        if self.sort_column:
            self.filtered_indices.sort(
                key=lambda product_index: self.tree_sort_value(self.products[product_index], self.sort_column),
                reverse=self.sort_reverse,
            )
        self.refresh_tree()
        if self.filtered_indices:
            self.current_index = min(self.current_index, len(self.filtered_indices) - 1)
        else:
            self.position_var.set("0/0")

    def refresh_tree(self):
        if self.tree_render_after_id:
            self.root.after_cancel(self.tree_render_after_id)
            self.tree_render_after_id = None
        self.tree.delete(*self.tree.get_children())
        self.status_var.set(f"一覧表示中... 0/{len(self.filtered_indices)}")
        self.render_tree_batch(0)

    def sort_tree_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.filtered_indices.sort(
            key=lambda product_index: self.tree_sort_value(self.products[product_index], column),
            reverse=self.sort_reverse,
        )
        self.current_index = 0
        self.refresh_tree()
        self.schedule_work_state_save()

    def tree_sort_value(self, product, column):
        if column == "code":
            return product.code.lower()
        if column == "name":
            return product.name.lower()
        if column == "priority":
            return 1 if product.priority else 0
        if column == "cpc":
            return product.current_cpc if product.current_cpc is not None else -1
        if column == "new_cpc":
            return product.output_cpc if product.output_cpc is not None else -1
        if column == "exclude":
            return 1 if product.excluded else 0
        if column == "click_diff":
            return safe_number(product.curr.get("クリック数(合計)", 0)) - safe_number(product.prev.get("クリック数(合計)", 0))
        if column == "cost_total":
            return self.total_report_value(product, "実績額(合計)")
        if column == "cost_diff":
            return safe_number(product.curr.get("実績額(合計)", 0)) - safe_number(product.prev.get("実績額(合計)", 0))
        if column == "sales_diff":
            return safe_number(product.curr.get("売上金額(合計720時間)", 0)) - safe_number(product.prev.get("売上金額(合計720時間)", 0))
        if column == "roas_curr":
            return safe_number(product.curr.get("ROAS(合計720時間)(%)", 0))
        return ""

    def total_report_value(self, product, column):
        reports = product.reports or [product.prev, product.curr]
        return sum(safe_number(report.get(column, 0)) for report in reports)

    def render_tree_batch(self, start):
        batch_size = 200
        end = min(start + batch_size, len(self.filtered_indices))
        for pos in range(start, end):
            product_index = self.filtered_indices[pos]
            p = self.products[product_index]
            self.tree.insert("", tk.END, iid=str(pos), values=(
                p.code,
                p.name[:80],
                "★" if p.priority else "",
                "" if p.current_cpc is None else p.current_cpc,
                self.format_cpc_status(p),
                p.exclude_status or ("除外ON" if p.excluded else ""),
                self.diff_value(p, "クリック数(合計)", integer=True) if self.has_report_data(p) else "",
                f'{self.total_report_value(p, "実績額(合計)"):,.0f}' if self.has_report_data(p) else "",
                self.diff_value(p, "実績額(合計)", integer=True) if self.has_report_data(p) else "",
                self.diff_value(p, "売上金額(合計720時間)", integer=True) if self.has_report_data(p) else "",
                f'{safe_number(p.curr.get("ROAS(合計720時間)(%)", 0)):.1f}' if p.curr else "",
            ))
        if end < len(self.filtered_indices):
            self.status_var.set(f"一覧表示中... {end}/{len(self.filtered_indices)}")
            self.tree_render_after_id = self.root.after(1, lambda: self.render_tree_batch(end))
            return
        self.tree_render_after_id = None
        self.status_var.set(f"一覧表示完了: {len(self.filtered_indices)}件")
        if self.filtered_indices:
            debug_log("tree render done; queue show product")
            self.restore_tree_selection()
            self.root.after(1, lambda: self.show_product(min(self.current_index, len(self.filtered_indices) - 1)))
        self.update_selection_count()

    def diff_value(self, product, col, integer=False):
        diff = safe_number(product.curr.get(col, 0)) - safe_number(product.prev.get(col, 0))
        return f"{diff:+.0f}" if integer else f"{diff:+.1f}"

    def has_report_data(self, product):
        return any(bool(report) for report in (product.reports or [product.prev, product.curr]))

    def format_cpc_status(self, product):
        if product.cpc_control == "d":
            return "削除"
        if product.cpc_status:
            cpc = "" if product.output_cpc is None else product.output_cpc
            return f"{cpc} {product.cpc_status}".strip()
        if product.cpc_enabled:
            return "" if product.output_cpc is None else str(product.output_cpc)
        return "未設定"

    def on_tree_select(self, _event=None):
        if self.updating_tree_selection or self.ignore_tree_select:
            return
        selection = self.tree.selection()
        self.selected_product_indices = {
            self.filtered_indices[int(item_id)]
            for item_id in selection
            if str(item_id).isdigit() and int(item_id) < len(self.filtered_indices)
        }
        self.update_selection_count()
        self.schedule_work_state_save()
        if not selection:
            return
        focus = self.tree.focus()
        selected_index = int(focus if focus in selection else selection[0])
        if selected_index == self.current_index:
            return
        self.apply_current_text_edits()
        self.show_product(selected_index)

    def restore_tree_selection(self):
        if not self.selected_product_indices:
            return
        visible_items = [
            str(pos)
            for pos, product_index in enumerate(self.filtered_indices)
            if product_index in self.selected_product_indices and self.tree.exists(str(pos))
        ]
        if not visible_items:
            return
        self.updating_tree_selection = True
        self.ignore_tree_select = True
        try:
            self.tree.selection_set(visible_items)
        finally:
            self.updating_tree_selection = False
            self.root.after(50, lambda: setattr(self, "ignore_tree_select", False))

    def update_selection_count(self):
        visible_selected = sum(1 for index in self.filtered_indices if index in self.selected_product_indices)
        self.selection_count_var.set(f"選択 {visible_selected}/{len(self.selected_product_indices)}件")

    def select_visible_products(self):
        self.selected_product_indices.update(self.filtered_indices)
        self.restore_tree_selection()
        self.update_selection_count()
        self.schedule_work_state_save()

    def clear_product_selection(self):
        self.selected_product_indices.clear()
        self.tree.selection_remove(self.tree.selection())
        self.update_selection_count()
        self.schedule_work_state_save()

    def invert_visible_selection(self):
        visible = set(self.filtered_indices)
        self.selected_product_indices = (self.selected_product_indices - visible) | (visible - self.selected_product_indices)
        self.tree.selection_remove(self.tree.selection())
        self.restore_tree_selection()
        self.update_selection_count()
        self.schedule_work_state_save()

    def selected_products(self):
        return [
            self.products[index]
            for index in sorted(self.selected_product_indices)
            if 0 <= index < len(self.products)
        ]

    def require_selected_products(self):
        products = self.selected_products()
        if not products:
            messagebox.showwarning("一括操作", "対象商品を選択してください。")
            return []
        return products

    def apply_bulk_cpc(self):
        products = self.require_selected_products()
        if not products:
            return
        try:
            value = int(safe_number(self.bulk_cpc_var.get(), None))
        except Exception:
            messagebox.showwarning("一括操作", "CPCは数値で入力してください。")
            return
        if value < 0:
            value = CPC_MIN_VALUE
        value = max(CPC_MIN_VALUE, value)
        for product in products:
            product.cpc_enabled = True
            product.new_cpc = value if value != product.current_cpc else None
        self.status_var.set(f"CPCを一括適用しました: {len(products)}件")
        self.refresh_tree()
        self.schedule_work_state_save()

    def delete_bulk_cpc(self):
        products = self.require_selected_products()
        if not products:
            return
        changed = 0
        for product in products:
            if product.cpc_original_enabled:
                product.cpc_enabled = False
                product.new_cpc = None
                changed += 1
            else:
                product.cpc_enabled = False
                product.new_cpc = None
        self.status_var.set(f"CPC削除対象: {changed}件")
        self.refresh_tree()
        self.schedule_work_state_save()

    def set_bulk_excluded(self, excluded):
        products = self.require_selected_products()
        if not products:
            return
        for product in products:
            product.excluded = excluded
        self.status_var.set(f"除外 {'ON' if excluded else 'OFF'}: {len(products)}件")
        self.refresh_tree()
        self.schedule_work_state_save()

    def set_bulk_priority(self, priority):
        products = self.require_selected_products()
        if not products:
            return
        for product in products:
            product.priority = priority
        self.status_var.set(f"重点 {'ON' if priority else 'OFF'}: {len(products)}件")
        self.refresh_tree()
        product = self.current_product()
        if product:
            self.update_priority_button(product)
        self.schedule_work_state_save()

    def show_product(self, filtered_pos):
        if not self.filtered_indices:
            return
        debug_log(f"show_product start {filtered_pos}")
        self.current_index = max(0, min(filtered_pos, len(self.filtered_indices) - 1))
        product = self.products[self.filtered_indices[self.current_index]]
        self.position_var.set(f"{self.current_index + 1}/{len(self.filtered_indices)}")
        item_id = str(self.current_index)
        if self.tree.exists(item_id):
            self.updating_tree_selection = True
            self.ignore_tree_select = True
            try:
                self.tree.focus(item_id)
                self.tree.see(item_id)
            finally:
                self.updating_tree_selection = False
                self.root.after(50, lambda: setattr(self, "ignore_tree_select", False))
        if self.detail_window and self.detail_window.winfo_exists():
            self.code_var.set(product.code)
            self.name_var.set(product.name or "(商品名なし)")
            self.catch_var.set(product.catch_copy)
            self.url_var.set(product.url)
            self.cpc_var.set("" if product.output_cpc is None else str(product.output_cpc))
            self.exclude_var.set(product.excluded)
            self.update_cpc_toggle_button(product)
            self.update_exclude_toggle_button(product)
            self.update_priority_button(product)
            self.update_image_selection_frame(product)
            self.draw_graph(product)
            self.show_cached_or_fetch_image(product)
        debug_log(f"show_product done {filtered_pos}")

    def apply_current_text_edits(self):
        if not self.filtered_indices:
            return
        if not hasattr(self, "code_var"):
            return
        product = self.products[self.filtered_indices[self.current_index]]
        if self.code_var.get() and self.code_var.get() != product.code:
            return
        product.name = self.name_var.get()
        product.catch_copy = self.catch_var.get()
        self.schedule_work_state_save()

    def current_product(self):
        if not self.filtered_indices:
            return None
        return self.products[self.filtered_indices[self.current_index]]

    def next_product(self):
        if self.filtered_indices:
            self.apply_current_text_edits()
            if self.current_index >= len(self.filtered_indices) - 1:
                self.status_var.set("最後の商品です")
                return "break"
            self.show_product(self.current_index + 1)
        return "break"

    def prev_product(self):
        if self.filtered_indices:
            self.apply_current_text_edits()
            if self.current_index <= 0:
                self.status_var.set("最初の商品です")
                return "break"
            self.show_product(self.current_index - 1)
        return "break"

    def on_image_wheel(self, event):
        if event.delta > 0:
            return self.prev_product()
        return self.next_product()

    def toggle_image_click_mode(self):
        current = self.image_click_mode_var.get()
        self.image_click_mode_var.set("exclude" if current == "select" else "select")
        self.update_image_click_mode_button()

    def update_image_click_mode_button(self):
        if not hasattr(self, "image_click_mode_button"):
            return
        if self.image_click_mode_var.get() == "exclude":
            self.image_click_mode_button.config(text="商品除外", bg="#ffd6d6", activebackground="#ffd6d6")
        else:
            self.image_click_mode_button.config(text="商品選択", bg="#d8e8ff", activebackground="#d8e8ff")

    def toggle_priority(self):
        product = self.current_product()
        if not product:
            return "break"
        product.priority = not product.priority
        self.update_priority_button(product)
        self.refresh_tree()
        self.schedule_work_state_save()
        return "break"

    def update_priority_button(self, product):
        if not hasattr(self, "priority_button") or not self.priority_button:
            return
        text = "重点 ON" if product.priority else "重点 OFF"
        bg = "#fff0a8" if product.priority else "#eeeeee"
        relief = tk.SUNKEN if product.priority else tk.RAISED
        self.priority_button.config(text=text, bg=bg, activebackground=bg, relief=relief)

    def on_image_click(self, _event=None):
        if self.image_click_mode_var.get() == "exclude":
            self.toggle_exclude()
            return "break"
        product = self.current_product()
        if not product:
            return "break"
        product_index = self.filtered_indices[self.current_index]
        if product_index in self.selected_product_indices:
            self.selected_product_indices.remove(product_index)
        else:
            self.selected_product_indices.add(product_index)
        self.updating_tree_selection = True
        self.ignore_tree_select = True
        try:
            self.tree.selection_remove(self.tree.selection())
        finally:
            self.updating_tree_selection = False
        self.restore_tree_selection()
        self.update_selection_count()
        self.update_image_selection_frame(product)
        self.schedule_work_state_save()
        return "break"

    def adjust_cpc(self, delta):
        value = int(safe_number(self.cpc_var.get(), 0)) + delta
        self.cpc_var.set(str(max(CPC_MIN_VALUE, value)))
        self.apply_cpc(silent=True)

    def apply_cpc(self, silent=False):
        product = self.current_product()
        if not product:
            return
        try:
            text = self.cpc_var.get().strip()
            if not text:
                if not silent:
                    messagebox.showwarning("入力エラー", "CPCを入力してください。")
                return
            value = int(safe_number(text, product.current_cpc if product.current_cpc is not None else 0))
        except Exception:
            if not silent:
                messagebox.showwarning("入力エラー", "CPCは数値で入力してください。")
            return
        value = max(CPC_MIN_VALUE, value)
        self.cpc_var.set(str(value))
        product.cpc_enabled = True
        product.new_cpc = value if value != product.current_cpc else None
        self.update_cpc_toggle_button(product)
        self.refresh_tree()
        self.schedule_work_state_save()

    def delete_cpc(self):
        product = self.current_product()
        if not product:
            return
        product.cpc_enabled = False
        product.new_cpc = None
        self.cpc_var.set("" if product.current_cpc is None else str(product.current_cpc))
        self.update_cpc_toggle_button(product)
        self.refresh_tree()
        self.schedule_work_state_save()

    def update_cpc_toggle_button(self, product):
        if not hasattr(self, "cpc_status_var"):
            return
        self.cpc_status_var.set(product.cpc_status or ("登録済" if product.cpc_enabled else "未登録"))

    def apply_exclude(self):
        product = self.current_product()
        if product:
            product.excluded = self.exclude_var.get()
            self.update_exclude_toggle_button(product)
            self.refresh_tree()
            self.schedule_work_state_save()

    def toggle_exclude(self):
        product = self.current_product()
        if not product:
            return
        product.excluded = not product.excluded
        self.exclude_var.set(product.excluded)
        self.update_exclude_toggle_button(product)
        self.refresh_tree()
        self.schedule_work_state_save()

    def update_exclude_toggle_button(self, product):
        if not hasattr(self, "exclude_button") or not self.exclude_button:
            return
        text = "除外 ON" if product.excluded else "除外 OFF"
        bg = "#ffd6d6" if product.excluded else "#eeeeee"
        relief = tk.SUNKEN if product.excluded else tk.RAISED
        self.exclude_button.config(text=text, bg=bg, activebackground=bg, relief=relief)

    def update_image_selection_frame(self, product):
        if not self.image_canvas:
            return
        try:
            product_index = self.products.index(product)
        except ValueError:
            product_index = None
        selected = product_index in self.selected_product_indices if product_index is not None else False
        color = "#4bd66a" if selected else "#f0f0f0"
        self.image_canvas.config(highlightbackground=color, highlightcolor=color, highlightthickness=3)

    def selected_comparison_columns(self):
        return [col for col in self.graph_columns if col and col not in NON_GRAPH_COLUMNS]

    def update_metrics(self, product):
        if not self.metrics_text:
            return
        lines = []
        reports = product.reports or [product.prev, product.curr]
        for col in self.selected_comparison_columns():
            if not any(col in report for report in reports):
                continue
            title = self.short_column_label(col)
            values = [safe_number(report.get(col, 0)) for report in reports]
            if not values:
                continue
            flow = " → ".join(self.format_metric_value(col, value) for value in values)
            diff = values[-1] - values[0] if len(values) >= 2 else 0
            lines.append(f"{title:<10} {flow} / 差 {self.format_metric_value(col, diff, signed=True)}")
        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete("1.0", tk.END)
        self.metrics_text.insert(tk.END, "\n".join(lines))
        self.metrics_text.config(state=tk.DISABLED)

    def draw_graph(self, product):
        if not self.graph or not self.graph_inner:
            return
        for child in self.graph_inner.winfo_children():
            child.destroy()
        width = max(360, self.graph.winfo_width())
        reports = product.reports or [product.prev, product.curr]
        metrics = [
            (self.short_column_label(col), col)
            for col in self.selected_comparison_columns()
            if any(safe_number(report.get(col), None) is not None for report in reports)
        ]
        if not metrics:
            tk.Label(self.graph_inner, text="グラフ対象の数値項目がありません", bg="white", font=("Meiryo", 9)).pack(anchor="w", padx=8, pady=8)
            return
        colors = ["#9ecae1", "#fdae6b", "#bcbddc", "#74c476", "#fb6a4a", "#6baed6", "#969696"]
        for label, col in metrics:
            values = [safe_number(report.get(col, 0)) for report in reports]
            metric_max = self.graph_metric_max_values.get(col) or max([abs(value) for value in values] + [1])
            row = tk.Frame(self.graph_inner, bg="white")
            row.pack(fill=tk.X, padx=6, pady=3)
            tk.Label(row, text=label, bg="white", font=("Meiryo", 9), width=18, anchor="w").pack(side=tk.LEFT)
            bar_height = max(34, 8 + len(values) * 14)
            canvas_width = max(260, width - 180)
            bar = tk.Canvas(row, bg="white", height=bar_height, width=canvas_width, highlightthickness=0)
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
            label_width = 22
            value_width = min(300, max(170, canvas_width // 2))
            bar_width = max(1, int(canvas_width - label_width - value_width - 12))
            for index, value in enumerate(values):
                y = 5 + index * 14
                bar_w = int((abs(value) / metric_max) * bar_width)
                bar.create_text(4, y + 4, text=f"{index + 1}", anchor="w", font=("Meiryo", 8), fill="#333333")
                bar.create_rectangle(label_width, y, label_width + bar_w, y + 9, fill=colors[index % len(colors)], outline="")
            diff = values[-1] - values[0] if len(values) >= 2 else 0
            flow = " → ".join(self.format_metric_value(col, value) for value in values)
            diff_text = self.format_metric_value(col, diff, signed=True)
            bar.create_text(label_width + bar_width + 8, bar_height // 2, text=f"{flow} / 差 {diff_text}", anchor="w", font=("Meiryo", 8))
        legend = tk.Frame(self.graph_inner, bg="white")
        legend.pack(anchor="w", padx=8, pady=6)
        for index in range(len(reports)):
            tk.Label(
                legend,
                text=f"■ 実績{index + 1}",
                fg=colors[index % len(colors)],
                bg="white",
                font=("Meiryo", 8),
            ).pack(side=tk.LEFT, padx=(0, 12))
        self.graph.configure(scrollregion=self.graph.bbox("all"))
        self.bind_graph_wheel_recursive(self.graph_inner)

    def on_graph_configure(self, event):
        if not self.graph or not self.graph_inner or self.graph_window is None:
            return
        self.graph.itemconfigure(self.graph_window, width=event.width)
        self.graph.configure(scrollregion=self.graph.bbox("all"))
        if self.graph_resize_after_id:
            self.root.after_cancel(self.graph_resize_after_id)
        self.graph_resize_after_id = self.root.after(120, self.redraw_current_graph)

    def redraw_current_graph(self):
        self.graph_resize_after_id = None
        product = self.current_product()
        if product and self.detail_window and self.detail_window.winfo_exists():
            self.draw_graph(product)

    def on_graph_wheel(self, event):
        if self.graph:
            self.graph.yview_scroll(-1 * int(event.delta / 120), "units")
        return "break"

    def bind_graph_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self.on_graph_wheel)
        for child in widget.winfo_children():
            self.bind_graph_wheel_recursive(child)

    def image_cache_path(self, image_url):
        key = hashlib.md5(image_url.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{key}.jpg"

    def show_cached_image_or_placeholder(self, product):
        if not self.image_canvas:
            return
        self.image_canvas.delete("all")
        if not product.image_url:
            self.image_canvas.create_text(90, 90, text="画像なし", font=("Meiryo", 9), fill="#666666")
            return
        self.image_canvas.create_text(90, 90, text="未読込", font=("Meiryo", 9), fill="#666666")

    def load_current_image(self):
        product = self.current_product()
        if not product:
            return
        self.show_cached_or_fetch_image(product)

    def show_cached_or_fetch_image(self, product):
        if not self.image_canvas:
            return
        self.image_canvas.delete("all")
        if not product.image_url:
            self.image_canvas.create_text(90, 90, text="画像なし", font=("Meiryo", 9), fill="#666666")
            return
        if self.display_cached_image(product.image_url):
            return
        self.image_canvas.create_text(90, 90, text="画像読込中", font=("Meiryo", 9), fill="#666666")
        threading.Thread(target=self.fetch_image_worker, args=(product.code, product.image_url), daemon=True).start()
        self.root.after(100, self.poll_image_queue)

    def fetch_image_worker(self, code, image_url):
        try:
            cache_path = self.image_cache_path(image_url)
            if not cache_path.exists():
                img_response = requests.get(image_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                img_response.raise_for_status()
                img = Image.open(BytesIO(img_response.content))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                img.save(cache_path, "JPEG")
            self.save_image_cache_map()
            self.image_queue.put((code, image_url))
        except Exception as e:
            logging.info("画像取得失敗: %s %s", image_url, e)
            self.image_queue.put((code, None))

    def cache_all_images(self):
        if self.image_cache_running:
            messagebox.showinfo("画像キャッシュ", "画像キャッシュを実行中です。")
            return
        if self.products and not any(p.image_url for p in self.products) and self.item_csv_path.get():
            messagebox.showinfo("画像キャッシュ", "商品CSVの画像情報を読み込みます。完了後にもう一度押してください。")
            self.load_item_info()
            return
        urls = [(p.code, p.image_url) for p in self.products if p.image_url]
        if not urls:
            messagebox.showinfo("画像キャッシュ", "キャッシュ対象の画像がありません。")
            return
        self.image_cache_running = True
        self.cache_progress_var.set(0)
        self.cache_status_var.set(f"キャッシュ中 0/{len(urls)}")
        self.update_cache_controls()
        self.status_var.set(f"サムネキャッシュ中... 0/{len(urls)}")
        self.root.update_idletasks()

        def worker():
            failed = 0
            for idx, (code, image_url) in enumerate(urls, 1):
                try:
                    cache_path = self.image_cache_path(image_url)
                    if not cache_path.exists():
                        img_response = requests.get(image_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                        img_response.raise_for_status()
                        img = Image.open(BytesIO(img_response.content))
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")
                        CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        img.save(cache_path, "JPEG")
                except Exception:
                    failed += 1
                self.image_queue.put(("__cache_progress__", idx, len(urls), failed))
            self.image_queue.put(("__cache_done__", len(urls), failed))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self.poll_image_queue)

    def update_cache_controls(self):
        state = tk.DISABLED if self.image_cache_running else tk.NORMAL
        for button in (self.cache_button, self.cache_clear_button):
            if not button:
                continue
            try:
                button.config(state=state)
            except tk.TclError:
                pass

    def clear_image_cache(self):
        if self.image_cache_running:
            return
        if not messagebox.askyesno("キャッシュクリア", "サムネキャッシュを削除します。CSVデータは変更されません。"):
            return
        try:
            if CACHE_DIR.exists():
                shutil.rmtree(CACHE_DIR)
            if CACHE_MAP_PATH.exists():
                CACHE_MAP_PATH.unlink()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self.image_cache_map = {}
            self.save_image_cache_map()
            self.cache_progress_var.set(0)
            self.cache_status_var.set("クリアしました")
            self.status_var.set("サムネキャッシュをクリアしました")
            product = self.current_product()
            if product:
                self.show_cached_or_fetch_image(product)
        except Exception as e:
            messagebox.showerror("キャッシュクリア", f"キャッシュの削除に失敗しました。\n{e}")

    def poll_image_queue(self):
        try:
            message = self.image_queue.get_nowait()
        except queue.Empty:
            if self.image_cache_running:
                self.root.after(100, self.poll_image_queue)
            return
        if message[0] == "__cache_progress__":
            _, idx, total, failed = message
            progress = (idx / total * 100) if total else 0
            self.cache_progress_var.set(progress)
            self.cache_status_var.set(f"キャッシュ中 {idx}/{total} 失敗:{failed}")
            self.status_var.set(f"サムネキャッシュ中... {idx}/{total} 失敗:{failed}")
            self.root.after(50, self.poll_image_queue)
            return
        if message[0] == "__cache_done__":
            _, total, failed = message
            self.image_cache_running = False
            self.cache_progress_var.set(100)
            self.cache_status_var.set(f"完了 {total}件 / 失敗:{failed}")
            self.update_cache_controls()
            self.status_var.set(f"サムネキャッシュ完了: {total}件 / 失敗:{failed}")
            product = self.current_product()
            if product:
                self.show_cached_or_fetch_image(product)
            return
        code, image_url = message
        product = self.current_product()
        if not product or product.code != code:
            if self.image_cache_running or not self.image_queue.empty():
                self.root.after(50, self.poll_image_queue)
            return
        if not self.image_canvas:
            if self.image_cache_running or not self.image_queue.empty():
                self.root.after(50, self.poll_image_queue)
            return
        if not image_url or not self.display_cached_image(image_url):
            self.image_canvas.delete("all")
            self.image_canvas.create_text(90, 90, text="画像なし", font=("Meiryo", 9), fill="#666666")
        if self.image_cache_running or not self.image_queue.empty():
            self.root.after(50, self.poll_image_queue)

    def display_cached_image(self, image_url):
        if not self.image_canvas:
            return False
        path = self.image_cache_path(image_url)
        if not path.exists():
            return False
        try:
            img = Image.open(path)
            img.thumbnail((180, 180))
            self.image_photo = ImageTk.PhotoImage(img)
            self.image_canvas.delete("all")
            x = (180 - img.width) // 2
            y = (180 - img.height) // 2
            self.image_canvas.create_image(x, y, image=self.image_photo, anchor="nw")
            return True
        except Exception:
            return False

    def export_cpc_csv(self):
        output_all = self.output_all_var.get()
        targets = [
            p for p in self.products
            if (p.cpc_enabled if output_all else p.cpc_changed) and p.output_cpc is not None
        ]
        if not targets:
            message = "CPC登録中の商品がありません。" if output_all else "CPC変更対象がありません。"
            messagebox.showinfo("出力", message)
            return
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            initialfile="rpp_item_boost_all.csv" if output_all else "rpp_item_boost_adjusted.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", encoding="cp932", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(CPC_OUTPUT_COLUMNS)
            for p in targets:
                control = "n" if output_all else p.cpc_control
                writer.writerow([control, p.code, p.output_cpc])
        title = "CPC全件CSV" if output_all else "CPC変更CSV"
        messagebox.showinfo("出力", f"{title}を出力しました。\n{path}")

    def export_exclude_csv(self):
        output_all = self.output_all_var.get()
        targets = [p for p in self.products if p.excluded] if output_all else [p for p in self.products if p.exclude_control]
        if not targets:
            message = "除外ONの商品がありません。" if output_all else "除外変更対象がありません。"
            messagebox.showinfo("出力", message)
            return
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            initialfile="RPP_exclude_items_all.csv" if output_all else "RPP_exclude_items_adjusted.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", encoding="cp932", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(EXCLUDE_COLUMNS)
            for p in targets:
                control = "n" if output_all else p.exclude_control
                writer.writerow([control, p.code])
        title = "除外全件CSV" if output_all else "除外変更CSV"
        messagebox.showinfo("出力", f"{title}を出力しました。\n{path}")

    def export_item_csv(self):
        self.apply_current_text_edits()
        if not self.item_csv_path.get():
            messagebox.showwarning("商品CSV出力", "商品CSVを指定してください。")
            return
        changed = {
            product.code: product
            for product in self.products
            if product.name != product.original_name or product.catch_copy != product.original_catch_copy
        }
        if not changed:
            messagebox.showinfo("商品CSV出力", "商品名・キャッチの変更対象がありません。")
            return
        source_path = Path(self.item_csv_path.get())
        if not source_path.exists():
            messagebox.showerror("商品CSV出力", "商品CSVが見つかりません。")
            return
        try:
            encoding = detect_encoding(source_path)
            with open(source_path, "r", encoding=encoding, errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                if PRODUCT_ID_COLUMN not in fieldnames or PRODUCT_NAME_COLUMN not in fieldnames or CATCH_COPY_COLUMN not in fieldnames:
                    messagebox.showerror("商品CSV出力", "商品CSVに必要な列がありません。")
                    return
                rows = []
                updated = 0
                for row in reader:
                    row.pop(None, None)
                    code = str(row.get(PRODUCT_ID_COLUMN, "")).strip()
                    product = changed.get(code)
                    if product:
                        row[PRODUCT_NAME_COLUMN] = product.name
                        row[CATCH_COPY_COLUMN] = product.catch_copy
                        updated += 1
                    rows.append(row)
        except Exception as e:
            messagebox.showerror("商品CSV出力", f"商品CSVの読み込みに失敗しました。\n{e}")
            return
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            initialfile="normal-item_name_catch_adjusted.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="cp932", errors="replace", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            messagebox.showerror("商品CSV出力", f"商品CSVの保存に失敗しました。\n{e}")
            return
        messagebox.showinfo("商品CSV出力", f"商品CSVを出力しました。\n更新行: {updated}件\n{path}")


def main():
    root = tk.Tk()
    app = RPPAdjuster(root)
    root.mainloop()


if __name__ == "__main__":
    main()
