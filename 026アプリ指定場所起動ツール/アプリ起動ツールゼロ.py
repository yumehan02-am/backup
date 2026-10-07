import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import subprocess
import pygetwindow as gw
import json
import os
import time

class AppPositionManager:
    def __init__(self, root):
        self.root = root
        self.root.title("アプリ・ファイル位置管理")
        self.items = self.load_items()
        self.configs = self.load_configs()
        self.processes = []
        self.editing_entry = None

        # ドラッグアンドドロップの設定
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.drop_files)

        # GUI要素
        self.tree = ttk.Treeview(self.root, columns=("名前", "パス", "X座標", "Y座標", "幅", "高さ", "待機時間"), show="headings")
        self.tree.heading("名前", text="名前")
        self.tree.heading("パス", text="ファイルパス")
        self.tree.heading("X座標", text="X座標")
        self.tree.heading("Y座標", text="Y座標")
        self.tree.heading("幅", text="幅")
        self.tree.heading("高さ", text="高さ")
        self.tree.heading("待機時間", text="待機時間（秒）")
        self.tree.column("名前", width=150, anchor="w")
        self.tree.column("パス", width=300, anchor="w")
        self.tree.column("X座標", width=50, anchor="center")  # 33×1.5
        self.tree.column("Y座標", width=50, anchor="center")  # 33×1.5
        self.tree.column("幅", width=50, anchor="center")     # 33×1.5
        self.tree.column("高さ", width=50, anchor="center")   # 33×1.5
        self.tree.column("待機時間", width=100, anchor="center")
        self.tree.pack(pady=10, fill=tk.BOTH, expand=True)

        # クリックイベント
        self.tree.bind("<Button-1>", self.on_click)

        # ボタンフレーム
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="ファイル追加", command=self.add_item).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="選択項目を起動", command=self.launch_items).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="選択項目を学習", command=self.learn_items).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="選択項目を削除", command=self.delete_item).pack(side=tk.LEFT, padx=5)

        # 設定保存/読込フレーム
        config_frame = tk.Frame(self.root)
        config_frame.pack(pady=5)
        tk.Label(config_frame, text="設定名:").pack(side=tk.LEFT, padx=5)
        self.config_name_entry = tk.Entry(config_frame, width=20)
        self.config_name_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(config_frame, text="設定保存", command=self.save_config).pack(side=tk.LEFT, padx=5)
        tk.Label(config_frame, text="設定読込:").pack(side=tk.LEFT, padx=5)
        self.config_combo = ttk.Combobox(config_frame, values=list(self.configs.keys()), state="readonly")
        self.config_combo.pack(side=tk.LEFT, padx=5)
        self.config_combo.bind("<<ComboboxSelected>>", self.load_config)

        self.update_treeview()

    def load_items(self):
        """アイテムデータをJSONファイルから読み込む"""
        try:
            with open("items.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_items(self):
        """アイテムデータをJSONファイルに保存"""
        with open("items.json", "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=4, ensure_ascii=False)

    def load_configs(self):
        """設定データをJSONファイルから読み込む"""
        try:
            with open("configs.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_configs(self):
        """設定データをJSONファイルに保存"""
        with open("configs.json", "w", encoding="utf-8") as f:
            json.dump(self.configs, f, indent=4, ensure_ascii=False)

    def update_treeview(self):
        """Treeviewを更新"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item_data in self.items:
            self.tree.insert("", tk.END, values=(
                item_data["name"],
                item_data["path"],
                item_data["x"] if item_data["x"] is not None else "",
                item_data["y"] if item_data["y"] is not None else "",
                item_data["width"] if item_data["width"] is not None else "",
                item_data["height"] if item_data["height"] is not None else "",
                item_data["wait_time"]
            ))

    def add_item(self):
        """ファイルまたはアプリを追加（ダイアログ経由）"""
        file_path = filedialog.askopenfilename(filetypes=[("すべてのファイル", "*.*")])
        if file_path:
            self.add_item_to_list(file_path)

    def drop_files(self, event):
        """ドラッグアンドドロップでファイルを追加"""
        files = self.root.splitlist(event.data)
        for file_path in files:
            if os.path.isfile(file_path):
                self.add_item_to_list(file_path)
            else:
                messagebox.showwarning("警告", f"{file_path} は有効なファイルではありません。")

    def add_item_to_list(self, file_path):
        """ファイルパスをリストに追加"""
        if any(item["path"] == file_path for item in self.items):
            messagebox.showwarning("警告", f"{file_path} は既にリストに存在します。")
            return

        name = os.path.basename(file_path).split('.')[0]
        item_data = {
            "name": name,
            "path": file_path,
            "x": None,      # 初期値はNone
            "y": None,      # 初期値はNone
            "width": None,  # 初期値はNone
            "height": None, # 初期値はNone
            "wait_time": 5.0  # デフォルト5秒
        }
        self.items.append(item_data)
        self.save_items()
        self.update_treeview()

    def on_click(self, event):
        """シングルクリックで選択または編集"""
        if self.editing_entry:
            return

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return

        col_index = int(column.replace("#", "")) - 1
        if col_index in (0, 1):  # 名前またはパスは選択/解除
            if item in self.tree.selection():
                self.tree.selection_remove(item)
            else:
                self.tree.selection_add(item)
            return "break"

        x, y, width, height = self.tree.bbox(item, column)
        item_index = int(self.tree.index(item))
        item_data = self.items[item_index]

        self.editing_entry = tk.Entry(self.tree)
        self.editing_entry.place(x=x, y=y, width=width, height=height)
        current_value = self.tree.item(item, "values")[col_index]
        self.editing_entry.insert(0, current_value)
        self.editing_entry.select_range(0, tk.END)
        self.editing_entry.focus_set()

        def save_edit(event=None):
            try:
                new_value = self.editing_entry.get()
                if col_index == 2:  # X座標
                    item_data["x"] = int(new_value) if new_value.strip() else None
                elif col_index == 3:  # Y座標
                    item_data["y"] = int(new_value) if new_value.strip() else None
                elif col_index == 4:  # 幅
                    item_data["width"] = int(new_value) if new_value.strip() else None
                elif col_index == 5:  # 高さ
                    item_data["height"] = int(new_value) if new_value.strip() else None
                elif col_index == 6:  # 待機時間
                    item_data["wait_time"] = float(new_value)
                self.save_items()
                self.update_treeview()
            except ValueError:
                messagebox.showerror("エラー", "座標、幅、高さ、待機時間には数値を入力してください（座標/幅/高さは空も可）。")
            finally:
                self.editing_entry.destroy()
                self.editing_entry = None

        self.editing_entry.bind("<Return>", save_edit)
        self.editing_entry.bind("<FocusOut>", save_edit)

    def launch_items(self):
        """選択されたファイルまたはアプリを起動またはフォーカス"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "起動する項目を少なくとも1つ選択してください。")
            return

        for item in selected:
            item_data = self.items[int(self.tree.index(item))]
            try:
                win_title = item_data["name"]
                windows = gw.getWindowsWithTitle(win_title)
                if windows:
                    win = windows[0]
                    win.activate()
                    if item_data["x"] is not None and item_data["y"] is not None:
                        win.moveTo(item_data["x"], item_data["y"])
                    if item_data["width"] is not None and item_data["height"] is not None:
                        win.resizeTo(item_data["width"], item_data["height"])
                else:
                    subprocess.run(f'start "" "{item_data["path"]}"', shell=True)
                    time.sleep(item_data["wait_time"])  # 起動から調整までの待機時間
                    windows = gw.getWindowsWithTitle(win_title)
                    if windows:
                        win = windows[0]
                        if item_data["x"] is not None and item_data["y"] is not None:
                            win.moveTo(item_data["x"], item_data["y"])
                        if item_data["width"] is not None and item_data["height"] is not None:
                            win.resizeTo(item_data["width"], item_data["height"])
                    else:
                        messagebox.showerror("エラー", f"{win_title} のウィンドウが見つかりませんでした。")
                self.update_treeview()
            except Exception as e:
                messagebox.showerror("エラー", f"{item_data['name']} の起動に失敗しました: {str(e)}")

    def learn_items(self):
        """選択された項目のウィンドウ位置とサイズを学習"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "学習する項目を少なくとも1つ選択してください。")
            return

        for item in selected:
            item_data = self.items[int(self.tree.index(item))]
            try:
                win_title = item_data["name"]
                windows = gw.getWindowsWithTitle(win_title)
                if windows:
                    win = windows[0]
                    item_data["x"] = win.left
                    item_data["y"] = win.top
                    item_data["width"] = win.width
                    item_data["height"] = win.height
                    self.save_items()
                    self.update_treeview()
                else:
                    messagebox.showerror("エラー", f"{win_title} のウィンドウが見つかりませんでした。")
            except Exception as e:
                messagebox.showerror("エラー", f"{item_data['name']} の学習に失敗しました: {str(e)}")

    def save_config(self):
        """現在の選択項目を名前付きで保存"""
        config_name = self.config_name_entry.get().strip()
        if not config_name:
            messagebox.showwarning("警告", "設定名を入力してください。")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "保存する項目を少なくとも1つ選択してください。")
            return

        selected_indices = [int(self.tree.index(item)) for item in selected]
        self.configs[config_name] = selected_indices
        self.save_configs()
        self.config_combo["values"] = list(self.configs.keys())
        messagebox.showinfo("成功", f"設定 '{config_name}' を保存しました。")
        self.update_treeview()

    def load_config(self, event):
        """設定を読み込んで選択状態を復元"""
        config_name = self.config_combo.get()
        if not config_name:
            return

        selected_indices = self.configs.get(config_name, [])
        for index in selected_indices:
            if index < len(self.items):
                item_id = self.tree.get_children()[index]
                self.tree.selection_add(item_id)
        self.update_treeview()

    def delete_item(self):
        """選択された項目を削除"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "削除する項目を選択してください。")
            return

        if messagebox.askyesno("確認", "選択した項目を削除しますか？"):
            indices = [int(self.tree.index(item)) for item in selected]
            for index in sorted(indices, reverse=True):
                self.items.pop(index)
            self.save_items()
            for config_name in self.configs:
                self.configs[config_name] = [i for i in self.configs[config_name] if i not in indices]
                self.configs[config_name] = [i if i < index else i - 1 for index in indices for i in self.configs[config_name]]
            self.save_configs()
            self.config_combo["values"] = list(self.configs.keys())
            self.update_treeview()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = AppPositionManager(root)
    root.mainloop()