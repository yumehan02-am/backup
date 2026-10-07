import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import pyperclip
import unicodedata
import json
import os
import csv

# グローバル変数でセクションごとの行数を保持
section_lengths = []

def get_char_width(char):
    width = unicodedata.east_asian_width(char)
    return 2 if width in ('F', 'W') else 1

def count_chars_and_bytes(text):
    byte_count = sum(get_char_width(char) for char in text)
    total_equivalent = byte_count / 2.0
    return total_equivalent, byte_count

def update_char_count(event=None):
    input_text = input_textbox.get("1.0", tk.END).strip()
    input_equivalent, input_bytes = count_chars_and_bytes(input_text)
    input_count_label.config(text=f"全角{input_equivalent:.1f}文字（{input_bytes}バイト）")

    output_text = output_textbox.get("1.0", tk.END).strip()
    output_equivalent, output_bytes = count_chars_and_bytes(output_text)
    output_count_label.config(text=f"全角{output_equivalent:.1f}文字（{output_bytes}バイト）")

def show_status(message, is_error=False):
    status_label.config(text=message, foreground="red" if is_error else "black")

def save_settings():
    name = settings_name_entry.get().strip()
    if not name:
        show_status("設定名を入力してください", is_error=True)
        return
    settings = {
        "mode": mode_var.get(),
        "trigger1": trigger1_entry.get(),
        "trigger2": trigger2_entry.get(),
        "continuous": continuous_var.get(),
        "delimiter_lines": delimiter_var.get(),
        "include_triggers": include_triggers_var.get()
    }
    try:
        try:
            with open("settings.json", "r") as f:
                all_settings = json.load(f)
        except FileNotFoundError:
            all_settings = {}
        all_settings[name] = settings
        with open("settings.json", "w") as f:
            json.dump(all_settings, f, indent=2)
        update_settings_dropdown()
        show_status(f"設定 '{name}' を保存しました")
    except Exception as e:
        show_status(f"保存に失敗しました: {str(e)}", is_error=True)

def delete_settings():
    name = settings_var.get()
    if not name:
        show_status("削除する設定を選択してください", is_error=True)
        return
    try:
        with open("settings.json", "r") as f:
            all_settings = json.load(f)
        if name in all_settings:
            del all_settings[name]
            with open("settings.json", "w") as f:
                json.dump(all_settings, f, indent=2)
            update_settings_dropdown()
            settings_var.set("")
            mode_var.set("削除←保持→削除")
            trigger1_entry.delete(0, tk.END)
            trigger2_entry.delete(0, tk.END)
            continuous_var.set(True)
            include_triggers_var.set(True)
            delimiter_var.set("1")
            show_status(f"設定 '{name}' を削除しました")
    except Exception as e:
        show_status(f"削除に失敗しました: {str(e)}", is_error=True)

def load_settings(*args):
    name = settings_var.get()
    if not name:
        return
    try:
        with open("settings.json", "r") as f:
            all_settings = json.load(f)
        if name in all_settings:
            settings = all_settings[name]
            mode_var.set(settings["mode"])
            trigger1_entry.delete(0, tk.END)
            trigger1_entry.insert(0, settings["trigger1"])
            trigger2_entry.delete(0, tk.END)
            trigger2_entry.insert(0, settings["trigger2"])
            continuous_var.set(settings["continuous"])
            delimiter_var.set(settings["delimiter_lines"])
            include_triggers_var.set(settings.get("include_triggers", True))
            show_status(f"設定 '{name}' を読み込みました")
    except Exception as e:
        show_status(f"読み込みに失敗しました: {str(e)}", is_error=True)

def update_settings_dropdown():
    try:
        with open("settings.json", "r") as f:
            all_settings = json.load(f)
        settings_dropdown['values'] = list(all_settings.keys())
    except FileNotFoundError:
        settings_dropdown['values'] = []

def update_labels(*args):
    trigger1_label.config(text="開始トリガー:")
    trigger2_label.config(text="終了トリガー:")

def clean_text(append=False):
    global section_lengths
    input_text = input_textbox.get("1.0", tk.END).rstrip()
    mode = mode_var.get()
    trigger1 = trigger1_entry.get()
    trigger2 = trigger2_entry.get()
    continuous = continuous_var.get()
    include_triggers = include_triggers_var.get()  # True: トリガー行を削除（デフォルト）, False: トリガー行を保持
    delimiter_lines = int(delimiter_var.get())

    if not trigger1 and not trigger2:
        show_status("削除条件を指定してください", is_error=True)
        return

    lines = input_text.split('\n')
    sections = []
    section_lengths.clear()  # セッションごとにリセット
    i = 0
    found = False

    is_keep_middle = (mode == "削除←保持→削除")
    start_trigger = trigger1 if is_keep_middle else trigger2
    end_trigger = trigger2 if is_keep_middle else trigger1
    first_trigger = trigger1
    second_trigger = trigger2

    if is_keep_middle:
        # 中央部分を残す
        while i < len(lines):
            if first_trigger in lines[i]:
                found = True
                start = i if not include_triggers else i + 1  # include_triggers=False で開始トリガー行を保持
                if continuous:
                    while i < len(lines) and first_trigger in lines[i]:
                        i += 1
                else:
                    i += 1
                while i < len(lines) and (not second_trigger or second_trigger not in lines[i]):
                    i += 1
                end = i + 1 if not include_triggers and second_trigger and i < len(lines) and second_trigger in lines[i] else i  # include_triggers=False で終了トリガー行を保持
                if start < end:
                    sections.append('\n'.join(lines[start:end]))
                    section_lengths.append(end - start)
                if not continuous:
                    break
            else:
                i += 1
    else:
        # 中央部分を削除
        start = 0
        while i < len(lines):
            if first_trigger in lines[i]:
                found = True
                end_part1 = i + 1 if not include_triggers else i  # include_triggers=False で開始トリガー行を保持
                if start < end_part1:
                    sections.append('\n'.join(lines[start:end_part1]))
                    section_lengths.append(end_part1 - start)
                if continuous:
                    while i < len(lines) and first_trigger in lines[i]:
                        i += 1
                else:
                    i += 1
                while i < len(lines) and (not second_trigger or second_trigger not in lines[i]):
                    i += 1
                if i >= len(lines):
                    break
                if continuous:
                    while i < len(lines) and second_trigger in lines[i]:
                        i += 1
                else:
                    i += 1
                start = i if not include_triggers or not second_trigger or i >= len(lines) or second_trigger not in lines[i] else i + 1  # include_triggers=False で終了トリガー行を保持
                if not continuous:
                    if start < len(lines):
                        sections.append('\n'.join(lines[start:]))
                        section_lengths.append(len(lines) - start)
                    break
            else:
                i += 1
        if start < len(lines):
            sections.append('\n'.join(lines[start:]))
            section_lengths.append(len(lines) - start)

    if not found and not continuous:
        sections = ['\n'.join(lines)]
        section_lengths = [len(lines)]

    if delimiter_lines == 0:
        separator = '\n'
    else:
        separator = '\n' * (delimiter_lines + 1)
    cleaned_text = separator.join(section for section in sections if section.strip() or delimiter_lines > 0).rstrip()

    if append and output_textbox.get("1.0", tk.END).strip():
        output_textbox.insert(tk.END, '\n\n' + cleaned_text)
    else:
        output_textbox.delete("1.0", tk.END)
        output_textbox.insert("1.0", cleaned_text)

    update_char_count()
    show_status("テキストを整形しました")

def replace_text():
    pattern = replace_pattern_entry.get()
    replacement = replace_text_entry.get()
    current_text = output_textbox.get("1.0", tk.END).strip()
    
    try:
        replaced_text = re.sub(pattern, replacement, current_text)
        output_textbox.delete("1.0", tk.END)
        output_textbox.insert("1.0", replaced_text)
        update_char_count()
        show_status("置換を実行しました")
    except re.error:
        show_status("無効な正規表現パターンです", is_error=True)

def newline_to_tab():
    global section_lengths
    delimiter_lines = int(delimiter_var.get())
    continuous = continuous_var.get()
    mode = mode_var.get()
    trigger1 = trigger1_entry.get()
    trigger2 = trigger2_entry.get()
    current_text = output_textbox.get("1.0", tk.END).rstrip()
    
    if delimiter_lines == 0:
        if continuous:
            output_lines = current_text.split('\n')
            total_lines = len([line for line in output_lines if line.strip()])
            expected_lines = sum(section_lengths) if section_lengths else 0
            if section_lengths and expected_lines == total_lines:
                sections = []
                current_index = 0
                for length in section_lengths:
                    if current_index < len(output_lines):
                        section = output_lines[current_index:current_index + length]
                        sections.append('\n'.join(section))
                        current_index += length
            else:
                input_text = input_textbox.get("1.0", tk.END).rstrip()
                input_lines = input_text.split('\n')
                section_lengths.clear()
                sections = []
                current_index = 0
                i = 0
                found = False

                is_keep_middle = (mode == "削除←保持→削除")
                start_trigger = trigger1 if is_keep_middle else trigger2
                end_trigger = trigger2 if is_keep_middle else trigger1
                first_trigger = trigger1
                second_trigger = trigger2

                if is_keep_middle:
                    while i < len(input_lines):
                        if first_trigger in input_lines[i]:
                            found = True
                            if continuous:
                                while i < len(input_lines) and first_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            start = i
                            while i < len(input_lines) and (not second_trigger or second_trigger not in input_lines[i]):
                                i += 1
                            end = i if second_trigger else len(input_lines)
                            if start < end:
                                section_lengths.append(end - start)
                                if current_index < len(output_lines):
                                    section = output_lines[current_index:current_index + (end - start)]
                                    sections.append('\n'.join(section))
                                    current_index += (end - start)
                            if not continuous:
                                break
                        else:
                            i += 1
                else:
                    start = 0
                    while i < len(input_lines):
                        if first_trigger in input_lines[i]:
                            found = True
                            end_part1 = i
                            if start < end_part1:
                                section_lengths.append(end_part1 - start)
                                if current_index < len(output_lines):
                                    section = output_lines[current_index:current_index + (end_part1 - start)]
                                    sections.append('\n'.join(section))
                                    current_index += (end_part1 - start)
                            if continuous:
                                while i < len(input_lines) and first_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            while i < len(input_lines) and (not second_trigger or second_trigger not in input_lines[i]):
                                i += 1
                            if i >= len(input_lines):
                                break
                            if continuous:
                                while i < len(input_lines) and second_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            start = i
                            if not continuous:
                                if start < len(input_lines):
                                    section_lengths.append(len(input_lines) - start)
                                    if current_index < len(output_lines):
                                        section = output_lines[current_index:current_index + (len(input_lines) - start)]
                                        sections.append('\n'.join(section))
                                        current_index += (len(input_lines) - start)
                                break
                        else:
                            i += 1
                    if start < len(input_lines):
                        section_lengths.append(len(input_lines) - start)
                        if current_index < len(output_lines):
                            section = output_lines[current_index:current_index + (len(input_lines) - start)]
                            sections.append('\n'.join(section))
                            current_index += (len(input_lines) - start)

                if not found and not continuous:
                    section_lengths = [len(output_lines)]
                    sections = ['\n'.join(output_lines)]

            converted_sections = ['\t'.join(section.split('\n')) for section in sections if section.strip()]
            converted_text = '\n'.join(converted_sections).rstrip()
        else:
            converted_text = '\t'.join(line for line in current_text.split('\n') if line.strip()).rstrip()
    else:
        delimiter = '\n' * (delimiter_lines + 1)
        sections = current_text.split(delimiter)
        converted_sections = ['\t'.join(section.split('\n')) for section in sections if section.strip() or delimiter_lines > 0]
        converted_text = delimiter.join(converted_sections).rstrip()
    
    output_textbox.delete("1.0", tk.END)
    output_textbox.insert("1.0", converted_text)
    update_char_count()
    show_status("改行をタブに変換しました")

def tab_to_newline():
    global section_lengths
    delimiter_lines = int(delimiter_var.get())
    continuous = continuous_var.get()
    mode = mode_var.get()
    trigger1 = trigger1_entry.get()
    trigger2 = trigger2_entry.get()
    current_text = output_textbox.get("1.0", tk.END).rstrip()
    
    if delimiter_lines == 0:
        if continuous:
            output_lines = current_text.split('\n')
            total_lines = len([line for line in output_lines if line.strip()])
            expected_lines = sum(section_lengths) if section_lengths else 0
            if section_lengths and expected_lines == total_lines:
                sections = []
                current_index = 0
                for length in section_lengths:
                    if current_index < len(output_lines):
                        section = output_lines[current_index:current_index + length]
                        sections.append('\n'.join(section))
                        current_index += length
            else:
                input_text = input_textbox.get("1.0", tk.END).rstrip()
                input_lines = input_text.split('\n')
                section_lengths.clear()
                sections = []
                current_index = 0
                i = 0
                found = False

                is_keep_middle = (mode == "削除←保持→削除")
                start_trigger = trigger1 if is_keep_middle else trigger2
                end_trigger = trigger2 if is_keep_middle else trigger1
                first_trigger = trigger1
                second_trigger = trigger2

                if is_keep_middle:
                    while i < len(input_lines):
                        if first_trigger in input_lines[i]:
                            found = True
                            if continuous:
                                while i < len(input_lines) and first_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            start = i
                            while i < len(input_lines) and (not second_trigger or second_trigger not in input_lines[i]):
                                i += 1
                            end = i if second_trigger else len(input_lines)
                            if start < end:
                                section_lengths.append(end - start)
                                if current_index < len(output_lines):
                                    section = output_lines[current_index:current_index + (end - start)]
                                    sections.append('\n'.join(section))
                                    current_index += (end - start)
                            if not continuous:
                                break
                        else:
                            i += 1
                else:
                    start = 0
                    while i < len(input_lines):
                        if first_trigger in input_lines[i]:
                            found = True
                            end_part1 = i
                            if start < end_part1:
                                section_lengths.append(end_part1 - start)
                                if current_index < len(output_lines):
                                    section = output_lines[current_index:current_index + (end_part1 - start)]
                                    sections.append('\n'.join(section))
                                    current_index += (end_part1 - start)
                            if continuous:
                                while i < len(input_lines) and first_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            while i < len(input_lines) and (not second_trigger or second_trigger not in input_lines[i]):
                                i += 1
                            if i >= len(input_lines):
                                break
                            if continuous:
                                while i < len(input_lines) and second_trigger in input_lines[i]:
                                    i += 1
                            else:
                                i += 1
                            start = i
                            if not continuous:
                                if start < len(input_lines):
                                    section_lengths.append(len(input_lines) - start)
                                    if current_index < len(output_lines):
                                        section = output_lines[current_index:current_index + (len(input_lines) - start)]
                                        sections.append('\n'.join(section))
                                        current_index += (len(input_lines) - start)
                                break
                        else:
                            i += 1
                    if start < len(input_lines):
                        section_lengths.append(len(input_lines) - start)
                        if current_index < len(output_lines):
                            section = output_lines[current_index:current_index + (len(input_lines) - start)]
                            sections.append('\n'.join(section))
                            current_index += (len(input_lines) - start)

                if not found and not continuous:
                    section_lengths = [len(output_lines)]
                    sections = ['\n'.join(output_lines)]

            converted_sections = ['\n'.join(section.split('\t')) for section in sections if section.strip()]
            converted_text = '\n'.join(converted_sections).rstrip()
        else:
            converted_text = '\n'.join(line for line in current_text.split('\t') if line.strip()).rstrip()
    else:
        delimiter = '\n' * (delimiter_lines + 1)
        sections = current_text.split(delimiter)
        converted_sections = ['\n'.join(section.split('\t')) for section in sections if section.strip() or delimiter_lines > 0]
        converted_text = delimiter.join(converted_sections).rstrip()
    
    output_textbox.delete("1.0", tk.END)
    output_textbox.insert("1.0", converted_text)
    update_char_count()
    show_status("タブを改行に変換しました")

def paste_text():
    try:
        clipboard_text = pyperclip.paste()
        input_textbox.delete("1.0", tk.END)
        input_textbox.insert("1.0", clipboard_text)
        update_char_count()
        show_status("テキストをペーストしました")
    except Exception as e:
        show_status("ペーストに失敗しました: " + str(e), is_error=True)

def clear_text():
    input_textbox.delete("1.0", tk.END)
    update_char_count()
    show_status("入力テキストをクリアしました")

def copy_text():
    try:
        output_text = output_textbox.get("1.0", tk.END).strip()
        pyperclip.copy(output_text)
        show_status("テキストをクリップボードにコピーしました")
    except Exception as e:
        show_status("コピーに失敗しました: " + str(e), is_error=True)

def save_csv():
    text = output_textbox.get("1.0", tk.END).rstrip()
    if not text:
        show_status("出力テキストが空です", is_error=True)
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if file_path:
        encoding = encoding_var.get()
        lines = text.split('\n')
        with open(file_path, "w", encoding=encoding, newline='') as f:
            writer = csv.writer(f)
            for line in lines:
                row = line.split('\t')
                writer.writerow(row)
        show_status("CSVとして保存しました")

# GUI setup
root = tk.Tk()
root.title("テキスト整形ツール")
root.geometry("800x600")

main_frame = ttk.Frame(root, padding="10")
main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# Remove options frame
remove_frame = ttk.LabelFrame(main_frame, text="削除条件", padding="5")
remove_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

mode_var = tk.StringVar(value="削除←保持→削除")
mode_combobox = ttk.Combobox(remove_frame, textvariable=mode_var, values=["削除←保持→削除", "保持→削除←保持"], state="readonly", width=18)
mode_combobox.grid(row=0, column=0, pady=2, sticky=tk.W)
mode_var.trace("w", update_labels)

trigger1_label = ttk.Label(remove_frame, text="開始トリガー:")
trigger1_label.grid(row=1, column=0, sticky=tk.W)
trigger1_entry = ttk.Entry(remove_frame)
trigger1_entry.grid(row=1, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))

trigger2_label = ttk.Label(remove_frame, text="終了トリガー:")
trigger2_label.grid(row=2, column=0, sticky=tk.W)
trigger2_entry = ttk.Entry(remove_frame)
trigger2_entry.grid(row=2, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))

continuous_var = tk.BooleanVar(value=True)
ttk.Checkbutton(remove_frame, text="連続処理", variable=continuous_var).grid(row=3, column=0, pady=2, sticky=tk.W)
include_triggers_var = tk.BooleanVar(value=True)
ttk.Checkbutton(remove_frame, text="削除にトリガー文字を含める", variable=include_triggers_var).grid(row=3, column=1, pady=2, sticky=tk.W)

delimiter_var = tk.StringVar(value="1")
ttk.Label(remove_frame, text="区切り行数:").grid(row=4, column=0, sticky=tk.W)
delimiter_combobox = ttk.Combobox(remove_frame, textvariable=delimiter_var, values=[str(i) for i in range(11)], state="readonly", width=5)
delimiter_combobox.grid(row=4, column=1, pady=2, sticky=tk.W)

ttk.Label(remove_frame, text="設定名:").grid(row=5, column=0, sticky=tk.W)
settings_name_entry = ttk.Entry(remove_frame)
settings_name_entry.grid(row=5, column=1, padx=5, pady=2, sticky=(tk.W, tk.E))
save_button = ttk.Button(remove_frame, text="保存", command=save_settings)
save_button.grid(row=6, column=0, pady=2)
delete_button = ttk.Button(remove_frame, text="削除", command=delete_settings)
delete_button.grid(row=6, column=1, pady=2, sticky=tk.W)

ttk.Label(remove_frame, text="設定読込:").grid(row=7, column=0, sticky=tk.W)
settings_var = tk.StringVar()
settings_dropdown = ttk.Combobox(remove_frame, textvariable=settings_var, state="readonly")
settings_dropdown.grid(row=7, column=1, pady=2, sticky=(tk.W, tk.E))
settings_var.trace("w", load_settings)
update_settings_dropdown()

remove_frame.columnconfigure(0, weight=0)
remove_frame.columnconfigure(1, weight=1)

# Replace frame
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

# Empty rows between replace and newline_to_tab
ttk.Label(replace_frame, text="").grid(row=3, column=0)
ttk.Label(replace_frame, text="").grid(row=4, column=0)

newline_to_tab_button = ttk.Button(replace_frame, text="改行→タブ", command=newline_to_tab)
newline_to_tab_button.grid(row=5, column=0, columnspan=2, pady=2)
tab_to_newline_button = ttk.Button(replace_frame, text="タブ→改行", command=tab_to_newline)
tab_to_newline_button.grid(row=6, column=0, columnspan=2, pady=2)

# Empty rows below tab_to_newline
ttk.Label(replace_frame, text="").grid(row=7, column=0)
ttk.Label(replace_frame, text="").grid(row=8, column=0)

replace_frame.columnconfigure(1, weight=1)

# Input textbox
input_label_frame = ttk.Frame(main_frame)
input_label_frame.grid(row=1, column=0, sticky=tk.W)
input_label = ttk.Label(input_label_frame, text="整形前テキスト:")
input_label.pack(side=tk.LEFT)
input_count_label = ttk.Label(input_label_frame, text="全角0.0文字（0バイト）")
input_count_label.pack(side=tk.LEFT, padx=10)
input_textbox = tk.Text(main_frame, height=12)
input_textbox.grid(row=2, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
input_textbox.bind("<KeyRelease>", update_char_count)

# Buttons
button_frame = ttk.Frame(main_frame)
button_frame.grid(row=3, column=0, pady=5, sticky=tk.W)
paste_button = ttk.Button(button_frame, text="ペースト", command=paste_text)
paste_button.pack(side=tk.LEFT, padx=5)
clear_button = ttk.Button(button_frame, text="クリア", command=clear_text)
clear_button.pack(side=tk.LEFT, padx=5)

# Format buttons
format_frame = ttk.Frame(main_frame)
format_frame.grid(row=2, column=1, pady=5)
format_button = ttk.Button(format_frame, text="整形", command=lambda: clean_text(append=False))
format_button.pack(pady=2)
append_button = ttk.Button(format_frame, text="整形追記", command=lambda: clean_text(append=True))
append_button.pack(pady=2)

status_frame = ttk.Frame(main_frame, style="White.TFrame")
status_frame.grid(row=4, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
status_label = ttk.Label(status_frame, text="", background="white")
status_label.pack(fill=tk.X)

# Output textbox
output_label_frame = ttk.Frame(main_frame)
output_label_frame.grid(row=1, column=2, sticky=tk.W)
output_label = ttk.Label(output_label_frame, text="整形済みテキスト:")
output_label.pack(side=tk.LEFT)
output_count_label = ttk.Label(output_label_frame, text="全角0.0文字（0バイト）")
output_count_label.pack(side=tk.LEFT, padx=10)
output_textbox = tk.Text(main_frame, height=12)
output_textbox.grid(row=2, column=2, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
output_textbox.bind("<KeyRelease>", update_char_count)

# Output buttons
output_button_frame = ttk.Frame(main_frame)
output_button_frame.grid(row=3, column=2, pady=5, sticky=tk.W)
copy_button = ttk.Button(output_button_frame, text="コピー", command=copy_text)
copy_button.pack(side=tk.LEFT, padx=5)
csv_button = ttk.Button(output_button_frame, text="CSV保存", command=save_csv)
csv_button.pack(side=tk.LEFT, padx=5)
encoding_var = tk.StringVar(value="cp932")
encoding_combobox = ttk.Combobox(output_button_frame, textvariable=encoding_var, values=["utf-8", "cp932", "shift_jis"], state="readonly", width=10)
encoding_combobox.pack(side=tk.LEFT, padx=5)

style = ttk.Style()
style.configure("White.TFrame", background="white")

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=0)
main_frame.columnconfigure(2, weight=1)
main_frame.rowconfigure(2, weight=1)
main_frame.rowconfigure(0, weight=0)
main_frame.rowconfigure(1, weight=0)
main_frame.rowconfigure(3, weight=0)
main_frame.rowconfigure(4, weight=0)
remove_frame.columnconfigure(1, weight=1)
replace_frame.columnconfigure(1, weight=1)

update_char_count()
update_labels()
root.mainloop()