import glob
import csv
import hashlib
import json
import math
import os
import pickle
import re
import shutil
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from fontTools.ttLib import TTCollection, TTFont
from PIL import Image, ImageDraw, ImageFont, ImageTk


class CombinedOverlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("画像一括 文字・画像挿入ツール レイヤー2実験4")
        self.cache_file = "font_cache.pkl"
        self.settings_file = "text_image_group_settings.json"
        self.settings = self.load_settings()

        self.folder_path = None
        self.image_files = []
        self.current_image_index = 0
        self.preview_window = None
        self.preview_window_pos = None
        self.preview_scale = 1.0
        self.preview_max_width = 1000
        self.preview_max_height = 700
        self.preview_scale_job = None
        self.preview_update_job = None

        self.selected_text_color = (0, 0, 0)
        self.selected_bg_color = (255, 255, 255)
        self.icon_image = None
        self.icon_path = None

        self.text_relative_x = 0.5
        self.text_relative_y = 0.5
        self.text_offset_x = None
        self.text_offset_y = None
        self.icon_relative_x = 0.5
        self.icon_relative_y = 0.5
        self.icon_offset_x = None
        self.icon_offset_y = None

        self.drag_target = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.preview_items = {}
        self.preview_center_offsets = {}
        self.preview_original_size = None
        self.variable_csv_path = ""
        self.variable_columns = []
        self.variable_rows_by_file = {}
        self.suppress_preview_update = False
        self.last_preview_text = ""
        self.text_layers = []
        self.icon_layers = []
        self.active_text_layer = 0
        self.active_icon_layer = 0
        self.active_layer_kind = "text"
        self.switching_layer = False
        self.layer_stack_order = ["icon0", "text0"]
        self.layer_rank_values = []

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        self.build_folder_ui()
        self.build_tabs()
        self.build_action_ui()
        self.initialize_layers()

    def build_folder_ui(self):
        frame = tk.Frame(self.root)
        frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        frame.columnconfigure(1, weight=1)

        tk.Label(frame, text="画像フォルダ:").grid(row=0, column=0, padx=5, pady=5)
        self.folder_path_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.folder_path_var, width=60).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(frame, text="参照", command=self.select_folder).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(frame, text="変数CSV:").grid(row=1, column=0, padx=5, pady=5)
        self.variable_csv_var = tk.StringVar(value=self.settings.get("variable_csv_path", ""))
        tk.Entry(frame, textvariable=self.variable_csv_var).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(frame, text="参照", command=self.select_variable_csv).grid(row=1, column=2, padx=5, pady=5)
        tk.Button(frame, text="環境変数", command=self.show_variable_help).grid(row=1, column=3, padx=5, pady=5)
        if self.variable_csv_var.get():
            self.load_variable_csv(show_error=False)

    def build_tabs(self):
        self.layer_tabs = ttk.Notebook(self.root)
        self.layer_tabs.grid(row=1, column=0, padx=5, pady=(5, 0), sticky="ew")
        self.layer_tab_meta = []
        self.create_layer_tab_markers()
        self.layer_tabs.bind("<<NotebookTabChanged>>", self.on_layer_tab_changed)

        self.editor_frame = tk.Frame(self.root)
        self.editor_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        self.editor_frame.columnconfigure(0, weight=1)
        self.editor_frame.rowconfigure(0, weight=1)

        self.text_tab = tk.Frame(self.editor_frame)
        self.icon_tab = tk.Frame(self.editor_frame)
        self.output_tab = tk.Frame(self.editor_frame)

        self.build_text_tab()
        self.build_icon_tab()
        self.build_output_tab()
        self.show_editor_panel("text")

    def create_layer_tab_markers(self):
        self.text_tab_marker = tk.PhotoImage(width=8, height=8)
        self.icon_tab_marker = tk.PhotoImage(width=8, height=8)
        self.text_tab_marker.put("#f2b84b", to=(0, 0, 8, 8))
        self.icon_tab_marker.put("#4d9de0", to=(0, 0, 8, 8))

    def build_text_tab(self):
        self.text_tab.columnconfigure(1, weight=1)

        self.text_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(self.text_tab, text="文字を挿入する", variable=self.text_enabled, command=self.schedule_preview_update).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.layer_rank_var = tk.StringVar(value="4: 最前面")
        tk.Label(self.text_tab, text="重ね順:").grid(row=0, column=1, padx=5, pady=5, sticky="e")
        self.text_layer_rank_list = ttk.Combobox(
            self.text_tab,
            textvariable=self.layer_rank_var,
            values=self.layer_rank_values,
            state="readonly",
            width=10,
        )
        self.text_layer_rank_list.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.text_layer_rank_list.bind("<<ComboboxSelected>>", self.on_layer_rank_changed)
        self.delete_text_layer_btn = tk.Button(self.text_tab, text="レイヤー削除", command=self.delete_active_text_layer, width=12)
        self.delete_text_layer_btn.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        tk.Label(self.text_tab, text="挿入テキスト:").grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        self.text_entry = tk.Text(self.text_tab, height=3, width=45)
        self.text_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.text_entry.bind("<KeyRelease>", self.schedule_text_preview_update)
        text_action_frame = tk.Frame(self.text_tab)
        text_action_frame.grid(row=1, column=3, padx=5, pady=5, sticky="n")
        tk.Button(text_action_frame, text="クリア", command=self.clear_text, width=12).pack(fill="x", pady=(0, 4))
        tk.Button(text_action_frame, text="縦書き", command=self.convert_to_vertical, width=12).pack(fill="x")

        self.font_dict = self.get_system_fonts()
        tk.Label(self.text_tab, text="フォント:").grid(row=2, column=0, padx=5, pady=5)
        self.font_list = ttk.Combobox(self.text_tab, values=list(self.font_dict.keys()), state="readonly")
        if self.font_dict:
            self.font_list.set("ＭＳ ゴシック" if "ＭＳ ゴシック" in self.font_dict else list(self.font_dict.keys())[0])
        self.font_list.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.font_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)
        tk.Button(self.text_tab, text="フォント再取得", command=self.refresh_fonts).grid(row=2, column=2, padx=5, pady=5)

        tk.Label(self.text_tab, text="フォントサイズ:").grid(row=3, column=0, padx=5, pady=5)
        self.font_size = tk.Scale(self.text_tab, from_=10, to=255, orient=tk.HORIZONTAL, length=220, command=self.schedule_preview_update)
        self.font_size.set(20)
        self.font_size.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.text_tab, text="文字色:").grid(row=4, column=0, padx=5, pady=5)
        self.text_color_chip = tk.Canvas(self.text_tab, width=24, height=24)
        self.text_color_chip.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        self.text_color_chip.create_rectangle(0, 0, 24, 24, fill="#000000", outline="#000000")
        self.text_color_chip.bind("<Button-1>", lambda _event: self.choose_text_color())
        self.text_color_chip.config(cursor="hand2")

        tk.Label(self.text_tab, text="文字揃え:").grid(row=5, column=0, padx=5, pady=5)
        self.alignment = tk.StringVar(value="中央揃え")
        self.alignment_list = ttk.Combobox(
            self.text_tab, textvariable=self.alignment, values=["左揃え", "中央揃え", "右揃え"], state="readonly"
        )
        self.alignment_list.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        self.alignment_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)

        tk.Label(self.text_tab, text="文字透明度:").grid(row=6, column=0, padx=5, pady=5)
        self.text_alpha = tk.Scale(self.text_tab, from_=0, to=255, orient=tk.HORIZONTAL, command=self.schedule_preview_update)
        self.text_alpha.set(0)
        self.text_alpha.grid(row=6, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.text_tab, text="回転角度:").grid(row=7, column=0, padx=5, pady=5)
        self.text_rotation = tk.Scale(self.text_tab, from_=-180, to=180, orient=tk.HORIZONTAL, command=self.schedule_preview_update)
        self.text_rotation.set(0)
        self.text_rotation.grid(row=7, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.text_tab, text="文字の基準:").grid(row=8, column=0, padx=5, pady=5)
        self.text_anchor_mode = tk.StringVar(value="背景画像")
        self.text_anchor_list = ttk.Combobox(
            self.text_tab,
            textvariable=self.text_anchor_mode,
            values=["背景画像", "貼り付け画像の中央"],
            state="readonly"
        )
        self.text_anchor_list.grid(row=8, column=1, padx=5, pady=5, sticky="ew")
        self.text_anchor_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)

        self.text_bg_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(self.text_tab, text="背景色を設定", variable=self.text_bg_enabled, command=self.toggle_text_bg).grid(
            row=9, column=0, padx=5, pady=5, sticky="w"
        )
        self.bg_color_chip = tk.Canvas(self.text_tab, width=24, height=24)
        self.bg_color_chip.grid(row=9, column=1, padx=5, pady=5, sticky="w")
        self.bg_color_chip.create_rectangle(0, 0, 24, 24, fill="#ffffff", outline="#ffffff")
        self.bg_color_chip.bind("<Button-1>", lambda _event: self.choose_bg_color())
        self.bg_color_chip.config(cursor="hand2")

        tk.Label(self.text_tab, text="背景幅:").grid(row=10, column=0, padx=5, pady=5)
        self.bg_width_var = tk.DoubleVar(value=1.0)
        self.bg_width = tk.Scale(
            self.text_tab,
            from_=0.5,
            to=3.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.bg_width_var,
            state="disabled",
            command=self.on_text_bg_scale_change,
        )
        self.bg_width.grid(row=10, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.text_tab, text="背景高さ:").grid(row=11, column=0, padx=5, pady=5)
        self.bg_height_var = tk.DoubleVar(value=1.0)
        self.bg_height = tk.Scale(
            self.text_tab,
            from_=0.5,
            to=3.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.bg_height_var,
            state="disabled",
            command=self.on_text_bg_scale_change,
        )
        self.bg_height.grid(row=11, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.text_tab, text="背景透明度:").grid(row=12, column=0, padx=5, pady=5)
        self.bg_alpha = tk.Scale(self.text_tab, from_=0, to=255, orient=tk.HORIZONTAL, state="disabled", command=self.on_text_bg_scale_change)
        self.bg_alpha.set(0)
        self.bg_alpha.grid(row=12, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        self.build_position_ui(self.text_tab, 13, "text")

    def build_icon_tab(self):
        self.icon_tab.columnconfigure(1, weight=1)

        self.icon_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(self.icon_tab, text="画像を挿入する", variable=self.icon_enabled, command=self.schedule_preview_update).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        tk.Label(self.icon_tab, text="重ね順:").grid(row=0, column=1, padx=5, pady=5, sticky="e")
        self.icon_layer_rank_list = ttk.Combobox(
            self.icon_tab,
            textvariable=self.layer_rank_var,
            values=self.layer_rank_values,
            state="readonly",
            width=10,
        )
        self.icon_layer_rank_list.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.icon_layer_rank_list.bind("<<ComboboxSelected>>", self.on_layer_rank_changed)
        self.delete_icon_layer_btn = tk.Button(self.icon_tab, text="レイヤー削除", command=self.delete_active_icon_layer, width=12)
        self.delete_icon_layer_btn.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        tk.Label(self.icon_tab, text="貼り付け画像:").grid(row=1, column=0, padx=5, pady=5)
        self.icon_path_var = tk.StringVar()
        tk.Entry(self.icon_tab, textvariable=self.icon_path_var, width=45).grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        tk.Button(self.icon_tab, text="参照", command=self.select_icon_image).grid(row=1, column=3, padx=5, pady=5)

        tk.Label(self.icon_tab, text="スケール基準:").grid(row=2, column=0, padx=5, pady=5)
        self.icon_scale_mode = tk.StringVar(value="貼り付け画像")
        self.icon_scale_mode_list = ttk.Combobox(
            self.icon_tab, textvariable=self.icon_scale_mode, values=["貼り付け画像", "カンバスサイズ"], state="readonly"
        )
        self.icon_scale_mode_list.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.icon_scale_mode_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)

        tk.Label(self.icon_tab, text="拡大縮小 (%):").grid(row=3, column=0, padx=5, pady=5)
        self.icon_scale = tk.Scale(self.icon_tab, from_=10, to=200, orient=tk.HORIZONTAL, command=self.schedule_preview_update)
        self.icon_scale.set(25)
        self.icon_scale.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.icon_tab, text="透明度 (%):").grid(row=4, column=0, padx=5, pady=5)
        self.icon_alpha = tk.Scale(self.icon_tab, from_=0, to=99, orient=tk.HORIZONTAL, command=self.schedule_preview_update)
        self.icon_alpha.set(0)
        self.icon_alpha.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.icon_tab, text="回転角度:").grid(row=5, column=0, padx=5, pady=5)
        self.icon_rotation = tk.Scale(self.icon_tab, from_=-180, to=180, orient=tk.HORIZONTAL, command=self.schedule_preview_update)
        self.icon_rotation.set(0)
        self.icon_rotation.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        self.build_position_ui(self.icon_tab, 6, "icon")

    def build_position_ui(self, parent, start_row, prefix):
        tk.Label(parent, text="位置指定モード:").grid(row=start_row, column=0, padx=5, pady=5)
        mode_var = tk.StringVar(value="比率設定")
        mode_list = ttk.Combobox(parent, textvariable=mode_var, values=["比率設定", "ピクセル設定"], state="readonly")
        mode_list.grid(row=start_row, column=1, padx=5, pady=5, sticky="w")
        mode_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)

        tk.Label(parent, text="起点位置:").grid(row=start_row + 1, column=0, padx=5, pady=5)
        origin_list = ttk.Combobox(parent, values=["左上", "右上", "中央", "左下", "右下"], state="readonly")
        origin_list.set("左上")
        origin_list.grid(row=start_row + 1, column=1, padx=5, pady=5, sticky="w")
        origin_list.bind("<<ComboboxSelected>>", self.schedule_preview_update)

        if prefix == "text":
            self.text_position_mode = mode_var
            self.text_origin_list = origin_list
        else:
            self.icon_position_mode = mode_var
            self.icon_origin_list = origin_list

    def build_output_tab(self):
        self.output_tab.columnconfigure(1, weight=1)

        tk.Label(self.output_tab, text="JPG保存品質:").grid(row=0, column=0, padx=5, pady=5)
        self.quality = tk.Scale(self.output_tab, from_=1, to=100, orient=tk.HORIZONTAL)
        self.quality.set(95)
        self.quality.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(self.output_tab, text="出力ファイル接尾辞:").grid(row=1, column=0, padx=5, pady=5)
        self.suffix_entry = tk.Entry(self.output_tab)
        self.suffix_entry.insert(0, "_combined")
        self.suffix_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.resize_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(self.output_tab, text="解像度を変更する", variable=self.resize_enabled, command=self.toggle_resize_entries).grid(
            row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w"
        )

        resize_frame = tk.Frame(self.output_tab)
        resize_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        tk.Label(resize_frame, text="横:").pack(side=tk.LEFT, padx=5)
        self.resize_width_var = tk.StringVar()
        self.resize_width_entry = tk.Entry(resize_frame, textvariable=self.resize_width_var, width=10, state="disabled")
        self.resize_width_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(resize_frame, text="縦:").pack(side=tk.LEFT, padx=5)
        self.resize_height_var = tk.StringVar()
        self.resize_height_entry = tk.Entry(resize_frame, textvariable=self.resize_height_var, width=10, state="disabled")
        self.resize_height_entry.pack(side=tk.LEFT, padx=5)
        self.keep_aspect = tk.BooleanVar(value=True)
        tk.Checkbutton(resize_frame, text="アスペクト比保持", variable=self.keep_aspect).pack(side=tk.LEFT, padx=10)
        self.resize_width_entry.bind("<KeyRelease>", self.update_resize_aspect)
        self.resize_height_entry.bind("<KeyRelease>", self.update_resize_aspect)

        tk.Label(self.output_tab, text="プレビュー倍率:").grid(row=4, column=0, padx=5, pady=5)
        self.preview_scale_percent = tk.Scale(
            self.output_tab, from_=10, to=100, orient=tk.HORIZONTAL, command=self.on_preview_scale_change
        )
        self.preview_scale_percent.set(self.settings.get("preview_scale_percent", 100))
        self.preview_scale_percent.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(self.output_tab, text="ドラッグ対象:").grid(row=5, column=0, padx=5, pady=5)
        tk.Label(self.output_tab, text="文字タブは文字、画像タブは画像").grid(row=5, column=1, padx=5, pady=5, sticky="w")

        template_frame = tk.Frame(self.output_tab)
        template_frame.grid(row=6, column=0, columnspan=2, padx=5, pady=10, sticky="w")
        tk.Button(template_frame, text="テンプレート保存", command=self.save_template, width=18).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(template_frame, text="テンプレート読込", command=self.load_template, width=18).pack(side=tk.LEFT)

    def build_action_ui(self):
        frame = tk.Frame(self.root)
        frame.grid(row=3, column=0, padx=5, pady=10)
        tk.Button(frame, text="プレビュー", command=self.preview_image, width=18, height=2).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="実行", command=self.process_images, width=18, height=2).grid(row=0, column=1, padx=5)

    def on_main_tab_changed(self, _event=None):
        if self.switching_layer:
            return
        self.schedule_preview_update()

    def show_editor_panel(self, kind):
        for frame in (self.text_tab, self.icon_tab, self.output_tab):
            frame.grid_remove()
        if kind == "text":
            self.text_tab.grid(row=0, column=0, sticky="nsew")
            self.update_delete_layer_buttons()
            self.update_layer_rank_control()
        elif kind == "icon":
            self.icon_tab.grid(row=0, column=0, sticky="nsew")
            self.update_delete_layer_buttons()
            self.update_layer_rank_control()
        else:
            self.output_tab.grid(row=0, column=0, sticky="nsew")

    def layer_key(self, kind, index):
        return f"{kind}{index}"

    def get_active_layer_key(self):
        if self.active_layer_kind == "icon":
            return self.layer_key("icon", self.active_icon_layer)
        if self.active_layer_kind == "text":
            return self.layer_key("text", self.active_text_layer)
        return None

    def update_layer_rank_values(self):
        total = len(self.text_layers) + len(self.icon_layers)
        values = []
        for i in range(total):
            if i == 0:
                values.append("1: 最背面")
            elif i == total - 1:
                values.append(f"{i + 1}: 最前面")
            else:
                values.append(str(i + 1))
        self.layer_rank_values = values
        if hasattr(self, "text_layer_rank_list"):
            self.text_layer_rank_list.configure(values=self.layer_rank_values)
        if hasattr(self, "icon_layer_rank_list"):
            self.icon_layer_rank_list.configure(values=self.layer_rank_values)

    def update_layer_rank_control(self):
        self.update_layer_rank_values()
        key = self.get_active_layer_key()
        if not key or key not in self.layer_stack_order or not self.layer_rank_values:
            return
        rank_index = self.layer_stack_order.index(key)
        if rank_index >= len(self.layer_rank_values):
            return
        self.layer_rank_var.set(self.layer_rank_values[rank_index])

    def update_delete_layer_buttons(self):
        if hasattr(self, "delete_text_layer_btn"):
            self.delete_text_layer_btn.config(state="normal" if len(self.text_layers) > 1 else "disabled")
        if hasattr(self, "delete_icon_layer_btn"):
            self.delete_icon_layer_btn.config(state="normal" if len(self.icon_layers) > 1 else "disabled")

    def on_layer_rank_changed(self, _event=None):
        if self.switching_layer or self.suppress_preview_update:
            return
        key = self.get_active_layer_key()
        if not key or key not in self.layer_stack_order:
            return
        try:
            new_index = self.layer_rank_values.index(self.layer_rank_var.get())
        except ValueError:
            self.update_layer_rank_control()
            return
        old_index = self.layer_stack_order.index(key)
        if old_index == new_index:
            return
        self.layer_stack_order[old_index], self.layer_stack_order[new_index] = (
            self.layer_stack_order[new_index],
            self.layer_stack_order[old_index],
        )
        self.update_layer_rank_control()
        self.schedule_preview_update()

    def rebuild_layer_tabs(self, select_kind=None, select_index=None):
        if not hasattr(self, "layer_tabs"):
            return
        previous_switching = self.switching_layer
        self.switching_layer = True
        try:
            for tab_id in self.layer_tabs.tabs():
                self.layer_tabs.forget(tab_id)
            self.layer_tab_meta = []
            for i in range(len(self.text_layers)):
                self.layer_tabs.add(
                    tk.Frame(self.layer_tabs),
                    text=f"  文字{i + 1}  ",
                    image=self.text_tab_marker,
                    compound=tk.LEFT,
                )
                self.layer_tab_meta.append(("text", i))
            self.layer_tabs.add(tk.Frame(self.layer_tabs), text="+文字")
            self.layer_tab_meta.append(("add_text", None))
            for i in range(len(self.icon_layers)):
                self.layer_tabs.add(
                    tk.Frame(self.layer_tabs),
                    text=f"  画像{i + 1}  ",
                    image=self.icon_tab_marker,
                    compound=tk.LEFT,
                )
                self.layer_tab_meta.append(("icon", i))
            self.layer_tabs.add(tk.Frame(self.layer_tabs), text="+画像")
            self.layer_tab_meta.append(("add_icon", None))
            self.layer_tabs.add(tk.Frame(self.layer_tabs), text="設定")
            self.layer_tab_meta.append(("output", None))

            if select_kind == "text":
                target = self.layer_tab_meta.index(("text", select_index))
            elif select_kind == "icon":
                target = self.layer_tab_meta.index(("icon", select_index))
            elif select_kind == "output":
                target = self.layer_tab_meta.index(("output", None))
            else:
                target = 0
            self.layer_tabs.select(target)
        finally:
            self.switching_layer = previous_switching

    def normalize_layer_stack_order(self):
        valid_keys = {self.layer_key("text", i) for i in range(len(self.text_layers))}
        valid_keys.update(self.layer_key("icon", i) for i in range(len(self.icon_layers)))
        self.layer_stack_order = [key for key in self.layer_stack_order if key in valid_keys]
        for key in sorted(valid_keys):
            if key not in self.layer_stack_order:
                self.layer_stack_order.append(key)
        self.update_layer_rank_values()

    def add_text_layer(self):
        self.save_active_layer()
        base = self.capture_text_layer() if self.text_layers else {}
        new_layer = dict(base)
        new_layer["text"] = ""
        self.text_layers.append(new_layer)
        self.active_layer_kind = "text"
        self.active_text_layer = len(self.text_layers) - 1
        self.layer_stack_order.append(self.layer_key("text", self.active_text_layer))
        self.normalize_layer_stack_order()
        self.rebuild_layer_tabs("text", self.active_text_layer)
        self.suppress_preview_update = True
        try:
            self.apply_text_layer(new_layer)
            self.show_editor_panel("text")
        finally:
            self.suppress_preview_update = False
        self.root.after_idle(self.focus_text_entry)
        self.schedule_preview_update()

    def add_icon_layer(self):
        self.save_active_layer()
        base = self.capture_icon_layer() if self.icon_layers else {}
        new_layer = dict(base)
        new_layer["path"] = ""
        new_layer["enabled"] = True
        self.icon_layers.append(new_layer)
        self.active_layer_kind = "icon"
        self.active_icon_layer = len(self.icon_layers) - 1
        self.layer_stack_order.append(self.layer_key("icon", self.active_icon_layer))
        self.normalize_layer_stack_order()
        self.rebuild_layer_tabs("icon", self.active_icon_layer)
        self.suppress_preview_update = True
        try:
            self.apply_icon_layer(new_layer)
            self.show_editor_panel("icon")
        finally:
            self.suppress_preview_update = False
        self.schedule_preview_update()

    def shift_layer_keys_after_delete(self, kind, deleted_index):
        shifted = []
        for key in self.layer_stack_order:
            if key.startswith(kind):
                index = int(key[len(kind):])
                if index == deleted_index:
                    continue
                if index > deleted_index:
                    key = self.layer_key(kind, index - 1)
            shifted.append(key)
        self.layer_stack_order = shifted

    def delete_active_text_layer(self):
        if len(self.text_layers) <= 1:
            messagebox.showinfo("確認", "文字レイヤーは最低1つ残します")
            return
        delete_index = self.active_text_layer
        del self.text_layers[delete_index]
        self.shift_layer_keys_after_delete("text", delete_index)
        self.active_text_layer = min(delete_index, len(self.text_layers) - 1)
        self.active_layer_kind = "text"
        self.normalize_layer_stack_order()
        self.rebuild_layer_tabs("text", self.active_text_layer)
        self.suppress_preview_update = True
        try:
            self.apply_text_layer(self.text_layers[self.active_text_layer])
            self.show_editor_panel("text")
        finally:
            self.suppress_preview_update = False
        self.schedule_preview_update()

    def delete_active_icon_layer(self):
        if len(self.icon_layers) <= 1:
            messagebox.showinfo("確認", "画像レイヤーは最低1つ残します")
            return
        delete_index = self.active_icon_layer
        del self.icon_layers[delete_index]
        self.shift_layer_keys_after_delete("icon", delete_index)
        self.active_icon_layer = min(delete_index, len(self.icon_layers) - 1)
        self.active_layer_kind = "icon"
        self.normalize_layer_stack_order()
        self.rebuild_layer_tabs("icon", self.active_icon_layer)
        self.suppress_preview_update = True
        try:
            self.apply_icon_layer(self.icon_layers[self.active_icon_layer])
            self.show_editor_panel("icon")
        finally:
            self.suppress_preview_update = False
        self.schedule_preview_update()

    def focus_text_entry(self):
        if hasattr(self, "text_entry") and self.text_entry.winfo_exists():
            self.text_entry.focus_set()

    def initialize_layers(self):
        text_layer_1 = self.capture_text_layer()
        icon_layer_1 = self.capture_icon_layer()
        self.text_layers = [text_layer_1]
        self.icon_layers = [icon_layer_1]
        self.normalize_layer_stack_order()
        self.rebuild_layer_tabs("text", 0)
        self.sync_layer_tab_selection("text")

    def sync_layer_tab_selection(self, kind):
        if not hasattr(self, "layer_tabs") or self.switching_layer:
            return
        if kind == "text":
            target = self.layer_tab_meta.index(("text", self.active_text_layer))
        elif kind == "icon":
            target = self.layer_tab_meta.index(("icon", self.active_icon_layer))
        else:
            target = self.layer_tab_meta.index(("output", None))
        try:
            if self.layer_tabs.index(self.layer_tabs.select()) != target:
                self.switching_layer = True
                self.layer_tabs.select(target)
                self.root.after_idle(self.finish_layer_switching)
        except tk.TclError:
            pass

    def finish_layer_switching(self):
        self.switching_layer = False

    def on_layer_tab_changed(self, _event=None):
        if self.switching_layer or not self.text_layers or not self.icon_layers:
            return
        try:
            selected = self.layer_tabs.index(self.layer_tabs.select())
        except tk.TclError:
            return
        if selected >= len(self.layer_tab_meta):
            return
        kind, index = self.layer_tab_meta[selected]
        if kind == "add_text":
            self.add_text_layer()
            return
        if kind == "add_icon":
            self.add_icon_layer()
            return
        self.save_active_layer()
        self.suppress_preview_update = True
        self.switching_layer = True
        try:
            if kind == "text":
                self.active_layer_kind = "text"
                self.active_text_layer = index
                self.apply_text_layer(self.text_layers[index])
                self.show_editor_panel("text")
                self.root.after_idle(self.focus_text_entry)
            elif kind == "icon":
                self.active_layer_kind = "icon"
                self.active_icon_layer = index
                self.apply_icon_layer(self.icon_layers[index])
                self.show_editor_panel("icon")
            else:
                self.active_layer_kind = "output"
                self.show_editor_panel("output")
        finally:
            self.switching_layer = False
            self.suppress_preview_update = False
        self.schedule_preview_update()

    def capture_text_layer(self):
        return {
            "enabled": self.text_enabled.get(),
            "text": self.get_text_value(),
            "font": self.font_list.get() if hasattr(self, "font_list") else "",
            "font_size": self.font_size.get(),
            "text_color": self.selected_text_color,
            "alignment": self.alignment.get(),
            "text_alpha": self.text_alpha.get(),
            "rotation": self.text_rotation.get(),
            "anchor_mode": self.text_anchor_mode.get(),
            "bg_enabled": self.text_bg_enabled.get(),
            "bg_color": self.selected_bg_color,
            "bg_width": self.bg_width.get(),
            "bg_height": self.bg_height.get(),
            "bg_alpha": self.bg_alpha.get(),
            "position_mode": self.text_position_mode.get(),
            "origin": self.text_origin_list.get(),
            "relative_x": self.text_relative_x,
            "relative_y": self.text_relative_y,
            "offset_x": self.text_offset_x,
            "offset_y": self.text_offset_y,
        }

    def capture_icon_layer(self):
        return {
            "enabled": self.icon_enabled.get(),
            "path": self.icon_path or self.icon_path_var.get(),
            "scale_mode": self.icon_scale_mode.get(),
            "scale": self.icon_scale.get(),
            "alpha": self.icon_alpha.get(),
            "rotation": self.icon_rotation.get(),
            "position_mode": self.icon_position_mode.get(),
            "origin": self.icon_origin_list.get(),
            "relative_x": self.icon_relative_x,
            "relative_y": self.icon_relative_y,
            "offset_x": self.icon_offset_x,
            "offset_y": self.icon_offset_y,
        }

    def apply_text_layer(self, layer):
        self.text_enabled.set(layer.get("enabled", True))
        self.text_entry.delete("1.0", tk.END)
        self.text_entry.insert("1.0", layer.get("text", ""))
        self.last_preview_text = self.get_text_value()
        if layer.get("font") in self.font_dict:
            self.font_list.set(layer.get("font"))
        self.font_size.set(layer.get("font_size", 20))
        self.selected_text_color = tuple(layer.get("text_color", (0, 0, 0)))
        text_hex = "#{:02x}{:02x}{:02x}".format(*self.selected_text_color)
        self.text_color_chip.delete("all")
        self.text_color_chip.create_rectangle(0, 0, 24, 24, fill=text_hex, outline=text_hex)
        self.alignment.set(layer.get("alignment", "中央揃え"))
        self.text_alpha.set(layer.get("text_alpha", 0))
        self.text_rotation.set(layer.get("rotation", 0))
        self.text_anchor_mode.set(layer.get("anchor_mode", "背景画像"))
        self.text_bg_enabled.set(layer.get("bg_enabled", False))
        self.selected_bg_color = tuple(layer.get("bg_color", (255, 255, 255)))
        bg_hex = "#{:02x}{:02x}{:02x}".format(*self.selected_bg_color)
        self.bg_color_chip.delete("all")
        self.bg_color_chip.create_rectangle(0, 0, 24, 24, fill=bg_hex, outline=bg_hex)
        self.bg_width.config(state="normal")
        self.bg_height.config(state="normal")
        self.bg_alpha.config(state="normal")
        self.bg_width.set(layer.get("bg_width", 1.0))
        self.bg_height.set(layer.get("bg_height", 1.0))
        self.bg_alpha.set(layer.get("bg_alpha", 0))
        self.text_position_mode.set(layer.get("position_mode", "比率設定"))
        self.text_origin_list.set(layer.get("origin", "左上"))
        self.text_relative_x = layer.get("relative_x", 0.5)
        self.text_relative_y = layer.get("relative_y", 0.5)
        self.text_offset_x = layer.get("offset_x")
        self.text_offset_y = layer.get("offset_y")
        self.toggle_text_bg()

    def apply_icon_layer(self, layer):
        self.icon_enabled.set(layer.get("enabled", True))
        self.icon_path = layer.get("path", "")
        self.icon_path_var.set(self.icon_path)
        self.icon_image = None
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                self.icon_image = Image.open(self.icon_path).convert("RGBA")
            except Exception:
                self.icon_image = None
        self.icon_scale_mode.set(layer.get("scale_mode", "貼り付け画像"))
        self.icon_scale.set(layer.get("scale", 25))
        self.icon_alpha.set(layer.get("alpha", 0))
        self.icon_rotation.set(layer.get("rotation", 0))
        self.icon_position_mode.set(layer.get("position_mode", "比率設定"))
        self.icon_origin_list.set(layer.get("origin", "左上"))
        self.icon_relative_x = layer.get("relative_x", 0.5)
        self.icon_relative_y = layer.get("relative_y", 0.5)
        self.icon_offset_x = layer.get("offset_x")
        self.icon_offset_y = layer.get("offset_y")

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            return {}
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Settings save error: {e}")

    def get_script_dir(self):
        return os.path.dirname(os.path.abspath(__file__))

    def get_template_dirs(self):
        base_dir = self.get_script_dir()
        template_dir = os.path.join(base_dir, "templates")
        asset_dir = os.path.join(base_dir, "template_assets")
        return template_dir, asset_dir

    def ensure_template_dirs(self):
        template_dir, asset_dir = self.get_template_dirs()
        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(asset_dir, exist_ok=True)
        return template_dir, asset_dir

    def make_template_asset_path(self, source_path):
        _template_dir, asset_dir = self.ensure_template_dirs()
        ext = os.path.splitext(source_path)[1].lower() or ".png"
        try:
            stat = os.stat(source_path)
            seed = f"{os.path.abspath(source_path)}:{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            seed = os.path.abspath(source_path)
        digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        safe_name = re.sub(r'[\\/:*?"<>|]+', "_", base_name).strip() or "asset"
        filename = f"{safe_name}_{digest}{ext}"
        return os.path.join(asset_dir, filename)

    def prepare_template_icon_layers(self):
        icon_layers = []
        script_dir = self.get_script_dir()
        for layer in self.icon_layers:
            saved_layer = dict(layer)
            path = saved_layer.get("path", "")
            if path and os.path.exists(path):
                try:
                    target_path = self.make_template_asset_path(path)
                    if not os.path.exists(target_path):
                        shutil.copy2(path, target_path)
                    saved_layer["path"] = os.path.relpath(target_path, script_dir).replace("\\", "/")
                except Exception as e:
                    messagebox.showwarning("警告", f"貼り付け画像のコピーに失敗しました\n{path}\n{e}")
            icon_layers.append(saved_layer)
        return icon_layers

    def resolve_template_icon_layers(self, icon_layers):
        script_dir = self.get_script_dir()
        resolved = []
        for layer in icon_layers:
            loaded_layer = dict(layer)
            path = loaded_layer.get("path", "")
            if path and not os.path.isabs(path):
                loaded_layer["path"] = os.path.normpath(os.path.join(script_dir, path))
            resolved.append(loaded_layer)
        return resolved

    def save_template(self):
        self.save_active_layer()
        template_dir, _asset_dir = self.ensure_template_dirs()
        file_path = filedialog.asksaveasfilename(
            initialdir=template_dir,
            defaultextension=".json",
            filetypes=[("テンプレート", "*.json"), ("All files", "*.*")],
            title="テンプレート保存",
        )
        if not file_path:
            return
        data = {
            "version": 1,
            "text_layers": self.text_layers,
            "icon_layers": self.prepare_template_icon_layers(),
            "layer_stack_order": self.layer_stack_order,
            "active_layer_kind": self.active_layer_kind,
            "active_text_layer": self.active_text_layer,
            "active_icon_layer": self.active_icon_layer,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("エラー", f"テンプレート保存に失敗しました\n{e}")
            return
        messagebox.showinfo("保存完了", "テンプレートを保存しました")

    def load_template(self):
        template_dir, _asset_dir = self.ensure_template_dirs()
        file_path = filedialog.askopenfilename(
            initialdir=template_dir,
            filetypes=[("テンプレート", "*.json"), ("All files", "*.*")],
            title="テンプレート読込",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("エラー", f"テンプレート読込に失敗しました\n{e}")
            return

        text_layers = data.get("text_layers") or [self.capture_text_layer()]
        icon_layers = data.get("icon_layers") or [self.capture_icon_layer()]
        self.suppress_preview_update = True
        try:
            self.text_layers = [dict(layer) for layer in text_layers]
            self.icon_layers = self.resolve_template_icon_layers(icon_layers)
            self.layer_stack_order = list(data.get("layer_stack_order", []))
            self.normalize_layer_stack_order()
            self.active_text_layer = min(max(int(data.get("active_text_layer", 0)), 0), len(self.text_layers) - 1)
            self.active_icon_layer = min(max(int(data.get("active_icon_layer", 0)), 0), len(self.icon_layers) - 1)
            self.active_layer_kind = data.get("active_layer_kind", "text")
            if self.active_layer_kind not in ("text", "icon", "output"):
                self.active_layer_kind = "text"
            self.apply_text_layer(self.text_layers[self.active_text_layer])
            self.apply_icon_layer(self.icon_layers[self.active_icon_layer])
            if self.active_layer_kind == "icon":
                self.rebuild_layer_tabs("icon", self.active_icon_layer)
                self.show_editor_panel("icon")
            elif self.active_layer_kind == "output":
                self.rebuild_layer_tabs("output", None)
                self.show_editor_panel("output")
            else:
                self.active_layer_kind = "text"
                self.rebuild_layer_tabs("text", self.active_text_layer)
                self.show_editor_panel("text")
        except Exception as e:
            messagebox.showerror("エラー", f"テンプレートの反映に失敗しました\n{e}")
            return
        finally:
            self.suppress_preview_update = False
        self.schedule_preview_update()

    def select_variable_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not file_path:
            return
        self.variable_csv_var.set(file_path)
        self.load_variable_csv(show_error=True)
        self.schedule_preview_update()

    def read_variable_csv(self, path):
        last_error = None
        for encoding in ("utf-8-sig", "cp932", "shift_jis"):
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    columns = reader.fieldnames or []
                return columns, rows
            except UnicodeDecodeError as e:
                last_error = e
        if last_error:
            raise last_error
        return [], []

    def load_variable_csv(self, show_error=False):
        path = self.variable_csv_var.get().strip()
        self.variable_csv_path = path
        self.variable_columns = []
        self.variable_rows_by_file = {}
        if not path:
            return False
        if not os.path.exists(path):
            if show_error:
                messagebox.showerror("エラー", "変数CSVが見つかりません")
            return False
        try:
            columns, rows = self.read_variable_csv(path)
        except Exception as e:
            if show_error:
                messagebox.showerror("エラー", f"変数CSVの読み込みに失敗しました\n{e}")
            return False
        self.variable_columns = columns
        for row in rows:
            for key in ("image_file", "保存画像ファイル", "processed_url", "image_url"):
                value = row.get(key, "")
                if value:
                    filename = os.path.basename(str(value))
                    if filename:
                        self.variable_rows_by_file[filename] = row
                        self.variable_rows_by_file[os.path.splitext(filename)[0]] = row
            image_file = row.get("image_file", "")
            if image_file:
                self.variable_rows_by_file[str(image_file)] = row
        self.settings["variable_csv_path"] = path
        self.save_settings()
        return True

    def get_variable_row_for_filename(self, filename):
        if not filename:
            return {}
        if not self.variable_rows_by_file and self.variable_csv_var.get().strip():
            self.load_variable_csv(show_error=False)
        basename = os.path.basename(filename)
        return (
            self.variable_rows_by_file.get(basename)
            or self.variable_rows_by_file.get(os.path.splitext(basename)[0])
            or {}
        )

    def resolve_text_variables(self, text, filename=None):
        if not text:
            return text
        if not self.variable_columns and self.variable_csv_var.get().strip():
            self.load_variable_csv(show_error=False)
        if not self.variable_columns:
            return text
        row = self.get_variable_row_for_filename(filename)

        def replace(match):
            key = match.group(1).strip()
            if key not in self.variable_columns:
                return match.group(0)
            return str(row.get(key, ""))

        return re.sub(r"\{([^{}]+)\}", replace, text)

    def insert_variable_token(self, column_name):
        self.text_entry.insert(tk.INSERT, "{" + column_name + "}")
        self.text_entry.focus_set()
        self.last_preview_text = self.get_text_value()
        self.schedule_preview_update()

    def show_variable_help(self):
        if not self.load_variable_csv(show_error=True):
            return
        if not self.variable_columns:
            messagebox.showerror("エラー", "変数CSVに列がありません")
            return

        help_window = tk.Toplevel(self.root)
        help_window.title("環境変数")
        help_window.geometry("520x520")
        help_window.transient(self.root)

        frame = tk.Frame(help_window, padx=10, pady=10)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="列名をクリックすると挿入テキストへ追加します").pack(anchor="w")

        list_frame = tk.Frame(frame)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        for column in self.variable_columns:
            listbox.insert(tk.END, "{" + column + "}")

        def on_select(_event):
            selection = listbox.curselection()
            if not selection:
                return
            token = listbox.get(selection[0])
            self.insert_variable_token(token.strip("{}"))

        listbox.bind("<<ListboxSelect>>", on_select)
        tk.Button(frame, text="閉じる", command=help_window.destroy).pack(pady=(8, 0))

    def save_active_layer(self):
        if self.suppress_preview_update or self.switching_layer:
            return
        if self.text_layers and 0 <= self.active_text_layer < len(self.text_layers):
            self.text_layers[self.active_text_layer] = self.capture_text_layer()
        if self.icon_layers and 0 <= self.active_icon_layer < len(self.icon_layers):
            self.icon_layers[self.active_icon_layer] = self.capture_icon_layer()

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return
        self.folder_path = folder_path
        self.folder_path_var.set(folder_path)
        self.image_files = [f for f in os.listdir(folder_path) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        self.current_image_index = 0
        if self.image_files:
            self.preview_image()

    def select_icon_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("画像ファイル", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")])
        if not file_path:
            return
        self.icon_path = file_path
        self.icon_path_var.set(file_path)
        self.icon_image = Image.open(file_path).convert("RGBA")
        self.save_active_layer()
        self.schedule_preview_update()

    def clear_text(self):
        self.text_entry.delete("1.0", tk.END)
        self.last_preview_text = self.get_text_value()
        self.schedule_preview_update()

    def convert_to_vertical(self):
        text = self.text_entry.get("1.0", tk.END).strip()
        if text:
            self.text_entry.delete("1.0", tk.END)
            self.text_entry.insert("1.0", "\n".join(text))
            self.last_preview_text = self.get_text_value()
            self.schedule_preview_update()

    def choose_text_color(self):
        color = colorchooser.askcolor(title="文字色の選択")
        if color[1]:
            self.selected_text_color = tuple(int(c) for c in color[0])
            rgb_hex = "#{:02x}{:02x}{:02x}".format(*self.selected_text_color)
            self.text_color_chip.delete("all")
            self.text_color_chip.create_rectangle(0, 0, 24, 24, fill=rgb_hex, outline=rgb_hex)
            self.schedule_preview_update()

    def choose_bg_color(self):
        color = colorchooser.askcolor(title="背景色の選択")
        if color[1]:
            self.selected_bg_color = tuple(int(c) for c in color[0])
            rgb_hex = "#{:02x}{:02x}{:02x}".format(*self.selected_bg_color)
            self.bg_color_chip.delete("all")
            self.bg_color_chip.create_rectangle(0, 0, 24, 24, fill=rgb_hex, outline=rgb_hex)
            self.schedule_preview_update()

    def toggle_text_bg(self):
        state = "normal" if self.text_bg_enabled.get() else "disabled"
        self.bg_width.config(state=state)
        self.bg_height.config(state=state)
        self.bg_alpha.config(state=state)
        self.schedule_preview_update()

    def on_text_bg_scale_change(self, _value=None):
        if not self.suppress_preview_update and not self.switching_layer:
            if self.text_layers and 0 <= self.active_text_layer < len(self.text_layers):
                layer = dict(self.text_layers[self.active_text_layer])
                layer["bg_width"] = self.bg_width.get()
                layer["bg_height"] = self.bg_height.get()
                layer["bg_alpha"] = self.bg_alpha.get()
                layer["bg_enabled"] = self.text_bg_enabled.get()
                self.text_layers[self.active_text_layer] = layer
        self.schedule_preview_update()

    def toggle_resize_entries(self):
        state = "normal" if self.resize_enabled.get() else "disabled"
        self.resize_width_entry.config(state=state)
        self.resize_height_entry.config(state=state)

    def update_resize_aspect(self, event):
        if not self.keep_aspect.get() or not self.image_files or not self.folder_path:
            return
        img_path = os.path.join(self.folder_path, self.image_files[self.current_image_index])
        try:
            width, height = Image.open(img_path).size
        except Exception:
            return
        if event.widget == self.resize_width_entry and self.resize_width_var.get().isdigit():
            new_width = int(self.resize_width_var.get())
            self.resize_height_var.set(str(int(new_width * height / width)))
        elif event.widget == self.resize_height_entry and self.resize_height_var.get().isdigit():
            new_height = int(self.resize_height_var.get())
            self.resize_width_var.set(str(int(new_height * width / height)))

    def schedule_preview_update(self, _event=None):
        if self.suppress_preview_update:
            return
        self.save_active_layer()
        if not self.preview_window or not self.image_files:
            return
        if self.preview_update_job:
            self.root.after_cancel(self.preview_update_job)
        self.preview_update_job = self.root.after(300, self.apply_preview_update)

    def schedule_text_preview_update(self, _event=None):
        current_text = self.get_text_value()
        if current_text == self.last_preview_text:
            return
        self.last_preview_text = current_text
        self.schedule_preview_update()

    def apply_preview_update(self):
        self.preview_update_job = None
        if self.preview_window and self.image_files:
            self.preview_image()

    def on_preview_scale_change(self, _value=None):
        self.settings["preview_scale_percent"] = self.preview_scale_percent.get()
        self.save_settings()
        if not self.preview_window or not self.image_files:
            return
        if self.preview_scale_job:
            self.root.after_cancel(self.preview_scale_job)
        self.preview_scale_job = self.root.after(200, self.apply_preview_scale_change)

    def apply_preview_scale_change(self):
        self.preview_scale_job = None
        if self.preview_window and self.image_files:
            self.preview_image()

    def get_system_fonts(self, force_refresh=False):
        if os.path.exists(self.cache_file) and not force_refresh:
            try:
                with open(self.cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass

        font_dirs = [
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
        ]
        font_files = []
        for font_dir in font_dirs:
            if os.path.exists(font_dir):
                font_files.extend(glob.glob(os.path.join(font_dir, "*.ttf")))
                font_files.extend(glob.glob(os.path.join(font_dir, "*.ttc")))
                font_files.extend(glob.glob(os.path.join(font_dir, "*.otf")))

        font_dict = {}
        for font_path in font_files:
            try:
                if font_path.lower().endswith(".ttc"):
                    collection = TTCollection(font_path)
                    for i, font in enumerate(collection.fonts):
                        font_name = self.get_font_name(font, font_path)
                        if font_name and font_name not in font_dict:
                            font_dict[font_name] = (font_path, i)
                    collection.close()
                else:
                    font = TTFont(font_path)
                    font_name = self.get_font_name(font, font_path)
                    if font_name and font_name not in font_dict:
                        font_dict[font_name] = (font_path, None)
                    font.close()
            except Exception:
                continue

        with open(self.cache_file, "wb") as f:
            pickle.dump(font_dict, f)
        with open("font_list_japanese_priority.txt", "w", encoding="utf-8") as f:
            for name, (path, index) in sorted(font_dict.items()):
                f.write(f"{name}: {path} (index: {index if index is not None else 'N/A'})\n")
        return font_dict

    def get_font_name(self, font, font_path):
        if "name" not in font:
            return os.path.splitext(os.path.basename(font_path))[0]
        for record in font["name"].names:
            if record.langID == 1041 and record.nameID in (1, 4, 16):
                try:
                    return record.toUnicode()
                except Exception:
                    pass
        for record in font["name"].names:
            if record.langID in (0, 1033) and record.nameID in (1, 4, 16):
                try:
                    return record.toUnicode()
                except Exception:
                    pass
        return os.path.splitext(os.path.basename(font_path))[0]

    def refresh_fonts(self):
        current_font = self.font_list.get()
        self.font_dict = self.get_system_fonts(force_refresh=True)
        font_names = list(self.font_dict.keys())
        self.font_list["values"] = font_names
        if current_font in self.font_dict:
            self.font_list.set(current_font)
        elif "ＭＳ ゴシック" in self.font_dict:
            self.font_list.set("ＭＳ ゴシック")
        elif font_names:
            self.font_list.set(font_names[0])
        messagebox.showinfo("完了", f"フォントを再取得しました\n取得数: {len(font_names)}件")
        self.schedule_preview_update()

    def load_selected_font(self):
        font_info = self.font_dict.get(self.font_list.get())
        if not font_info:
            messagebox.showerror("エラー", "フォントが見つかりません")
            return None
        font_path, font_index = font_info
        try:
            return ImageFont.truetype(font_path, self.font_size.get(), index=font_index if font_index is not None else 0)
        except Exception:
            messagebox.showwarning("警告", "フォント読み込みに失敗しました。デフォルトフォントを使用します")
            return ImageFont.load_default()

    def load_font_from_layer(self, layer):
        font_info = self.font_dict.get(layer.get("font", ""))
        if not font_info:
            font_info = self.font_dict.get(self.font_list.get())
        if not font_info:
            return ImageFont.load_default()
        font_path, font_index = font_info
        try:
            return ImageFont.truetype(font_path, layer.get("font_size", 20), index=font_index if font_index is not None else 0)
        except Exception:
            return ImageFont.load_default()

    def get_text_value(self):
        return self.text_entry.get("1.0", tk.END).rstrip("\n")

    def get_position_center(self, kind, img_width, img_height):
        if kind == "text":
            mode = self.text_position_mode.get()
            origin = self.text_origin_list.get()
            rel_x, rel_y = self.text_relative_x, self.text_relative_y
            off_x = self.text_offset_x if self.text_offset_x is not None else img_width / 2
            off_y = self.text_offset_y if self.text_offset_y is not None else img_height / 2
        else:
            mode = self.icon_position_mode.get()
            origin = self.icon_origin_list.get()
            rel_x, rel_y = self.icon_relative_x, self.icon_relative_y
            off_x = self.icon_offset_x if self.icon_offset_x is not None else img_width / 2
            off_y = self.icon_offset_y if self.icon_offset_y is not None else img_height / 2

        if mode == "ピクセル設定":
            center_x, center_y = off_x, off_y
            if origin == "右上":
                center_x = img_width - center_x
            elif origin == "中央":
                center_x = img_width / 2 + center_x
                center_y = img_height / 2 + center_y
            elif origin == "左下":
                center_y = img_height - center_y
            elif origin == "右下":
                center_x = img_width - center_x
                center_y = img_height - center_y
        else:
            if origin == "左上":
                center_x = rel_x * img_width
                center_y = rel_y * img_height
            elif origin == "右上":
                center_x = img_width - rel_x * img_width
                center_y = rel_y * img_height
            elif origin == "中央":
                center_x = img_width / 2 + rel_x * img_width
                center_y = img_height / 2 + rel_y * img_height
            elif origin == "左下":
                center_x = rel_x * img_width
                center_y = img_height - rel_y * img_height
            elif origin == "右下":
                center_x = img_width - rel_x * img_width
                center_y = img_height - rel_y * img_height
            else:
                center_x = rel_x * img_width
                center_y = rel_y * img_height
        return center_x, center_y

    def get_position_center_from_layer(self, layer, img_width, img_height):
        mode = layer.get("position_mode", "比率設定")
        origin = layer.get("origin", "左上")
        rel_x = layer.get("relative_x", 0.5)
        rel_y = layer.get("relative_y", 0.5)
        off_x = layer.get("offset_x")
        off_y = layer.get("offset_y")
        if off_x is None:
            off_x = img_width / 2
        if off_y is None:
            off_y = img_height / 2

        if mode == "ピクセル設定":
            center_x, center_y = off_x, off_y
            if origin == "右上":
                center_x = img_width - center_x
            elif origin == "中央":
                center_x = img_width / 2 + center_x
                center_y = img_height / 2 + center_y
            elif origin == "左下":
                center_y = img_height - center_y
            elif origin == "右下":
                center_x = img_width - center_x
                center_y = img_height - center_y
            return center_x, center_y

        if origin == "右上":
            return img_width - rel_x * img_width, rel_y * img_height
        if origin == "中央":
            return img_width / 2 + rel_x * img_width, img_height / 2 + rel_y * img_height
        if origin == "左下":
            return rel_x * img_width, img_height - rel_y * img_height
        if origin == "右下":
            return img_width - rel_x * img_width, img_height - rel_y * img_height
        return rel_x * img_width, rel_y * img_height

    def update_position_from_center(self, kind, center_x, center_y, img_width, img_height):
        if kind == "text":
            mode = self.text_position_mode.get()
            origin = self.text_origin_list.get()
        else:
            mode = self.icon_position_mode.get()
            origin = self.icon_origin_list.get()

        if mode == "ピクセル設定":
            if kind == "text":
                self.text_offset_x, self.text_offset_y = center_x, center_y
            else:
                self.icon_offset_x, self.icon_offset_y = center_x, center_y
            return

        if origin == "左上":
            rel_x, rel_y = center_x / img_width, center_y / img_height
        elif origin == "右上":
            rel_x, rel_y = (img_width - center_x) / img_width, center_y / img_height
        elif origin == "中央":
            rel_x, rel_y = (center_x - img_width / 2) / img_width, (center_y - img_height / 2) / img_height
        elif origin == "左下":
            rel_x, rel_y = center_x / img_width, (img_height - center_y) / img_height
        elif origin == "右下":
            rel_x, rel_y = (img_width - center_x) / img_width, (img_height - center_y) / img_height
        else:
            rel_x, rel_y = center_x / img_width, center_y / img_height

        if kind == "text":
            self.text_relative_x, self.text_relative_y = rel_x, rel_y
        else:
            self.icon_relative_x, self.icon_relative_y = rel_x, rel_y

    def calculate_text_layout(self, draw, font, text, center_x, center_y, alignment=None):
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        space_bbox = draw.textbbox((0, 0), " ", font=font)
        space_width = space_bbox[2] - space_bbox[0]
        lines = text.splitlines(keepends=True) or [""]

        max_width = 0
        processed_lines = []
        line_widths = []
        for line in lines:
            stripped = line.rstrip("\n")
            trailing_spaces = len(stripped) - len(stripped.rstrip())
            if stripped.strip():
                bbox = draw.textbbox((0, 0), stripped.rstrip(), font=font)
                line_width = bbox[2] - bbox[0] + space_width * trailing_spaces
            else:
                line_width = space_width * trailing_spaces
            max_width = max(max_width, line_width)
            processed_lines.append(stripped)
            line_widths.append(line_width)

        total_height = line_height * len(processed_lines)
        alignment = alignment or self.alignment.get()
        if alignment == "左揃え":
            actual_x = center_x
        elif alignment == "右揃え":
            actual_x = center_x - max_width
        else:
            actual_x = center_x - max_width / 2
        actual_y = center_y - total_height / 2

        return {
            "lines": processed_lines,
            "line_widths": line_widths,
            "line_height": line_height,
            "max_width": max_width,
            "total_height": total_height,
            "actual_x": actual_x,
            "actual_y": actual_y,
            "center_x": center_x,
            "center_y": center_y,
            "alignment": alignment,
            "bg_bbox": None,
        }

    def alpha_composite_clipped(self, dest, src, x, y):
        dest_left = max(0, int(x))
        dest_top = max(0, int(y))
        dest_right = min(dest.width, int(x) + src.width)
        dest_bottom = min(dest.height, int(y) + src.height)
        if dest_right <= dest_left or dest_bottom <= dest_top:
            return
        src_left = dest_left - int(x)
        src_top = dest_top - int(y)
        src_crop = src.crop((src_left, src_top, src_left + dest_right - dest_left, src_top + dest_bottom - dest_top))
        dest.alpha_composite(src_crop, (dest_left, dest_top))

    def create_text_overlay(self, base_img, font, text, center_x, center_y, layer_data=None):
        measure_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(measure_img)
        alignment = layer_data.get("alignment") if layer_data else None
        layout = self.calculate_text_layout(draw, font, text, center_x, center_y, alignment=alignment)
        text_rgb = tuple(layer_data.get("text_color", self.selected_text_color)) if layer_data else self.selected_text_color
        text_alpha = layer_data.get("text_alpha", self.text_alpha.get()) if layer_data else self.text_alpha.get()
        text_color = text_rgb + (255 - text_alpha,)

        padding = 8
        left = layout["actual_x"]
        top = layout["actual_y"]
        right = layout["actual_x"] + layout["max_width"]
        bottom = layout["actual_y"] + layout["total_height"]
        bg_enabled = layer_data.get("bg_enabled", self.text_bg_enabled.get()) if layer_data else self.text_bg_enabled.get()
        bg_width = layer_data.get("bg_width", self.bg_width.get()) if layer_data else self.bg_width.get()
        bg_height = layer_data.get("bg_height", self.bg_height.get()) if layer_data else self.bg_height.get()
        if bg_enabled:
            width = layout["max_width"] * bg_width
            height = layout["total_height"] * bg_height
            bg_left = layout["actual_x"] - (width - layout["max_width"]) / 2
            bg_top = layout["actual_y"] - (height - layout["total_height"]) / 2
            layout["bg_bbox"] = (bg_left, bg_top, bg_left + width, bg_top + height)
            left = min(left, bg_left)
            top = min(top, bg_top)
            right = max(right, bg_left + width)
            bottom = max(bottom, bg_top + height)

        layer_x = int(math.floor(left - padding))
        layer_y = int(math.floor(top - padding))
        layer_w = max(1, int(math.ceil(right + padding)) - layer_x)
        layer_h = max(1, int(math.ceil(bottom + padding)) - layer_y)
        layer = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)

        if bg_enabled and layout.get("bg_bbox"):
            bg_rgb = tuple(layer_data.get("bg_color", self.selected_bg_color)) if layer_data else self.selected_bg_color
            bg_alpha = layer_data.get("bg_alpha", self.bg_alpha.get()) if layer_data else self.bg_alpha.get()
            bg_color = bg_rgb + (255 - bg_alpha,)
            bg = layout["bg_bbox"]
            layer_draw.rectangle((bg[0] - layer_x, bg[1] - layer_y, bg[2] - layer_x, bg[3] - layer_y), fill=bg_color)

        y = layout["actual_y"]
        for idx, line in enumerate(layout["lines"]):
            if line.strip():
                line_width = layout["line_widths"][idx]
                if layout["alignment"] == "左揃え":
                    x = layout["actual_x"]
                elif layout["alignment"] == "右揃え":
                    x = layout["actual_x"] + (layout["max_width"] - line_width)
                else:
                    x = layout["actual_x"] + (layout["max_width"] - line_width) / 2
                layer_draw.text((x - layer_x, y - layer_y), line, font=font, fill=text_color)
            y += layout["line_height"]

        angle = layer_data.get("rotation", self.text_rotation.get()) if layer_data else self.text_rotation.get()
        if angle:
            layer = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
            layer_x = int(round(center_x - layer.width / 2))
            layer_y = int(round(center_y - layer.height / 2))
            layout["bg_bbox"] = None

        overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        self.alpha_composite_clipped(overlay, layer, layer_x, layer_y)
        layout["actual_x"] = layer_x
        layout["actual_y"] = layer_y
        layout["max_width"] = layer.width
        layout["total_height"] = layer.height
        layout["preview_image"] = layer
        return overlay, layout

    def rotate_overlay_crop(self, overlay, layout, base_size, center_x, center_y, angle):
        width, height = base_size
        padding = 8
        left = layout["actual_x"]
        top = layout["actual_y"]
        right = layout["actual_x"] + layout["max_width"]
        bottom = layout["actual_y"] + layout["total_height"]
        if layout.get("bg_bbox"):
            bg = layout["bg_bbox"]
            left, top, right, bottom = min(left, bg[0]), min(top, bg[1]), max(right, bg[2]), max(bottom, bg[3])
        crop_left = max(0, int(math.floor(left - padding)))
        crop_top = max(0, int(math.floor(top - padding)))
        crop_right = min(width, int(math.ceil(right + padding)))
        crop_bottom = min(height, int(math.ceil(bottom + padding)))
        if crop_right <= crop_left or crop_bottom <= crop_top:
            return overlay, layout

        crop = overlay.crop((crop_left, crop_top, crop_right, crop_bottom))
        rotated = crop.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        rotated_overlay = Image.new("RGBA", base_size, (0, 0, 0, 0))
        paste_x = int(round(center_x - rotated.width / 2))
        paste_y = int(round(center_y - rotated.height / 2))
        rotated_overlay.alpha_composite(rotated, (paste_x, paste_y))
        layout["actual_x"] = paste_x
        layout["actual_y"] = paste_y
        layout["max_width"] = rotated.width
        layout["total_height"] = rotated.height
        layout["bg_bbox"] = None
        return rotated_overlay, layout

    def get_icon_effective_scale(self, base_width, base_height, icon_image=None, layer_data=None):
        icon_image = icon_image or self.icon_image
        if not icon_image:
            return 1.0
        scale_value = (layer_data.get("scale", self.icon_scale.get()) if layer_data else self.icon_scale.get()) / 100.0
        scale_mode = layer_data.get("scale_mode", self.icon_scale_mode.get()) if layer_data else self.icon_scale_mode.get()
        if scale_mode == "貼り付け画像":
            return scale_value
        icon_w, icon_h = icon_image.size
        bg_aspect = base_width / base_height
        icon_aspect = icon_w / icon_h
        relative_scale = base_width / icon_w if bg_aspect > icon_aspect else base_height / icon_h
        return scale_value * relative_scale

    def create_icon_overlay(self, base_img, center_x, center_y, layer_data=None):
        icon_image = self.icon_image
        if layer_data is not None:
            icon_path = layer_data.get("path", "")
            icon_image = None
            if icon_path and os.path.exists(icon_path):
                try:
                    icon_image = Image.open(icon_path).convert("RGBA")
                except Exception:
                    icon_image = None
        if not icon_image:
            return Image.new("RGBA", base_img.size, (0, 0, 0, 0)), None
        effective_scale = self.get_icon_effective_scale(base_img.width, base_img.height, icon_image=icon_image, layer_data=layer_data)
        new_width = max(1, int(icon_image.width * effective_scale))
        new_height = max(1, int(icon_image.height * effective_scale))
        icon = icon_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        rotation = layer_data.get("rotation", self.icon_rotation.get()) if layer_data else self.icon_rotation.get()
        if rotation:
            icon = icon.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)

        icon_alpha = layer_data.get("alpha", self.icon_alpha.get()) if layer_data else self.icon_alpha.get()
        alpha = icon.split()[3].point(lambda p: p * (1 - icon_alpha / 100.0))
        icon = Image.merge("RGBA", (*icon.split()[:3], alpha))
        actual_x = int(center_x - icon.width / 2)
        actual_y = int(center_y - icon.height / 2)
        overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        self.alpha_composite_clipped(overlay, icon, actual_x, actual_y)
        layout = {
            "actual_x": actual_x,
            "actual_y": actual_y,
            "max_width": icon.width,
            "total_height": icon.height,
            "center_x": center_x,
            "center_y": center_y,
            "bg_bbox": None,
            "preview_image": icon,
        }
        return overlay, layout

    def compose_image(self, base_img, filename=None, preview_active_only=False):
        self.save_active_layer()
        result = base_img.copy()
        layouts = {}
        overlays = []

        anchor_icon_center = None
        for layer in self.icon_layers:
            if not layer.get("enabled") or not layer.get("path"):
                continue
            if not os.path.exists(layer.get("path")):
                continue
            anchor_icon_center = self.get_position_center_from_layer(layer, base_img.width, base_img.height)
            break

        for kind, index, key in self.get_layer_draw_order():
            if kind == "icon":
                layer = self.icon_layers[index]
                if not layer.get("enabled") or not layer.get("path"):
                    continue
                icon_center = self.get_position_center_from_layer(layer, base_img.width, base_img.height)
                icon_overlay, icon_layout = self.create_icon_overlay(base_img, *icon_center, layer_data=layer)
                if icon_layout is None:
                    continue
                overlays.append((key, icon_overlay))
                layouts[key] = icon_layout
                continue

            layer = self.text_layers[index]
            text = self.resolve_text_variables(layer.get("text", ""), filename)
            if not layer.get("enabled") or not text.strip():
                continue
            font = self.load_font_from_layer(layer)
            if layer.get("anchor_mode") == "貼り付け画像の中央" and anchor_icon_center is not None:
                text_center = anchor_icon_center
            else:
                text_center = self.get_position_center_from_layer(layer, base_img.width, base_img.height)
            text_overlay, text_layout = self.create_text_overlay(base_img, font, text, *text_center, layer_data=layer)
            overlays.append((key, text_overlay))
            layouts[key] = text_layout

        if preview_active_only:
            return result, layouts

        for _key, overlay in overlays:
            result = Image.alpha_composite(result, overlay)
        return result, layouts

    def get_layer_draw_order(self):
        order = []
        self.normalize_layer_stack_order()
        for key in self.layer_stack_order:
            if key.startswith("text"):
                order.append(("text", int(key[4:]), key))
            elif key.startswith("icon"):
                order.append(("icon", int(key[4:]), key))
        return tuple(order)

    def get_preview_scale(self, img_width, img_height):
        fit_scale = min(1.0, self.preview_max_width / img_width, self.preview_max_height / img_height)
        return max(0.01, fit_scale * self.preview_scale_percent.get() / 100.0)

    def resize_for_preview(self, image, scale):
        if scale >= 1.0:
            return image
        return image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)

    def preview_image(self):
        focused_widget = self.root.focus_get()
        if self.preview_update_job:
            self.root.after_cancel(self.preview_update_job)
            self.preview_update_job = None
        if self.preview_scale_job:
            self.root.after_cancel(self.preview_scale_job)
            self.preview_scale_job = None
        if not self.folder_path or not self.image_files:
            messagebox.showerror("エラー", "画像フォルダを指定してください")
            return

        current_filename = self.image_files[self.current_image_index]
        img_path = os.path.join(self.folder_path, current_filename)
        base_img = Image.open(img_path).convert("RGBA")
        composed, layouts = self.compose_image(base_img, current_filename, preview_active_only=True)
        if composed is None:
            return

        self.preview_scale = self.get_preview_scale(base_img.width, base_img.height)
        self.preview_original_size = base_img.size
        display_base = self.resize_for_preview(composed, self.preview_scale)

        if self.preview_window:
            self.preview_window.destroy()
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title(f"プレビュー ({self.current_image_index + 1}/{len(self.image_files)})")

        canvas_width = display_base.width
        canvas_height = display_base.height
        if self.preview_window_pos:
            self.preview_window.geometry(f"{canvas_width}x{canvas_height + 42}+{self.preview_window_pos[0]}+{self.preview_window_pos[1]}")
        else:
            self.preview_window.geometry(f"{canvas_width}x{canvas_height + 42}")
        self.preview_window.grid_rowconfigure(0, weight=0)
        self.preview_window.grid_rowconfigure(1, weight=1)
        self.preview_window.grid_columnconfigure(0, weight=1)

        bar = tk.Frame(self.preview_window)
        bar.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.prev_btn = tk.Button(bar, text="戻る", command=self.prev_image, width=10)
        self.prev_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.next_btn = tk.Button(bar, text="次へ", command=self.next_image, width=10)
        self.next_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.count_label = tk.Label(bar, text=f"{self.current_image_index + 1}/{len(self.image_files)}")
        self.count_label.pack(side=tk.LEFT, padx=5)

        self.canvas = tk.Canvas(self.preview_window, width=canvas_width, height=canvas_height)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_img = ImageTk.PhotoImage(display_base)
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_img)

        self.preview_items = {}
        self.preview_center_offsets = {}
        self.preview_overlay_images = {}
        for _kind, _index, key in self.get_layer_draw_order():
            if key not in layouts:
                continue
            self.add_preview_overlay(key, None, layouts[key], base_img.size)

        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_overlay)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<MouseWheel>", self.on_preview_mousewheel)
        self.preview_window.bind("<MouseWheel>", self.on_preview_mousewheel)
        self.preview_window.bind("<Left>", self.on_preview_key)
        self.preview_window.bind("<Right>", self.on_preview_key)
        self.preview_window.bind("<Up>", self.on_preview_key)
        self.preview_window.bind("<Down>", self.on_preview_key)
        self.preview_window.bind("<Configure>", self.save_preview_position)
        self.update_button_state()
        if focused_widget and focused_widget.winfo_exists() and focused_widget.winfo_toplevel() == self.root:
            focused_widget.focus_set()

    def add_preview_overlay(self, kind, overlay, layout, base_size):
        layer = layout.get("preview_image")
        if layer is None:
            layer = overlay
        if layer.width <= 0 or layer.height <= 0:
            return
        display_layer = self.resize_for_preview(layer, self.preview_scale)
        tk_img = ImageTk.PhotoImage(display_layer)
        item = self.canvas.create_image(layout["actual_x"] * self.preview_scale, layout["actual_y"] * self.preview_scale, image=tk_img, anchor="nw")
        self.preview_overlay_images[kind] = tk_img
        self.preview_items[kind] = item
        self.preview_center_offsets[kind] = (
            (layout["center_x"] - layout["actual_x"]) * self.preview_scale,
            (layout["center_y"] - layout["actual_y"]) * self.preview_scale,
        )

    def start_drag(self, event):
        self.drag_target = self.get_active_drag_target()
        if self.drag_target not in self.preview_items:
            self.drag_target = None
            return
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def get_active_drag_target(self):
        if self.active_layer_kind == "icon":
            return f"icon{self.active_icon_layer}"
        if self.active_layer_kind == "text":
            return f"text{self.active_text_layer}"
        for key in reversed(self.layer_stack_order):
            if key in self.preview_items:
                return key
        return f"text{self.active_text_layer}"

    def drag_overlay(self, event):
        if not self.drag_target:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.canvas.move(self.preview_items[self.drag_target], dx, dy)
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def stop_drag(self, _event):
        if not self.drag_target or self.drag_target not in self.preview_items:
            return
        coords = self.canvas.coords(self.preview_items[self.drag_target])
        offset = self.preview_center_offsets[self.drag_target]
        center_x = (coords[0] + offset[0]) / self.preview_scale
        center_y = (coords[1] + offset[1]) / self.preview_scale
        img_width, img_height = self.preview_original_size
        base_kind = "icon" if self.drag_target.startswith("icon") else "text"
        self.update_position_from_center(base_kind, center_x, center_y, img_width, img_height)
        self.save_active_layer()
        if base_kind == "icon" and any(layer.get("anchor_mode") == "貼り付け画像の中央" for layer in self.text_layers):
            self.root.after(10, self.preview_image)
        self.drag_target = None

    def on_preview_key(self, event):
        if event.keysym in ("Left", "Up"):
            self.prev_image()
            return "break"
        if event.keysym in ("Right", "Down"):
            self.next_image()
            return "break"
        return None

    def on_preview_mousewheel(self, event):
        if event.delta > 0:
            self.prev_image()
        elif event.delta < 0:
            self.next_image()
        return "break"

    def update_button_state(self):
        if hasattr(self, "prev_btn"):
            self.prev_btn.config(state="disabled" if self.current_image_index == 0 else "normal")
        if hasattr(self, "next_btn"):
            self.next_btn.config(state="disabled" if self.current_image_index == len(self.image_files) - 1 else "normal")

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.preview_image()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.preview_image()

    def save_preview_position(self, event):
        if self.preview_window and event.widget == self.preview_window:
            self.preview_window_pos = (self.preview_window.winfo_x(), self.preview_window.winfo_y())

    def validate_before_process(self):
        if not self.folder_path or not self.image_files:
            messagebox.showerror("エラー", "画像フォルダを指定してください")
            return False
        self.save_active_layer()
        icon_is_effective = any(layer.get("enabled") and layer.get("path") for layer in self.icon_layers)
        text_is_effective = any(layer.get("enabled") and layer.get("text", "").strip() for layer in self.text_layers)
        if any(layer.get("enabled") and layer.get("path") and not os.path.exists(layer.get("path")) for layer in self.icon_layers):
            messagebox.showerror("エラー", "存在しない貼り付け画像があります")
            return False
        if not icon_is_effective and not text_is_effective:
            messagebox.showerror("エラー", "文字または画像のどちらかを有効にしてください")
            return False
        if self.resize_enabled.get():
            if not (self.resize_width_var.get().isdigit() and self.resize_height_var.get().isdigit()):
                messagebox.showerror("エラー", "解像度を正しく入力してください")
                return False
        return True

    def process_images(self, show_dialog=True):
        if not self.validate_before_process():
            return None
        output_dir = self.folder_path if os.path.basename(self.folder_path) == "output" else os.path.join(self.folder_path, "output")
        os.makedirs(output_dir, exist_ok=True)
        quality = self.quality.get()
        suffix = self.suffix_entry.get().strip()
        processed_count = 0
        error_count = 0

        for filename in self.image_files:
            try:
                img_path = os.path.join(self.folder_path, filename)
                base_img = Image.open(img_path).convert("RGBA")
                img, _layouts = self.compose_image(base_img, filename)
                if img is None:
                    error_count += 1
                    continue
                img = img.convert("RGB")
                if self.resize_enabled.get():
                    img = img.resize((int(self.resize_width_var.get()), int(self.resize_height_var.get())), Image.Resampling.LANCZOS)
                base_name = os.path.splitext(filename)[0]
                output_path = os.path.join(output_dir, f"{base_name}{suffix}.jpg")
                img.save(output_path, quality=quality)
                processed_count += 1
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                error_count += 1

        if show_dialog:
            messagebox.showinfo("完了", f"処理が完了しました\n出力先: {output_dir}\n成功: {processed_count}枚\n失敗: {error_count}枚")
        return output_dir, processed_count, error_count

    def process_images_continuous(self):
        result = self.process_images(show_dialog=False)
        if not result:
            return
        output_dir, processed_count, error_count = result
        if processed_count > 0:
            self.folder_path = output_dir
            self.folder_path_var.set(output_dir)
            self.image_files = [f for f in os.listdir(output_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            self.current_image_index = 0
            if self.image_files:
                self.preview_image()
        messagebox.showinfo("連続実行", f"出力フォルダを次の入力に設定しました\nフォルダ: {output_dir}\n成功: {processed_count}枚\n失敗: {error_count}枚")


if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedOverlayApp(root)
    root.mainloop()
