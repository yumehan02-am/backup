import tkinter as tk
from tkinter import ttk, scrolledtext
import itertools

class ProductCodeGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("商品コードバリエーション作成ツール")
        
        # メインコンテナ
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 商品コード入力
        ttk.Label(self.main_frame, text="商品コード:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.code_entry = ttk.Entry(self.main_frame, width=50)
        self.code_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 選択肢入力フレーム
        self.options_frame = ttk.LabelFrame(self.main_frame, text="選択肢カンマ区切り", padding="5")
        self.options_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.option_entries = []
        self.add_option_entry()
        
        # 選択肢追加・削除ボタン
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=2, column=0, columnspan=3, pady=5)
        ttk.Button(self.button_frame, text="選択肢を追加", command=self.add_option_entry).grid(row=0, column=0, padx=5)
        self.delete_button = ttk.Button(self.button_frame, text="選択肢を削除", command=self.delete_option_entry)
        self.delete_button.grid(row=0, column=1, padx=5)
        self.delete_button.config(state="disabled")  # 初期状態では無効
        
        # 出力形式選択（プルダウン）
        ttk.Label(self.main_frame, text="出力形式:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.output_format = tk.StringVar(value="カンマ区切り")
        format_combo = ttk.Combobox(self.main_frame, textvariable=self.output_format, values=["カンマ区切り", "タブ区切り", "改行区切り"], state="readonly")
        format_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        format_combo.current(0)

        # 表示内容切り替え
        self.show_option_only = False
        self.display_mode_button = ttk.Button(self.main_frame, text="選択肢コードのみ", command=self.toggle_display_mode)
        self.display_mode_button.grid(row=3, column=2, sticky=tk.E, padx=5, pady=5)
        
        # 生成ボタン
        ttk.Button(self.main_frame, text="コード生成", command=self.generate_codes).grid(row=4, column=0, columnspan=3, pady=10)
        
        # 結果表示
        ttk.Label(self.main_frame, text="生成されたコード:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.result_text = scrolledtext.ScrolledText(self.main_frame, width=50, height=10, wrap=tk.WORD)
        self.result_text.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 順送りコピー機能
        self.copy_frame = ttk.Frame(self.main_frame)
        self.copy_frame.grid(row=7, column=0, columnspan=3, pady=5)
        self.copy_button = ttk.Button(self.copy_frame, text="次をコピー", command=self.copy_next_code)
        self.copy_button.grid(row=0, column=0, padx=5)
        self.copy_status = ttk.Label(self.copy_frame, text="0/0")
        self.copy_status.grid(row=0, column=1, padx=5)
        self.current_code = ttk.Label(self.copy_frame, text="")
        self.current_code.grid(row=0, column=2, padx=5)
        
        # コピー機能用の変数
        self.full_codes = []
        self.option_only_codes = []
        self.codes = []
        self.copy_index = 0
        
        # ウィンドウのリサイズ設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(6, weight=1)
    
    def add_option_entry(self):
        row = len(self.option_entries) + 1
        ttk.Label(self.options_frame, text=f"選択肢 {row}:").grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(self.options_frame, width=50)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        entry.bind("<KeyRelease>", lambda e, w=entry: self.convert_comma(w))  # ★ 入力補正を追加
        self.option_entries.append(entry)
        self.options_frame.columnconfigure(1, weight=1)
        # 選択肢が2つ以上なら削除ボタンを有効化
        if len(self.option_entries) > 1:
            self.delete_button.config(state="normal")
    
    def delete_option_entry(self):
        if len(self.option_entries) > 1:  # 選択肢1は削除不可
            entry = self.option_entries.pop()
            # 対応するラベルとエントリーを削除
            for widget in self.options_frame.grid_slaves(row=len(self.option_entries) + 1):
                widget.destroy()
            if len(self.option_entries) == 1:
                self.delete_button.config(state="disabled")
    
    def convert_comma(self, widget):
        """入力中の「、」「タブ」「改行」を「,」に変換"""
        text = widget.get()
        if any(ch in text for ch in ["、", "\t", "\n"]):
            new_text = text.replace("、", ",").replace("\t", ",").replace("\n", ",")
            widget.delete(0, tk.END)
            widget.insert(0, new_text)
    
    def generate_codes(self):
        self.result_text.delete(1.0, tk.END)
        self.full_codes = []
        self.option_only_codes = []
        self.codes = []
        self.copy_index = 0
        self.copy_status.config(text="0/0")
        self.current_code.config(text="")
        self.copy_button.config(state="disabled")
        
        base_code = self.code_entry.get().strip()
        if not base_code:
            self.result_text.insert(tk.END, "商品コードを入力してください。")
            return
        
        # 選択肢1は必須
        options = [entry.get().strip() for entry in self.option_entries if entry.get().strip()]
        if not options:
            self.result_text.insert(tk.END, "少なくとも選択肢1を入力してください。")
            return
        
        # カンマ区切りの選択肢をリストに変換
        option_lists = [opt.split(",") for opt in options]
        # すべての組み合わせを生成
        combinations = list(itertools.product(*option_lists))
        # 商品コードと選択肢を結合
        self.option_only_codes = ["".join(combo) for combo in combinations]
        self.full_codes = [base_code + option_code for option_code in self.option_only_codes]
        self.update_displayed_codes()

    def get_separator(self):
        format_map = {
            "カンマ区切り": ",",
            "タブ区切り": "\t",
            "改行区切り": "\n"
        }
        return format_map[self.output_format.get()]

    def update_displayed_codes(self):
        self.result_text.delete(1.0, tk.END)
        self.codes = self.option_only_codes if self.show_option_only else self.full_codes
        self.copy_index = 0
        self.current_code.config(text="")

        separator = self.get_separator()
        result = separator.join(self.codes)
        self.result_text.insert(tk.END, result)

        # コピーボタンを有効化し、ステータスを更新
        if self.codes:
            self.copy_button.config(state="normal")
            self.copy_status.config(text=f"0/{len(self.codes)}")
        else:
            self.copy_button.config(state="disabled")
            self.copy_status.config(text="0/0")

    def toggle_display_mode(self):
        self.show_option_only = not self.show_option_only
        if self.show_option_only:
            self.display_mode_button.config(text="コード全体")
        else:
            self.display_mode_button.config(text="選択肢コードのみ")

        if self.full_codes or self.option_only_codes:
            self.update_displayed_codes()
    
    def copy_next_code(self):
        if self.copy_index < len(self.codes):
            code = self.codes[self.copy_index]
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.current_code.config(text=code)
            self.copy_index += 1
            self.copy_status.config(text=f"{self.copy_index}/{len(self.codes)}")
            if self.copy_index == len(self.codes):
                self.copy_button.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ProductCodeGenerator(root)
    root.mainloop()
