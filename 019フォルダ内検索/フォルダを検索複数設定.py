import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
import ipaddress
import subprocess
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import unicodedata
from datetime import datetime
import string

DEFAULT_EXCLUDE_FOLDER_NAMES = {
    "$recycle.bin", "#recycle", "@recycle", "recycler", "recycled",
    "@eadir", ".snapshot", ".sync", ".stfolder", ".git", "node_modules", "__pycache__"
}
KEYWORD_MODE_LABELS = {
    "folder_exclude": "フォルダ除外",
    "folder_include": "フォルダ参照",
    "file_exclude": "ファイル除外",
    "file_include": "ファイル参照",
}
KEYWORD_LABEL_MODES = {label: mode for mode, label in KEYWORD_MODE_LABELS.items()}
SEARCH_TARGET_LABELS = ("ファイル名検索", "フォルダ名検索", "両方検索")
SEARCH_TARGET_LABEL_MODES = {
    "ファイル名検索": "file",
    "フォルダ名検索": "folder",
    "両方検索": "both",
}
COMPACT_DEFAULT_WIDTH = 240
COMPACT_MIN_WIDTH = 220
COMPACT_COLLAPSED_HEIGHT = 28
COMPACT_RESULT_DIRECTION_LABELS = ("自動", "下", "上")

class FileSearchTool:
    def __init__(self, root):
        self.root = root
        self.root.title("File Search Tool")
        self.config_file = "search_tool_config.json"
        self.cache_file = "cache.json"
        self.load_config()
        self.load_cache()
        self.create_button_images()
        self.worker_thread = None
        self.cancel_event = threading.Event()
        self.result_queue = queue.Queue()
        self.debug_paths = False
        self.folder_row_frames = []
        self.active_folder_var = tk.StringVar(value=self.config.get("active_folder_path", ""))
        self.selected_folder_vars = {}
        self.always_on_top_var = tk.BooleanVar(value=self.config.get("always_on_top", False))
        self.compact_mode = False
        self.compact_results_expanded = False
        self.normal_geometry = None
        self.compact_drag_offset = None
        self.compact_position = None
        self.compact_size = None
        self.compact_manual_resized = False
        self.compact_visible_result_rows = 1
        self.compact_resize_start = None
        self.compact_width_resize_start = None
        self.compact_result_direction = "down"
        self.compact_result_paths = []
        self.loading_keyword_rules = False
        self.current_keyword_folder_path = self.config.get("active_folder_path", "")

        self.folder_frame = tk.Frame(root)
        self.folder_frame.pack(pady=5, padx=5, fill=tk.X)
        tk.Label(self.folder_frame, text="指定フォルダ(URL):").pack(side=tk.LEFT)
        self.folder_entry = tk.Entry(self.folder_frame)
        self.folder_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Button(self.folder_frame, text="参照", command=self.browse_folder).pack(side=tk.LEFT)
        tk.Button(self.folder_frame, text="追加", command=self.add_registered_folder).pack(side=tk.LEFT, padx=2)
        tk.Button(self.folder_frame, text="ネットワーク取得", command=self.refresh_local_networks).pack(side=tk.LEFT, padx=5)
        tk.Button(self.folder_frame, text="保存", command=self.save_config).pack(side=tk.LEFT)

        self.folder_list_frame = tk.Frame(root)
        self.folder_list_frame.pack(pady=2, padx=5, fill=tk.X)

        self.option_frame = tk.Frame(root)
        self.option_frame.pack(pady=5, fill=tk.X)
        self.option_row1 = tk.Frame(self.option_frame)
        self.option_row1.pack(fill=tk.X, padx=5)
        self.option_row2 = tk.Frame(self.option_frame)
        self.option_row2.pack(fill=tk.X, padx=5, pady=(2, 0))
        self.subfolder_var = tk.BooleanVar(value=self.config.get("include_subfolders", True))
        tk.Checkbutton(self.option_row1, text="サブフォルダを含む", variable=self.subfolder_var).pack(side=tk.LEFT)
        tk.Label(self.option_row1, text="最大検索深度 (0=無制限):").pack(side=tk.LEFT, padx=10)
        self.max_depth_var = tk.IntVar(value=self.config.get("max_depth", 0))
        tk.Entry(self.option_row1, textvariable=self.max_depth_var, width=5).pack(side=tk.LEFT)
        self.search_target_var = tk.StringVar(value=self.get_configured_search_target_label())
        ttk.Combobox(
            self.option_row1,
            textvariable=self.search_target_var,
            values=SEARCH_TARGET_LABELS,
            state="readonly",
            width=14
        ).pack(side=tk.LEFT, padx=10)
        self.multiple_folder_var = tk.BooleanVar(value=self.config.get("multiple_folder_selection", False))
        tk.Checkbutton(
            self.option_row1,
            text="複数フォルダ選択",
            variable=self.multiple_folder_var,
            command=self.toggle_multiple_folder_selection
        ).pack(side=tk.LEFT)
        tk.Checkbutton(
            self.option_row2,
            text="最前面に表示",
            variable=self.always_on_top_var,
            command=self.toggle_always_on_top
        ).pack(side=tk.LEFT)
        tk.Label(self.option_row2, text="ミニ結果表示:").pack(side=tk.LEFT, padx=(10, 2))
        self.compact_result_direction_var = tk.StringVar(
            value=self.get_configured_compact_result_direction()
        )
        ttk.Combobox(
            self.option_row2,
            textvariable=self.compact_result_direction_var,
            values=COMPACT_RESULT_DIRECTION_LABELS,
            state="readonly",
            width=5
        ).pack(side=tk.LEFT)
        self.compact_result_direction_var.trace_add("write", self.on_compact_result_direction_change)
        self.compact_mode_button = tk.Button(
            self.option_row2,
            image=self.compact_image,
            command=self.enter_compact_mode,
            width=28,
            height=24,
            bg="#f4a340",
            activebackground="#e8891a",
            relief=tk.RAISED
        )
        self.compact_mode_button.pack(side=tk.RIGHT)

        self.network_frame = tk.Frame(root)
        self.network_frame.pack(pady=5, padx=5, fill=tk.X)
        tk.Label(self.network_frame, text="ローカルネットワーク:").pack(side=tk.LEFT)
        self.network_var = tk.StringVar(value="")
        self.network_entry = tk.Entry(self.network_frame, textvariable=self.network_var, state="readonly")
        self.network_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Button(self.network_frame, text="コピー", command=self.copy_network_address).pack(side=tk.LEFT)

        self.keyword_frame = tk.Frame(root)
        self.keyword_frame.pack(pady=5, padx=5, fill=tk.X)
        tk.Label(self.keyword_frame, text="キーワード:").pack(side=tk.LEFT)
        self.keyword_entry = tk.Entry(self.keyword_frame)
        self.keyword_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.keyword_mode_var = tk.StringVar(value="フォルダ除外")
        ttk.Combobox(
            self.keyword_frame,
            textvariable=self.keyword_mode_var,
            values=list(KEYWORD_LABEL_MODES.keys()),
            state="readonly",
            width=12
        ).pack(side=tk.LEFT)
        tk.Button(self.keyword_frame, text="追加", command=self.add_keyword_rule).pack(side=tk.LEFT)
        tk.Button(self.keyword_frame, text="削除", command=self.delete_keyword_rule).pack(side=tk.LEFT)
        tk.Button(self.keyword_frame, text="クリア", command=self.clear_keyword_rules).pack(side=tk.LEFT)

        self.keyword_listbox = tk.Listbox(root, height=3, width=80)
        self.keyword_listbox.pack(pady=5, padx=5, fill=tk.X)
        for rule in self.get_active_folder_keyword_rules():
            self.keyword_listbox.insert(tk.END, self.format_keyword_rule(rule))

        self.search_frame = tk.Frame(root)
        self.search_frame.pack(pady=5, padx=5, fill=tk.X)
        self.search_controls_frame = tk.Frame(self.search_frame)
        self.search_controls_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry_row = tk.Frame(self.search_controls_frame)
        self.search_entry_row.pack(fill=tk.X)
        self.search_button_row = tk.Frame(self.search_controls_frame)
        self.search_button_row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(self.search_entry_row, text="検索:").pack(side=tk.LEFT)
        self.search_entry = tk.Entry(self.search_entry_row)
        self.search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.index_button = tk.Button(self.search_button_row, text="更新", width=5, command=self.update_index)
        self.cancel_button = tk.Button(self.search_button_row, text="停止", command=self.cancel_current_task, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.RIGHT)
        self.index_button.pack(side=tk.RIGHT, padx=(0, 5))
        self.search_button = tk.Button(
            self.search_frame,
            text="検索",
            command=self.search_files,
            width=10,
            height=2,
            bg="#9be28f",
            activebackground="#b7efac",
            relief=tk.RAISED
        )
        self.search_button.pack(side=tk.LEFT, padx=(6, 0), fill=tk.Y)

        self.status_frame = tk.Frame(root)
        self.status_frame.pack(pady=2, padx=5, fill=tk.X)
        self.status_var = tk.StringVar(value="待機中")
        tk.Label(self.status_frame, textvariable=self.status_var, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(self.status_frame, text="開く", command=self.open_file).pack(side=tk.RIGHT)
        tk.Button(self.status_frame, text="参照", command=self.reveal_file).pack(side=tk.RIGHT, padx=5)

        self.result_frame = tk.Frame(root)
        self.result_frame.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        self.result_listbox = tk.Listbox(self.result_frame, width=80, height=15)
        self.result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar = tk.Scrollbar(self.result_frame, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.result_listbox.yview)
        self.result_listbox.bind('<Double-1>', self.open_file)

        self.main_frames = [
            self.folder_frame,
            self.folder_list_frame,
            self.option_frame,
            self.network_frame,
            self.keyword_frame,
            self.keyword_listbox,
            self.search_frame,
            self.status_frame,
            self.result_frame
        ]
        self.create_compact_widgets()
        self.apply_always_on_top()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        if self.config.get("folder_path"):
            self.folder_entry.insert(0, self.normalize_path(self.config["folder_path"]))
        self.render_registered_folders()
        self.refresh_local_networks(show_message=False)
        self.root.after(0, self.adjust_window_height)

    def create_button_images(self):
        self.search_image = self.create_icon_image("search")
        self.restore_image = self.create_icon_image("restore")
        self.compact_image = self.create_icon_image("compact")
        self.grip_image = self.create_icon_image("grip")
        self.close_image = self.create_icon_image("close")

    def create_icon_image(self, kind, size=18):
        image = tk.PhotoImage(width=size, height=size)
        transparent = ""
        for y in range(size):
            image.put(transparent, to=(0, y, size, y + 1))

        def put(x, y, color="#222222"):
            if 0 <= x < size and 0 <= y < size:
                image.put(color, (x, y))

        def line(x1, y1, x2, y2, color="#222222"):
            dx = abs(x2 - x1)
            dy = -abs(y2 - y1)
            sx = 1 if x1 < x2 else -1
            sy = 1 if y1 < y2 else -1
            err = dx + dy
            x, y = x1, y1
            while True:
                put(x, y, color)
                if x == x2 and y == y2:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x += sx
                if e2 <= dx:
                    err += dx
                    y += sy

        if kind == "grip":
            for x in (5, 11):
                for y in (4, 8, 12):
                    for dx in (0, 1):
                        for dy in (0, 1):
                            put(x + dx, y + dy, "#555555")
        elif kind == "search":
            center_x, center_y, radius = 7, 7, 5
            points = [
                (center_x + radius, center_y),
                (center_x + 4, center_y + 3),
                (center_x + 2, center_y + 5),
                (center_x - 2, center_y + 5),
                (center_x - 4, center_y + 3),
                (center_x - radius, center_y),
                (center_x - 4, center_y - 3),
                (center_x - 2, center_y - 5),
                (center_x + 2, center_y - 5),
                (center_x + 4, center_y - 3),
            ]
            for index, point in enumerate(points):
                next_point = points[(index + 1) % len(points)]
                line(point[0], point[1], next_point[0], next_point[1])
            line(11, 11, 15, 15)
            line(12, 11, 15, 14)
        elif kind == "restore":
            line(4, 4, 14, 4)
            line(14, 4, 14, 14)
            line(14, 14, 4, 14)
            line(4, 14, 4, 4)
        elif kind == "close":
            line(5, 5, 13, 13)
            line(6, 5, 13, 12)
            line(13, 5, 5, 13)
            line(12, 5, 5, 12)
        else:
            line(3, 6, 15, 6)
            line(15, 6, 15, 12)
            line(15, 12, 3, 12)
            line(3, 12, 3, 6)
            line(6, 9, 12, 9)
        return image

    def create_compact_widgets(self):
        self.compact_frame = tk.Frame(self.root)

        self.compact_bar = tk.Frame(self.compact_frame)
        self.compact_bar.pack(fill=tk.X, padx=1, pady=1)

        self.compact_grip = tk.Label(
            self.compact_bar,
            image=self.grip_image,
            cursor="fleur",
            bd=0,
            relief=tk.FLAT
        )
        self.compact_grip.pack(side=tk.LEFT, padx=(0, 1))
        self.compact_grip.bind("<ButtonPress-1>", self.start_compact_drag)
        self.compact_grip.bind("<B1-Motion>", self.drag_compact_window)

        self.compact_search_entry = tk.Entry(self.compact_bar, width=10)
        self.compact_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 1))
        self.compact_search_entry.bind("<Return>", lambda event: self.compact_search_files())

        self.compact_search_button = tk.Button(
            self.compact_bar,
            image=self.search_image,
            width=24,
            height=22,
            command=self.compact_search_files
        )
        self.compact_search_button.pack(side=tk.LEFT, padx=(0, 1))

        self.compact_restore_button = tk.Button(
            self.compact_bar,
            image=self.restore_image,
            width=24,
            height=22,
            command=self.restore_normal_mode
        )
        self.compact_restore_button.pack(side=tk.LEFT)

        self.compact_close_button = tk.Button(
            self.compact_bar,
            image=self.close_image,
            width=24,
            height=22,
            command=self.close_app
        )
        self.compact_close_button.pack(side=tk.LEFT, padx=(1, 0))

        self.compact_width_grip = tk.Label(
            self.compact_bar,
            width=1,
            height=1,
            cursor="sb_h_double_arrow",
            bg="#e6e6e6",
            fg="#555555",
            text="▶",
            font=("TkDefaultFont", 7),
            bd=0,
            padx=0,
            pady=0
        )
        self.compact_width_grip.pack(side=tk.LEFT, padx=(3, 0), fill=tk.Y)
        self.compact_width_grip.bind("<ButtonPress-1>", self.start_compact_width_resize)
        self.compact_width_grip.bind("<B1-Motion>", self.resize_compact_width)

        self.compact_result_frame = tk.Frame(self.compact_frame)
        self.compact_result_header_frame = tk.Frame(self.compact_result_frame)
        self.compact_reveal_button = tk.Button(
            self.compact_result_header_frame,
            text="参照",
            width=5,
            command=self.reveal_compact_file
        )
        self.compact_reveal_button.pack(side=tk.LEFT, padx=(1, 0), pady=(0, 1))
        self.compact_result_header = tk.Button(
            self.compact_result_header_frame,
            text="検索結果",
            anchor="w",
            command=self.toggle_compact_results
        )
        self.compact_result_header.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(1, 1), pady=(0, 1))
        self.compact_result_header_frame.pack(fill=tk.X)

        self.compact_result_body = tk.Frame(self.compact_result_frame)
        self.compact_result_listbox = tk.Listbox(self.compact_result_body, height=8)
        self.compact_result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        compact_scrollbar = tk.Scrollbar(self.compact_result_body, orient=tk.VERTICAL)
        compact_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.compact_result_listbox.config(yscrollcommand=compact_scrollbar.set)
        compact_scrollbar.config(command=self.compact_result_listbox.yview)
        self.compact_result_listbox.bind("<Double-1>", self.open_compact_file)

        self.compact_resize_grip = tk.Label(
            self.compact_result_body,
            text="◢",
            cursor="size_nw_se",
            fg="#555555"
        )
        self.compact_resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self.compact_resize_grip.bind("<ButtonPress-1>", self.start_compact_resize)
        self.compact_resize_grip.bind("<B1-Motion>", self.resize_compact_window)

    def apply_always_on_top(self):
        self.root.attributes("-topmost", bool(self.always_on_top_var.get()))

    def toggle_always_on_top(self):
        self.apply_always_on_top()
        self.save_config(show_message=False)

    def get_configured_compact_result_direction(self):
        direction = self.config.get("compact_result_direction", "自動")
        if direction not in COMPACT_RESULT_DIRECTION_LABELS:
            return "自動"
        return direction

    def get_configured_search_target_label(self):
        mode = self.config.get("search_target", "file")
        for label, label_mode in SEARCH_TARGET_LABEL_MODES.items():
            if label_mode == mode:
                return label
        return "ファイル名検索"

    def on_compact_result_direction_change(self, *args):
        direction = self.compact_result_direction_var.get()
        if direction not in COMPACT_RESULT_DIRECTION_LABELS:
            direction = "自動"
            self.compact_result_direction_var.set(direction)
        self.config["compact_result_direction"] = direction
        if getattr(self, "compact_mode", False):
            self.update_compact_geometry()
        self.save_config(show_message=False)

    def get_search_target_mode(self):
        return SEARCH_TARGET_LABEL_MODES.get(self.search_target_var.get(), "file")

    def toggle_multiple_folder_selection(self):
        if not self.multiple_folder_var.get():
            active_folder = self.get_active_folder_path()
            self.config["selected_folder_paths"] = [active_folder] if active_folder else []
        else:
            selected = self.get_selected_folder_paths()
            if not selected:
                active_folder = self.get_active_folder_path()
                self.config["selected_folder_paths"] = [active_folder] if active_folder else []
        self.render_registered_folders()
        self.save_config(show_message=False)

    def load_compact_state(self):
        state = self.config.get("compact_state", {})
        if not isinstance(state, dict):
            state = {}
        width = self.safe_int(state.get("width"), COMPACT_DEFAULT_WIDTH)
        height = self.safe_int(state.get("height"), COMPACT_COLLAPSED_HEIGHT)
        x = self.safe_int(state.get("x"), 10)
        y = self.safe_int(state.get("y"), 10)
        self.compact_position = (x, y)
        self.compact_size = (max(COMPACT_MIN_WIDTH, width), max(COMPACT_COLLAPSED_HEIGHT, height))
        self.compact_results_expanded = bool(state.get("expanded", False))
        self.compact_manual_resized = bool(state.get("manual_resized", False))
        self.compact_visible_result_rows = max(1, min(30, self.safe_int(state.get("visible_rows"), 1)))
        self.compact_result_listbox.config(height=self.compact_visible_result_rows)
        self.compact_search_entry.delete(0, tk.END)
        self.compact_search_entry.insert(0, state.get("query", ""))

    def save_compact_state(self):
        if not hasattr(self, "compact_search_entry"):
            return
        x, y = self.compact_position or (max(0, self.root.winfo_x()), max(0, self.root.winfo_y()))
        width, height = self.compact_size or (self.root.winfo_width(), self.root.winfo_height())
        if self.compact_mode and self.compact_results_expanded:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
        self.config["compact_state"] = {
            "x": int(x),
            "y": int(y),
            "width": int(max(COMPACT_MIN_WIDTH, width)),
            "height": int(max(COMPACT_COLLAPSED_HEIGHT, height)),
            "expanded": bool(self.compact_results_expanded),
            "manual_resized": bool(self.compact_manual_resized),
            "visible_rows": int(max(1, min(30, self.compact_visible_result_rows))),
            "query": self.compact_search_entry.get()
        }

    def safe_int(self, value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def close_app(self):
        self.save_compact_state()
        self.save_config(show_message=False)
        self.root.destroy()

    def enter_compact_mode(self):
        if self.compact_mode:
            return
        self.normal_geometry = self.root.geometry()
        self.load_compact_state()
        self.compact_mode = True
        self.root.overrideredirect(True)
        self.root.deiconify()
        self.root.title("フォルダ内検索 - ミニ検索")
        for frame in self.main_frames:
            frame.pack_forget()
        self.compact_frame.pack(fill=tk.BOTH, expand=True)
        if self.search_entry.get().strip():
            self.compact_search_entry.delete(0, tk.END)
            self.compact_search_entry.insert(0, self.search_entry.get())
        self.compact_search_entry.focus_set()
        self.compact_result_body.pack_forget()
        if self.compact_result_listbox.size() > 0 or self.compact_result_header.cget("text").startswith("検索結果"):
            self.compact_result_frame.pack(fill=tk.BOTH, expand=True)
            if self.compact_results_expanded:
                if self.compact_result_listbox.size() > 0:
                    self.compact_result_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))
                else:
                    self.compact_result_body.pack_forget()
        else:
            self.compact_result_frame.pack_forget()
            self.compact_results_expanded = False
        self.root.resizable(True, False)
        self.apply_always_on_top()
        self.update_compact_geometry()

    def restore_normal_mode(self):
        if not self.compact_mode:
            return
        self.save_compact_state()
        self.save_config(show_message=False)
        self.compact_mode = False
        self.root.overrideredirect(False)
        self.compact_frame.pack_forget()
        for frame in self.main_frames:
            if frame in (self.keyword_listbox, self.result_frame):
                frame.pack(pady=5, padx=5, fill=tk.BOTH if frame == self.result_frame else tk.X, expand=(frame == self.result_frame))
            elif frame == self.status_frame:
                frame.pack(pady=2, padx=5, fill=tk.X)
            elif frame == self.option_frame:
                frame.pack(pady=5, fill=tk.X)
            elif frame == self.folder_list_frame:
                frame.pack(pady=2, padx=5, fill=tk.X)
            else:
                frame.pack(pady=5, padx=5, fill=tk.X)
        self.root.title("File Search Tool")
        self.root.resizable(True, True)
        if self.normal_geometry:
            self.root.geometry(self.normal_geometry)
        else:
            self.adjust_window_height()
        self.apply_always_on_top()

    def update_compact_geometry(self):
        default_width = COMPACT_DEFAULT_WIDTH
        default_collapsed_height = COMPACT_COLLAPSED_HEIGHT
        default_expanded_height = self.get_compact_expanded_height()
        width, height = self.compact_size or (default_width, default_collapsed_height)
        width = max(COMPACT_MIN_WIDTH, width)
        if self.compact_results_expanded:
            height = max(default_expanded_height, height) if self.compact_manual_resized else default_expanded_height
        else:
            height = default_collapsed_height
        if self.compact_position is None:
            self.compact_position = (max(0, self.root.winfo_x()), max(0, self.root.winfo_y()))
        direction = self.get_compact_result_direction(height)
        self.arrange_compact_layout(direction)
        x, bar_y = self.compact_position
        x = max(0, min(x, self.root.winfo_screenwidth() - width))
        if self.compact_results_expanded and direction == "up":
            y = bar_y - (height - default_collapsed_height)
        else:
            y = bar_y
        y = max(0, min(y, self.root.winfo_screenheight() - height))
        if self.compact_results_expanded and direction == "up":
            bar_y = y + height - default_collapsed_height
        else:
            bar_y = y
        self.compact_position = (x, bar_y)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def get_compact_result_direction(self, expanded_height):
        direction = self.compact_result_direction_var.get() if hasattr(self, "compact_result_direction_var") else "自動"
        if direction == "上":
            self.compact_result_direction = "up"
            return "up"
        if direction == "下":
            self.compact_result_direction = "down"
            return "down"
        bar_y = self.compact_position[1] if self.compact_position else self.root.winfo_y()
        screen_height = self.root.winfo_screenheight()
        needs_up = bar_y + expanded_height > screen_height
        self.compact_result_direction = "up" if needs_up else "down"
        return self.compact_result_direction

    def arrange_compact_layout(self, direction):
        self.compact_bar.pack_forget()
        self.compact_result_frame.pack_forget()
        has_result_header = self.compact_result_header.cget("text").startswith("検索結果")
        if self.compact_results_expanded and has_result_header and direction == "up":
            self.compact_result_frame.pack(fill=tk.BOTH, expand=True)
            self.compact_bar.pack(fill=tk.X, padx=1, pady=1)
        else:
            self.compact_bar.pack(fill=tk.X, padx=1, pady=1)
            if self.compact_results_expanded and has_result_header:
                self.compact_result_frame.pack(fill=tk.BOTH, expand=True)

    def get_compact_expanded_height(self):
        self.root.update_idletasks()
        body_height = self.compact_result_body.winfo_reqheight() if self.compact_result_listbox.size() > 0 else 0
        return self.compact_bar.winfo_reqheight() + self.compact_result_header_frame.winfo_reqheight() + body_height + 4

    def compact_search_files(self):
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, self.compact_search_entry.get())
        self.search_files()

    def display_compact_results(self, results):
        self.compact_result_listbox.delete(0, tk.END)
        self.compact_result_paths = []
        self.compact_visible_result_rows = max(1, min(len(results), 30))
        self.compact_result_listbox.config(height=self.compact_visible_result_rows)
        for result in results:
            self.compact_result_paths.append(result)
            self.compact_result_listbox.insert(tk.END, self.compact_display_name(result))
        self.compact_result_header.config(text=f"検索結果 {len(results)}件")
        if self.compact_mode:
            self.compact_results_expanded = True
            self.compact_manual_resized = False
            self.compact_size = (self.root.winfo_width() or COMPACT_DEFAULT_WIDTH, self.get_compact_expanded_height())
            if len(results) > 0:
                self.compact_result_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))
            else:
                self.compact_result_body.pack_forget()
            self.update_compact_geometry()

    def compact_display_name(self, path):
        normalized = os.path.normpath(path).replace('/', '\\')
        name = os.path.basename(normalized.rstrip("\\"))
        if name:
            return name
        return normalized

    def toggle_compact_results(self):
        self.compact_results_expanded = not self.compact_results_expanded
        if self.compact_results_expanded:
            if not self.compact_manual_resized:
                self.compact_size = (self.root.winfo_width() or COMPACT_DEFAULT_WIDTH, self.get_compact_expanded_height())
            if self.compact_result_listbox.size() > 0:
                self.compact_result_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))
            else:
                self.compact_result_body.pack_forget()
        else:
            self.compact_result_body.pack_forget()
        self.update_compact_geometry()

    def start_compact_drag(self, event):
        bar_y = self.compact_position[1] if self.compact_position else self.root.winfo_y()
        self.compact_drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - bar_y)

    def drag_compact_window(self, event):
        if not self.compact_drag_offset:
            return
        offset_x, offset_y = self.compact_drag_offset
        x = event.x_root - offset_x
        y = event.y_root - offset_y
        self.compact_position = (x, y)
        self.update_compact_geometry()

    def start_compact_resize(self, event):
        self.compact_resize_start = (
            event.x_root,
            event.y_root,
            self.root.winfo_width(),
            self.root.winfo_height()
        )

    def start_compact_width_resize(self, event):
        self.compact_width_resize_start = (
            event.x_root,
            self.root.winfo_width(),
            self.root.winfo_height()
        )

    def resize_compact_width(self, event):
        if not self.compact_width_resize_start:
            return
        start_x, start_width, start_height = self.compact_width_resize_start
        width = max(COMPACT_MIN_WIDTH, start_width + event.x_root - start_x)
        height = start_height if self.compact_results_expanded else COMPACT_COLLAPSED_HEIGHT
        self.compact_size = (width, height)
        self.update_compact_geometry()

    def resize_compact_window(self, event):
        if not self.compact_resize_start:
            return
        start_x, start_y, start_width, start_height = self.compact_resize_start
        width = max(COMPACT_MIN_WIDTH, start_width + event.x_root - start_x)
        min_height = self.get_compact_expanded_height() if self.compact_results_expanded else COMPACT_COLLAPSED_HEIGHT
        height = max(min_height, start_height + event.y_root - start_y)
        self.compact_size = (width, height)
        self.compact_manual_resized = True
        self.update_compact_geometry()

    def open_compact_file(self, event=None):
        file_path = self.get_selected_compact_result_path()
        if not file_path:
            return
        try:
            if self.path_exists_safe(file_path):
                if os.name == 'nt':
                    self.startfile_safe(file_path)
                else:
                    subprocess.call(['open' if os.name == 'darwin' else 'xdg-open', file_path])
            else:
                raise FileNotFoundError(file_path)
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルを開けませんでした: {e}")

    def reveal_compact_file(self):
        file_path = self.get_selected_compact_result_path()
        if file_path:
            self.reveal_path(file_path)

    def get_selected_compact_result_path(self):
        selection = self.compact_result_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "ファイルを選択してください。")
            return None
        index = selection[0]
        if index >= len(self.compact_result_paths):
            return None
        return os.path.normpath(self.compact_result_paths[index]).replace('/', '\\')

    def get_local_networks(self):
        networks = self.get_local_networks_from_ipconfig()
        if not networks:
            networks = self.get_local_networks_from_powershell()
        return networks

    def get_local_networks_from_powershell(self):
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-NetIPConfiguration | "
                "Where-Object {$_.IPv4Address -and $_.NetAdapter.Status -eq 'Up'} | "
                "ForEach-Object {[PSCustomObject]@{"
                "InterfaceAlias=$_.InterfaceAlias;"
                "IPv4=$_.IPv4Address.IPAddress;"
                "PrefixLength=$_.IPv4Address.PrefixLength;"
                "Gateway=($_.IPv4DefaultGateway.NextHop -join ',')"
                "}} | ConvertTo-Json -Compress"
            )
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5, encoding="utf-8")
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]

            networks = []
            for item in data:
                ip = item.get("IPv4")
                prefix = item.get("PrefixLength")
                if not ip or prefix is None:
                    continue
                try:
                    interface = ipaddress.ip_interface(f"{ip}/{prefix}")
                except ValueError:
                    continue
                networks.append({
                    "adapter": item.get("InterfaceAlias", ""),
                    "ip": ip,
                    "network": str(interface.network),
                    "gateway": item.get("Gateway", "")
                })
            return networks
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PowerShellでのネットワーク取得に失敗: {e}")
            return []

    def get_local_networks_from_ipconfig(self):
        try:
            result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5, encoding="cp932", errors="ignore")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ipconfigでのネットワーク取得に失敗: {e}")
            return []

        networks = []
        adapter = ""
        ip = None
        mask = None
        gateway_candidates = []
        for line in result.stdout.splitlines() + [""]:
            stripped = line.strip()
            if stripped.endswith(":") and not line.startswith(" "):
                if ip and mask:
                    self.append_ipconfig_network(networks, adapter, ip, mask, self.select_ipv4_gateway(gateway_candidates))
                adapter = stripped.rstrip(":")
                ip = None
                mask = None
                gateway_candidates = []
                continue
            if "IPv4" in stripped and ":" in stripped:
                ip = stripped.split(":", 1)[1].strip()
            elif ("Subnet Mask" in stripped or "サブネット マスク" in stripped) and ":" in stripped:
                mask = stripped.split(":", 1)[1].strip()
            elif ("Default Gateway" in stripped or "デフォルト ゲートウェイ" in stripped) and ":" in stripped:
                gateway_value = stripped.split(":", 1)[1].strip()
                if gateway_value:
                    gateway_candidates.append(gateway_value)
            elif gateway_candidates and stripped and ip and mask:
                try:
                    ipaddress.ip_address(stripped)
                    gateway_candidates.append(stripped)
                except ValueError:
                    pass

        return networks

    def select_ipv4_gateway(self, gateway_candidates):
        for gateway in gateway_candidates:
            try:
                if ipaddress.ip_address(gateway).version == 4:
                    return gateway
            except ValueError:
                continue
        return gateway_candidates[0] if gateway_candidates else ""

    def append_ipconfig_network(self, networks, adapter, ip, mask, gateway):
        try:
            network = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
        except ValueError:
            return
        if network.version != 4 or ip.startswith("127.") or ip.startswith("169.254."):
            return
        networks.append({
            "adapter": adapter,
            "ip": ip,
            "network": str(network),
            "gateway": gateway
        })

    def refresh_local_networks(self, show_message=True):
        networks = self.get_local_networks()
        if not networks:
            self.network_var.set("取得できませんでした")
            if show_message:
                messagebox.showwarning("警告", "ローカルネットワークのアドレスを取得できませんでした。")
            return

        display_items = []
        for item in networks:
            parts = [item["network"], f"IP {item['ip']}"]
            if item.get("gateway"):
                parts.append(f"GW {item['gateway']}")
            if item.get("adapter"):
                parts.append(item["adapter"])
            display_items.append(" / ".join(parts))
        self.network_var.set("  |  ".join(display_items))

    def copy_network_address(self):
        value = self.network_var.get().strip()
        if not value or value == "取得できませんでした":
            messagebox.showwarning("警告", "コピーできるネットワークアドレスがありません。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        messagebox.showinfo("成功", "ローカルネットワーク情報をコピーしました。")

    def normalize_path(self, path):
        """パスを正規化する。ネットワークパスの\\を確実に保護し、二重化を防ぐ"""
        if not path:
            return path

        # ネットワークパスを保護
        is_network_path = path.startswith('\\\\')
        if is_network_path:
            path = path.replace('\\\\', '__NETWORK__', 1)

        # ディレクトリとファイル名に分解
        dirname = os.path.dirname(path) or ''
        basename = os.path.basename(path)
        basename = unicodedata.normalize('NFKC', basename).replace('\u3000', ' ').strip()
        dirname = os.path.normpath(dirname).replace('/', '\\')
        normalized_path = os.path.join(dirname, basename).replace('/', '\\')

        # ネットワークパスの復元
        if is_network_path:
            normalized_path = normalized_path.replace('__NETWORK__', '\\\\', 1)
            if not normalized_path.startswith('\\\\'):
                normalized_path = '\\\\' + normalized_path.lstrip('\\')

        # 余計なバックスラッシュを削除
        while normalized_path.startswith('\\\\\\'):
            normalized_path = normalized_path[1:]

        if getattr(self, "debug_paths", False):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] 入力パス: {path}")
            print(f"[{timestamp}] 正規化されたパス: {normalized_path}")
        return normalized_path

    def load_config(self):
        self.config = {
            "folder_path": "",
            "active_folder_path": "",
            "registered_folders": [],
            "include_subfolders": True,
            "max_depth": 0,
            "filename_only": True,
            "search_target": "file",
            "multiple_folder_selection": False,
            "selected_folder_paths": [],
            "always_on_top": False,
            "compact_result_direction": "自動",
            "compact_state": {},
            "folder_keyword_rules": [],
            "folder_keyword_rules_by_path": {}
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config.update(json.load(f))
            self.config["folder_path"] = self.normalize_path(self.config.get("folder_path", ""))
            self.config["active_folder_path"] = self.normalize_path(self.config.get("active_folder_path", ""))
            self.config["registered_folders"] = [
                self.normalize_path(path) for path in self.config.get("registered_folders", [])
                if path
            ]
        except FileNotFoundError:
            pass
        if self.config["folder_path"] and self.config["folder_path"] not in self.config["registered_folders"]:
            self.config["registered_folders"].insert(0, self.config["folder_path"])
        if not self.config["active_folder_path"]:
            self.config["active_folder_path"] = self.config["folder_path"]
        if self.config.get("compact_result_direction") not in COMPACT_RESULT_DIRECTION_LABELS:
            self.config["compact_result_direction"] = "自動"
        if self.config.get("search_target") not in ("file", "folder", "both"):
            self.config["search_target"] = "file" if self.config.get("filename_only", True) else "both"
        self.config["selected_folder_paths"] = [
            self.normalize_path(path) for path in self.config.get("selected_folder_paths", [])
            if path
        ]
        self.config["folder_keyword_rules"] = self.normalize_keyword_rules(
            self.config.get("folder_keyword_rules", [])
        )
        self.config["folder_keyword_rules_by_path"] = self.normalize_keyword_rule_map(
            self.config.get("folder_keyword_rules_by_path", {})
        )

    def normalize_keyword_rule_map(self, rule_map):
        normalized_map = {}
        if not isinstance(rule_map, dict):
            return normalized_map
        for path, rules in rule_map.items():
            normalized_path = self.normalize_path(path)
            if normalized_path:
                normalized_map[normalized_path] = self.normalize_keyword_rules(rules)
        return normalized_map

    def normalize_keyword_rules(self, rules):
        normalized_rules = []
        seen = set()
        for rule in rules:
            if isinstance(rule, dict):
                mode = rule.get("mode", "exclude")
                keyword = rule.get("keyword", "")
            else:
                mode = "exclude"
                keyword = str(rule)
            mode = self.normalize_keyword_mode(mode)
            keyword = self.normalize_search_text(keyword)
            if not keyword:
                continue
            key = (mode, keyword)
            if key not in seen:
                normalized_rules.append({"mode": mode, "keyword": keyword})
                seen.add(key)
        return normalized_rules

    def normalize_keyword_mode(self, mode):
        if mode in ("folder_include", "include", "参照", "フォルダ参照"):
            return "folder_include"
        if mode in ("file_exclude", "ファイル除外"):
            return "file_exclude"
        if mode in ("file_include", "ファイル参照"):
            return "file_include"
        return "folder_exclude"

    def format_keyword_rule(self, rule):
        mode_label = KEYWORD_MODE_LABELS.get(self.normalize_keyword_mode(rule.get("mode")), "フォルダ除外")
        return f"{mode_label}: {rule.get('keyword', '')}"

    def parse_keyword_rule_text(self, text):
        if ":" not in text:
            return {"mode": "folder_exclude", "keyword": self.normalize_search_text(text)}
        mode_label, keyword = text.split(":", 1)
        mode = KEYWORD_LABEL_MODES.get(mode_label.strip(), self.normalize_keyword_mode(mode_label.strip()))
        return {"mode": mode, "keyword": self.normalize_search_text(keyword)}

    def get_keyword_rules_from_listbox(self):
        return self.normalize_keyword_rules(
            self.parse_keyword_rule_text(item) for item in self.keyword_listbox.get(0, tk.END)
        )

    def get_active_folder_path(self):
        return self.normalize_path(self.active_folder_var.get() or self.folder_entry.get())

    def get_active_folder_keyword_rules(self):
        active_path = self.get_active_folder_path()
        return self.get_keyword_rules_for_folder_path(active_path)

    def get_keyword_rules_for_folder_path(self, folder_path):
        active_path = self.normalize_path(folder_path)
        rule_map = self.config.get("folder_keyword_rules_by_path", {})
        if active_path in rule_map:
            return self.normalize_keyword_rules(rule_map[active_path])
        if not rule_map:
            return self.normalize_keyword_rules(self.config.get("folder_keyword_rules", []))
        return []

    def save_active_folder_keyword_rules(self):
        if self.loading_keyword_rules:
            return
        active_path = self.normalize_path(self.current_keyword_folder_path or self.get_active_folder_path())
        if not active_path or not hasattr(self, "keyword_listbox"):
            return
        self.config.setdefault("folder_keyword_rules_by_path", {})
        self.config["folder_keyword_rules_by_path"][active_path] = self.get_keyword_rules_from_listbox()
        self.config["folder_keyword_rules"] = self.config["folder_keyword_rules_by_path"][active_path]

    def load_keyword_rules_for_folder(self, path):
        self.loading_keyword_rules = True
        self.keyword_listbox.delete(0, tk.END)
        normalized_path = self.normalize_path(path)
        rule_map = self.config.get("folder_keyword_rules_by_path", {})
        if normalized_path in rule_map:
            rules = rule_map[normalized_path]
        elif not rule_map:
            rules = self.config.get("folder_keyword_rules", [])
        else:
            rules = []
        for rule in self.normalize_keyword_rules(rules):
            self.keyword_listbox.insert(tk.END, self.format_keyword_rule(rule))
        self.current_keyword_folder_path = normalized_path
        self.loading_keyword_rules = False

    def is_recycle_folder_path(self, path):
        path_parts = [part.lower() for part in self.normalize_path(path).split("\\") if part]
        return any(part in DEFAULT_EXCLUDE_FOLDER_NAMES for part in path_parts)

    def folder_path_has_keyword(self, folder_path, keywords):
        parts = [
            self.normalize_search_text(part)
            for part in self.normalize_path(folder_path).split("\\")
            if part
        ]
        return any(keyword in part for keyword in keywords for part in parts)

    def is_excluded_path(self, path, keyword_rules):
        if self.is_recycle_folder_path(path):
            return True
        exclude_keywords = [rule["keyword"] for rule in keyword_rules if rule["mode"] == "folder_exclude"]
        return self.folder_path_has_keyword(path, exclude_keywords)

    def is_referenced_path(self, path, keyword_rules):
        include_keywords = [rule["keyword"] for rule in keyword_rules if rule["mode"] == "folder_include"]
        if not include_keywords:
            return True
        return self.folder_path_has_keyword(path, include_keywords)

    def file_name_has_keyword(self, file_path, keywords):
        file_name = self.normalize_search_text(os.path.basename(file_path))
        return any(keyword in file_name for keyword in keywords)

    def is_file_excluded(self, file_path, keyword_rules):
        exclude_keywords = [rule["keyword"] for rule in keyword_rules if rule["mode"] == "file_exclude"]
        return self.file_name_has_keyword(file_path, exclude_keywords)

    def is_file_referenced(self, file_path, keyword_rules):
        include_keywords = [rule["keyword"] for rule in keyword_rules if rule["mode"] == "file_include"]
        if not include_keywords:
            return True
        return self.file_name_has_keyword(file_path, include_keywords)

    def save_config(self, show_message=True):
        self.save_active_folder_keyword_rules()
        self.config["folder_path"] = self.normalize_path(self.folder_entry.get())
        self.config["active_folder_path"] = self.active_folder_var.get() or self.config["folder_path"]
        self.config["registered_folders"] = self.get_registered_folders()
        self.config["include_subfolders"] = self.subfolder_var.get()
        self.config["max_depth"] = self.max_depth_var.get()
        self.config["search_target"] = self.get_search_target_mode()
        self.config["filename_only"] = self.get_search_target_mode() == "file"
        self.config["multiple_folder_selection"] = self.multiple_folder_var.get()
        self.config["selected_folder_paths"] = self.get_selected_folder_paths()
        self.config["always_on_top"] = self.always_on_top_var.get()
        self.config["compact_result_direction"] = self.compact_result_direction_var.get()
        self.save_compact_state()
        self.config["folder_keyword_rules"] = self.get_active_folder_keyword_rules()
        self.config.pop("exclude_folders", None)
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            if show_message:
                messagebox.showinfo("成功", "設定を保存しました。")
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")

    def load_cache(self):
        self.cache = {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
        except FileNotFoundError:
            pass

    def save_cache(self, folder_path, file_list):
        self.cache[folder_path] = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": file_list
        }
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4, ensure_ascii=False)
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] キャッシュ保存エラー: {e}")

    def get_cached_file_list(self, cache_key):
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict):
            return cached.get("files", []), cached.get("created_at", "")
        if isinstance(cached, list):
            return cached, ""
        return None, ""

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, self.normalize_path(folder))

    def get_registered_folders(self):
        folders = []
        seen = set()
        for folder in self.config.get("registered_folders", []):
            normalized = self.normalize_path(folder)
            key = os.path.normcase(normalized)
            if normalized and key not in seen:
                folders.append(normalized)
                seen.add(key)
        return folders

    def get_configured_selected_folder_paths(self):
        folders = self.get_registered_folders()
        folder_keys = {os.path.normcase(folder) for folder in folders}
        selected = []
        seen = set()
        for path in self.config.get("selected_folder_paths", []):
            normalized = self.normalize_path(path)
            key = os.path.normcase(normalized)
            if normalized and key in folder_keys and key not in seen:
                selected.append(normalized)
                seen.add(key)
        multiple_selection = getattr(self, "multiple_folder_var", None)
        is_multiple = multiple_selection.get() if multiple_selection is not None else self.config.get("multiple_folder_selection", False)
        if not selected and not is_multiple:
            active = self.normalize_path(self.active_folder_var.get() or self.config.get("active_folder_path", ""))
            if active and os.path.normcase(active) in folder_keys:
                selected.append(active)
        return selected

    def get_selected_folder_paths(self):
        if hasattr(self, "selected_folder_vars") and self.selected_folder_vars:
            selected = [
                path for path, var in self.selected_folder_vars.items()
                if var.get()
            ]
        else:
            selected = self.config.get("selected_folder_paths", [])
        if not self.multiple_folder_var.get():
            active = self.get_active_folder_path()
            return [active] if active else []
        folders = self.get_registered_folders()
        folder_keys = {os.path.normcase(folder) for folder in folders}
        normalized_selected = []
        seen = set()
        for path in selected:
            normalized = self.normalize_path(path)
            key = os.path.normcase(normalized)
            if normalized and key in folder_keys and key not in seen:
                normalized_selected.append(normalized)
                seen.add(key)
        return normalized_selected

    def render_registered_folders(self):
        for frame in self.folder_row_frames:
            frame.destroy()
        self.folder_row_frames = []
        self.selected_folder_vars = {}

        self.config["registered_folders"] = self.get_registered_folders()
        current_folder = self.normalize_path(self.folder_entry.get())
        active_folder = self.active_folder_var.get() or self.config.get("active_folder_path", "")
        if not active_folder and current_folder:
            active_folder = current_folder
        self.active_folder_var.set(active_folder)
        selected_folders = self.get_configured_selected_folder_paths()
        selected_keys = {os.path.normcase(path) for path in selected_folders}
        multiple_selection = self.multiple_folder_var.get()

        for folder in self.config["registered_folders"]:
            row = tk.Frame(self.folder_list_frame)
            row.pack(fill=tk.X, pady=1)
            folder_key = os.path.normcase(folder)
            is_active = folder_key == os.path.normcase(active_folder)
            is_selected = folder_key in selected_keys if multiple_selection else is_active
            toggle_bg = "#9be28f" if is_selected else "#d9d9d9"
            path_bg = "white" if is_selected else "#e6e6e6"
            if multiple_selection:
                var = tk.BooleanVar(value=is_selected)
                self.selected_folder_vars[folder] = var
                toggle = tk.Checkbutton(
                    row,
                    text="選択",
                    variable=var,
                    indicatoron=False,
                    width=6,
                    bg=toggle_bg,
                    selectcolor="#9be28f",
                    activebackground="#b7efac",
                    command=lambda path=folder: self.toggle_registered_folder(path)
                )
            else:
                toggle = tk.Radiobutton(
                    row,
                    text="選択",
                    variable=self.active_folder_var,
                    value=folder,
                    indicatoron=False,
                    width=6,
                    bg=toggle_bg,
                    selectcolor="#9be28f",
                    activebackground="#b7efac",
                    command=lambda path=folder: self.select_registered_folder(path)
                )
            toggle.pack(side=tk.LEFT)
            path_var = tk.StringVar(value=folder)
            path_entry = tk.Entry(
                row,
                textvariable=path_var,
                state="readonly",
                readonlybackground=path_bg,
                fg="black"
            )
            path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            tk.Button(
                row,
                text="削除",
                command=lambda path=folder: self.delete_registered_folder(path)
            ).pack(side=tk.LEFT, padx=5)
            self.folder_row_frames.append(row)
        self.adjust_window_height()

    def adjust_window_height(self):
        if getattr(self, "compact_mode", False):
            self.update_compact_geometry()
            return
        base_height = 650
        row_height = 28
        folder_count = len(self.config.get("registered_folders", []))
        height = base_height + max(0, folder_count - 1) * row_height
        width = max(self.root.winfo_width(), 600)
        self.root.geometry(f"{width}x{height}")

    def add_registered_folder(self):
        self.save_active_folder_keyword_rules()
        folder = self.normalize_path(self.folder_entry.get())
        if not folder:
            messagebox.showerror("エラー", "追加するフォルダを入力してください。")
            return
        if not os.path.exists(folder):
            messagebox.showerror("エラー", "有効なフォルダを選択してください。")
            return

        folders = self.get_registered_folders()
        if os.path.normcase(folder) not in [os.path.normcase(path) for path in folders]:
            folders.append(folder)
        self.config["registered_folders"] = folders
        if self.multiple_folder_var.get():
            selected = self.get_selected_folder_paths()
            if os.path.normcase(folder) not in [os.path.normcase(path) for path in selected]:
                selected.append(folder)
            self.config["selected_folder_paths"] = selected
        self.active_folder_var.set(folder)
        self.select_registered_folder(folder, save=False)
        self.render_registered_folders()
        self.save_config(show_message=False)

    def select_registered_folder(self, path, save=True):
        self.save_active_folder_keyword_rules()
        normalized = self.normalize_path(path)
        self.folder_entry.delete(0, tk.END)
        self.folder_entry.insert(0, normalized)
        self.active_folder_var.set(normalized)
        self.config["folder_path"] = normalized
        self.config["active_folder_path"] = normalized
        self.load_keyword_rules_for_folder(normalized)
        self.render_registered_folders()
        if save:
            self.save_config(show_message=False)

    def toggle_registered_folder(self, path):
        self.save_active_folder_keyword_rules()
        normalized = self.normalize_path(path)
        selected = self.get_selected_folder_paths()
        if not selected:
            if normalized in self.selected_folder_vars:
                self.selected_folder_vars[normalized].set(True)
            messagebox.showwarning("警告", "少なくとも1つのフォルダを選択してください。")
            selected = [normalized]
        self.folder_entry.delete(0, tk.END)
        self.folder_entry.insert(0, normalized)
        self.active_folder_var.set(normalized)
        self.config["folder_path"] = normalized
        self.config["active_folder_path"] = normalized
        self.load_keyword_rules_for_folder(normalized)
        self.config["selected_folder_paths"] = selected
        self.render_registered_folders()
        self.save_config(show_message=False)

    def delete_registered_folder(self, path):
        self.save_active_folder_keyword_rules()
        normalized_delete = os.path.normcase(self.normalize_path(path))
        delete_path = self.normalize_path(path)
        folders = [
            folder for folder in self.get_registered_folders()
            if os.path.normcase(folder) != normalized_delete
        ]
        self.config["registered_folders"] = folders
        self.config.get("folder_keyword_rules_by_path", {}).pop(delete_path, None)
        self.config["selected_folder_paths"] = [
            folder for folder in self.get_selected_folder_paths()
            if os.path.normcase(folder) != normalized_delete
        ]

        if os.path.normcase(self.active_folder_var.get()) == normalized_delete:
            next_folder = folders[0] if folders else ""
            self.active_folder_var.set(next_folder)
            self.folder_entry.delete(0, tk.END)
            if next_folder:
                self.folder_entry.insert(0, next_folder)
            self.config["folder_path"] = next_folder
            self.config["active_folder_path"] = next_folder
            self.load_keyword_rules_for_folder(next_folder)

        self.render_registered_folders()
        self.save_config(show_message=False)

    def add_keyword_rule(self):
        keyword = self.normalize_search_text(self.keyword_entry.get())
        if not keyword:
            messagebox.showerror("エラー", "キーワードを入力してください。")
            return
        mode = KEYWORD_LABEL_MODES.get(self.keyword_mode_var.get(), "folder_exclude")
        rule = {"mode": mode, "keyword": keyword}
        display = self.format_keyword_rule(rule)
        if display in self.keyword_listbox.get(0, tk.END):
            messagebox.showwarning("警告", "このキーワード設定は既にあります。")
            return
        self.keyword_listbox.insert(tk.END, display)
        self.keyword_entry.delete(0, tk.END)
        self.save_active_folder_keyword_rules()

    def delete_keyword_rule(self):
        selection = self.keyword_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "削除するキーワード設定を選択してください。")
            return
        for index in reversed(selection):
            self.keyword_listbox.delete(index)
        self.save_active_folder_keyword_rules()

    def clear_keyword_rules(self):
        self.keyword_listbox.delete(0, tk.END)
        self.save_active_folder_keyword_rules()
        messagebox.showinfo("成功", "キーワード設定をクリアしました。")

    def validate_folder_path(self):
        folder_paths = self.validate_folder_paths()
        if not folder_paths:
            return None
        return folder_paths[0]

    def validate_folder_paths(self):
        folder_paths = self.get_selected_folder_paths() if self.multiple_folder_var.get() else [self.normalize_path(self.folder_entry.get())]
        folder_paths = [path for path in folder_paths if path]
        if not folder_paths:
            messagebox.showerror("エラー", "有効なフォルダを選択してください。")
            return None
        valid_paths = []
        for folder_path in folder_paths:
            if not os.path.exists(folder_path):
                messagebox.showerror("エラー", f"有効なフォルダを選択してください。\n{folder_path}")
                return None
            if not os.access(folder_path, os.R_OK):
                messagebox.showerror("エラー", f"フォルダにアクセスできません。権限を確認してください。\n{folder_path}")
                return None
            valid_paths.append(folder_path)
        return valid_paths

    def get_search_settings(self, folder_paths):
        self.save_active_folder_keyword_rules()
        return {
            "folder_paths": folder_paths,
            "include_subfolders": self.subfolder_var.get(),
            "max_depth": self.max_depth_var.get(),
            "search_target": self.get_search_target_mode()
        }

    def build_cache_key(self, settings):
        folder_keys = []
        for folder_path in settings["folder_paths"]:
            keyword_rules = self.get_keyword_rules_for_folder_path(folder_path)
            keyword_key = "_".join(
                f"{rule['mode']}:{rule['keyword']}" for rule in keyword_rules
            )
            folder_keys.append(f"{folder_path}:{keyword_key}")
        return f"{'|'.join(folder_keys)}_{settings['include_subfolders']}_{settings['max_depth']}_{settings['search_target']}"

    def set_busy(self, busy, status=None):
        state = tk.DISABLED if busy else tk.NORMAL
        self.search_button.config(state=state)
        if hasattr(self, "compact_search_button"):
            self.compact_search_button.config(state=state)
        self.index_button.config(state=state)
        if hasattr(self, "compact_mode_button"):
            self.compact_mode_button.config(state=state)
        self.cancel_button.config(state=tk.NORMAL if busy else tk.DISABLED)
        if status:
            self.status_var.set(status)

    def start_worker(self, status, worker_func):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("警告", "処理中です。停止するか完了まで待ってください。")
            return
        self.cancel_event.clear()
        while not self.result_queue.empty():
            self.result_queue.get_nowait()
        self.set_busy(True, status)
        self.worker_thread = threading.Thread(target=worker_func, daemon=True)
        self.worker_thread.start()
        self.root.after(100, self.poll_worker_result)

    def poll_worker_result(self):
        try:
            while True:
                message_type, payload = self.result_queue.get_nowait()
                if message_type == "status":
                    self.status_var.set(payload)
                elif message_type == "done":
                    self.finish_worker(payload)
                    return
                elif message_type == "cancelled":
                    self.set_busy(False, payload)
                    return
                elif message_type == "error":
                    self.set_busy(False, "エラー")
                    messagebox.showerror("エラー", payload)
                    return
        except queue.Empty:
            pass

        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(100, self.poll_worker_result)
        else:
            self.set_busy(False, "待機中")

    def finish_worker(self, payload):
        self.set_busy(False, payload.get("status", "完了"))
        results = payload.get("results")
        if results is not None:
            self.result_listbox.delete(0, tk.END)
            for result in results:
                self.result_listbox.insert(tk.END, result)
            if hasattr(self, "compact_result_listbox"):
                self.display_compact_results(results)

    def cancel_current_task(self):
        self.cancel_event.set()
        self.status_var.set("停止中...")

    def is_within_depth(self, file_path, folder_path, max_depth):
        if max_depth <= 0:
            return True
        relative_path = file_path[len(folder_path):].lstrip("\\/")
        return relative_path.count(os.sep) <= max_depth

    def normalize_search_text(self, text):
        normalized = unicodedata.normalize('NFKC', text)
        normalized = normalized.replace('\u3000', ' ')
        normalized = normalized.replace('\u301c', '~').replace('\uff5e', '~')
        return normalized.strip().lower()

    def path_matches(self, path, search_terms):
        target = os.path.basename(path)
        target = self.normalize_search_text(target)
        return all(self.normalize_search_text(term) in target for term in search_terms)

    def scan_file_list(self, settings):
        include_subfolders = settings["include_subfolders"]
        max_depth = settings["max_depth"]
        search_target = settings["search_target"]
        include_files = search_target in ("file", "both")
        include_folders = search_target in ("folder", "both")
        file_list = []
        scanned_dirs = 0
        scanned_files = 0

        for folder_path in settings["folder_paths"]:
            keyword_rules = self.get_keyword_rules_for_folder_path(folder_path)
            if include_subfolders:
                walker = os.walk(folder_path)
            else:
                try:
                    entries = os.listdir(folder_path)
                except OSError:
                    entries = []
                dirs = [entry for entry in entries if os.path.isdir(os.path.join(folder_path, entry))]
                files = [entry for entry in entries if os.path.isfile(os.path.join(folder_path, entry))]
                walker = [(folder_path, dirs, files)]

            for root, dirs, files in walker:
                if self.cancel_event.is_set():
                    return file_list, scanned_files, True

                norm_root = self.normalize_path(root)
                if self.is_excluded_path(norm_root, keyword_rules):
                    continue

                dirs[:] = [
                    directory for directory in dirs
                    if not self.is_excluded_path(os.path.join(root, directory), keyword_rules)
                ]

                if max_depth > 0:
                    depth = norm_root[len(folder_path):].lstrip("\\/").count(os.sep)
                    if depth > max_depth:
                        dirs[:] = []
                        continue

                if include_folders and self.is_referenced_path(norm_root, keyword_rules):
                    file_list.append(norm_root)
                    if not include_subfolders:
                        for directory in dirs:
                            directory_path = self.normalize_path(os.path.join(root, directory))
                            if self.is_referenced_path(directory_path, keyword_rules):
                                file_list.append(directory_path)

                scanned_dirs += 1
                scanned_files += len(files)
                if scanned_dirs % 50 == 0:
                    self.result_queue.put(("status", f"スキャン中... {scanned_dirs}フォルダ / {scanned_files}ファイル"))

                if include_files:
                    for file in files:
                        if self.cancel_event.is_set():
                            return file_list, scanned_files, True
                        file_path = os.path.normpath(os.path.join(root, file)).replace('/', '\\')
                        if (
                            os.path.isfile(file_path)
                            and not self.is_excluded_path(os.path.dirname(file_path), keyword_rules)
                            and self.is_referenced_path(os.path.dirname(file_path), keyword_rules)
                            and not self.is_file_excluded(file_path, keyword_rules)
                            and self.is_file_referenced(file_path, keyword_rules)
                        ):
                            file_list.append(file_path)

        return file_list, scanned_files, False

    def update_index(self):
        folder_paths = self.validate_folder_paths()
        if not folder_paths:
            return
        settings = self.get_search_settings(folder_paths)
        cache_key = self.build_cache_key(settings)

        def worker():
            try:
                start_time = time.time()
                file_list, scanned_files, cancelled = self.scan_file_list(settings)
                if cancelled:
                    self.result_queue.put(("cancelled", "停止しました"))
                    return
                self.save_cache(cache_key, file_list)
                elapsed = time.time() - start_time
                self.result_queue.put(("done", {
                    "status": f"インデックス更新完了: {len(file_list)}件 / {elapsed:.2f}秒"
                }))
            except Exception as e:
                self.result_queue.put(("error", f"インデックス更新中にエラーが発生しました: {e}"))

        self.start_worker("インデックス更新中...", worker)

    def search_files(self):
        folder_paths = self.validate_folder_paths()
        if not folder_paths:
            return

        search_terms = self.search_entry.get().strip().split()
        if not search_terms:
            messagebox.showerror("エラー", "検索語を入力してください。")
            return

        settings = self.get_search_settings(folder_paths)
        cache_key = self.build_cache_key(settings)
        cached_file_list, created_at = self.get_cached_file_list(cache_key)
        self.result_listbox.delete(0, tk.END)

        def worker():
            try:
                start_time = time.time()
                if cached_file_list is None:
                    self.result_queue.put(("status", "キャッシュなし。NASをスキャン中..."))
                    file_list, scanned_files, cancelled = self.scan_file_list(settings)
                    if cancelled:
                        self.result_queue.put(("cancelled", "停止しました"))
                        return
                    self.save_cache(cache_key, file_list)
                    source = "新規スキャン"
                else:
                    file_list = cached_file_list
                    scanned_files = len(file_list)
                    source = f"キャッシュ {created_at}" if created_at else "キャッシュ"

                results = []
                for index, file_path in enumerate(file_list, start=1):
                    if self.cancel_event.is_set():
                        self.result_queue.put(("cancelled", "停止しました"))
                        return
                    if self.path_matches(file_path, search_terms):
                        results.append(file_path)
                    if index % 5000 == 0:
                        self.result_queue.put(("status", f"検索中... {index}/{len(file_list)}件"))

                elapsed = time.time() - start_time
                self.result_queue.put(("done", {
                    "results": results,
                    "status": f"{source}: {len(results)}件 / 対象{scanned_files}件 / {elapsed:.2f}秒"
                }))
            except Exception as e:
                self.result_queue.put(("error", f"検索中にエラーが発生しました: {e}"))

        self.start_worker("検索中...", worker)

    def get_selected_result_path(self):
        selection = self.result_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "ファイルを選択してください。")
            return None
        file_path = self.result_listbox.get(selection[0]).strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] リストボックスから取得したパス: {file_path}")
        normalized_path = os.path.normpath(file_path).replace('/', '\\')
        print(f"[{timestamp}] 正規化後のパス: {normalized_path}")
        return normalized_path

    def to_windows_extended_path(self, path):
        if os.name != 'nt' or not path:
            return path
        if path.startswith("\\\\?\\"):
            return path
        if path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + path.lstrip("\\")
        if len(path) >= 248 and len(path) > 1 and path[1] == ":":
            return "\\\\?\\" + path
        return path

    def path_exists_safe(self, path):
        return os.path.exists(path) or os.path.exists(self.to_windows_extended_path(path))

    def path_isdir_safe(self, path):
        return os.path.isdir(path) or os.path.isdir(self.to_windows_extended_path(path))

    def startfile_safe(self, path):
        try:
            os.startfile(path)
        except OSError:
            os.startfile(self.to_windows_extended_path(path))

    def reveal_in_explorer(self, path):
        try:
            subprocess.Popen(["explorer.exe", "/select," + path])
            return True
        except OSError:
            return False

    def open_parent_folder(self, path):
        parent_path = os.path.dirname(path)
        if parent_path and self.path_exists_safe(parent_path):
            if os.name == 'nt':
                self.startfile_safe(parent_path)
            else:
                subprocess.call(['open' if os.name == 'darwin' else 'xdg-open', parent_path])
            return True
        return False

    def open_file(self, event=None):
        normalized_path = self.get_selected_result_path()
        if not normalized_path:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if self.path_exists_safe(normalized_path):
                if os.name == 'nt':
                    self.startfile_safe(normalized_path)
                else:
                    subprocess.call(['open' if os.name == 'darwin' else 'xdg-open', normalized_path])
            else:
                raise FileNotFoundError(f"ファイルが存在しません: {normalized_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"[{timestamp}] ファイルを開けませんでした: {e}\nパス: {normalized_path}")

    def reveal_file(self):
        normalized_path = self.get_selected_result_path()
        if not normalized_path:
            return
        self.reveal_path(normalized_path)

    def reveal_path(self, normalized_path):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if self.path_exists_safe(normalized_path):
                if os.name == 'nt':
                    if self.path_isdir_safe(normalized_path):
                        self.startfile_safe(normalized_path)
                    else:
                        if not self.reveal_in_explorer(normalized_path):
                            self.open_parent_folder(normalized_path)
                else:
                    target_path = normalized_path if self.path_isdir_safe(normalized_path) else os.path.dirname(normalized_path)
                    subprocess.call(['open' if os.name == 'darwin' else 'xdg-open', target_path])
            else:
                if not self.open_parent_folder(normalized_path):
                    raise FileNotFoundError(f"ファイルが存在しません: {normalized_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"[{timestamp}] ファイルを参照できませんでした: {e}\nパス: {normalized_path}")

if __name__ == "__main__":
    if not tk._default_root:
        root = tk.Tk()
        app = FileSearchTool(root)
        root.geometry("600x650")
        root.mainloop()
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 既存のTkインスタンスが検出されました。")
