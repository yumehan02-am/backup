# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pandas as pd
from pathlib import Path
from datetime import datetime
import chardet

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV SKU 加工ツール - カタログID→JANコード対応")
        self.geometry("800x600")
        self.result_df = None
        self.input_encoding = "utf-8-sig"
        self.selected_cells = set()
        self.drag_start = None

        # ステータスバー用
        self.status_var = tk.StringVar()
        self.status_var.set("準備完了")

        self.create_widgets()
        self.apply_windows_style()
        self.bind("<Configure>", self.on_resize)

    def apply_windows_style(self):
        self.option_add("*Font", ("Segoe UI", 9))

    def show_status(self, message, timeout=2000):
        """ステータスバーに一時的にメッセージを表示（timeoutミリ秒後に消える）"""
        self.status_var.set(message)
        self.bell()  # コピー音は残す
        if timeout > 0:
            self.after(timeout, lambda: self.status_var.set(""))

    def create_widgets(self):
        pad = {"padx": 10, "pady": 6}
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, **pad)

        # === 読込エリア ===
        frm_in = ttk.LabelFrame(main, text="読込 CSV")
        frm_in.pack(fill="x", **pad)
        ttk.Label(frm_in, text="ファイル:").pack(side="left")
        self.ent_in = ttk.Entry(frm_in, width=50)
        self.ent_in.pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(frm_in, text="参照", command=self.browse_input).pack(side="left")
        ttk.Label(frm_in, text="  読込文字コード:").pack(side="left")
        self.enc_in_var = tk.StringVar(value="自動検知")
        ttk.Combobox(frm_in, textvariable=self.enc_in_var,
                     values=("自動検知","utf-8","utf-8-sig","cp932"), width=12, state="readonly").pack(side="left", padx=5)

        # === 出力エリア ===
        frm_out = ttk.LabelFrame(main, text="出力設定")
        frm_out.pack(fill="x", **pad)
        ttk.Label(frm_out, text="保存先:").pack(side="left")
        self.ent_out = ttk.Entry(frm_out, width=50)
        self.ent_out.pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(frm_out, text="変更", command=self.browse_output).pack(side="left")
        ttk.Label(frm_out, text="  保存文字コード:").pack(side="left")
        self.enc_out_var = tk.StringVar(value="cp932")
        ttk.Combobox(frm_out, textvariable=self.enc_out_var,
                     values=("cp932","utf-8","utf-8-sig"), width=12, state="readonly").pack(side="left", padx=5)

        # === ボタン ===
        frm_btn = ttk.Frame(main)
        frm_btn.pack(fill="x", pady=8)
        ttk.Button(frm_btn, text="加工実行", command=self.process).pack(side="left", padx=8)
        ttk.Button(frm_btn, text="CSV保存", command=self.save).pack(side="left", padx=8)
        ttk.Button(frm_btn, text="選択範囲コピー", command=self.copy_selection).pack(side="left", padx=8)

        # === 結果テーブル ===
        frm_res = ttk.LabelFrame(main, text="結果表：カタログID→JANコード / 在庫数→数量")
        frm_res.pack(fill="both", expand=True, **pad)

        canvas = tk.Canvas(frm_res)
        vsb = ttk.Scrollbar(frm_res, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(frm_res, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        scroll_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        self.cols = [
            "商品管理番号（商品URL）","商品名","SKU管理番号","システム連携用SKU番号",
            "バリエーション項目選択肢1","バリエーション項目選択肢2","バリエーション項目選択肢3",
            "バリエーション項目選択肢4","バリエーション項目選択肢5","バリエーション項目選択肢6",
            "通常購入販売価格","表示価格","数量","JANコード"
        ]

        self.tree = ttk.Treeview(scroll_frame, columns=self.cols, show="headings", selectmode="none")
        for col in self.cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="w", minwidth=0)
        self.tree.pack(fill="both", expand=True)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

        self.tree.tag_configure("cell_highlight", background="#FFEB3B", foreground="black")

        self.tree.bind("<Double-Button-1>", self.on_double_click)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<B1-Motion>", self.on_drag)
        self.tree.bind("<ButtonRelease-1>", self.on_release)
        self.tree.bind("<Control-c>", self.copy_selection)

        # === ステータスバー（最後に追加）===
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding="4 2")
        status_bar.pack(side="bottom", fill="x")

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            col = self.tree.identify_column(event.x)
            col_idx = int(col[1:]) - 1
            col_name = self.cols[col_idx]
            values = [self.tree.item(item, "values")[col_idx] for item in self.tree.get_children()]
            text = "\n".join(values)
            self.clipboard_clear()
            self.clipboard_append(text)
            self.show_status(f"列 [{col_name}] をコピーしました（{len(values)}件）", 2500)

        elif region == "cell":
            row = self.tree.identify_row(event.y)
            col = self.tree.identify_column(event.x)
            col_idx = int(col[1:]) - 1
            value = self.tree.item(row, "values")[col_idx]
            self.clipboard_clear()
            self.clipboard_append(value)
            self.show_status(f"コピー: {value}", 2000)

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if row and col:
            self.drag_start = (row, col)
            self.highlight_range(row, col, row, col)

    def on_drag(self, event):
        if not self.drag_start: return
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if row and col:
            self.highlight_range(self.drag_start[0], self.drag_start[1], row, col)

    def on_release(self, event):
        self.drag_start = None

    def highlight_range(self, r1, c1, r2, c2):
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        self.selected_cells.clear()
        rows = self.get_rows_between(r1, r2)
        cols_idx = self.get_cols_between(c1, c2)
        for row_id in rows:
            self.tree.item(row_id, tags=("cell_highlight",))
            for col_idx in cols_idx:
                self.selected_cells.add((row_id, col_idx))

    def get_rows_between(self, r1, r2):
        all_rows = self.tree.get_children()
        if not all_rows: return []
        i1 = list(all_rows).index(r1) if r1 in all_rows else 0
        i2 = list(all_rows).index(r2) if r2 in all_rows else len(all_rows)-1
        return all_rows[min(i1,i2):max(i1,i2)+1]

    def get_cols_between(self, c1, c2):
        i1 = int(c1[1:]) - 1
        i2 = int(c2[1:]) - 1
        return list(range(min(i1,i2), max(i1,i2)+1))

    def copy_selection(self, event=None):
        if not self.selected_cells:
            self.show_status("範囲が選択されていません（ドラッグで選択 → Ctrl+C）", 3000)
            return
        rows = sorted({r for r,c in self.selected_cells}, key=lambda x: self.tree.index(x))
        cols = sorted({c for r,c in self.selected_cells})
        data = []
        for row_id in rows:
            values = self.tree.item(row_id, "values")
            row_data = [values[c] for c in cols]
            data.append("\t".join(row_data))
        text = "\n".join(data)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.show_status(f"コピー完了：{len(rows)}行 × {len(cols)}列", 2000)

    def on_resize(self, event):
        if event.widget != self: return
        available_height = self.winfo_height() - 280  # ステータスバー分少し増やす
        row_height = 22
        visible_rows = max(5, available_height // row_height)
        self.tree.configure(height=visible_rows)

    def browse_input(self):
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        self.ent_in.delete(0, tk.END); self.ent_in.insert(0, path)
        with open(path,"rb") as f:
            enc = chardet.detect(f.read(100000))["encoding"] or "utf-8"
            self.input_encoding = enc
        p = Path(path); ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ent_out.delete(0, tk.END); self.ent_out.insert(0, str(p.parent/f"{p.stem}_加工済_{ts}.csv"))
        self.enc_out_var.set("cp932" if "shift" in enc.lower() else "utf-8-sig")
        self.show_status(f"読込ファイル設定完了: {Path(path).name}", 3000)

    def browse_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if path:
            self.ent_out.delete(0, tk.END); self.ent_out.insert(0, path)
            self.show_status("保存先を変更しました", 2000)

    def process(self):
        in_path = self.ent_in.get().strip()
        if not Path(in_path).exists():
            return messagebox.showwarning("エラー", "CSVを選択してください")
        enc = self.input_encoding if self.enc_in_var.get() == "自動検知" else self.enc_in_var.get()
        enc_map = {"utf-8":"utf-8", "utf-8-sig":"utf-8-sig", "cp932":"cp932"}
        enc = enc_map.get(enc, enc)
        try:
            df = pd.read_csv(in_path, dtype=str, encoding=enc).fillna("")
            self.result_df = self.transform(df)
            self.display_result(self.result_df)
            messagebox.showinfo("成功", f"加工完了！ {len(self.result_df):,} 件")
            self.show_status(f"加工完了：{len(self.result_df):,} 件", 3000)
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def transform(self, df):
        key_col = "商品管理番号（商品URL）"
        sku_col = "商品番号"
        opt_col = "選択肢タイプ"
        sub_sku_col = "SKU管理番号"
        sys_sku_col = "システム連携用SKU番号"
        price_col = "通常購入販売価格"
        disp_col = "表示価格"
        name_col = "商品名"
        var_cols = [f"バリエーション項目選択肢{i}" for i in range(1,7)]

        out_rows = []
        for grp_key, group in df.groupby(key_col):
            if not grp_key: continue
            parent = group[group[sku_col] != ""].iloc[0]
            common = {"商品管理番号（商品URL）": grp_key, "商品名": parent.get(name_col, "")}
            child_rows = group[(group[sku_col]=="") & (group[opt_col]=="") & (group[sub_sku_col]!="")]
            for _, row in child_rows.iterrows():
                out = common.copy()
                out["SKU管理番号"] = row[sub_sku_col]
                out["システム連携用SKU番号"] = row.get(sys_sku_col, "")
                for i, vcol in enumerate(var_cols,1): out[vcol] = row.get(vcol, "")
                out["通常購入販売価格"] = row.get(price_col, "") or parent.get(price_col, "")
                out["表示価格"] = row.get(disp_col, "") or parent.get(disp_col, "")
                out["数量"] = row.get("在庫数", "1")
                out["JANコード"] = row.get("カタログID", "")
                out_rows.append(out)

        out_df = pd.DataFrame(out_rows)
        return out_df.reindex(columns=self.cols)

    def display_result(self, df):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for _, row in df.iterrows():
            self.tree.insert("", "end", values=[row[c] for c in self.cols])
        self.selected_cells.clear()

        for col_idx, col_name in enumerate(self.cols):
            values = [self.tree.item(item, "values")[col_idx] for item in self.tree.get_children()]
            if all(v == "" for v in values):
                self.tree.column(col_name, width=0, minwidth=0)
            else:
                self.tree.column(col_name, width=120)

        self.after(100, lambda: self.on_resize(type('obj', (object,), {'widget': self})()))

    def save(self):
        if self.result_df is None:
            return messagebox.showwarning("警告", "先に加工してください")
        out_path = self.ent_out.get().strip()
        if not out_path:
            return messagebox.showwarning("警告", "保存先を指定してください")
        enc = self.enc_out_var.get()
        try:
            self.result_df.to_csv(out_path, index=False, encoding=enc)
            messagebox.showinfo("保存完了", f"保存しました！\n{out_path}")
            self.show_status(f"保存完了: {Path(out_path).name}", 3000)
        except Exception as e:
            messagebox.showerror("エラー", str(e))

if __name__ == "__main__":
    try:
        import chardet
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
        import chardet
    App().mainloop()