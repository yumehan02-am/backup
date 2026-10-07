import pyperclip
import keyboard
import time
import json
import os
import csv
from io import StringIO
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QComboBox, QPushButton, QListWidget, QListWidgetItem, QLabel, QLineEdit, QInputDialog, QDialog, QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal

HOTKEYS = [("Pause（標準）", "pause"), ("Scroll Lock", "scroll lock"), ("Insert", "insert")]
HOTKEYS += [(f"F{i}", f"f{i}") for i in range(1, 13)]
HOTKEYS += [(f"{label}+F{i}", f"{modifier}+f{i}")
            for label, modifier in (("Ctrl", "ctrl"), ("Alt", "alt"), ("Ctrl+Alt", "ctrl+alt"))
            for i in range(1, 13)]

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumWidth(470)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("始動キー："), 0, 0)
        self.hotkey_combo = QComboBox()
        for label, key in HOTKEYS:
            self.hotkey_combo.addItem(label, key)
        self.hotkey_combo.setCurrentIndex(self.hotkey_combo.findData(parent.hotkey))
        layout.addWidget(self.hotkey_combo, 0, 1)
        hint = QLabel("Shift＋始動キーで前の値に戻ります。設定は監視停止中に変更できます。")
        hint.setWordWrap(True)
        layout.addWidget(hint, 1, 0, 1, 2)
        layout.addWidget(QLabel("区切り文字の位置："), 2, 0)
        self.separator_position_combo = QComboBox()
        self.separator_position_combo.addItem("末尾に追加", "append")
        self.separator_position_combo.addItem("先頭に追加", "prepend")
        self.separator_position_combo.setCurrentIndex(self.separator_position_combo.findData(parent.separator_position))
        layout.addWidget(self.separator_position_combo, 2, 1)
        layout.addWidget(QLabel("区切り文字："), 3, 0)
        self.separator_input = QLineEdit(parent.separator)
        self.separator_input.setPlaceholderText("空欄：なし ／ 例：, または半角スペース")
        layout.addWidget(self.separator_input, 3, 1)
        self.strip_quotes_check = QCheckBox('先頭・末尾のダブルクォート（"）を削除する')
        self.strip_quotes_check.setChecked(parent.strip_quotes)
        layout.addWidget(self.strip_quotes_check, 4, 0, 1, 2)
        self.newline_check = QCheckBox("値の中の改行を <br> に置き換える")
        self.newline_check.setChecked(parent.newline_to_br)
        layout.addWidget(self.newline_check, 5, 0, 1, 2)
        note = QLabel("各項目のコピー時に、引用符の除去 → 改行変換 → 区切り文字の追加の順で処理します。元のリストは保持します。")
        note.setWordWrap(True)
        layout.addWidget(note, 6, 0, 1, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("キャンセル")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 7, 0, 1, 2)

class HotkeyThread(QThread):
    next_requested_signal = pyqtSignal()  # 次の値をコピーするためのシグナル
    back_requested_signal = pyqtSignal()  # 前の値をコピーするためのシグナル
    macro_signal = pyqtSignal()           # マクロ実行のためのシグナル
    error_signal = pyqtSignal(str)        # エラー通知のためのシグナル

    def __init__(self, hotkey, back_hotkey, mode_func, monitoring_func, macro_running_func=lambda: False):
        super().__init__()
        self.hotkey = hotkey
        self.back_hotkey = back_hotkey
        self.macro_running = macro_running_func
        self.mode = mode_func
        self.monitoring = monitoring_func
        self.running = True

    def run(self):
        while self.running and self.monitoring():
            try:
                if self.macro_running():
                    time.sleep(0.02)
                    continue
                if keyboard.is_pressed(self.back_hotkey) and self.mode() == "next":
                    self.back_requested_signal.emit()
                    self.wait_for_key_release(self.back_hotkey)
                elif keyboard.is_pressed(self.hotkey):
                    if self.mode() == "next":
                        self.next_requested_signal.emit()
                    else:  # macro
                        self.macro_signal.emit()
                    self.wait_for_key_release(self.hotkey)
                time.sleep(0.01)  # CPU負荷軽減
            except Exception as e:
                self.running = False
                self.error_signal.emit(str(e))
                break

    def wait_for_key_release(self, key):
        while self.running and self.monitoring() and keyboard.is_pressed(key):
            time.sleep(0.02)
        time.sleep(0.05)

    def stop(self):
        self.running = False

class KeyListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("マクロ入力補助")
        layout = QGridLayout()
        layout.addWidget(QLabel("キーをクリックで追加"), 0, 0, 1, 5, Qt.AlignCenter)

        keypad_layout = [
            ["ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "f2"],
            ["next", "back", "reset", ".", "."],
            ["wait:0.1", "wait:0.3", "wait:0.5", "wait:1.0", "wait:2.0"],
            [".", ".", ".", ".", "."],
            ["tab", "home", "shift+home", "pageup", "backspace"],
            ["shift+tab", "end", "shift+end", "pagedown", "delete"],
            [".", ".", ".", ".", "."],
            ["f3", "f4", "f5", "f6", "f7"],
            ["f8", "f9", "f10", "f11", "f12"],
            [".", ".", ".", ".", "."],
            ["7", "8", "9", "/", "*"],
            ["4", "5", "6", "-", "+"],
            ["1", "2", "3", "=", "enter"],
            ["0", "space", "up", ".", "."],
            [".", "left", "down", "right", "."],
            [".", ".", ".", ".", "."],
            [".", ".", "閉じる", ".", "削除"]
        ]

        for row, keys in enumerate(keypad_layout, start=1):
            for col, key in enumerate(keys):
                if key == ".":
                    layout.addWidget(QLabel(""), row, col)
                elif key == "閉じる":
                    button = QPushButton(key)
                    button.clicked.connect(self.accept)
                    layout.addWidget(button, row, col)
                elif key == "削除":
                    button = QPushButton(key)
                    button.clicked.connect(self.delete_last_key)
                    layout.addWidget(button, row, col)
                else:
                    button = QPushButton(key)
                    button.clicked.connect(lambda checked=False, k=key: self.add_key(k))
                    layout.addWidget(button, row, col)

        self.setLayout(layout)
        self.setFixedSize(460, 560)
        self.center_dialog()

    def add_key(self, key):
        self.parent().append_macro_key(key)

    def delete_last_key(self):
        self.parent().delete_last_macro_key()

    def center_dialog(self):
        parent = self.parent()
        if parent:
            parent_geo = parent.geometry()
            parent_center = parent_geo.center()
            self_geo = self.geometry()
            self_geo.moveCenter(parent_center)
            self.setGeometry(self_geo)

class ClipboardPaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = []
        self.current_index = -1
        self.order = "column_first"
        self.hotkey = "pause"  # デフォルト：Pause
        self.back_hotkey = "shift+pause"
        self.mode = "next"  # デフォルト：1行進む
        self.separator = ""  # デフォルト：なし
        self.separator_position = "append"  # デフォルト：末尾に追加
        self.strip_quotes = False
        self.newline_to_br = False
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macros.json")
        self.macro_commands = []
        self.macro_repeat_count = 1
        self.macro_interval = 0.2
        self.saved_macros = {}
        self.monitoring = False
        self.last_clipboard = ""
        self.paste_value = None
        self.macro_running = False
        self.macro_stop_requested = False
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_clipboard)
        self.hotkey_thread = None
        self.load_macros()  # 起動時にマクロ読み込み

    def initUI(self):
        self.setWindowTitle("Clipboard Paster v1.2")
        self.setGeometry(100, 100, 600, 500)
        
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QGridLayout()

        # リスト順
        layout.addWidget(QLabel("リスト順："), 0, 0)
        self.order_combo = QComboBox()
        self.order_combo.addItem("上から下、左から右", "column_first")
        self.order_combo.addItem("左から右、上から下", "row_first")
        self.order_combo.addItem("左下から上、左から右", "column_last_to_first")
        self.order_combo.addItem("左下から右、下から上", "row_last_to_first")
        self.order_combo.currentIndexChanged.connect(self.change_order)
        layout.addWidget(self.order_combo, 0, 1)

        # 始動キーの動作
        layout.addWidget(QLabel("始動キーの動作："), 1, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("1行進む", "next")
        self.mode_combo.addItem("マクロスタート", "macro")
        self.mode_combo.currentIndexChanged.connect(self.change_mode)
        layout.addWidget(self.mode_combo, 1, 1)

        # キーマクロ
        layout.addWidget(QLabel("キーマクロ（コンマ区切り）："), 4, 0)
        self.macro_input = QLineEdit()
        self.macro_input.setPlaceholderText("例: ctrl+c,next,ctrl+v,enter,back")
        self.macro_input.textChanged.connect(self.update_macro_commands)
        layout.addWidget(self.macro_input, 4, 1)

        # マクロ繰り返し回数
        layout.addWidget(QLabel("マクロ繰り返し回数："), 5, 0)
        self.macro_repeat_spin = QSpinBox()
        self.macro_repeat_spin.setRange(1, 100)
        self.macro_repeat_spin.setValue(self.macro_repeat_count)
        self.macro_repeat_spin.valueChanged.connect(self.change_macro_repeat_count)
        layout.addWidget(self.macro_repeat_spin, 5, 1)

        # マクロ実行間隔
        layout.addWidget(QLabel("キー操作間隔："), 6, 0)
        self.macro_interval_spin = QDoubleSpinBox()
        self.macro_interval_spin.setRange(0.05, 5.0)
        self.macro_interval_spin.setSingleStep(0.05)
        self.macro_interval_spin.setDecimals(2)
        self.macro_interval_spin.setSuffix(" 秒")
        self.macro_interval_spin.setValue(self.macro_interval)
        self.macro_interval_spin.valueChanged.connect(self.change_macro_interval)
        layout.addWidget(self.macro_interval_spin, 6, 1)

        # 保存マクロ
        layout.addWidget(QLabel("保存マクロ："), 7, 0)
        self.macro_select_combo = QComboBox()
        self.macro_select_combo.addItem("選択...", "")
        self.macro_select_combo.currentIndexChanged.connect(self.load_selected_macro)
        layout.addWidget(self.macro_select_combo, 7, 1)

        # マクロ入力補助
        self.available_keys_button = QPushButton("マクロ入力補助")
        self.available_keys_button.clicked.connect(self.show_available_keys)
        layout.addWidget(self.available_keys_button, 8, 0)

        # マクロ保存ボタン
        self.save_macro_button = QPushButton("保存")
        self.save_macro_button.clicked.connect(self.save_macro)
        layout.addWidget(self.save_macro_button, 8, 1)

        # クリップボード内容
        self.clipboard_label = QLabel("クリップボード: (未取得)")
        self.clipboard_label.setWordWrap(True)
        layout.addWidget(self.clipboard_label, 9, 0, 1, 2)

        # 現在位置
        self.position_label = QLabel("現在位置: - / -")
        layout.addWidget(self.position_label, 10, 0, 1, 2)

        # ペースト候補リスト
        self.paste_list = QListWidget()
        self.paste_list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.paste_list, 11, 0, 1, 2)

        # ボタン
        self.reset_button = QPushButton("リセット")
        self.reset_button.clicked.connect(self.reset_data)
        self.reset_button.setEnabled(False)
        layout.addWidget(self.reset_button, 12, 0)

        self.start_button = QPushButton("開始")
        self.start_button.clicked.connect(self.toggle_monitoring)
        layout.addWidget(self.start_button, 12, 1)

        self.settings_button = QPushButton("設定")
        self.settings_button.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_button, 13, 0)
        self.hotkey_label = QLabel()
        layout.addWidget(self.hotkey_label, 13, 1)
        self.update_hotkey_label()

        widget.setLayout(layout)

    def show_available_keys(self):
        dialog = KeyListDialog(self)
        dialog.exec_()

    def append_macro_key(self, key):
        current_text = self.macro_input.text().strip()
        if current_text:
            self.macro_input.setText(f"{current_text},{key}")
        else:
            self.macro_input.setText(key)
        self.update_macro_commands()

    def delete_last_macro_key(self):
        current_text = self.macro_input.text().strip()
        if not current_text:
            return
        keys = [key.strip() for key in current_text.split(",") if key.strip()]
        if keys:
            keys.pop()
        self.macro_input.setText(",".join(keys))
        self.update_macro_commands()

    def center_dialog(self, dialog):
        parent_geo = self.geometry()
        parent_center = parent_geo.center()
        dialog_geo = dialog.geometry()
        dialog_geo.moveCenter(parent_center)
        dialog.setGeometry(dialog_geo)

    def load_macros(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    hotkey = data.get("hotkey", "pause")
                    self.hotkey = hotkey if hotkey in dict(HOTKEYS).values() else "pause"
                    self.back_hotkey = f"shift+{self.hotkey}"
                    self.separator = str(data.get("separator", ""))
                    position = data.get("separator_position", "append")
                    self.separator_position = position if position in ("append", "prepend") else "append"
                    self.strip_quotes = data.get("strip_quotes", False) is True
                    self.newline_to_br = data.get("newline_to_br", False) is True
                    self.update_hotkey_label()
                    self.saved_macros = data.get("macros", {})
                    last_used = data.get("last_used", "")
                    if last_used:
                        self.macro_input.setText(last_used)
                        self.update_macro_commands()
                    self.macro_repeat_count = int(data.get("macro_repeat_count", 1))
                    self.macro_interval = float(data.get("macro_interval", 0.2))
                    self.macro_repeat_spin.setValue(self.macro_repeat_count)
                    self.macro_interval_spin.setValue(self.macro_interval)
                self.macro_select_combo.clear()
                self.macro_select_combo.addItem("選択...", "")
                for name in self.saved_macros:
                    self.macro_select_combo.addItem(name, name)
        except Exception as e:
            self.clipboard_label.setText(f"マクロ読み込みエラー: {str(e)}")

    def save_macros(self):
        try:
            data = {
                "hotkey": self.hotkey,
                "separator": self.separator,
                "separator_position": self.separator_position,
                "strip_quotes": self.strip_quotes,
                "newline_to_br": self.newline_to_br,
                "last_used": self.macro_input.text().strip(),
                "macro_repeat_count": self.macro_repeat_count,
                "macro_interval": self.macro_interval,
                "macros": self.saved_macros
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.clipboard_label.setText(f"マクロ保存エラー: {str(e)}")

    def save_macro(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("マクロ保存")
        dialog.setLabelText("マクロ名を入力してください:")
        self.center_dialog(dialog)
        name, ok = dialog.getText(self, "マクロ保存", "マクロ名を入力してください:")
        if ok and name.strip():
            if name in self.saved_macros:
                self.clipboard_label.setText(f"エラー: マクロ名 '{name}' は既に存在します")
                return
            if not self.macro_input.text().strip():
                self.clipboard_label.setText("エラー: マクロ内容が空です")
                return
            self.saved_macros[name] = {
                "commands": self.macro_input.text().strip(),
                "repeat_count": self.macro_repeat_count,
                "interval": self.macro_interval
            }
            self.save_macros()
            self.macro_select_combo.addItem(name, name)
            self.clipboard_label.setText(f"マクロ '{name}' を保存しました")
        elif ok:
            self.clipboard_label.setText("エラー: マクロ名が空です")

    def load_selected_macro(self):
        name = self.macro_select_combo.currentData()
        if name and name in self.saved_macros:
            macro = self.saved_macros[name]
            if isinstance(macro, dict):
                self.macro_input.setText(macro.get("commands", ""))
                self.macro_repeat_spin.setValue(int(macro.get("repeat_count", 1)))
                self.macro_interval_spin.setValue(float(macro.get("interval", 0.2)))
            else:
                self.macro_input.setText(macro)
            self.update_macro_commands()
            self.clipboard_label.setText(f"マクロ '{name}' を読み込みました")

    def change_order(self):
        self.order = self.order_combo.currentData()
        self.current_index = -1
        self.update_paste_list()

    def change_mode(self):
        self.mode = self.mode_combo.currentData()

    def update_hotkey_label(self):
        label = next(label for label, key in HOTKEYS if key == self.hotkey)
        self.hotkey_label.setText(f"始動: {label} ／ 戻る: Shift+{label}")

    def show_settings(self):
        if self.monitoring:
            return
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.hotkey = dialog.hotkey_combo.currentData()
            self.back_hotkey = f"shift+{self.hotkey}"
            self.separator = dialog.separator_input.text()
            self.separator_position = dialog.separator_position_combo.currentData()
            self.strip_quotes = dialog.strip_quotes_check.isChecked()
            self.newline_to_br = dialog.newline_check.isChecked()
            self.update_hotkey_label()
            self.save_macros()

    def format_copy_value(self, value):
        if self.strip_quotes:
            if value.startswith('"'):
                value = value[1:]
            if value.endswith('"'):
                value = value[:-1]
        if self.newline_to_br:
            value = value.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')
        if self.separator:
            if self.separator_position == "append":
                value += self.separator
            else:
                value = self.separator + value
        return value

    def change_macro_repeat_count(self):
        self.macro_repeat_count = self.macro_repeat_spin.value()

    def change_macro_interval(self):
        self.macro_interval = self.macro_interval_spin.value()

    def update_macro_commands(self):
        text = self.macro_input.text().strip()
        if text:
            self.macro_commands = [cmd.strip() for cmd in text.split(",") if cmd.strip()]
        else:
            self.macro_commands = []

    def toggle_monitoring(self):
        if self.monitoring:
            # 監視停止
            try:
                self.monitoring = False
                self.settings_button.setEnabled(True)
                self.start_button.setText("開始")
                self.start_button.setStyleSheet("")  # デフォルトカラー
                self.reset_button.setEnabled(False)
                self.timer.stop()
                self.clipboard_label.setText("監視停止")
                if self.hotkey_thread:
                    self.hotkey_thread.stop()
                    self.hotkey_thread.quit()
                    self.hotkey_thread.wait(1000)  # 位置引数として1000ms
                    self.hotkey_thread = None
                self.save_macros()
            except Exception as e:
                self.clipboard_label.setText(f"監視停止エラー: {str(e)}")
        else:
            # 監視開始
            try:
                self.monitoring = True
                self.settings_button.setEnabled(False)
                self.start_button.setText("監視中")
                self.start_button.setStyleSheet("background-color: #77ff77")
                self.reset_button.setEnabled(True)
                self.timer.start(1000)
                self.hotkey_thread = HotkeyThread(
                    self.hotkey, self.back_hotkey, lambda: self.mode, lambda: self.monitoring,
                    lambda: self.macro_running
                )
                self.hotkey_thread.next_requested_signal.connect(self.handle_next_requested)
                self.hotkey_thread.back_requested_signal.connect(self.handle_back_requested)
                self.hotkey_thread.macro_signal.connect(self.run_macro_internal)
                self.hotkey_thread.error_signal.connect(self.handle_hotkey_error)
                self.hotkey_thread.start()
                self.clipboard_label.setText("監視開始")
            except Exception as e:
                self.monitoring = False
                self.settings_button.setEnabled(True)
                self.start_button.setText("開始")
                self.start_button.setStyleSheet("")
                self.reset_button.setEnabled(False)
                self.timer.stop()
                self.clipboard_label.setText(f"監視開始エラー: {str(e)}")

    def handle_next_requested(self):
        value = self.get_next_value_internal()
        if value is not None:
            self.copy_next_value(value)
        self.update_paste_list()

    def handle_back_requested(self):
        value = self.get_back_value_internal()
        if value is not None:
            self.copy_back_value(value)
        self.update_paste_list()

    def handle_hotkey_error(self, message):
        self.clipboard_label.setText(f"ホットキー監視エラー: {message}")
        if self.monitoring:
            self.toggle_monitoring()

    def check_clipboard(self):
        if not self.monitoring or self.data:
            return
        try:
            clipboard = pyperclip.paste()
            if clipboard != self.last_clipboard and clipboard != self.paste_value:
                self.last_clipboard = clipboard
                self.clipboard_label.setText(f"クリップボード: {clipboard[:100]}...")
                self.parse_clipboard(clipboard)
        except Exception as e:
            self.clipboard_label.setText(f"クリップボード: アクセスエラー ({str(e)})")

    def parse_clipboard(self, text):
        try:
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            if not text.strip():
                return
            data = []
            reader = csv.reader(StringIO(text), delimiter='\t')
            for row in reader:
                row = [cell.strip('\t') for cell in row if cell.strip()]
                if row:
                    data.append(row)
            if data:
                self.data = data
                self.current_index = 0  # 最初の項目にフォーカス
                self.update_paste_list()
                indices = []
                rows, cols = len(self.data), max(len(row) for row in self.data)
                if self.order == "column_first":
                    for j in range(cols):
                        for i in range(rows):
                            if j < len(self.data[i]):
                                indices.append((i, j))
                elif self.order == "row_first":
                    for i in range(rows):
                        for j in range(cols):
                            if j < len(self.data[i]):
                                indices.append((i, j))
                elif self.order == "column_last_to_first":
                    for j in range(cols):
                        for i in range(rows-1, -1, -1):
                            if j < len(self.data[i]):
                                indices.append((i, j))
                elif self.order == "row_last_to_first":
                    for i in range(rows-1, -1, -1):
                        for j in range(cols):
                            if j < len(self.data[i]):
                                indices.append((i, j))
                if indices:
                    i, j = indices[0]
                    value = self.data[i][j]
                    self.copy_next_value(value)
                self.update_position_label()
                self.timer.stop()
        except Exception as e:
            self.clipboard_label.setText(f"クリップボード: 解析エラー ({str(e)})")
            self.paste_list.clear()

    def reset_data(self):
        try:
            self.data = []
            self.current_index = -1
            self.paste_list.clear()
            self.clipboard_label.setText("クリップボード: (未取得)")
            self.update_position_label()
            if self.monitoring:
                self.timer.start(1000)
        except Exception as e:
            self.clipboard_label.setText(f"リセットエラー: {str(e)}")

    def update_paste_list(self):
        try:
            self.paste_list.clear()
            if not self.data:
                self.update_position_label()
                return
            indices = []
            rows, cols = len(self.data), max(len(row) for row in self.data)
            if self.order == "column_first":
                for j in range(cols):
                    for i in range(rows):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_first":
                for i in range(rows):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "column_last_to_first":
                for j in range(cols):
                    for i in range(rows-1, -1, -1):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_last_to_first":
                for i in range(rows-1, -1, -1):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            
            for idx, (i, j) in enumerate(indices):
                item = QListWidgetItem(f"{self.data[i][j]} (行{i+1}, 列{j+1})")
                if idx == self.current_index:
                    item.setBackground(Qt.yellow)
                self.paste_list.addItem(item)
            self.update_position_label()
        except Exception as e:
            self.clipboard_label.setText(f"リスト更新エラー: {str(e)}")

    def update_position_label(self):
        try:
            total = len(self.build_indices())
            if total and 0 <= self.current_index < total:
                self.position_label.setText(f"現在位置: {self.current_index + 1} / {total}")
            elif total:
                self.position_label.setText(f"現在位置: - / {total}")
            else:
                self.position_label.setText("現在位置: - / -")
        except Exception:
            self.position_label.setText("現在位置: - / -")

    def get_next_value_internal(self):
        try:
            if not self.data:
                return None
            indices = []
            rows, cols = len(self.data), max(len(row) for row in self.data)
            if self.order == "column_first":
                for j in range(cols):
                    for i in range(rows):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_first":
                for i in range(rows):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "column_last_to_first":
                for j in range(cols):
                    for i in range(rows-1, -1, -1):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_last_to_first":
                for i in range(rows-1, -1, -1):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            
            self.current_index += 1
            if self.current_index >= len(indices):
                self.current_index = 0
            i, j = indices[self.current_index]
            return self.data[i][j]
        except Exception as e:
            self.clipboard_label.setText(f"次値取得エラー: {str(e)}")
            return None

    def get_back_value_internal(self):
        try:
            if not self.data:
                return None
            indices = []
            rows, cols = len(self.data), max(len(row) for row in self.data)
            if self.order == "column_first":
                for j in range(cols):
                    for i in range(rows):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_first":
                for i in range(rows):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "column_last_to_first":
                for j in range(cols):
                    for i in range(rows-1, -1, -1):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_last_to_first":
                for i in range(rows-1, -1, -1):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            
            self.current_index -= 1
            if self.current_index < 0:
                self.current_index = len(indices) - 1
            i, j = indices[self.current_index]
            return self.data[i][j]
        except Exception as e:
            self.clipboard_label.setText(f"前値取得エラー: {str(e)}")
            return None

    def on_item_clicked(self, item):
        try:
            if not self.data:
                return
            index = self.paste_list.row(item)
            self.current_index = index
            self.update_paste_list()
            indices = []
            rows, cols = len(self.data), max(len(row) for row in self.data)
            if self.order == "column_first":
                for j in range(cols):
                    for i in range(rows):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_first":
                for i in range(rows):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "column_last_to_first":
                for j in range(cols):
                    for i in range(rows-1, -1, -1):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            elif self.order == "row_last_to_first":
                for i in range(rows-1, -1, -1):
                    for j in range(cols):
                        if j < len(self.data[i]):
                            indices.append((i, j))
            
            if index < len(indices):
                i, j = indices[index]
                value = self.data[i][j]
                value = self.format_copy_value(value)
                self.paste_value = value
                pyperclip.copy(value)
                self.clipboard_label.setText(f"クリップボード: {value[:100]}...")
        except Exception as e:
            self.clipboard_label.setText(f"リストクリックエラー: {str(e)}")

    def copy_next_value(self, value):
        try:
            value = self.format_copy_value(value)
            self.paste_value = value
            pyperclip.copy(value)
            self.clipboard_label.setText(f"クリップボード: {value[:100]}...")
            time.sleep(0.2)
        except Exception as e:
            self.clipboard_label.setText(f"コピーエラー: {str(e)}")

    def copy_back_value(self, value):
        try:
            value = self.format_copy_value(value)
            self.paste_value = value
            pyperclip.copy(value)
            self.clipboard_label.setText(f"クリップボード: {value[:100]}...")
            time.sleep(0.2)
        except Exception as e:
            self.clipboard_label.setText(f"コピーエラー: {str(e)}")

    def run_macro_internal(self):
        if self.macro_running:
            return
        self.macro_running = True
        self.macro_stop_requested = False
        valid_keys = {
            'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'tab', 'shift+tab', 'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+a',
            'end', 'shift+end', 'home', 'shift+home',
            'up', 'down', 'left', 'right', 'space', 'enter',
            'backspace', 'delete', 'pageup', 'pagedown',
            '*', '+', '-', '/', '=',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
            'next', 'back', 'reset'
        }
        key_aliases = {
            'pageup': 'page up',
            'pagedown': 'page down'
        }
        try:
            indices = self.build_indices()

            if not self.macro_commands:
                self.clipboard_label.setText("マクロが空です")
                return

            for repeat_index in range(self.macro_repeat_count):
                if self.should_stop_macro():
                    break
                for cmd in self.macro_commands:
                    cmd = cmd.lower()
                    if self.should_stop_macro():
                        break
                    if cmd.startswith('wait:'):
                        if not self.run_wait_command(cmd):
                            break
                        continue
                    if cmd == 'next' and indices:
                        if 0 <= self.current_index < len(indices):
                            i, j = indices[self.current_index]
                            value = self.data[i][j]
                            self.copy_next_value(value)
                        self.current_index += 1
                        if self.current_index >= len(indices):
                            self.current_index = 0
                        self.update_paste_list()
                    elif cmd == 'back' and indices:
                        if 0 <= self.current_index < len(indices):
                            i, j = indices[self.current_index]
                            value = self.data[i][j]
                            self.copy_back_value(value)
                        self.current_index -= 1
                        if self.current_index < 0:
                            self.current_index = len(indices) - 1
                        self.update_paste_list()
                    elif cmd == 'reset':
                        self.reset_data()
                        indices = self.build_indices()
                    elif cmd in valid_keys:
                        try:
                            keyboard.press_and_release(key_aliases.get(cmd, cmd))
                        except Exception as e:
                            self.clipboard_label.setText(f"マクロエラー: {str(e)}")
                    else:
                        self.clipboard_label.setText(f"無効なマクロキー: {cmd}")
                        self.macro_stop_requested = True
                    if not self.sleep_with_stop(self.macro_interval):
                        break
                if self.macro_stop_requested:
                    break
                self.clipboard_label.setText(f"マクロ実行中: {repeat_index + 1} / {self.macro_repeat_count}")
            if self.macro_stop_requested:
                self.clipboard_label.setText("マクロ停止: Esc")
            else:
                self.clipboard_label.setText("マクロ完了")
        except Exception as e:
            self.clipboard_label.setText(f"マクロ実行エラー: {str(e)}")
        finally:
            self.macro_running = False

    def should_stop_macro(self):
        if not self.monitoring:
            return True
        if keyboard.is_pressed('esc'):
            self.macro_stop_requested = True
            return True
        return self.macro_stop_requested

    def sleep_with_stop(self, seconds):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.should_stop_macro():
                return False
            time.sleep(0.02)
        return True

    def run_wait_command(self, cmd):
        try:
            seconds = float(cmd.split(":", 1)[1])
            if seconds < 0:
                raise ValueError
            if seconds > 30:
                seconds = 30
            return self.sleep_with_stop(seconds)
        except ValueError:
            self.clipboard_label.setText(f"無効な待機コマンド: {cmd}")
            self.macro_stop_requested = True
            return False

    def build_indices(self):
        indices = []
        if not self.data:
            return indices
        rows, cols = len(self.data), max(len(row) for row in self.data)
        if self.order == "column_first":
            for j in range(cols):
                for i in range(rows):
                    if j < len(self.data[i]):
                        indices.append((i, j))
        elif self.order == "row_first":
            for i in range(rows):
                for j in range(cols):
                    if j < len(self.data[i]):
                        indices.append((i, j))
        elif self.order == "column_last_to_first":
            for j in range(cols):
                for i in range(rows-1, -1, -1):
                    if j < len(self.data[i]):
                        indices.append((i, j))
        elif self.order == "row_last_to_first":
            for i in range(rows-1, -1, -1):
                for j in range(cols):
                    if j < len(self.data[i]):
                        indices.append((i, j))
        return indices

    def closeEvent(self, event):
        try:
            self.monitoring = False
            self.timer.stop()
            if self.hotkey_thread:
                self.hotkey_thread.stop()
                self.hotkey_thread.quit()
                self.hotkey_thread.wait(1000)
                self.hotkey_thread = None
            self.save_macros()
        finally:
            event.accept()

def main():
    app = QApplication([])
    window = ClipboardPaster()
    window.show()
    app.exec_()

if __name__ == "__main__":
    main()
