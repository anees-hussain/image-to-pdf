import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

class ImageToPDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Crop & PDF Creator")
        self.root.geometry("900x600")

        self.images = []
        self.current_image = None
        self.original_image = None
        self.tk_image = None
        self.crop_start = None
        self.crop_end = None
        self.brightness_value = 1.0

        self.create_ui()

    def create_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=5)

        tk.Button(top_frame, text="Load Images", command=self.load_images).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Crop Image", command=self.crop_image).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Save Image", command=self.save_image).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Create PDF", command=self.create_pdf).pack(side=tk.LEFT, padx=5)

        brightness_frame = tk.Frame(self.root)
        brightness_frame.pack()

        tk.Label(brightness_frame, text="Brightness").pack(side=tk.LEFT)
        self.brightness_slider = tk.Scale(
            brightness_frame,
            from_=0.3,
            to=2.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            command=self.adjust_brightness
        )
        self.brightness_slider.set(1.0)
        self.brightness_slider.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self.root, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.start_crop)
        self.canvas.bind("<B1-Motion>", self.update_crop)
        self.canvas.bind("<ButtonRelease-1>", self.end_crop)

    def load_images(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Images", "*.png *.jpg *.jpeg")]
        )
        if not files:
            return

        self.images = [Image.open(f).convert("RGB") for f in files]
        self.current_image = self.images[0]
        self.original_image = self.current_image.copy()
        self.show_image()

    def show_image(self):
        if not self.current_image:
            return

        img = self.current_image.copy()
        img.thumbnail((800, 500))
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(450, 250, image=self.tk_image)

    def adjust_brightness(self, value):
        if not self.original_image:
            return

        enhancer = ImageEnhance.Brightness(self.original_image)
        self.current_image = enhancer.enhance(float(value))
        self.show_image()

    def start_crop(self, event):
        self.crop_start = (event.x, event.y)

    def update_crop(self, event):
        self.canvas.delete("crop")
        self.canvas.create_rectangle(
            self.crop_start[0], self.crop_start[1],
            event.x, event.y,
            outline="red",
            tag="crop"
        )

    def end_crop(self, event):
        self.crop_end = (event.x, event.y)

    def crop_image(self):
        if not self.crop_start or not self.crop_end:
            messagebox.showwarning("Crop", "Please select crop area")
            return

        width, height = self.current_image.size
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        x1 = int(self.crop_start[0] * width / canvas_w)
        y1 = int(self.crop_start[1] * height / canvas_h)
        x2 = int(self.crop_end[0] * width / canvas_w)
        y2 = int(self.crop_end[1] * height / canvas_h)

        self.current_image = self.current_image.crop((x1, y1, x2, y2))
        self.original_image = self.current_image.copy()
        self.show_image()

    def save_image(self):
        if not self.current_image:
            return

        self.images.append(self.current_image.copy())
        messagebox.showinfo("Saved", "Image saved for PDF")

    def create_pdf(self):
        if not self.images:
            messagebox.showwarning("PDF", "No images to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not file_path:
            return

        pdf = canvas.Canvas(file_path, pagesize=A4)
        page_width, page_height = A4

        for img in self.images:
            img_path = "temp_image.jpg"
            img.save(img_path)

            img_width, img_height = img.size
            ratio = min(page_width / img_width, page_height / img_height)

            new_width = img_width * ratio
            new_height = img_height * ratio

            x = (page_width - new_width) / 2
            y = (page_height - new_height) / 2

            pdf.drawImage(img_path, x, y, new_width, new_height)
            pdf.showPage()

        pdf.save()
        os.remove("temp_image.jpg")

        messagebox.showinfo("Success", "PDF created successfully")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageToPDFApp(root)
    root.mainloop()