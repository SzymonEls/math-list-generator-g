import cv2
import numpy as np
import io
import tkinter as tk
from tkinter import ttk
import threading
import queue
from tkinter import filedialog
from PIL import Image, ImageTk
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pdf2image import convert_from_path, pdfinfo_from_path
import os

#pdf
pdf_pages = []  # Lista PIL.Image dla każdej strony PDF
pdf_rectangles = []  # Lista list prostokątów per strona
current_page = 0
is_pdf_mode = False
pdf_load_queue = queue.Queue()
pdf_load_in_progress = False
pdf_load_total = 0
pdf_load_thread = None

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
task_items = []
preview_image = None
image_sources = {}
image_rectangles = {}
current_image_id = None
image_counter = 0

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

def create_pdf_from_task_items(task_items, pdf_filename, title_text):
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    width, height = A4
    total_pages = len(task_items)
    page_num = 1

    for item in task_items:
        img_np = item["img"]
        start, end = item["rect"]
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

        if title_text:
            c.setFont("DejaVu", 11)
            c.drawCentredString(width / 2, 15, title_text)

        c.setFont("DejaVu", 10)
        c.drawRightString(width - 20, 10, f"{page_num}/{total_pages}")

        page_num += 1
        c.showPage()

    c.save()

def rebuild_task_listbox():
    task_listbox.delete(0, tk.END)
    for item in task_items:
        task_listbox.insert(tk.END, item["label"])
    update_preview()

def update_preview():
    global preview_image
    selection = task_listbox.curselection()
    if not selection:
        preview_label.config(image="", text="Brak podglądu")
        preview_image = None
        return
    index = selection[0]
    item = task_items[index]
    img_np = item["img"]
    start, end = item["rect"]
    x1, y1 = map(int, start)
    x2, y2 = map(int, end)
    x_min, x_max = sorted([x1, x2])
    y_min, y_max = sorted([y1, y2])
    roi = img_np[y_min:y_max, x_min:x_max]
    if roi.size == 0:
        preview_label.config(image="", text="Brak podglądu")
        preview_image = None
        return
    roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(roi_rgb)
    pil_image.thumbnail((220, 220))
    preview_image = ImageTk.PhotoImage(pil_image)
    preview_label.config(image=preview_image, text="")

def add_task_item(img_np, rect, label, source, source_id):
    task_items.append(
        {
            "img": img_np.copy(),
            "rect": rect,
            "label": label,
            "source": source,
            "source_id": source_id,
        }
    )
    rebuild_task_listbox()

def remove_task_item(index):
    if index < 0 or index >= len(task_items):
        return
    item = task_items.pop(index)
    if item["source"] == "pdf":
        rects = pdf_rectangles[item["source_id"]]
        if item["rect"] in rects:
            rects.remove(item["rect"])
    else:
        rects = image_rectangles.get(item["source_id"], [])
        if item["rect"] in rects:
            rects.remove(item["rect"])
    rebuild_task_listbox()
    redraw_current_image()

def redraw_current_image():
    canvas_widget.delete("all")
    if tk_image is None:
        return
    canvas_widget.create_image(0, 0, image=tk_image, anchor="nw")
    if rectangles:
        for start, end in rectangles:
            canvas_widget.create_rectangle(*start, *end, outline='green', width=2)

def move_task(direction):
    selection = task_listbox.curselection()
    if not selection:
        return
    index = selection[0]
    new_index = index + direction
    if new_index < 0 or new_index >= len(task_items):
        return
    task_items[index], task_items[new_index] = task_items[new_index], task_items[index]
    rebuild_task_listbox()
    task_listbox.selection_set(new_index)
    update_preview()

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

    if is_pdf_mode:
        page_label = f"PDF strona {current_page + 1}"
        img_np = cv2.cvtColor(np.array(pdf_pages[current_page]), cv2.COLOR_RGB2BGR)
        add_task_item(img_np, (start_point, end_point), page_label, "pdf", current_page)
    else:
        if current_image_id is not None and img_copy is not None:
            image_label = f"Obraz {current_image_id}"
            add_task_item(img_copy, (start_point, end_point), image_label, "image", current_image_id)

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

def show_pdf_page():
    global tk_image, img_copy, rectangles

    pil_image = pdf_pages[current_page]
    img_copy = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    rectangles = pdf_rectangles[current_page]

    tk_image = ImageTk.PhotoImage(pil_image)
    canvas_widget.delete("all")
    canvas_widget.create_image(0, 0, image=tk_image, anchor="nw")
    canvas_widget.config(scrollregion=canvas_widget.bbox("all"))

    # Rysuj prostokąty z tej strony
    for start, end in rectangles:
        canvas_widget.create_rectangle(*start, *end, outline='green', width=2)

def set_loading_state(is_loading):
    state = tk.DISABLED if is_loading else tk.NORMAL
    load_image_button.config(state=state)
    load_pdf_button.config(state=state)
    prev_page_button.config(state=state)
    next_page_button.config(state=state)
    save_pdf_button.config(state=state)
    if is_loading:
        progress_label.config(text="Wczytywanie PDF...")
    else:
        progress_label.config(text="")

def process_pdf_queue():
    global pdf_pages, current_page, is_pdf_mode, rectangles, pdf_rectangles, pdf_load_in_progress
    try:
        while True:
            message = pdf_load_queue.get_nowait()
            message_type = message.get("type")
            if message_type == "progress":
                total = message.get("total", 0)
                current = message.get("current", 0)
                if total:
                    progress_bar.stop()
                    progress_bar.config(mode="determinate", maximum=total)
                    progress_var.set(current)
                    progress_label.config(text=f"Wczytywanie PDF: {current}/{total}")
            elif message_type == "done":
                pdf_pages = message.get("pages", [])
                if not pdf_pages:
                    progress_label.config(text="Nie udało się wczytać PDF.")
                else:
                    is_pdf_mode = True
                    pdf_rectangles = [[] for _ in pdf_pages]
                    current_page = 0
                    rectangles = pdf_rectangles[current_page]
                    show_pdf_page()
                pdf_load_in_progress = False
                set_loading_state(False)
                progress_bar.stop()
                progress_var.set(0)
            elif message_type == "error":
                progress_label.config(text=f"Błąd odczytu PDF: {message.get('error', '')}")
                pdf_load_in_progress = False
                set_loading_state(False)
                progress_bar.stop()
                progress_var.set(0)
    except queue.Empty:
        pass

    if pdf_load_in_progress:
        root.after(100, process_pdf_queue)

def load_pdf_worker(file_path, dpi=200):
    try:
        info = pdfinfo_from_path(file_path)
        total_pages = int(info.get("Pages", 0))
        pages = []
        for page_num in range(1, total_pages + 1):
            images = convert_from_path(file_path, dpi=dpi, first_page=page_num, last_page=page_num)
            if images:
                pages.append(images[0])
            pdf_load_queue.put({"type": "progress", "current": page_num, "total": total_pages})
        pdf_load_queue.put({"type": "done", "pages": pages})
    except Exception as e:
        pdf_load_queue.put({"type": "error", "error": str(e)})

def choose_pdf():
    global pdf_load_in_progress, pdf_load_thread, pdf_load_total

    file_path = filedialog.askopenfilename(title="Wybierz PDF", filetypes=[("PDF files", "*.pdf")])
    if not file_path:
        return

    if pdf_load_in_progress:
        return

    pdf_load_in_progress = True
    set_loading_state(True)
    progress_var.set(0)
    progress_bar.config(mode="indeterminate")
    progress_bar.start(10)
    pdf_load_thread = threading.Thread(target=load_pdf_worker, args=(file_path,), daemon=True)
    pdf_load_thread.start()
    root.after(100, process_pdf_queue)


def choose_file():
    global rectangles, img_copy, tk_image, img_copy_prev, current_image_id, image_counter

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

    image_counter += 1
    current_image_id = image_counter
    image_sources[current_image_id] = image
    image_rectangles[current_image_id] = []
    rectangles = image_rectangles[current_image_id]

    img_copy = image
    img_copy_prev = image
    tk_image = ImageTk.PhotoImage(pil_image)

    canvas_widget.delete("all")
    canvas_widget.create_image(0, 0, image=tk_image, anchor="nw")
    canvas_widget.config(scrollregion=canvas_widget.bbox("all"))

def save_pdf():
    global img_copy_prev
    
    if not task_items:
        print("Brak zaznaczonych zadań.")
        return

    pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if pdf_path:
        title_text = title_entry.get()
        create_pdf_from_task_items(task_items, pdf_path, title_text)
        print(f"Zapisano PDF: {pdf_path}")

def on_ctrl_z(event):
    if rectangles:
        removed = rectangles.pop()
        for idx in range(len(task_items) - 1, -1, -1):
            item = task_items[idx]
            if item["rect"] == removed:
                if is_pdf_mode and item["source"] == "pdf" and item["source_id"] == current_page:
                    task_items.pop(idx)
                    break
                if not is_pdf_mode and item["source"] == "image" and item["source_id"] == current_image_id:
                    task_items.pop(idx)
                    break
        rebuild_task_listbox()
        redraw_current_image()

def prev_page():
    global current_page
    if not is_pdf_mode or current_page == 0:
        return
    current_page -= 1
    show_pdf_page()

def next_page():
    global current_page
    if not is_pdf_mode or current_page >= len(pdf_pages) - 1:
        return
    current_page += 1
    show_pdf_page()


# === GUI ===
root = tk.Tk()
root.title("Zaznaczanie zadań do PDF (polskie znaki w ścieżce i info)")
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

root.bind('<Control-z>', on_ctrl_z)

content_frame = tk.Frame(frame)
content_frame.pack(fill=tk.BOTH, expand=True)

canvas_frame = tk.Frame(content_frame)
canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

canvas_widget = tk.Canvas(canvas_frame, bg="white", width=800, height=600, scrollregion=(0, 0, 2000, 2000))
canvas_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar_y = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas_widget.yview)
scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
canvas_widget.config(yscrollcommand=scrollbar_y.set)

scrollbar_x = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas_widget.xview)
scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
canvas_widget.config(xscrollcommand=scrollbar_x.set)

canvas_widget.bind("<ButtonPress-1>", on_mouse_down)
canvas_widget.bind("<B1-Motion>", on_mouse_move)
canvas_widget.bind("<ButtonRelease-1>", on_mouse_up)
canvas_widget.bind_all("<MouseWheel>", _on_mousewheel)
canvas_widget.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

# === Panel boczny ===
side_frame = tk.Frame(content_frame, padx=10, pady=10)
side_frame.pack(side=tk.RIGHT, fill=tk.Y)

tk.Label(side_frame, text="Zaznaczone zadania").pack(anchor="w")
task_listbox = tk.Listbox(side_frame, height=18, width=30)
task_listbox.pack(fill=tk.Y, expand=False)
task_listbox.bind("<<ListboxSelect>>", lambda event: update_preview())

task_buttons_frame = tk.Frame(side_frame)
task_buttons_frame.pack(pady=5, fill=tk.X)
tk.Button(task_buttons_frame, text="↑", command=lambda: move_task(-1)).pack(side=tk.LEFT, padx=2)
tk.Button(task_buttons_frame, text="↓", command=lambda: move_task(1)).pack(side=tk.LEFT, padx=2)
tk.Button(task_buttons_frame, text="Usuń", command=lambda: remove_task_item(task_listbox.curselection()[0]) if task_listbox.curselection() else None).pack(side=tk.LEFT, padx=2)

tk.Label(side_frame, text="Podgląd zadania").pack(anchor="w", pady=(10, 0))
preview_label = tk.Label(side_frame, text="Brak podglądu", width=30, height=10, relief=tk.SUNKEN)
preview_label.pack()

# === Panel przycisków ===
btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

load_image_button = tk.Button(btn_frame, text="Wczytaj obraz", command=choose_file)
load_image_button.pack(side=tk.LEFT, padx=5)
load_pdf_button = tk.Button(btn_frame, text="Wczytaj PDF", command=choose_pdf)
load_pdf_button.pack(side=tk.LEFT, padx=5)
prev_page_button = tk.Button(btn_frame, text="←", command=prev_page)
prev_page_button.pack(side=tk.LEFT, padx=2)
next_page_button = tk.Button(btn_frame, text="→", command=next_page)
next_page_button.pack(side=tk.LEFT, padx=2)

save_pdf_button = tk.Button(btn_frame, text="Zapisz PDF", command=save_pdf)
save_pdf_button.pack(side=tk.LEFT, padx=5)

tk.Label(btn_frame, text="Tytuł PDF (na dole każdej strony):").pack(side=tk.LEFT, padx=5)
title_entry = tk.Entry(btn_frame, width=30)
title_entry.pack(side=tk.LEFT)

progress_frame = tk.Frame(root)
progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
progress_var = tk.DoubleVar(value=0)
progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
progress_bar.pack(fill=tk.X, expand=True)
progress_label = tk.Label(progress_frame, text="")
progress_label.pack(anchor="w")

root.mainloop()
