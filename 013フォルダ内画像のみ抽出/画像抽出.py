import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

class ImageMoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Mover")
        self.root.geometry("500x300")

        # Variables for folder paths
        self.source_folder = tk.StringVar()
        self.dest_folder = tk.StringVar()

        # GUI Elements
        tk.Label(root, text="Source Folder:").pack(pady=10)
        tk.Entry(root, textvariable=self.source_folder, width=50).pack()
        tk.Button(root, text="Browse", command=self.browse_source).pack()

        tk.Label(root, text="Destination Folder:").pack(pady=10)
        tk.Entry(root, textvariable=self.dest_folder, width=50).pack()
        tk.Button(root, text="Browse", command=self.browse_dest).pack()

        tk.Button(root, text="Move Images", command=self.move_images).pack(pady=20)

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)

    def browse_dest(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_folder.set(folder)

    def move_images(self):
        source = self.source_folder.get()
        dest = self.dest_folder.get()

        if not source or not dest:
            messagebox.showerror("Error", "Please select both source and destination folders.")
            return

        if not os.path.exists(source):
            messagebox.showerror("Error", "Source folder does not exist.")
            return

        if not os.path.exists(dest):
            os.makedirs(dest)

        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        moved_count = 0

        try:
            for root, _, files in os.walk(source):
                for file in files:
                    if file.lower().endswith(image_extensions):
                        source_path = os.path.join(root, file)
                        dest_path = os.path.join(dest, file)
                        
                        # Handle duplicate file names
                        if os.path.exists(dest_path):
                            base, ext = os.path.splitext(file)
                            i = 1
                            while os.path.exists(os.path.join(dest, f"{base}_{i}{ext}")):
                                i += 1
                            dest_path = os.path.join(dest, f"{base}_{i}{ext}")

                        shutil.move(source_path, dest_path)
                        moved_count += 1

            messagebox.showinfo("Success", f"Moved {moved_count} image(s) successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageMoverApp(root)
    root.mainloop()