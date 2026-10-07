import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import os

class ImageOverlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("画像一括貼り付けツール")
        self.preview_window_pos = None
        self.preview_window_size = None
        
        self.scale_mode = tk.StringVar(value="カンバスサイズ")
        self.last_output_dir = None
        self.drag_start_x = None
        self.drag_start_y = None
        
        # ★追加：プレビュー縮小モード（0: 元サイズ, 1: 1/2, 2: 1/4）
        self.preview_scale_mode = 0  # 0=full, 1=half, 2=quarter
        
        # メインウィンドウのグリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=0)
        self.root.rowconfigure(3, weight=0)
        self.root.rowconfigure(4, weight=0)
        self.root.rowconfigure(5, weight=0)
        self.root.rowconfigure(6, weight=0)  # 保存設定拡張のため追加

        # 1. 画像フォルダ選択
        self.folder_frame = tk.Frame(self.root)
        self.folder_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.folder_frame.columnconfigure(1, weight=1)

        self.folder_label = tk.Label(self.folder_frame, text="画像フォルダ:")
        self.folder_label.grid(row=0, column=0, padx=5, pady=5)

        self.folder_path_var = tk.StringVar()
        self.folder_entry = tk.Entry(self.folder_frame, textvariable=self.folder_path_var, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.browse_btn = tk.Button(self.folder_frame, text="参照", command=self.select_folder)
        self.browse_btn.grid(row=0, column=2, padx=5, pady=5)

        # 2. 貼り付け画像選択
        self.overlay_image_frame = tk.Frame(self.root)
        self.overlay_image_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.overlay_image_frame.columnconfigure(1, weight=1)

        self.overlay_image_label = tk.Label(self.overlay_image_frame, text="貼り付け画像:")
        self.overlay_image_label.grid(row=0, column=0, padx=5, pady=5)

        self.overlay_image_path_var = tk.StringVar()
        self.overlay_image_entry = tk.Entry(self.overlay_image_frame, textvariable=self.overlay_image_path_var, width=50)
        self.overlay_image_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.overlay_image_btn = tk.Button(self.overlay_image_frame, text="参照", command=self.select_overlay_image)
        self.overlay_image_btn.grid(row=0, column=2, padx=5, pady=5)

        # 3. 貼り付け画像の設定
        self.image_settings_group = tk.LabelFrame(self.root, text="貼り付け画像の設定", padx=5, pady=5)
        self.image_settings_group.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        self.image_settings_group.columnconfigure(0, weight=0)
        self.image_settings_group.columnconfigure(1, weight=1)

        self.scale_mode_label = tk.Label(self.image_settings_group, text="スケール基準:")
        self.scale_mode_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.scale_mode_combo = ttk.Combobox(self.image_settings_group, textvariable=self.scale_mode, 
                                           values=["貼り付け画像", "カンバスサイズ"], 
                                           state="readonly", width=12)
        self.scale_mode_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.scale_label = tk.Label(self.image_settings_group, text="拡大縮小 (%):")
        self.scale_label.grid(row=1, column=0, padx=5, pady=5)

        self.image_scale = tk.Scale(self.image_settings_group, from_=10, to=200, orient=tk.HORIZONTAL, length=200)
        self.image_scale.set(25)
        self.image_scale.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.alpha_label = tk.Label(self.image_settings_group, text="透明度 (%):")
        self.alpha_label.grid(row=2, column=0, padx=5, pady=5)

        self.image_alpha = tk.Scale(self.image_settings_group, from_=0, to=99, orient=tk.HORIZONTAL, length=200)
        self.image_alpha.set(0)
        self.image_alpha.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        self.rotation_label = tk.Label(self.image_settings_group, text="回転角度 (度):")
        self.rotation_label.grid(row=3, column=0, padx=5, pady=5)

        self.image_rotation = tk.Scale(self.image_settings_group, from_=-180, to=180, orient=tk.HORIZONTAL, length=200)
        self.image_rotation.set(0)
        self.image_rotation.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        self.apply_btn_frame = tk.Frame(self.image_settings_group)
        self.apply_btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        self.apply_btn = tk.Button(self.apply_btn_frame, text="反映", command=self.apply_preview, width=15, height=2)
        self.apply_btn.pack()

        # 4. 位置の指定
        self.position_group = tk.LabelFrame(self.root, text="位置の指定", padx=5, pady=5)
        self.position_group.grid(row=3, column=0, padx=5, pady=5, sticky="ew")

        self.position_mode_label = tk.Label(self.position_group, text="位置指定モード:")
        self.position_mode_label.grid(row=0, column=0, padx=5, pady=5)

        self.position_mode = tk.StringVar(value="比率設定")
        self.position_mode_list = ttk.Combobox(self.position_group, textvariable=self.position_mode, 
                                              values=["比率設定", "ピクセル設定"], state="readonly")
        self.position_mode_list.set("比率設定")
        self.position_mode_list.grid(row=0, column=1, padx=5, pady=5)

        self.origin_label = tk.Label(self.position_group, text="起点位置:")
        self.origin_label.grid(row=0, column=2, padx=5, pady=5)

        self.origin_list = ttk.Combobox(self.position_group, values=["左上", "右上", "中央", "左下", "右下"], state="readonly")
        self.origin_list.set("左上")
        self.origin_list.grid(row=0, column=3, padx=5, pady=5)

        # 5. 保存の設定（拡張）
        self.save_group = tk.LabelFrame(self.root, text="保存の設定", padx=5, pady=5)
        self.save_group.grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        self.save_group.columnconfigure(1, weight=1)

        # JPG品質
        self.quality_label = tk.Label(self.save_group, text="JPG保存品質:")
        self.quality_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.quality = tk.Scale(self.save_group, from_=1, to=100, orient=tk.HORIZONTAL)
        self.quality.set(95)
        self.quality.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 接尾辞
        self.suffix_label = tk.Label(self.save_group, text="出力ファイル接尾辞:")
        self.suffix_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.suffix_entry = tk.Entry(self.save_group)
        self.suffix_entry.insert(0, "_overlay")
        self.suffix_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # ★新規：解像度指定オプション
        self.resize_var = tk.BooleanVar(value=False)
        self.resize_check = tk.Checkbutton(self.save_group, text="保存解像度指定", variable=self.resize_var,
                                           command=self.toggle_resize_options)
        self.resize_check.grid(row=2, column=0, columnspan=2, pady=8, sticky="w")

        # 横・縦解像度
        self.width_label = tk.Label(self.save_group, text="横解像度 (px):")
        self.width_label.grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.width_var = tk.StringVar()
        self.width_entry = tk.Entry(self.save_group, textvariable=self.width_var, width=10)
        self.width_entry.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.height_label = tk.Label(self.save_group, text="縦解像度 (px):")
        self.height_label.grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.height_var = tk.StringVar()
        self.height_entry = tk.Entry(self.save_group, textvariable=self.height_var, width=10)
        self.height_entry.grid(row=4, column=1, padx=5, pady=2, sticky="w")

        # アスペクト比保持
        self.aspect_var = tk.BooleanVar(value=True)
        self.aspect_check = tk.Checkbutton(self.save_group, text="アスペクト比を保持", variable=self.aspect_var)
        self.aspect_check.grid(row=5, column=0, columnspan=2, pady=5, sticky="w")

        # 入力イベント（アスペクト比保持時自動計算）
        self.width_var.trace("w", self.on_resolution_change)
        self.height_var.trace("w", self.on_resolution_change)

        # 初期状態は無効
        self.toggle_resize_options()

        # 6. 実行ボタン
        self.button_frame = tk.Frame(self.root)
        self.button_frame.grid(row=5, column=0, padx=5, pady=10)

        self.run_btn = tk.Button(self.button_frame, text="実行", command=self.process_images, width=15, height=2)
        self.run_btn.grid(row=0, column=0, padx=5)

        self.continuous_run_btn = tk.Button(self.button_frame, text="連続実行", command=self.continuous_process_images, width=15, height=2)
        self.continuous_run_btn.grid(row=0, column=1, padx=5)

        # その他の変数
        self.preview_window = None
        self.image_x = None
        self.image_y = None
        self.relative_x = None
        self.relative_y = None
        self.offset_x = None
        self.offset_y = None
        self.image_files = []
        self.current_image_index = 0
        self.overlay_image = None
        self.overlay_image_id = None
        self.overlay_tk = None
        self.folder_path = None

    # 保存解像度指定の有効/無効切り替え
    def toggle_resize_options(self):
        state = "normal" if self.resize_var.get() else "disabled"
        self.width_entry.config(state=state)
        self.height_entry.config(state=state)
        self.aspect_check.config(state=state)

    # アスペクト比保持時の自動計算
    def on_resolution_change(self, *args):
        if not self.aspect_var.get() or not self.resize_var.get():
            return
        try:
            if self.width_var.get().strip() and not self.height_var.get().strip():
                w = int(self.width_var.get())
                if hasattr(self, 'current_base_img_size'):
                    orig_w, orig_h = self.current_base_img_size
                    h = int(w * orig_h / orig_w)
                    self.height_var.set(str(h))
            elif self.height_var.get().strip() and not self.width_var.get().strip():
                h = int(self.height_var.get())
                if hasattr(self, 'current_base_img_size'):
                    orig_w, orig_h = self.current_base_img_size
                    w = int(h * orig_w / orig_h)
                    self.width_var.set(str(w))
        except:
            pass

    def apply_preview(self):
        if not hasattr(self, 'folder_path'):
            messagebox.showerror("エラー", "フォルダを指定してください")
            return
        if not hasattr(self, 'overlay_image') or self.overlay_image is None:
            messagebox.showerror("エラー", "貼り付け画像を選択してください")
            return
            
        mode = self.position_mode.get()
        if mode == "ピクセル設定":
            if self.offset_x is None or self.offset_y is None:
                self.offset_x = 50
                self.offset_y = 50
        else:
            if self.relative_x is None or self.relative_y is None:
                self.relative_x = 0.5
                self.relative_y = 0.5
        
        if not self.image_files:
            messagebox.showwarning("警告", "プレビュー用の画像がありません")
            return
            
        self.show_preview()

    # プレビュー縮小モードのトグル（0→1→2→0）
    def toggle_preview_scale(self):
        self.preview_scale_mode = (self.preview_scale_mode + 1) % 3
        self.show_preview()

    def get_preview_scale_factor(self):
        if self.preview_scale_mode == 0:
            return 1.0
        elif self.preview_scale_mode == 1:
            return 0.5
        else:
            return 0.25

    def get_preview_button_text(self):
        if self.preview_scale_mode == 0:
            return "プレビュー：元サイズ"
        elif self.preview_scale_mode == 1:
            return "プレビュー：1/2"
        else:
            return "プレビュー：1/4"

    def process_images(self):
        if not hasattr(self, 'folder_path'):
            messagebox.showerror("エラー", "フォルダと画像位置を指定してください")
            return
        if not hasattr(self, 'overlay_image') or self.overlay_image is None:
            messagebox.showerror("エラー", "貼り付け画像を選択してください")
            return
            
        mode = self.position_mode.get()
        if mode == "ピクセル設定":
            if self.offset_x is None or self.offset_y is None:
                messagebox.showerror("エラー", "画像位置を指定してください")
                return
        else:
            if self.relative_x is None or self.relative_y is None:
                messagebox.showerror("エラー", "画像位置を指定してください")
                return
            
        output_dir = os.path.join(self.folder_path, "output")
        os.makedirs(output_dir, exist_ok=True)
        self.last_output_dir = output_dir
        
        rotation = self.image_rotation.get()
        quality = self.quality.get()
        suffix = self.suffix_entry.get().strip()
        
        # 保存解像度取得
        target_width = None
        target_height = None
        if self.resize_var.get():
            try:
                if self.width_var.get().strip():
                    target_width = int(self.width_var.get())
                if self.height_var.get().strip():
                    target_height = int(self.height_var.get())
                if target_width is None and target_height is None:
                    messagebox.showerror("エラー", "解像度指定が有効な場合、横または縦のいずれかを入力してください")
                    return
            except ValueError:
                messagebox.showerror("エラー", "解像度は整数で入力してください")
                return
        
        processed_count = 0
        error_count = 0
        
        for filename in self.image_files:
            try:
                img_path = os.path.join(self.folder_path, filename)
                base_img = Image.open(img_path).convert('RGBA')
                
                # 現在の画像サイズを記憶（アスペクト比計算用）
                self.current_base_img_size = base_img.size
                
                effective_scale = self.get_effective_scale(base_img.width, base_img.height)
                
                new_width = int(self.overlay_image.width * effective_scale)
                new_height = int(self.overlay_image.height * effective_scale)
                resized_overlay = self.overlay_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                if rotation != 0:
                    resized_overlay = resized_overlay.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
                
                overlay_alpha = resized_overlay.split()[3]
                overlay_alpha = overlay_alpha.point(lambda p: p * (1 - self.image_alpha.get() / 100.0))
                overlay_rgb = resized_overlay.split()[:3]
                resized_overlay = Image.merge('RGBA', (*overlay_rgb, overlay_alpha))
                
                img_width, img_height = base_img.size
                origin = self.origin_list.get()
                
                if mode == "ピクセル設定":
                    center_x = self.offset_x
                    center_y = self.offset_y
                    if origin == "左上":
                        pass
                    elif origin == "右上":
                        center_x = img_width - center_x
                    elif origin == "中央":
                        center_x = img_width / 2 + center_x
                        center_y = img_height / 2 + center_y
                    elif origin == "左下":
                        center_y = img_height - center_y
                    elif origin == "右下":
                        center_x = img_width - center_x
                        center_y = img_height - center_y
                else:
                    if origin == "左上":
                        center_x = self.relative_x * img_width
                        center_y = self.relative_y * img_height
                    elif origin == "右上":
                        center_x = img_width - self.relative_x * img_width
                        center_y = self.relative_y * img_height
                    elif origin == "中央":
                        center_x = img_width / 2 + self.relative_x * img_width
                        center_y = img_height / 2 + self.relative_y * img_height
                    elif origin == "左下":
                        center_x = self.relative_x * img_width
                        center_y = img_height - self.relative_y * img_height
                    elif origin == "右下":
                        center_x = img_width - self.relative_x * img_width
                        center_y = img_height - self.relative_y * img_height
                
                new_width, new_height = resized_overlay.size
                actual_x = int(center_x - new_width / 2)
                actual_y = int(center_y - new_height / 2)
                
                overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
                overlay.paste(resized_overlay, (actual_x, actual_y))
                img = Image.alpha_composite(base_img, overlay).convert('RGB')
                
                # ★保存時リサイズ処理
                if target_width or target_height:
                    if self.aspect_var.get():
                        img = img.resize((target_width or int(img.width * target_height / img.height),
                                          target_height or int(img.height * target_width / img.width)),
                                         Image.Resampling.LANCZOS)
                    else:
                        img = img.resize((target_width or img.width, target_height or img.height),
                                         Image.Resampling.LANCZOS)
                
                base_name = os.path.splitext(filename)[0]
                output_filename = f"{base_name}{suffix}.jpg"
                output_path = os.path.join(output_dir, output_filename)
                img.save(output_path, quality=quality)
                processed_count += 1
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                error_count += 1
                continue
                    
        messagebox.showinfo("完了", f"処理が完了しました\n"
                                 f"出力先: {output_dir}\n"
                                 f"成功: {processed_count}枚\n"
                                 f"失敗: {error_count}枚")

    # continuous_process_images も process_images と同様にリサイズ対応（省略せず同じ処理をコピー）
    def continuous_process_images(self):
        # process_images とほぼ同じ処理（出力後に自動遷移）
        if not hasattr(self, 'folder_path'):
            messagebox.showerror("エラー", "フォルダを指定してください")
            return
        if not hasattr(self, 'overlay_image') or self.overlay_image is None:
            messagebox.showerror("エラー", "貼り付け画像を選択してください")
            return
            
        mode = self.position_mode.get()
        if mode == "ピクセル設定":
            if self.offset_x is None or self.offset_y is None:
                messagebox.showerror("エラー", "画像位置を指定してください")
                return
        else:
            if self.relative_x is None or self.relative_y is None:
                messagebox.showerror("エラー", "画像位置を指定してください")
                return
        
        output_dir = os.path.join(self.folder_path, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        rotation = self.image_rotation.get()
        quality = self.quality.get()
        suffix = self.suffix_entry.get().strip()
        
        target_width = None
        target_height = None
        if self.resize_var.get():
            try:
                if self.width_var.get().strip():
                    target_width = int(self.width_var.get())
                if self.height_var.get().strip():
                    target_height = int(self.height_var.get())
                if target_width is None and target_height is None:
                    messagebox.showerror("エラー", "解像度指定が有効な場合、横または縦のいずれかを入力してください")
                    return
            except ValueError:
                messagebox.showerror("エラー", "解像度は整数で入力してください")
                return
        
        processed_count = 0
        error_count = 0
        
        for filename in self.image_files:
            try:
                img_path = os.path.join(self.folder_path, filename)
                base_img = Image.open(img_path).convert('RGBA')
                self.current_base_img_size = base_img.size
                
                effective_scale = self.get_effective_scale(base_img.width, base_img.height)
                new_width = int(self.overlay_image.width * effective_scale)
                new_height = int(self.overlay_image.height * effective_scale)
                resized_overlay = self.overlay_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                if rotation != 0:
                    resized_overlay = resized_overlay.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
                
                overlay_alpha = resized_overlay.split()[3]
                overlay_alpha = overlay_alpha.point(lambda p: p * (1 - self.image_alpha.get() / 100.0))
                overlay_rgb = resized_overlay.split()[:3]
                resized_overlay = Image.merge('RGBA', (*overlay_rgb, overlay_alpha))
                
                img_width, img_height = base_img.size
                origin = self.origin_list.get()
                
                if mode == "ピクセル設定":
                    center_x = self.offset_x
                    center_y = self.offset_y
                    if origin == "左上": pass
                    elif origin == "右上": center_x = img_width - center_x
                    elif origin == "中央":
                        center_x = img_width / 2 + center_x
                        center_y = img_height / 2 + center_y
                    elif origin == "左下": center_y = img_height - center_y
                    elif origin == "右下":
                        center_x = img_width - center_x
                        center_y = img_height - center_y
                else:
                    if origin == "左上":
                        center_x = self.relative_x * img_width
                        center_y = self.relative_y * img_height
                    elif origin == "右上":
                        center_x = img_width - self.relative_x * img_width
                        center_y = self.relative_y * img_height
                    elif origin == "中央":
                        center_x = img_width / 2 + self.relative_x * img_width
                        center_y = img_height / 2 + self.relative_y * img_height
                    elif origin == "左下":
                        center_x = self.relative_x * img_width
                        center_y = img_height - self.relative_y * img_height
                    elif origin == "右下":
                        center_x = img_width - self.relative_x * img_width
                        center_y = img_height - self.relative_y * img_height
                
                new_width, new_height = resized_overlay.size
                actual_x = int(center_x - new_width / 2)
                actual_y = int(center_y - new_height / 2)
                
                overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
                overlay.paste(resized_overlay, (actual_x, actual_y))
                img = Image.alpha_composite(base_img, overlay).convert('RGB')
                
                if target_width or target_height:
                    if self.aspect_var.get():
                        img = img.resize((target_width or int(img.width * target_height / img.height),
                                          target_height or int(img.height * target_width / img.width)),
                                         Image.Resampling.LANCZOS)
                    else:
                        img = img.resize((target_width or img.width, target_height or img.height),
                                         Image.Resampling.LANCZOS)
                
                base_name = os.path.splitext(filename)[0]
                output_filename = f"{base_name}{suffix}.jpg"
                output_path = os.path.join(output_dir, output_filename)
                img.save(output_path, quality=quality)
                processed_count += 1
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                error_count += 1
                continue
        
        self.last_output_dir = output_dir
        self.folder_path = output_dir
        self.folder_path_var.set(output_dir)
        
        self.image_files = [f for f in os.listdir(self.folder_path) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        if self.image_files:
            self.current_image_index = 0
            self.show_preview()
            messagebox.showinfo("連続実行完了", f"処理完了後、出力フォルダに自動遷移しました\n"
                                               f"フォルダ: {output_dir}\n"
                                               f"成功: {processed_count}枚\n"
                                               f"失敗: {error_count}枚\n"
                                               f"プレビューが更新されました")
        else:
            messagebox.showwarning("警告", f"出力フォルダに画像が見つかりません: {output_dir}")

    def calculate_canvas_ratio_scale(self, base_width, base_height):
        if not self.overlay_image:
            return 1.0
        scale_value = self.image_scale.get() / 100.0
        overlay_w, overlay_h = self.overlay_image.size
        bg_aspect = base_width / base_height
        overlay_aspect = overlay_w / overlay_h
        if bg_aspect > overlay_aspect:
            relative_scale = base_width / overlay_w
        else:
            relative_scale = base_height / overlay_h
        return scale_value * relative_scale

    def get_effective_scale(self, base_width, base_height):
        if self.scale_mode.get() == "カンバスサイズ":
            return self.calculate_canvas_ratio_scale(base_width, base_height)
        else:
            return self.image_scale.get() / 100.0

    def create_alpha_applied_overlay(self, base_img):
        effective_scale = self.get_effective_scale(base_img.width, base_img.height)
        new_width = int(self.overlay_image.width * effective_scale)
        new_height = int(self.overlay_image.height * effective_scale)
        resized_overlay = self.overlay_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        rotation = self.image_rotation.get()
        if rotation != 0:
            resized_overlay = resized_overlay.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
        overlay_alpha = resized_overlay.split()[3]
        overlay_alpha = overlay_alpha.point(lambda p: p * (1 - self.image_alpha.get() / 100.0))
        overlay_rgb = resized_overlay.split()[:3]
        resized_overlay = Image.merge('RGBA', (*overlay_rgb, overlay_alpha))
        return resized_overlay

    def calculate_position(self, base_img):
        mode = self.position_mode.get()
        origin = self.origin_list.get()
        initial_x = self.image_x if self.image_x else base_img.width / 2
        initial_y = self.image_y if self.image_y else base_img.height / 2
        
        if mode == "ピクセル設定":
            center_x = initial_x
            center_y = initial_y
        else:
            if origin == "左上":
                center_x = self.relative_x * base_img.width if self.relative_x is not None else base_img.width / 2
                center_y = self.relative_y * base_img.height if self.relative_y is not None else base_img.height / 2
            elif origin == "右上":
                center_x = base_img.width - (self.relative_x * base_img.width if self.relative_x is not None else base_img.width / 2)
                center_y = self.relative_y * base_img.height if self.relative_y is not None else base_img.height / 2
            elif origin == "中央":
                center_x = base_img.width / 2 + (self.relative_x * base_img.width if self.relative_x is not None else 0)
                center_y = base_img.height / 2 + (self.relative_y * base_img.height if self.relative_y is not None else 0)
            elif origin == "左下":
                center_x = self.relative_x * base_img.width if self.relative_x is not None else base_img.width / 2
                center_y = base_img.height - (self.relative_y * base_img.height if self.relative_y is not None else base_img.height / 2)
            elif origin == "右下":
                center_x = base_img.width - (self.relative_x * base_img.width if self.relative_x is not None else base_img.width / 2)
                center_y = base_img.height - (self.relative_y * base_img.height if self.relative_y is not None else base_img.height / 2)
        return center_x, center_y

    def update_position_info(self, base_img, center_x, center_y):
        mode = self.position_mode.get()
        origin = self.origin_list.get()
        self.image_x = center_x
        self.image_y = center_y
        if mode == "ピクセル設定":
            self.offset_x = self.image_x
            self.offset_y = self.image_y
        else:
            img_width = base_img.width
            img_height = base_img.height
            if origin == "左上":
                self.relative_x = self.image_x / img_width
                self.relative_y = self.image_y / img_height
            elif origin == "右上":
                self.relative_x = (img_width - self.image_x) / img_width
                self.relative_y = self.image_y / img_height
            elif origin == "中央":
                self.relative_x = (self.image_x - img_width / 2) / img_width
                self.relative_y = (self.image_y - img_height / 2) / img_height
            elif origin == "左下":
                self.relative_x = self.image_x / img_width
                self.relative_y = (img_height - self.image_y) / img_height
            elif origin == "右下":
                self.relative_x = (img_width - self.image_x) / img_width
                self.relative_y = (img_height - self.image_y) / img_height

    def start_drag(self, event):
        factor = self.get_preview_scale_factor()
        self.drag_start_x = (event.x + self.canvas.canvasx(0)) / factor
        self.drag_start_y = (event.y + self.canvas.canvasy(0)) / factor

    def drag_image(self, event):
        if self.drag_start_x is None or self.drag_start_y is None:
            self.start_drag(event)
            return
        factor = self.get_preview_scale_factor()
        current_x = (event.x + self.canvas.canvasx(0)) / factor
        current_y = (event.y + self.canvas.canvasy(0)) / factor
        dx = current_x - self.drag_start_x
        dy = current_y - self.drag_start_y
        if self.overlay_image_id:
            self.canvas.move(self.overlay_image_id, dx * factor, dy * factor)
        self.drag_start_x = current_x
        self.drag_start_y = current_y

    def stop_drag(self, event):
        if self.overlay_image_id:
            coords = self.canvas.coords(self.overlay_image_id)
            actual_x = coords[0]
            actual_y = coords[1]
            factor = self.get_preview_scale_factor()
            img_path = os.path.join(self.folder_path, self.image_files[self.current_image_index])
            base_img = Image.open(img_path).convert('RGBA')
            alpha_applied_overlay = self.create_alpha_applied_overlay(base_img)
            new_width, new_height = alpha_applied_overlay.size
            self.image_x = (actual_x / factor) + new_width / 2
            self.image_y = (actual_y / factor) + new_height / 2
            self.update_position_info(base_img, self.image_x, self.image_y)
        self.drag_start_x = None
        self.drag_start_y = None

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_path = folder_path
            self.folder_path_var.set(folder_path)
            self.image_files = [f for f in os.listdir(self.folder_path) 
                              if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            if self.image_files:
                self.current_image_index = 0
                self.show_background_preview()
            else:
                messagebox.showwarning("警告", "選択したフォルダに画像が見つかりません")

    def show_background_preview(self):
        # 背景プレビューは変更なし（オーバーレイなし）
        if not self.image_files:
            return
        if self.preview_window:
            self.preview_window.destroy()
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title(f"背景プレビュー ({self.current_image_index + 1}/{len(self.image_files)})")
        if self.preview_window_size and self.preview_window_pos:
            geom = f"{self.preview_window_size[0]}x{self.preview_window_size[1]}+{self.preview_window_pos[0]}+{self.preview_window_pos[1]}"
            self.preview_window.geometry(geom)
        else:
            self.preview_window.geometry("800x600")
        self.preview_window.grid_rowconfigure(0, weight=1)
        self.preview_window.grid_rowconfigure(1, weight=0)
        self.preview_window.grid_columnconfigure(0, weight=1)

        img_path = os.path.join(self.folder_path, self.image_files[self.current_image_index])
        base_img = Image.open(img_path).convert('RGBA')
        self.preview_img = ImageTk.PhotoImage(base_img)

        scroll_frame = tk.Frame(self.preview_window)
        scroll_frame.grid(row=0, column=0, sticky="nsew")
        h_scrollbar = tk.Scrollbar(scroll_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar = tk.Scrollbar(scroll_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(scroll_frame, width=800, height=600, 
                               xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)

        self.canvas.config(scrollregion=(0, 0, base_img.width, base_img.height))
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_img)

        btn_frame = tk.Frame(self.preview_window)
        btn_frame.grid(row=1, column=0, pady=5, padx=5, sticky="ew")
        self.prev_btn = tk.Button(btn_frame, text="戻る", command=self.prev_image, width=10)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        self.next_btn = tk.Button(btn_frame, text="次へ", command=self.next_image, width=10)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        self.update_button_state()
        self.preview_window.bind("<Configure>", self.save_window_geometry)

    def select_overlay_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif"), ("All files", "*.*")]
        )
        if file_path:
            self.overlay_image_path = file_path
            self.overlay_image_path_var.set(file_path)
            try:
                self.overlay_image = Image.open(file_path).convert('RGBA')
            except Exception as e:
                messagebox.showerror("エラー", f"画像の読み込みに失敗しました: {str(e)}")
                self.overlay_image = None
                self.overlay_image_path_var.set("")
                return
            if self.image_files:
                self.show_preview()

    def show_preview(self):
        if not self.image_files or not hasattr(self, 'overlay_image') or self.overlay_image is None:
            return
        if self.preview_window:
            self.preview_window.destroy()
            
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title(f"位置指定プレビュー ({self.current_image_index + 1}/{len(self.image_files)})")
        if self.preview_window_size and self.preview_window_pos:
            geom = f"{self.preview_window_size[0]}x{self.preview_window_size[1]}+{self.preview_window_pos[0]}+{self.preview_window_pos[1]}"
            self.preview_window.geometry(geom)
        else:
            self.preview_window.geometry("800x600")
        
        self.preview_window.grid_rowconfigure(0, weight=1)
        self.preview_window.grid_rowconfigure(1, weight=0)
        self.preview_window.grid_columnconfigure(0, weight=1)

        img_path = os.path.join(self.folder_path, self.image_files[self.current_image_index])
        base_img = Image.open(img_path).convert('RGBA')
        
        factor = self.get_preview_scale_factor()
        display_base_img = base_img.resize((int(base_img.width * factor), int(base_img.height * factor)), Image.Resampling.LANCZOS)
        self.preview_img = ImageTk.PhotoImage(display_base_img)

        scroll_frame = tk.Frame(self.preview_window)
        scroll_frame.grid(row=0, column=0, sticky="nsew")
        h_scrollbar = tk.Scrollbar(scroll_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar = tk.Scrollbar(scroll_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(scroll_frame, width=800, height=600, 
                               xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)

        self.canvas.config(scrollregion=(0, 0, display_base_img.width, display_base_img.height))
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_img)

        alpha_applied_overlay = self.create_alpha_applied_overlay(base_img)
        center_x, center_y = self.calculate_position(base_img)
        new_width, new_height = alpha_applied_overlay.size
        actual_x = center_x - new_width / 2
        actual_y = center_y - new_height / 2

        display_overlay = alpha_applied_overlay.resize((int(new_width * factor), int(new_height * factor)), Image.Resampling.LANCZOS)
        display_actual_x = actual_x * factor
        display_actual_y = actual_y * factor

        self.overlay_tk = ImageTk.PhotoImage(display_overlay)
        self.overlay_image_id = self.canvas.create_image(display_actual_x, display_actual_y, image=self.overlay_tk, anchor="nw")

        self.update_position_info(base_img, center_x, center_y)

        self.drag_start_x = None
        self.drag_start_y = None
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_image)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)

        btn_frame = tk.Frame(self.preview_window)
        btn_frame.grid(row=1, column=0, pady=5, padx=5, sticky="ew")
        self.prev_btn = tk.Button(btn_frame, text="戻る", command=self.prev_image_with_preview, width=10)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        self.next_btn = tk.Button(btn_frame, text="次へ", command=self.next_image_with_preview, width=10)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # プレビュー縮小トグルボタン（3段階）
        self.scale_btn = tk.Button(btn_frame, text=self.get_preview_button_text(),
                                   command=self.toggle_preview_scale, width=18)
        self.scale_btn.pack(side=tk.LEFT, padx=10)

        self.update_button_state()
        self.preview_window.bind("<Configure>", self.save_window_geometry)

    def prev_image_with_preview(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.show_preview()

    def next_image_with_preview(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.show_preview()

    def save_window_geometry(self, event):
        if self.preview_window and event.widget == self.preview_window:
            width = self.preview_window.winfo_width()
            height = self.preview_window.winfo_height()
            x = self.preview_window.winfo_x()
            y = self.preview_window.winfo_y()
            if width >= 200 and height >= 200:
                self.preview_window_size = (width, height)
                self.preview_window_pos = (x, y)

    def update_button_state(self):
        if hasattr(self, 'prev_btn'):
            self.prev_btn.config(state="disabled" if self.current_image_index == 0 else "normal")
        if hasattr(self, 'next_btn'):
            self.next_btn.config(state="disabled" if self.current_image_index == len(self.image_files) - 1 else "normal")

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.show_background_preview()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.show_background_preview()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageOverlayApp(root)
    root.mainloop()