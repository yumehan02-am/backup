import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import os
import chardet
from typing import List, Tuple

class TextSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("テキストファイル分割ツール")
        self.file_path = None
        self.line_count = 0
        self.detected_encoding = None
        self.detected_newline = None
        self.is_csv = False
        self.is_tsv = False  # タブ区切りテキスト用のフラグ
        self.header = None  # ヘッダー行を保存
        self.lines = None  # 読み込んだ行を保存

        # GUIの構築
        self.create_widgets()

    def create_widgets(self):
        # ファイル選択フレーム
        file_frame = ttk.LabelFrame(self.root, text="読み込みファイル")
        file_frame.pack(padx=10, pady=5, fill="x")

        self.file_label = ttk.Label(file_frame, text="未選択", width=50, anchor="w")
        self.file_label.pack(side="left", padx=5)

        button_frame = ttk.Frame(file_frame)
        button_frame.pack(side="right", padx=5)
        ttk.Button(button_frame, text="参照", command=self.select_file).pack(side="left", padx=5)

        # ヘッダー選択フレーム
        header_frame = ttk.LabelFrame(self.root, text="ヘッダー設定")
        header_frame.pack(padx=10, pady=5, fill="x")
        self.header_mode = tk.StringVar(value="no_header")
        self.header_yes_radio = ttk.Radiobutton(header_frame, text="ヘッダーあり", variable=self.header_mode, value="with_header", command=self.count_lines)
        self.header_yes_radio.pack(side="left", padx=5)
        self.header_no_radio = ttk.Radiobutton(header_frame, text="ヘッダーなし", variable=self.header_mode, value="no_header", command=self.count_lines)
        self.header_no_radio.pack(side="left", padx=5)
        self.header_yes_radio.config(state="disabled")
        self.header_no_radio.config(state="disabled")

        # 空白行設定フレーム
        blank_frame = ttk.LabelFrame(self.root, text="空白行設定")
        blank_frame.pack(padx=10, pady=5, fill="x")
        self.blank_mode = tk.StringVar(value="keep_blank")  # デフォルトは保持
        self.blank_remove_radio = ttk.Radiobutton(blank_frame, text="空白行の削除", variable=self.blank_mode, value="remove_blank", command=self.count_lines)
        self.blank_remove_radio.pack(side="left", padx=5)
        self.blank_keep_radio = ttk.Radiobutton(blank_frame, text="空白行の保持", variable=self.blank_mode, value="keep_blank", command=self.count_lines)
        self.blank_keep_radio.pack(side="left", padx=5)

        # 読み込み設定フレーム
        input_frame = ttk.LabelFrame(self.root, text="読み込み設定")
        input_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(input_frame, text="文字コード:").pack(side="left", padx=5)
        self.input_encoding = ttk.Combobox(input_frame, values=["自動判別", "UTF-8", "Shift-JIS", "EUC-JP"])
        self.input_encoding.set("自動判別")
        self.input_encoding.pack(side="left", padx=5)

        ttk.Label(input_frame, text="改行コード:").pack(side="left", padx=5)
        self.input_newline = ttk.Combobox(input_frame, values=["自動判別", "LF", "CRLF", "CR"])
        self.input_newline.set("自動判別")
        self.input_newline.pack(side="left", padx=5)

        # 行数と検出情報表示
        self.line_info_label = ttk.Label(self.root, text="行数: 0 | 文字コード: 未検出 | 改行コード: 未検出")
        self.line_info_label.pack(pady=5)

        # 分割設定フレーム
        split_frame = ttk.LabelFrame(self.root, text="分割設定")
        split_frame.pack(padx=10, pady=5, fill="x")

        self.split_mode = tk.StringVar(value="by_count")
        ttk.Radiobutton(split_frame, text="分割数", variable=self.split_mode, value="by_count", command=self.update_split_info).pack(side="left", padx=5)
        self.split_count_entry = ttk.Entry(split_frame, width=10)
        self.split_count_entry.pack(side="left", padx=5)
        self.split_count_entry.insert(0, "2")
        self.split_count_entry.bind("<Return>", lambda event: self.update_split_info())
        self.split_count_info = ttk.Label(split_frame, text="")
        self.split_count_info.pack(side="left", padx=5)

        ttk.Radiobutton(split_frame, text="分割行数", variable=self.split_mode, value="by_lines", command=self.update_split_info).pack(side="left", padx=5)
        self.split_lines_entry = ttk.Entry(split_frame, width=10)
        self.split_lines_entry.pack(side="left", padx=5)
        self.split_lines_entry.insert(0, "100")
        self.split_lines_entry.bind("<Return>", lambda event: self.update_split_info())
        self.split_lines_info = ttk.Label(split_frame, text="")
        self.split_lines_info.pack(side="left", padx=5)

        # 書き出し設定フレーム
        output_frame = ttk.LabelFrame(self.root, text="書き出し設定")
        output_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(output_frame, text="文字コード:").pack(side="left", padx=5)
        self.output_encoding = ttk.Combobox(output_frame, values=["UTF-8", "Shift-JIS", "EUC-JP"])
        self.output_encoding.set("UTF-8")
        self.output_encoding.pack(side="left", padx=5)

        ttk.Label(output_frame, text="改行コード:").pack(side="left", padx=5)
        self.output_newline = ttk.Combobox(output_frame, values=["LF", "CRLF", "CR"])
        self.output_newline.set("LF")
        self.output_newline.pack(side="left", padx=5)

        # 結果表示ウィンドウ
        result_frame = ttk.LabelFrame(self.root, text="結果")
        result_frame.pack(padx=10, pady=5, fill="both", expand=True)
        self.result_text = tk.Text(result_frame, height=10, width=50)
        self.result_text.pack(fill="both", expand=True)

        # 実行ボタン
        ttk.Button(self.root, text="実行", command=self.execute_split).pack(pady=10)

    def select_file(self):
        self.file_path = filedialog.askopenfilename()
        if self.file_path:
            self.file_label.config(text=os.path.basename(self.file_path))
            # CSVまたはTSVかどうかを判定
            self.is_csv = self.file_path.lower().endswith('.csv')
            self.is_tsv = self.file_path.lower().endswith('.tsv')
            if self.is_csv or self.is_tsv:
                self.header_yes_radio.config(state="normal")
                self.header_no_radio.config(state="normal")
            else:
                self.header_yes_radio.config(state="disabled")
                self.header_no_radio.config(state="disabled")
            self.count_lines()
            self.update_split_info()

    def count_lines(self):
        if not self.file_path:
            return
        encoding = self.input_encoding.get()
        newline = self.input_newline.get()
        newline_map = {"LF": "\n", "CRLF": "\r\n", "CR": "\r", "自動判別": None}

        try:
            with open(self.file_path, "rb") as f:
                raw_data = f.read()
            if encoding == "自動判別":
                result = chardet.detect(raw_data)
                encoding = result["encoding"]
            text = raw_data.decode(encoding)
            self.lines = text.splitlines()
            
            # 行数をカウント（空白行の設定を考慮）
            if newline == "自動判別":
                if "\r\n" in text:
                    self.detected_newline = "CRLF"
                    self.line_count = text.count("\r\n")
                elif "\r" in text:
                    self.detected_newline = "CR"
                    self.line_count = text.count("\r")
                else:
                    self.detected_newline = "LF"
                    self.line_count = text.count("\n")
            else:
                self.detected_newline = newline
                self.line_count = text.count(newline_map[newline])
            if not text.endswith("\n") and not text.endswith("\r") and not text.endswith("\r\n"):
                self.line_count += 1

            # 空白行の削除を選択した場合、空白行を除外
            if self.blank_mode.get() == "remove_blank":
                if self.is_csv:
                    # CSV: カンマや引用符だけの行を空白と見なす
                    self.lines = [line for line in self.lines if line.strip() and line.strip(',"') != '']
                elif self.is_tsv:
                    # TSV: タブや引用符だけの行を空白と見なす
                    self.lines = [line for line in self.lines if line.strip() and line.strip('\t"') != '']
                else:
                    # その他: 通常の空白行判定
                    self.lines = [line for line in self.lines if line.strip()]
                self.line_count = len(self.lines)

            # CSVまたはTSVでヘッダーありの場合、2行目からカウント
            if (self.is_csv or self.is_tsv) and self.header_mode.get() == "with_header" and self.line_count > 0:
                self.header = self.lines[0]  # ヘッダー行を保存
                self.line_count -= 1  # ヘッダーを除外
            else:
                self.header = None

            self.detected_encoding = encoding
            self.line_info_label.config(text=f"行数: {self.line_count} | 文字コード: {self.detected_encoding} | 改行コード: {self.detected_newline}")
            self.output_encoding.set(self.detected_encoding)
            self.output_newline.set(self.detected_newline)
            self.update_split_info()  # 設定変更後に即時更新
        except FileNotFoundError:
            messagebox.showerror("エラー", "ファイルが見つかりません")
            self.line_count = 0
            self.detected_encoding = None
            self.detected_newline = None
            self.lines = None
            self.line_info_label.config(text="行数: 0 | 文字コード: 未検出 | 改行コード: 未検出")
        except PermissionError:
            messagebox.showerror("エラー", "ファイルアクセス権限がありません")
            self.line_count = 0
            self.detected_encoding = None
            self.detected_newline = None
            self.lines = None
            self.line_info_label.config(text="行数: 0 | 文字コード: 未検出 | 改行コード: 未検出")
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルの読み込みに失敗しました: {e}")
            self.line_count = 0
            self.detected_encoding = None
            self.detected_newline = None
            self.lines = None
            self.line_info_label.config(text="行数: 0 | 文字コード: 未検出 | 改行コード: 未検出")

    def update_split_info(self):
        if not self.file_path or self.line_count == 0:
            return
        try:
            if self.split_mode.get() == "by_count":
                split_count = int(self.split_count_entry.get())
                lines_per_file = self.line_count // split_count
                remainder = self.line_count % split_count
                self.split_count_info.config(text=f"1ファイルあたり: {lines_per_file}行 (余り: {remainder}行)")
                self.split_lines_info.config(text="")
            else:
                lines_per_file = int(self.split_lines_entry.get())
                split_count = (self.line_count + lines_per_file - 1) // lines_per_file
                self.split_lines_info.config(text=f"分割数: {split_count}")
                self.split_count_info.config(text="")
        except ValueError:
            self.split_count_info.config(text="整数を入力してください")
            self.split_lines_info.config(text="整数を入力してください")

    def execute_split(self):
        if not self.file_path:
            messagebox.showwarning("警告", "ファイルを指定してください")
            return

        try:
            split_param = int(self.split_count_entry.get() if self.split_mode.get() == "by_count" else self.split_lines_entry.get())
            if split_param <= 0:
                raise ValueError("正の整数を入力してください")
        except ValueError:
            messagebox.showerror("エラー", "分割数または分割行数に正の整数を入力してください")
            return

        base_name, ext = os.path.splitext(self.file_path)
        output_newline = {"LF": "\n", "CRLF": "\r\n", "CR": "\r"}[self.output_newline.get()]
        output_encoding = self.output_encoding.get()

        # CSVまたはTSVでヘッダーありの場合、データ部分のみを対象に
        if (self.is_csv or self.is_tsv) and self.header_mode.get() == "with_header":
            data_lines = self.lines[1:]  # ヘッダーを除いたデータ
        else:
            data_lines = self.lines  # ヘッダーなしまたはCSV/TSV以外

        # 空白行の削除が選択されている場合、フィルタを適用
        if self.blank_mode.get() == "remove_blank":
            if self.is_csv:
                data_lines = [line for line in data_lines if line.strip() and line.strip(',"') != '']
            elif self.is_tsv:
                data_lines = [line for line in data_lines if line.strip() and line.strip('\t"') != '']
            else:
                data_lines = [line for line in data_lines if line.strip()]

        if self.split_mode.get() == "by_count":
            split_count = split_param
            lines_per_file = self.line_count // split_count
            remainder = self.line_count % split_count
        else:
            lines_per_file = split_param
            split_count = (self.line_count + lines_per_file - 1) // lines_per_file

        output_files: List[Tuple[str, int]] = []
        for i in range(split_count):
            start = i * lines_per_file
            if i == split_count - 1 and self.split_mode.get() == "by_count":
                end = None  # 残り全て
            else:
                end = start + lines_per_file
            chunk = data_lines[start:end]
            
            output_filename = f"{base_name}_{i+1}{ext}"
            try:
                with open(output_filename, "w", encoding=output_encoding, newline="") as f:
                    if (self.is_csv or self.is_tsv) and self.header_mode.get() == "with_header":
                        f.write(self.header)
                        if chunk:
                            f.write(output_newline)
                    if chunk:
                        f.write(output_newline.join(chunk))
                line_count = len(chunk) + (1 if (self.is_csv or self.is_tsv) and self.header_mode.get() == "with_header" else 0)
                output_files.append((output_filename, line_count))
            except PermissionError:
                messagebox.showerror("エラー", f"{output_filename}への書き込み権限がありません")
                return
            except Exception as e:
                messagebox.showerror("エラー", f"{output_filename}への書き込みに失敗しました: {e}")
                return

        self.result_text.delete("1.0", tk.END)
        result_message = ""
        total_lines_written = sum(count for _, count in output_files)
        for filename, count in output_files:
            result_message += f"{os.path.basename(filename)}: {count}行\n"
        original_count = self.line_count + (split_count if (self.is_csv or self.is_tsv) and self.header_mode.get() == "with_header" else 0)
        result_message += f"\n総行数: {total_lines_written} (元ファイル: {original_count})"
        self.result_text.insert("1.0", result_message)

        if total_lines_written != original_count:
            self.result_text.insert("end", "\nエラー: 行数の整合性が取れませんでした")
        
        messagebox.showinfo("完了", "処理を完了しました")

if __name__ == "__main__":
    root = tk.Tk()
    app = TextSplitterApp(root)
    root.mainloop()