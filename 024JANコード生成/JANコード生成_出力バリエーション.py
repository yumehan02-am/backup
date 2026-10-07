import tkinter as tk
from tkinter import ttk, scrolledtext
import itertools

def calculate_check_digit(jan12):
    """JANコードのチェックデジットを計算する（EAN-13規格準拠）"""
    if len(jan12) != 12 or not jan12.isdigit():
        raise ValueError("Invalid JAN prefix")
    
    sum_odd = 0
    sum_even = 0
    for i in range(12):
        digit = int(jan12[i])  # 左から処理
        if (i + 1) % 2 == 0:  # 偶数桁
            sum_even += digit
        else:  # 奇数桁
            sum_odd += digit
    
    total = sum_odd + sum_even * 3
    check = (10 - (total % 10)) % 10
    return check

class JanCodeAllocator:
    def __init__(self, root):
        self.root = root
        self.root.title("JANコード生成ツール")
        
        # メインコンテナ
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 発行済JAN入力
        ttk.Label(self.main_frame, text="発行済JAN:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.jan_entry = ttk.Entry(self.main_frame, width=50)
        self.jan_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # ラベル入力フレーム
        self.labels_frame = ttk.LabelFrame(self.main_frame, text="ラベル入力欄", padding="5")
        self.labels_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # ラベル追加・削除ボタン
        self.label_button_frame = ttk.Frame(self.main_frame)
        self.label_button_frame.grid(row=2, column=0, columnspan=3, pady=5)
        ttk.Button(self.label_button_frame, text="ラベルを追加", command=self.add_label_entry).grid(row=0, column=0, padx=5)
        self.delete_label_button = ttk.Button(self.label_button_frame, text="ラベルを削除", command=self.delete_label_entry)
        self.delete_label_button.grid(row=0, column=1, padx=5)
        
        # ラベル入力欄の初期化（デフォルト2）
        self.label_entries = []
        self.add_label_entry()
        self.add_label_entry()
        
        # 選択肢入力フレーム
        self.options_frame = ttk.LabelFrame(self.main_frame, text="選択肢カンマ区切り", padding="5")
        self.options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 選択肢追加・削除ボタン
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, columnspan=3, pady=5)
        ttk.Button(self.button_frame, text="選択肢を追加", command=self.add_option_entry).grid(row=0, column=0, padx=5)
        self.delete_button = ttk.Button(self.button_frame, text="選択肢を削除", command=self.delete_option_entry)
        self.delete_button.grid(row=0, column=1, padx=5)
        self.delete_button.config(state="normal")
        
        # 選択肢入力欄の初期化（デフォルト2）
        self.option_entries = []
        self.add_option_entry()
        self.add_option_entry()
        
        # 生成オプション
        self.options_extra = ttk.Frame(self.main_frame)
        self.options_extra.grid(row=5, column=0, columnspan=3, pady=5)
        self.jan_last_var = tk.BooleanVar(value=False)
        self.jan_last_check = ttk.Checkbutton(self.options_extra, text="JANコードを末尾に出力", variable=self.jan_last_var)
        self.jan_last_check.grid(row=0, column=0, padx=5)
        
        # 生成ボタン
        ttk.Button(self.main_frame, text="コード生成", command=self.generate_codes).grid(row=6, column=0, columnspan=3, pady=10)
        
        # 結果表示
        ttk.Label(self.main_frame, text="生成されたコード:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.result_text = scrolledtext.ScrolledText(self.main_frame, width=50, height=10, wrap=tk.WORD)
        self.result_text.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # コピー機能
        self.copy_frame = ttk.Frame(self.main_frame)
        self.copy_frame.grid(row=9, column=0, columnspan=3, pady=5)
        self.all_copy_button = ttk.Button(self.copy_frame, text="すべてコピー", command=self.copy_all)
        self.all_copy_button.grid(row=0, column=0, padx=5)
        self.next_copy_button = ttk.Button(self.copy_frame, text="次へコピー", command=self.copy_next_code)
        self.next_copy_button.grid(row=0, column=1, padx=5)
        # チェックボックス
        self.jan_only_var = tk.BooleanVar(value=True)  # デフォルトでオン
        self.jan_only_check = ttk.Checkbutton(self.copy_frame, text="JANコードのみ", variable=self.jan_only_var)
        self.jan_only_check.grid(row=0, column=2, padx=5)
        self.copy_status = ttk.Label(self.copy_frame, text="0/0")
        self.copy_status.grid(row=0, column=3, padx=5)
        self.current_code = ttk.Label(self.copy_frame, text="")
        self.current_code.grid(row=0, column=4, padx=5)
        
        # コピー機能用の変数
        self.codes = []
        self.copy_index = 0
        
        # ウィンドウのリサイズ設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(8, weight=1)
    
    def add_label_entry(self):
        row = len(self.label_entries) + 1
        ttk.Label(self.labels_frame, text=f"ラベル {row}:").grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(self.labels_frame, width=50)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        self.label_entries.append(entry)
        self.labels_frame.columnconfigure(1, weight=1)
    
    def delete_label_entry(self):
        if self.label_entries:
            entry = self.label_entries.pop()
            for widget in self.labels_frame.grid_slaves(row=len(self.label_entries) + 1):
                widget.destroy()
    
    def add_option_entry(self):
        row = len(self.option_entries) + 1
        ttk.Label(self.options_frame, text=f"選択肢 {row}:").grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(self.options_frame, width=50)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        entry.bind("<KeyRelease>", lambda event: self.convert_comma(event.widget))
        self.option_entries.append(entry)
        self.options_frame.columnconfigure(1, weight=1)
        if len(self.option_entries) > 1:
            self.delete_button.config(state="normal")
    
    def convert_comma(self, widget):
        """入力中の「、」「タブ」「改行」を「,」に変換"""
        text = widget.get()
        if any(ch in text for ch in ["、", "\t", "\n"]):
            new_text = text.replace("、", ",").replace("\t", ",").replace("\n", ",")
            widget.delete(0, tk.END)
            widget.insert(0, new_text)
    
    def delete_option_entry(self):
        if len(self.option_entries) > 1:
            self.option_entries.pop()
            for widget in self.options_frame.grid_slaves(row=len(self.option_entries) + 1):
                widget.destroy()
            if len(self.option_entries) == 1:
                self.delete_button.config(state="disabled")
    
    def generate_codes(self):
        self.result_text.delete(1.0, tk.END)
        self.codes = []
        self.copy_index = 0
        self.copy_status.config(text="0/0")
        self.current_code.config(text="")
        self.all_copy_button.config(state="disabled")
        self.next_copy_button.config(state="disabled")
        
        base_jan = self.jan_entry.get().strip()
        if len(base_jan) != 13 or not base_jan.isdigit():
            self.result_text.insert(tk.END, "発行済JANは13桁の数字で入力してください。")
            return
        
        # ラベル入力
        labels = [entry.get().strip() for entry in self.label_entries]
        
        # 選択肢入力
        options = [entry.get().strip() for entry in self.option_entries if entry.get().strip()]
        option_lists = [opt.split(",") for opt in options] if options else [[]]
        combinations = list(itertools.product(*option_lists)) if option_lists[0] else [()]
        
        # JANコード生成
        start_num = int(base_jan[:12]) + 1
        for i, combo in enumerate(combinations):
            jan12 = str(start_num + i).zfill(12)
            check = calculate_check_digit(jan12)
            jan = jan12 + str(check)
            
            # 出力行構築
            parts = [jan]  # デフォルト先頭にJAN
            parts.extend(labels)  # ラベル
            parts.extend(combo)   # 選択肢
            
            if self.jan_last_var.get():  # JAN末尾オプション
                parts.append(jan)
                parts = parts[1:]  # 先頭JANを削除して末尾に残す
            
            line = "\t".join(parts)
            self.codes.append(line)
        
        # 結果表示
        result = "\n".join(self.codes)
        self.result_text.insert(tk.END, result)
        
        if self.codes:
            self.all_copy_button.config(state="normal")
            self.next_copy_button.config(state="normal")
            self.copy_status.config(text=f"0/{len(self.codes)}")
    
    def copy_all(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.result_text.get(1.0, tk.END))
    
    def copy_next_code(self):
        if self.copy_index < len(self.codes):
            code = self.codes[self.copy_index]
            if self.jan_only_var.get():
                code = code.split("\t")[0]  # JANコードのみ
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.current_code.config(text=code)
            self.copy_index += 1
            self.copy_status.config(text=f"{self.copy_index}/{len(self.codes)}")
            if self.copy_index == len(self.codes):
                self.next_copy_button.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = JanCodeAllocator(root)
    root.mainloop()