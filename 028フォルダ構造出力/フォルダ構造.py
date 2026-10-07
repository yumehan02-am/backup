import os
import csv
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# ---------------- GUI関数 ----------------
def browse_input_folder():
    folder = filedialog.askdirectory(title="対象フォルダを選択")
    if folder:
        input_var.set(folder)
        if not output_var.get():
            output_var.set(folder)

def browse_output_folder():
    folder = filedialog.askdirectory(title="出力先フォルダを選択")
    if folder:
        output_var.set(folder)

# ---------------- フォルダ構造取得 ----------------
def get_folder_structure(base_path, include_files=True, include_dirs=True):
    structure = []
    for root, dirs, files in os.walk(base_path):
        rel_path = os.path.relpath(root, base_path)
        parts = [] if rel_path == '.' else rel_path.split(os.sep)

        if include_dirs:
            for d in dirs:
                structure.append((parts, d + "/", True))  # True=フォルダ
        if include_files:
            for f in files:
                structure.append((parts, f, False))  # False=ファイル
        if not dirs and not files and include_dirs:
            structure.append((parts, "<空フォルダ>", True))
    return structure

# ---------------- 進行バー更新 ----------------
def update_progress(progress, total):
    percent = int(progress / total * 100)
    progress_var.set(percent)
    root.update_idletasks()

# ---------------- 出力関数 ----------------
def export_file(to_excel=True):
    input_folder = input_var.get()
    output_folder = output_var.get()
    if not input_folder or not output_folder:
        messagebox.showwarning("警告", "対象フォルダと出力先フォルダを選択してください。")
        return

    # 出力対象チェック
    include_dirs = dir_var.get()
    include_files = file_var.get()
    if not (include_dirs or include_files):
        messagebox.showwarning("警告", "出力対象を選択してください。")
        return

    data = get_folder_structure(input_folder, include_files, include_dirs)
    if not data:
        messagebox.showwarning("警告", "対象フォルダ内に出力対象がありません。")
        return

    # 出力形式
    mode = format_var.get()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if to_excel:
        wb = Workbook()
        ws = wb.active
        ws.title = "フォルダ構造"
    else:
        csv_rows = []

    max_depth = max(len(parts) for parts, name, is_dir in data) if mode=="level" else 1

    for idx, (parts, name, is_dir) in enumerate(data, start=1):
        # フィルタ（空フォルダの場合も扱う）
        if name == "<空フォルダ>":
            display_name = name
        else:
            display_name = name

        if mode == "level":
            row = [""] * max_depth
            for i, p in enumerate(parts):
                if i < max_depth:
                    row[i] = p
            if len(parts) < max_depth:
                row[len(parts)] = "" if name=="<空フォルダ>" else display_name
            else:
                row[-1] = "" if name=="<空フォルダ>" else display_name
            if to_excel:
                ws.append(row + [""])  # Tree列は空
            else:
                csv_rows.append(row + [""])

        elif mode == "fullpath":
            full_path = os.path.join(*parts, display_name) if parts else display_name
            if to_excel:
                ws.append([full_path])
            else:
                csv_rows.append([full_path])

        elif mode == "tree":
            tree_str = "│  " * len(parts)
            if name.endswith("/"):
                tree_str += "├─" + name[:-1]
            elif name == "<空フォルダ>":
                tree_str += "└─" + name
            else:
                tree_str += "└─" + name
            if to_excel:
                ws.append(["", tree_str])
            else:
                csv_rows.append(["", tree_str])

        update_progress(idx, len(data))

    # 保存
    if to_excel:
        if mode=="level":
            headers = [f"Level {i+1}" for i in range(max_depth)] + ["Tree"]
        elif mode=="fullpath":
            headers = ["FullPath"]
        else:
            headers = ["", "Tree"]
        ws.insert_rows(1)
        for col, h in enumerate(headers, 1):
            ws.cell(row=1, column=col).value = h
            ws.cell(row=1, column=col).font = Font(bold=True)

        output_path = os.path.join(output_folder, f"folder_structure_{timestamp}.xlsx")
        wb.save(output_path)
        messagebox.showinfo("完了", f"Excelで出力しました:\n{output_path}")
    else:
        output_path = os.path.join(output_folder, f"folder_structure_{timestamp}.csv")
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if mode=="level":
                headers = [f"Level {i+1}" for i in range(max_depth)] + ["Tree"]
            elif mode=="fullpath":
                headers = ["FullPath"]
            else:
                headers = ["", "Tree"]
            writer.writerow(headers)
            writer.writerows(csv_rows)
        messagebox.showinfo("完了", f"CSVで出力しました:\n{output_path}")
    progress_var.set(0)

# ---------------- GUI構築 ----------------
root = tk.Tk()
root.title("フォルダ構造出力ツール")
root.geometry("800x380")

input_var = tk.StringVar()
output_var = tk.StringVar()
progress_var = tk.IntVar()

# 出力形式
format_var = tk.StringVar(value="level")
frame_format = tk.LabelFrame(root, text="出力形式")
frame_format.pack(fill="x", padx=10, pady=5)
tk.Radiobutton(frame_format, text="階層Level列形式", variable=format_var, value="level").pack(side="left", padx=10)
tk.Radiobutton(frame_format, text="フルパス形式", variable=format_var, value="fullpath").pack(side="left", padx=10)
tk.Radiobutton(frame_format, text="ツリー形式", variable=format_var, value="tree").pack(side="left", padx=10)

# 出力対象
dir_var = tk.BooleanVar(value=True)
file_var = tk.BooleanVar(value=True)
frame_target = tk.LabelFrame(root, text="出力対象")
frame_target.pack(fill="x", padx=10, pady=5)
tk.Checkbutton(frame_target, text="フォルダ", variable=dir_var).pack(side="left", padx=10)
tk.Checkbutton(frame_target, text="ファイル", variable=file_var).pack(side="left", padx=10)

# 対象フォルダ
frame1 = tk.Frame(root)
frame1.pack(fill="x", padx=10, pady=5)
tk.Label(frame1, text="対象フォルダ:").pack(side="left")
tk.Entry(frame1, textvariable=input_var, width=60).pack(side="left", padx=5)
tk.Button(frame1, text="参照", command=browse_input_folder).pack(side="left")

# 出力フォルダ
frame2 = tk.Frame(root)
frame2.pack(fill="x", padx=10, pady=5)
tk.Label(frame2, text="出力フォルダ:").pack(side="left")
tk.Entry(frame2, textvariable=output_var, width=60).pack(side="left", padx=5)
tk.Button(frame2, text="参照", command=browse_output_folder).pack(side="left")

# 出力ボタン
frame3 = tk.Frame(root)
frame3.pack(pady=10)
tk.Button(frame3, text="Excel出力", command=lambda: export_file(True), bg="#4CAF50", fg="white", width=15).pack(side="left", padx=10)
tk.Button(frame3, text="CSV出力", command=lambda: export_file(False), bg="#2196F3", fg="white", width=15).pack(side="left", padx=10)

# レベルメーター
tk.Label(root, text="進行状況:").pack(anchor="w", padx=10)
progress_bar = ttk.Progressbar(root, orient="horizontal", length=760, mode="determinate", variable=progress_var)
progress_bar.pack(padx=10, pady=5)

root.mainloop()
