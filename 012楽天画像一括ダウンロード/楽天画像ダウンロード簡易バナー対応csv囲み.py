import tkinter as tk
from tkinter import filedialog, ttk, messagebox, colorchooser
import pandas as pd
import requests
from PIL import Image
import os
import datetime
import configparser
import shutil
import re
from urllib.parse import urlparse

class RakutenImageProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("楽天/Yahoo!画像処理ツール")
        self.config = configparser.ConfigParser()
        self.config_file = "settings.ini"
        self.setup_gui()
        self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            if 'DEFAULT' in self.config:
                self.input_csv_var.set(self.config['DEFAULT'].get('input_csv', ''))
                self.output_csv_var.set(self.config['DEFAULT'].get('output_csv', ''))
                self.store_url_values['楽天'] = self.config['DEFAULT'].get('rakuten_store_url', self.config['DEFAULT'].get('store_url', ''))
                self.store_url_values['Yahoo!'] = self.config['DEFAULT'].get('yahoo_store_url', '')
                self.image_dir_var.set(self.config['DEFAULT'].get('image_dir', ''))
                self.sku_option_var.set(self.config['DEFAULT'].getboolean('sku_option', False))
                self.width_var.set(self.config['DEFAULT'].get('width', ''))
                self.canvas_height_var.set(self.config['DEFAULT'].get('canvas_height', ''))
                self.canvas_width_var.set(self.config['DEFAULT'].get('canvas_width', ''))
                self.alignment_var.set(self.config['DEFAULT'].get('alignment', '左上で合わせる'))
                self.scale_var.set(self.config['DEFAULT'].getboolean('scale', False))
                self.margin_var.set(self.config['DEFAULT'].get('margin', ''))
                self.canvas_color_var.set(self.config['DEFAULT'].get('canvas_color', '#FFFFFF'))
                self.color_button.configure(bg=self.canvas_color_var.get())
                self.prefix_var.set(self.config['DEFAULT'].get('prefix', ''))
                self.suffix_var.set(self.config['DEFAULT'].get('suffix', ''))
                self.set_active_mall(self.config['DEFAULT'].get('mall', '楽天'), preserve_current=False)
                self.discount_base_col_var.set(self.config['DEFAULT'].get('discount_base_col', ''))
                self.discount_sale_col_var.set(self.config['DEFAULT'].get('discount_sale_col', ''))
                self.refresh_csv_columns()
                window_geometry = self.config['DEFAULT'].get('window_geometry', '')
                if window_geometry:
                    try:
                        self.root.geometry(window_geometry)
                    except tk.TclError:
                        pass

    def save_settings(self):
        self.save_active_store_url()
        self.config['DEFAULT'] = {
            'input_csv': self.input_csv_var.get(),
            'output_csv': self.output_csv_var.get(),
            'store_url': self.store_url_values.get('楽天', ''),
            'rakuten_store_url': self.store_url_values.get('楽天', ''),
            'yahoo_store_url': self.store_url_values.get('Yahoo!', ''),
            'image_dir': self.image_dir_var.get(),
            'sku_option': str(self.sku_option_var.get()),
            'width': self.width_var.get(),
            'canvas_height': self.canvas_height_var.get(),
            'canvas_width': self.canvas_width_var.get(),
            'alignment': self.alignment_var.get(),
            'scale': str(self.scale_var.get()),
            'margin': self.margin_var.get(),
            'canvas_color': self.canvas_color_var.get(),
            'prefix': self.prefix_var.get(),
            'suffix': self.suffix_var.get(),
            'mall': self.mall_var.get(),
            'discount_base_col': self.discount_base_col_var.get(),
            'discount_sale_col': self.discount_sale_col_var.get(),
            'window_geometry': self.root.geometry()
        }
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def setup_gui(self):
        self.root.columnconfigure(0, weight=1)

        # データ作成グループ
        data_frame = ttk.LabelFrame(self.root, text="データ作成", padding=10)
        data_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        data_frame.columnconfigure(1, weight=1)

        # 楽天商品.csv
        ttk.Label(data_frame, text="対象モール:").grid(row=0, column=0, sticky="w", pady=5)
        self.mall_var = tk.StringVar(value="楽天")
        self.current_store_mall = "楽天"
        self.store_url_values = {"楽天": "", "Yahoo!": ""}
        self.mall_combo = ttk.Combobox(data_frame, textvariable=self.mall_var, values=["楽天", "Yahoo!"], width=12, state="readonly")
        self.mall_combo.grid(row=0, column=1, sticky="w", pady=5)
        self.mall_combo.bind("<<ComboboxSelected>>", lambda event: self.on_mall_change(self.mall_var.get()))

        ttk.Label(data_frame, text="商品CSV:").grid(row=1, column=0, sticky="w", pady=5)
        self.input_csv_var = tk.StringVar()
        ttk.Entry(data_frame, textvariable=self.input_csv_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(data_frame, text="参照", command=self.browse_input_csv).grid(row=1, column=2, pady=5)

        # 出力CSV
        ttk.Label(data_frame, text="出力CSV:").grid(row=2, column=0, sticky="w", pady=5)
        self.output_csv_var = tk.StringVar()
        ttk.Entry(data_frame, textvariable=self.output_csv_var).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Button(data_frame, text="参照", command=self.browse_output_csv).grid(row=2, column=2, pady=5)

        # 店舗URL
        self.store_url_label = ttk.Label(data_frame, text="楽天店舗URL:")
        self.store_url_label.grid(row=3, column=0, sticky="w", pady=5)
        self.store_url_var = tk.StringVar()
        self.store_url_entry = ttk.Entry(data_frame, textvariable=self.store_url_var)
        self.store_url_entry.grid(row=3, column=1, sticky="ew", pady=5)

        # SKU画像オプション
        self.sku_option_var = tk.BooleanVar(value=False)
        self.sku_option_check = ttk.Checkbutton(data_frame, text="SKU画像も作成する（楽天）", variable=self.sku_option_var)
        self.sku_option_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

        # 割引率計算
        discount_frame = ttk.LabelFrame(data_frame, text="割引率計算", padding=8)
        discount_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        discount_frame.columnconfigure(1, weight=1)
        discount_frame.columnconfigure(3, weight=1)
        ttk.Label(discount_frame, text="基準価格列:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=3)
        self.discount_base_col_var = tk.StringVar()
        self.discount_base_col_combo = ttk.Combobox(discount_frame, textvariable=self.discount_base_col_var, width=24, state="readonly")
        self.discount_base_col_combo.grid(row=0, column=1, sticky="ew", pady=3)
        self.discount_base_col_combo.configure(postcommand=self.refresh_csv_columns)
        ttk.Label(discount_frame, text="割引後価格列:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=3)
        self.discount_sale_col_var = tk.StringVar()
        self.discount_sale_col_combo = ttk.Combobox(discount_frame, textvariable=self.discount_sale_col_var, width=24, state="readonly")
        self.discount_sale_col_combo.grid(row=0, column=3, sticky="ew", pady=3)
        self.discount_sale_col_combo.configure(postcommand=self.refresh_csv_columns)
        ttk.Button(discount_frame, text="列再取得", command=self.refresh_csv_columns).grid(row=0, column=4, padx=(10, 0), pady=3)
        ttk.Label(discount_frame, text="未選択または割引なしの場合は空欄").grid(row=1, column=1, columnspan=4, sticky="w", pady=3)

        # データ加工グループ
        process_frame = ttk.LabelFrame(self.root, text="データ加工", padding=10)
        process_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        process_frame.columnconfigure(1, weight=1)

        # 画像解像度(幅)
        ttk.Label(process_frame, text="画像解像度(幅):").grid(row=0, column=0, sticky="w", pady=5)
        self.width_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.width_var, width=10).grid(row=0, column=1, sticky="w", pady=5)
        ttk.Label(process_frame, text="px").grid(row=0, column=2, sticky="w", pady=5)

        # キャンバス解像度
        ttk.Label(process_frame, text="キャンバス解像度を変更:").grid(row=1, column=0, sticky="w", pady=5)
        self.canvas_height_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.canvas_height_var, width=10).grid(row=1, column=1, sticky="w", pady=5)
        ttk.Label(process_frame, text="px").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Label(process_frame, text="×").grid(row=1, column=3, sticky="w", pady=5)
        self.canvas_width_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.canvas_width_var, width=10).grid(row=1, column=4, sticky="w", pady=5)
        ttk.Label(process_frame, text="px").grid(row=1, column=5, sticky="w", pady=5)

        # 配置
        ttk.Label(process_frame, text="配置:").grid(row=2, column=0, sticky="w", pady=5)
        self.alignment_var = tk.StringVar(value="左上で合わせる")
        alignments = ["左上で合わせる", "左中央で合わせる", "左下で合わせる", "右上で合わせる", "右中央で合わせる", "右下で合わせる"]
        ttk.OptionMenu(process_frame, self.alignment_var, "左上で合わせる", *alignments).grid(row=2, column=1, sticky="w", pady=5)

        # キャンバスカラー
        ttk.Label(process_frame, text="キャンバスカラー:").grid(row=3, column=0, sticky="w", pady=5)
        self.canvas_color_var = tk.StringVar(value="#FFFFFF")
        self.color_button = tk.Button(process_frame, text="色を選択", command=self.choose_color, bg="#FFFFFF")
        self.color_button.grid(row=3, column=1, sticky="w", pady=5)

        # スケーリング
        self.scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(process_frame, text="スケーリング", variable=self.scale_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

        # 余白
        ttk.Label(process_frame, text="余白:").grid(row=5, column=0, sticky="w", pady=5)
        self.margin_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.margin_var, width=10).grid(row=5, column=1, sticky="w", pady=5)
        ttk.Label(process_frame, text="px").grid(row=5, column=2, sticky="w", pady=5)

        # 楽天画像フォルダ名
        ttk.Label(process_frame, text="楽天画像フォルダ名:").grid(row=6, column=0, sticky="w", pady=5)
        self.image_dir_var = tk.StringVar()
        self.image_dir_entry = ttk.Entry(process_frame, textvariable=self.image_dir_var)
        self.image_dir_entry.grid(row=6, column=1, sticky="ew", pady=5)

        # ファイル名先頭
        ttk.Label(process_frame, text="ファイル名先頭に挿入:").grid(row=7, column=0, sticky="w", pady=5)
        self.prefix_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.prefix_var).grid(row=7, column=1, sticky="ew", pady=5)

        # ファイル名末尾
        ttk.Label(process_frame, text="ファイル名の末尾に追加:").grid(row=8, column=0, sticky="w", pady=5)
        self.suffix_var = tk.StringVar()
        ttk.Entry(process_frame, textvariable=self.suffix_var).grid(row=8, column=1, sticky="ew", pady=5)

        # ボタン
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=2, column=0, pady=10)
        ttk.Button(button_frame, text="設定保存", command=self.save_config).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="実行", command=self.process_images).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="2種類のCSVヘルプ", command=self.show_output_csv_help).grid(row=0, column=2, padx=5)

    def choose_color(self):
        color = colorchooser.askcolor(title="キャンバスカラーを選択", initialcolor=self.canvas_color_var.get())
        if color[1]:  # color[1]は16進数のカラーコード（例：#FFFFFF）
            self.canvas_color_var.set(color[1])
            self.color_button.configure(bg=color[1])

    def browse_input_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.input_csv_var.set(file_path)
            output_path = os.path.join(os.path.dirname(file_path), f"Processed_{os.path.basename(file_path)}")
            self.output_csv_var.set(output_path)
            self.refresh_csv_columns()

    def browse_output_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.output_csv_var.set(file_path)

    def save_active_store_url(self):
        if hasattr(self, 'store_url_values') and hasattr(self, 'current_store_mall'):
            self.store_url_values[self.current_store_mall] = self.store_url_var.get()

    def set_active_mall(self, mall, preserve_current=True):
        if preserve_current:
            self.save_active_store_url()
        self.current_store_mall = mall
        self.mall_var.set(mall)
        self.store_url_var.set(self.store_url_values.get(mall, ''))
        if mall == "Yahoo!":
            self.store_url_label.configure(text="ストアアカウント:")
            if hasattr(self, 'image_dir_entry'):
                self.image_dir_entry.configure(state="disabled")
            if hasattr(self, 'sku_option_check'):
                self.sku_option_check.configure(state="disabled")
        else:
            self.store_url_label.configure(text="ショップURL:")
            if hasattr(self, 'image_dir_entry'):
                self.image_dir_entry.configure(state="normal")
            if hasattr(self, 'sku_option_check'):
                self.sku_option_check.configure(state="normal")

    def on_mall_change(self, mall):
        self.set_active_mall(mall)

    def refresh_csv_columns(self):
        csv_path = self.input_csv_var.get()
        columns = ['']
        if csv_path and os.path.exists(csv_path):
            for encoding in ('cp932', 'shift_jis', 'utf-8-sig'):
                try:
                    columns.extend(pd.read_csv(csv_path, encoding=encoding, nrows=0).columns.tolist())
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    break
        current_base = self.discount_base_col_var.get()
        current_sale = self.discount_sale_col_var.get()
        self.discount_base_col_combo['values'] = columns
        self.discount_sale_col_combo['values'] = columns
        if current_base in columns:
            self.discount_base_col_var.set(current_base)
        elif current_base:
            self.discount_base_col_var.set('')
        if current_sale in columns:
            self.discount_sale_col_var.set(current_sale)
        elif current_sale:
            self.discount_sale_col_var.set('')

    def save_config(self):
        self.save_settings()
        tk.messagebox.showinfo("保存完了", "設定を保存しました")

    def show_output_csv_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("2種類のCSVヘルプ")
        help_window.geometry("760x620")
        help_window.transient(self.root)

        frame = ttk.Frame(help_window, padding=10)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, wrap="word", height=28)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        help_text = """このツールが出力する2種類のCSV

1. Processed_元CSV名.csv

画像加工後のデータアップロード用CSVです。
元CSVと同じ仕様を保ち、画像URLまたは画像パスだけを書き換えます。
楽天の場合、楽天画像フォルダ名が空欄なら元CSVの画像URL/画像パスを変更せずに出力します。
Yahoo!の場合、Yahoo!ストアアカウントから https://shopping.c.yimg.jp/lib/ストアアカウント/ファイル名 を作成します。

2. image_overlay_data.csv

このCSVは、ダウンロード・加工した画像ファイルと商品情報を紐づけるためのCSVです。
後続の画像文字入れツールで、画像ごとに異なる文字列を差し込む用途を想定しています。
アップロード用CSVではなく、画像加工ツールで環境変数のように使うためのCSVです。

基本列
- image_file: 保存した画像ファイル名
- product_code: 商品コード
- product_name: 商品名
- current_price: 現在使う価格。モールごとの優先順で自動選択
- discount_rate: GUIで選んだ2列から計算した割引率。数字のみ
- image_url: 元画像URL
- processed_url: アップロード用CSVに書き込む加工後URL。空欄の場合があります
- mall: 楽天 または Yahoo!
- source_row: 元CSVの行番号
- source_column: 元CSVの画像列
- overlay_text: 後続ツール用の任意テキスト欄

Processed_元CSV名.csv の画像URL/画像パス書き換え
- 楽天は、楽天画像フォルダ名に値がある場合だけ、Processed_元CSV名.csv の画像URL/画像パスを書き換えます
- 楽天画像フォルダ名が空欄の場合、楽天の元CSVの画像URL/画像パスは変更しません
- Yahoo!は楽天画像フォルダ名を使いません。Yahoo!選択時は楽天画像フォルダ名欄が無効になります
- Yahoo!は、Yahoo!ストアアカウントに値がある場合だけ、item-image-urls の1枚目を https://shopping.c.yimg.jp/lib/ストアアカウント/ファイル名 に書き換えます
- image_overlay_data.csv はURL書き換えをしない場合でも別途出力します
- Yahoo!は必要に応じて「ファイル名の末尾に追加」で加工後ファイル名を変えて管理します

共通価格列
- regular_price: 通常価格
- display_price: 表示価格
- sale_price: セール価格
- lyp_price: LYPプレミアム会員向け価格
- maker_price: メーカー希望小売価格

割引率計算
- GUIの「基準価格列」と「割引後価格列」で選んだ列から discount_rate を出力
- 計算式: (基準価格 - 割引後価格) / 基準価格 * 100
- 小数点以下は切り捨て
- 出力は数字のみ。%OFF などの文字は付けません
- 未選択、金額が空欄、基準価格が0以下、割引なしの場合は空欄

楽天の価格対応
- 販売価格 -> rakuten_selling_price / regular_price
- 表示価格 -> rakuten_display_price / display_price
- メーカー希望小売価格 -> rakuten_maker_price / maker_price
- current_price の優先順: 販売価格 -> 表示価格 -> メーカー希望小売価格

楽天専用価格列
- rakuten_selling_price: 楽天の販売価格
- rakuten_display_price: 楽天の表示価格
- rakuten_maker_price: 楽天のメーカー希望小売価格

Yahoo!の価格対応
- 通常販売価格 / 販売価格 / price -> yahoo_regular_price / regular_price
- セール価格 / sale-price -> yahoo_sale_price / sale_price
- LYPプレミアム会員向け販売価格 -> yahoo_lyp_price / lyp_price
- メーカー希望小売価格 -> yahoo_maker_price / maker_price
- current_price の優先順: LYP価格 -> セール価格 -> 通常価格 -> メーカー希望小売価格

Yahoo!専用価格列
- yahoo_regular_price: Yahoo!の通常販売価格
- yahoo_sale_price: Yahoo!のセール価格
- yahoo_lyp_price: Yahoo!のLYPプレミアム会員向け販売価格
- yahoo_maker_price: Yahoo!のメーカー希望小売価格

使い分けの目安
- 楽天/Yahoo!を共通テンプレートで使う場合: current_price, regular_price, sale_price, maker_price
- モールごとに厳密に出し分ける場合: rakuten_* または yahoo_* の列
- 画像ごとに自由な文字を入れたい場合: overlay_text
"""
        text.insert("1.0", help_text)
        text.configure(state="disabled")

        ttk.Button(frame, text="閉じる", command=help_window.destroy).grid(row=1, column=0, columnspan=2, pady=(8, 0))

    def show_progress_window(self, total_images):
        progress_window = tk.Toplevel(self.root)
        progress_window.title("処理中")
        progress_window.geometry("300x100")
        progress_window.transient(self.root)
        progress_window.grab_set()

        ttk.Label(progress_window, text="画像を処理中...").pack(pady=5)
        progress_bar = ttk.Progressbar(progress_window, maximum=total_images, mode='determinate')
        progress_bar.pack(fill="x", padx=10, pady=5)
        progress_label = ttk.Label(progress_window, text="0 / 0")
        progress_label.pack()

        return progress_window, progress_bar, progress_label

    def read_csv_with_fallback(self, path):
        for encoding in ('cp932', 'shift_jis', 'utf-8-sig'):
            try:
                return pd.read_csv(path, encoding=encoding), encoding
            except UnicodeDecodeError:
                continue
        return pd.read_csv(path), ''

    def is_value_present(self, value):
        return pd.notna(value) and str(value).strip() != ''

    def split_yahoo_image_urls(self, value):
        if not self.is_value_present(value):
            return []
        return [url.strip() for url in str(value).split(';') if url.strip()]

    def get_first_present_value(self, row, columns):
        for column in columns:
            if column in row and self.is_value_present(row.get(column)):
                return str(row.get(column)).strip()
        return ''

    def parse_price_value(self, value):
        if not self.is_value_present(value):
            return None
        text = str(value).strip()
        text = text.translate(str.maketrans('０１２３４５６７８９．，', '0123456789.,'))
        text = re.sub(r'[^\d.\-]', '', text)
        if not text or text in ('-', '.', '-.'):
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def calculate_discount_rate(self, row):
        base_col = self.discount_base_col_var.get() if hasattr(self, 'discount_base_col_var') else ''
        sale_col = self.discount_sale_col_var.get() if hasattr(self, 'discount_sale_col_var') else ''
        if not base_col or not sale_col or base_col not in row or sale_col not in row:
            return ''
        base_price = self.parse_price_value(row.get(base_col))
        sale_price = self.parse_price_value(row.get(sale_col))
        if base_price is None or sale_price is None or base_price <= 0:
            return ''
        discount_rate = int((base_price - sale_price) / base_price * 100)
        if discount_rate <= 0:
            return ''
        return str(discount_rate)

    def build_rakuten_price_fields(self, row):
        selling_price = self.get_first_present_value(row, ['販売価格', 'price'])
        display_price = self.get_first_present_value(row, ['表示価格', 'display-price', 'display_price'])
        maker_price = self.get_first_present_value(row, ['メーカー希望小売価格', '定価', 'maker-price', 'maker_price', 'list-price', 'list_price'])
        current_price = self.get_first_present_value(row, ['販売価格', '表示価格', 'メーカー希望小売価格'])
        return {
            '楽天販売価格': selling_price,
            '楽天表示価格': display_price,
            '楽天メーカー希望小売価格': maker_price,
            'Yahoo通常販売価格': '',
            'Yahooセール価格': '',
            'YahooLYP価格': '',
            'Yahooメーカー希望小売価格': '',
            '通常価格': selling_price,
            '表示価格': display_price,
            'セール価格': '',
            'LYP価格': '',
            'メーカー希望小売価格': maker_price,
            '現在価格': current_price,
            '割引率': self.calculate_discount_rate(row)
        }

    def build_yahoo_price_fields(self, row):
        regular_price = self.get_first_present_value(row, ['通常販売価格', '販売価格', 'price', 'regular-price', 'regular_price'])
        sale_price = self.get_first_present_value(row, ['セール価格', 'sale-price', 'sale_price', 'salePrice'])
        lyp_price = self.get_first_present_value(row, [
            'LYPプレミアム会員向け販売価格',
            'LYPプレミアム会員価格',
            'lyp-price',
            'lyp_price',
            'premium-price',
            'premium_price'
        ])
        maker_price = self.get_first_present_value(row, [
            'メーカー希望小売価格',
            '定価',
            'maker-price',
            'maker_price',
            'original-price',
            'original_price',
            'list-price',
            'list_price'
        ])
        current_price = self.get_first_present_value(row, [
            'LYPプレミアム会員向け販売価格',
            'LYPプレミアム会員価格',
            'lyp-price',
            'lyp_price',
            'セール価格',
            'sale-price',
            'sale_price',
            '通常販売価格',
            '販売価格',
            'price',
            'メーカー希望小売価格'
        ])
        return {
            '楽天販売価格': '',
            '楽天表示価格': '',
            '楽天メーカー希望小売価格': '',
            'Yahoo通常販売価格': regular_price,
            'Yahooセール価格': sale_price,
            'YahooLYP価格': lyp_price,
            'Yahooメーカー希望小売価格': maker_price,
            '通常価格': regular_price,
            '表示価格': '',
            'セール価格': sale_price,
            'LYP価格': lyp_price,
            'メーカー希望小売価格': maker_price,
            '現在価格': current_price,
            '割引率': self.calculate_discount_rate(row)
        }

    def sanitize_filename(self, value, fallback):
        text = str(value).strip() if self.is_value_present(value) else fallback
        text = re.sub(r'[\\/:*?"<>|]+', '_', text)
        text = re.sub(r'\s+', '_', text).strip('._ ')
        return text or fallback

    def make_unique_filename(self, filename, used_filenames):
        name, ext = os.path.splitext(filename)
        candidate = filename
        count = 2
        while candidate.lower() in used_filenames:
            candidate = f"{name}_{count}{ext}"
            count += 1
        used_filenames.add(candidate.lower())
        return candidate

    def get_url_filename_parts(self, image_url, fallback_name):
        parsed_path = urlparse(image_url).path
        original_filename = os.path.basename(parsed_path)
        name, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.jpg'
        return self.sanitize_filename(name, fallback_name), ext

    def get_yahoo_store_account(self):
        value = self.store_url_var.get().strip()
        if not value:
            return ''
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            parts = [part for part in parsed.path.split('/') if part]
            if 'lib' in parts:
                lib_index = parts.index('lib')
                if len(parts) > lib_index + 1:
                    return parts[lib_index + 1].strip('/')
            return os.path.basename(parsed.path.strip('/'))
        return value.strip('/')

    def build_processed_url(self, new_filename, mall=None):
        mall = mall or self.mall_var.get()
        if mall == "Yahoo!":
            store_account = self.get_yahoo_store_account()
            if store_account:
                return f"https://shopping.c.yimg.jp/lib/{store_account}/{new_filename}"
            return ''
        dir_path = self.image_dir_var.get().strip('/')
        if dir_path:
            return f"/{dir_path}/{new_filename}"
        return ''

    def process_downloaded_image(self, image_path):
        img = Image.open(image_path)
        img = img.convert('RGB')

        # 解像度(幅)のリサイズ
        if self.width_var.get():
            try:
                width = int(self.width_var.get())
                aspect = img.height / img.width
                new_height = int(width * aspect)
                img = img.resize((width, new_height), Image.LANCZOS)
            except ValueError:
                pass

        # キャンバス解像度とスケーリング
        if self.canvas_width_var.get() and self.canvas_height_var.get():
            try:
                canvas_width = int(self.canvas_width_var.get())
                canvas_height = int(self.canvas_height_var.get())
                margin = int(self.margin_var.get()) if self.margin_var.get() else 0

                if self.scale_var.get():
                    scale_width = canvas_width - 2 * margin
                    scale_height = canvas_height - 2 * margin
                    aspect = img.width / img.height
                    if scale_width / scale_height > aspect:
                        new_height = scale_height
                        new_width = int(new_height * aspect)
                    else:
                        new_width = scale_width
                        new_height = int(new_width / aspect)
                    img = img.resize((new_width, new_height), Image.LANCZOS)

                canvas_color = tuple(int(self.canvas_color_var.get().lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                canvas = Image.new('RGB', (canvas_width, canvas_height), canvas_color)

                effective_width = canvas_width - 2 * margin
                effective_height = canvas_height - 2 * margin
                alignment = self.alignment_var.get()

                if alignment == "左上で合わせる":
                    x = margin
                    y = margin
                elif alignment == "左中央で合わせる":
                    x = margin
                    y = margin + (effective_height - img.height) // 2
                elif alignment == "左下で合わせる":
                    x = margin
                    y = canvas_height - margin - img.height
                elif alignment == "右上で合わせる":
                    x = canvas_width - margin - img.width
                    y = margin
                elif alignment == "右中央で合わせる":
                    x = canvas_width - margin - img.width
                    y = margin + (effective_height - img.height) // 2
                elif alignment == "右下で合わせる":
                    x = canvas_width - margin - img.width
                    y = canvas_height - margin - img.height
                else:
                    x = margin
                    y = margin

                canvas.paste(img, (x, y))
                canvas.save(image_path)
            except ValueError:
                img.save(image_path)
        else:
            img.save(image_path)

    def build_rakuten_temp_data(self, df):
        temp_data = []
        store_url = self.store_url_var.get().strip()
        for index, row in df.iterrows():
            product_code = self.get_first_present_value(row, ['商品管理番号（商品URL）', '商品番号', 'SKU管理番号'])
            product_name = self.get_first_present_value(row, ['商品名'])
            price_fields = self.build_rakuten_price_fields(row)

            if self.is_value_present(row.get('商品画像パス1')):
                image_path = str(row['商品画像パス1']).strip()
                image_url = f"https://image.rakuten.co.jp/{store_url}/cabinet{image_path}"
                item = {
                    'モール': '楽天',
                    '元行': index,
                    '読み込み位置': '商品画像パス1',
                    '画像URL': image_url,
                    '元画像値': image_path,
                    '商品コード': product_code,
                    '商品名': product_name
                }
                item.update(price_fields)
                temp_data.append(item)

            if self.sku_option_var.get() and self.is_value_present(row.get('SKU画像パス')) and not self.is_value_present(row.get('商品画像パス1')):
                image_path = str(row['SKU画像パス']).strip()
                image_url = f"https://image.rakuten.co.jp/{store_url}/cabinet{image_path}"
                item = {
                    'モール': '楽天',
                    '元行': index,
                    '読み込み位置': 'SKU画像パス',
                    '画像URL': image_url,
                    '元画像値': image_path,
                    '商品コード': product_code,
                    '商品名': product_name
                }
                item.update(price_fields)
                temp_data.append(item)
        return temp_data

    def build_yahoo_temp_data(self, df):
        if 'item-image-urls' not in df.columns:
            raise ValueError("Yahoo! CSVに item-image-urls 列がありません")

        temp_data = []
        for index, row in df.iterrows():
            urls = self.split_yahoo_image_urls(row.get('item-image-urls'))
            if not urls:
                continue
            product_code = self.get_first_present_value(row, ['code', '商品コード', 'path'])
            product_name = self.get_first_present_value(row, ['name', '商品名'])
            price_fields = self.build_yahoo_price_fields(row)
            item = {
                'モール': 'Yahoo!',
                '元行': index,
                '読み込み位置': 'item-image-urls',
                '画像URL': urls[0],
                '元画像値': row.get('item-image-urls'),
                '商品コード': product_code,
                '商品名': product_name
            }
            item.update(price_fields)
            temp_data.append(item)
        return temp_data

    def process_images(self):
        # 入力チェック
        self.save_active_store_url()
        mall = self.mall_var.get()
        if not self.input_csv_var.get() or not self.output_csv_var.get():
            tk.messagebox.showerror("エラー", "必須項目を入力してください")
            return
        if mall == "楽天" and not self.store_url_var.get().strip():
            tk.messagebox.showerror("エラー", "必須項目を入力してください")
            return

        # ベースパス（入力CSVのディレクトリ）
        base_path = os.path.dirname(self.input_csv_var.get())
        
        # 画像保存フォルダとCSVフォルダ作成
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_folder = os.path.join(base_path, "gazou", timestamp)
        csv_folder = os.path.join(base_path, "csv", timestamp)
        os.makedirs(image_folder, exist_ok=True)
        os.makedirs(csv_folder, exist_ok=True)

        # CSV読み込み
        try:
            df, _ = self.read_csv_with_fallback(self.input_csv_var.get())
        except Exception as e:
            tk.messagebox.showerror("エラー", f"CSVの読み込みに失敗しました\n{e}")
            return

        # 一時ファイル用データ
        try:
            if mall == "Yahoo!":
                temp_data = self.build_yahoo_temp_data(df)
            else:
                temp_data = self.build_rakuten_temp_data(df)
        except ValueError as e:
            tk.messagebox.showerror("エラー", str(e))
            return

        temp_df = pd.DataFrame(temp_data)
        if temp_df.empty:
            tk.messagebox.showerror("エラー", "処理対象の画像が見つかりません")
            return
        temp_images_path = os.path.join(csv_folder, 'temp_images.csv')
        temp_df.to_csv(temp_images_path, encoding='cp932', index=False)

        # 進行状況ウィンドウ表示
        total_images = len(temp_df)
        progress_window, progress_bar, progress_label = self.show_progress_window(total_images)
        
        # 画像ダウンロードと処理
        processed_urls = []
        saved_filenames = []
        used_filenames = set()
        for index, row in temp_df.iterrows():
            try:
                # 画像ダウンロード
                response = requests.get(row['画像URL'], stream=True, timeout=20)
                if response.status_code == 200:
                    fallback_name = f"image_{index + 1}"
                    url_name, ext = self.get_url_filename_parts(row['画像URL'], fallback_name)
                    if mall == "Yahoo!" and self.is_value_present(row.get('商品コード')):
                        url_name = self.sanitize_filename(row.get('商品コード'), url_name)
                    
                    # リネーム
                    new_filename = f"{self.prefix_var.get()}{url_name}{self.suffix_var.get()}{ext}"
                    new_filename = self.make_unique_filename(new_filename, used_filenames)
                    image_path = os.path.join(image_folder, new_filename)
                    
                    # 画像保存
                    with open(image_path, 'wb') as f:
                        shutil.copyfileobj(response.raw, f)
                    
                    # 画像処理
                    self.process_downloaded_image(image_path)

                    # 加工後URL作成
                    processed_url = self.build_processed_url(new_filename, mall)
                    processed_urls.append(processed_url)
                    saved_filenames.append(new_filename)
                else:
                    processed_urls.append('')
                    saved_filenames.append('')
            except Exception:
                processed_urls.append('')
                saved_filenames.append('')
            
            # 進行状況更新
            progress_bar['value'] = index + 1
            progress_label['text'] = f"{index + 1} / {total_images}"
            self.root.update()

        temp_df['加工後画像URL'] = processed_urls
        temp_df['保存画像ファイル'] = saved_filenames
        temp_processed_path = os.path.join(csv_folder, 'temp_processed.csv')
        temp_df.to_csv(temp_processed_path, encoding='cp932', index=False)

        link_rows = []
        for _, row in temp_df.iterrows():
            if row['保存画像ファイル']:
                link_rows.append({
                    'image_file': row['保存画像ファイル'],
                    'product_code': row.get('商品コード', ''),
                    'product_name': row.get('商品名', ''),
                    'current_price': row.get('現在価格', ''),
                    'discount_rate': row.get('割引率', ''),
                    'regular_price': row.get('通常価格', ''),
                    'display_price': row.get('表示価格', ''),
                    'sale_price': row.get('セール価格', ''),
                    'lyp_price': row.get('LYP価格', ''),
                    'maker_price': row.get('メーカー希望小売価格', ''),
                    'rakuten_selling_price': row.get('楽天販売価格', ''),
                    'rakuten_display_price': row.get('楽天表示価格', ''),
                    'rakuten_maker_price': row.get('楽天メーカー希望小売価格', ''),
                    'yahoo_regular_price': row.get('Yahoo通常販売価格', ''),
                    'yahoo_sale_price': row.get('Yahooセール価格', ''),
                    'yahoo_lyp_price': row.get('YahooLYP価格', ''),
                    'yahoo_maker_price': row.get('Yahooメーカー希望小売価格', ''),
                    'image_url': row.get('画像URL', ''),
                    'processed_url': row.get('加工後画像URL', ''),
                    'mall': row.get('モール', mall),
                    'source_row': row.get('元行', ''),
                    'source_column': row.get('読み込み位置', ''),
                    'overlay_text': ''
                })
        link_csv_path = os.path.join(csv_folder, 'image_overlay_data.csv')
        pd.DataFrame(link_rows).to_csv(link_csv_path, encoding='cp932', index=False)

        # 元データに書き戻し
        for _, row in temp_df.iterrows():
            if row['加工後画像URL']:
                orig_index = int(row['元行'])
                if mall == "Yahoo!":
                    urls = self.split_yahoo_image_urls(df.at[orig_index, row['読み込み位置']])
                    if urls:
                        urls[0] = row['加工後画像URL']
                        df.at[orig_index, row['読み込み位置']] = ';'.join(urls)
                else:
                    df.at[orig_index, row['読み込み位置']] = row['加工後画像URL']

        # 出力CSV保存
        output_filename = f"Processed_{os.path.basename(self.input_csv_var.get())}"
        output_path = os.path.join(csv_folder, output_filename)
        temp_output = os.path.join(csv_folder, "temp_output.csv")
        df.to_csv(temp_output, encoding='utf-8', index=False, quoting=1)
        with open(temp_output, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(output_path, 'w', encoding='cp932', newline='\r\n') as f:
            f.write(content)
        os.remove(temp_output)

        # 進行状況ウィンドウを閉じる
        progress_window.destroy()

        tk.messagebox.showinfo(
            "完了",
            "処理が完了しました\n\n"
            f"アップロード用CSV:\n{output_path}\n\n"
            f"画像加工ツール用CSV:\n{link_csv_path}"
        )

if __name__ == "__main__":
    root = tk.Tk()
    app = RakutenImageProcessor(root)
    root.mainloop()
