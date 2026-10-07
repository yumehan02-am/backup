import tkinter as tk
from tkinter import ttk
import pyperclip
import re
import os

def generate_html():
    image_url_base = image_url_entry.get()
    if not image_url_base:
        status_label.config(text="エラー: 画像URLは必須です。")
        return

    try:
        連番個数 = int(連番個数_spinbox.get())
        if 連番個数 <= 0:
            status_label.config(text="エラー: 連番個数には1以上の整数を入力してください。")
            return
    except ValueError:
        status_label.config(text="エラー: 連番個数には整数を入力してください。")
        return

    連番番号_input = 連番番号_entry.get()
    numbering_mode = numbering_combobox.get()

    try:
        改行個数 = int(改行個数_spinbox.get())
    except ValueError:
        status_label.config(text="エラー: 改行個数には整数を入力してください。")
        return

    width_option = width_combobox.get()
    if width_option == "指定px":
        width_value = width_entry.get()
        if not width_value:
            status_label.config(text="エラー: width(px指定)に数値を入力してください。")
            return
        try:
            int(width_value)
        except ValueError:
            status_label.config(text="エラー: width(px指定)には数値を入力してください。")
            return
        width_html = f'width="{width_value}"'
    elif width_option == "指定%":
        width_value = width_entry.get()
        if not width_value:
            status_label.config(text="エラー: width(％指定)に数値を入力してください。")
            return
        try:
            int(width_value)
        except ValueError:
            status_label.config(text="エラー: width(％指定)には数値を入力してください。")
            return
        width_html = f'width="{width_value}%"'
    elif width_option == "100%":
        width_html = 'width="100%"'
    else:  # 指定なし
        width_html = ''

    alt_text = alt_entry.get()
    alt_html = f'alt="{alt_text}"' if alt_text else ''
    border_value = border_entry.get()
    border_html = f'border="{border_value}"' if border_value else ''

    html_code = ""
    global image_urls
    image_urls = []

    if numbering_mode == "連番開始番号" and 連番番号_input:
        start_number_input_str = 連番番号_input
        match_start_number = re.search(r'(\d+)(?=[^\d]*$)', start_number_input_str)
        if match_start_number:
            start_number_prefix = start_number_input_str[:match_start_number.start(1)]
            start_number_str = match_start_number.group(1)
            try:
                start_number = int(start_number_str)
                number_format = "{:0" + str(len(start_number_str)) + "d}" if start_number_str.startswith('0') and len(start_number_str) > 1 else "{}"

                match_url_number = re.search(r'(\d+)(?=[^\d]*$)', image_url_base)
                if match_url_number:
                    base_url_prefix_for_format = image_url_base[:match_url_number.start(1)] + "{}" + image_url_base[match_url_number.end(1):]
                else:
                    filename, ext = os.path.splitext(image_url_base)
                    base_url_prefix_for_format = filename + "{}" + ext

                for i in range(連番個数):
                    current_number = start_number + i
                    current_number_str = number_format.format(current_number)
                    current_serial = start_number_prefix + current_number_str
                    current_url = base_url_prefix_for_format.format(current_serial)
                    image_urls.append(current_url)
                    img_tag_parts = ['<img src="{}"'.format(current_url)]
                    if alt_html:
                        img_tag_parts.append(" " + alt_html)
                    if width_html:
                        img_tag_parts.append(" " + width_html)
                    if border_html:
                        img_tag_parts.append(" " + border_html)

                    img_tag = ''.join(img_tag_parts) + '>'
                    br_tags = "<br>" * 改行個数
                    html_code += img_tag + br_tags + "\n"
            except ValueError:
                status_label.config(text="エラー: 連番開始番号には数字を含む連番形式の文字列を入力してください。例: sp_01")
                return
        else:
            status_label.config(text="エラー: 連番開始番号には数字を含む連番形式の文字列を入力してください。例: sp_01")
            return
    elif numbering_mode == "連番追加番号" and 連番番号_input:
        filename, ext = os.path.splitext(image_url_base)
        match = re.search(r'(\d+)(?=[^\d]*$)', 連番番号_input)
        if match:
            number_prefix = 連番番号_input[:match.start(1)]
            number_str = match.group(1)
            number_format = "{:0" + str(len(number_str)) + "d}" if number_str.startswith('0') and len(number_str) > 1 else "{}"
            start_number = int(number_str)

            for i in range(連番個数):
                current_number = start_number + i
                current_number_str = number_format.format(current_number)
                current_serial = number_prefix + current_number_str
                current_url = f"{filename}{current_serial}{ext}"
                image_urls.append(current_url)
                img_tag_parts = ['<img src="{}"'.format(current_url)]
                if alt_html:
                    img_tag_parts.append(" " + alt_html)
                if width_html:
                    img_tag_parts.append(" " + width_html)
                if border_html:
                    img_tag_parts.append(" " + border_html)

                img_tag = ''.join(img_tag_parts) + '>'
                br_tags = "<br>" * 改行個数
                html_code += img_tag + br_tags + "\n"
        else:
            status_label.config(text="エラー: 連番追加番号には数字を含む形式の文字列を入力してください。例: _01")
            return
    else:
        match = re.search(r'(\d+)(?=[^\d]*$)', image_url_base)
        if match:
            base_number_str = match.group(1)
            base_url_prefix_for_format = image_url_base[:match.start(1)] + "{}" + image_url_base[match.end(1):]
            number_format_auto = "{:0" + str(len(base_number_str)) + "d}" if base_number_str.startswith('0') and len(base_number_str) > 1 else "{}"

            for i in range(連番個数):
                current_number = int(base_number_str) + i
                current_number_str = number_format_auto.format(current_number)
                current_url = base_url_prefix_for_format.format(current_number_str)
                image_urls.append(current_url)
                img_tag_parts = ['<img src="{}"'.format(current_url)]
                if alt_html:
                    img_tag_parts.append(" " + alt_html)
                if width_html:
                    img_tag_parts.append(" " + width_html)
                if border_html:
                    img_tag_parts.append(" " + border_html)

                img_tag = ''.join(img_tag_parts) + '>'
                br_tags = "<br>" * 改行個数
                html_code += img_tag + br_tags + "\n"
        else:
            filename, ext = os.path.splitext(image_url_base)
            base_url_prefix_for_format = filename + "{:02d}" + ext

            for i in range(連番個数):
                current_number = i + 1
                current_number_str = "{:02d}".format(current_number)
                current_url = base_url_prefix_for_format.format(current_number_str)
                image_urls.append(current_url)
                img_tag_parts = ['<img src="{}"'.format(current_url)]
                if alt_html:
                    img_tag_parts.append(" " + alt_html)
                if width_html:
                    img_tag_parts.append(" " + width_html)
                if border_html:
                    img_tag_parts.append(" " + border_html)

                img_tag = ''.join(img_tag_parts) + '>'
                br_tags = "<br>" * 改行個数
                html_code += img_tag + br_tags + "\n"

    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, html_code)
    status_label.config(text="HTMLコードを生成しました。")

image_urls = []
current_url_index = [0]

def copy_next_url():
    if not image_urls:
        status_label.config(text="情報: 画像URLがありません。まずHTMLを生成してください。")
        return
    if current_url_index[0] >= len(image_urls):
        current_url_index[0] = 0
    pyperclip.copy(image_urls[current_url_index[0]])
    status_label.config(text=f"URL {image_urls[current_url_index[0]]} をクリップボードにコピーしました。")
    current_url_index[0] += 1

def copy_to_clipboard():
    html_code = output_text.get("1.0", tk.END)
    pyperclip.copy(html_code)
    status_label.config(text="HTMLコードをクリップボードにコピーしました。")

def paste_from_clipboard():
    clipboard_text = pyperclip.paste()
    image_url_entry.delete(0, tk.END)
    image_url_entry.insert(0, clipboard_text)
    status_label.config(text="画像URLをペーストしました。")

def clear_url_entry():
    image_url_entry.delete(0, tk.END)
    status_label.config(text="画像URLをクリアしました。")

def paste_alt_entry():
    clipboard_text = pyperclip.paste()
    alt_entry.delete(0, tk.END)
    alt_entry.insert(0, clipboard_text)
    status_label.config(text="altテキストをペーストしました。")

def clear_alt_entry():
    alt_entry.delete(0, tk.END)
    status_label.config(text="altテキストをクリアしました。")

def update_width_entry_state(*args):
    """widthの選択に応じて入力欄と単位ラベルを更新"""
    selected = width_combobox.get()
    if selected == "指定px":
        width_entry.config(state=tk.NORMAL)
        width_unit_label.config(text="px")
        width_unit_label.grid()
    elif selected == "指定%":
        width_entry.config(state=tk.NORMAL)
        width_unit_label.config(text="%")
        width_unit_label.grid()
    else:
        width_entry.config(state=tk.DISABLED)
        width_entry.delete(0, tk.END)
        width_unit_label.grid_remove()

def update_numbering_entry_state(*args):
    """連番モードの選択に応じて入力欄を更新"""
    selected = numbering_combobox.get()
    if selected in ["連番開始番号", "連番追加番号"]:
        連番番号_entry.config(state=tk.NORMAL)
    else:
        連番番号_entry.config(state=tk.DISABLED)
        連番番号_entry.delete(0, tk.END)

# メインウィンドウ
root = tk.Tk()
root.title("画像タグ生成ツール")

# 行と列の重み設定 (リサイズに対応)
root.grid_columnconfigure(1, weight=1)
root.grid_rowconfigure(8, weight=1)

# 画像URL
image_url_label = ttk.Label(root, text="画像URL (必須):")
image_url_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
image_url_entry = ttk.Entry(root, width=60)
image_url_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW)
paste_button = ttk.Button(root, text="ペースト", command=paste_from_clipboard)
paste_button.grid(row=0, column=4, padx=5, pady=5, sticky=tk.W)
clear_button = ttk.Button(root, text="クリア", command=clear_url_entry)
clear_button.grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)

# 連番番号
numbering_combobox = ttk.Combobox(root, values=["連番開始番号", "連番追加番号"], state="readonly", width=15)
numbering_combobox.set("連番開始番号")
numbering_combobox.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
連番番号_entry = ttk.Entry(root, width=10)
連番番号_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
numbering_combobox.bind("<<ComboboxSelected>>", update_numbering_entry_state)

# 連番個数と改行個数
serial_frame = ttk.Frame(root)
serial_frame.grid(row=2, column=0, columnspan=6, padx=(5, 0), pady=5, sticky=tk.W)
連番個数_label = ttk.Label(serial_frame, text="連番個数:")
連番個数_label.grid(row=0, column=0, padx=0, pady=5, sticky=tk.W)
連番個数_spinbox = ttk.Spinbox(serial_frame, from_=1, to=100, increment=1, width=5)
連番個数_spinbox.insert(0, "10")
連番個数_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
改行個数_label = ttk.Label(serial_frame, text="改行個数:")
改行個数_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
改行個数_spinbox = ttk.Spinbox(serial_frame, from_=0, to=10, increment=1, width=5)
改行個数_spinbox.insert(0, "2")
改行個数_spinbox.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

# width
width_label = ttk.Label(root, text="width:")
width_label.grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
width_combobox = ttk.Combobox(root, values=["100%", "指定なし", "指定px", "指定%"], state="readonly", width=10)
width_combobox.set("100%")
width_combobox.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
width_entry = ttk.Entry(root, width=5, state=tk.DISABLED)
width_entry.grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
width_unit_label = ttk.Label(root, text="")
width_unit_label.grid(row=3, column=3, padx=5, pady=5, sticky=tk.W)
width_unit_label.grid_remove()
width_combobox.bind("<<ComboboxSelected>>", update_width_entry_state)

# alt
alt_label = ttk.Label(root, text="alt:")
alt_label.grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
alt_entry = ttk.Entry(root, width=30)
alt_entry.grid(row=4, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW)
alt_paste_button = ttk.Button(root, text="ペースト", command=paste_alt_entry)
alt_paste_button.grid(row=4, column=4, padx=5, pady=5, sticky=tk.W)
alt_clear_button = ttk.Button(root, text="クリア", command=clear_alt_entry)
alt_clear_button.grid(row=4, column=5, padx=5, pady=5, sticky=tk.W)

# border
border_label = ttk.Label(root, text="border:")
border_label.grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
border_entry = ttk.Entry(root, width=5)
border_entry.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)

# HTML生成ボタン
generate_button = ttk.Button(root, text="HTML生成", command=generate_html)
generate_button.grid(row=6, column=0, columnspan=6, pady=10, sticky=tk.EW)

# 生成されたHTML表示テキストボックス
output_text_label = ttk.Label(root, text="生成されたHTML:")
output_text_label.grid(row=7, column=0, columnspan=6, sticky=tk.W, padx=5)
output_text = tk.Text(root, height=10, width=70, yscrollcommand=tk.Scrollbar.set)
output_text.grid(row=8, column=0, columnspan=5, padx=5, pady=5, sticky=tk.NSEW)
scrollbar = tk.Scrollbar(root, orient=tk.VERTICAL, command=output_text.yview)
scrollbar.grid(row=8, column=5, sticky=tk.NS, padx=0, pady=5)
output_text.config(yscrollcommand=scrollbar.set)

# コピーボタン
copy_button = ttk.Button(root, text="クリップボードにコピー", command=copy_to_clipboard)
copy_button.grid(row=9, column=0, columnspan=3, pady=10, sticky=tk.EW)
copy_url_button = ttk.Button(root, text="URLのみ順番にコピー", command=copy_next_url)
copy_url_button.grid(row=9, column=3, columnspan=3, pady=10, sticky=tk.EW)

# ステータス表示欄
status_label = ttk.Label(root, text="", wraplength=500)
status_label.grid(row=10, column=0, columnspan=6, padx=5, pady=5, sticky=tk.W)

root.mainloop()