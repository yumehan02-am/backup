import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

class TableGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Table Tag Generator")
        self.rows = 3
        self.cols = 3
        self.table_data = [[{"tag": "td", "text": "", "rowspan": 1, "colspan": 1, "class": ""} 
                            for _ in range(self.cols)] for _ in range(self.rows)]
        self.merged_cells = set()
        self.selected_cells = set()
        self.start_row = None
        self.start_col = None
        self.cell_width = 80  # セルの幅（ピクセル）
        self.cell_height = 40  # セルの高さ（ピクセル）

        self.create_widgets()

    def create_widgets(self):
        size_frame = ttk.Frame(self.root)
        size_frame.pack(pady=5)
        ttk.Label(size_frame, text="Rows:").pack(side=tk.LEFT)
        self.row_spin = ttk.Spinbox(size_frame, from_=1, to=20, width=5, command=self.resize_table)
        self.row_spin.set(self.rows)
        self.row_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="Cols:").pack(side=tk.LEFT)
        self.col_spin = ttk.Spinbox(size_frame, from_=1, to=20, width=5, command=self.resize_table)
        self.col_spin.set(self.cols)
        self.col_spin.pack(side=tk.LEFT, padx=5)

        self.table_frame = ttk.Frame(self.root)
        self.table_frame.pack(pady=10)
        self.render_table()

        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=5)
        ttk.Button(button_frame, text="td ↔ th", command=self.toggle_tag).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="結合", command=self.merge_cells).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="分割", command=self.split_cells).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="文字入力", command=self.set_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="クラス設定", command=self.set_class).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="HTML出力", command=self.show_html).pack(side=tk.LEFT, padx=5)

        self.preview = tk.Text(self.root, height=10, width=50)
        self.preview.pack(pady=10)
        self.update_preview()

    def render_table(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) in self.merged_cells:
                    continue
                cell = self.table_data[r][c]
                text = cell["text"] if cell["text"] else f"{r},{c}"
                bg = "lightgrey" if cell["tag"] == "th" else "white"
                label = tk.Label(self.table_frame, text=text, bg=bg, relief="solid", width=10, height=2)
                label.grid(row=r, column=c, rowspan=cell["rowspan"], columnspan=cell["colspan"])
                label.bind("<Button-1>", lambda e, row=r, col=c: self.start_drag(e, row, col))
                label.bind("<B1-Motion>", lambda e: self.drag(e))
                label.bind("<ButtonRelease-1>", lambda e: self.end_drag())

    def start_drag(self, event, row, col):
        self.start_row = row
        self.start_col = col
        self.selected_cells = {(row, col)}
        self.update_selection()
        print(f"Start drag at: ({row}, {col})")

    def drag(self, event):
        if self.start_row is None or self.start_col is None:
            return

        # マウス座標からグリッド座標を計算
        x = event.x_root - self.table_frame.winfo_rootx()
        y = event.y_root - self.table_frame.winfo_rooty()
        current_row = min(max(y // self.cell_height, 0), self.rows - 1)
        current_col = min(max(x // self.cell_width, 0), self.cols - 1)

        # 選択範囲を更新
        self.selected_cells.clear()
        for r in range(min(self.start_row, current_row), max(self.start_row, current_row) + 1):
            for c in range(min(self.start_col, current_col), max(self.start_col, current_col) + 1):
                if 0 <= r < self.rows and 0 <= c < self.cols and (r, c) not in self.merged_cells:
                    self.selected_cells.add((r, c))
        self.update_selection()
        print(f"Dragging: {self.selected_cells}")

    def end_drag(self):
        self.start_row = None
        self.start_col = None
        print(f"End drag, selected: {self.selected_cells}")

    def update_selection(self):
        for r in range(self.rows):
            for c in range(self.cols):
                widget = self.table_frame.grid_slaves(row=r, column=c)
                if widget:
                    bg = "yellow" if (r, c) in self.selected_cells else \
                         ("lightgrey" if self.table_data[r][c]["tag"] == "th" else "white")
                    widget[0].config(bg=bg)

    def resize_table(self):
        new_rows = int(self.row_spin.get())
        new_cols = int(self.col_spin.get())
        if new_rows != self.rows or new_cols != self.cols:
            self.rows = new_rows
            self.cols = new_cols
            self.table_data = [[{"tag": "td", "text": "", "rowspan": 1, "colspan": 1, "class": ""} 
                                for _ in range(self.cols)] for _ in range(self.rows)]
            self.merged_cells.clear()
            self.selected_cells.clear()
            self.render_table()
            self.update_preview()

    def toggle_tag(self):
        if not self.selected_cells:
            messagebox.showwarning("警告", "セルを選択してください。")
            return
        for r, c in self.selected_cells:
            if (r, c) not in self.merged_cells:
                cell = self.table_data[r][c]
                cell["tag"] = "th" if cell["tag"] == "td" else "td"
        self.render_table()
        self.update_preview()

    def merge_cells(self):
        if not self.selected_cells:
            messagebox.showwarning("警告", "セルを選択してください。")
            return
        min_r = min(r for r, _ in self.selected_cells)
        min_c = min(c for _, c in self.selected_cells)
        max_r = max(r for r, _ in self.selected_cells)
        max_c = max(c for _, c in self.selected_cells)

        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                if (r, c) in self.merged_cells:
                    messagebox.showwarning("警告", "すでに結合されたセルを含む範囲は結合できません。")
                    return

        self.table_data[min_r][min_c]["rowspan"] = max_r - min_r + 1
        self.table_data[min_r][min_c]["colspan"] = max_c - min_c + 1
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                if (r, c) != (min_r, min_c):
                    self.merged_cells.add((r, c))
        self.render_table()
        self.update_preview()

    def split_cells(self):
        if not self.selected_cells:
            messagebox.showwarning("警告", "セルを選択してください。")
            return
        for r, c in self.selected_cells:
            cell = self.table_data[r][c]
            if cell["rowspan"] > 1 or cell["colspan"] > 1:
                rowspan, colspan = cell["rowspan"], cell["colspan"]
                cell["rowspan"] = 1
                cell["colspan"] = 1
                for i in range(r, r + rowspan):
                    for j in range(c, c + colspan):
                        self.merged_cells.discard((i, j))
        self.render_table()
        self.update_preview()

    def set_text(self):
        if not self.selected_cells:
            messagebox.showwarning("警告", "セルを選択してください。")
            return
        text = simpledialog.askstring("入力", "セルに設定するテキストを入力してください:")
        if text:
            for r, c in self.selected_cells:
                if (r, c) not in self.merged_cells:
                    self.table_data[r][c]["text"] = text
        self.render_table()
        self.update_preview()

    def set_class(self):
        if not self.selected_cells:
            messagebox.showwarning("警告", "セルを選択してください。")
            return
        class_name = simpledialog.askstring("入力", "クラス名を入力してください:")
        if class_name:
            for r, c in self.selected_cells:
                if (r, c) not in self.merged_cells:
                    self.table_data[r][c]["class"] = class_name
        self.update_preview()

    def generate_html(self):
        html = "<table>\n"
        for r in range(self.rows):
            html += "  <tr>\n"
            c = 0
            while c < self.cols:
                if (r, c) in self.merged_cells:
                    c += 1
                    continue
                cell = self.table_data[r][c]
                tag = cell["tag"]
                attrs = []
                if cell["rowspan"] > 1:
                    attrs.append(f'rowspan="{cell["rowspan"]}"')
                if cell["colspan"] > 1:
                    attrs.append(f'colspan="{cell["colspan"]}"')
                if cell["class"]:
                    attrs.append(f'class="{cell["class"]}"')
                attr_str = " " + " ".join(attrs) if attrs else ""
                html += f"    <{tag}{attr_str}>{cell['text']}</{tag}>\n"
                c += cell["colspan"]
            html += "  </tr>\n"
        html += "</table>"
        return html

    def update_preview(self):
        self.preview.delete(1.0, tk.END)
        self.preview.insert(tk.END, self.generate_html())

    def show_html(self):
        html = self.generate_html()
        messagebox.showinfo("HTML出力", html)

if __name__ == "__main__":
    root = tk.Tk()
    app = TableGeneratorGUI(root)
    root.mainloop()