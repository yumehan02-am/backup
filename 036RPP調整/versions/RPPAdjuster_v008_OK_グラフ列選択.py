import csv
import hashlib
import json
import logging
import threading
import queue
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import chardet
import requests
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk


SCRIPT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = SCRIPT_DIR / "rpp_adjuster_settings.json"
CACHE_DIR = SCRIPT_DIR / "cache" / "images"
CACHE_MAP_PATH = SCRIPT_DIR / "cache" / "image_cache.json"
DEBUG_LOG_PATH = SCRIPT_DIR / "rpp_adjuster_debug.log"

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
    detected = chardet.detect(raw).get("encoding")
    return detected or "cp932"


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
    current_cpc: int = 0
    new_cpc: int | None = None
    cpc_original_enabled: bool = False
    cpc_enabled: bool = False
    original_excluded: bool = False
    excluded: bool = False
    already_excluded: str = "No"
    prev: dict = field(default_factory=dict)
    curr: dict = field(default_factory=dict)

    @property
    def output_cpc(self) -> int:
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
        if self.cpc_original_enabled and self.cpc_enabled and self.output_cpc != self.current_cpc:
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
        self.root.geometry("1320x820")
        self.root.minsize(1100, 700)

        self.prev_report_path = tk.StringVar()
        self.curr_report_path = tk.StringVar()
        self.boost_path = tk.StringVar()
        self.exclude_path = tk.StringVar()
        self.item_csv_path = tk.StringVar()
        self.shop_url_var = tk.StringVar()
        self.period_var = tk.StringVar(value="比較期間: -")

        self.products: list[ProductState] = []
        self.filtered_indices: list[int] = []
        self.selected_product_indices: set[int] = set()
        self.current_index = 0
        self.search_var = tk.StringVar()
        self.search_column_var = tk.StringVar(value="商品名")
        self.numeric_search_var = tk.StringVar()
        self.numeric_operator_var = tk.StringVar(value="以下")
        self.bulk_cpc_var = tk.StringVar()
        self.active_text_filter = None
        self.active_numeric_filter = None
        self.filter_conditions = []
        self.show_changed_only = tk.BooleanVar(value=False)
        self.show_excluded_only = tk.BooleanVar(value=False)
        self.selection_count_var = tk.StringVar(value="選択 0件")
        self.graph_columns = list(DEFAULT_GRAPH_COLUMNS)
        self.graph_column_vars = {}

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
        self.load_settings()
        self.load_image_cache_map()
        self.build_ui()
        self.auto_fill_files()

    def load_settings(self):
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                self.prev_report_path.set(data.get("prev_report_path", ""))
                self.curr_report_path.set(data.get("curr_report_path", ""))
                self.boost_path.set(data.get("boost_path", ""))
                self.exclude_path.set(data.get("exclude_path", ""))
                self.item_csv_path.set(data.get("item_csv_path", ""))
                self.shop_url_var.set(data.get("shop_url", ""))
                columns = data.get("graph_columns")
                if isinstance(columns, list) and columns:
                    self.graph_columns = [str(col) for col in columns]
            except Exception:
                logging.exception("設定読み込みに失敗しました")

    def save_settings(self):
        data = {
            "prev_report_path": self.prev_report_path.get(),
            "curr_report_path": self.curr_report_path.get(),
            "boost_path": self.boost_path.get(),
            "exclude_path": self.exclude_path.get(),
            "item_csv_path": self.item_csv_path.get(),
            "shop_url": self.shop_url_var.get(),
            "graph_columns": self.graph_columns,
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
            reports = sorted([p for p in files if p.name.startswith("rpp_item_reports")], key=lambda p: p.stat().st_mtime)
            if len(reports) >= 2:
                self.prev_report_path.set(str(reports[-2]))
                self.curr_report_path.set(str(reports[-1]))

    def build_ui(self):
        top = ttk.LabelFrame(self.root, text="読み込み", padding=6)
        top.pack(fill=tk.X, padx=8, pady=6)
        self.add_shortcut_button(top, 0, "元実績", self.prev_report_path)
        self.add_shortcut_button(top, 1, "先実績", self.curr_report_path)
        self.add_shortcut_button(top, 2, "CPC", self.boost_path)
        self.add_shortcut_button(top, 3, "除外", self.exclude_path)
        self.add_shortcut_button(top, 4, "商品", self.item_csv_path)
        tk.Button(top, text="読み込み", command=self.load_all, font=("Meiryo", 9), width=12).grid(row=0, column=5, padx=(12, 4), sticky="ew")
        tk.Button(top, text="設定", command=self.open_settings_window, font=("Meiryo", 9), width=10).grid(row=0, column=6, padx=4, sticky="ew")
        tk.Button(top, text="CPC CSV出力", command=self.export_cpc_csv, font=("Meiryo", 9), width=14).grid(row=0, column=7, padx=4, sticky="ew")
        tk.Button(top, text="除外CSV出力", command=self.export_exclude_csv, font=("Meiryo", 9), width=14).grid(row=0, column=8, padx=4, sticky="ew")
        tk.Button(top, text="商品CSV出力", command=self.export_item_csv, font=("Meiryo", 9), width=14).grid(row=0, column=9, padx=4, sticky="ew")
        top.grid_columnconfigure(10, weight=1)

        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(toolbar, text="検索列", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.search_column_combo = ttk.Combobox(toolbar, textvariable=self.search_column_var, font=("Meiryo", 9), width=24, state="readonly")
        self.search_column_combo.pack(side=tk.LEFT, padx=4)
        self.search_column_combo["values"] = ("商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "除外")
        tk.Label(toolbar, text="文字", font=("Meiryo", 9)).pack(side=tk.LEFT)
        search = tk.Entry(toolbar, textvariable=self.search_var, font=("Meiryo", 9), width=18)
        search.pack(side=tk.LEFT, padx=4)
        search.bind("<Return>", lambda event: self.run_text_search())
        tk.Button(toolbar, text="文字検索", command=self.run_text_search, font=("Meiryo", 9), width=8).pack(side=tk.LEFT)
        tk.Label(toolbar, text="数値", font=("Meiryo", 9)).pack(side=tk.LEFT, padx=(8, 0))
        tk.Entry(toolbar, textvariable=self.numeric_search_var, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=4)
        ttk.Combobox(toolbar, textvariable=self.numeric_operator_var, font=("Meiryo", 9), width=6, state="readonly", values=("以下", "以上", "未満", "より大", "等しい")).pack(side=tk.LEFT)
        tk.Button(toolbar, text="数値検索", command=self.run_numeric_search, font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="検索解除", command=self.clear_search_filters, font=("Meiryo", 9), width=8).pack(side=tk.LEFT)
        tk.Checkbutton(toolbar, text="変更のみ", variable=self.show_changed_only, command=self.apply_filter, font=("Meiryo", 9)).pack(side=tk.LEFT, padx=6)
        tk.Checkbutton(toolbar, text="除外のみ", variable=self.show_excluded_only, command=self.apply_filter, font=("Meiryo", 9)).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Prev", command=self.prev_product, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=(18, 4))
        tk.Button(toolbar, text="Next", command=self.next_product, font=("Meiryo", 9), width=6).pack(side=tk.LEFT)
        self.position_var = tk.StringVar(value="0/0")
        tk.Label(toolbar, textvariable=self.position_var, font=("Meiryo", 9), width=12).pack(side=tk.LEFT, padx=8)
        self.status_var = tk.StringVar(value="未読込")
        tk.Label(toolbar, textvariable=self.status_var, font=("Meiryo", 9), anchor="w").pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)
        tk.Label(toolbar, textvariable=self.period_var, font=("Meiryo", 9), anchor="e", fg="#444444").pack(side=tk.RIGHT, padx=4)

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
        tk.Button(bulk_bar, text="選択へ適用", command=self.apply_bulk_cpc, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=3)
        tk.Button(bulk_bar, text="CPC ON", command=lambda: self.set_bulk_cpc_enabled(True), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=(12, 3))
        tk.Button(bulk_bar, text="CPC OFF", command=lambda: self.set_bulk_cpc_enabled(False), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(bulk_bar, text="除外ON", command=lambda: self.set_bulk_excluded(True), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=(12, 3))
        tk.Button(bulk_bar, text="除外OFF", command=lambda: self.set_bulk_excluded(False), font=("Meiryo", 9), width=8).pack(side=tk.LEFT, padx=3)

        history_bar = ttk.LabelFrame(self.root, text="選別履歴", padding=5)
        history_bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.condition_listbox = tk.Listbox(history_bar, height=3, font=("Meiryo", 8), exportselection=False)
        self.condition_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        history_scroll = tk.Scrollbar(history_bar, orient=tk.VERTICAL, command=self.condition_listbox.yview)
        history_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.condition_listbox.configure(yscrollcommand=history_scroll.set)
        tk.Button(history_bar, text="一つ戻す", command=self.undo_last_condition, font=("Meiryo", 9), width=10).pack(side=tk.LEFT, padx=6)
        tk.Button(history_bar, text="リセット", command=self.reset_conditions_and_selection, font=("Meiryo", 9), width=10).pack(side=tk.LEFT)

        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left = tk.Frame(main)
        main.add(left, minsize=660)
        right = tk.Frame(main)
        main.add(right, minsize=360)

        columns = ("code", "name", "cpc", "new_cpc", "exclude", "click_diff", "cost_diff", "sales_diff", "roas_curr")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=20, selectmode="extended")
        headings = {
            "code": "商品管理番号",
            "name": "商品名",
            "cpc": "現CPC",
            "new_cpc": "新CPC",
            "exclude": "除外",
            "click_diff": "クリック差",
            "cost_diff": "費用差",
            "sales_diff": "売上差",
            "roas_curr": "ROAS",
        }
        widths = {"code": 130, "name": 330, "cpc": 60, "new_cpc": 60, "exclude": 50, "click_diff": 70, "cost_diff": 70, "sales_diff": 80, "roas_curr": 70}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w" if col in ("code", "name") else "e")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ybar = tk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=ybar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        product = ttk.LabelFrame(right, text="商品", padding=8)
        product.pack(fill=tk.X)
        self.image_canvas = tk.Canvas(product, width=180, height=180, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.image_canvas.grid(row=0, column=0, rowspan=5, padx=(0, 10), sticky="nw")
        self.image_canvas.bind("<MouseWheel>", self.on_image_wheel)
        self.image_canvas.bind("<Button-1>", lambda event: self.toggle_exclude())
        self.name_var = tk.StringVar()
        self.catch_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.url_var = tk.StringVar()
        tk.Label(product, textvariable=self.code_var, font=("Meiryo", 10, "bold"), anchor="w").grid(row=0, column=1, sticky="ew")
        tk.Entry(product, textvariable=self.name_var, font=("Meiryo", 9)).grid(row=1, column=1, sticky="ew")
        tk.Entry(product, textvariable=self.catch_var, font=("Meiryo", 8), fg="#555555").grid(row=2, column=1, sticky="ew")
        tk.Label(product, textvariable=self.url_var, font=("Meiryo", 8), fg="#336699", wraplength=430, justify=tk.LEFT, anchor="w").grid(row=3, column=1, sticky="ew")

        cpc_frame = tk.Frame(product)
        cpc_frame.grid(row=4, column=1, sticky="w", pady=8)
        tk.Label(cpc_frame, text="新CPC", font=("Meiryo", 9)).pack(side=tk.LEFT)
        self.cpc_var = tk.StringVar()
        tk.Entry(cpc_frame, textvariable=self.cpc_var, font=("Meiryo", 10), width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(cpc_frame, text="-5", command=lambda: self.adjust_cpc(-5), font=("Meiryo", 9), width=4).pack(side=tk.LEFT)
        tk.Button(cpc_frame, text="-1", command=lambda: self.adjust_cpc(-1), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=(2, 0))
        tk.Button(cpc_frame, text="+1", command=lambda: self.adjust_cpc(1), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=(2, 0))
        tk.Button(cpc_frame, text="+5", command=lambda: self.adjust_cpc(5), font=("Meiryo", 9), width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(cpc_frame, text="適用", command=self.apply_cpc, font=("Meiryo", 9), width=6).pack(side=tk.LEFT, padx=6)
        self.cpc_toggle_button = tk.Button(cpc_frame, command=self.toggle_cpc_enabled, font=("Meiryo", 9), width=12)
        self.cpc_toggle_button.pack(side=tk.LEFT, padx=(0, 6))
        self.exclude_var = tk.BooleanVar()
        self.exclude_toggle_button = tk.Button(cpc_frame, command=self.toggle_exclude, font=("Meiryo", 9), width=12)
        self.exclude_toggle_button.pack(side=tk.LEFT)
        product.grid_columnconfigure(1, weight=1)

        metrics = ttk.LabelFrame(right, text="比較", padding=8)
        metrics.pack(fill=tk.X, pady=6)
        self.metrics_text = tk.Text(metrics, height=8, font=("Meiryo", 9), wrap=tk.NONE)
        self.metrics_text.pack(fill=tk.X)
        self.metrics_text.config(state=tk.DISABLED)

        graph_frame = ttk.LabelFrame(right, text="グラフ", padding=8)
        graph_frame.pack(fill=tk.BOTH, expand=True)
        self.graph = tk.Canvas(graph_frame, bg="white", height=260)
        self.graph.pack(fill=tk.BOTH, expand=True)

        self.root.bind("<Control-Up>", lambda event: self.prev_product())
        self.root.bind("<Control-Down>", lambda event: self.next_product())

    def add_file_row(self, parent, row, label, var):
        tk.Label(parent, text=label, font=("Meiryo", 9), width=10, anchor="w").grid(row=row, column=0, sticky="w", pady=2)
        tk.Entry(parent, textvariable=var, font=("Meiryo", 9)).grid(row=row, column=1, sticky="ew", padx=4)
        tk.Button(parent, text="参照", command=lambda: self.select_file(var), font=("Meiryo", 9), width=8).grid(row=row, column=2, padx=2)

    def add_shortcut_button(self, parent, column, label, var):
        button = tk.Button(parent, text=label, command=lambda: self.select_file(var), font=("Meiryo", 9), width=10)
        button.grid(row=0, column=column, padx=3, sticky="ew")
        return button

    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("設定")
        win.geometry("860x560")
        win.transient(self.root)
        frame = ttk.LabelFrame(win, text="読み込みファイル", padding=8)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.add_file_row(frame, 0, "比較元実績", self.prev_report_path)
        self.add_file_row(frame, 1, "比較先実績", self.curr_report_path)
        self.add_file_row(frame, 2, "CPC設定CSV", self.boost_path)
        self.add_file_row(frame, 3, "除外CSV", self.exclude_path)
        self.add_file_row(frame, 4, "商品CSV", self.item_csv_path)
        tk.Label(frame, text="店舗ID/URL", font=("Meiryo", 9), width=10, anchor="w").grid(row=5, column=0, sticky="w", pady=2)
        tk.Entry(frame, textvariable=self.shop_url_var, font=("Meiryo", 9)).grid(row=5, column=1, sticky="ew", padx=4)
        frame.grid_columnconfigure(1, weight=1)

        graph_frame = ttk.LabelFrame(frame, text="グラフ列", padding=6)
        graph_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.graph_column_vars = {}
        for index, column in enumerate(self.get_graph_column_candidates()):
            var = tk.BooleanVar(value=column in self.graph_columns)
            self.graph_column_vars[column] = var
            tk.Checkbutton(graph_frame, text=self.short_column_label(column), variable=var, font=("Meiryo", 8)).grid(
                row=index // 3, column=index % 3, sticky="w", padx=4, pady=1
            )
        graph_frame.grid_columnconfigure(2, weight=1)

        buttons = tk.Frame(win)
        buttons.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Button(buttons, text="商品情報読込", command=self.load_item_info, font=("Meiryo", 9), width=14).pack(side=tk.LEFT)
        tk.Button(buttons, text="全画像キャッシュ", command=self.cache_all_images, font=("Meiryo", 9), width=16).pack(side=tk.LEFT, padx=6)
        tk.Button(buttons, text="グラフ列適用", command=self.apply_graph_column_settings, font=("Meiryo", 9), width=14).pack(side=tk.LEFT)
        tk.Button(buttons, text="閉じる", command=win.destroy, font=("Meiryo", 9), width=10).pack(side=tk.RIGHT)

    def get_graph_column_candidates(self):
        candidates = []
        seen = set()
        for column in NUMERIC_COLUMNS + DEFAULT_GRAPH_COLUMNS:
            if column not in seen:
                seen.add(column)
                candidates.append(column)
        for product in self.products[:20]:
            for source in (product.prev, product.curr):
                for column, value in source.items():
                    if column in seen:
                        continue
                    if safe_number(value, None) is not None:
                        seen.add(column)
                        candidates.append(column)
        return candidates

    def short_column_label(self, column):
        return (
            column.replace("(合計720時間)", "720h")
            .replace("(合計12時間)", "12h")
            .replace("(合計)", "")
        )

    def apply_graph_column_settings(self):
        selected = [column for column, var in self.graph_column_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("グラフ列", "グラフ列を1つ以上選択してください。")
            return
        self.graph_columns = selected
        self.save_settings()
        product = self.current_product()
        if product:
            self.update_metrics(product)
            self.draw_graph(product)

    def select_file(self, var):
        path = filedialog.askopenfilename(initialdir=SCRIPT_DIR, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            var.set(path)
            self.save_settings()

    def load_all(self):
        if self.loading:
            messagebox.showinfo("読み込み", "読み込み中です。完了までお待ちください。")
            return
        self.root.config(cursor="wait")
        self.loading = True
        self.status_var.set("CSVを読み込み中...")
        debug_log("load_all start")
        self.root.update_idletasks()

        paths = {
            "prev": self.prev_report_path.get(),
            "curr": self.curr_report_path.get(),
            "boost": self.boost_path.get(),
            "exclude": self.exclude_path.get(),
            "shop_url": self.shop_url_var.get(),
        }
        threading.Thread(target=self.load_all_worker, args=(paths,), daemon=True).start()
        self.root.after(100, self.poll_load_queue)

    def load_all_worker(self, paths):
        try:
            prev_period = read_report_period(Path(paths["prev"]))
            curr_period = read_report_period(Path(paths["curr"]))
            debug_log("read prev report start")
            prev = read_rpp_report(Path(paths["prev"]))
            debug_log(f"read prev report done rows={len(prev)}")
            debug_log("read curr report start")
            curr = read_rpp_report(Path(paths["curr"]))
            debug_log(f"read curr report done rows={len(curr)}")
            debug_log("read boost csv start")
            boost = read_normal_csv(Path(paths["boost"])) if paths["boost"] else []
            debug_log(f"read boost csv done rows={len(boost)}")
            debug_log("read exclude csv start")
            exclude = read_normal_csv(Path(paths["exclude"])) if paths["exclude"] else []
            debug_log(f"read exclude csv done rows={len(exclude)}")
            item_map = {}
            debug_log("build products start")
            products = self.build_products(prev, curr, boost, exclude, item_map, paths["shop_url"])
            debug_log(f"build products done rows={len(products)}")
            self.load_queue.put(("done", products, prev_period, curr_period))
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
            messagebox.showerror("読み込みエラー", message[1])
            return
        self.products = message[1]
        prev_period = message[2] if len(message) > 2 else ""
        curr_period = message[3] if len(message) > 3 else ""
        if prev_period or curr_period:
            self.period_var.set(f"比較期間: {prev_period or '-'} → {curr_period or '-'}")
        else:
            self.period_var.set("比較期間: -")
        self.save_settings()
        self.update_search_columns()
        debug_log("apply filter start")
        self.apply_filter()
        debug_log("apply filter queued")
        self.status_var.set(f"読込完了: {len(self.products)}商品")
        if self.item_csv_path.get():
            self.root.after(100, self.load_item_info)

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
        self.status_var.set(f"商品情報読込完了: {updated}件")
        self.update_search_columns()
        self.apply_filter()

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

    def collect_target_codes(self, prev, curr, boost):
        codes = set()
        for rows in (prev, curr, boost):
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

    def build_products(self, prev, curr, boost, exclude, item_map, shop_url=""):
        prev_map = {str(row.get("商品管理番号", "")).strip(): row for row in prev if str(row.get("商品管理番号", "")).strip()}
        curr_map = {str(row.get("商品管理番号", "")).strip(): row for row in curr if str(row.get("商品管理番号", "")).strip()}
        boost_map = {str(row.get("商品管理番号", "")).strip(): row for row in boost if str(row.get("商品管理番号", "")).strip()}
        excluded_codes = {str(row.get("商品管理番号", "")).strip() for row in exclude if str(row.get("商品管理番号", "")).strip()}
        codes = sorted(set(prev_map) | set(curr_map) | set(boost_map))
        products = []
        for code in codes:
            b = boost_map.get(code, {})
            item = item_map.get(code, {})
            c = curr_map.get(code, {})
            p = prev_map.get(code, {})
            current_cpc = int(safe_number(b.get("商品CPC") or c.get("入札単価") or p.get("入札単価"), 0))
            image_path = str(item.get(MAIN_IMAGE_COLUMN, "") or "")
            cpc_original_enabled = bool(b)
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
            ))
        products.sort(key=lambda item: safe_number(item.curr.get("実績額(合計)", 0), 0), reverse=True)
        return products

    def update_search_columns(self):
        fixed = ["商品名", "商品管理番号", "キャッチコピー", "現CPC", "新CPC", "除外"]
        raw_columns = []
        seen = set()
        for product in self.products:
            for source in (product.prev, product.curr):
                for key in source.keys():
                    if key and key not in seen:
                        seen.add(key)
                        raw_columns.append(key)
        values = fixed + [f"元:{col}" for col in raw_columns] + [f"先:{col}" for col in raw_columns] + [f"差:{col}" for col in raw_columns]
        if hasattr(self, "search_column_combo"):
            self.search_column_combo["values"] = values
        if self.search_column_var.get() not in values:
            self.search_column_var.set("商品名")

    def run_text_search(self):
        column = self.search_column_var.get() or "商品名"
        value = self.search_var.get().strip()
        if not value:
            return
        self.filter_conditions.append(("text", column, "含む", value))
        self.update_condition_history()
        self.apply_filter()

    def run_numeric_search(self):
        column = self.search_column_var.get() or "現CPC"
        value_text = self.numeric_search_var.get().strip()
        if not value_text:
            return
        try:
            value = safe_number(value_text)
        except Exception:
            messagebox.showwarning("検索", "数値検索には数値を入力してください。")
            return
        self.filter_conditions.append(("numeric", column, self.numeric_operator_var.get(), value))
        self.update_condition_history()
        self.apply_filter()

    def clear_search_filters(self):
        self.search_var.set("")
        self.numeric_search_var.set("")
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

    def product_column_value(self, product, column):
        if column == "商品名":
            return product.name
        if column == "商品管理番号":
            return product.code
        if column == "キャッチコピー":
            return product.catch_copy
        if column == "現CPC":
            return product.current_cpc
        if column == "新CPC":
            return product.output_cpc
        if column == "除外":
            return product.exclude_status or ("除外ON" if product.excluded else "除外OFF")
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
                value = self.product_column_value(product, column)
                if kind == "text":
                    if str(target).lower() not in str(value or "").lower():
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

    def render_tree_batch(self, start):
        batch_size = 200
        end = min(start + batch_size, len(self.filtered_indices))
        for pos in range(start, end):
            product_index = self.filtered_indices[pos]
            p = self.products[product_index]
            self.tree.insert("", tk.END, iid=str(pos), values=(
                p.code,
                p.name[:80],
                p.current_cpc,
                self.format_cpc_status(p),
                p.exclude_status or ("除外ON" if p.excluded else ""),
                self.diff_value(p, "クリック数(合計)", integer=True),
                self.diff_value(p, "実績額(合計)", integer=True),
                self.diff_value(p, "売上金額(合計720時間)", integer=True),
                f'{safe_number(p.curr.get("ROAS(合計720時間)(%)", 0)):.1f}',
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

    def format_cpc_status(self, product):
        if product.cpc_control == "d":
            return "削除"
        if product.cpc_status:
            return f"{product.output_cpc} {product.cpc_status}"
        if product.cpc_enabled:
            return str(product.output_cpc)
        return "OFF"

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

    def clear_product_selection(self):
        self.selected_product_indices.clear()
        self.tree.selection_remove(self.tree.selection())
        self.update_selection_count()

    def invert_visible_selection(self):
        visible = set(self.filtered_indices)
        self.selected_product_indices = (self.selected_product_indices - visible) | (visible - self.selected_product_indices)
        self.tree.selection_remove(self.tree.selection())
        self.restore_tree_selection()
        self.update_selection_count()

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
            messagebox.showwarning("一括操作", "CPCは0以上で入力してください。")
            return
        for product in products:
            product.cpc_enabled = True
            product.new_cpc = value if value != product.current_cpc else None
        self.status_var.set(f"CPCを一括適用しました: {len(products)}件")
        self.refresh_tree()

    def set_bulk_cpc_enabled(self, enabled):
        products = self.require_selected_products()
        if not products:
            return
        for product in products:
            product.cpc_enabled = enabled
            if enabled and product.output_cpc <= 0:
                product.new_cpc = max(1, product.current_cpc)
        self.status_var.set(f"CPC {'ON' if enabled else 'OFF'}: {len(products)}件")
        self.refresh_tree()

    def set_bulk_excluded(self, excluded):
        products = self.require_selected_products()
        if not products:
            return
        for product in products:
            product.excluded = excluded
        self.status_var.set(f"除外 {'ON' if excluded else 'OFF'}: {len(products)}件")
        self.refresh_tree()

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
                current_selection = self.tree.selection()
                if item_id not in current_selection:
                    self.tree.selection_set(item_id)
                    self.selected_product_indices = {self.filtered_indices[self.current_index]}
                    self.update_selection_count()
                self.tree.focus(item_id)
                self.tree.see(item_id)
            finally:
                self.updating_tree_selection = False
                self.root.after(50, lambda: setattr(self, "ignore_tree_select", False))
        self.code_var.set(product.code)
        self.name_var.set(product.name or "(商品名なし)")
        self.catch_var.set(product.catch_copy)
        self.url_var.set(product.url)
        self.cpc_var.set(str(product.output_cpc))
        self.exclude_var.set(product.excluded)
        self.update_cpc_toggle_button(product)
        self.update_exclude_toggle_button(product)
        self.update_metrics(product)
        self.draw_graph(product)
        self.show_cached_or_fetch_image(product)
        debug_log(f"show_product done {filtered_pos}")

    def apply_current_text_edits(self):
        if not self.filtered_indices:
            return
        product = self.products[self.filtered_indices[self.current_index]]
        if self.code_var.get() and self.code_var.get() != product.code:
            return
        product.name = self.name_var.get()
        product.catch_copy = self.catch_var.get()

    def current_product(self):
        if not self.filtered_indices:
            return None
        return self.products[self.filtered_indices[self.current_index]]

    def next_product(self):
        if self.filtered_indices:
            self.apply_current_text_edits()
            self.apply_cpc(silent=True)
            self.show_product((self.current_index + 1) % len(self.filtered_indices))
        return "break"

    def prev_product(self):
        if self.filtered_indices:
            self.apply_current_text_edits()
            self.apply_cpc(silent=True)
            self.show_product(self.current_index - 1 if self.current_index > 0 else len(self.filtered_indices) - 1)
        return "break"

    def on_image_wheel(self, event):
        if event.delta > 0:
            return self.prev_product()
        return self.next_product()

    def adjust_cpc(self, delta):
        value = int(safe_number(self.cpc_var.get(), 0)) + delta
        self.cpc_var.set(str(max(0, value)))
        self.apply_cpc(silent=True)

    def apply_cpc(self, silent=False):
        product = self.current_product()
        if not product:
            return
        try:
            value = int(safe_number(self.cpc_var.get(), product.current_cpc))
        except Exception:
            if not silent:
                messagebox.showwarning("入力エラー", "CPCは数値で入力してください。")
            return
        product.cpc_enabled = True
        product.new_cpc = value if value != product.current_cpc else None
        self.update_cpc_toggle_button(product)
        self.refresh_tree()

    def toggle_cpc_enabled(self):
        product = self.current_product()
        if not product:
            return
        product.cpc_enabled = not product.cpc_enabled
        if product.cpc_enabled and product.output_cpc <= 0:
            product.new_cpc = max(1, product.current_cpc)
            self.cpc_var.set(str(product.output_cpc))
        self.update_cpc_toggle_button(product)
        self.refresh_tree()

    def update_cpc_toggle_button(self, product):
        if not hasattr(self, "cpc_toggle_button"):
            return
        text = f"CPC {product.cpc_status or ('ON' if product.cpc_enabled else 'OFF')}"
        bg = "#c8ebd4" if product.cpc_enabled else "#eeeeee"
        relief = tk.SUNKEN if product.cpc_enabled else tk.RAISED
        self.cpc_toggle_button.config(text=text, bg=bg, relief=relief)

    def apply_exclude(self):
        product = self.current_product()
        if product:
            product.excluded = self.exclude_var.get()
            self.update_exclude_toggle_button(product)
            self.refresh_tree()

    def toggle_exclude(self):
        product = self.current_product()
        if not product:
            return
        product.excluded = not product.excluded
        self.exclude_var.set(product.excluded)
        self.update_exclude_toggle_button(product)
        self.refresh_tree()

    def update_exclude_toggle_button(self, product):
        if not hasattr(self, "exclude_toggle_button"):
            return
        text = product.exclude_status or ("除外ON" if product.excluded else "除外OFF")
        bg = "#ffd6d6" if product.excluded else "#eeeeee"
        relief = tk.SUNKEN if product.excluded else tk.RAISED
        self.exclude_toggle_button.config(text=text, bg=bg, relief=relief)

    def update_metrics(self, product):
        lines = []
        for col in self.graph_columns:
            title = self.short_column_label(col)
            prev = safe_number(product.prev.get(col, 0))
            curr = safe_number(product.curr.get(col, 0))
            lines.append(f"{title:<10} 比較元 {prev:>10.1f} / 比較先 {curr:>10.1f} / 差 {curr - prev:>+10.1f}")
        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete("1.0", tk.END)
        self.metrics_text.insert(tk.END, "\n".join(lines))
        self.metrics_text.config(state=tk.DISABLED)

    def draw_graph(self, product):
        self.graph.delete("all")
        width = max(360, self.graph.winfo_width())
        metrics = [(self.short_column_label(col), col) for col in self.graph_columns]
        max_value = max([safe_number(product.prev.get(col, 0)) for _, col in metrics] + [safe_number(product.curr.get(col, 0)) for _, col in metrics] + [1])
        y = 24
        for label, col in metrics:
            prev = safe_number(product.prev.get(col, 0))
            curr = safe_number(product.curr.get(col, 0))
            self.graph.create_text(8, y + 12, text=label, anchor="w", font=("Meiryo", 9))
            prev_w = int((prev / max_value) * (width - 160))
            curr_w = int((curr / max_value) * (width - 160))
            self.graph.create_rectangle(80, y, 80 + prev_w, y + 12, fill="#9ecae1", outline="")
            self.graph.create_rectangle(80, y + 16, 80 + curr_w, y + 28, fill="#31a354", outline="")
            self.graph.create_text(88 + max(prev_w, curr_w), y + 14, text=f"{prev:.0f} → {curr:.0f}", anchor="w", font=("Meiryo", 8))
            y += 48
        self.graph.create_rectangle(80, y, 94, y + 10, fill="#9ecae1", outline="")
        self.graph.create_text(100, y + 5, text="比較元", anchor="w", font=("Meiryo", 8))
        self.graph.create_rectangle(170, y, 184, y + 10, fill="#31a354", outline="")
        self.graph.create_text(190, y + 5, text="比較先", anchor="w", font=("Meiryo", 8))

    def image_cache_path(self, image_url):
        key = hashlib.md5(image_url.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{key}.jpg"

    def show_cached_image_or_placeholder(self, product):
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
        self.status_var.set(f"画像キャッシュ中... 0/{len(urls)}")
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

    def poll_image_queue(self):
        try:
            message = self.image_queue.get_nowait()
        except queue.Empty:
            if self.image_cache_running:
                self.root.after(100, self.poll_image_queue)
            return
        if message[0] == "__cache_progress__":
            _, idx, total, failed = message
            self.status_var.set(f"画像キャッシュ中... {idx}/{total} 失敗:{failed}")
            self.root.after(50, self.poll_image_queue)
            return
        if message[0] == "__cache_done__":
            _, total, failed = message
            self.image_cache_running = False
            self.status_var.set(f"画像キャッシュ完了: {total}件 / 失敗:{failed}")
            product = self.current_product()
            if product:
                self.show_cached_or_fetch_image(product)
            return
        code, image_url = message
        product = self.current_product()
        if not product or product.code != code:
            return
        if not image_url or not self.display_cached_image(image_url):
            self.image_canvas.delete("all")
            self.image_canvas.create_text(90, 90, text="画像なし", font=("Meiryo", 9), fill="#666666")
        if not self.image_queue.empty():
            self.root.after(50, self.poll_image_queue)

    def display_cached_image(self, image_url):
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
        changed = [p for p in self.products if p.cpc_changed]
        if not changed:
            messagebox.showinfo("出力", "CPC変更対象がありません。")
            return
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            initialfile="rpp_item_boost_adjusted.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", encoding="cp932", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(CPC_OUTPUT_COLUMNS)
            for p in changed:
                writer.writerow([p.cpc_control, p.code, p.output_cpc])
        messagebox.showinfo("出力", f"CPC変更CSVを出力しました。\n{path}")

    def export_exclude_csv(self):
        changed = [p for p in self.products if p.exclude_control]
        if not changed:
            messagebox.showinfo("出力", "除外変更対象がありません。")
            return
        path = filedialog.asksaveasfilename(
            initialdir=SCRIPT_DIR,
            initialfile="RPP_exclude_items_adjusted.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", encoding="cp932", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(EXCLUDE_COLUMNS)
            for p in changed:
                writer.writerow([p.exclude_control, p.code])
        messagebox.showinfo("出力", f"除外変更CSVを出力しました。\n{path}")

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
