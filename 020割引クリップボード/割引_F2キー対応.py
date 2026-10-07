import tkinter as tk
from tkinter import ttk
import pyperclip
import re
import time
import threading
import math
import json
import os
import pyautogui
import keyboard

# 安全設定：マウスを画面左上に移動でマクロ停止
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

class MacroExecutor:
    def __init__(self, parent):
        self.parent = parent
        self.is_macro_running = False
        self.trigger_key = None
        self.macro_widgets = []
        self.create_macro_widgets()
        self.load_macro_settings()

    def create_macro_widgets(self):
        # チェックボックス
        self.macro_checkbox_var = tk.BooleanVar(value=False)
        self.macro_checkbox = tk.Checkbutton(self.parent.root, text="キーマクロ", variable=self.macro_checkbox_var, command=self.toggle_macro_visibility)
        self.macro_checkbox.grid(row=6, column=0, columnspan=5, sticky="w", pady=10)

        # マクロ名プルダウン
        self.macro_name_label = tk.Label(self.parent.root, text="マクロ名")
        self.macro_name_label.grid(row=7, column=0, padx=5, pady=5)
        self.macro_widgets.append(self.macro_name_label)
        self.macro_name_var = tk.StringVar(value="新規")
        self.macro_name_menu = ttk.Combobox(self.parent.root, textvariable=self.macro_name_var, state="readonly")
        self.macro_name_menu.grid(row=7, column=1, columnspan=4, padx=5, pady=5, sticky="ew")
        self.macro_name_menu.bind("<<ComboboxSelected>>", self.load_selected_macro)
        self.macro_widgets.append(self.macro_name_menu)
        self.update_macro_name_menu()

        # トリガーキー
        self.trigger_key_label = tk.Label(self.parent.root, text="トリガーキー")
        self.trigger_key_label.grid(row=8, column=0, padx=5, pady=5)
        self.macro_widgets.append(self.trigger_key_label)
        self.trigger_key_var = tk.StringVar(value="F1")
        trigger_options = [f"F{i}" for i in range(1, 13)]
        self.trigger_menu = ttk.Combobox(self.parent.root, textvariable=self.trigger_key_var, values=trigger_options, state="readonly")
        self.trigger_menu.grid(row=8, column=1, columnspan=4, padx=5, pady=5, sticky="ew")
        self.macro_widgets.append(self.trigger_menu)

        # 繰り返し回数
        self.repeat_count_label = tk.Label(self.parent.root, text="繰り返し回数")
        self.repeat_count_label.grid(row=9, column=0, padx=5, pady=5)
        self.macro_widgets.append(self.repeat_count_label)
        self.repeat_count_entry = tk.Entry(self.parent.root, width=10)
        self.repeat_count_entry.insert(0, "1")
        self.repeat_count_entry.grid(row=9, column=1, columnspan=4, padx=5, pady=5, sticky="ew")
        self.macro_widgets.append(self.repeat_count_entry)

        # キーシーケンス
        self.key_sequence_label = tk.Label(self.parent.root, text="キーシーケンス")
        self.key_sequence_label.grid(row=10, column=0, padx=5, pady=5)
        self.macro_widgets.append(self.key_sequence_label)
        self.key_sequence_entry = tk.Entry(self.parent.root, width=30)
        self.key_sequence_entry.insert(0, "Ctrl+C,Tab,Ctrl+V,Enter")
        self.key_sequence_entry.grid(row=10, column=1, columnspan=4, padx=5, pady=5, sticky="ew")
        self.macro_widgets.append(self.key_sequence_entry)

        # 確定、入力補助、開始ボタン
        self.macro_confirm_button = tk.Button(self.parent.root, text="マクロ確定", command=self.save_macro_settings, width=8)
        self.macro_confirm_button.grid(row=11, column=0, padx=5, pady=10)
        self.macro_widgets.append(self.macro_confirm_button)
        self.macro_assist_button = tk.Button(self.parent.root, text="入力補助", command=self.show_key_assist_dialog, width=8)
        self.macro_assist_button.grid(row=11, column=1, padx=5, pady=10)
        self.macro_widgets.append(self.macro_assist_button)
        self.macro_button = tk.Button(self.parent.root, text="マクロ開始", command=self.toggle_macro, width=8)
        self.macro_button.grid(row=11, column=2, columnspan=3, padx=5, pady=10, sticky="ew")
        self.macro_widgets.append(self.macro_button)

        # ステータス
        self.macro_status_label = tk.Label(self.parent.root, text="マクロ停止中")
        self.macro_status_label.grid(row=12, column=0, columnspan=5, pady=5)
        self.macro_widgets.append(self.macro_status_label)

        # 初期非表示
        if not self.macro_checkbox_var.get():
            for widget in self.macro_widgets:
                widget.grid_remove()

    def toggle_macro_visibility(self):
        if self.macro_checkbox_var.get():
            for widget in self.macro_widgets:
                widget.grid()
        else:
            for widget in self.macro_widgets:
                widget.grid_remove()

    def update_macro_name_menu(self):
        macro_names = ["新規"] + list(self.parent.settings.get("macros", {}).keys())
        self.macro_name_menu["values"] = macro_names
        if self.macro_name_var.get() not in macro_names:
            self.macro_name_var.set("新規")

    def load_selected_macro(self, event=None):
        macro_name = self.macro_name_var.get()
        if macro_name != "新規" and "macros" in self.parent.settings:
            macro_settings = self.parent.settings["macros"].get(macro_name, {})
            self.trigger_key_var.set(macro_settings.get("trigger_key", "F1"))
            self.repeat_count_entry.delete(0, tk.END)
            self.repeat_count_entry.insert(0, str(macro_settings.get("repeat_count", 1)))
            self.key_sequence_entry.delete(0, tk.END)
            self.key_sequence_entry.insert(0, macro_settings.get("key_sequence", "Ctrl+C,Tab,Ctrl+V,Enter"))

    def load_macro_settings(self):
        if "macro" in self.parent.settings:
            macro_settings = self.parent.settings["macro"]
            self.trigger_key_var.set(macro_settings.get("trigger_key", "F1"))
            self.repeat_count_entry.delete(0, tk.END)
            self.repeat_count_entry.insert(0, str(macro_settings.get("repeat_count", 1)))
            self.key_sequence_entry.delete(0, tk.END)
            self.key_sequence_entry.insert(0, macro_settings.get("key_sequence", "Ctrl+C,Tab,Ctrl+V,Enter"))
        self.macro_checkbox_var.set(False)  # 常にオフで開始
        self.toggle_macro_visibility()

    def show_key_assist_dialog(self):
        dialog = tk.Toplevel(self.parent.root)
        dialog.title("キー選択")
        dialog.transient(self.parent.root)
        dialog.grab_set()
        dialog.geometry("400x500+%d+%d" % (
            self.parent.root.winfo_rootx() + self.parent.root.winfo_width() // 2 - 200,
            self.parent.root.winfo_rooty() + self.parent.root.winfo_height() // 2 - 325
        ))

        tk.Label(dialog, text="キーをクリックで追加").pack(pady=10)

        # キーパッドフレーム
        keypad_frame = tk.Frame(dialog)
        keypad_frame.pack(pady=10)

        # キーパッドレイアウト（5列×14行、ctrl+aの右にF2を追加）
        keypad_layout = [
            ["ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "F2"],
            [".", ".", ".", ".", "."],
            ["tab", "home", "shift+home", "pageup", "backspace"],
            ["shift+tab", "end", "shift+end", "pagedown", "delete"],
            [".", ".", ".", ".", "."],
            ["setting1", ".", ".", "/", "*"],
            ["setting2", "7", "8", "9", "-"],
            ["setting3", "4", "5", "6", "+"],
            ["setting4", "1", "2", "3", "="],
            ["setting5", "0", ".", ".", "enter"],
            ["reset", ".", "up", ".", "."],
            [".", "left", "down", "right", "."],
            [".", ".", ".", ".", "."],
            [".", ".", "閉じる", ".", "削除"]
        ]

        def add_keypad_key(key):
            if key != "." and key != "閉じる" and key != "削除":
                current_sequence = self.key_sequence_entry.get().strip()
                new_sequence = current_sequence + ("," + key if current_sequence else key)
                self.key_sequence_entry.delete(0, tk.END)
                self.key_sequence_entry.insert(0, new_sequence)

        def delete_last_key():
            current_sequence = self.key_sequence_entry.get().strip()
            if current_sequence:
                keys = current_sequence.split(",")
                if keys:
                    keys.pop()  # 最後のキーを削除
                    new_sequence = ",".join(keys)
                    self.key_sequence_entry.delete(0, tk.END)
                    self.key_sequence_entry.insert(0, new_sequence)

        for row, keys in enumerate(keypad_layout):
            for col, key in enumerate(keys):
                if key == "閉じる":
                    btn = tk.Button(keypad_frame, text=key, width=8, command=dialog.destroy)
                    btn.grid(row=row, column=col, padx=2, pady=2)
                elif key == "削除":
                    btn = tk.Button(keypad_frame, text=key, width=8, command=delete_last_key)
                    btn.grid(row=row, column=col, padx=2, pady=2)
                elif key != ".":
                    btn = tk.Button(keypad_frame, text=key, width=8, command=lambda k=key: add_keypad_key(k))
                    btn.grid(row=row, column=col, padx=2, pady=2)
                else:
                    tk.Label(keypad_frame, text="", width=8).grid(row=row, column=col, padx=2, pady=2)

    def save_macro_settings(self):
        try:
            repeat_count = int(self.repeat_count_entry.get())
            if not (1 <= repeat_count <= 100):
                raise ValueError
            key_sequence = self.key_sequence_entry.get().strip()
            if not self.validate_key_sequence(key_sequence):
                raise ValueError
        except ValueError:
            self.macro_status_label.config(text="無効な入力です（繰り返し回数：1～100、キーシーケンスを確認）")
            return

        # 名前入力ダイアログ
        dialog = tk.Toplevel(self.parent.root)
        dialog.title("マクロ名を入力")
        dialog.transient(self.parent.root)
        dialog.grab_set()
        dialog.geometry("300x150+%d+%d" % (
            self.parent.root.winfo_rootx() + self.parent.root.winfo_width() // 2 - 150,
            self.parent.root.winfo_rooty() + self.parent.root.winfo_height() // 2 - 75
        ))

        tk.Label(dialog, text="マクロ名を入力してください").pack(pady=10)
        name_entry = tk.Entry(dialog, width=20)
        current_macro_name = self.macro_name_var.get()
        if current_macro_name != "新規":
            name_entry.insert(0, current_macro_name)
        name_entry.pack(pady=5)
        name_entry.focus_set()

        def save():
            macro_name = name_entry.get().strip()
            if not macro_name:
                self.macro_status_label.config(text="マクロ名を入力してください")
                dialog.destroy()
                return
            if "macros" not in self.parent.settings:
                self.parent.settings["macros"] = {}
            self.parent.settings["macros"][macro_name] = {
                "trigger_key": self.trigger_key_var.get(),
                "repeat_count": repeat_count,
                "key_sequence": key_sequence
            }
            self.parent.settings["macro"] = {
                "trigger_key": self.trigger_key_var.get(),
                "repeat_count": repeat_count,
                "key_sequence": key_sequence
            }
            self.parent.save_settings()
            self.update_macro_name_menu()
            self.macro_name_var.set(macro_name)
            self.macro_status_label.config(text=f"マクロ '{macro_name}' を保存しました")
            dialog.destroy()

        tk.Button(dialog, text="保存", command=save).pack(pady=10)
        dialog.bind("<Return>", lambda event: save())

    def toggle_macro(self):
        if not self.is_macro_running:
            try:
                repeat_count = int(self.repeat_count_entry.get())
                if 1 <= repeat_count <= 100:
                    self.trigger_key = self.trigger_key_var.get().lower()
                    key_sequence = self.key_sequence_entry.get().strip()
                    if self.validate_key_sequence(key_sequence):
                        self.is_macro_running = True
                        self.macro_button.config(text="マクロ停止")
                        self.macro_status_label.config(text="マクロ待機中")
                        self.trigger_menu.config(state="disabled")
                        self.repeat_count_entry.config(state="disabled")
                        self.key_sequence_entry.config(state="disabled")
                        self.macro_assist_button.config(state="disabled")
                        threading.Thread(target=self.monitor_trigger, daemon=True).start()
                    else:
                        self.macro_status_label.config(text="無効なキーシーケンスです")
                else:
                    self.macro_status_label.config(text="繰り返し回数は1～100で入力してください")
            except ValueError:
                self.macro_status_label.config(text="有効な繰り返し回数を入力してください")
        else:
            self.is_macro_running = False
            self.macro_button.config(text="マクロ開始")
            self.macro_status_label.config(text="マクロ停止中")
            self.trigger_menu.config(state="readonly")
            self.repeat_count_entry.config(state="normal")
            self.key_sequence_entry.config(state="normal")
            self.macro_assist_button.config(state="normal")

    def validate_key_sequence(self, sequence):
        if not sequence:
            return False
        keys = sequence.split(",")
        for key in keys:
            key = key.strip().lower()
            if key not in self.valid_keys:
                return False
        return True

    @property
    def valid_keys(self):
        return {
            "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "f2", "enter", "tab", "shift+tab",
            "home", "shift+home", "end", "shift+end", "up", "down", "left", "right",
            "backspace", "delete", "pageup", "pagedown", "*", "+", "-", "/", "=",
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "reset", "setting1", "setting2", "setting3", "setting4", "setting5"
        }

    def execute_macro(self, sequence, repeat_count):
        for _ in range(repeat_count):
            for key in sequence.split(","):
                key = key.strip().lower()
                if key in {"reset", "setting1", "setting2", "setting3", "setting4", "setting5"}:
                    # 特殊入力の処理
                    if key == "reset":
                        self.parent.reset_last_clipboard()
                    else:
                        setting_id = key.replace("setting", "")
                        self.parent.load_setting(setting_id)
                elif "+" in key:
                    combo = key.split("+")
                    with pyautogui.hold(combo[0]):
                        pyautogui.press(combo[1])
                else:
                    if key == "=":
                        pyautogui.press("equals")
                    elif key == "f2":
                        pyautogui.press("f2")
                    else:
                        pyautogui.press(key)
                if not self.is_macro_running:
                    break
            if not self.is_macro_running:
                break

    def monitor_trigger(self):
        while self.is_macro_running:
            try:
                if keyboard.is_pressed(self.trigger_key):
                    self.macro_status_label.config(text=f"マクロ実行中: {self.trigger_key}")
                    repeat_count = int(self.repeat_count_entry.get())
                    key_sequence = self.key_sequence_entry.get().strip()
                    self.execute_macro(key_sequence, repeat_count)
                    self.macro_status_label.config(text="マクロ待機中")
                    while keyboard.is_pressed(self.trigger_key):
                        time.sleep(0.01)
            except Exception as e:
                self.macro_status_label.config(text=f"マクロエラー: {str(e)}")
            time.sleep(0.01)

class DiscountCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Discount Calculator")
        self.is_running = False
        self.last_clipboard = ""
        self.ignore_next_clipboard = False
        self.current_setting = None
        self.settings = self.load_settings()
        self.create_widgets()
        self.macro_executor = MacroExecutor(self)

    def load_settings(self):
        default_settings = {
            "1": {"discount": 10, "round_type": "切り捨て", "round_digit": "10の位"},
            "2": {"discount": 20, "round_type": "切り捨て", "round_digit": "10の位"},
            "3": {"discount": 30, "round_type": "切り捨て", "round_digit": "10の位"},
            "4": {"discount": 40, "round_type": "切り捨て", "round_digit": "10の位"},
            "5": {"discount": 50, "round_type": "切り捨て", "round_digit": "10の位"},
            "macro": {
                "trigger_key": "F1",
                "repeat_count": 1,
                "key_sequence": "Ctrl+C,Tab,Ctrl+V,Enter"
            },
            "macros": {}
        }
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    loaded = json.load(f)
                    settings = {**default_settings, **loaded}
                    return settings
            except:
                return default_settings
        return default_settings

    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

    def create_widgets(self):
        self.setting_buttons = {}
        for i in range(1, 6):
            discount = int(self.settings[str(i)]["discount"]) if self.settings[str(i)]["discount"] else "設定"
            btn = tk.Button(self.root, text=f"設定{i} ({discount}%)", command=lambda x=i: self.load_setting(str(x)))
            btn.grid(row=0, column=i-1, padx=2, pady=5)
            self.setting_buttons[str(i)] = btn

        tk.Label(self.root, text="割引率 (%)").grid(row=1, column=0, padx=5, pady=5)
        self.discount_entry = tk.Entry(self.root, width=10)
        self.discount_entry.insert(0, "10")
        self.discount_entry.grid(row=1, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        tk.Label(self.root, text="丸め処理").grid(row=2, column=0, padx=5, pady=5)
        self.round_type = tk.StringVar(value="切り捨て")
        round_options = ["四捨五入", "切り上げ", "切り捨て"]
        self.round_menu = ttk.Combobox(self.root, textvariable=self.round_type, values=round_options, state="readonly")
        self.round_menu.grid(row=2, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        tk.Label(self.root, text="丸め桁数").grid(row=3, column=0, padx=5, pady=5)
        self.round_digit = tk.StringVar(value="10の位")
        digit_options = ["1の位", "10の位", "100の位"]
        self.digit_menu = ttk.Combobox(self.root, textvariable=self.round_digit, values=digit_options, state="readonly")
        self.digit_menu.grid(row=3, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        self.confirm_button = tk.Button(self.root, text="確定", command=self.confirm_setting, width=8)
        self.confirm_button.grid(row=4, column=0, padx=5, pady=10)
        self.reset_button = tk.Button(self.root, text="リセット", command=self.reset_last_clipboard, width=8)
        self.reset_button.grid(row=4, column=1, padx=5, pady=10)
        self.start_button = tk.Button(self.root, text="開始", command=self.toggle_monitoring, width=8)
        self.start_button.grid(row=4, column=2, columnspan=3, padx=5, pady=10, sticky="ew")

        self.status_label = tk.Label(self.root, text="停止中")
        self.status_label.grid(row=5, column=0, columnspan=5, pady=5)

    def reset_last_clipboard(self):
        self.last_clipboard = ""
        self.status_label.config(text="リセット完了")

    def load_setting(self, setting_id):
        self.current_setting = setting_id
        setting = self.settings[setting_id]
        self.discount_entry.delete(0, tk.END)
        self.discount_entry.insert(0, str(setting["discount"]))
        self.round_type.set(setting["round_type"])
        self.round_digit.set(setting["round_digit"])
        for btn_id in self.setting_buttons:
            self.setting_buttons[btn_id].config(bg="SystemButtonFace")
        self.setting_buttons[setting_id].config(bg="#77ff77")
        self.update_button_labels()

    def confirm_setting(self):
        if not self.current_setting:
            self.status_label.config(text="設定ボタンを選択してください")
            return
        try:
            discount = float(self.discount_entry.get())
            if 0 <= discount <= 100:
                self.settings[self.current_setting] = {
                    "discount": discount,
                    "round_type": self.round_type.get(),
                    "round_digit": self.round_digit.get()
                }
                self.save_settings()
                self.update_button_labels()
                self.status_label.config(text=f"設定{self.current_setting}を保存しました")
            else:
                self.status_label.config(text="割引率は0～100の範囲で入力してください")
        except ValueError:
            self.status_label.config(text="有効な割引率を入力してください")

    def update_button_labels(self):
        for i in range(1, 6):
            discount = int(self.settings[str(i)]["discount"]) if self.settings[str(i)]["discount"] else "設定"
            self.setting_buttons[str(i)].config(text=f"設定{i} ({discount}%)")

    def toggle_monitoring(self):
        if not self.is_running:
            try:
                discount = float(self.discount_entry.get())
                if 0 <= discount <= 100:
                    self.is_running = True
                    self.start_button.config(text="停止")
                    self.status_label.config(text="監視中")
                    threading.Thread(target=self.monitor_clipboard, daemon=True).start()
                else:
                    self.status_label.config(text="割引率は0～100の範囲で入力してください")
            except ValueError:
                self.status_label.config(text="有効な割引率を入力してください")
        else:
            self.is_running = False
            self.start_button.config(text="開始")
            self.status_label.config(text="停止中")

    def monitor_clipboard(self):
        while self.is_running:
            try:
                current_clipboard = pyperclip.paste()
                if self.ignore_next_clipboard:
                    self.last_clipboard = current_clipboard
                    self.ignore_next_clipboard = False
                    time.sleep(0.1)
                    continue

                # 先頭/末尾の空白類を除去
                current_clipboard_stripped = current_clipboard.strip()

                # 正規表現を調整して空白類を許容
                if current_clipboard_stripped != self.last_clipboard.strip() and re.match(r'^\s*\d+(?:,\d{3})*(?:\.\d+)?\s*$', current_clipboard):
                    self.last_clipboard = current_clipboard
                    # カンマを除去して数値に変換（stripしたものを使用）
                    number_str = current_clipboard_stripped.replace(",", "")
                    number = float(number_str)
                    result = self.calculate_discount(number)
                    # 入力にコンマが含まれているかチェック（オリジナルを使用）
                    use_commas = "," in current_clipboard
                    # 結果を入力形式に合わせてフォーマット
                    if use_commas:
                        result_str = f"{result:,.2f}".rstrip("0").rstrip(".")
                    else:
                        result_str = f"{result:.2f}".rstrip("0").rstrip(".")
                    self.ignore_next_clipboard = True
                    pyperclip.copy(result_str)
                    self.status_label.config(text=f"計算結果: {result_str}")
                self.last_clipboard = current_clipboard
            except Exception as e:
                self.status_label.config(text=f"エラー: {str(e)}")
            time.sleep(0.1)

    def calculate_discount(self, number):
        discount_rate = float(self.discount_entry.get()) / 100
        discounted = number * (1 - discount_rate)
        digit_map = {"1の位": 0, "10の位": 1, "100の位": 2}
        digit = digit_map[self.round_digit.get()]
        if self.round_type.get() == "四捨五入":
            return round(discounted, -digit)
        elif self.round_type.get() == "切り上げ":
            factor = 10 ** digit
            return math.ceil(discounted / factor) * factor
        elif self.round_type.get() == "切り捨て":
            factor = 10 ** digit
            return math.floor(discounted / factor) * factor

if __name__ == "__main__":
    root = tk.Tk()
    app = DiscountCalculator(root)
    root.protocol("WM_DELETE_WINDOW", lambda: [app.save_settings(), root.destroy()])
    root.mainloop()