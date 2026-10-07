import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string
import json
import os
from tkinter.simpledialog import askstring
from tkinter import font as tkfont
import logging
from collections import deque

# UI 構築より前に root を作成
root = tk.Tk()

# ToolTip クラス
class ToolTip:
    def __init__(self, widget, tooltip_text, wraplength=200, delay=500):
        self.widget = widget
        self.tooltip_text = tooltip_text
        self.wraplength = wraplength
        self.delay = delay
        self.tooltip_window = None
        self.timer = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if not self.tooltip_text:
            return
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        self.timer = self.widget.after(self.delay, self._show_tooltip)

    def _show_tooltip(self):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.tooltip_text, background="#FFFFE0", relief=tk.SOLID, borderwidth=1, wraplength=self.wraplength, font=tkfont.Font(family="Meiryo UI", size=9))
        label.pack(ipadx=5, ipady=5)

    def hide_tooltip(self, event):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

# 設定ファイルとログファイルのパス
CONFIG_FILE = "amazon_excel_tool.json"
LOG_FILE = "error.log"

# ロギング設定
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 設定ファイルの読み込み
def load_config():
    default_config = {
        "initial_row": 7,
        "initial_col": 1,
        "window_width": 800,
        "window_height": 400,
        "recent_files_limit": 5,
        "recent_files": [],
        "last_opened_dir": "",
        "sku_column": "A",  # 出品者SKUのデフォルト列
        "name_column": "D",  # 商品名のデフォルト列
        "column_name_row": 4  # カラム名のデフォルト行
    }
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        return default_config

# 設定ファイルの保存
def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logging.error(f"設定ファイルの保存中にエラー: {e}")
        messagebox.showerror("エラー", "設定ファイルの保存に失敗しました。")

# グローバル変数
wb = None
sheet = None
current_row = 7
current_col = 1
max_row = 1
max_col = 1
current_value = ""
config = load_config()
recent_files_menu = None
undo_stack = deque(maxlen=50)
redo_stack = deque(maxlen=50)
last_file_path = None
search_var = tk.StringVar()
sku_var = tk.StringVar(value="（ファイル未読み込み）")
name_var = tk.StringVar(value="（ファイル未読み込み）")
column_name_var = tk.StringVar(value="カラム名")
char_count_var = tk.StringVar(value="文字数: 0")
jump_cell_var = tk.StringVar()
last_search_text = ""
last_search_row = 7
last_search_col = 1

# 最近使ったファイルリストを更新
def update_recent_files_list(file_path):
    global config, recent_files_menu
    if file_path in config["recent_files"]:
        config["recent_files"].remove(file_path)
    config["recent_files"].insert(0, file_path)
    config["recent_files"] = config["recent_files"][:config["recent_files_limit"]]
    save_config(config)
    update_recent_menu()

# 「最近使ったファイル」メニューを更新
def update_recent_menu():
    global recent_files_menu, config
    if recent_files_menu:
        recent_files_menu.delete(0, tk.END)
        for file_path in config["recent_files"]:
            recent_files_menu.add_command(label=os.path.basename(file_path), command=lambda path=file_path: load_excel(path))

# ファイル選択ダイアログ
def select_file():
    global config
    initial_dir = config["last_opened_dir"] if config["last_opened_dir"] else os.path.expanduser("~")
    file_path = filedialog.askopenfilename(
        filetypes=[("Excel files", "*.xlsm;*.xlsx")],
        initialdir=initial_dir
    )
    if file_path:
        load_excel(file_path)

# 「名前を付けて保存」機能
def save_as_file():
    global wb, last_file_path, config
    if wb is None:
        return
    initial_dir = config["last_opened_dir"] if config["last_opened_dir"] else os.path.expanduser("~")
    file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsm",
        filetypes=[("Excel Macro-Enabled Workbook", "*.xlsm"), ("Excel Workbook", "*.xlsx")],
        initialdir=initial_dir
    )
    if file_path:
        try:
            wb.save(file_path)
            messagebox.showinfo("保存", "ファイルが保存されました")
            update_recent_files_list(file_path)
            config["last_opened_dir"] = os.path.dirname(file_path)
            save_config(config)
            last_file_path = file_path
            update_title_bar()
        except Exception as e:
            logging.error(f"ファイル保存中にエラー: {e}")
            messagebox.showerror("エラー", f"ファイルの保存中にエラーが発生しました: {e}")

# Excel ファイルをロード
def load_excel(file_path):
    global wb, sheet, current_row, current_col, max_row, max_col, config, last_file_path, undo_stack, redo_stack, last_search_text, last_search_row, last_search_col
    try:
        wb = load_workbook(file_path, keep_vba=True)

        if "テンプレート" not in wb.sheetnames:
            messagebox.showerror("エラー", "テンプレートシートが見つかりません")
            return

        sheet = wb["テンプレート"]
        max_row, max_col = sheet.max_row, sheet.max_column
        current_row, current_col = config["initial_row"], config["initial_col"]

        update_display()
        update_recent_files_list(file_path)
        config["last_opened_dir"] = os.path.dirname(file_path)
        save_config(config)
        last_file_path = file_path
        update_title_bar()
        status_bar_message(f"ファイル '{os.path.basename(file_path)}' を読み込みました", 3)
        undo_stack.clear()
        redo_stack.clear()
        update_undo_redo_menu()
        last_search_text = ""
        last_search_row = 7
        last_search_col = 1

    except Exception as e:
        logging.error(f"ファイル読み込み中にエラー: {e}")
        messagebox.showerror("エラー", f"ファイルの読み込み中にエラーが発生しました: {e}")
        status_bar_message("ファイル読み込みエラー", 5)

# タイトルバーを更新
def update_title_bar():
    global last_file_path, root
    file_name = os.path.basename(last_file_path) if last_file_path else "新規ファイル"
    root.title(f"{file_name} - Amazon 商品登録入力補助ツール")

# ステータスバーにメッセージを表示
def status_bar_message(message, duration=0):
    status_bar_var.set(message)
    if duration > 0:
        root.after(duration * 1000, clear_status_bar)

# ステータスバーをクリア
def clear_status_bar():
    status_bar_var.set("")

# 現在のセルのデータを更新
def update_display():
    global current_row, current_col, current_value
    if sheet is None:
        return

    # 設定から列と行を取得
    sku_col = config["sku_column"]
    name_col = config["name_column"]
    column_name_row = config["column_name_row"]
    
    sku_var.set(sheet[f"{sku_col}{current_row}"].value if sheet[f"{sku_col}{current_row}"].value else "（空白）")
    name_var.set(sheet[f"{name_col}{current_row}"].value if sheet[f"{name_col}{current_row}"].value else "（空白）")

    column_name = sheet.cell(row=column_name_row, column=current_col).value
    column_name_var.set(column_name if column_name else "カラム名なし")
    column_name_label.tooltip_text = column_name if column_name else ""

    cell_value = sheet.cell(row=current_row, column=current_col).value
    input_text.delete("1.0", tk.END)
    if cell_value is not None:
        input_text.insert("1.0", str(cell_value))
    current_value = str(cell_value) if cell_value is not None else ""

    status_bar_cell_pos()
    update_char_count()

# 簡易的なセルアドレス取得関数
def get_cell_address_simple(row, col):
    return f"{get_column_letter(col)}{row}"

# 現在のセル位置をステータスバーに表示
def status_bar_cell_pos():
    status_bar_pos_var.set(f"セル: {get_column_letter(current_col)}{current_row}")

# セルの内容を保存 (アンドゥ・リドゥ対応)
def save_cell(event=None):
    global current_row, current_col, current_value, undo_stack, redo_stack
    logging.debug("save_cell: save_cell() 関数が開始")
    logging.debug(f"save_cell: 現在の undo_stack: {undo_stack}")
    logging.debug(f"save_cell: 現在の redo_stack: {redo_stack}")

    new_value = input_text.get("1.0", tk.END).strip()
    old_value = current_value
    logging.debug(f"save_cell: 比較 - new_value='{new_value}', old_value='{old_value}'")

    if new_value != old_value:
        logging.debug("save_cell: 値が変更されました。アンドゥ履歴に追加します")
        undo_info = {
            "action": "cell_edit",
            "cell_address": (current_row, current_col),
            "old_value": old_value
        }
        undo_stack.append(undo_info)
        logging.debug(f"save_cell: アンドゥスタックに追加 - undo_info={undo_info}")
        logging.debug(f"save_cell: 現在の undo_stack: {undo_stack}")

        sheet.cell(row=current_row, column=current_col, value=new_value)
        current_value = new_value
        status_bar_message("変更を保存しました", 3)
        redo_stack.clear()
        update_undo_redo_menu()
        logging.debug("save_cell: update_undo_redo_menu() 呼び出し")
    else:
        logging.debug("save_cell: 値に変更はありません。アンドゥ履歴に追加しません")
    logging.debug("save_cell: save_cell() 関数が終了")
    return "break"

# セル内改行 (Shift+Enter)
def insert_newline(event):
    global input_text
    input_text.insert(tk.INSERT, '\n')
    update_char_count()
    return "break"

# セル内容をクリア
def clear_cell():
    global input_text, current_value, undo_stack, redo_stack, current_row, current_col
    logging.debug("clear_cell: clear_cell() 関数が開始")
    logging.debug(f"clear_cell: 現在の undo_stack: {undo_stack}")
    logging.debug(f"clear_cell: 現在の redo_stack: {redo_stack}")
    if sheet is None:
        logging.debug("clear_cell: sheet が None のため、処理を中断")
        return

    cell_address = (current_row, current_col)
    old_value = current_value
    logging.debug(f"clear_cell: clear前の old_value='{old_value}'")

    input_text.delete("1.0", tk.END)
    new_value = ""

    if old_value != new_value:
        logging.debug(f"clear_cell: 値が変更されました。アンドゥ履歴に追加します。old_value='{old_value}', new_value='{new_value}'")
        undo_info = {
            "action": "clear",
            "cell_address": cell_address,
            "old_value": old_value
        }
        undo_stack.append(undo_info)
        logging.debug(f"clear_cell: アンドゥスタックに追加 - undo_info={undo_info}")
        logging.debug(f"clear_cell: 現在の undo_stack: {undo_stack}")
        sheet.cell(row=current_row, column=current_col, value=new_value)
        current_value = new_value
        status_bar_message("セル内容をクリアしました", 3)
        redo_stack.clear()
        update_undo_redo_menu()
        logging.debug("clear_cell: update_undo_redo_menu() 呼び出し")
    else:
        logging.debug(f"clear_cell: 値に変更はありません。アンドゥ履歴に追加しません。old_value='{old_value}', new_value='{new_value}'")

    update_display()
    logging.debug("clear_cell: clear_cell() 関数が終了")

# アンドゥ
def undo():
    global undo_stack, redo_stack, current_value, current_row, current_col
    logging.debug("undo: undo() 関数が開始")
    logging.debug(f"undo: 現在の undo_stack: {undo_stack}")
    logging.debug(f"undo: 現在の redo_stack: {redo_stack}")
    if not undo_stack:
        logging.debug("undo: undo_stack が空です。処理なしで終了")
        return

    undo_info = undo_stack.pop()
    logging.debug(f"undo: undo_stack から pop - undo_info={undo_info}")

    action = undo_info.get("action")
    logging.debug(f"undo: action = {action}")

    if action == "cell_edit":
        cell_address = undo_info["cell_address"]
        old_value = undo_info["old_value"]
        row, col = cell_address
        logging.debug(f"undo: cell_edit - cell_address={cell_address}, old_value='{old_value}'")
        redo_stack.append({
            "action": "cell_edit",
            "cell_address": (current_row, current_col),
            "old_value": current_value
        })
        logging.debug(f"undo: redo_stack に追加: {redo_stack[-1]}")

        sheet.cell(row=row, column=col, value=old_value)
        current_row, current_col = row, col
        current_value = old_value

    elif action == "clear":
        cell_address = undo_info["cell_address"]
        old_value = undo_info["old_value"]
        row, col = cell_address
        logging.debug(f"undo: clear - cell_address={cell_address}, old_value='{old_value}'")
        redo_stack.append({
            "action": "clear",
            "cell_address": (current_row, current_col),
            "old_value": current_value
        })
        logging.debug(f"undo: redo_stack に追加: {redo_stack[-1]}")

        sheet.cell(row=row, column=col, value=old_value)
        current_row, current_col = row, col
        current_value = old_value
    else:
        logging.warning(f"undo: 不明なアクション種別: {action}")

    update_display()
    input_text.focus_set()
    status_bar_message("アンドゥ実行", 2)
    update_undo_redo_menu()
    logging.debug("undo: undo() 関数が終了")

# リドゥ
def redo():
    global undo_stack, redo_stack, current_value, current_row, current_col
    logging.debug("redo: redo() 関数が開始")
    logging.debug(f"redo: 現在の undo_stack: {undo_stack}")
    logging.debug(f"redo: 現在の redo_stack: {redo_stack}")
    if not redo_stack:
        logging.debug("redo: redo_stack が空です。処理なしで終了")
        return

    redo_info = redo_stack.pop()
    logging.debug(f"redo: redo_stack から pop - redo_info={redo_info}")

    action = redo_info.get("action")
    logging.debug(f"redo: action = {action}")

    if action == "cell_edit":
        cell_address = redo_info["cell_address"]
        old_value = redo_info["old_value"]
        row, col = cell_address
        logging.debug(f"redo: cell_edit - cell_address={cell_address}, old_value='{old_value}'")
        undo_stack.append({
            "action": "cell_edit",
            "cell_address": (current_row, current_col),
            "old_value": current_value
        })
        logging.debug(f"redo: undo_stack に追加: {redo_stack[-1]}")

        sheet.cell(row=row, column=col, value=old_value)
        current_row, current_col = row, col
        current_value = old_value

    elif action == "clear":
        cell_address = redo_info["cell_address"]
        old_value = redo_info["old_value"]
        row, col = cell_address
        logging.debug(f"redo: clear - cell_address={cell_address}, old_value='{old_value}'")
        undo_stack.append({
            "action": "clear",
            "cell_address": (current_row, current_col),
            "old_value": current_value
        })
        logging.debug(f"redo: undo_stack に追加: {redo_stack[-1]}")

        sheet.cell(row=row, column=col, value=old_value)
        current_row, current_col = row, col
        current_value = old_value
    else:
        logging.warning(f"redo: 不明なアクション種別: {action}")

    update_display()
    input_text.focus_set()
    status_bar_message("リドゥ実行", 2)
    update_undo_redo_menu()
    logging.debug("redo: redo() 関数が終了")

# アンドゥ・リドゥメニューの有効/無効を更新
def update_undo_redo_menu():
    logging.debug("update_undo_redo_menu: update_undo_redo_menu() 関数が開始")
    is_undo_enabled = bool(undo_stack)
    is_redo_enabled = bool(redo_stack)
    edit_menu.entryconfig("アンドゥ", state=tk.NORMAL if is_undo_enabled else tk.DISABLED)
    edit_menu.entryconfig("リドゥ", state=tk.NORMAL if is_redo_enabled else tk.DISABLED)

    for child in button_frame_action.winfo_children():
        if isinstance(child, tk.Button):
            if child.cget("text") == "アンドゥ":
                child.config(state=tk.NORMAL if is_undo_enabled else tk.DISABLED)
            elif child.cget("text") == "リドゥ":
                child.config(state=tk.NORMAL if is_redo_enabled else tk.DISABLED)
    logging.debug(f"update_undo_redo_menu: undo_stack is empty={not is_undo_enabled}, redo_stack is empty={not is_redo_enabled}")
    logging.debug("update_undo_redo_menu: update_undo_redo_menu() 関数が終了")

# セル移動処理
def move(direction):
    global current_row, current_col, max_row, max_col, current_value, undo_stack, redo_stack
    if sheet is None:
        return

    new_value = input_text.get("1.0", tk.END).strip()
    if new_value != current_value:
        save_cell_without_history()

    redo_stack.clear()
    undo_stack.clear()
    update_undo_redo_menu()

    if direction == "up" and current_row > 7:
        current_row -= 1
    elif direction == "down" and current_row < max_row:
        current_row += 1
    elif direction == "left" and current_col > 1:
        current_col -= 1
    elif direction == "right" and current_col < max_col:
        current_col += 1
    elif direction == "home":
        current_col = 1
    elif direction == "end":
        current_col = max_col
    elif direction == "pgup" and current_row > 7:
        current_row = max(7, current_row - 10)
    elif direction == "pgdn" and current_row < max_row:
        current_row = min(max_row, current_row + 10)

    update_display()
    input_text.focus_set()

# アンドゥ履歴なしでセルを保存
def save_cell_without_history():
    global current_row, current_col, current_value
    if sheet is None:
        return

    new_value = input_text.get("1.0", tk.END).strip()
    if new_value != current_value:
        sheet.cell(row=current_row, column=current_col, value=new_value)
    current_value = new_value

# 上からコピー処理
def copy_above():
    global current_row, current_col, root
    if sheet is None or current_row <= 7:
        return

    value = sheet.cell(row=current_row - 1, column=current_col).value
    root.clipboard_clear()
    if value is not None:
        root.clipboard_append(str(value))
        status_bar_message("上のセルの内容をコピーしました", 3)
    else:
        status_bar_message("上のセルは空白です", 3)
    root.update()

# 左からコピー処理
def copy_left():
    global current_row, current_col, root
    if sheet is None or current_col <= 1:
        return

    value = sheet.cell(row=current_row, column=current_col - 1).value
    root.clipboard_clear()
    if value is not None:
        root.clipboard_append(str(value))
        status_bar_message("左のセルの内容をコピーしました", 3)
    else:
        status_bar_message("左のセルは空白です", 3)
    root.update()

# 入力欄コピー機能
def copy_input_text_clipboard():
    global root, input_text
    text_to_copy = input_text.get("1.0", tk.END).strip()
    if not text_to_copy:
        status_bar_message("入力欄が空白です", 3)
        return

    root.clipboard_clear()
    root.clipboard_append(text_to_copy)
    root.update()
    status_bar_message("入力欄の内容をコピーしました", 3)

# 入力欄ペースト機能
def paste_input_text_clipboard():
    global root, input_text
    try:
        text_to_paste = root.clipboard_get()
        input_text.delete("1.0", tk.END)
        input_text.insert("1.0", text_to_paste)
        save_cell()
        status_bar_message("クリップボードからペーストしました", 3)
    except tk.TclError:
        status_bar_message("クリップボードにテキストデータがありません", 3)
        messagebox.showerror("エラー", "クリップボードにテキストデータがありません")

# クリップボードへコピー
def copy_cell_clipboard():
    global root, input_text
    text_to_copy = input_text.get("1.0", tk.END).strip()
    root.clipboard_clear()
    root.clipboard_append(text_to_copy)
    root.update()

# クリップボードからペースト
def paste_cell_clipboard_menu():
    global root, input_text
    try:
        text_to_paste = root.clipboard_get()
        input_text.delete("1.0", tk.END)
        input_text.insert("1.0", text_to_paste)
        save_cell()
    except tk.TclError:
        messagebox.showerror("エラー", "クリップボードにテキストデータがありません")

# 検索とジャンプ
def search_and_jump():
    global current_row, current_col, sheet, search_var, last_search_text, last_search_row, last_search_col
    if sheet is None:
        status_bar_message("Excelファイルを読み込んでから検索してください", 5)
        return

    search_text = search_var.get()
    if not search_text:
        return

    found = False
    start_row, start_col = current_row, current_col

    if search_text != last_search_text:
        start_row, start_col = current_row, current_col
        last_search_text = search_text
    else:
        start_row, start_col = last_search_row, last_search_col

    for row in range(start_row, max_row + 1):
        for col in range(start_col if row == start_row else 1, max_col + 1):
            cell_value = sheet.cell(row=row, column=col).value
            if cell_value is not None and search_text in str(cell_value):
                current_row, current_col = row, col
                last_search_row, last_search_col = current_row + (0 if current_col < max_col else 1), current_col + 1 if current_col < max_col else 1
                if last_search_row > max_row:
                    last_search_row = 7
                    last_search_col = 1
                update_display()
                status_bar_message(f"'{search_text}' をセル {get_column_letter(current_col)}{current_row} に見つけました", 5)
                found = True
                break
        if found:
            break

    if not found:
        for row in range(7, start_row + 1):
            for col in range(1, start_col if row == start_row else max_col + 1):
                if row == start_row and col >= start_col:
                    continue
                cell_value = sheet.cell(row=row, column=col).value
                if cell_value is not None and search_text in str(cell_value):
                    current_row, current_col = row, col
                    last_search_row, last_search_col = current_row + (0 if current_col < max_col else 1), current_col + 1 if current_col < max_col else 1
                    if last_search_row > max_row:
                        last_search_row = 7
                        last_search_col = 1
                    update_display()
                    status_bar_message(f"'{search_text}' をセル {get_column_letter(current_col)}{current_row} に見つけました (シート先頭から再検索)", 5)
                    found = True
                    break
            if found:
                break

    if not found:
        status_bar_message(f"'{search_text}' は見つかりませんでした", 5)
        messagebox.showinfo("検索", f"'{search_text}' は見つかりませんでした")

# 置換ダイアログを表示
def open_replace_dialog():
    replace_dialog = tk.Toplevel(root)
    replace_dialog.title("置換")
    replace_dialog.geometry("350x150")
    replace_dialog.resizable(False, False)

    search_var_replace = tk.StringVar()
    replace_var_replace = tk.StringVar()

    tk.Label(replace_dialog, text="検索する文字列:").pack()
    search_entry = tk.Entry(replace_dialog, textvariable=search_var_replace, width=20)
    search_entry.pack(pady=5)
    search_entry.focus_set()

    tk.Label(replace_dialog, text="置換後の文字列:").pack()
    replace_entry = tk.Entry(replace_dialog, textvariable=replace_var_replace, width=20)
    replace_entry.pack(pady=5)

    def replace_text_in_cell():
        search_text = search_var_replace.get()
        replace_text = replace_var_replace.get()
        if not search_text:
            return

        nonlocal replace_dialog

        current_cell_value = input_text.get("1.0", tk.END)
        if search_text in current_cell_value:
            modified_value = current_cell_value.replace(search_text, replace_text)
            input_text.delete("1.0", tk.END)
            input_text.insert("1.0", modified_value)
            save_cell()
            update_display()
            status_bar_message(f"セル内の '{search_text}' を '{replace_text}' に置換しました", 5)
        else:
            status_bar_message(f"セル内に '{search_text}' は見つかりませんでした", 5)
            messagebox.showinfo("置換", f"'{search_text}' は見つかりませんでした")
        replace_dialog.destroy()

    replace_button = tk.Button(replace_dialog, text="置換", command=replace_text_in_cell, width=12)
    replace_button.pack(pady=5)
    replace_dialog.bind('<Return>', lambda event=None: replace_text_in_cell())

# 指定セルへジャンプ
def jump_to_cell(cell_address):
    global current_row, current_col, max_row, max_col
    if sheet is None:
        return

    if not cell_address:
        return

    try:
        col_str = ''.join(filter(str.isalpha, cell_address.upper()))
        row_str = ''.join(filter(str.isdigit, cell_address))

        if not col_str or not row_str:
            raise ValueError("不正なセルアドレス形式")

        col_index = column_index_from_string(col_str)
        row = int(row_str)

        if row < 7 or row > max_row:
            raise ValueError("指定行番号が範囲外です")
        if col_index < 1 or col_index > max_col:
            raise ValueError("指定列番号が範囲外です")

        current_row, current_col = row, col_index
        update_display()
        status_bar_message(f"セル {cell_address.upper()} へ移動しました", 3)
    except ValueError as e:
        messagebox.showerror("エラー", f"不正なセルアドレスです: {e}")
    except Exception as e:
        logging.error(f"セルジャンプ中にエラー: {e}")
        messagebox.showerror("エラー", f"セルジャンプ中にエラーが発生しました: {e}")

# 入力欄からセルアドレスを取得してジャンプ
def jump_to_cell_from_entry():
    cell_address = jump_cell_var.get()
    if cell_address:
        jump_to_cell(cell_address)

# 列設定ダイアログ
def open_column_settings():
    global config
    dialog = tk.Toplevel(root)
    dialog.title("列設定")
    dialog.geometry("300x200")
    dialog.resizable(False, False)

    tk.Label(dialog, text="出品者SKUの列 (例: A):").pack(pady=5)
    sku_entry = ttk.Entry(dialog, width=5)
    sku_entry.insert(0, config["sku_column"])
    sku_entry.pack()

    tk.Label(dialog, text="商品名の列 (例: D):").pack(pady=5)
    name_entry = ttk.Entry(dialog, width=5)
    name_entry.insert(0, config["name_column"])
    name_entry.pack()

    tk.Label(dialog, text="カラム名の行 (例: 4):").pack(pady=5)
    row_entry = ttk.Entry(dialog, width=5)
    row_entry.insert(0, str(config["column_name_row"]))
    row_entry.pack()

    def save_settings():
        new_sku_col = sku_entry.get().strip().upper()
        new_name_col = name_entry.get().strip().upper()
        new_row = row_entry.get().strip()
        try:
            column_index_from_string(new_sku_col)
            column_index_from_string(new_name_col)
            row_num = int(new_row)
            if row_num < 1:
                raise ValueError("行番号は1以上でなければなりません")
            config["sku_column"] = new_sku_col
            config["name_column"] = new_name_col
            config["column_name_row"] = row_num
            save_config(config)
            update_display()
            dialog.destroy()
            status_bar_message("列設定を保存しました", 3)
        except ValueError as e:
            messagebox.showerror("エラー", f"無効な入力です: {e}")

    ttk.Button(dialog, text="保存", command=save_settings).pack(pady=10)
    dialog.bind('<Return>', lambda event=None: save_settings())

# ヘルプメッセージ表示
def show_help():
    help_text = """
    Amazon商品登録入力補助ツール ヘルプ

    【基本操作】
    ・Excelファイルを開く: 「ファイル」→「開く」または Ctrl+O
    ・名前を付けて保存: 「ファイル」→「名前を付けて保存」または Ctrl+Shift+S
    ・上書き保存:  「ファイル」→「保存」または Ctrl+S
    + セルへジャンプ:  「セルへジャンプ」欄にセルアドレスを入力し、Enterキーまたは「ジャンプ」ボタンをクリック
    + 検索:  「検索」欄に検索したい文字列を入力し、Enterキーまたは「ジャンプ」ボタンをクリック (最初に見つかったセルへジャンプ)
    ・アンドゥ: 「編集」→「アンドゥ」ボタン または Ctrl+Z
    ・リドゥ: 「編集」→「リドゥ」ボタン または Ctrl+Y
    ・置換: 「編集」→「置換」または Ctrl+R (現在のセル内を一括置換)
    ・上のセルをコピー: 操作ボタン「上からコピー」 (クリップボードへコピー)
    ・左のセルをコピー: 操作ボタン「左からコピー」 (クリップボードへコピー)
    ・入力欄コピー: 操作ボタン「入力欄コピー」
    ・入力欄ペースト: 操作ボタン「ペースト」
    ・クリップボードへコピー (セル内容): Ctrl+C
    ・クリップボードからペースト (セル内容): Ctrl+V
    ・セル内容クリア: Deleteキー
    ・セル移動: Ctrl+矢印キー、Ctrl+Home, Ctrl+End, Ctrl+PageUp (Ctrl+Prior), Ctrl+PageDown (Ctrl+Next)

    【ステータスバー表示】
    ・画面下部に、現在のセル位置、メッセージなどが表示されます。

    【その他】
    ・設定ファイル (config.json) : 起動時の初期セル位置、ウィンドウサイズ、最近使ったファイルリストなどが保存されます。
    ・ログファイル (error.log) : エラー発生時のログが記録されます。

    【注意点】
    ・「テンプレート」シートがあるExcelファイル（*.xlsm, *.xlsx）のみ対応しています。
    ・マクロ有効ブック (*.xlsm) で保存することを推奨します。
    ・検索は、「テンプレート」シート全体から最初に見つかったセルへジャンプします (部分一致検索)。
    ・置換は、現在選択されているセル内でのみ有効です。

    【バージョン情報】
    バージョン: 1.0 (2024-02-24)
    """
    help_text = help_text.replace("クリップボードへコピー (セル内容): Ctrl+C", "クリップボードへコピー (セル内容): Ctrl+C")
    help_text = help_text.replace("クリップボードからペースト (セル内容): Ctrl+V", "クリップボードからペースト (セル内容): Ctrl+V")
    messagebox.showinfo("ヘルプ", help_text)

# バージョン情報表示
def show_version():
    version_text = "Amazon商品登録入力補助ツール Version 1.0 (2024-02-24)"
    messagebox.showinfo("バージョン情報", version_text)

# 文字数をカウントし、表示を更新
def update_char_count(event=None):
    current_text = input_text.get("1.0", tk.END)
    char_count = len(current_text.strip())
    char_count_var.set(f"文字数: {char_count}")

# UI 構築
root.title("Amazon 商品登録入力補助ツール")

sku_var = tk.StringVar(value="（ファイル未読み込み）")
name_var = tk.StringVar(value="（ファイル未読み込み）")
column_name_var = tk.StringVar(value="カラム名")
char_count_var = tk.StringVar(value="文字数: 0")
jump_cell_var = tk.StringVar()
search_var = tk.StringVar()

window_width = config.get("window_width", 800)
window_height = config.get("window_height", 400)
root.geometry(f"{window_width}x{window_height}")

menubar = tk.Menu(root)
root.config(menu=menubar)

file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="開く", command=select_file, accelerator="Ctrl+O")
file_menu.add_command(label="名前を付けて保存", command=save_as_file, accelerator="Ctrl+Shift+S")
file_menu.add_command(label="保存", command=save_as_file, accelerator="Ctrl+S")
file_menu.add_separator()
recent_files_menu = tk.Menu(file_menu, tearoff=0)
file_menu.add_cascade(label="最近使ったファイル", menu=recent_files_menu)
update_recent_menu()
file_menu.add_separator()
file_menu.add_command(label="終了", command=root.quit)
menubar.add_cascade(label="ファイル", menu=file_menu)

edit_menu = tk.Menu(menubar, tearoff=0)
edit_menu.add_command(label="アンドゥ", command=undo, accelerator="Ctrl+Z", state=tk.DISABLED)
edit_menu.add_command(label="リドゥ", command=redo, accelerator="Ctrl+Y", state=tk.DISABLED)
edit_menu.add_separator()
edit_menu.add_command(label="置換", command=open_replace_dialog, accelerator="Ctrl+R")
edit_menu.add_separator()
edit_menu.add_command(label="クリップボードへコピー", command=copy_cell_clipboard, accelerator="Ctrl+C")
edit_menu.add_command(label="クリップボードからペースト", command=paste_cell_clipboard_menu, accelerator="Ctrl+V")
edit_menu.add_command(label="セル内容クリア", command=clear_cell, accelerator="Delete")
menubar.add_cascade(label="編集", menu=edit_menu)

settings_menu = tk.Menu(menubar, tearoff=0)
settings_menu.add_command(label="表示列の設定", command=open_column_settings)
menubar.add_cascade(label="設定", menu=settings_menu)

help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="ヘルプ", command=show_help)
help_menu.add_command(label="バージョン情報", command=show_version)
menubar.add_cascade(label="ヘルプ", menu=help_menu)

main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill=tk.BOTH, expand=True)

main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(2, weight=1)

# 左側操作UI Frame
left_ui_frame = ttk.Frame(main_frame)
left_ui_frame.grid(row=0, column=0, sticky="nw")

# 出品者SKU Frame
sku_frame = ttk.Frame(left_ui_frame)
sku_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

sku_label = ttk.Label(sku_frame, text="出品者SKU:", font=("Meiryo UI", 10))
sku_label.grid(row=0, column=0, sticky=tk.W)
sku_value_label = ttk.Label(sku_frame, textvariable=sku_var, font=("Meiryo UI", 10, "bold"), anchor=tk.W)
sku_value_label.grid(row=0, column=1, sticky=tk.W)

# 商品名 Frame
name_frame = ttk.Frame(left_ui_frame)
name_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

name_label = ttk.Label(name_frame, text="商品名:", font=("Meiryo UI", 10))
name_label.pack(side=tk.LEFT, anchor=tk.NW)

name_value_label = ttk.Label(name_frame, textvariable=name_var, font=("Meiryo UI", 10, "bold"), anchor=tk.W)
name_value_label.pack(side=tk.LEFT, anchor=tk.NW, fill=tk.X, expand=True)

# 文字数 Frame
char_count_frame = ttk.Frame(left_ui_frame)
char_count_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

char_count_label_ui = ttk.Label(char_count_frame, text="文字数:", font=("Meiryo UI", 9))
char_count_label_ui.pack(side=tk.LEFT, anchor=tk.W)
char_count_label = ttk.Label(char_count_frame, textvariable=char_count_var, anchor=tk.W, font=("Meiryo UI", 9))
char_count_label.pack(side=tk.LEFT, anchor=tk.W)

# セルへジャンプ Frame
jump_frame = ttk.Frame(left_ui_frame)
jump_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

jump_cell_label = ttk.Label(jump_frame, text="セルへジャンプ:", font=("Meiryo UI", 10))
jump_cell_label.grid(row=0, column=0, sticky=tk.W)

jump_cell_entry = ttk.Entry(jump_frame, textvariable=jump_cell_var, width=10, font=("Meiryo UI", 10))
jump_cell_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

jump_button = ttk.Button(jump_frame, text="ジャンプ", command=lambda: jump_to_cell_from_entry(), width=8)
jump_button.grid(row=0, column=2, sticky=tk.W, padx=5)

# 検索UI Frame
search_ui_frame = ttk.Frame(left_ui_frame)
search_ui_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

search_label = ttk.Label(search_ui_frame, text="検索:", font=("Meiryo UI", 10))
search_label.grid(row=0, column=0, sticky=tk.W)

search_entry_inline = ttk.Entry(search_ui_frame, textvariable=search_var, width=10, font=("Meiryo UI", 10))
search_entry_inline.grid(row=0, column=1, sticky=tk.W, padx=5)

search_button_inline = ttk.Button(search_ui_frame, text="ジャンプ", command=search_and_jump, width=8)
search_button_inline.grid(row=0, column=2, sticky=tk.W, padx=5)

# 操作ボタン Frame
button_frame_action = ttk.Frame(left_ui_frame)
button_frame_action.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))

tk.Button(button_frame_action, text="保存", command=save_as_file, width=10).grid(row=0, column=0, padx=2, pady=2)
tk.Button(button_frame_action, text="クリア", command=clear_cell, width=10).grid(row=0, column=1, padx=2, pady=2)
tk.Button(button_frame_action, text="アンドゥ", command=undo, width=10).grid(row=0, column=2, padx=2, pady=2)
tk.Button(button_frame_action, text="リドゥ", command=redo, width=10).grid(row=0, column=3, padx=2, pady=2)
tk.Button(button_frame_action, text="上からコピー", command=copy_above, width=10).grid(row=1, column=0, padx=2, pady=2)
tk.Button(button_frame_action, text="左からコピー", command=copy_left, width=10).grid(row=1, column=1, padx=2, pady=2)
tk.Button(button_frame_action, text="入力欄コピー", command=copy_input_text_clipboard, width=10).grid(row=1, column=2, padx=2, pady=2)
tk.Button(button_frame_action, text="ペースト", command=paste_input_text_clipboard, width=10).grid(row=1, column=3, padx=2, pady=2)

# カラム名表示
column_name_label = ttk.Label(main_frame, textvariable=column_name_var, anchor=tk.W, relief=tk.SOLID, padding=5, borderwidth=1, font=("Meiryo UI", 10))
column_name_label.grid(row=1, column=0, sticky=tk.W+tk.E, pady=5, padx=5)
column_name_label.tooltip_text = ""
ToolTip(column_name_label, column_name_label.tooltip_text)

# テキスト入力エリア
input_text = tk.Text(main_frame, height=15, width=60, font=("Meiryo UI", 11), wrap=tk.WORD)
input_text.grid(row=2, column=0, sticky=tk.NSEW, padx=5)
input_text.bind("<FocusOut>", lambda event: save_cell(event))
input_text.bind("<Return>", lambda event: save_cell(event))
input_text.bind("<Shift-Return>", insert_newline)

# 移動ボタン Frame
button_frame_move = ttk.Frame(main_frame)
button_frame_move.grid(row=6, column=0, sticky="ew", padx=5, pady=(5, 0))

tk.Button(button_frame_move, text="↑", command=lambda: move("up"), width=5).grid(row=0, column=1)
tk.Button(button_frame_move, text="↓", command=lambda: move("down"), width=5).grid(row=1, column=1)
tk.Button(button_frame_move, text="←", command=lambda: move("left"), width=5).grid(row=1, column=0)
tk.Button(button_frame_move, text="→", command=lambda: move("right"), width=5).grid(row=1, column=2)
tk.Button(button_frame_move, text="Home", command=lambda: move("home"), width=5).grid(row=0, column=0)
tk.Button(button_frame_move, text="End", command=lambda: move("end"), width=5).grid(row=0, column=2)
tk.Button(button_frame_move, text="PageUp", command=lambda: move("pgup"), width=5).grid(row=0, column=3)
tk.Button(button_frame_move, text="PageDown", command=lambda: move("pgdn"), width=5).grid(row=1, column=3)

# ステータスバー
status_bar_var = tk.StringVar()
status_bar = ttk.Label(root, textvariable=status_bar_var, relief=tk.SUNKEN, anchor=tk.W, font=("Meiryo UI", 9))
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

status_bar_pos_var = tk.StringVar()
status_bar_pos = ttk.Label(status_bar, textvariable=status_bar_pos_var, relief=tk.FLAT, anchor=tk.E, font=("Meiryo UI", 9))
status_bar_pos.pack(side=tk.RIGHT, padx=10)
status_bar_cell_pos()

# ショートカットキー設定
root.bind("<Control-o>", lambda event=None: select_file())
root.bind("<Control-Shift-s>", lambda event=None: save_as_file())
root.bind("<Control-s>", lambda event=None: save_as_file())
root.bind("<Control-z>", lambda event=None: undo())
root.bind("<Control-y>", lambda event=None: redo())
root.bind("<Delete>", lambda event=None: clear_cell())
root.bind("<Control-r>", lambda event=None: open_replace_dialog())
root.bind("<Control-c>", lambda event=None: copy_cell_clipboard())
root.bind("<Control-v>", lambda event=None: paste_cell_clipboard_menu())
root.bind("<Control-Home>", lambda event=None: move("home"))
root.bind("<Control-End>", lambda event=None: move("end"))
root.bind("<Control-Left>", lambda event=None: move("left"))
root.bind("<Control-Right>", lambda event=None: move("right"))
root.bind("<Control-Prior>", lambda event=None: move("pgup"))
root.bind("<Control-Next>", lambda event=None: move("pgdn"))
root.bind("<Return>", lambda event=None: search_and_jump())

input_text.bind("<KeyRelease>", update_char_count)

# 初期設定
update_undo_redo_menu()

# ウィンドウが閉じられる際の処理
def on_closing():
    config["window_width"] = root.winfo_width()
    config["window_height"] = root.winfo_height()
    save_config(config)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# メインループ開始
root.mainloop()
