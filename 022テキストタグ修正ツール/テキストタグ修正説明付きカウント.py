import tkinter as tk
from tkinter import ttk
import re
import pyperclip
import unicodedata

def get_char_width(char):
    # 文字の幅を判定（全角=2、半角=1）
    width = unicodedata.east_asian_width(char)
    if width in ('F', 'W'):
        return 2
    else:
        return 1

def count_chars_and_bytes(text):
    # 全角相当数と論理バイト数を計算
    byte_count = sum(get_char_width(char) for char in text)
    total_equivalent = byte_count / 2.0
    return total_equivalent, byte_count

def update_char_count(event=None):
    # 入力テキストの文字数とバイト数を更新
    input_text = input_textbox.get("1.0", tk.END).strip()
    input_equivalent, input_bytes = count_chars_and_bytes(input_text)
    input_count_label.config(text=f"全角{input_equivalent:.1f}文字（{input_bytes}バイト）")

    # 出力テキストの文字数とバイト数を更新
    output_text = output_textbox.get("1.0", tk.END).strip()
    output_equivalent, output_bytes = count_chars_and_bytes(output_text)
    output_count_label.config(text=f"全角{output_equivalent:.1f}文字（{output_bytes}バイト）")

def show_status(message, is_error=False):
    # 状況メッセージを表示（消去しない）
    status_label.config(text=message, foreground="red" if is_error else "black")

def update_br_option_state():
    # モードに応じて<br>オプションの有効/無効を切り替え
    mode = mode_var.get()
    if mode == "remove_tags":
        br_option_combobox.config(state="normal")
        # モード変更時の説明
        br_option = br_option_var.get()
        if br_option == "<br>のみ改行する":
            show_status("タグ消去モード：<br>を改行に変換、通常の改行は削除")
        elif br_option == "<br>を改行に変換":
            show_status("タグ消去モード：<br>と通常の改行を保持")
        else:
            show_status("タグ消去モード：<br>を削除、通常の改行を保持")
    else:
        br_option_combobox.config(state="disabled")
        show_status("改行タグ挿入モード：各行末に<br>を挿入")

def on_br_option_change(*args):
    # <br>オプション変更時の説明
    if mode_var.get() == "remove_tags":
        br_option = br_option_var.get()
        if br_option == "<br>のみ改行する":
            show_status("タグ消去モード：<br>を改行に変換、通常の改行は削除")
        elif br_option == "<br>を改行に変換":
            show_status("タグ消去モード：<br>と通常の改行を保持")
        else:
            show_status("タグ消去モード：<br>を削除、通常の改行を保持")

def clean_text(append=False):
    # 入力テキストを取得
    input_text = input_textbox.get("1.0", tk.END).rstrip()
    
    # 重複改行をまとめるオプション
    collapse_newlines = collapse_newlines_var.get()
    
    # モードに応じて処理
    mode = mode_var.get()
    if mode == "remove_tags":
        # タグ消去モード
        br_option = br_option_var.get()
        if br_option == "<br>のみ改行する":
            # <br>を改行に変換、通常の改行(\n)は削除
            cleaned_text = input_text
            # 通常の改行を一時的なマーカーに置き換え
            cleaned_text = re.sub(r'\n+', '\0', cleaned_text)
            # <br>を改行に変換
            cleaned_text = re.sub(r'<br\s*/?>', '\n', cleaned_text, flags=re.IGNORECASE)
            # 他のHTMLタグを削除
            cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
            # マーカーを削除して通常の改行は消去
            cleaned_text = cleaned_text.replace('\0', '')
            # 重複改行をまとめる場合
            if collapse_newlines:
                cleaned_text = re.sub(r'\n\s*\n+', '\n', cleaned_text.strip())
        elif br_option == "<br>を改行に変換":
            # <br>と通常の改行(\n)の両方を保持
            cleaned_text = re.sub(r'<br\s*/?>', '\n', input_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
            # 重複改行をまとめる場合
            if collapse_newlines:
                cleaned_text = re.sub(r'\n\s*\n+', '\n\n', cleaned_text.strip())
        else:  # <br>で改行を挿入しない
            # <br>を削除、通常の改行(\n)は保持
            cleaned_text = re.sub(r'<br\s*/?>', '', input_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
            # 重複改行をまとめる場合
            if collapse_newlines:
                cleaned_text = re.sub(r'\n\s*\n+', '\n\n', cleaned_text.strip())
    else:
        # 改行タグ挿入モード: 各行に<br>を挿入（空行含む）
        lines = input_text.split('\n')
        cleaned_text = ''
        for line in lines:
            # 空行（空白文字のみや完全な空行）にも<br>を追加
            cleaned_text += line.rstrip() + '<br>\n'
        cleaned_text = cleaned_text.rstrip('\n')
        # 重複改行をまとめるオプションがオンの場合
        if collapse_newlines:
            cleaned_text = re.sub(r'(<br>\n\s*)+', '<br>\n', cleaned_text)
    
    # 出力テキストボックスを更新
    if append and output_textbox.get("1.0", tk.END).strip():
        # 追記モード: 既存の内容に改行を加えて追記
        prefix = '<br>\n' if mode == "insert_br" else '\n\n'
        output_textbox.insert(tk.END, prefix + cleaned_text)
    else:
        # 通常モード: クリアして新規に挿入
        output_textbox.delete("1.0", tk.END)
        output_textbox.insert("1.0", cleaned_text)
    
    update_char_count()
    show_status("テキストを整形しました")

def paste_text():
    # クリップボードからテキストをペースト
    try:
        clipboard_text = pyperclip.paste()
        input_textbox.delete("1.0", tk.END)
        input_textbox.insert("1.0", clipboard_text)
        update_char_count()
        show_status("テキストをペーストしました")
    except Exception as e:
        show_status("ペーストに失敗しました: " + str(e), is_error=True)

def clear_text():
    # 入力テキストボックスをクリア
    input_textbox.delete("1.0", tk.END)
    update_char_count()
    show_status("入力テキストをクリアしました")

def copy_text():
    # 出力テキストをクリップボードにコピー
    try:
        output_text = output_textbox.get("1.0", tk.END).strip()
        pyperclip.copy(output_text)
        show_status("テキストをクリップボードにコピーしました")
    except Exception as e:
        show_status("コピーに失敗しました: " + str(e), is_error=True)

def replace_text():
    # 置換パターンと置換後の文字列を取得
    pattern = replace_pattern_entry.get()
    replacement = replace_text_entry.get()
    
    # 出力テキストを取得
    current_text = output_textbox.get("1.0", tk.END).strip()
    
    try:
        # 正規表現で置換を実行
        replaced_text = re.sub(pattern, replacement, current_text)
        
        # 出力テキストボックスを更新
        output_textbox.delete("1.0", tk.END)
        output_textbox.insert("1.0", replaced_text)
        update_char_count()
        show_status("置換を実行しました")
    except re.error:
        show_status("無効な正規表現パターンです", is_error=True)

# GUIウィンドウの作成
root = tk.Tk()
root.title("タグ消去ツール")
root.geometry("700x500")

# フレームの作成
main_frame = ttk.Frame(root, padding="10")
main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# モード選択フレーム
mode_frame = ttk.LabelFrame(main_frame, text="モード選択", padding="5")
mode_frame.grid(row=0, column=0, sticky=tk.W, pady=5)
mode_var = tk.StringVar(value="remove_tags")
ttk.Radiobutton(mode_frame, text="タグ消去モード", value="remove_tags", variable=mode_var, command=update_br_option_state).grid(row=0, column=0, padx=5)
ttk.Radiobutton(mode_frame, text="改行タグ挿入モード", value="insert_br", variable=mode_var, command=update_br_option_state).grid(row=0, column=1, padx=5)
br_option_var = tk.StringVar(value="<br>のみ改行する")  # デフォルト
br_option_combobox = ttk.Combobox(mode_frame, textvariable=br_option_var, values=["<br>のみ改行する", "<br>を改行に変換", "<br>で改行を挿入しない"], state="readonly", width=23)
br_option_combobox.grid(row=1, column=0, columnspan=2, pady=2, sticky=tk.W)
br_option_var.trace("w", on_br_option_change)  # <br>オプション変更時に説明表示
collapse_newlines_var = tk.BooleanVar(value=False)  # デフォルトでオフ
ttk.Checkbutton(mode_frame, text="重複改行をまとめる", variable=collapse_newlines_var).grid(row=2, column=0, columnspan=2, pady=2, sticky=tk.W)

# 入力テキストボックス
input_label_frame = ttk.Frame(main_frame)
input_label_frame.grid(row=1, column=0, sticky=tk.W)
input_label = ttk.Label(input_label_frame, text="整形前テキスト:")
input_label.pack(side=tk.LEFT)
input_count_label = ttk.Label(input_label_frame, text="全角0.0文字（0バイト）")
input_count_label.pack(side=tk.LEFT, padx=10)
input_textbox = tk.Text(main_frame, height=12)
input_textbox.grid(row=2, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
input_textbox.bind("<KeyRelease>", update_char_count)

# ペーストボタンとクリアボタン
button_frame = ttk.Frame(main_frame)
button_frame.grid(row=3, column=0, pady=5, sticky=tk.W)
paste_button = ttk.Button(button_frame, text="ペースト", command=paste_text)
paste_button.pack(side=tk.LEFT, padx=5)
clear_button = ttk.Button(button_frame, text="クリア", command=clear_text)
clear_button.pack(side=tk.LEFT, padx=5)

# 状況表示ラベル（行全体を白背景に）
status_frame = ttk.Frame(main_frame, style="White.TFrame")
status_frame.grid(row=4, column=0, pady=5, sticky=(tk.W, tk.E))
status_label = ttk.Label(status_frame, text="", background="white")
status_label.pack(fill=tk.X)

# 整形ボタンと整形追記ボタン
format_frame = ttk.Frame(main_frame)
format_frame.grid(row=2, column=1, pady=5)
format_button = ttk.Button(format_frame, text="整形", command=lambda: clean_text(append=False))
format_button.pack(pady=2)
append_button = ttk.Button(format_frame, text="整形追記", command=lambda: clean_text(append=True))
append_button.pack(pady=2)

# 置換機能のGUI（整形済みテキストの上に移動）
replace_frame = ttk.LabelFrame(main_frame, text="整形済みテキストの置換", padding="5")
replace_frame.grid(row=0, column=2, sticky=(tk.W, tk.E), pady=5)
ttk.Label(replace_frame, text="置換前:").grid(row=0, column=0, sticky=tk.W)
replace_pattern_entry = ttk.Entry(replace_frame)
replace_pattern_entry.grid(row=0, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))
ttk.Label(replace_frame, text="置換後:").grid(row=1, column=0, sticky=tk.W)
replace_text_entry = ttk.Entry(replace_frame)
replace_text_entry.grid(row=1, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))
replace_button = ttk.Button(replace_frame, text="置換実行", command=replace_text)
replace_button.grid(row=2, column=0, columnspan=2, pady=5)

# 出力テキストボックス
output_label_frame = ttk.Frame(main_frame)
output_label_frame.grid(row=1, column=2, sticky=tk.W)
output_label = ttk.Label(output_label_frame, text="整形済みテキスト:")
output_label.pack(side=tk.LEFT)
output_count_label = ttk.Label(output_label_frame, text="全角0.0文字（0バイト）")
output_count_label.pack(side=tk.LEFT, padx=10)
output_textbox = tk.Text(main_frame, height=12)
output_textbox.grid(row=2, column=2, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
output_textbox.bind("<KeyRelease>", update_char_count)

# コピーボタン
copy_button = ttk.Button(main_frame, text="コピー", command=copy_text)
copy_button.grid(row=3, column=2, pady=5)

# スタイル設定（白背景用）
style = ttk.Style()
style.configure("White.TFrame", background="white")

# ウィンドウとグリッドの設定
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
main_frame.columnconfigure(0, weight=1)  # 入力テキストボックスを拡縮
main_frame.columnconfigure(1, weight=0)  # 整形ボタンは固定
main_frame.columnconfigure(2, weight=1)  # 出力テキストボックスを拡縮
main_frame.rowconfigure(2, weight=1)     # テキストボックスの高さを拡縮
main_frame.rowconfigure(0, weight=0)     # モード選択と置換設定は固定
main_frame.rowconfigure(1, weight=0)     # ラベルは固定
main_frame.rowconfigure(3, weight=0)     # ペースト/クリアボタンとコピーボタンは固定
main_frame.rowconfigure(4, weight=0)     # 状況ラベルは固定
replace_frame.columnconfigure(1, weight=1)  # 置換入力欄を拡縮

# 初期状態でオプションの状態を設定
update_br_option_state()

# 初期文字数更新
update_char_count()

# メインループの開始
root.mainloop()