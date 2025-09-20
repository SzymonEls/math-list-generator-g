import cv2
import numpy as np
import io
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Ścieżka do czcionki w katalogu skryptu
font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")

if not os.path.exists(font_path):
    raise FileNotFoundError(
        "Brak pliku czcionki 'DejaVuSans.ttf'. Pobierz ją np. z https://dejavu-fonts.github.io/ i umieść w katalogu skryptu."
    )

# Rejestracja czcionki
pdfmetrics.registerFont(TTFont('DejaVu', font_path))


rectangles = []
start_point = None
drawing = False
images_with_rois = []
img_copy = None
img_copy_prev = None
tk_image = None

def draw_grid(c, page_width, page_height, grid_size_mm=5):
    grid_size = grid_size_mm * mm
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.3)
    for x in np.arange(0, page_width, grid_size):
        c.line(x, 0, x, page_height)
    for y in np.arange(0, page_height, grid_size):
        c.line(0, y, page_width, y)

def create_pdf_with_tasks(images_with_rois, pdf_filename, title_text):
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    width, height = A4
    # Oblicz całkowitą liczbę stron
    total_pages = sum(len(rects) for _, rects in images_with_rois)
    page_num = 1

    for img_np, rects in images_with_rois:
        for start, end in rects:
            x1, y1 = map(int, start)
            x2, y2 = map(int, end)
            x_min, x_max = sorted([x1, x2])
            y_min, y_max = sorted([y1, y2])
            roi = img_np[y_min:y_max, x_min:x_max]

            draw_grid(c, width, height, grid_size_mm=5)

            is_success, buffer = cv2.imencode(".jpg", roi)
            if not is_success:
                continue
            img_bytes = io.BytesIO(buffer)
            img_reader = ImageReader(img_bytes)
            iw, ih = img_reader.getSize()

            scale = min(width / iw, height / ih) * 0.9
            iw_scaled, ih_scaled = iw * scale, ih * scale
            x = (width - iw_scaled) / 2
            y = height - ih_scaled - 40

            c.drawImage(img_reader, x, y, width=iw_scaled, height=ih_scaled)

            # Dodaj tytuł na dole
            if title_text:
                c.setFont("DejaVu", 11)
                c.drawCentredString(width / 2, 15, title_text)

            # Numeracja stron w stylu "Strona X z Y"
            c.setFont("DejaVu", 10)
            c.drawRightString(width - 20, 10, f"{page_num}/{total_pages}")

            page_num += 1
            c.showPage()

    c.save()

def on_mouse_down(event):
    global start_point, drawing
    drawing = True
    start_point = (canvas_widget.canvasx(event.x), canvas_widget.canvasy(event.y))

def on_mouse_up(event):
    global drawing
    if not drawing:
        return
    end_point = (canvas_widget.canvasx(event.x), canvas_widget.canvasy(event.y))
    rectangles.append((start_point, end_point))
    canvas_widget.create_rectangle(*start_point, *end_point, outline='green', width=2)
    drawing = False

def on_mouse_move(event):
    global drawing
    if drawing:
        canvas_widget.delete("preview")
        current = (canvas_widget.canvasx(event.x), canvas_widget.canvasy(event.y))
        canvas_widget.create_rectangle(*start_point, *current, outline='green', width=2, tag="preview")

def _on_mousewheel(event):
    canvas_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

def _on_shift_mousewheel(event):
    canvas_widget.xview_scroll(int(-1 * (event.delta / 120)), "units")

def choose_file():
    global rectangles, img_copy, tk_image, img_copy_prev

    file_path = filedialog.askopenfilename(title="Wybierz obraz", filetypes=[("Obrazy", "*.jpg *.png *.bmp")])
    if not file_path:
        return

    # Wczytanie obrazu z obsługą ścieżek Unicode
    try:
        img_array = np.fromfile(file_path, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Błąd odczytu obrazu: {e}")
        return

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)

    # Zapisz poprzednie zaznaczenia
    if rectangles and img_copy_prev is not None:
        images_with_rois.append((img_copy_prev, rectangles.copy()))

    rectangles.clear()

    img_copy = image
    img_copy_prev = image
    tk_image = ImageTk.PhotoImage(pil_image)

    canvas_widget.delete("all")
    canvas_widget.create_image(0, 0, image=tk_image, anchor="nw")
    canvas_widget.config(scrollregion=canvas_widget.bbox("all"))

def save_pdf():
    global img_copy_prev

    if rectangles and img_copy_prev is not None:
        images_with_rois.append((img_copy_prev, rectangles.copy()))

    if not images_with_rois:
        print("Brak zaznaczonych zadań.")
        return

    pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if pdf_path:
        title_text = title_entry.get()
        create_pdf_with_tasks(images_with_rois, pdf_path, title_text)
        print(f"Zapisano PDF: {pdf_path}")

def on_ctrl_z(event):
    if rectangles:
        rectangles.pop()
        canvas_widget.delete("all")
        canvas_widget.create_image(0, 0, image=tk_image, anchor="nw")
        for start, end in rectangles:
            canvas_widget.create_rectangle(*start, *end, outline='green', width=2)

# === GUI ===
root = tk.Tk()
root.title("Zaznaczanie zadań do PDF")
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

root.bind('<Control-z>', on_ctrl_z)

canvas_widget = tk.Canvas(frame, bg="white", width=800, height=600, scrollregion=(0, 0, 2000, 2000))
canvas_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar_y = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas_widget.yview)
scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
canvas_widget.config(yscrollcommand=scrollbar_y.set)

scrollbar_x = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=canvas_widget.xview)
scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
canvas_widget.config(xscrollcommand=scrollbar_x.set)

canvas_widget.bind("<ButtonPress-1>", on_mouse_down)
canvas_widget.bind("<B1-Motion>", on_mouse_move)
canvas_widget.bind("<ButtonRelease-1>", on_mouse_up)
canvas_widget.bind_all("<MouseWheel>", _on_mousewheel)
canvas_widget.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

# === Panel przycisków ===
btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Wczytaj obraz", command=choose_file).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="Zapisz PDF", command=save_pdf).pack(side=tk.LEFT, padx=5)

tk.Label(btn_frame, text="Tytuł PDF (na dole każdej strony):").pack(side=tk.LEFT, padx=5)
title_entry = tk.Entry(btn_frame, width=30)
title_entry.pack(side=tk.LEFT)

root.mainloop()
