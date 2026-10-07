import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image
import os
from tkinterdnd2 import *

class WebPtoJPEGConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to JPEG Converter")
        self.root.geometry("420x500")
        
        # ドラッグアンドドロップ対応
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        
        # ファイルリストと保存先、チェックボックス状態
        self.files = []
        self.output_dir = None
        self.file_check_vars = {}
        self.conversion_count = 0
        self.overwrite_mode = tk.StringVar(value="ファイルごとに確認")  # 上書きモード

        # GUI要素
        self.create_widgets()
        
    def create_widgets(self):
        # メインフレーム（グリッドレイアウト）
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # リスト一覧（枠線で囲む）
        list_frame = tk.LabelFrame(self.root, text="入力ファイル一覧", padx=5, pady=5)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_frame, bg="white", height=100)
        self.scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="white")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # 設定グループ（枠線で囲む）
        settings_frame = tk.LabelFrame(self.root, text="変換設定", padx=5, pady=5)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.instant_convert_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="ドラッグアンドドロップで即時変換", variable=self.instant_convert_var).grid(row=0, column=0, columnspan=2, sticky="w")

        self.keep_aspect_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="縦横比を保持", variable=self.keep_aspect_var).grid(row=1, column=0, sticky="w")

        tk.Label(settings_frame, text="幅:").grid(row=1, column=1, sticky="e")
        self.width_entry = tk.Entry(settings_frame, width=10)
        self.width_entry.grid(row=1, column=2, padx=5)

        tk.Label(settings_frame, text="高さ:").grid(row=1, column=3, sticky="e")
        self.height_entry = tk.Entry(settings_frame, width=10)
        self.height_entry.grid(row=1, column=4, padx=5)

        tk.Label(settings_frame, text="JPEG品質:").grid(row=2, column=0, sticky="w")
        self.quality_var = tk.IntVar(value=90)
        self.quality_entry = tk.Entry(settings_frame, textvariable=self.quality_var, width=5)
        self.quality_entry.grid(row=2, column=1, sticky="w", padx=5)
        quality_scale = tk.Scale(settings_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.quality_var)
        quality_scale.grid(row=2, column=2, columnspan=3, sticky="ew")

        # ファイル名接尾辞設定
        self.suffix_var = tk.BooleanVar(value=False)
        tk.Checkbutton(settings_frame, text="ファイル名:", variable=self.suffix_var).grid(row=3, column=0, sticky="w")
        self.suffix_position = tk.StringVar(value="先頭に")
        suffix_menu = ttk.Combobox(settings_frame, textvariable=self.suffix_position, values=["先頭に", "末尾に"], state="readonly", width=10)
        suffix_menu.grid(row=3, column=1, sticky="w", padx=5)
        self.suffix_entry = tk.Entry(settings_frame, width=15)
        self.suffix_entry.insert(0, "done_")
        self.suffix_entry.grid(row=3, column=2, columnspan=3, sticky="w", padx=5)

        # 上書きモード設定
        tk.Label(settings_frame, text="同一ファイル名(JPG):").grid(row=4, column=0, sticky="w")
        overwrite_menu = ttk.Combobox(settings_frame, textvariable=self.overwrite_mode, 
                                     values=["ファイルごとに確認", "すべて上書き", "すべてスキップ"], state="readonly")
        overwrite_menu.grid(row=4, column=1, columnspan=4, sticky="w", padx=5)

        # ファイル選択グループ（枠線で囲む）
        file_selection_frame = tk.LabelFrame(self.root, text="ファイル選択", padx=5, pady=5)
        file_selection_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        tk.Label(file_selection_frame, text="ファイル:").grid(row=0, column=0, sticky="w")
        self.file_label = tk.Label(file_selection_frame, text="未選択", anchor="w", width=40, bg="white")
        self.file_label.grid(row=0, column=1, sticky="w")
        tk.Button(file_selection_frame, text="選択", command=self.select_files).grid(row=0, column=2, padx=5)

        tk.Label(file_selection_frame, text="フォルダ:").grid(row=1, column=0, sticky="w")
        self.folder_label = tk.Label(file_selection_frame, text="未選択", anchor="w", width=40, bg="white")
        self.folder_label.grid(row=1, column=1, sticky="w")
        tk.Button(file_selection_frame, text="選択", command=self.select_folder).grid(row=1, column=2, padx=5)

        tk.Label(file_selection_frame, text="保存先:").grid(row=2, column=0, sticky="w")
        self.output_label = tk.Label(file_selection_frame, text="元のファイルと同じ場所", anchor="w", width=40, bg="white")
        self.output_label.grid(row=2, column=1, sticky="w")
        tk.Button(file_selection_frame, text="選択", command=self.select_output_folder).grid(row=2, column=2, padx=5)

        # ボタンフレーム（リストクリアと変換ボタン）
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=3, column=0, pady=10)
        tk.Button(button_frame, text="リストクリア", command=self.clear_file_list, width=10).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, text="変換", command=self.convert_files, width=10).grid(row=0, column=1, padx=5)

        # 変換結果表示（3行、ホワイト背景）
        self.result_text = tk.Text(self.root, height=3, bg="white", wrap="word")
        self.result_text.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        self.result_text.insert(tk.END, "変換結果: 0 ファイル変換済み")
        self.result_text.config(state="disabled")

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.webp *.bmp *.gif *.jpg *.jpeg *.png")])
        if files:
            self.file_label.config(text=f"{len(files)} ファイル選択済み")
            for file in files:
                if file not in self.files:
                    self.add_file_to_list(file)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_label.config(text=folder)
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.webp', '.bmp', '.gif', '.jpg', '.jpeg', '.png')) and file not in self.files:
                        filepath = os.path.join(root, file)
                        self.add_file_to_list(filepath)

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.output_label.config(text=folder)
        else:
            self.output_dir = None
            self.output_label.config(text="元のファイルと同じ場所")

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        for file in files:
            if file.lower().endswith(('.webp', '.bmp', '.gif', '.jpg', '.jpeg', '.png')) and file not in self.files:
                self.add_file_to_list(file)
        if self.instant_convert_var.get():
            self.convert_files()

    def add_file_to_list(self, file):
        self.files.append(file)
        file_frame = tk.Frame(self.scrollable_frame, bg="white")
        file_frame.pack(fill=tk.X, pady=1)
        check_var = tk.BooleanVar(value=True)
        self.file_check_vars[file] = check_var
        tk.Checkbutton(file_frame, variable=check_var, bg="white").pack(side=tk.LEFT)
        tk.Label(file_frame, text=file, anchor="w", bg="white").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def clear_file_list(self):
        self.files = []
        self.file_check_vars = {}
        self.file_label.config(text="未選択")
        self.scrollable_frame.destroy()
        self.scrollable_frame = tk.Frame(self.canvas, bg="white")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

    def apply_suffix(self, filename):
        if not self.suffix_var.get():
            return filename
        suffix = self.suffix_entry.get()
        if not suffix:
            return filename
        name, ext = os.path.splitext(filename)
        if self.suffix_position.get() == "先頭に":
            return f"{suffix}{name}{ext}"
        else:
            return f"{name}{suffix}{ext}"

    def ask_overwrite(self, filepath):
        dialog = tk.Toplevel(self.root)
        dialog.title("上書き確認")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()

        # メインウィンドウの中央にダイアログを配置
        self.root.update_idletasks()  # ウィンドウサイズを確定
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        main_x = self.root.winfo_rootx()
        main_y = self.root.winfo_rooty()
        dialog_width = 300
        dialog_height = 120
        x = main_x + (main_width - dialog_width) // 2
        y = main_y + (main_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        filename = os.path.basename(filepath)
        tk.Label(dialog, text=f"{filename} は既に存在します。\n上書きしますか？", wraplength=280).pack(pady=10)
        
        # ボタンフレーム（「はい」「いいえ」を中央寄せ）
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=5)
        
        result = {"value": False}
        
        def set_yes():
            result["value"] = True
            dialog.destroy()
        
        def set_no():
            result["value"] = False
            dialog.destroy()
        
        tk.Button(button_frame, text="はい", command=set_yes).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, text="いいえ", command=set_no).grid(row=0, column=1, padx=5)
        
        self.root.wait_window(dialog)
        return result["value"]

    def convert_files(self):
        if not self.files:
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "変換結果: ファイルが選択されていません")
            self.result_text.config(state="disabled")
            return

        try:
            width = int(self.width_entry.get()) if self.width_entry.get() else None
            height = int(self.height_entry.get()) if self.height_entry.get() else None
            quality = self.quality_var.get()

            files_to_remove = []
            current_conversion_count = 0
            skipped_count = 0
            for filepath in self.files:
                if not self.file_check_vars.get(filepath, tk.BooleanVar(value=True)).get():
                    continue

                try:
                    # 画像読み込み
                    img = Image.open(filepath)
                    # 透過PNG/GIFまたはPモードの場合、RGBAに変換して白色背景を適用
                    if (filepath.lower().endswith(('.png', '.gif')) and img.mode in ('RGBA', 'LA', 'P')) or \
                       (hasattr(img, 'has_transparency') and img.has_transparency):
                        if img.mode == 'P':
                            img = img.convert('RGBA')  # 警告を防ぐためPモードをRGBAに変換
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    else:
                        img = img.convert('RGB')
                except Exception as e:
                    self.result_text.config(state="normal")
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, f"エラー: {filepath} の読み込みに失敗しました: {str(e)}")
                    self.result_text.config(state="disabled")
                    continue
                
                if width or height:
                    if self.keep_aspect_var.get():
                        if width and height:
                            img.thumbnail((width, height), Image.LANCZOS)
                        elif width:
                            aspect = width / float(img.size[0])
                            new_height = int(float(img.size[1]) * aspect)
                            img = img.resize((width, new_height), Image.LANCZOS)
                        elif height:
                            aspect = height / float(img.size[1])
                            new_width = int(float(img.size[0]) * aspect)
                            img = img.resize((new_width, height), Image.LANCZOS)
                    else:
                        new_width = width if width else img.size[0]
                        new_height = height if height else img.size[1]
                        img = img.resize((new_width, new_height), Image.LANCZOS)

                filename = os.path.basename(filepath)
                filename = self.apply_suffix(os.path.splitext(filename)[0])
                output_path = os.path.join(
                    self.output_dir or os.path.dirname(filepath),
                    f"{filename}.jpg"
                )

                # JPG上書き確認
                if filepath.lower().endswith(('.jpg', '.jpeg')) and os.path.exists(output_path):
                    if self.overwrite_mode.get() == "すべて上書き":
                        pass  # 上書き続行
                    elif self.overwrite_mode.get() == "すべてスキップ":
                        skipped_count += 1
                        files_to_remove.append(filepath)
                        continue
                    elif not self.ask_overwrite(output_path):  # ファイルごとに確認
                        skipped_count += 1
                        files_to_remove.append(filepath)
                        continue

                img.save(output_path, 'JPEG', quality=quality)
                files_to_remove.append(filepath)
                self.conversion_count += 1
                current_conversion_count += 1

            for file in files_to_remove:
                self.files.remove(file)
                del self.file_check_vars[file]
            
            self.scrollable_frame.destroy()
            self.scrollable_frame = tk.Frame(self.canvas, bg="white")
            self.scrollable_frame.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )
            self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
            for file in self.files:
                self.add_file_to_list(file)
            
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"{current_conversion_count} ファイル変換しました。\n{skipped_count} ファイルスキップしました。\n合計 {self.conversion_count} ファイル変換済み")
            self.result_text.config(state="disabled")
            
        except Exception as e:
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"エラー: {str(e)}")
            self.result_text.config(state="disabled")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = WebPtoJPEGConverter(root)
    root.mainloop()