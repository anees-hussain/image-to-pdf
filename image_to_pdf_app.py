import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import threading
import os

class ImageToPDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Editor & PDF Creator")
        self.root.geometry("1000x700")

        self.images = []
        self.history = []
        self.redo_stack = []
        self.lasso_points = []
        self.lasso_active = False
        self.slider_editing = False
        self.pre_slider_image = None


        self.current_index = 0
        self.current_image = None
        self.original_image = None

        self.tk_image = None
        self.display_rect = None  # (x, y, w, h)

        self.crop_start = None
        self.crop_end = None

        self.create_ui()

    # ---------------- UI ----------------
    def create_ui(self):
        top = tk.Frame(self.root)
        top.pack(pady=5)

        tk.Button(top, text="Load", command=self.load_images).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Crop", command=self.crop_image).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="⟲", command=lambda: self.rotate(-90)).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="⟳", command=lambda: self.rotate(90)).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="PDF", command=self.create_pdf).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="◀ Prev", command=self.prev_image).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Next ▶", command=self.next_image).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Auto Adjust", command=self.auto_adjust_all).pack(side=tk.LEFT, padx=6)

        controls = tk.Frame(self.root)
        controls.pack()

        tk.Label(controls, text="Brightness").pack(side=tk.LEFT)
        self.brightness = tk.Scale(
            controls, from_=0.3, to=2, resolution=0.1,
            orient=tk.HORIZONTAL, command=self.on_slider_change, length=200
        )
        self.brightness.set(1.0)
        self.brightness.pack(side=tk.LEFT, padx=10)

        self.slider = tk.Scale(
            controls, from_=0, to=0,
            orient=tk.HORIZONTAL, label="Image",
            command=self.change_image, length=200
        )
        self.slider.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self.root, bg="#444")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.start_crop)
        self.canvas.bind("<B1-Motion>", self.update_crop)
        self.canvas.bind("<ButtonRelease-1>", self.end_crop)


        tk.Label(controls, text="Contrast").pack(side=tk.LEFT)
        self.contrast = tk.Scale(
            controls, from_=0.5, to=2, resolution=0.1,
            orient=tk.HORIZONTAL, command=self.on_slider_change, length=150
        )
        self.contrast.set(1.0)
        self.contrast.pack(side=tk.LEFT, padx=5)

        tk.Label(controls, text="Saturation").pack(side=tk.LEFT)
        self.saturation = tk.Scale(
            controls, from_=0, to=2, resolution=0.1,
            orient=tk.HORIZONTAL, command=self.on_slider_change, length=150
        )
        self.saturation.set(1.0)
        self.saturation.pack(side=tk.LEFT, padx=5)

        tk.Label(controls, text="Sharpness").pack(side=tk.LEFT)
        self.sharpness = tk.Scale(
            controls, from_=0, to=3, resolution=0.1,
            orient=tk.HORIZONTAL, command=self.on_slider_change, length=150
        )
        self.sharpness.set(1.0)
        self.sharpness.pack(side=tk.LEFT, padx=5)

        # ---- Slider bindings (AFTER widgets exist) ----
        for slider in (self.brightness, self.contrast, self.saturation, self.sharpness):
            slider.bind("<ButtonPress-1>", self.on_slider_start)
            slider.bind("<ButtonRelease-1>", self.on_slider_release)

    # ---------------- Image Load ----------------
    def load_images(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Images", "*.jpg *.png *.jpeg")]
        )
        if not files:
            return

        self.images = [Image.open(f).convert("RGB") for f in files]
        self.history = [[img.copy()] for img in self.images]
        self.redo_stack = [[] for _ in self.images]

        self.current_index = 0
        self.slider.config(to=len(self.images) - 1)
        self.load_current()
        self.slider.config(state="normal")

    def load_current(self):
        if not self.images:
            return

        if self.current_index < 0 or self.current_index >= len(self.images):
            return

        self.current_image = self.images[self.current_index]
        self.original_image = self.current_image.copy()
        self.brightness.set(1.0)
        self.show_image()

    # ---------------- Display ----------------
    def show_image(self):
        self.canvas.delete("all")

        img = self.current_image.copy()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()

        img.thumbnail((cw - 40, ch - 40))

        w, h = img.size
        x = (cw - w) // 2
        y = (ch - h) // 2

        self.display_rect = (x, y, w, h)

        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.create_image(x, y, image=self.tk_image, anchor="nw")

    # ---------------- Navigation ----------------
    def prev_image(self):
        if not self.images:
            return

        if self.current_index > 0:
            self.current_index -= 1
            self.slider.set(self.current_index)
            self.load_current()

    def next_image(self):
        if not self.images:
            return

        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.slider.set(self.current_index)
            self.load_current()

    def change_image(self, index):
        if not self.images:
            return  # nothing loaded

        index = int(index)

        if index < 0 or index >= len(self.images):
            return

        self.current_index = index
        self.load_current()

    # ---------------- History ----------------
    def push_history(self):
        self.history[self.current_index].append(self.current_image.copy())
        self.redo_stack[self.current_index].clear()

    def undo(self):
        h = self.history[self.current_index]
        if len(h) > 1:
            self.redo_stack[self.current_index].append(h.pop())
            self.current_image = h[-1].copy()
            self.images[self.current_index] = self.current_image
            self.show_image()

    def redo(self):
        r = self.redo_stack[self.current_index]
        if r:
            img = r.pop()
            self.history[self.current_index].append(img)
            self.current_image = img.copy()
            self.images[self.current_index] = self.current_image
            self.show_image()

    # ---------------- Edit Ops ----------------

    def rotate(self, angle):
        self.push_history()
        self.current_image = self.current_image.rotate(angle, expand=True)
        self.original_image = self.current_image.copy()
        self.images[self.current_index] = self.current_image
        self.show_image()

    def auto_adjust_all(self):
        if not self.images:
            messagebox.showwarning("Auto Adjust", "No images loaded")
            return

        # Show loader
        self.show_loader("Auto adjusting images...\nPlease wait")

        thread = threading.Thread(
            target=self._auto_adjust_worker,
            daemon=True
        )
        thread.start()

    def _auto_adjust_worker(self):
        try:
            new_images = []

            for img in self.images:
                img = self._auto_rotate(img)
                img = self._auto_enhance(img)
                new_images.append(img)

            # Back to UI thread
            self.root.after(0, lambda: self._on_auto_adjust_done(new_images))

        except Exception as e:
            self.root.after(0, lambda: self._on_auto_adjust_error(e))

    def _auto_rotate(self, img):
        try:
            # This fixes camera-rotated images properly
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        return img

    def _auto_enhance(self, img):
        # Gentle brightness boost
        img = ImageEnhance.Brightness(img).enhance(1.05)

        # Gentle contrast boost (text clarity)
        img = ImageEnhance.Contrast(img).enhance(1.25)

        # Slight saturation boost (ink visibility)
        img = ImageEnhance.Color(img).enhance(1.1)

        # Optional: slight sharpening
        img = ImageEnhance.Sharpness(img).enhance(1.1)

        return img

    def _on_auto_adjust_done(self, new_images):
        self.hide_loader()

        self.images = new_images
        self.history = [[img.copy()] for img in self.images]
        self.redo_stack = [[] for _ in self.images]

        self.current_index = 0
        self.slider.config(to=len(self.images) - 1)
        self.slider.set(0)
        self.slider.config(state="normal")

        self.load_current()

        messagebox.showinfo("Auto Adjust", "All images auto adjusted successfully")

    def _on_auto_adjust_error(self, error):
        self.hide_loader()
        messagebox.showerror("Auto Adjust Failed", str(error))

    # ---------------- Crop (FIXED) ----------------
    def start_crop(self, e):
        self.crop_start = (e.x, e.y)

    def update_crop(self, e):
        self.canvas.delete("crop")
        self.canvas.create_rectangle(
            self.crop_start[0], self.crop_start[1],
            e.x, e.y, outline="red", tag="crop"
        )

    def end_crop(self, e):
        self.crop_end = (e.x, e.y)

    def crop_image(self):
        if not self.crop_start or not self.crop_end:
            messagebox.showwarning("Crop", "Drag to select crop area")
            return

        self.push_history()

        dx, dy, dw, dh = self.display_rect
        img_w, img_h = self.current_image.size

        # Normalize crop rectangle
        x1 = min(self.crop_start[0], self.crop_end[0])
        y1 = min(self.crop_start[1], self.crop_end[1])
        x2 = max(self.crop_start[0], self.crop_end[0])
        y2 = max(self.crop_start[1], self.crop_end[1])

        # Clamp to image display area
        x1 = max(x1, dx)
        y1 = max(y1, dy)
        x2 = min(x2, dx + dw)
        y2 = min(y2, dy + dh)

        # Convert to image coordinates
        scale_x = img_w / dw
        scale_y = img_h / dh

        ix1 = int((x1 - dx) * scale_x)
        iy1 = int((y1 - dy) * scale_y)
        ix2 = int((x2 - dx) * scale_x)
        iy2 = int((y2 - dy) * scale_y)

        if ix2 <= ix1 or iy2 <= iy1:
            messagebox.showwarning("Crop", "Invalid crop area")
            return

        self.current_image = self.current_image.crop((ix1, iy1, ix2, iy2))
        self.original_image = self.current_image.copy()
        self.images[self.current_index] = self.current_image

        self.crop_start = None
        self.crop_end = None

        self.show_image()

        # ------------------ Lasso Methods ------------------
    
    def start_lasso(self, e):
        self.lasso_points = [(e.x, e.y)]
        self.lasso_active = True

    def draw_lasso(self, e):
        if not self.lasso_active:
            return
        self.lasso_points.append((e.x, e.y))
        if len(self.lasso_points) > 1:
            self.canvas.create_line(
                self.lasso_points[-2][0], self.lasso_points[-2][1],
                self.lasso_points[-1][0], self.lasso_points[-1][1],
                fill="red", width=2
            )

    def end_lasso(self, e):
        self.lasso_active = False

    # ------------------ slider ---------------------
    def on_slider_start(self, event):
        if not self.slider_editing:
            self.slider_editing = True
            self.pre_slider_image = self.current_image.copy()
    
    def on_slider_change(self, _=None):
        if not self.slider_editing:
            return

        img = self.pre_slider_image.copy()

        img = ImageEnhance.Brightness(img).enhance(self.brightness.get())
        img = ImageEnhance.Contrast(img).enhance(self.contrast.get())
        img = ImageEnhance.Color(img).enhance(self.saturation.get())
        img = ImageEnhance.Sharpness(img).enhance(self.sharpness.get())

        self.current_image = img
        self.images[self.current_index] = img
        self.show_image()

    def on_slider_release(self, event):
        if self.slider_editing:
            self.slider_editing = False
            self.push_history()
            self.original_image = self.current_image.copy()
    # ---------------- PDF ----------------

    def create_pdf(self):
        if not self.images:
            messagebox.showwarning("PDF", "No images to export")
            return

        # Commit last slider edit
        if self.slider_editing:
            self.on_slider_release(None)

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not path:
            return

        # Show loader
        self.show_loader("Generating PDF...\nPlease wait")

        # Run PDF generation in background
        thread = threading.Thread(
            target=self._generate_pdf_worker,
            args=(path,),
            daemon=True
        )
        thread.start()

    def reset_app(self):
        self.images.clear()
        self.history.clear()
        self.redo_stack.clear()

        self.current_index = 0
        self.current_image = None
        self.original_image = None

        self.slider_editing = False
        self.pre_slider_image = None

        self.crop_start = None
        self.crop_end = None

        # Reset sliders
        self.brightness.set(1.0)
        self.contrast.set(1.0)
        self.saturation.set(1.0)
        self.sharpness.set(1.0)

        # Reset image navigation slider
        self.slider.config(from_=0, to=0)
        self.slider.set(0)

        # Clear canvas
        self.canvas.delete("all")

        self.slider.config(state="disabled")

# -------------- Loader ----------------

    def show_loader(self, text="Processing..."):
        self.loader = tk.Toplevel(self.root)
        self.loader.title("Please wait")
        self.loader.geometry("300x100")
        self.loader.resizable(False, False)
        self.loader.transient(self.root)
        self.loader.grab_set()

        tk.Label(
            self.loader,
            text=text,
            font=("Arial", 11)
        ).pack(expand=True, pady=20)

        self.loader.update()

    def hide_loader(self):
        if hasattr(self, "loader") and self.loader:
            self.loader.destroy()
            self.loader = None
    
    def _generate_pdf_worker(self, path):
        try:
            pdf = canvas.Canvas(path, pagesize=A4)
            pw, ph = A4

            # Snapshot to avoid mutation
            export_images = [img.copy() for img in self.images]

            for img in export_images:
                reader = ImageReader(img)
                iw, ih = img.size

                scale = min(pw / iw, ph / ih)
                nw, nh = iw * scale, ih * scale

                pdf.drawImage(
                    reader,
                    (pw - nw) / 2,
                    (ph - nh) / 2,
                    nw, nh
                )
                pdf.showPage()

            pdf.save()

            # Back to UI thread
            self.root.after(0, self._on_pdf_success)

        except Exception as e:
            self.root.after(0, lambda: self._on_pdf_error(e))

    def _on_pdf_success(self):
        self.hide_loader()
        messagebox.showinfo("Success", "PDF created successfully")
        self.reset_app()

    def _on_pdf_error(self, error):
        self.hide_loader()
        messagebox.showerror("Error", f"Failed to create PDF:\n{error}")

# ---------------- RUN ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageToPDFApp(root)
    root.mainloop()