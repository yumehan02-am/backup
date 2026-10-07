import tkinter as tk
from tkinter import ttk, colorchooser
import pyautogui
import pyperclip
import win32clipboard
import os
import csv
from threading import Thread, RLock
import time
from pynput import mouse, keyboard
import logging
import json

# デバッグ用ログ設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class MouseTextApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mouse Text Follower")
        self.root.geometry("350x60")
        self.root.minsize(350, 50)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.running = False
        self.text_window = None
        self.settings_window = None
        self.update_thread = None
        self.clipboard_monitoring = False
        self.clipboard_thread = None
        self.hotkey = "f1"  # ← デフォルトを f1 に変更
        self.history = []
        self.history_index = -1
        self.history_file = "history.csv"
        self.settings_file = "settings.json"
        self.wheel_base_key = "alt"
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.alt_pressed = False
        self.history_limit = 50
        self.file_separator = "\n"
        self.file_copy_mode = "file"
        
        self.text_color = "#FFFFFF"
        self.bg_color = "#000000"
        self.bg_alpha = 0.8
        self.font_size = 10
        self.clipboard_var = tk.BooleanVar(value=True)
        self.popup_var = tk.BooleanVar(value=True)
        self.popup_display = True
        self.last_scroll_time = 0
        self.last_key_time = 0
        self.history_lock = RLock()
        
        self.display_state = 0  # 0: OFF, 1: ON yellow (popup on), 2: ON green (popup off)
        
        self.load_settings()
        self.load_history()
        self.create_widgets()
        self.update_gui_from_settings()
        self.start_input_listeners()
        self.root.mainloop()

    def create_widgets(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(pady=2, padx=5, fill=tk.BOTH, expand=True)
        
        self.text_entry = tk.Text(main_frame, height=1, width=25, wrap=tk.WORD)
        self.text_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        button_frame = tk.Frame(main_frame)
        button_frame.pack(side=tk.RIGHT)
        
        top_button_frame = tk.Frame(button_frame)
        top_button_frame.pack()
        
        self.back_button = tk.Button(top_button_frame, text="▲", 
                                     command=self.history_forward, width=3)
        self.back_button.pack(side=tk.LEFT, padx=2)
        
        self.toggle_button = tk.Button(top_button_frame, text="OFF", 
                                     command=self.cycle_display, width=5)
        self.toggle_button.pack(side=tk.LEFT, padx=2)
        
        tk.Button(top_button_frame, text="クリア", 
                 command=self.clear_history_entry, width=5).pack(side=tk.LEFT, padx=2)
        
        bottom_button_frame = tk.Frame(button_frame)
        bottom_button_frame.pack()
        
        self.forward_button = tk.Button(bottom_button_frame, text="▼", 
                                        command=self.history_backward, width=3)
        self.forward_button.pack(side=tk.LEFT, padx=2)
        
        self.data_button = tk.Button(bottom_button_frame, text="データ", 
                                    command=self.toggle_file_mode, width=5)
        self.data_button.pack(side=tk.LEFT, padx=2)
        
        tk.Button(bottom_button_frame, text="設定", 
                 command=self.open_settings, width=5).pack(side=tk.LEFT, padx=2)

    def update_gui_from_settings(self):
        if self.file_copy_mode == "filename":
            self.data_button.config(text="名前")
        else:
            self.data_button.config(text="データ")

    def cycle_display(self):
        """GUIボタン・ホットキー共通の3状態トグル"""
        self.display_state = (self.display_state + 1) % 3
        if self.display_state == 0:
            self.running = False
            self.toggle_button.config(text="OFF", bg="SystemButtonFace")
            self.clipboard_monitoring = False
            if self.text_window:
                self.text_window.destroy()
                self.text_window = None
        elif self.display_state == 1:
            self.running = True
            self.toggle_button.config(text="ON", bg="yellow")
            self.popup_display = True
            if self.history:
                self.history_index = 0
                self.update_from_history()
            if self.clipboard_var.get() and (not self.clipboard_thread or not self.clipboard_thread.is_alive()):
                self.clipboard_monitoring = True
                self.clipboard_thread = Thread(target=self.monitor_clipboard, daemon=True)
                self.clipboard_thread.start()
            self.show_text()
        elif self.display_state == 2:
            self.running = True
            self.toggle_button.config(text="ON", bg="#39FF14")  # 明るい蛍光グリーン
            self.popup_display = False
            if self.history:
                self.history_index = 0
                self.update_from_history()
            if self.clipboard_var.get() and (not self.clipboard_thread or not self.clipboard_thread.is_alive()):
                self.clipboard_monitoring = True
                self.clipboard_thread = Thread(target=self.monitor_clipboard, daemon=True)
                self.clipboard_thread.start()
            if self.text_window:
                self.text_window.destroy()
                self.text_window = None

    def toggle_file_mode(self):
        if self.file_copy_mode == "file":
            self.file_copy_mode = "filename"
            self.data_button.config(text="名前")
        else:
            self.file_copy_mode = "file"
            self.data_button.config(text="データ")
        self.save_settings()

    def open_settings(self):
        if self.settings_window is not None:
            return
        
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("設定")
        self.settings_window.geometry("265x380")
        self.settings_window.resizable(False, False)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings)
        self.root.attributes('-disabled', True)
        
        self.temp_settings = {
            'font_size': self.font_size,
            'text_color': self.text_color,
            'bg_color': self.bg_color,
            'bg_alpha': self.bg_alpha,
            'history_limit': self.history_limit,
            'file_separator': self.file_separator,
            'hotkey': self.hotkey,
            'wheel_base_key': self.wheel_base_key
        }
        
        tk.Label(self.settings_window, text="フォントサイズ:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.size_var = tk.IntVar(value=self.temp_settings['font_size'])
        tk.Scale(self.settings_window, from_=8, to=50, orient=tk.HORIZONTAL,
                variable=self.size_var, length=120,
                command=lambda v: self.update_temp_setting('font_size', int(v))).grid(row=0, column=1, pady=5)
        
        tk.Label(self.settings_window, text="テキストカラー:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        tk.Button(self.settings_window, text="選択", 
                 command=lambda: self.choose_color('text')).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        tk.Label(self.settings_window, text="背景カラー:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        tk.Button(self.settings_window, text="選択", 
                 command=lambda: self.choose_color('bg')).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        tk.Label(self.settings_window, text="透明度:").grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        self.bg_alpha_var = tk.DoubleVar(value=self.temp_settings['bg_alpha'])
        tk.Scale(self.settings_window, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                variable=self.bg_alpha_var, resolution=0.1, length=120,
                command=lambda v: self.update_temp_setting('bg_alpha', float(v))).grid(row=3, column=1, pady=5)
        
        tk.Label(self.settings_window, text="ON/OFFホットキー:").grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        self.hotkey_entry = tk.Entry(self.settings_window, width=10)
        self.hotkey_entry.insert(0, self.temp_settings['hotkey'])
        self.hotkey_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        tk.Button(self.settings_window, text="設定", command=self.set_hotkey).grid(row=4, column=1, sticky=tk.E, pady=5)
        
        tk.Label(self.settings_window, text="履歴ホイールキー:").grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)
        self.wheel_base_entry = tk.Entry(self.settings_window, width=10)
        self.wheel_base_entry.insert(0, self.temp_settings['wheel_base_key'])
        self.wheel_base_entry.grid(row=5, column=1, sticky=tk.W, pady=5)
        tk.Button(self.settings_window, text="設定", command=self.set_wheel_base).grid(row=5, column=1, sticky=tk.E, pady=5)
        
        tk.Label(self.settings_window, text="履歴上限:").grid(row=6, column=0, sticky=tk.W, pady=5, padx=5)
        self.history_limit_entry = tk.Entry(self.settings_window, width=10)
        self.history_limit_entry.insert(0, str(self.temp_settings['history_limit']))
        self.history_limit_entry.grid(row=6, column=1, sticky=tk.W, pady=5)
        
        tk.Label(self.settings_window, text="ファイル名区切り:").grid(row=7, column=0, sticky=tk.W, pady=5, padx=5)
        self.separator_var = tk.StringVar()
        separator_options = ["改行", "カンマ", "タブ", "半角スペース", "バーティカルバー"]
        self.separator_combobox = ttk.Combobox(self.settings_window, textvariable=self.separator_var, values=separator_options, state="readonly")
        self.separator_combobox.grid(row=7, column=1, sticky=tk.W, pady=5)
        separator_map = {"改行": "\n", "カンマ": ",", "タブ": "\t", "半角スペース": " ", "バーティカルバー": "|"}
        current_label = next((k for k, v in separator_map.items() if v == self.temp_settings['file_separator']), "改行")
        self.separator_var.set(current_label)
        
        tk.Button(self.settings_window, text="決定", 
                 command=self.apply_settings).grid(row=8, column=0, columnspan=2, pady=10, sticky=tk.EW)

    def choose_color(self, target):
        color = colorchooser.askcolor(title=f"{target}カラーの選択")[1]
        if color:
            self.update_temp_setting(f"{target}_color", color)

    def update_temp_setting(self, key, value):
        self.temp_settings[key] = value

    def apply_settings(self):
        self.font_size = self.temp_settings['font_size']
        self.text_color = self.temp_settings['text_color']
        self.bg_color = self.temp_settings['bg_color']
        self.bg_alpha = self.temp_settings['bg_alpha']
        try:
            self.history_limit = int(self.history_limit_entry.get())
            self.temp_settings['history_limit'] = self.history_limit
            self.trim_history()
        except ValueError:
            pass
        separator_map = {"改行": "\n", "カンマ": ",", "タブ": "\t", "半角スペース": " ", "バーティカルバー": "|"}
        self.file_separator = separator_map.get(self.separator_var.get(), "\n")
        self.hotkey = self.temp_settings['hotkey']
        self.wheel_base_key = self.temp_settings['wheel_base_key']
        self.update_text()
        self.reset_display()
        self.save_settings()
        self.close_settings()

    def reset_display(self):
        if self.running:
            self.running = False
            self.clipboard_monitoring = False
            if self.text_window:
                self.text_window.destroy()
                self.text_window = None
            self.running = True
            self.clipboard_monitoring = True
            if self.clipboard_thread and not self.clipboard_thread.is_alive():
                self.clipboard_thread = Thread(target=self.monitor_clipboard, daemon=True)
                self.clipboard_thread.start()
            if self.popup_display:
                self.show_text()
            if self.history:
                self.update_from_history()

    def close_settings(self):
        if self.settings_window:
            self.settings_window.destroy()
            self.settings_window = None
            self.root.attributes('-disabled', False)

    def set_hotkey(self):
        new_hotkey = self.hotkey_entry.get().strip().lower()
        if new_hotkey:
            self.temp_settings['hotkey'] = new_hotkey
            self.hotkey_entry.delete(0, tk.END)
            self.hotkey_entry.insert(0, new_hotkey)

    def set_wheel_base(self):
        new_key = self.wheel_base_entry.get().strip()
        if new_key:
            self.temp_settings['wheel_base_key'] = new_key
            self.wheel_base_entry.delete(0, tk.END)
            self.wheel_base_entry.insert(0, self.temp_settings['wheel_base_key'])
            self.ctrl_pressed = False
            self.shift_pressed = False
            self.alt_pressed = False

    def start_input_listeners(self):
        def on_press(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = True
                elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                    self.shift_pressed = True
                elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                    self.alt_pressed = True

                # ホットキー（F1など）で cycle_display を直接呼び出し（GUIボタンと同じ動作）
                elif hasattr(key, 'name') and key.name == self.hotkey:
                    self.cycle_display()
                elif hasattr(key, 'char') and key.char and key.char.lower() == self.hotkey:
                    self.cycle_display()

                # Alt + ↑↓ で履歴移動
                elif self.alt_pressed and self.running and self.history:
                    current_time = time.time()
                    if current_time - self.last_key_time < 0.3:
                        return
                    with self.history_lock:
                        if key == keyboard.Key.up:
                            self.history_forward()
                        elif key == keyboard.Key.down:
                            self.history_backward()
                    self.last_key_time = current_time
            except AttributeError:
                pass

        def on_release(key):
            try:
                if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    self.ctrl_pressed = False
                elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    self.shift_pressed = False
                elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                    self.alt_pressed = False
            except AttributeError:
                pass

        def on_scroll(x, y, dx, dy):
            if self.running and self.history:
                current_time = time.time()
                if current_time - self.last_scroll_time < 0.3:
                    return
                wheel_keys = self.wheel_base_key.lower().split('+')
                required = {'ctrl': self.ctrl_pressed, 'shift': self.shift_pressed, 'alt': self.alt_pressed}
                if all(required.get(k, False) for k in wheel_keys if k in required):
                    with self.history_lock:
                        if dy > 0:
                            self.history_forward()
                        elif dy < 0:
                            self.history_backward()
                    self.last_scroll_time = current_time

        self.mouse_listener = mouse.Listener(on_scroll=on_scroll)
        self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def load_history(self):
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.history = [row[0] for row in reader if row]
            self.trim_history()
            if self.history:
                self.history_index = 0

    def save_history(self, content=None):
        with self.history_lock:
            if content and content not in self.history:
                self.history.insert(0, content)
                self.trim_history()
            try:
                with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for item in self.history:
                        writer.writerow([item])
            except PermissionError:
                logging.warning("Permission denied when saving history.csv")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.font_size = settings.get('font_size', self.font_size)
                    self.text_color = settings.get('text_color', self.text_color)
                    self.bg_color = settings.get('bg_color', self.bg_color)
                    self.bg_alpha = settings.get('bg_alpha', self.bg_alpha)
                    self.history_limit = settings.get('history_limit', self.history_limit)
                    self.file_separator = settings.get('file_separator', self.file_separator)
                    self.file_copy_mode = settings.get('file_copy_mode', self.file_copy_mode)
                    self.clipboard_var.set(settings.get('clipboard_enabled', True))
                    self.popup_var.set(settings.get('popup_enabled', True))
                    self.hotkey = settings.get('hotkey', "f1")  # デフォルト f1
                    self.wheel_base_key = settings.get('wheel_base_key', self.wheel_base_key)
                    self.popup_display = self.popup_var.get()
            except Exception as e:
                logging.warning(f"Failed to load settings: {e}")

    def save_settings(self):
        settings = {
            'font_size': self.font_size,
            'text_color': self.text_color,
            'bg_color': self.bg_color,
            'bg_alpha': self.bg_alpha,
            'history_limit': self.history_limit,
            'file_separator': self.file_separator,
            'file_copy_mode': self.file_copy_mode,
            'clipboard_enabled': self.clipboard_var.get(),
            'popup_enabled': self.popup_var.get(),
            'hotkey': self.hotkey,
            'wheel_base_key': self.wheel_base_key
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logging.warning(f"Failed to save settings: {e}")

    def trim_history(self):
        while len(self.history) > self.history_limit:
            self.history.pop()
        if self.history_index >= len(self.history):
            self.history_index = len(self.history) - 1 if self.history else -1

    def history_forward(self):
        if self.history and self.running:
            new_index = max(self.history_index - 1, 0)
            if new_index != self.history_index:
                self.history_index = new_index
                self.update_from_history()

    def history_backward(self):
        if self.history and self.running:
            new_index = min(self.history_index + 1, len(self.history) - 1)
            if new_index != self.history_index:
                self.history_index = new_index
                self.update_from_history()

    def update_from_history(self):
        if 0 <= self.history_index < len(self.history):
            content = self.history[self.history_index]
            self.text_entry.delete("1.0", tk.END)
            self.text_entry.insert("1.0", content)
            self.update_text()
            pyperclip.copy(content)

    def clear_history_entry(self):
        with self.history_lock:
            if self.history and 0 <= self.history_index < len(self.history):
                del self.history[self.history_index]
                if self.history:
                    self.history_index = min(self.history_index, len(self.history) - 1)
                else:
                    self.history_index = -1
                self.save_history()
        self.root.after(0, self._update_after_clear)

    def _update_after_clear(self):
        if self.history:
            self.update_from_history()
        else:
            self.text_entry.delete("1.0", tk.END)
            self.update_text()

    def get_clipboard_files(self):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                win32clipboard.CloseClipboard()
                return files
            win32clipboard.CloseClipboard()
        except Exception:
            return None
        return None

    def monitor_clipboard(self):
        last_content = pyperclip.paste() if pyperclip.paste() else ""
        while self.clipboard_monitoring:
            if not self.running:
                time.sleep(0.1)
                continue
            try:
                current_content = pyperclip.paste()
                files = self.get_clipboard_files()

                if files and files != last_content:
                    basenames = [os.path.basename(f) for f in files]
                    file_names = self.file_separator.join(basenames)
                    if self.file_copy_mode == "filename":
                        self.text_entry.delete("1.0", tk.END)
                        self.text_entry.insert("1.0", file_names)
                        self.save_history(file_names)
                        pyperclip.copy(file_names)
                    else:
                        self.text_entry.delete("1.0", tk.END)
                        self.text_entry.insert("1.0", file_names)
                        self.save_history(file_names)
                    self.root.after(0, self.update_text)
                    last_content = files
                elif current_content != last_content and isinstance(current_content, str) and current_content:
                    self.text_entry.delete("1.0", tk.END)
                    self.text_entry.insert("1.0", current_content)
                    self.save_history(current_content)
                    self.root.after(0, self.update_text)
                    last_content = current_content
            except pyperclip.PyperclipException:
                pass
            time.sleep(0.1)

    def update_text(self):
        if self.text_window and hasattr(self, 'label') and self.label and self.running:
            try:
                text = self.text_entry.get("1.0", tk.END).strip() or "クリップボード"
                self.label.config(
                    text=text,
                    font=("Arial", self.font_size),
                    fg=self.text_color,
                    bg=self.bg_color,
                    wraplength=480,
                    justify=tk.LEFT,
                    anchor=tk.W
                )
                self.text_window.attributes('-alpha', self.bg_alpha)
            except tk.TclError:
                pass

    def show_text(self):
        self.text_window = tk.Toplevel(self.root)
        self.text_window.overrideredirect(True)
        self.text_window.attributes('-topmost', True)
        
        self.label = tk.Label(self.text_window)
        self.label.pack()
        self.update_text()
        
        self.update_thread = Thread(target=self.update_position, daemon=True)
        self.update_thread.start()

    def update_position(self):
        while self.running and self.text_window:
            try:
                x, y = pyautogui.position()
                self.text_window.geometry(f"+{x+10}+{y-30}")
            except tk.TclError:
                break
            pyautogui.sleep(0.01)

    def on_closing(self):
        current_text = self.text_entry.get("1.0", tk.END).strip()
        if current_text and current_text != "クリップボード":
            self.save_history(current_text)
        self.save_settings()
        self.clipboard_monitoring = False
        self.running = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    app = MouseTextApp()