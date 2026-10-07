import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os
from datetime import datetime, date
import calendar

# Excel列記号 → 列番号変換 (A=0, B=1, AA=26 など 0-based)
def excel_col_to_num(col_str):
    if not col_str:
        return None
    col_str = col_str.upper().strip()
    num = 0
    for c in col_str:
        if 'A' <= c <= 'Z':
            num = num * 26 + (ord(c) - ord('A') + 1)
        else:
            return None
    return num - 1

# 安全な日付フォーマット関数
def safe_format_date(x):
    if pd.isnull(x):
        return ''
    if isinstance(x, (pd.Timestamp, datetime)):
        try:
            return x.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(x)
    else:
        return str(x)

# カスタム日付解析関数
def parse_date(x):
    if pd.isnull(x):
        return pd.NaT
    x_str = str(x).strip()
    if not x_str:
        return pd.NaT

    # 数値の場合 (Excelシリアル日付)
    try:
        num = float(x_str)
        return pd.Timestamp('1899-12-30') + pd.Timedelta(days=num)
    except ValueError:
        pass

    # 様々な文字列形式を試す
    formats = [
        '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        '%d-%m-%Y', '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M',
        '%m-%d-%Y', '%m-%d-%Y %H:%M:%S', '%m-%d-%Y %H:%M',
        '%Y/%m/%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M',
        '%d/%m/%Y', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
        '%m/%d/%Y', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M',
        '%Y%m%d', '%Y%m%d %H%M%S', '%Y%m%d %H%M',
        '%d%m%Y', '%d%m%Y %H%M%S', '%d%m%Y %H%M',
        '%m%d%Y', '%m%d%Y %H%M%S', '%m%d%Y %H%M',
        # ISO形式
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M',
        # 日本語形式例
        '%Y年%m月%d日', '%Y年%m月%d日 %H時%M分%S秒', '%Y年%m月%d日 %H時%M分',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(x_str, fmt)
        except ValueError:
            pass

    # デフォルトのpd.to_datetimeにフォールバック
    try:
        return pd.to_datetime(x_str, errors='raise')
    except:
        return pd.NaT

# 日付ピッカー（カレンダー）
class DatePicker(tk.Toplevel):
    def __init__(self, parent, entry_widget, initial_date=None):
        super().__init__(parent)
        self.entry = entry_widget
        self.title("日付選択")
        self.geometry("280x300")
        self.resizable(False, False)
        self.selected_date = None

        if initial_date and isinstance(initial_date, date):
            self.year = initial_date.year
            self.month = initial_date.month
        else:
            today = datetime.today()
            self.year = today.year
            self.month = today.month

        top_frame = tk.Frame(self)
        top_frame.pack(pady=10)

        tk.Button(top_frame, text="<<", command=self.prev_year).pack(side=tk.LEFT, padx=5)
        self.year_label = tk.Label(top_frame, text=str(self.year), width=6)
        self.year_label.pack(side=tk.LEFT)
        tk.Button(top_frame, text=">>", command=self.next_year).pack(side=tk.LEFT, padx=5)

        tk.Button(top_frame, text="<", command=self.prev_month).pack(side=tk.LEFT, padx=5)
        self.month_label = tk.Label(top_frame, text=f"{self.month:02d}", width=4)
        self.month_label.pack(side=tk.LEFT)
        tk.Button(top_frame, text=">", command=self.next_month).pack(side=tk.LEFT, padx=5)

        self.cal_frame = tk.Frame(self)
        self.cal_frame.pack(pady=5)

        self.create_calendar()

        tk.Button(self, text="選択", command=self.select_date, width=10).pack(pady=10)

        self.bind("<MouseWheel>", self.on_mousewheel)
        self.cal_frame.bind("<MouseWheel>", self.on_mousewheel)
        for child in self.cal_frame.winfo_children():
            child.bind("<MouseWheel>", self.on_mousewheel)

    def create_calendar(self):
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        cal = calendar.monthcalendar(self.year, self.month)
        days = ["月", "火", "水", "木", "金", "土", "日"]

        for i, day in enumerate(days):
            tk.Label(self.cal_frame, text=day, width=4, relief="ridge").grid(row=0, column=i, padx=1, pady=1)

        for week_idx, week in enumerate(cal):
            for day_idx, day in enumerate(week):
                if day == 0:
                    tk.Label(self.cal_frame, text="", width=4).grid(row=week_idx+1, column=day_idx, padx=1, pady=1)
                else:
                    btn = tk.Button(self.cal_frame, text=str(day), width=4,
                                    command=lambda d=day: self.set_date(d))
                    btn.grid(row=week_idx+1, column=day_idx, padx=1, pady=1)

        self.year_label.config(text=str(self.year))
        self.month_label.config(text=f"{self.month:02d}")

    def set_date(self, day):
        self.selected_date = date(self.year, self.month, day)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, self.selected_date.strftime("%Y-%m-%d"))
        self.destroy()

    def select_date(self):
        if self.selected_date:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.selected_date.strftime("%Y-%m-%d"))
        self.destroy()

    def prev_year(self): 
        self.year -= 1
        self.create_calendar()

    def next_year(self): 
        self.year += 1
        self.create_calendar()

    def prev_month(self):
        self.month -= 1
        if self.month == 0:
            self.month = 12
            self.year -= 1
        self.create_calendar()

    def next_month(self):
        self.month += 1
        if self.month == 13:
            self.month = 1
            self.year += 1
        self.create_calendar()

    def on_mousewheel(self, event):
        if event.delta > 0:
            self.prev_month()
        else:
            self.next_month()

def show_date_picker(entry):
    DatePicker(root, entry)

# ── メイン処理 ──────────────────────────────────────────────────────────────

def process_excel():
    input_file = input_path_entry.get().strip()
    output_dir = output_path_entry.get().strip()
    search_string = search_string_entry.get().strip()
    col_start_str = col_start_entry.get().strip()
    col_end_str = col_end_entry.get().strip()
    partial_match = partial_match_var.get()
    date_col_str = date_col_entry.get().strip()

    if not input_file or not search_string:
        messagebox.showerror("エラー", "入力ファイルと検索文字列は必須です。")
        return

    try:
        df = pd.read_excel(input_file)
    except Exception as e:
        messagebox.showerror("エラー", f"ファイル読み込み失敗: {e}")
        return

    # 列番号変換
    try:
        start_col = excel_col_to_num(col_start_str) if col_start_str and col_start_str.isalpha() else \
                    (int(col_start_str) - 1 if col_start_str else 0)
        end_col = excel_col_to_num(col_end_str) if col_end_str and col_end_str.isalpha() else \
                  (int(col_end_str) if col_end_str else df.shape[1])
        date_col = excel_col_to_num(date_col_str) if date_col_str and date_col_str.isalpha() else \
                   (int(date_col_str) - 1 if date_col_str else None)

        if start_col < 0 or end_col > df.shape[1] or start_col >= end_col:
            messagebox.showerror("エラー", "検索列の指定が不正です。")
            return
        if date_col is not None and (date_col < 0 or date_col >= df.shape[1]):
            messagebox.showerror("エラー", "日時列の指定が不正です。")
            return
    except:
        messagebox.showerror("エラー", "列番号の入力形式が正しくありません。")
        return

    # 削除条件適用
    for del_cond in delete_conditions:
        del_type = del_cond['type'].get()
        del_start_str = del_cond['start'].get().strip()
        del_end_str = del_cond['end'].get().strip()

        if not del_start_str:
            continue

        try:
            del_start = excel_col_to_num(del_start_str) if del_type == '列' and del_start_str.isalpha() else int(del_start_str) - 1
            del_end = excel_col_to_num(del_end_str) if del_type == '列' and del_end_str.isalpha() else (int(del_end_str) if del_end_str else None)

            if del_type == '列':
                if del_end is None:
                    del_end = df.shape[1] - 1
                del_count = del_end - del_start + 1

                # date_col調整
                if date_col is not None:
                    if date_col >= del_start and date_col <= del_end:
                        messagebox.showerror("エラー", "日時列が削除範囲に含まれています。")
                        return
                    elif date_col > del_end:
                        date_col -= del_count

                # 検索範囲調整
                if start_col >= del_start and start_col <= del_end:
                    messagebox.showerror("エラー", "検索開始列が削除範囲に含まれています。")
                    return
                if end_col - 1 >= del_start and end_col - 1 <= del_end:
                    messagebox.showerror("エラー", "検索終了列が削除範囲に含まれています。")
                    return
                if start_col > del_end:
                    start_col -= del_count
                if end_col > del_end + 1:
                    end_col -= del_count

                if del_end is None or del_end == df.shape[1] - 1:
                    df = df.iloc[:, :del_start]
                else:
                    df = df.drop(columns=df.columns[del_start:del_end + 1], errors='ignore')
            elif del_type == '行':
                if del_end is None:
                    df = df.iloc[:del_start]
                else:
                    df = df.drop(df.index[del_start:del_end + 1 if del_end else None], errors='ignore')
        except Exception as e:
            messagebox.showwarning("警告", f"削除条件の指定が不正です: {del_type} {del_start_str} - {del_end_str}\n{e}")

    # 検索 & 重複削除
    filtered_df = pd.DataFrame()
    for col in range(start_col, end_col):
        series = df.iloc[:, col].astype(str).fillna('')
        mask = series.str.contains(search_string, na=False) if partial_match else (series == search_string)
        filtered_df = pd.concat([filtered_df, df[mask]], ignore_index=True)

    filtered_df = filtered_df.drop_duplicates()

    if date_col is not None:
        date_series = filtered_df.iloc[:, date_col]

        # カスタム解析を使用
        date_converted = date_series.apply(parse_date)

        filtered_df[filtered_df.columns[date_col]] = pd.Series(date_converted, dtype='datetime64[ns]', index=filtered_df.index)
        filtered_df['__valid_date__'] = filtered_df.iloc[:, date_col].notna()

        # 日付範囲フィルタ
        if range_var.get():
            start_str = start_date_entry.get().strip()
            end_str = end_date_entry.get().strip()

            try:
                start_dt = pd.to_datetime(start_str) if start_str else None
                end_dt = pd.to_datetime(end_str) if end_str else None

                mask = filtered_df['__valid_date__']
                if start_dt:
                    mask &= (filtered_df.iloc[:, date_col] >= start_dt)
                if end_dt:
                    mask &= (filtered_df.iloc[:, date_col] <= end_dt)

                filtered_df = filtered_df[mask].copy()
                if filtered_df.empty:
                    messagebox.showwarning("警告", "指定した日付範囲にデータがありません。")
            except Exception as e:
                messagebox.showwarning("警告", f"日付範囲の形式が正しくありません。\n{e}")

        # 計算処理
        if calc_var.get():
            valid_df = filtered_df[filtered_df['__valid_date__']].copy()

            if valid_df.empty:
                messagebox.showwarning("警告", "有効な日付データがありません。計算をスキップします。")
            else:
                valid_df = valid_df.sort_values(by=valid_df.columns[date_col])

                new_rows = []
                original_columns = [c for c in filtered_df.columns if c not in ['__valid_date__']]

                if group_var.get() != 'なし':
                    period = 'M' if group_var.get() == '月ごと' else 'Y'
                    valid_df['__group__'] = valid_df.iloc[:, date_col].dt.to_period(period).astype(str)

                    original_columns = [c for c in original_columns if c != '__group__']

                    for name, group in valid_df.groupby('__group__', sort=False):
                        for _, row in group.iterrows():
                            new_rows.append(row[original_columns].to_dict())

                        sum_row = {}
                        for col in original_columns:
                            if col == original_columns[0]:
                                sum_row[col] = f'{name} 合計'
                            else:
                                sum_row[col] = ''

                        for col in original_columns:
                            if col == original_columns[date_col] or col == original_columns[0]:
                                continue
                            numeric_data = pd.to_numeric(group[col], errors='coerce').fillna(0)
                            total = numeric_data.sum()
                            sum_row[col] = total if total != 0 else ''

                        new_rows.append(sum_row)

                if group_var.get() == 'なし':
                    for _, row in valid_df.iterrows():
                        new_rows.append(row[original_columns].to_dict())

                if range_var.get():
                    range_total_row = {}
                    for col in original_columns:
                        if col == original_columns[0]:
                            range_total_row[col] = '範囲合計'
                        else:
                            range_total_row[col] = ''

                    for col in original_columns:
                        if col == original_columns[date_col] or col == original_columns[0]:
                            continue
                        numeric_data = pd.to_numeric(valid_df[col], errors='coerce').fillna(0)
                        total = numeric_data.sum()
                        range_total_row[col] = total if total != 0 else ''

                    new_rows.append(range_total_row)

                filtered_df = pd.DataFrame(new_rows, columns=original_columns)

        if date_col is not None and date_col < len(filtered_df.columns):
            filtered_df.iloc[:, date_col] = filtered_df.iloc[:, date_col].apply(safe_format_date)

        filtered_df = filtered_df.drop(columns=['__valid_date__'], errors='ignore')

    if not output_dir:
        output_dir = os.path.dirname(input_file)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{base_name}_抽出_{timestamp}.xlsx"
    output_path = os.path.join(output_dir, output_filename)

    try:
        filtered_df.to_excel(output_path, index=False)
        messagebox.showinfo("完了", f"処理完了。\n出力ファイル: {output_path}")
    except Exception as e:
        messagebox.showerror("エラー", f"書き込み失敗: {e}")

# ── GUI ─────────────────────────────────────────────────────────────────────

root = tk.Tk()
root.title("Excelデータ抽出")
root.geometry("540x370")

def create_left_frame(parent):
    f = tk.Frame(parent)
    f.pack(fill=tk.X, padx=12, pady=4, anchor="w")
    return f

# 入力ファイル
f = create_left_frame(root)
tk.Label(f, text="入力").pack(side=tk.LEFT, padx=(0,8))
input_path_entry = tk.Entry(f, width=55)
input_path_entry.pack(side=tk.LEFT, padx=5)
tk.Button(f, text="参照", command=lambda: [
    input_path_entry.delete(0, tk.END),
    input_path_entry.insert(0, filedialog.askopenfilename(filetypes=[("Excel","*.xlsx")]))
]).pack(side=tk.LEFT)

# 出力フォルダ
f = create_left_frame(root)
tk.Label(f, text="出力").pack(side=tk.LEFT, padx=(0,8))
output_path_entry = tk.Entry(f, width=55)
output_path_entry.pack(side=tk.LEFT, padx=5)
tk.Button(f, text="参照", command=lambda: [
    output_path_entry.delete(0, tk.END),
    output_path_entry.insert(0, filedialog.askdirectory())
]).pack(side=tk.LEFT)

# 検索文字列 + 一致条件
f = create_left_frame(root)
tk.Label(f, text="検索文字列").pack(side=tk.LEFT, padx=(0,8))
search_string_entry = tk.Entry(f, width=30)
search_string_entry.pack(side=tk.LEFT, padx=5)

partial_match_var = tk.BooleanVar(value=True)
tk.Radiobutton(f, text="部分一致", variable=partial_match_var, value=True).pack(side=tk.LEFT, padx=8)
tk.Radiobutton(f, text="完全一致", variable=partial_match_var, value=False).pack(side=tk.LEFT)

# 検索列
f = create_left_frame(root)
tk.Label(f, text="検索列").pack(side=tk.LEFT, padx=(0,8))
col_start_entry = tk.Entry(f, width=10)
col_start_entry.pack(side=tk.LEFT)
tk.Label(f, text="列から").pack(side=tk.LEFT, padx=5)
col_end_entry = tk.Entry(f, width=10)
col_end_entry.pack(side=tk.LEFT)
tk.Label(f, text="列まで").pack(side=tk.LEFT, padx=5)

# 日時列
f = create_left_frame(root)
tk.Label(f, text="日時列").pack(side=tk.LEFT, padx=(0,8))
date_col_entry = tk.Entry(f, width=10)
date_col_entry.pack(side=tk.LEFT)

# 計算オプション
f = create_left_frame(root)
calc_var = tk.BooleanVar(value=False)
tk.Checkbutton(f, text="計算を行う", variable=calc_var).pack(side=tk.LEFT)

tk.Label(f, text="グループ化").pack(side=tk.LEFT, padx=(20,8))
group_var = tk.StringVar(value='なし')
group_menu = ttk.Combobox(f, textvariable=group_var, values=['なし','月ごと','年ごと'], state='readonly', width=10)
group_menu.pack(side=tk.LEFT)

# 日付範囲指定
f = create_left_frame(root)
range_var = tk.BooleanVar(value=False)
tk.Checkbutton(f, text="日付範囲指定", variable=range_var).pack(side=tk.LEFT)

tk.Label(f, text="開始日").pack(side=tk.LEFT, padx=(20,5))
start_date_entry = tk.Entry(f, width=12)
start_date_entry.pack(side=tk.LEFT)
tk.Button(f, text="カレンダー", command=lambda: show_date_picker(start_date_entry)).pack(side=tk.LEFT, padx=3)

tk.Label(f, text="終了日").pack(side=tk.LEFT, padx=(15,5))
end_date_entry = tk.Entry(f, width=12)
end_date_entry.pack(side=tk.LEFT)
tk.Button(f, text="カレンダー", command=lambda: show_date_picker(end_date_entry)).pack(side=tk.LEFT, padx=3)

# 削除条件エリア
delete_frame = tk.Frame(root)
delete_frame.pack(fill=tk.X, padx=12, pady=10, anchor="w")

tk.Label(delete_frame, text="削除条件").pack(side=tk.LEFT, pady=5)

delete_conditions = []

def update_window_height():
    root.update_idletasks()
    req_height = root.winfo_reqheight()
    req_width = root.winfo_reqwidth()
    root.geometry(f"{req_width}x{req_height + 30}")  # 余裕を持たせる

def add_delete_condition():
    cond_frame = tk.Frame(delete_frame)
    cond_frame.pack(fill=tk.X, pady=2, anchor="w")

    type_var = tk.StringVar(value='列')
    ttk.Combobox(cond_frame, textvariable=type_var, values=['列', '行'], state='readonly', width=5).pack(side=tk.LEFT, padx=5)

    start_entry = tk.Entry(cond_frame, width=10)
    start_entry.pack(side=tk.LEFT)
    tk.Label(cond_frame, text="から").pack(side=tk.LEFT, padx=5)
    end_entry = tk.Entry(cond_frame, width=10)
    end_entry.pack(side=tk.LEFT)
    tk.Label(cond_frame, text="を削除").pack(side=tk.LEFT, padx=5)

    tk.Button(cond_frame, text="削除", command=lambda cf=cond_frame: remove_delete_condition(cf)).pack(side=tk.LEFT, padx=5)

    start_entry.bind("<FocusOut>", lambda e: convert_col_entry(e, start_entry))
    end_entry.bind("<FocusOut>", lambda e: convert_col_entry(e, end_entry))

    delete_conditions.append({
        'frame': cond_frame,
        'type': type_var,
        'start': start_entry,
        'end': end_entry
    })

    update_window_height()

def remove_delete_condition(frame):
    for cond in delete_conditions[:]:
        if cond['frame'] == frame:
            delete_conditions.remove(cond)
            frame.destroy()
            update_window_height()
            break

# 条件追加ボタン
tk.Button(delete_frame, text="条件追加", command=add_delete_condition).pack(side=tk.LEFT, pady=5)

# 実行ボタン
tk.Button(root, text="実行", command=process_excel, width=15, height=2, font=("Helvetica", 12)).pack(pady=25)

# 列記号自動変換
def convert_col_entry(event, entry):
    val = entry.get().strip()
    if val and val.isalpha():
        num = excel_col_to_num(val)
        if num is not None:
            entry.delete(0, tk.END)
            entry.insert(0, str(num + 1))

col_start_entry.bind("<FocusOut>", lambda e: convert_col_entry(e, col_start_entry))
col_end_entry.bind("<FocusOut>", lambda e: convert_col_entry(e, col_end_entry))
date_col_entry.bind("<FocusOut>", lambda e: convert_col_entry(e, date_col_entry))

root.mainloop()