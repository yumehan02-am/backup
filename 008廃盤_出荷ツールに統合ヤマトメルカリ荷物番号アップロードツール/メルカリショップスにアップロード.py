import csv
import os
import json
import logging
import threading
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from logging.handlers import RotatingFileHandler
from typing import Dict, Set, Optional, List, Tuple

class ShippingCSVConverter:
    """メルカリショップス向けCSV変換ツール"""

    DEFAULT_SHIPPING_CODES = {
        "A": "ヤマト運輸 ネコポス(メール便)",
        "0": "ヤマト運輸 宅急便",
        "2": "ヤマト運輸 宅急便(代引き)",
        "8": "ヤマト運輸 宅急便コンパクト",
        "9": "ヤマト運輸 宅急便コンパクト(代引き)",
        "": ""
    }

    CONFIG_FILE = "shipping_config.json"

    def __init__(self):
        """初期化メソッド"""
        log_handler = RotatingFileHandler("shipping_converter.log", maxBytes=1_000_000, backupCount=5)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s: %(message)s",
            handlers=[log_handler]
        )

        self.root = tk.Tk()
        self.root.title("メルカリショップス 配送データ変換 v4.4")
        self.root.geometry("600x750")
        self.shipping_codes: Dict[str, str] = {}
        self.check_states: Dict[str, bool] = {code: False for code in self.DEFAULT_SHIPPING_CODES.keys()}
        self.tracking_template = {
            "before": "ご注文ありがとうございます。発送の詳細をお知らせいたします。",
            "after": "お荷物の配送状況はヤマト運輸追跡サービスをご利用ください。",
            "multiple": "複数のお荷物での発送となります。",
            "checked": "メール便はポスト投函にて配達完了となります。",
            "combined": "複数のご注文を同梱で発送いたしました。"
        }
        self.processing_log = []  # 処理状況のログを保持
        self.history = []  # 選択履歴を保持
        self.load_config()
        self.setup_ui()

    def load_config(self):
        """設定ファイルの読み込み"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.shipping_codes = config.get('shipping_codes', self.DEFAULT_SHIPPING_CODES)
                    self.tracking_template = config.get('tracking_template', self.tracking_template)
                    loaded_check_states = config.get('check_states', {})
                    self.check_states = {code: loaded_check_states.get(code, False) 
                                       for code in self.DEFAULT_SHIPPING_CODES.keys()}
            else:
                self.shipping_codes = self.DEFAULT_SHIPPING_CODES.copy()
                self.check_states = {code: False for code in self.DEFAULT_SHIPPING_CODES.keys()}
        except Exception as e:
            logging.error(f"設定ファイル読み込みエラー: {e}")
            self.shipping_codes = self.DEFAULT_SHIPPING_CODES.copy()
            self.check_states = {code: False for code in self.DEFAULT_SHIPPING_CODES.keys()}

    def save_config(self):
        """設定ファイルの保存"""
        config = {
            'shipping_codes': self.shipping_codes,
            'tracking_template': self.tracking_template,
            'check_states': {code_var.get().strip(): check_var.get() 
                           for code_var, check_var in zip(self.code_entries, self.check_vars)}
        }
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存", "設定が保存されました")
        except Exception as e:
            logging.error(f"設定ファイル保存エラー: {e}")
            messagebox.showerror("エラー", "設定の保存に失敗しました")

    def setup_ui(self):
        """UIセットアップ"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)

        ttk.Label(main_frame, text="入力ファイル:").grid(row=0, column=0, sticky="w", pady=5)
        self.input_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", pady=5)
        tk.Button(main_frame, text="参照", command=self.select_input, relief="raised").grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(main_frame, text="出力先:").grid(row=1, column=0, sticky="w", pady=5)
        self.output_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", pady=5)
        tk.Button(main_frame, text="参照", command=self.select_output, relief="raised").grid(row=1, column=2, padx=5, pady=5)

        shipping_frame = ttk.LabelFrame(main_frame, text="配送方法設定", padding="5")
        shipping_frame.grid(row=2, column=0, columnspan=3, pady=5, sticky="ew")
        self.code_entries = []
        self.method_entries = []
        self.check_vars = []
        
        for code, method in self.DEFAULT_SHIPPING_CODES.items():
            saved_method = self.shipping_codes.get(code, method)
            row = len(self.code_entries) // 2
            col = (len(self.code_entries) % 2) * 2
            frame = ttk.Frame(shipping_frame)
            frame.grid(row=row, column=col, columnspan=2, pady=2, padx=5)
            check_var = tk.BooleanVar(value=self.check_states.get(code, False))
            ttk.Checkbutton(frame, variable=check_var).pack(side="left")
            code_var = tk.StringVar(value=code)
            method_var = tk.StringVar(value=saved_method)
            ttk.Entry(frame, textvariable=code_var, width=5).pack(side="left")
            ttk.Label(frame, text="：").pack(side="left")
            ttk.Entry(frame, textvariable=method_var, width=30).pack(side="left")
            self.code_entries.append(code_var)
            self.method_entries.append(method_var)
            self.check_vars.append(check_var)
        tk.Button(shipping_frame, text="セット", command=self.set_shipping_codes, relief="raised").grid(row=3, column=2, padx=5, pady=5)

        template_frame = ttk.LabelFrame(main_frame, text="追跡情報テンプレート", padding="5")
        template_frame.grid(row=3, column=0, columnspan=3, pady=5, sticky="ew")
        template_frame.columnconfigure(1, weight=1)
        
        ttk.Label(template_frame, text="差し込み文(前):").grid(row=0, column=0, sticky="w", pady=5)
        self.before_var = tk.StringVar(value=self.tracking_template["before"])
        self.before_text = tk.Text(template_frame, height=2, wrap="word")
        self.before_text.insert("1.0", self.before_var.get())
        self.before_text.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(template_frame, text="複数個口の場合:").grid(row=1, column=0, sticky="w", pady=5)
        self.multiple_var = tk.StringVar(value=self.tracking_template["multiple"])
        self.multiple_text = tk.Text(template_frame, height=2, wrap="word")
        self.multiple_text.insert("1.0", self.multiple_var.get())
        self.multiple_text.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(template_frame, text="同梱発送の場合:").grid(row=2, column=0, sticky="w", pady=5)
        self.combined_var = tk.StringVar(value=self.tracking_template["combined"])
        self.combined_text = tk.Text(template_frame, height=2, wrap="word")
        self.combined_text.insert("1.0", self.combined_var.get())
        self.combined_text.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(template_frame, text="運送便種類：荷物番号").grid(row=3, column=1, pady=5)
        
        ttk.Label(template_frame, text="配送方法チェックあり:").grid(row=4, column=0, sticky="w", pady=5)
        self.checked_var = tk.StringVar(value=self.tracking_template["checked"])
        self.checked_text = tk.Text(template_frame, height=2, wrap="word")
        self.checked_text.insert("1.0", self.checked_var.get())
        self.checked_text.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(template_frame, text="差し込み文(後):").grid(row=5, column=0, sticky="w", pady=5)
        self.after_var = tk.StringVar(value=self.tracking_template["after"])
        self.after_text = tk.Text(template_frame, height=2, wrap="word")
        self.after_text.insert("1.0", self.after_var.get())
        self.after_text.grid(row=5, column=1, columnspan=2, sticky="ew", pady=5)

        tk.Button(template_frame, text="セット", command=self.set_template, relief="raised").grid(row=6, column=2, padx=5, pady=5)

        self.convert_button = tk.Button(main_frame, text="変換開始", command=self.start_conversion_thread, relief="raised", width=20)
        self.convert_button.grid(row=6, column=0, columnspan=3, pady=10)
        
        ttk.Label(main_frame, text="処理状況:").grid(row=7, column=0, sticky="w", pady=5)
        console_frame = ttk.Frame(main_frame)
        console_frame.grid(row=7, column=1, columnspan=2, sticky="nsew", pady=5)
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        self.console_text = tk.Text(console_frame, height=5, wrap="word")
        self.console_text.grid(row=0, column=0, sticky="nsew")
        console_scroll = ttk.Scrollbar(console_frame, orient="vertical", command=self.console_text.yview)
        console_scroll.grid(row=0, column=1, sticky="ns")
        self.console_text.config(yscrollcommand=console_scroll.set)
        
        self.status_var = tk.StringVar(value="待機中...")
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, pady=5)

    def select_input(self):
        """入力ファイル選択"""
        file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file:
            self.input_var.set(file)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_var.set(os.path.join(os.path.dirname(file), f"メルカリショップスアップロードデータ_{timestamp}.csv"))

    def select_output(self):
        """出力先選択"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file = filedialog.asksaveasfilename(
            filetypes=[("CSV files", "*.csv")],
            defaultextension=".csv",
            initialdir=os.path.dirname(self.input_var.get()) if self.input_var.get() else None,
            initialfile=f"メルカリショップスアップロードデータ_{timestamp}"
        )
        if file:
            self.output_var.set(file)

    def set_shipping_codes(self):
        """配送方法の設定"""
        new_shipping_codes = {}
        new_check_states = {}
        
        for code_var, method_var, check_var in zip(self.code_entries, self.method_entries, self.check_vars):
            code = code_var.get().strip()
            method = method_var.get().strip()
            checked = check_var.get()
            
            if method:
                new_shipping_codes[code] = method
                new_check_states[code] = checked
            elif code in self.DEFAULT_SHIPPING_CODES:
                new_shipping_codes[code] = self.DEFAULT_SHIPPING_CODES[code]
                new_check_states[code] = checked

        self.shipping_codes = new_shipping_codes
        self.check_states = new_check_states
        self.save_config()

    def set_template(self):
        """テンプレートの設定"""
        self.tracking_template = {
            "before": self.before_text.get("1.0", "end-1c"),
            "after": self.after_text.get("1.0", "end-1c"),
            "multiple": self.multiple_text.get("1.0", "end-1c"),
            "checked": self.checked_text.get("1.0", "end-1c"),
            "combined": self.combined_text.get("1.0", "end-1c")
        }
        self.save_config()

    def start_conversion_thread(self):
        """変換処理を別スレッドで実行"""
        if not self.input_var.get() or not self.output_var.get():
            messagebox.showerror("エラー", "入力ファイルと出力先を選択してください")
            return
        self.convert_button["state"] = "disabled"
        thread = threading.Thread(target=self.process_csv)
        thread.start()

    def center_dialog(self, dialog, width, height):
        """ダイアログを親ウィンドウの中央に配置"""
        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        dialog_x = root_x + (root_width - width) // 2
        dialog_y = root_y + (root_height - height) // 2
        dialog.geometry(f"{width}x{height}+{dialog_x}+{dialog_y}")

    def select_tracking_number(self, rows: List[List[str]], title: str) -> Tuple[Optional[str], List[List[str]], bool]:
        """荷物番号選択ダイアログ"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        height = min(200 + len(rows) * 40, 600)
        dialog_width = 480
        self.center_dialog(dialog, dialog_width, height)

        frame = ttk.Frame(dialog)
        frame.pack(pady=10, padx=10, fill="both", expand=True)

        ttk.Label(frame, text="採用するお荷物番号をお選びください。", wraplength=350).pack(pady=10)
        radio_var = tk.StringVar(value=rows[0][3] if rows[0][3] else "未登録")
        for row in rows:
            tracking = row[3] if row[3] else "未登録"
            shipping_method = self.shipping_codes.get(row[1], f"不明な配送方法 ({row[1]})")
            ttk.Radiobutton(frame, text=f"{shipping_method}: {tracking}, 送付先名: {row[15]}", 
                          value=tracking, variable=radio_var).pack(anchor="w", padx=20, pady=5)

        result = [None]
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="決定", command=lambda: [result.__setitem__(0, radio_var.get()), dialog.destroy()], 
                 relief="raised").pack(side="left", padx=5)
        back_btn = tk.Button(btn_frame, text="戻る", command=lambda: [result.__setitem__(0, "back"), dialog.destroy()], 
                            relief="raised")
        back_btn.pack(side="left", padx=5)

        dialog.wait_window()
        selected_tracking = result[0]
        
        if selected_tracking == "back":
            return None, [], True
        elif selected_tracking:
            unadopted = [row for row in rows if row[3] and row[3] != selected_tracking]
            return selected_tracking, unadopted, False
        return None, [], False

    def handle_duplicate(self, order_id: str, duplicates: list) -> Tuple[Optional[list], bool]:
        """重複データの処理（分割発送）"""
        logging.debug(f"handle_duplicate: 注文ID {order_id}, 件数 {len(duplicates)}")
        dialog = tk.Toplevel(self.root)
        dialog.title("重複データ検出")
        dialog.transient(self.root)
        dialog.grab_set()
        height = min(200 + len(duplicates) * 40, 600)
        dialog_width = 480
        self.center_dialog(dialog, dialog_width, height)

        frame = ttk.Frame(dialog)
        frame.pack(pady=10, padx=10, fill="both", expand=True)

        ttk.Label(frame, text=f'注文ID "{order_id}" が{len(duplicates)}件あります。', justify="center").pack(pady=(0, 5))
        detail_frame = ttk.Frame(frame)
        detail_frame.pack(fill="x", pady=5)
        ttk.Label(detail_frame, text="重複データ詳細:", justify="left").pack(anchor="w")
        for i, row in enumerate(duplicates, 1):
            col_16 = row[15] if len(row) > 15 else "データなし"
            ttk.Label(detail_frame, text=f"{i}. 注文ID: {row[0]}, 送付先名: {col_16}", justify="left").pack(anchor="w")

        ttk.Label(frame, text="理由を選択してください:", justify="left").pack(pady=(5, 5))
        choice = tk.IntVar()
        reasons = [
            "複数の荷物に分割発送",
            "再発行（最新データを使用）",
            "重複発送の可能性（処理中止）"
        ]
        for i, reason in enumerate(reasons):
            ttk.Radiobutton(frame, text=reason, value=i, variable=choice).pack(anchor="w", padx=20, pady=5)

        result = [None]
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="決定", command=lambda: [result.__setitem__(0, choice.get()), dialog.destroy()], 
                 relief="raised").pack(side="left", padx=5)
        back_btn = tk.Button(btn_frame, text="戻る", command=lambda: [result.__setitem__(0, "back"), dialog.destroy()], 
                            relief="raised", state="disabled" if not self.history else "normal")
        back_btn.pack(side="left", padx=5)

        dialog.wait_window()

        if result[0] == "back":
            return None, True
        if result[0] is None:
            return None, False

        action = reasons[result[0]]
        col_16 = duplicates[0][15] if len(duplicates[0]) > 15 else "データなし"
        self.processing_log.append(f"分割発送処理: 注文ID {order_id}:{col_16}, 選択: {action}")

        if result[0] == 0:  # 分割発送
            self.history.append(("duplicate", order_id, duplicates, None))
            return duplicates, False
        elif result[0] == 1:  # 再発行
            selected_tracking, unadopted, back = self.select_tracking_number(duplicates, "再発行する荷物番号選択")
            if back:
                return self.handle_duplicate(order_id, duplicates)  # 理由選択に戻る
            if selected_tracking:
                selected_row = [row for row in duplicates if row[3] == selected_tracking][0]
                if unadopted:
                    self.unadopted_tracking.extend([[row[3], row[0], row[15], row[16]] for row in unadopted])
                self.history.append(("duplicate", order_id, duplicates, selected_tracking))
                return [selected_row], False
            return None, False
        else:  # 中止
            return None, False

    def handle_combined_shipping(self, potential_matches: List[List[str]]) -> Tuple[List[List[str]], List[List[str]], Optional[str], bool]:
        """同梱発送の可能性の処理"""
        logging.debug(f"handle_combined_shipping: 対象件数 {len(potential_matches)}")
        dialog = tk.Toplevel(self.root)
        dialog.title("重複宛先検出")
        dialog.transient(self.root)
        dialog.grab_set()
        height = min(200 + len(potential_matches) * 40, 600)
        dialog_width = 480
        self.center_dialog(dialog, dialog_width, height)

        frame = ttk.Frame(dialog)
        frame.pack(pady=10, padx=10, fill="both", expand=True)

        ttk.Label(frame, text="同じ宛先へのお荷物があります。", justify="center").pack(pady=(0, 5))
        detail_frame = ttk.Frame(frame)
        detail_frame.pack(fill="x", pady=5)
        ttk.Label(detail_frame, text="重複データ詳細:", justify="left").pack(anchor="w")
        for i, row in enumerate(potential_matches, 1):
            ttk.Label(detail_frame, text=f"{i}. 注文ID: {row[0]}, 送付先名: {row[15]}", justify="left").pack(anchor="w")

        ttk.Label(frame, text="どうしますか？", justify="left").pack(pady=(5, 5))
        choice = tk.IntVar()
        ttk.Radiobutton(frame, text="同梱発送", value=0, variable=choice).pack(anchor="w", padx=20, pady=5)
        ttk.Radiobutton(frame, text="個別発送", value=1, variable=choice).pack(anchor="w", padx=20, pady=5)

        result = [None]
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="決定", command=lambda: [result.__setitem__(0, choice.get()), dialog.destroy()], 
                 relief="raised").pack(side="left", padx=5)
        back_btn = tk.Button(btn_frame, text="戻る", command=lambda: [result.__setitem__(0, "back"), dialog.destroy()], 
                            relief="raised", state="disabled" if not self.history else "normal")
        back_btn.pack(side="left", padx=5)

        dialog.wait_window()

        if result[0] == "back":
            return [], [], None, True
        if result[0] is None:
            return [], [], None, False

        order_ids_with_col16 = [f"{row[0]}:{row[15]}" for row in potential_matches]
        action = "同梱発送" if result[0] == 0 else "個別発送"
        self.processing_log.append(f"同梱発送処理: 注文ID {', '.join(order_ids_with_col16)}, 選択: {action}")

        if result[0] == 1:  # 個別発送
            self.history.append(("combined", None, potential_matches, None))
            return [], potential_matches, None, False

        # 同梱発送
        if len(potential_matches) == 2:
            combined_rows = potential_matches
            individual_rows = []
        else:
            dialog2 = tk.Toplevel(self.root)
            dialog2.title("同梱するお荷物選択")
            dialog2.transient(self.root)
            dialog2.grab_set()
            height2 = min(200 + len(potential_matches) * 40, 600)
            self.center_dialog(dialog2, dialog_width, height2)

            frame2 = ttk.Frame(dialog2)
            frame2.pack(pady=10, padx=10, fill="both", expand=True)

            ttk.Label(frame2, text="同梱するお荷物をお選びください。", wraplength=350).pack(pady=10)
            check_vars = []
            for row in potential_matches:
                var = tk.BooleanVar(value=True)
                ttk.Checkbutton(frame2, text=f"注文ID: {row[0]}, 送付先名: {row[15]}", variable=var).pack(anchor="w", padx=20, pady=5)
                check_vars.append(var)

            result2 = [None]
            btn_frame2 = ttk.Frame(frame2)
            btn_frame2.pack(pady=10)
            tk.Button(btn_frame2, text="決定", command=lambda: [result2.__setitem__(0, [var.get() for var in check_vars]), dialog2.destroy()], 
                     relief="raised").pack(side="left", padx=5)
            back_btn2 = tk.Button(btn_frame2, text="戻る", command=lambda: [result2.__setitem__(0, "back"), dialog2.destroy()], 
                                 relief="raised")
            back_btn2.pack(side="left", padx=5)

            dialog2.wait_window()

            if result2[0] == "back":
                return self.handle_combined_shipping(potential_matches)  # 同梱/個別選択に戻る
            if result2[0] is None:
                return [], potential_matches, None, False

            combined_rows = []
            individual_rows = []
            for i, selected_flag in enumerate(result2[0]):
                if selected_flag:
                    combined_rows.append(potential_matches[i])
                else:
                    individual_rows.append(potential_matches[i])

            if not combined_rows:
                return [], potential_matches, None, False

        selected_tracking, unadopted, back = self.select_tracking_number(combined_rows, "採用する荷物番号選択")
        if back:
            if len(potential_matches) > 2:
                return self.handle_combined_shipping(potential_matches)  # 同梱する荷物選択に戻る
            return self.handle_combined_shipping(potential_matches)  # 同梱/個別選択に戻る
        if selected_tracking:
            if unadopted:
                self.unadopted_tracking.extend([[row[3], row[0], row[15], row[16]] for row in unadopted])
            if combined_rows:
                combined_ids_with_col16 = [f"{row[0]}:{row[15]}" for row in combined_rows]
                self.processing_log.append(f"同梱発送詳細: 採用荷物番号 {selected_tracking}, 対象注文ID {', '.join(combined_ids_with_col16)}")
            if individual_rows:
                individual_ids_with_col16 = [f"{row[0]}:{row[15]}" for row in individual_rows]
                self.processing_log.append(f"同梱候補から除外: 注文ID {', '.join(individual_ids_with_col16)}, 再処理へ")
            self.history.append(("combined", None, potential_matches, selected_tracking))
            return combined_rows, individual_rows, selected_tracking, False
        return [], potential_matches, None, False

    def process_csv(self):
        """CSVファイルの処理"""
        try:
            logging.debug("process_csv 開始")
            rows = []
            with open(self.input_var.get(), 'r', encoding='shift_jis', errors='ignore') as infile:
                reader = csv.reader(infile)
                first_row = next(reader)
                if first_row[0] != "お客様管理番号":
                    rows.append(first_row)
                rows.extend(reader)

            order_data = {}
            for row in rows:
                if len(row) < 17 or not row[0].startswith("order_"):
                    continue
                order_id = row[0]
                if order_id in order_data:
                    order_data[order_id].append(row)
                else:
                    order_data[order_id] = [row]

            total_orders = len(order_data)
            multiple_count = 0
            combined_count = 0
            processed_count = 0
            combined_groups = []
            individual_orders = []
            self.unadopted_tracking = []
            self.processing_log = []
            self.history = []

            all_rows = []
            for order_id, rows in order_data.items():
                all_rows.extend([(order_id, row) for row in rows])

            processed_order_ids = set()
            remaining_rows = all_rows[:]

            # 同梱発送の処理
            while remaining_rows:
                address_keys = {}
                for order_id, row in remaining_rows:
                    if order_id in processed_order_ids:
                        continue
                    key = tuple(row[i-1] for i in [9, 11, 12, 13, 14, 15, 16, 17])
                    if key in address_keys:
                        address_keys[key].append((order_id, row))
                    else:
                        address_keys[key] = [(order_id, row)]

                new_remaining_rows = []
                found_combined = False
                for key, potential_matches in address_keys.items():
                    if len(potential_matches) <= 1 or len(set(order_id for order_id, _ in potential_matches)) <= 1:
                        new_remaining_rows.extend(potential_matches)
                        continue
                    found_combined = True
                    match_rows = [row for _, row in potential_matches]
                    combined_rows, individual_rows, selected_tracking, back = self.handle_combined_shipping(match_rows)
                    if back:
                        if self.history:
                            last_action = self.history.pop()
                            if last_action[0] == "combined":
                                return self.process_csv()  # 前の同梱発送に戻る
                            elif last_action[0] == "duplicate":
                                order_id = last_action[1]
                                duplicates = last_action[2]
                                return self.process_csv()  # 前の分割発送に戻る
                        new_remaining_rows.extend(potential_matches)
                        continue
                    if combined_rows:
                        combined_groups.append((combined_rows, selected_tracking))
                        combined_count += 1
                        for row in combined_rows:
                            order_id = row[0]
                            processed_order_ids.add(order_id)
                            processed_count += 1
                        new_remaining_rows.extend([(row[0], row) for row in individual_rows])
                    elif individual_rows:
                        for row in individual_rows:
                            individual_orders.append([row])
                            processed_order_ids.add(row[0])
                            processed_count += 1
                    else:
                        new_remaining_rows.extend(potential_matches)

                remaining_rows = new_remaining_rows[:]
                if not found_combined:
                    break

                self.console_text.delete("1.0", tk.END)
                self.console_text.insert("1.0", f"処理状況:\n"
                                              f"総注文数: {total_orders}\n"
                                              f"処理済み: {processed_count}\n"
                                              f"複数個口: {multiple_count}\n"
                                              f"同梱注文数: {combined_count}\n\n"
                                              f"処理ログ:\n" + "\n".join(self.processing_log))

            # 分割発送および通常処理
            remaining_order_data = {}
            for order_id, row in remaining_rows:
                if order_id in processed_order_ids:
                    continue
                if order_id in remaining_order_data:
                    remaining_order_data[order_id].append(row)
                else:
                    remaining_order_data[order_id] = [row]

            with open(self.output_var.get(), 'w', encoding='utf-8-sig', newline='') as outfile:
                writer = csv.writer(outfile, quoting=csv.QUOTE_ALL)
                writer.writerow(["order_id", "shipping_method", "shipping_tracking_info", "shipping_date"])

                for combined_rows, selected_tracking in combined_groups:
                    order_ids = [row[0] for row in combined_rows]
                    shipping_method_code = combined_rows[0][1]
                    shipping_method = self.shipping_codes.get(shipping_method_code, f"不明な配送方法 ({shipping_method_code})")
                    tracking_info = self.tracking_template["before"] + "\n" + self.tracking_template["combined"]
                    tracking_info += "\n" + "\n".join(f"注文ID: {oid}" for oid in order_ids)
                    tracking_info += "\n" + f"{shipping_method}：{selected_tracking}"
                    is_checked = any(code_var.get().strip() == shipping_method_code and check_var.get() 
                                   for code_var, check_var in zip(self.code_entries, self.check_vars))
                    if is_checked:
                        tracking_info += "\n" + self.tracking_template["checked"]
                    tracking_info += "\n" + self.tracking_template["after"]
                    date_str = combined_rows[0][4] if len(combined_rows[0]) > 4 else ""
                    shipping_date = (datetime.datetime.strptime(date_str, "%Y/%m/%d").strftime("%Y/%m/%d") if date_str else "")
                    for row in combined_rows:
                        writer.writerow([row[0], shipping_method, tracking_info, shipping_date])

                for rows in individual_orders:
                    row = rows[0]
                    order_id = row[0]
                    shipping_method_code = row[1]
                    tracking_number = row[3] if row[3] else "未登録"
                    shipping_method = self.shipping_codes.get(shipping_method_code, f"不明な配送方法 ({shipping_method_code})")
                    date_str = row[4] if len(row) > 4 else ""
                    shipping_date = (datetime.datetime.strptime(date_str, "%Y/%m/%d").strftime("%Y/%m/%d") if date_str else "")
                    tracking_info = self.tracking_template["before"] + "\n" + f"{shipping_method}：{tracking_number}"
                    is_checked = any(code_var.get().strip() == shipping_method_code and check_var.get() 
                                   for code_var, check_var in zip(self.code_entries, self.check_vars))
                    if is_checked:
                        tracking_info += "\n" + self.tracking_template["checked"]
                    tracking_info += "\n" + self.tracking_template["after"]
                    writer.writerow([order_id, shipping_method, tracking_info, shipping_date])

                for order_id, rows in list(remaining_order_data.items()):
                    if order_id in processed_order_ids:
                        continue
                    if len(rows) > 1:
                        result, back = self.handle_duplicate(order_id, rows)
                        if back:
                            if self.history:
                                last_action = self.history.pop()
                                if last_action[0] == "combined":
                                    return self.process_csv()  # 前の同梱発送に戻る
                                elif last_action[0] == "duplicate":
                                    order_id = last_action[1]
                                    duplicates = last_action[2]
                                    return self.process_csv()  # 前の分割発送に戻る
                            continue
                        if result is None:
                            self.status_var.set("処理が中止されました")
                            self.console_text.delete("1.0", tk.END)
                            self.console_text.insert("1.0", "処理が中止されました")
                            messagebox.showwarning("中止", "処理が中止されました")
                            return
                        rows = result
                        if len(rows) > 1:
                            multiple_count += 1
                    else:
                        result = rows

                    tracking_lines = []
                    shipping_method = ""
                    shipping_date = ""
                    is_checked = False
                    for row in rows:
                        shipping_method_code = row[1]
                        tracking_number = row[3] if row[3] else "未登録"
                        date_str = row[4] if len(row) > 4 else ""
                        if date_str:
                            date_obj = datetime.datetime.strptime(date_str, "%Y/%m/%d")
                            shipping_date = f"{date_obj.year}/{date_obj.month}/{date_obj.day}"
                        shipping_method = self.shipping_codes.get(shipping_method_code, f"不明な配送方法 ({shipping_method_code})")
                        for i, (code_var, check_var) in enumerate(zip(self.code_entries, self.check_vars)):
                            if code_var.get().strip() == shipping_method_code and check_var.get():
                                is_checked = True
                                break
                        tracking_lines.append(f"{shipping_method}：{tracking_number}")

                    tracking_info = self.tracking_template["before"]
                    if len(rows) > 1:
                        tracking_info += "\n" + self.tracking_template["multiple"] + "\n" + "\n".join(tracking_lines)
                    else:
                        tracking_info += "\n" + tracking_lines[0]
                    if is_checked:
                        tracking_info += "\n" + self.tracking_template["checked"]
                    tracking_info += "\n" + self.tracking_template["after"]

                    writer.writerow([order_id, shipping_method, tracking_info, shipping_date])
                    processed_count += 1
                    processed_order_ids.add(order_id)

                    self.console_text.delete("1.0", tk.END)
                    self.console_text.insert("1.0", f"処理状況:\n"
                                                  f"総注文数: {total_orders}\n"
                                                  f"処理済み: {processed_count}\n"
                                                  f"複数個口: {multiple_count}\n"
                                                  f"同梱注文数: {combined_count}\n\n"
                                                  f"処理ログ:\n" + "\n".join(self.processing_log))
                    del remaining_order_data[order_id]

            if self.unadopted_tracking:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.dirname(self.input_var.get())
                unadopted_file = os.path.join(output_dir, f"不採用荷物番号一覧_{timestamp}.txt")
                with open(unadopted_file, 'w', encoding='utf-8') as f:
                    f.write("\t".join(["荷物番号", "注文ID", "送付先名", "17列目"]) + "\n")
                    for row in self.unadopted_tracking:
                        f.write("\t".join(row) + "\n")

            self.status_var.set("変換完了")
            self.console_text.delete("1.0", tk.END)
            self.console_text.insert("1.0", f"処理完了:\n"
                                          f"総注文数: {total_orders}\n"
                                          f"処理済み: {processed_count}\n"
                                          f"複数個口: {multiple_count}\n"
                                          f"同梱注文数: {combined_count}\n\n"
                                          f"処理ログ:\n" + "\n".join(self.processing_log))
            messagebox.showinfo("完了", "データ変換が完了しました")
            logging.debug("process_csv 完了")

        except Exception as e:
            logging.error(f"CSV処理中にエラー: {e}", exc_info=True)
            self.console_text.delete("1.0", tk.END)
            self.console_text.insert("1.0", f"エラー: {str(e)}")
            messagebox.showerror("エラー", str(e))
        
        self.convert_button["state"] = "normal"

    def run(self):
        """アプリケーションの実行"""
        self.root.mainloop()

def main():
    """メイン関数"""
    converter = ShippingCSVConverter()
    converter.run()

if __name__ == "__main__":
    main()