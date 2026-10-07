import os
import shutil
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
from pathlib import Path

class FileSortingTool:
    def __init__(self, root):
        self.root = root
        self.root.title("ファイル振り分けツール")
        self.root.geometry("550x700")
        self.root.resizable(True, True)

        # 変数の初期化
        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.files_per_folder = tk.StringVar(value="50")
        self.folder_name_prefix = tk.StringVar()
        self.sort_criterion = tk.StringVar(value="ファイル名")
        self.sort_order = tk.StringVar(value="昇順")
        self.operation_mode = tk.StringVar(value="コピー")
        self.delete_subfolders_var = tk.BooleanVar()

        # ヘルプテキスト
        self.help_texts = {
            "input_folder": "振り分けまたはファイル収集の対象となるフォルダを指定します。\n「参照」ボタンをクリックしてフォルダを選択してください。",
            "output_folder": "ファイルの振り分け先または収集先となるフォルダを指定します。\n未指定の場合は、入力フォルダと同じフォルダに出力します。",
            "files_per_folder": "「ファイルを振り分ける」処理で、作成する各フォルダに格納するファイルの最大数を指定します。",
            "folder_name_prefix": "「ファイルを振り分ける」処理で作成されるフォルダの接頭辞を指定します。\n末尾に「001」から始まる連番が付与されます。",
            "sort_criterion": "「ファイルを振り分ける」処理で、ファイルをどの項目で並び替えるかを指定します。",
            "sort_order": "ファイルの並び順を「昇順」または「降順」から選択します。",
            "operation_mode": "ファイルの処理方法を「コピー」または「移動」から選択します。",
            "delete_subfolders": "「ファイルを集める」処理で「移動」を選択した場合に有効。\nチェックを入れると、空のサブフォルダを削除します。",
            "sort_files_button": "設定された条件に基づいて、ファイルを複数のフォルダに振り分けます。",
            "collect_files_button": "入力フォルダおよびサブフォルダ内のすべてのファイルを収集します。",
            "status_area": "処理の進捗状況や結果、エラーメッセージなどを表示します。"
        }

        self.create_widgets()

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)

        help_menu.add_command(label="入力フォルダの説明", command=lambda: self.show_help("input_folder"))
        help_menu.add_command(label="出力フォルダの説明", command=lambda: self.show_help("output_folder"))
        help_menu.add_command(label="1フォルダあたりの数量の説明", command=lambda: self.show_help("files_per_folder"))
        help_menu.add_command(label="フォルダ名の説明", command=lambda: self.show_help("folder_name_prefix"))
        help_menu.add_command(label="ファイルの並び順の説明", command=lambda: self.show_help("sort_criterion"))
        help_menu.add_command(label="並び順の説明", command=lambda: self.show_help("sort_order"))
        help_menu.add_command(label="操作の説明", command=lambda: self.show_help("operation_mode"))
        help_menu.add_command(label="サブフォルダを削除するの説明", command=lambda: self.show_help("delete_subfolders"))
        help_menu.add_separator()
        help_menu.add_command(label="ファイルを振り分けるボタンの説明", command=lambda: self.show_help("sort_files_button"))
        help_menu.add_command(label="ファイルを集めるボタンの説明", command=lambda: self.show_help("collect_files_button"))
        help_menu.add_separator()
        help_menu.add_command(label="ステータス表示エリアの説明", command=lambda: self.show_help("status_area"))
        help_menu.add_separator()
        help_menu.add_command(label="バージョン情報", command=self.show_version_info)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(11, weight=1)

        ttk.Label(main_frame, text="入力フォルダ:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.input_folder, width=50).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(main_frame, text="参照", command=self.browse_input_folder).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(main_frame, text="出力フォルダ:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(main_frame, text="参照", command=self.browse_output_folder).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(main_frame, text="1フォルダあたりの数量:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.files_per_folder, width=10).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(main_frame, text="フォルダ名:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.folder_name_prefix, width=50).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Label(main_frame, text="未入力可能／001から連番").grid(row=3, column=1, padx=5, pady=30, sticky=tk.E)

        ttk.Label(main_frame, text="ファイルの並び順:").grid(row=4, column=0, sticky=tk.W, pady=5)
        sort_criteria = ["ファイル名", "更新日時", "種類", "サイズ", "作成日時"]
        ttk.Combobox(main_frame, textvariable=self.sort_criterion, values=sort_criteria, state="readonly").grid(row=4, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(main_frame, text="並び順:").grid(row=5, column=0, sticky=tk.W, pady=5)
        order_frame = ttk.Frame(main_frame)
        order_frame.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Radiobutton(order_frame, text="昇順", variable=self.sort_order, value="昇順").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(order_frame, text="降順", variable=self.sort_order, value="降順").pack(side=tk.LEFT, padx=5)

        ttk.Label(main_frame, text="操作:").grid(row=6, column=0, sticky=tk.W, pady=5)
        operation_frame = ttk.Frame(main_frame)
        operation_frame.grid(row=6, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Radiobutton(operation_frame, text="コピー", variable=self.operation_mode, value="コピー", command=self.update_delete_subfolder_checkbox).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(operation_frame, text="移動", variable=self.operation_mode, value="移動", command=self.update_delete_subfolder_checkbox).pack(side=tk.LEFT, padx=5)

        self.delete_subfolders_check = ttk.Checkbutton(main_frame, text="サブフォルダを削除する", variable=self.delete_subfolders_var)
        self.delete_subfolders_check.grid(row=10, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Button(main_frame, text="ファイルを振り分ける", command=self.sort_files).grid(row=8, column=0, columnspan=3, pady=20, sticky=tk.EW)
        ttk.Button(main_frame, text="ファイルを集める", command=self.collect_files).grid(row=9, column=0, columnspan=3, pady=10, sticky=tk.EW)

        self.status_text = tk.Text(main_frame, height=8, width=70, wrap=tk.WORD)
        self.status_text.grid(row=11, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)
        self.status_text.config(state=tk.DISABLED)

        self.progress = ttk.Progressbar(main_frame, mode="determinate")
        self.progress.grid(row=12, column=0, columnspan=3, pady=5, sticky=tk.EW)

    def browse_input_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)
            if not self.output_folder.get():
                self.output_folder.set(folder)

    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def sort_files(self):
        if not self.validate_inputs():
            return
        thread = threading.Thread(target=self._sort_files_thread)
        thread.start()

    def validate_inputs(self):
        """入力値の検証"""
        input_path = self.input_folder.get()
        if not input_path:
            messagebox.showerror("エラー", "入力フォルダを選択してください。")
            return False
        try:
            files_per_folder = int(self.files_per_folder.get())
            if files_per_folder <= 0:
                messagebox.showerror("エラー", "1フォルダあたりの数量は1以上の整数を入力してください。")
                return False
        except ValueError:
            messagebox.showerror("エラー", "1フォルダあたりの数量は整数を入力してください。")
            return False
        prefix = self.folder_name_prefix.get()
        if any(c in prefix for c in "/\\:*?\"<>|"):
            messagebox.showerror("エラー", "フォルダ名に使用できない文字が含まれています。")
            return False
        return True

    def _sort_files_thread(self):
        """スレッドで実行されるファイル振り分け処理"""
        input_path = self.input_folder.get()
        output_path = self.output_folder.get() or input_path
        files_per_folder = int(self.files_per_folder.get())
        prefix = self.folder_name_prefix.get()
        criterion = self.sort_criterion.get()
        order = self.sort_order.get()
        operation = self.operation_mode.get()

        try:
            files = [f for f in os.listdir(input_path) if os.path.isfile(os.path.join(input_path, f))]
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"ファイルの取得中にエラーが発生しました: {str(e)}"))
            return

        if not files:
            self.root.after(0, lambda: messagebox.showinfo("情報", "入力フォルダにファイルが存在しません。"))
            return

        files = self.sort_files_by_criterion(input_path, files, criterion, order)
        self.progress["maximum"] = len(files)

        if operation == "移動" and not messagebox.askyesno("確認", "ファイルを移動します。元のファイルは削除されます。よろしいですか？"):
            return

        folder_count = self.distribute_files(input_path, output_path, files, files_per_folder, prefix, operation)
        self.root.after(0, lambda: messagebox.showinfo("完了", f"{folder_count}フォルダに振り分けました。"))

    def sort_files_by_criterion(self, input_path, files, criterion, order):
        reversed_order = (order == "降順")
        if criterion == "ファイル名":
            files.sort(reverse=reversed_order)
        elif criterion == "更新日時":
            files.sort(key=lambda f: os.path.getmtime(os.path.join(input_path, f)), reverse=reversed_order)
        elif criterion == "種類":
            files.sort(key=lambda f: os.path.splitext(f)[1], reverse=reversed_order)
        elif criterion == "サイズ":
            files.sort(key=lambda f: os.path.getsize(os.path.join(input_path, f)), reverse=reversed_order)
        elif criterion == "作成日時":
            files.sort(key=lambda f: os.path.getctime(os.path.join(input_path, f)), reverse=reversed_order)
        return files

    def distribute_files(self, input_path, output_path, files, files_per_folder, prefix, operation):
        total_files = len(files)
        folder_count = (total_files + files_per_folder - 1) // files_per_folder
        self.update_status(f"合計 {total_files} ファイルを {folder_count} フォルダに{operation}で振り分けます...")

        for i in range(folder_count):
            folder_number = str(i + 1).zfill(3)
            folder_name = f"{prefix}{folder_number}" if prefix else folder_number
            folder_path = os.path.join(output_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            start_idx = i * files_per_folder
            end_idx = min((i + 1) * files_per_folder, total_files)

            for j in range(start_idx, end_idx):
                src = os.path.join(input_path, files[j])
                dst = os.path.join(folder_path, files[j])
                try:
                    if operation == "コピー":
                        shutil.copy2(src, dst)
                    else:
                        shutil.move(src, dst)
                    self.progress["value"] = j + 1
                    self.root.update_idletasks()
                except Exception as e:
                    operation_str = "コピー" if operation == "コピー" else "移動"
                    self.update_status(f"エラー: {files[j]} の{operation_str}中にエラーが発生しました: {str(e)}")

            operation_str = "コピー" if operation == "コピー" else "移動"
            self.update_status(f"フォルダ {folder_name} に {end_idx - start_idx} ファイルを{operation_str}しました。")

        return folder_count

    def collect_files(self):
        if not self.input_folder.get():
            messagebox.showerror("エラー", "入力フォルダを選択してください。")
            return
        thread = threading.Thread(target=self._collect_files_thread)
        thread.start()

    def _collect_files_thread(self):
        input_path = Path(self.input_folder.get())
        output_path = Path(self.output_folder.get() or self.input_folder.get())
        operation = self.operation_mode.get()
        delete_subfolders = self.delete_subfolders_var.get()

        if operation == "移動" and not messagebox.askyesno("確認", "ファイルを移動します。元のファイルは削除されます。よろしいですか？"):
            return

        collected_file_count = 0
        error_occurred = False
        files_to_process = [p for p in input_path.rglob("*") if p.is_file()]
        self.progress["maximum"] = len(files_to_process)

        self.update_status("ファイル収集処理を開始します...")

        for i, src_path in enumerate(files_to_process):
            dst_path = output_path / src_path.name
            output_path.mkdir(parents=True, exist_ok=True)
            try:
                if operation == "コピー":
                    shutil.copy2(src_path, dst_path)
                else:
                    shutil.move(src_path, dst_path)
                collected_file_count += 1
                self.progress["value"] = i + 1
                self.root.update_idletasks()
            except Exception as e:
                error_occurred = True
                operation_str = "コピー" if operation == "コピー" else "移動"
                self.update_status(f"エラー: {src_path.name} の{operation_str}中にエラーが発生しました: {str(e)}")

        if operation == "移動" and delete_subfolders:
            self.update_status("空のサブフォルダを削除します...")
            deleted_folder_count = 0
            for dir_path in input_path.rglob("*"):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        deleted_folder_count += 1
                    except OSError as e:
                        self.update_status(f"警告: フォルダ {dir_path} の削除に失敗しました: {e}")
            self.update_status(f"{deleted_folder_count} 個の空フォルダを削除しました。")

        self.root.after(0, lambda: self._show_collect_files_result(error_occurred, collected_file_count, operation))

    def _show_collect_files_result(self, error_occurred, collected_file_count, operation):
        if error_occurred:
            messagebox.showerror("完了", f"ファイル収集処理は完了しましたが、一部エラーが発生しました。ステータス表示を確認してください。")
        else:
            messagebox.showinfo("完了", f"すべてのファイルを収集しました。{collected_file_count} 個のファイルを {operation} しました。")
        self.update_status(f"ファイル収集処理が完了しました。{collected_file_count} 個のファイルを {operation} しました。")

    def update_status(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update()

    def update_delete_subfolder_checkbox(self):
        self.delete_subfolders_check.config(state=tk.NORMAL if self.operation_mode.get() == "移動" else tk.DISABLED)

    def show_help(self, item_key):
        help_text = self.help_texts.get(item_key, "ヘルプテキストがありません。")
        help_window = tk.Toplevel(self.root)
        help_window.title(f"{item_key} ヘルプ")
        ttk.Label(help_window, text=help_text, padding=10, justify=tk.LEFT).pack(expand=True, fill=tk.BOTH)
        ttk.Button(help_window, text="OK", command=help_window.destroy).pack(pady=10)
        help_window.grab_set()
        self.root.wait_window(help_window)

    def show_version_info(self):
        messagebox.showinfo("バージョン情報", "ファイル振り分けツール Ver 1.1")

def main():
    root = tk.Tk()
    app = FileSortingTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()