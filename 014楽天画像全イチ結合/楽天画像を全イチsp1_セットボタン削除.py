import csv
import os
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import re
import requests
from PIL import Image, ImageTk
from datetime import datetime
import io
import shutil
from collections import defaultdict
import urllib.parse
import json
import sys
import threading

class ImageProcessorGUI:
    CONFIG_FILE_NAME = "rakuten2in1.json"
    DEFAULT_RESIZE_WIDTH = 750
    DEFAULT_IMAGE_SPACING = 20
    DEFAULT_IMAGE_COUNT = 2
    DEFAULT_OUTPUT_FOLDER = ""
    DEFAULT_BASE_URL_3839 = "https://image.rakuten.co.jp/店舗URL/cabinet/"
    DEFAULT_BASE_URL_3840 = "https://www.rakuten.ne.jp/gold/店舗URL/"
    DEFAULT_SHOP_BASE_URL = "https://image.rakuten.co.jp/店舗URL/"
    DEFAULT_RESOLUTION_THRESHOLD = 3840
    INPUT_DATA_OPTIONS = ["スマートフォン用商品説明文", "PC用販売説明文", "商品画像パス", "ローカルフォルダ", "ダウンロードリスト"]
    DEFAULT_INPUT_DATA_OPTION = "スマートフォン用商品説明文"
    DEFAULT_NEWLINE_COUNT = 2
    DEFAULT_PRE_INSERT_FILE_PATH = ""
    DEFAULT_POST_INSERT_FILE_PATH = ""
    DEFAULT_INSERT_PC_DESCRIPTION = False
    DEFAULT_IMAGE_NAME_SEPARATOR = "_sp_"
    DEFAULT_WRITE_BACK = False
    DEFAULT_IMAGE_COUNT_THRESHOLD = 2
    DEFAULT_EXCLUDE_LINKED_IMAGES = True

    INPUT_DATA_OPTIONS_MAP = {
        1: "スマートフォン用商品説明文",
        2: "PC用販売説明文",
        3: "商品画像パス",
        4: "ローカルフォルダ",
        5: "ダウンロードリスト"
    }
    INPUT_DATA_OPTIONS_REVERSE_MAP = {
        "スマートフォン用商品説明文": 1,
        "PC用販売説明文": 2,
        "商品画像パス": 3,
        "ローカルフォルダ": 4,
        "ダウンロードリスト": 5
    }

    def __init__(self, master):
        self.master = master
        master.title("楽天画像処理ツール")

        self.base_dir = None
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = None
        self.is_local_folder_mode = False
        self.stop_event = threading.Event()  # 停止フラグ
        self.progress_var = tk.DoubleVar()  # プログレスバーの値
        self.total_tasks = 0  # 総タスク数
        self.completed_tasks = 0  # 完了したタスク数

        self.default_resize_width = self.DEFAULT_RESIZE_WIDTH
        self.default_image_spacing = self.DEFAULT_IMAGE_SPACING
        self.default_image_count = self.DEFAULT_IMAGE_COUNT
        self.default_output_folder = self.DEFAULT_OUTPUT_FOLDER
        self.default_base_url_3839 = self.DEFAULT_BASE_URL_3839
        self.default_base_url_3840 = self.DEFAULT_BASE_URL_3840
        self.default_shop_base_url = self.DEFAULT_SHOP_BASE_URL
        self.default_resolution_threshold = self.DEFAULT_RESOLUTION_THRESHOLD
        self.selected_input_data = tk.StringVar(value=self.DEFAULT_INPUT_DATA_OPTION)
        self.shop_url_var = tk.StringVar(value=self.default_shop_base_url)
        self.resolution_threshold_var = tk.IntVar(value=self.default_resolution_threshold)
        self.default_newline_count = self.DEFAULT_NEWLINE_COUNT
        self.newline_count_var = tk.IntVar(value=self.default_newline_count)
        self.default_pre_insert_file_path = self.DEFAULT_PRE_INSERT_FILE_PATH
        self.default_post_insert_file_path = self.DEFAULT_POST_INSERT_FILE_PATH
        self.pre_insert_file_path = tk.StringVar(value=self.default_pre_insert_file_path)
        self.post_insert_file_path = tk.StringVar(value=self.default_post_insert_file_path)
        self.separate_url_var = tk.BooleanVar()
        self.insert_pc_description_var = tk.BooleanVar(value=self.DEFAULT_INSERT_PC_DESCRIPTION)
        self.default_image_name_separator = self.DEFAULT_IMAGE_NAME_SEPARATOR
        self.image_name_separator_var = tk.StringVar(value=self.default_image_name_separator)
        self.write_back_var = tk.BooleanVar(value=self.DEFAULT_WRITE_BACK)
        self.default_image_count_threshold = self.DEFAULT_IMAGE_COUNT_THRESHOLD
        self.image_count_threshold_var = tk.IntVar(value=self.default_image_count_threshold)
        self.default_exclude_linked_images = self.DEFAULT_EXCLUDE_LINKED_IMAGES
        self.exclude_linked_images_var = tk.BooleanVar(value=self.default_exclude_linked_images)

        # ファイル選択フレーム
        self.file_frame = tk.LabelFrame(master, text="1. CSVファイル選択")
        self.file_frame.pack(padx=10, pady=10, fill=tk.X)

        self.input_file_path = tk.StringVar()
        self.file_entry = tk.Entry(self.file_frame, textvariable=self.input_file_path, state='disabled', width=50)
        self.file_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        self.file_button = tk.Button(self.file_frame, text="CSVファイルを選択", command=self.select_input_file_gui)
        self.file_button.pack(side=tk.LEFT, padx=5, pady=5)

        # 入力データ選択
        input_data_frame = tk.Frame(master)
        input_data_frame.pack(padx=10, pady=0, fill=tk.X)

        input_data_label = tk.Label(input_data_frame, text="入力データ:")
        input_data_label.pack(side=tk.LEFT, padx=5)

        self.input_data_var = tk.StringVar()
        self.input_data_var.set(self.selected_input_data.get())
        input_data_dropdown = ttk.Combobox(input_data_frame, textvariable=self.input_data_var, values=self.INPUT_DATA_OPTIONS, state='readonly')
        input_data_dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        input_data_dropdown.bind("<<ComboboxSelected>>", self.select_input_data_type)

        # 画像数閾値とリンク付き画像除外オプション（1行に統合）
        image_count_exclude_frame = tk.Frame(master)
        image_count_exclude_frame.pack(padx=10, pady=0, fill=tk.X)
        tk.Label(image_count_exclude_frame, text="画像数:").pack(side=tk.LEFT, padx=5)
        image_count_entry = tk.Entry(image_count_exclude_frame, textvariable=self.image_count_threshold_var, width=10)
        image_count_entry.pack(side=tk.LEFT, padx=5)
        image_count_entry.bind("<FocusOut>", lambda e: self.set_image_count_and_exclude())
        tk.Label(image_count_exclude_frame, text="以上の場合のみ対象とする").pack(side=tk.LEFT, padx=5)
        exclude_cb = tk.Checkbutton(image_count_exclude_frame, text="リンク付き画像除外", variable=self.exclude_linked_images_var)
        exclude_cb.pack(side=tk.LEFT, padx=5)
        exclude_cb.bind("<Button-1>", lambda e: self.master.after(100, self.set_image_count_and_exclude))

        # ショップURL設定
        shop_url_frame = tk.Frame(master)
        shop_url_frame.pack(padx=10, pady=0, fill=tk.X)

        shop_url_label = tk.Label(shop_url_frame, text="ショップ画像URL：")
        shop_url_label.pack(side=tk.LEFT, padx=5)

        self.shop_url_entry = tk.Entry(shop_url_frame, textvariable=self.shop_url_var, width=60, state='disabled')
        self.shop_url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.shop_url_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("shop_url", self.get_shop_url, self.shop_url_var, "ショップ画像URL"))
        shop_url_example_label = tk.Label(shop_url_frame, text="cabinet/画像URL")
        shop_url_example_label.pack(side=tk.LEFT, padx=5)

        # 設定フレーム
        settings_frame = tk.LabelFrame(master, text="2. 設定")
        settings_frame.pack(padx=10, pady=10, fill=tk.X)

        # リサイズ幅、画像間隔、結合画像数を1行に統合
        image_settings_frame = tk.Frame(settings_frame)
        image_settings_frame.pack(fill=tk.X, pady=2)
        tk.Label(image_settings_frame, text="リサイズ幅px:").pack(side=tk.LEFT, padx=5)
        self.resize_width_var = tk.IntVar(value=self.default_resize_width)
        resize_width_entry = tk.Entry(image_settings_frame, textvariable=self.resize_width_var, width=10)
        resize_width_entry.pack(side=tk.LEFT, padx=5)
        resize_width_entry.bind("<FocusOut>", lambda e: self.set_image_settings())
        tk.Label(image_settings_frame, text="画像間隔px:").pack(side=tk.LEFT, padx=5)
        self.image_spacing_var = tk.IntVar(value=self.default_image_spacing)
        image_spacing_entry = tk.Entry(image_settings_frame, textvariable=self.image_spacing_var, width=10)
        image_spacing_entry.pack(side=tk.LEFT, padx=5)
        image_spacing_entry.bind("<FocusOut>", lambda e: self.set_image_settings())
        tk.Label(image_settings_frame, text="結合画像数:").pack(side=tk.LEFT, padx=5)
        self.image_count_combine_var = tk.IntVar(value=self.default_image_count)
        image_count_combine_entry = tk.Entry(image_settings_frame, textvariable=self.image_count_combine_var, width=10)
        image_count_combine_entry.pack(side=tk.LEFT, padx=5)
        image_count_combine_entry.bind("<FocusOut>", lambda e: self.set_image_settings())

        output_folder_frame = tk.Frame(settings_frame)
        output_folder_frame.pack(fill=tk.X, pady=2)
        tk.Label(output_folder_frame, text="出力フォルダ:").pack(side=tk.LEFT, padx=5)
        self.output_folder_var = tk.StringVar(value=self.default_output_folder)
        output_folder_entry = tk.Entry(output_folder_frame, textvariable=self.output_folder_var, state='disabled', width=40)
        output_folder_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        output_folder_button = tk.Button(output_folder_frame, text="フォルダを選択", command=self.select_output_folder_gui)
        output_folder_button.pack(side=tk.LEFT, padx=5, pady=5)

        resolution_threshold_setting_frame = tk.Frame(settings_frame)
        resolution_threshold_setting_frame.pack(fill=tk.X, pady=2)

        self.separate_url_var = tk.BooleanVar()
        separate_url_check = tk.Checkbutton(resolution_threshold_setting_frame, text="指定解像度以上を別URLにする", variable=self.separate_url_var, command=self.toggle_resolution_threshold_widgets)
        separate_url_check.pack(side=tk.LEFT, padx=5)
        separate_url_check.bind("<Button-1>", lambda e: self.master.after(100, self.toggle_resolution_threshold_widgets))

        self.resolution_threshold_entry = tk.Entry(resolution_threshold_setting_frame, textvariable=self.resolution_threshold_var, width=10, state='disabled')
        self.resolution_threshold_entry.pack(side=tk.LEFT, padx=5)
        self.resolution_threshold_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("resolution_threshold", self.get_resolution_threshold, self.resolution_threshold_var, "解像度閾値", None, "px", self.update_base_url_labels))

        base_url_3839_frame = tk.Frame(settings_frame)
        base_url_3839_frame.pack(fill=tk.X, pady=2)
        self.base_url_3839_label = tk.Label(base_url_3839_frame, text=f"baseURL (解像度{self.default_resolution_threshold - 1}px以下):")
        self.base_url_3839_label.pack(side=tk.LEFT, padx=5)
        self.base_url_3839_var = tk.StringVar(value=self.default_base_url_3839)
        base_url_3839_entry = tk.Entry(base_url_3839_frame, textvariable=self.base_url_3839_var, width=60)
        base_url_3839_entry.pack(side=tk.LEFT, padx=5)
        base_url_3839_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("base_url_3839", self.get_base_url_3839, self.base_url_3839_var, f"baseURL (解像度{self.default_resolution_threshold - 1}px以下)"))

        base_url_3840_frame = tk.Frame(settings_frame)
        base_url_3840_frame.pack(fill=tk.X, pady=2)
        self.base_url_3840_label = tk.Label(base_url_3840_frame, text=f"baseURL (解像度{self.default_resolution_threshold}px以上):")
        self.base_url_3840_label.pack(side=tk.LEFT, padx=5)
        self.base_url_3840_var = tk.StringVar(value=self.default_base_url_3840)
        base_url_3840_entry = tk.Entry(base_url_3840_frame, textvariable=self.base_url_3840_var, width=60)
        base_url_3840_entry.pack(side=tk.LEFT, padx=5)
        base_url_3840_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("base_url_3840", self.get_base_url_3840, self.base_url_3840_var, f"baseURL (解像度{self.default_resolution_threshold}px以上)"))

        image_name_frame = tk.Frame(settings_frame)
        image_name_frame.pack(fill=tk.X, pady=2)
        tk.Label(image_name_frame, text="出力画像名：商品URL").pack(side=tk.LEFT, padx=5)
        image_name_separator_entry = tk.Entry(image_name_frame, textvariable=self.image_name_separator_var, width=10)
        image_name_separator_entry.pack(side=tk.LEFT, padx=5)
        image_name_separator_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("image_name_separator", self.get_image_name_separator, self.image_name_separator_var, "出力画像名セパレータ"))
        tk.Label(image_name_frame, text="連番").pack(side=tk.LEFT, padx=5)

        # HTML出力設定
        html_output_frame = tk.LabelFrame(master, text="3. HTML出力設定")
        html_output_frame.pack(padx=10, pady=10, fill=tk.X)

        newline_count_frame = tk.Frame(html_output_frame)
        newline_count_frame.pack(fill=tk.X, pady=2)
        tk.Label(newline_count_frame, text="改行数：").pack(side=tk.LEFT, padx=5)
        newline_count_entry = tk.Entry(newline_count_frame, textvariable=self.newline_count_var, width=10)
        newline_count_entry.pack(side=tk.LEFT, padx=5)
        newline_count_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("newline_count", self.get_newline_count, self.newline_count_var, "改行数"))

        pre_insert_frame = tk.Frame(html_output_frame)
        pre_insert_frame.pack(fill=tk.X, pady=2)
        tk.Label(pre_insert_frame, text="差し込みデータ前：").pack(side=tk.LEFT, padx=5)
        self.pre_insert_entry = tk.Entry(pre_insert_frame, textvariable=self.pre_insert_file_path, width=40)
        self.pre_insert_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.pre_insert_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("pre_insert_file_path", self.get_pre_insert_file_path, self.pre_insert_file_path, "差し込みデータ前 ファイルパス"))
        pre_insert_button = tk.Button(pre_insert_frame, text="参照", command=self.select_pre_insert_file_gui)
        pre_insert_button.pack(side=tk.LEFT, padx=5)
        clear_pre_insert_button = tk.Button(pre_insert_frame, text="クリア", command=self.clear_pre_insert_file_path_gui)
        clear_pre_insert_button.pack(side=tk.LEFT, padx=5)

        post_insert_frame = tk.Frame(html_output_frame)
        post_insert_frame.pack(fill=tk.X, pady=2)
        tk.Label(post_insert_frame, text="差し込みデータ後：").pack(side=tk.LEFT, padx=5)
        self.post_insert_entry = tk.Entry(post_insert_frame, textvariable=self.post_insert_file_path, width=40)
        self.post_insert_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.post_insert_entry.bind("<FocusOut>", lambda e: self.set_default_value_gui("post_insert_file_path", self.get_post_insert_file_path, self.post_insert_file_path, "差し込みデータ後 ファイルパス"))
        post_insert_button = tk.Button(post_insert_frame, text="参照", command=self.select_post_insert_file_gui)
        post_insert_button.pack(side=tk.LEFT, padx=5)
        clear_post_insert_button = tk.Button(post_insert_frame, text="クリア", command=self.clear_post_insert_file_path_gui)
        clear_post_insert_button.pack(side=tk.LEFT, padx=5)

        # PC用商品説明と書き戻しを1行に統合
        output_options_frame = tk.Frame(html_output_frame)
        output_options_frame.pack(fill=tk.X, pady=2)
        pc_cb = tk.Checkbutton(output_options_frame, text="PC用商品説明を差し込む", variable=self.insert_pc_description_var)
        pc_cb.pack(side=tk.LEFT, padx=5)
        pc_cb.bind("<Button-1>", lambda e: self.master.after(100, self.set_output_options))
        write_back_cb = tk.Checkbutton(output_options_frame, text="データを楽天CSV形式で書き出し", variable=self.write_back_var)
        write_back_cb.pack(side=tk.LEFT, padx=5)
        write_back_cb.bind("<Button-1>", lambda e: self.master.after(100, self.set_output_options))

        # 実行ボタンとプログレスバー
        run_frame = tk.Frame(master)
        run_frame.pack(pady=10)
        self.run_button = tk.Button(run_frame, text="画像処理開始", command=self.run_workflow_gui, padx=20, pady=5)
        self.run_button.pack()

        # プログレスバー
        progress_frame = tk.LabelFrame(master, text="処理進行状況")
        progress_frame.pack(padx=10, pady=5, fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)

        # コンソール出力
        console_frame = tk.LabelFrame(master, text="コンソール出力")
        console_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.console_text = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD, state='disabled', height=5)
        self.console_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        sys.stdout = StdoutRedirector(self.console_text)

        self.input_data_var.set(self.selected_input_data.get())
        self.shop_url_entry.config(state='normal' if self.input_data_var.get() == "商品画像パス" else 'disabled')
        self.toggle_resolution_threshold_widgets()

        self.load_settings()

        self.resize_width_var.set(self.default_resize_width)
        self.image_spacing_var.set(self.default_image_spacing)
        self.base_url_3839_var.set(self.default_base_url_3839)
        self.base_url_3840_var.set(self.default_base_url_3840)
        self.image_name_separator_var.set(self.default_image_name_separator)
        self.image_count_combine_var.set(self.default_image_count)

    def set_image_count_and_exclude(self):
        try:
            image_count = self.get_image_count_threshold()
            if image_count is not None:
                self.set_default_value_gui("image_count_threshold", lambda: image_count, self.image_count_threshold_var, "画像数閾値")
            exclude_linked = self.exclude_linked_images_var.get()
            self.set_default_value_gui("exclude_linked_images", lambda: exclude_linked, self.exclude_linked_images_var, "リンク付き画像除外設定")
        except Exception as e:
            error_msg = f"エラー[set_image_count_and_exclude]: 画像数閾値またはリンク付き画像除外設定中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def set_image_settings(self):
        try:
            resize_width = self.get_resize_width()
            if resize_width is not None:
                self.set_default_value_gui("resize_width", lambda: resize_width, self.resize_width_var, "リサイズ幅", None, "px")
            image_spacing = self.get_image_spacing()
            if image_spacing is not None:
                self.set_default_value_gui("image_spacing", lambda: image_spacing, self.image_spacing_var, "画像間隔", None, "px")
            image_count_combine = self.get_image_count_combine()
            if image_count_combine is not None:
                self.set_default_value_gui("image_count", lambda: image_count_combine, self.image_count_combine_var, "結合画像数")
        except Exception as e:
            error_msg = f"エラー[set_image_settings]: 画像設定中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def set_output_options(self):
        try:
            insert_pc = self.insert_pc_description_var.get()
            self.set_default_value_gui("insert_pc_description", lambda: insert_pc, self.insert_pc_description_var, "PC用商品説明文の差し込み")
            write_back = self.write_back_var.get()
            self.set_default_value_gui("write_back", lambda: write_back, self.write_back_var, "入力CSVへの書き戻し")
        except Exception as e:
            error_msg = f"エラー[set_output_options]: 出力設定中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def set_default_value_gui(self, attr_name, get_value_func, gui_var, display_name, validate_func=None, unit="", callback=None):
        try:
            if callable(get_value_func):
                current_value = get_value_func()
                if current_value is None:
                    return
            else:
                current_value = get_value_func

            if validate_func and not validate_func(current_value):
                raise ValueError(f"{display_name} の値が不正です: {current_value}")

            setattr(self, f"default_{attr_name}", current_value)
            if gui_var:
                gui_var.set(current_value)
            print(f"設定変更: {display_name} を {current_value} {unit} に更新しました。")
            if callback:
                callback()
            self.save_settings()
        except Exception as e:
            error_msg = f"エラー[set_default_value_gui]: {display_name} の設定中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def set_input_data_option(self):
        selected_data_type = self.input_data_var.get()
        try:
            if selected_data_type == "ローカルフォルダ":
                self.is_local_folder_mode = True
                self.file_frame.config(text="1. フォルダ選択")
                self.file_button.config(text="フォルダを選択", command=self.select_input_folder_gui)
                self.input_file_path.set("")
            else:
                self.is_local_folder_mode = False
                self.file_frame.config(text="1. CSVファイル選択")
                self.file_button.config(text="CSVファイルを選択", command=self.select_input_file_gui)
                self.input_file_path.set("")
            self.set_default_value_gui("input_data_option", lambda: selected_data_type, None, "入力データ", lambda x: x in self.INPUT_DATA_OPTIONS)
        except Exception as e:
            error_msg = f"エラー[set_input_data_option]: 入力データ設定中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def select_input_file_gui(self):
        try:
            file_path = filedialog.askopenfilename(
                title="処理ファイルを選択してください",
                filetypes=[("CSV files", "*.csv")]
            )
            if file_path:
                self.input_file_path.set(file_path)
                self.base_dir = os.path.dirname(file_path)
                default_output_dir = os.path.join(self.base_dir, f"output_{self.timestamp}")
                self.output_folder_var.set(default_output_dir)
        except Exception as e:
            error_msg = f"エラー[select_input_file_gui]: ファイル選択中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ファイルエラー", error_msg)

    def select_input_folder_gui(self):
        try:
            folder_path = filedialog.askdirectory(
                title="処理フォルダを選択してください",
                initialdir=self.base_dir if self.base_dir else os.path.expanduser("~")
            )
            if folder_path:
                self.input_file_path.set(folder_path)
                self.base_dir = os.path.dirname(folder_path)
                default_output_dir = os.path.join(self.base_dir, f"output_{self.timestamp}")
                self.output_folder_var.set(default_output_dir)
                self.set_default_value_gui("output_folder", lambda: default_output_dir, self.output_folder_var, "出力フォルダ")
        except Exception as e:
            error_msg = f"エラー[select_input_folder_gui]: フォルダ選択中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("フォルダエラー", error_msg)

    def select_output_folder_gui(self):
        try:
            folder_path = filedialog.askdirectory(
                title="出力フォルダを選択してください",
                initialdir=self.base_dir if self.base_dir else os.path.expanduser("~")
            )
            if folder_path:
                self.output_folder_var.set(folder_path)
        except Exception as e:
            error_msg = f"エラー[select_output_folder_gui]: フォルダ選択中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("フォルダエラー", error_msg)

    def select_pre_insert_file_gui(self):
        try:
            file_path = filedialog.askopenfilename(
                title="差し込みデータ前 ファイルを選択してください",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if file_path:
                self.pre_insert_file_path.set(file_path)
        except Exception as e:
            error_msg = f"エラー[select_pre_insert_file_gui]: ファイル選択中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ファイルエラー", error_msg)

    def select_post_insert_file_gui(self):
        try:
            file_path = filedialog.askopenfilename(
                title="差し込みデータ後 ファイルを選択してください",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if file_path:
                self.post_insert_file_path.set(file_path)
        except Exception as e:
            error_msg = f"エラー[select_post_insert_file_gui]: ファイル選択中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ファイルエラー", error_msg)

    def clear_pre_insert_file_path_gui(self):
        self.pre_insert_file_path.set("")

    def clear_post_insert_file_path_gui(self):
        self.post_insert_file_path.set("")

    def get_resize_width(self):
        try:
            width = int(self.resize_width_var.get())
            if width <= 0 or width > 2000:
                messagebox.showerror("設定エラー", "リサイズ幅は1以上の数値を入力してください。(上限: 2000px)")
                return None
            return width
        except ValueError:
            messagebox.showerror("設定エラー", "リサイズ幅には数値を入力してください。")
            return None

    def get_image_spacing(self):
        try:
            spacing = int(self.image_spacing_var.get())
            if spacing < 0:
                messagebox.showerror("設定エラー", "画像間隔は0以上の数値を入力してください。")
                return None
            return spacing
        except ValueError:
            messagebox.showerror("設定エラー", "画像間隔には数値を入力してください。")
            return None

    def get_image_count_combine(self):
        try:
            count = int(self.image_count_combine_var.get())
            if count <= 0:
                messagebox.showerror("設定エラー", "結合画像数は1以上の整数を入力してください。")
                return None
            return count
        except ValueError:
            messagebox.showerror("設定エラー", "結合画像数には整数を入力してください。")
            return None

    def get_output_dir(self):
        output_dir = self.output_folder_var.get()
        if not output_dir:
            messagebox.showerror("設定エラー", "出力フォルダを選択してください。")
            return None
        return output_dir

    def get_base_url_3839(self):
        url_3839 = self.base_url_3839_var.get()
        if not self.is_valid_url(url_3839):
            messagebox.showerror("設定エラー", f"baseURL (解像度{self.default_resolution_threshold - 1}px以下) のURL形式が正しくありません。")
            return None
        return url_3839

    def get_base_url_3840(self):
        url_3840 = self.base_url_3840_var.get()
        if not self.is_valid_url(url_3840):
            messagebox.showerror("設定エラー", f"baseURL (解像度{self.default_resolution_threshold}px以上) のURL形式が正しくありません。")
            return None
        return url_3840

    def get_shop_url(self):
        shop_url = self.shop_url_var.get()
        if not shop_url:
            messagebox.showerror("設定エラー", "ショップ画像URLを入力してください。")
            return None
        return shop_url

    def get_resolution_threshold(self):
        if not self.separate_url_var.get():
            return self.DEFAULT_RESOLUTION_THRESHOLD
        try:
            threshold = int(self.resolution_threshold_var.get())
            if threshold <= 0 or threshold > 7680:
                messagebox.showerror("設定エラー", "解像度閾値は1以上の数値を入力してください。(上限: 7680px)")
                return None
            return threshold
        except ValueError:
            messagebox.showerror("設定エラー", "解像度閾値には数値を入力してください。")
            return None

    def get_newline_count(self):
        try:
            count = int(self.newline_count_var.get())
            if count < 0 or count > 10:
                messagebox.showerror("設定エラー", "改行数は0以上10以下の整数を入力してください。")
                return None
            return count
        except ValueError:
            messagebox.showerror("設定エラー", "改行数には整数を入力してください。")
            return None

    def get_pre_insert_file_path(self):
        return self.pre_insert_file_path.get()

    def get_post_insert_file_path(self):
        return self.post_insert_file_path.get()

    def get_image_name_separator(self):
        separator = self.image_name_separator_var.get()
        if not separator:
            messagebox.showerror("設定エラー", "出力画像名セパレータを入力してください。")
            return None
        return separator

    def get_image_count_threshold(self):
        try:
            threshold = int(self.image_count_threshold_var.get())
            if threshold < 0:
                messagebox.showerror("設定エラー", "画像数閾値は0以上の整数を入力してください。")
                return None
            return threshold
        except ValueError:
            messagebox.showerror("設定エラー", "画像数閾値には整数を入力してください。")
            return None

    def is_valid_url(self, url):
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def save_settings(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(base_dir, self.CONFIG_FILE_NAME)
        
        config_data = {
            "default_resize_width": self.default_resize_width,
            "default_image_spacing": self.default_image_spacing,
            "default_image_count": self.default_image_count,
            "default_base_url_3839": self.default_base_url_3839,
            "default_base_url_3840": self.default_base_url_3840,
            "default_resolution_threshold": self.default_resolution_threshold,
            "selected_input_data": self.INPUT_DATA_OPTIONS_REVERSE_MAP.get(self.input_data_var.get(), 1),
            "shop_url": self.shop_url_var.get(),
            "separate_url_var": self.separate_url_var.get(),
            "resolution_threshold": self.resolution_threshold_var.get(),
            "default_newline_count": self.default_newline_count,
            "newline_count": self.newline_count_var.get(),
            "default_pre_insert_file_path": self.default_pre_insert_file_path,
            "pre_insert_file_path": self.pre_insert_file_path.get(),
            "default_post_insert_file_path": self.default_post_insert_file_path,
            "post_insert_file_path": self.post_insert_file_path.get(),
            "insert_pc_description": self.insert_pc_description_var.get(),
            "default_image_name_separator": self.default_image_name_separator,
            "write_back": self.write_back_var.get(),
            "default_image_count_threshold": self.default_image_count_threshold,
            "image_count_threshold": self.image_count_threshold_var.get(),
            "default_exclude_linked_images": self.default_exclude_linked_images,
            "exclude_linked_images": self.exclude_linked_images_var.get()
        }
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(f"設定を保存しました: {config_file_path}")
        except Exception as e:
            error_msg = f"エラー[save_settings]: 設定ファイルの保存に失敗しました: {e}"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def load_settings(self):
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            config_file_path = os.path.join(base_dir, self.CONFIG_FILE_NAME)
        except Exception as e:
            print(f"エラー[load_settings]: ベースディレクトリの取得に失敗しました: {e}")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_file_path = os.path.join(base_dir, self.CONFIG_FILE_NAME)

        try:
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.default_resize_width = config_data.get("default_resize_width", self.DEFAULT_RESIZE_WIDTH)
                    self.default_image_spacing = config_data.get("default_image_spacing", self.DEFAULT_IMAGE_SPACING)
                    self.default_image_count = config_data.get("default_image_count", self.DEFAULT_IMAGE_COUNT)
                    self.default_base_url_3839 = config_data.get("default_base_url_3839", self.DEFAULT_BASE_URL_3839)
                    self.default_base_url_3840 = config_data.get("default_base_url_3840", self.DEFAULT_BASE_URL_3840)
                    self.default_resolution_threshold = int(config_data.get("default_resolution_threshold", self.DEFAULT_RESOLUTION_THRESHOLD))
                    selected_input_data_num = config_data.get("selected_input_data", 1)
                    self.selected_input_data.set(self.INPUT_DATA_OPTIONS_MAP.get(selected_input_data_num, self.DEFAULT_INPUT_DATA_OPTION))
                    self.shop_url_var.set(config_data.get("shop_url", self.DEFAULT_SHOP_BASE_URL))
                    self.separate_url_var.set(bool(config_data.get("separate_url_var", False)))
                    self.resolution_threshold_var.set(config_data.get("resolution_threshold", self.default_resolution_threshold))
                    self.default_newline_count = int(config_data.get("default_newline_count", self.DEFAULT_NEWLINE_COUNT))
                    self.newline_count_var.set(config_data.get("newline_count", self.default_newline_count))
                    self.default_pre_insert_file_path = config_data.get("default_pre_insert_file_path", self.DEFAULT_PRE_INSERT_FILE_PATH)
                    self.pre_insert_file_path.set(config_data.get("pre_insert_file_path", ""))
                    self.default_post_insert_file_path = config_data.get("default_post_insert_file_path", self.DEFAULT_POST_INSERT_FILE_PATH)
                    self.post_insert_file_path.set(config_data.get("post_insert_file_path", ""))
                    self.insert_pc_description_var.set(bool(config_data.get("insert_pc_description", self.DEFAULT_INSERT_PC_DESCRIPTION)))
                    self.default_image_name_separator = config_data.get("default_image_name_separator", self.DEFAULT_IMAGE_NAME_SEPARATOR)
                    self.image_name_separator_var.set(self.default_image_name_separator)
                    self.write_back_var.set(bool(config_data.get("write_back", self.DEFAULT_WRITE_BACK)))
                    self.default_image_count_threshold = int(config_data.get("default_image_count_threshold", self.DEFAULT_IMAGE_COUNT_THRESHOLD))
                    self.image_count_threshold_var.set(config_data.get("image_count_threshold", self.default_image_count_threshold))
                    self.default_exclude_linked_images = bool(config_data.get("default_exclude_linked_images", self.DEFAULT_EXCLUDE_LINKED_IMAGES))
                    self.exclude_linked_images_var.set(bool(config_data.get("exclude_linked_images", self.DEFAULT_EXCLUDE_LINKED_IMAGES)))

                    self.resize_width_var.set(self.default_resize_width)
                    self.image_spacing_var.set(self.default_image_spacing)
                    self.base_url_3839_var.set(self.default_base_url_3839)
                    self.base_url_3840_var.set(self.default_base_url_3840)

                    self.update_base_url_labels()
                    self.toggle_resolution_threshold_widgets()

                    print(f"設定ファイルを読み込みました: {config_file_path}")
            else:
                print(f"設定ファイルが見つかりません: {config_file_path}。初期設定を使用します。")
                self.resize_width_var.set(self.default_resize_width)
                self.image_spacing_var.set(self.default_image_spacing)
                self.image_count_combine_var.set(self.default_image_count)
                self.base_url_3839_var.set(self.default_base_url_3839)
                self.base_url_3840_var.set(self.default_base_url_3840)
                self.image_name_separator_var.set(self.default_image_name_separator)
                self.write_back_var.set(self.DEFAULT_WRITE_BACK)
                self.image_count_threshold_var.set(self.default_image_count_threshold)
                self.exclude_linked_images_var.set(self.default_exclude_linked_images)
        except Exception as e:
            error_msg = f"エラー[load_settings]: 設定ファイルの読み込みに失敗しました: {e}。初期設定を使用します。"
            print(error_msg)
            messagebox.showerror("設定エラー", error_msg)

    def update_base_url_labels(self):
        threshold = self.resolution_threshold_var.get()
        self.base_url_3839_label.config(text=f"baseURL (解像度{threshold - 1}px以下):")
        self.base_url_3840_label.config(text=f"baseURL (解像度{threshold}px以上):")

    def toggle_resolution_threshold_widgets(self):
        state = 'normal' if self.separate_url_var.get() else 'disabled'
        self.resolution_threshold_entry.config(state=state)
        if not self.separate_url_var.get():
            threshold = self.DEFAULT_RESOLUTION_THRESHOLD
            self.default_resolution_threshold = threshold
            self.update_base_url_labels()

    def select_input_data_type(self, event=None):
        selected_data_type = self.input_data_var.get()
        is_image_path_selected = selected_data_type == "商品画像パス"
        self.shop_url_entry.config(state='normal' if is_image_path_selected else 'disabled')
        self.selected_input_data.set(selected_data_type)
        self.set_input_data_option()

    def update_progress(self, completed, total):
        if total > 0:
            progress = (completed / total) * 100
            self.progress_var.set(progress)
            self.master.update_idletasks()

    def run_workflow_gui(self):
        try:
            input_path = self.input_file_path.get()
            if not input_path:
                raise ValueError("入力ファイルまたはフォルダを選択してください。")

            resize_width = self.get_resize_width()
            if resize_width is None: return

            image_spacing = self.get_image_spacing()
            if image_spacing is None: return

            image_count_combine = self.get_image_count_combine()
            if image_count_combine is None: return

            output_dir = self.get_output_dir()
            if output_dir is None: return

            base_url_3839 = self.get_base_url_3839()
            if base_url_3839 is None: return

            base_url_3840 = self.get_base_url_3840()
            if base_url_3840 is None: return

            shop_url = None
            if self.input_data_var.get() == "商品画像パス":
                shop_url = self.get_shop_url()
                if shop_url is None: return

            newline_count = self.get_newline_count()
            if newline_count is None: return

            image_name_separator = self.get_image_name_separator()
            if image_name_separator is None: return

            image_count_threshold = self.get_image_count_threshold()
            if image_count_threshold is None: return

            pre_insert_file_path = self.get_pre_insert_file_path()
            post_insert_file_path = self.get_post_insert_file_path()

            self.output_dir = output_dir
            print("画像処理ワークフローを開始します...")

            workflow_params = {
                'input_path': input_path,
                'resize_width': resize_width,
                'image_spacing': image_spacing,
                'image_count_combine': image_count_combine,
                'output_dir': output_dir,
                'base_url_3839': base_url_3839,
                'base_url_3840': base_url_3840,
                'selected_input_data_type': self.input_data_var.get(),
                'shop_url': shop_url,
                'resolution_threshold': self.get_resolution_threshold(),
                'newline_count': newline_count,
                'image_name_separator': image_name_separator,
                'image_count_threshold': image_count_threshold,
                'pre_insert_file_path': pre_insert_file_path,
                'post_insert_file_path': post_insert_file_path,
                'insert_pc_description': self.insert_pc_description_var.get(),
                'write_back': self.write_back_var.get(),
                'exclude_linked_images': self.exclude_linked_images_var.get(),
            }

            self.stop_event.clear()  # 停止フラグをリセット
            self.progress_var.set(0)  # プログレスバーをリセット
            self.run_button.config(text="中止", command=self.stop_workflow)
            self.master.config(cursor="wait")
            threading.Thread(target=self.process_workflow, args=(workflow_params,), daemon=True).start()
        except Exception as e:
            error_msg = f"エラー[run_workflow_gui]: ワークフロー実行中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ワークフローエラー", error_msg)
            self.reset_ui()

    def stop_workflow(self):
        self.stop_event.set()  # 停止フラグをセット
        print("処理を中断します...")
        self.reset_ui()

    def reset_ui(self):
        self.run_button.config(text="画像処理開始", command=self.run_workflow_gui)
        self.master.config(cursor="")
        self.progress_var.set(0)

    def process_workflow(self, params):
        try:
            input_path = params['input_path']
            resize_width = params['resize_width']
            image_spacing = params['image_spacing']
            image_count_combine = params['image_count_combine']
            output_dir = params['output_dir']
            base_url_3839 = params['base_url_3839']
            base_url_3840 = params['base_url_3840']
            selected_input_data_type = params['selected_input_data_type']
            shop_url = params['shop_url']
            resolution_threshold = params['resolution_threshold']
            newline_count = params['newline_count']
            image_name_separator = params['image_name_separator']
            image_count_threshold = params['image_count_threshold']
            pre_insert_file_path = params['pre_insert_file_path']
            post_insert_file_path = params['post_insert_file_path']
            insert_pc_description = params['insert_pc_description']
            write_back = params['write_back']
            exclude_linked_images = params['exclude_linked_images']

            pc_itemdata_path = None
            if insert_pc_description and selected_input_data_type != "ローカルフォルダ" and selected_input_data_type != "ダウンロードリスト":
                pc_itemdata_path = self.create_pc_itemdata_csv(input_path, output_dir)
                if not pc_itemdata_path:
                    raise ValueError("PC用商品説明文中間ファイルの作成に失敗しました。")
                if self.stop_event.is_set():
                    raise RuntimeError("処理がユーザーにより中断されました。")

            if selected_input_data_type == "ローカルフォルダ":
                stage2_output = self.process_local_folder_gui(input_path, output_dir, resize_width, image_spacing, image_count_combine, image_name_separator)
                if not stage2_output:
                    raise RuntimeError("ローカルフォルダ処理が失敗しました。")
                print("処理終了: ローカルフォルダ画像処理が完了しました。")
            else:
                stage1_output = self.process_initial_csv_gui(input_path, selected_input_data_type, shop_url, image_count_threshold, exclude_linked_images)
                if not stage1_output:
                    raise RuntimeError("Stage 1 が失敗しました。")
                print("処理終了: Stage 1 (画像URL抽出) が完了しました。")

                stage2_output = self.process_images_gui(stage1_output, output_dir, resize_width, image_spacing, image_count_combine, image_name_separator)
                if not stage2_output:
                    raise RuntimeError("Stage 2 が失敗しました。")
                print("処理終了: Stage 2 (画像ダウンロードと処理) が完了しました。")

            if not self.process_final_csv_gui(stage2_output, output_dir, base_url_3839, base_url_3840, resolution_threshold, newline_count, pre_insert_file_path, post_insert_file_path, insert_pc_description, pc_itemdata_path):
                raise RuntimeError("Stage 3 が失敗しました。")
            print("処理終了: Stage 3 (HTML生成) が完了しました。")

            if write_back and selected_input_data_type != "ローカルフォルダ" and selected_input_data_type != "ダウンロードリスト":
                output_html_csv = os.path.join(output_dir, "csv", f'html_list_{self.timestamp}.csv')
                if not self.write_back_to_input_csv(input_path, output_html_csv, output_dir):
                    raise RuntimeError("入力CSVへの書き戻しが失敗しました。")
                print("処理終了: 入力CSVへの書き戻しが完了しました。")

            print("処理終了: すべての画像処理ワークフローが正常に完了しました。")
            self.master.after(0, lambda: messagebox.showinfo("完了", "すべての処理が完了しました。"))
        except Exception as e:
            error_msg = f"エラー[process_workflow]: ワークフロー処理中にエラーが発生しました: {e}"
            print(error_msg)
            self.master.after(0, lambda: messagebox.showerror("ワークフローエラー", error_msg))
        finally:
            self.master.after(0, self.reset_ui)

    def write_back_to_input_csv(self, input_file, output_html_csv, output_dir):
        try:
            print("入力CSVにデータを書き戻す処理を開始します...")

            with open(output_html_csv, 'r', encoding='cp932', newline='') as f:
                reader = csv.DictReader(f)
                html_data = {row['商品管理番号（商品URL）']: row['スマートフォン用商品説明文'] for row in reader}

            input_data = []
            with open(input_file, 'r', encoding='cp932', newline='') as infile:
                reader = csv.DictReader(infile)
                input_data = list(reader)
                fieldnames = reader.fieldnames

            if "商品管理番号（商品URL）" not in fieldnames or "スマートフォン用商品説明文" not in fieldnames:
                raise ValueError("入力CSVに必要なカラム（'商品管理番号（商品URL）', 'スマートフォン用商品説明文'）が見つかりません。")

            seen_product_ids = set()
            for row in input_data:
                product_id = row['商品管理番号（商品URL）']
                if product_id in html_data and product_id not in seen_product_ids:
                    row['スマートフォン用商品説明文'] = html_data[product_id]
                    seen_product_ids.add(product_id)

            input_filename = os.path.basename(input_file)
            output_path = os.path.join(output_dir, "csv", f"done_{input_filename}")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='cp932', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(input_data)

            print(f"入力CSVのコピーにデータを書き戻しました: {output_path}")
            return True
        except Exception as e:
            error_msg = f"エラー[write_back_to_input_csv]: 入力CSVへの書き戻し中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("書き戻しエラー", error_msg)
            return False

    def create_pc_itemdata_csv(self, input_file, output_dir):
        output_path = os.path.join(output_dir, "csv", f"pc_itemdata_{self.timestamp}.csv")
        results = []
        try:
            with open(input_file, 'r', encoding='cp932', newline='\r\n') as infile:
                reader = csv.DictReader(infile)
                if "商品管理番号（商品URL）" not in reader.fieldnames or "PC用商品説明文" not in reader.fieldnames:
                    raise ValueError("必要なカラム（'商品管理番号（商品URL）', 'PC用商品説明文'）が入力CSVファイルに見つかりません。")

                for row in reader:
                    if self.stop_event.is_set():
                        return None
                    pc_description = row.get("PC用商品説明文", "").strip()
                    product_id = row["商品管理番号（商品URL）"]
                    if pc_description:
                        results.append({
                            "商品管理番号（商品URL）": product_id,
                            "PC用商品説明文": pc_description
                        })

            if results:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='cp932', newline='\r\n') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=["商品管理番号（商品URL）", "PC用商品説明文"])
                    writer.writeheader()
                    writer.writerows(results)
                print(f"PC用商品説明文中間ファイルを作成しました: {output_path}")
                return output_path
            else:
                print("PC用商品説明文が存在するデータが見つかりませんでした。")
                return None
        except Exception as e:
            error_msg = f"エラー[create_pc_itemdata_csv]: PC用商品説明文中間ファイル作成中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ファイルエラー", error_msg)
            return None

    def process_initial_csv_gui(self, input_path, selected_input_data_type, shop_url, image_count_threshold, exclude_linked_images):
        output_path_csv = os.path.join(self.output_dir, "csv", f"{os.path.splitext(os.path.basename(input_path))[0]}_imglist.csv")
        results = []
        try:
            print("Stage 1: 画像URL抽出 開始...")
            with open(input_path, 'r', encoding='cp932', newline='') as infile:
                reader = csv.DictReader(infile)
                data = list(reader)
                self.total_tasks = len(data)  # 総タスク数を設定
                self.completed_tasks = 0

                if selected_input_data_type == "ダウンロードリスト":
                    if not all(field in reader.fieldnames for field in ['商品管理番号', '画像リスト', '連番']):
                        raise ValueError("ダウンロードリストCSVに必要なカラム（'商品管理番号', '画像リスト', '連番'）が見つかりません。")
                    
                    product_image_counts = defaultdict(int)
                    for row in data:
                        if self.stop_event.is_set():
                            return None
                        product_id = row['商品管理番号']
                        product_image_counts[product_id] += 1
                        results.append({
                            "商品管理番号": row['商品管理番号'],
                            "画像リスト": row['画像リスト'],
                            "連番": row['連番'],
                            "スペース": row.get('スペース', '')  # スペースカラムがあれば取得、なければ空文字
                        })
                        self.completed_tasks += 1
                        self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))

                    # 画像数閾値でフィルタリング
                    filtered_results = []
                    for row in results:
                        product_id = row['商品管理番号']
                        if product_image_counts[product_id] >= image_count_threshold:
                            filtered_results.append(row)
                    results = filtered_results

                elif selected_input_data_type in ["スマートフォン用商品説明文", "PC用販売説明文"]:
                    input_column_name = "スマートフォン用商品説明文" if selected_input_data_type == "スマートフォン用商品説明文" else "PC用販売説明文"
                    if input_column_name not in reader.fieldnames or "商品管理番号（商品URL）" not in reader.fieldnames:
                        raise ValueError(f"必要なカラム（'{input_column_name}', '商品管理番号（商品URL）'）がCSVファイルに見つかりません。")

                    for row in data:
                        if self.stop_event.is_set():
                            return None
                        html_content = row[input_column_name]
                        if not html_content:
                            continue
                        image_urls = self.extract_images_from_html(html_content, exclude_linked_images)
                        if len(image_urls) >= image_count_threshold:
                            product_id = row["商品管理番号（商品URL）"]
                            for i, url in enumerate(image_urls, 1):
                                results.append({
                                    "商品管理番号": product_id,
                                    "画像リスト": url,
                                    "連番": i,
                                    "スペース": ''  # デフォルトではスペースカラムは空
                                })
                        self.completed_tasks += 1
                        self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))
                elif selected_input_data_type == "商品画像パス":
                    results = self.extract_image_paths_from_row(data, shop_url)

            if not results:
                print("条件に合う画像が見つかりませんでした。")
                return None

            os.makedirs(os.path.dirname(output_path_csv), exist_ok=True)
            with open(output_path_csv, 'w', encoding='cp932', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=["商品管理番号", "画像リスト", "連番", "スペース"])
                writer.writeheader()
                writer.writerows(results)
            print(f"Stage 1 完了: {output_path_csv}")
            return output_path_csv
        except Exception as e:
            error_msg = f"エラー[process_initial_csv_gui]: Stage 1 処理中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("Stage 1 エラー", error_msg)
            return None

    def extract_image_paths_from_row(self, data, shop_url):
        results = []
        try:
            if not shop_url:
                raise ValueError("ショップ画像URLを入力してください。")

            self.total_tasks = len(data)
            self.completed_tasks = 0
            for row in data:
                if self.stop_event.is_set():
                    return None
                product_id = row.get("商品管理番号（商品URL）")
                if not product_id:
                    continue

                has_image_path = False
                for i in range(1, 21):
                    image_path_key = f"商品画像パス{i}"
                    image_path = row.get(image_path_key)
                    if image_path:
                        has_image_path = True
                        full_url = f"{shop_url}cabinet{image_path}"
                        results.append({
                            "商品管理番号": product_id,
                            "画像リスト": full_url,
                            "連番": i,
                            "スペース": ''  # デフォルトではスペースカラムは空
                        })
                if not has_image_path:
                    continue
                self.completed_tasks += 1
                self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))
            return results
        except Exception as e:
            error_msg = f"エラー[extract_image_paths_from_row]: 画像パス抽出中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("抽出エラー", error_msg)
            return None

    def process_local_folder_gui(self, input_folder, output_dir, resize_width, image_spacing, image_count_combine, image_name_separator):
        image_info = []
        images_output_dir = os.path.join(output_dir, "images")
        try:
            print("ローカルフォルダ画像処理 開始...")
            os.makedirs(images_output_dir, exist_ok=True)
            print(f"出力ディレクトリを作成しました: {images_output_dir}")

            subfolders = [f for f in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, f))]
            self.total_tasks = len(subfolders)
            self.completed_tasks = 0

            for subfolder in subfolders:
                if self.stop_event.is_set():
                    return None
                subfolder_path = os.path.join(input_folder, subfolder)
                product_id = subfolder
                image_files = [f for f in os.listdir(subfolder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                image_files = sorted(image_files, key=self.natural_sort_key)

                if len(image_files) < self.get_image_count_threshold():
                    print(f"商品ID {product_id} は画像数が閾値未満のためスキップします。")
                    continue

                sp_count = 1
                for i in range(0, len(image_files), image_count_combine):
                    output_filename = f"{product_id}{image_name_separator}{sp_count}.jpg"
                    output_path = os.path.join(images_output_dir, output_filename)

                    selected_files = image_files[i:i+image_count_combine]
                    image_paths = [os.path.join(subfolder_path, f) for f in selected_files]
                    try:
                        images = [self.resize_image_gui(img_path, resize_width) for img_path in image_paths]
                        if images:
                            # ローカルフォルダではスペースカラムがないため、デフォルトの間隔を使用
                            combined = self.combine_images_gui(images, image_spacing, None)
                            combined.save(output_path, quality=95)
                            image_info.append({
                                '商品管理番号': product_id,
                                '画像名': output_filename,
                                '解像度': str(combined.height)
                            })
                    except Exception as e:
                        print(f"エラー[process_local_folder_gui]: 画像処理中にエラーが発生しました (商品ID: {product_id}, ファイル: {selected_files}): {e}")
                    sp_count += 1
                self.completed_tasks += 1
                self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))

            output_csv_path = os.path.join(output_dir, "csv", f"image_list_{self.timestamp}.csv")
            os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
            with open(output_csv_path, 'w', encoding='cp932', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['商品管理番号', '画像名', '解像度'])
                writer.writeheader()
                writer.writerows(image_info)

            print(f"ローカルフォルダ処理 完了: {output_csv_path}")
            return output_csv_path
        except Exception as e:
            error_msg = f"エラー[process_local_folder_gui]: ローカルフォルダ処理中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("ローカルフォルダエラー", error_msg)
            return None

    def process_images_gui(self, input_csv, output_dir, resize_width, image_spacing, image_count_combine, image_name_separator):
        image_info = []
        images_output_dir = os.path.join(output_dir, "images")
        try:
            print("Stage 2: 画像ダウンロードと処理 開始...")
            os.makedirs(images_output_dir, exist_ok=True)
            print(f"出力ディレクトリを作成しました: {images_output_dir}")

            with open(input_csv, 'r', encoding='cp932', newline='') as f:
                reader = csv.DictReader(f)
                image_data = list(reader)
                if not image_data:
                    raise ValueError("画像リストCSVファイルが空です。")

            processed_files = defaultdict(list)
            image_spacing_map = defaultdict(list)  # 商品IDごとのスペースリスト
            self.total_tasks = len(image_data)
            self.completed_tasks = 0

            for row in image_data:
                if self.stop_event.is_set():
                    return None
                product_id = row['商品管理番号']
                image_url = row['画像リスト']
                seq_num = row['連番']
                space = row.get('スペース', '')

                product_dir = os.path.join(self.base_dir, product_id)
                os.makedirs(product_dir, exist_ok=True)

                image_filename = f"{product_id}{seq_num}.jpg"
                image_path = os.path.join(product_dir, image_filename)

                if self.download_image_gui(image_url, image_path):
                    try:
                        resized = self.resize_image_gui(image_path, resize_width)
                        resized.save(image_path, quality=95)
                        processed_files[product_id].append(image_filename)
                        image_spacing_map[product_id].append(space)
                    except Exception as resize_e:
                        print(f"エラー[process_images_gui]: 画像リサイズ処理中にエラーが発生しました (商品ID: {product_id}, ファイル: {image_filename}): {resize_e}")
                self.completed_tasks += 1
                self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))

            for product_id, files in processed_files.items():
                if self.stop_event.is_set():
                    return None
                source_dir = os.path.join(self.base_dir, product_id)
                sp_count = 1
                sorted_files = sorted(files, key=self.natural_sort_key)
                sorted_spaces = [image_spacing_map[product_id][files.index(f)] for f in sorted_files]

                for i in range(0, len(sorted_files), image_count_combine):
                    output_filename = f"{product_id}{image_name_separator}{sp_count}.jpg"
                    output_path = os.path.join(images_output_dir, output_filename)

                    selected_files = sorted_files[i:i+image_count_combine]
                    selected_spaces = sorted_spaces[i:i+image_count_combine]
                    image_paths = [os.path.join(source_dir, f) for f in selected_files]
                    try:
                        images = [self.resize_image_gui(img_path, resize_width) for img_path in image_paths]
                        if images:
                            combined = self.combine_images_gui(images, image_spacing, selected_spaces)
                            combined.save(output_path, quality=95)
                            image_info.append({
                                '商品管理番号': product_id,
                                '画像名': output_filename,
                                '解像度': str(combined.height)
                            })
                    except Exception as combine_e:
                        print(f"エラー[process_images_gui]: 画像結合処理中にエラーが発生しました (商品ID: {product_id}, ファイル: {selected_files}): {combine_e}")
                    sp_count += 1

            output_csv_path = os.path.join(output_dir, "csv", f"image_list_{self.timestamp}.csv")
            os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
            with open(output_csv_path, 'w', encoding='cp932', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['商品管理番号', '画像名', '解像度'])
                writer.writeheader()
                writer.writerows(image_info)

            print(f"Stage 2 完了: {output_csv_path}")
            return output_csv_path
        except Exception as e:
            error_msg = f"エラー[process_images_gui]: Stage 2 処理中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("Stage 2 エラー", error_msg)
            return None

    def process_final_csv_gui(self, input_file, output_dir, base_url_3839, base_url_3840, resolution_threshold, newline_count, pre_insert_file_path, post_insert_file_path, insert_pc_description, pc_itemdata_path):
        try:
            print("Stage 3: HTML生成 開始...")
            product_data = defaultdict(list)

            with open(input_file, 'r', encoding='cp932', newline='') as f:
                reader = csv.DictReader(f)
                image_data = list(reader)
                if not image_data or not all(field in reader.fieldnames for field in ['商品管理番号', '画像名', '解像度']):
                    raise ValueError("必要なカラム('商品管理番号', '画像名', '解像度')がCSVファイルに見つかりません。")

                self.total_tasks = len(image_data)
                self.completed_tasks = 0

                for row in image_data:
                    if self.stop_event.is_set():
                        return None
                    product_id = row['商品管理番号']
                    image_name = row['画像名']
                    resolution = row['解像度']
                    html = self.generate_image_html_gui(image_name, resolution, base_url_3839, base_url_3840, resolution_threshold, newline_count)
                    product_data[product_id].append(html)
                    self.completed_tasks += 1
                    self.master.after(0, lambda: self.update_progress(self.completed_tasks, self.total_tasks))

            pc_descriptions = {}
            if insert_pc_description and pc_itemdata_path and os.path.exists(pc_itemdata_path):
                with open(pc_itemdata_path, 'r', encoding='cp932', newline='\r\n') as f:
                    reader = csv.DictReader(f)
                    pc_descriptions = {row["商品管理番号（商品URL）"]: row["PC用商品説明文"] for row in reader}

            output_data = []
            for product_id, html_list in product_data.items():
                if self.stop_event.is_set():
                    return None
                combined_html = ''.join(html_list)

                pre_insert_data = ""
                if pre_insert_file_path and os.path.exists(pre_insert_file_path):
                    try:
                        with open(pre_insert_file_path, 'r', encoding='cp932', newline='\r\n') as insert_file:
                            pre_insert_data = insert_file.read()
                    except Exception as e:
                        print(f"警告[process_final_csv_gui]: 差し込みデータ前 ファイル読み込みエラー: {e}")

                post_insert_data = ""
                if post_insert_file_path and os.path.exists(post_insert_file_path):
                    try:
                        with open(post_insert_file_path, 'r', encoding='cp932', newline='\r\n') as insert_file:
                            post_insert_data = insert_file.read()
                    except Exception as e:
                        print(f"警告[process_final_csv_gui]: 差し込みデータ後 ファイル読み込みエラー: {e}")

                pc_description_data = pc_descriptions.get(product_id, "") if insert_pc_description else ""
                full_html = pre_insert_data + combined_html + post_insert_data + pc_description_data

                output_data.append({
                    '商品管理番号（商品URL）': product_id,
                    'スマートフォン用商品説明文': full_html
                })

            output_file_path = os.path.join(output_dir, "csv", f'html_list_{self.timestamp}.csv')
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            with open(output_file_path, 'w', encoding='cp932', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['商品管理番号（商品URL）', 'スマートフォン用商品説明文'])
                writer.writeheader()
                writer.writerows(output_data)

            print(f"Stage 3 完了: {output_file_path}")
            return True
        except Exception as e:
            error_msg = f"エラー[process_final_csv_gui]: Stage 3 処理中にエラーが発生しました: {e}"
            print(error_msg)
            messagebox.showerror("Stage 3 エラー", error_msg)
            return False

    def download_image_gui(self, url, save_path):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        except requests.exceptions.RequestException as e:
            error_msg = f"エラー[download_image_gui]: 画像のダウンロードに失敗しました: {url}: {e}"
            print(error_msg)
            return False

    def resize_image_gui(self, image_path, target_width):
        try:
            with Image.open(image_path) as img:
                w_ratio = target_width / img.width
                target_height = int(img.height * w_ratio)
                return img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        except Exception as e:
            error_msg = f"エラー[resize_image_gui]: 画像リサイズ処理に失敗しました: {image_path}: {e}"
            print(error_msg)
            raise

    def combine_images_gui(self, images, default_spacing, space_values=None):
        try:
            if not images:
                return None
            target_width = self.get_resize_width() or self.default_resize_width
            
            # スペース値の処理
            if space_values:
                spacings = []
                for space in space_values:
                    try:
                        # スペース値が空または無効な場合はデフォルトの間隔を使用
                        spacings.append(int(space) if space.strip() else default_spacing)
                    except ValueError:
                        spacings.append(default_spacing)
            else:
                spacings = [default_spacing] * (len(images) - 1)

            # 画像の高さとスペースの合計でキャンバスの高さを計算
            total_height = sum(img.height for img in images) + sum(spacings)
            combined = Image.new('RGB', (target_width, total_height), 'white')
            current_y = 0

            for i, img in enumerate(images):
                combined.paste(img, (0, current_y))
                if i < len(images) - 1:
                    current_y += img.height + spacings[i]
                else:
                    current_y += img.height
            return combined
        except Exception as e:
            error_msg = f"エラー[combine_images_gui]: 画像結合処理に失敗しました: {e}"
            print(error_msg)
            raise

    def generate_image_html_gui(self, image_name, resolution, base_url_3839, base_url_3840, resolution_threshold, newline_count):
        try:
            url = f"{base_url_3839}{image_name}" if int(resolution) < resolution_threshold else f"{base_url_3840}{image_name}"
            newline_str = "<br>" * newline_count
            return f'<img src="{url}" width="100%" border="0">{newline_str}'
        except Exception as e:
            error_msg = f"エラー[generate_image_html_gui]: HTML生成中にエラーが発生しました: {e}"
            print(error_msg)
            raise

    def extract_images_from_html(self, html_content, exclude_linked_images=True):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            if exclude_linked_images:
                for a_tag in soup.find_all('a'):
                    for img in a_tag.find_all('img'):
                        img.decompose()
            return [img['src'] for img in soup.find_all('img') if img.get('src')]
        except Exception as e:
            error_msg = f"エラー[extract_images_from_html]: HTMLからの画像抽出中にエラーが発生しました: {e}"
            print(error_msg)
            return []

    def natural_sort_key(self, s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        self.text_widget.config(state='normal')
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')

    def flush(self):
        pass

def main():
    root = tk.Tk()
    gui = ImageProcessorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()