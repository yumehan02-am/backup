# -*- coding: utf-8 -*-
"""
ゆめはん LP 更新ツール 完全最終版
・置換／追加切り替え → 予定枚数も即時反映
・文字装飾なし（シンプル黒文字）
・ログに画像ダウンロード状況も表示
・ウィンドウサイズ 600x600（リサイズ可）
"""

import os
import csv
import requests
from PIL import Image
import io
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import shutil

# ------------------- 設定 -------------------
IMAGE_SIZE = (563, 563)
OUTPUT_IMAGE_DIR = "images"
SHOP_BASE = "https://store.shopping.yahoo.co.jp/u-b-yumehan/"

class YumehanUpdater:
    def __init__(self, root):
        self.root = root
        self.root.title("ゆめはん LP 更新ツール")
        self.root.geometry("600x600")
        self.root.resizable(True, True)

        # ファイルパス
        self.yahoo_csv_path = tk.StringVar()
        self.select_csv_path = tk.StringVar()
        self.html_path = tk.StringVar()

        # グループ設定
        self.loop_a = tk.IntVar(value=1); self.mode_a = tk.StringVar(value="replace")
        self.loop_b = tk.IntVar(value=1); self.mode_b = tk.StringVar(value="replace")
        self.loop_c = tk.IntVar(value=1); self.mode_c = tk.StringVar(value="replace")
        self.loop_d = tk.IntVar(value=1); self.mode_d = tk.StringVar(value="replace")

        # 状態保持
        self.current_counts = {"a": 0, "b": 0, "c": 0, "d": 0}
        self.base_items = {"a": [], "b": [], "c": [], "d": []}  # 商品指定CSVの商品数
        self.current_labels = {}
        self.planned_labels = {}

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        main = tk.Frame(self.root, padx=15, pady=12)
        main.pack(fill="both", expand=True)

        # ファイル選択
        for text, var, cmd in [
            ("Yahoo!ショッピング 商品CSV", self.yahoo_csv_path, self.select_yahoo_csv),
            ("商品指定CSV（group,code）", self.select_csv_path, self.select_select_csv),
            ("更新対象 index.html", self.html_path, self.select_html),
        ]:
            f = tk.Frame(main)
            f.pack(fill="x", pady=4)
            tk.Label(f, text=text + "：", width=23, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, state="readonly").pack(side="left", expand=True, fill="x", padx=5)
            tk.Button(f, text="参照", width=6, command=cmd).pack(side="right")

        # グループ設定
        gf = tk.LabelFrame(main, text="グループ設定", padx=10, pady=8)
        gf.pack(fill="x", pady=12)

        for g, name in [("a", "aグループ"), ("b", "bグループ"), ("c", "cグループ"), ("d", "dグループ")]:
            f = tk.Frame(gf)
            f.pack(fill="x", pady=4)

            tk.Label(f, text=f"{name}：", width=10, anchor="w").pack(side="left")
            tk.Label(f, text="現在 ").pack(side="left")
            cur_lbl = tk.Label(f, text="--枚", width=6, anchor="w")
            cur_lbl.pack(side="left", padx=(0,5))
            self.current_labels[g] = cur_lbl

            plan_lbl = tk.Label(f, text="→ 予定 --枚", width=16, anchor="w")
            plan_lbl.pack(side="left", padx=(0,10))
            self.planned_labels[g] = plan_lbl

            tk.Label(f, text="ループ：").pack(side="left")
            spin = tk.Spinbox(f, from_=1, to=30, textvariable=getattr(self, f"loop_{g}"), width=3)
            spin.pack(side="left", padx=(0,8))

            tk.Radiobutton(f, text="置換", variable=getattr(self, f"mode_{g}"), value="replace").pack(side="left", padx=3)
            tk.Radiobutton(f, text="追加", variable=getattr(self, f"mode_{g}"), value="append").pack(side="left", padx=3)

        # 実行ボタン
        btn_f = tk.Frame(main)
        btn_f.pack(pady=12)
        self.run_btn = tk.Button(btn_f, text="更新実行", font=("Meiryo UI", 11), bg="#1976D2", fg="white",
                                 command=self.start_processing, padx=30, pady=8)
        self.run_btn.pack()

        # ログ
        tk.Label(main, text="処理ログ").pack(anchor="w", pady=(8,3))
        log_box = tk.Frame(main)
        log_box.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_box, height=12, font=("Meiryo UI", 9))
        sb = tk.Scrollbar(log_box, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def bind_events(self):
        # ループ・モード変更で即時予定枚数更新
        for g in "abcd":
            getattr(self, f"loop_{g}").trace("w", lambda *args: self.update_planned())
            getattr(self, f"mode_{g}").trace("w", lambda *args: self.update_planned())

    def update_current(self):
        if not self.html_path.get(): return
        try:
            with open(self.html_path.get(), "r", encoding="utf-8") as f:
                html = f.read()
            for g in "abcd":
                count = len(re.findall(rf'item-{g}\d+\.jpg', html))
                self.current_counts[g] = count
                self.current_labels[g].config(text=f"{count}枚")
        except: pass
        self.update_planned()

    def load_base_items(self):
        if not self.select_csv_path.get(): return
        self.base_items = {"a": [], "b": [], "c": [], "d": []}
        try:
            with open(self.select_csv_path.get(), encoding="utf-8", errors="ignore", newline="") as f:
                for row in csv.reader(f):
                    if len(row) < 2 or row[0].strip().lower() in ["", "group", "グループ"]: continue
                    g, code = row[0].strip().lower(), row[1].strip()
                    if g in self.base_items and code not in self.base_items[g]:
                        self.base_items[g].append(code)
        except: pass
        self.update_planned()

    def update_planned(self):
        for g in "abcd":
            base = len(self.base_items[g])
            loop = getattr(self, f"loop_{g}").get()
            mode = getattr(self, f"mode_{g}").get()
            planned = base * loop
            if mode == "append":
                planned += self.current_counts[g]
            self.planned_labels[g].config(text=f"→ 予定 {planned}枚")

    def select_yahoo_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if p: self.yahoo_csv_path.set(p)

    def select_select_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if p:
            self.select_csv_path.set(p)
            self.load_base_items()

    def select_html(self):
        p = filedialog.askopenfilename(filetypes=[("HTML", "*.html")])
        if p:
            self.html_path.set(p)
            self.update_current()

    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def start_processing(self):
        if not all([self.yahoo_csv_path.get(), self.select_csv_path.get(), self.html_path.get()]):
            messagebox.showwarning("確認", "すべてのファイルを選択してください")
            return
        self.run_btn.config(state="disabled", text="処理中...")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        self.log("処理開始")

        # 1. Yahoo!CSV
        yahoo_data = {}
        try:
            with open(self.yahoo_csv_path.get(), encoding="cp932", newline="") as f:
                for row in csv.DictReader(f):
                    code = row.get("code", "").strip()
                    urls = row.get("item-image-urls", "")
                    if code and urls:
                        yahoo_data[code] = urls.split(";")[0].strip()
            self.log(f"Yahoo!CSV読み込み完了：{len(yahoo_data)}件")
        except Exception as e:
            self.log(f"エラー：Yahoo!CSV → {e}")
            self.finish(); return

        # 2. HTML読み込み
        try:
            with open(self.html_path.get(), "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            self.log(f"HTML読み込み失敗：{e}"); self.finish(); return

        existing_max = {}
        for g in "abcd":
            matches = re.findall(rf'item-{g}(\d+)\.jpg', html_content)
            existing_max[g] = max([int(x) for x in matches]) if matches else 0

        # 3. 商品指定CSV（本処理）
        group_items = {"a": [], "b": [], "c": [], "d": []}
        try:
            with open(self.select_csv_path.get(), encoding="utf-8", errors="ignore", newline="") as f:
                for row in csv.reader(f):
                    if len(row) < 2 or row[0].strip().lower() in ["", "group", "グループ"]: continue
                    g, code = row[0].strip().lower(), row[1].strip()
                    if g in group_items and code in yahoo_data:
                        group_items[g].append(code)
        except Exception as e:
            self.log(f"商品指定CSVエラー：{e}"); self.finish(); return

        # 4. モード・ループ処理
        modes = {g: getattr(self, f"mode_{g}").get() for g in "abcd"}
        loops = {g: getattr(self, f"loop_{g}").get() for g in "abcd"}
        final_items = {"a": [], "b": [], "c": [], "d": []}
        counters = {}

        for g in "abcd":
            start = existing_max[g] + 1 if modes[g] == "append" else 1
            counters[g] = start
            for _ in range(loops[g]):
                for code in group_items[g]:
                    final_items[g].append((code, counters[g]))
                    counters[g] += 1

        # 5. 画像ダウンロード（ログ付き）
        os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True)
        success_count = 0
        for g in "abcd":
            for code, num in final_items[g]:
                url = yahoo_data[code]
                path = f"{OUTPUT_IMAGE_DIR}/item-{g}{num}.jpg"
                try:
                    r = requests.get(url, timeout=20)
                    r.raise_for_status()
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    w, h = img.size
                    s = min(w, h)
                    img = img.crop(((w-s)//2, (h-s)//2, (w+s)//2, (h+s)//2)).resize(IMAGE_SIZE, Image.LANCZOS)
                    img.save(path, "JPEG", quality=94, optimize=True)
                    self.log(f"ダウンロード成功 item-{g}{num}.jpg ({code})")
                    success_count += 1
                except Exception as e:
                    self.log(f"ダウンロード失敗 {code} → {e}")

        # 6. HTML更新
        backup = self.html_path.get() + ".backup"
        shutil.copy2(self.html_path.get(), backup)

        summary = []
        for g in "abcd":
            start_tag = f"<!-- ここからグループ{g} -->"
            end_tag = f"<!-- ここまでグループ{g} -->"
            new_divs = [f'<div><a href="{SHOP_BASE}{code}.html"><img src="images/item-{g}{num}.jpg" alt=""></a></div>'
                        for code, num in final_items[g]]

            if modes[g] == "replace":
                content = "\n".join(new_divs) if new_divs else "<!-- 空 -->"
                new_block = f"{start_tag}\n{content}\n{end_tag}"
                pattern = re.compile(f"{re.escape(start_tag)}.*?{re.escape(end_tag)}", re.DOTALL)
                old_count = len(re.findall(rf'item-{g}\d+\.jpg', pattern.search(html_content).group() if pattern.search(html_content) else ""))
                html_content = pattern.sub(new_block, html_content, count=1)
                summary.append(f"{g}：置換 {old_count}→{len(new_divs)}件")
            else:
                if new_divs:
                    insert = "\n" + "\n".join(new_divs) + "\n"
                    html_content = html_content.replace(end_tag, insert + end_tag)
                    summary.append(f"{g}：追加 +{len(new_divs)}件（計 {existing_max[g] + len(new_divs)}件）")
                else:
                    summary.append(f"{g}：変更なし（{existing_max[g]}件）")

        with open(self.html_path.get(), "w", encoding="utf-8") as f:
            f.write(html_content)

        self.log("\n処理完了！")
        for s in summary: self.log("   " + s)
        self.log(f"画像ダウンロード成功：{success_count}枚")
        self.log(f"バックアップ：{os.path.basename(backup)}")

        messagebox.showinfo("完了", "更新が正常に完了しました！\n\n" + "\n".join([s[4:] for s in summary]))
        self.finish()
        self.update_current()

    def finish(self):
        self.run_btn.config(state="normal", text="更新実行")

if __name__ == "__main__":
    root = tk.Tk()
    app = YumehanUpdater(root)
    root.mainloop()