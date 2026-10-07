import os
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageGrab
import pytesseract
import requests
from io import BytesIO

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windowsの場合

class ScreenshotSaver:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Saver OCR")
        self.save_path = os.path.join(os.path.expanduser("~/Desktop"))
        
        # GUI Elements
        self.label = tk.Label(root, text="保存場所:")
        self.path_entry = tk.Entry(root, width=30)
        self.path_entry.insert(0, self.save_path)
        self.browse_button = tk.Button(root, text="参照", command=self.browse_folder)
        
        self.quality_label = tk.Label(root, text="JPG品質:")
        self.quality_var = tk.IntVar(value=95)
        self.quality_scale = tk.Scale(root, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.quality_var)
        self.quality_entry = tk.Entry(root, textvariable=self.quality_var, width=5)
        
        # OCRチェックボックス
        self.ocr_var = tk.BooleanVar(value=False)
        self.ocr_checkbox = tk.Checkbutton(root, text="Tesseract OCRでテキストを保存", variable=self.ocr_var)
        
        # バッチ処理チェックボックス
        self.batch_var = tk.BooleanVar(value=False)
        self.batch_checkbox = tk.Checkbutton(root, text="複数のファイルを一括処理", variable=self.batch_var)
        
        # Configure grid
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=0)
        self.root.rowconfigure(4, weight=1)
        
        # Grid the widgets
        self.label.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.browse_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.quality_label.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.quality_scale.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.quality_entry.grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.ocr_checkbox.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        self.batch_checkbox.grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        
        # Log window
        self.log_frame = tk.Frame(root)
        self.log_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")
        
        self.log_text = tk.Text(self.log_frame, height=3, width=50, bg="white")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text.config(yscrollcommand=self.scrollbar.set)
        
        # Initialize last states
        self.last_clipboard = None
        self.last_file_list = None
        self.last_url = None
        self.initialize_last_states()
        
        # Start monitoring
        self.monitor_clipboard()
        
        # Initial log message
        self.log_message("クリップボードを監視中...")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_path = folder
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, self.save_path)

    def initialize_last_states(self):
        clipboard_content = ImageGrab.grabclipboard()
        if isinstance(clipboard_content, Image.Image):
            self.last_clipboard = clipboard_content
        elif isinstance(clipboard_content, list):
            self.last_file_list = clipboard_content
        else:
            try:
                text = self.root.clipboard_get()
                if text.startswith(("http://", "https://")):
                    self.last_url = text
            except tk.TclError:
                pass

    def images_equal(self, img1, img2):
        if img1 is None or img2 is None:
            return img1 == img2
        return img1.size == img2.size and img1.mode == img2.mode and img1.tobytes() == img2.tobytes()

    def monitor_clipboard(self):
        try:
            clipboard_content = ImageGrab.grabclipboard()
            if isinstance(clipboard_content, Image.Image):
                if self.last_clipboard is None or not self.images_equal(clipboard_content, self.last_clipboard):
                    self.save_image(clipboard_content)
                    self.last_clipboard = clipboard_content
                    self.last_file_list = None
                    self.last_url = None
            elif isinstance(clipboard_content, list):
                if clipboard_content != self.last_file_list:
                    if self.batch_var.get():
                        for filepath in clipboard_content:
                            try:
                                image = Image.open(filepath)
                                self.save_image(image)
                            except Exception as e:
                                self.log_message(f"Error opening file {filepath}: {e}")
                    else:
                        if clipboard_content:
                            filepath = clipboard_content[0]
                            try:
                                image = Image.open(filepath)
                                self.save_image(image)
                            except Exception as e:
                                self.log_message(f"Error opening file {filepath}: {e}")
                    self.last_file_list = clipboard_content
                    self.last_clipboard = None
                    self.last_url = None
            else:
                try:
                    text = self.root.clipboard_get()
                    if text.startswith(("http://", "https://")) and text != self.last_url:
                        try:
                            response = requests.get(text)
                            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
                                image_data = BytesIO(response.content)
                                image = Image.open(image_data)
                                self.save_image(image)
                                self.last_url = text
                                self.last_clipboard = None
                                self.last_file_list = None
                            else:
                                self.log_message(f"URL {text} does not point to an image.")
                        except Exception as e:
                            self.log_message(f"Error downloading URL {text}: {e}")
                except tk.TclError:
                    pass
        except Exception as e:
            self.log_message(f"エラー: {str(e)}")
        self.root.after(100, self.monitor_clipboard)

    def save_image(self, image):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"img_{timestamp}"
        filename_jpg = base_filename + ".jpg"
        filepath_jpg = os.path.join(self.save_path, filename_jpg)
        counter = 1
        while os.path.exists(filepath_jpg):
            filename_jpg = f"{base_filename}_{counter}.jpg"
            filepath_jpg = os.path.join(self.save_path, filename_jpg)
            counter += 1
        # Save image
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            # Create a white background image
            background = Image.new('RGB', image.size, (255, 255, 255))
            # Paste the image on the white background, using the alpha channel as mask if available
            if image.mode == 'RGBA':
                background.paste(image, (0, 0), image.split()[3])
            else:
                background.paste(image.convert('RGBA'), (0, 0), image.convert('RGBA').split()[3])
            image = background
        else:
            image = image.convert("RGB")
        quality = self.quality_var.get()
        image.save(filepath_jpg, "JPEG", quality=quality)
        
        if self.ocr_var.get():
            try:
                text = pytesseract.image_to_string(image, lang='jpn')
                stem = os.path.splitext(os.path.basename(filepath_jpg))[0]
                filename_txt = stem + ".txt"
                filepath_txt = os.path.join(self.save_path, filename_txt)
                with open(filepath_txt, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.log_message(f"保存しました: {filename_jpg} と {filename_txt}")
            except Exception as e:
                self.log_message(f"OCRエラー: {str(e)}")
        else:
            self.log_message(f"保存しました: {filename_jpg}")

    def log_message(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenshotSaver(root)
    root.geometry("350x200")
    root.mainloop()