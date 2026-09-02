"""Zaznaczanie zadań z obrazów i PDF-ów i składanie ich w nowy PDF.

Jedno zadanie na stronę, kratka w tle, tytuł i numeracja stron.
"""

import io
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageTk
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

RENDER_DPI = 200
# Rozdzielczość zakładana dla obrazów, które nie niosą sensownej informacji o DPI
# (typowy skan/zdjęcie podręcznika). Decyduje o tym, jak duże będzie zadanie na stronie.
DEFAULT_IMAGE_DPI = 200
MIN_SOURCE_DPI = 100  # niżej to prawie zawsze bezsensowna wartość domyślna z pliku

# Marginesy strony wynikowego PDF-u. Dolny jest większy — mieści tytuł i numerację.
MARGIN_X = 15 * mm
MARGIN_TOP = 12 * mm
MARGIN_BOTTOM = 18 * mm

MIN_ZOOM = 0.05
MAX_ZOOM = 4.0
ZOOM_FACTOR = 1.25
MIN_RECT_PX = 8  # mniejsze przeciągnięcie traktujemy jak kliknięcie

SIZE_NATURAL = "Naturalny (bez powiększania)"
SIZE_FIT = "Dopasuj do strony"

COLOR_RECT = "#1a9c3c"
COLOR_RECT_SEL = "#0a63d8"
COLOR_PREVIEW = "#1a9c3c"


def resource_dir():
    """Katalog z plikami dołączonymi do programu.

    Działa zarówno przy zwykłym `python main.py`, jak i w wersji spakowanej
    PyInstallerem (zasoby lądują wtedy w katalogu tymczasowym `sys._MEIPASS`).
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# Czcionka z polskimi znakami: najpierw kopia dołączona do projektu,
# potem typowe lokalizacje systemowe (Linux / Windows / macOS).
FONT_CANDIDATES = [
    os.path.join(resource_dir(), "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]

font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)

if font_path is None:
    _msg = (
        "Nie znaleziono czcionki z polskimi znakami. Pobierz 'DejaVuSans.ttf' "
        "z https://dejavu-fonts.github.io/ i umieść w katalogu programu."
    )
    _err_root = tk.Tk()
    _err_root.withdraw()
    messagebox.showerror("Brak czcionki", _msg)
    raise SystemExit(_msg)

pdfmetrics.registerFont(TTFont("DejaVu", font_path))


# === Model danych ===

class Page:
    """Jedna strona PDF-u albo jeden wczytany obraz."""

    def __init__(self, doc, label, index_in_doc=0, dpi=RENDER_DPI):
        self.doc = doc
        self.label = label
        self.index_in_doc = index_in_doc
        self.dpi = dpi  # ile pikseli obrazu przypada na cal — stąd rozmiar na stronie
        self._pil = None

    @property
    def pil(self):
        """Obraz strony. Strony PDF renderujemy dopiero przy pierwszym pokazaniu."""
        if self._pil is None:
            page = self.doc.pdf[self.index_in_doc]
            # scale = dpi / 72; .copy() odrywa obraz od bufora pdfium
            self._pil = page.render(scale=RENDER_DPI / 72).to_pil().copy()
        return self._pil

    @property
    def is_rendered(self):
        return self._pil is not None


class Document:
    """Wczytany plik: obraz (jedna strona) albo PDF (wiele stron)."""

    def __init__(self, path, kind):
        self.path = path
        self.kind = kind  # "image" albo "pdf"
        self.name = os.path.basename(path)
        self.pdf = None
        self.pages = []


class Task:
    """Jedno zaznaczone zadanie: prostokąt w koordynatach obrazu."""

    def __init__(self, page, x1, y1, x2, y2):
        self.page = page
        self.x1, self.x2 = sorted((int(x1), int(x2)))
        self.y1, self.y2 = sorted((int(y1), int(y2)))

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    def contains(self, x, y):
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def crop(self):
        return self.page.pil.crop((self.x1, self.y1, self.x2, self.y2))


# === Generowanie PDF ===

def detect_dpi(pil_image):
    """Rozdzielczość obrazu z metadanych pliku albo rozsądne założenie."""
    try:
        dpi = float((pil_image.info.get("dpi") or (0,))[0])
    except (TypeError, ValueError, IndexError):
        dpi = 0.0
    return dpi if dpi >= MIN_SOURCE_DPI else DEFAULT_IMAGE_DPI


def task_layout(task, fit_to_page=False):
    """Pozycja i rozmiar zadania na stronie A4, w punktach.

    Domyślnie zadanie trafia na stronę w rozmiarze naturalnym — takim, jaki
    wynika z rozdzielczości źródła. Małe zadanie zostaje małe, a reszta strony
    zostaje wolna na rozwiązanie. Zmniejszamy tylko wtedy, gdy wycinek nie
    mieści się w marginesach.
    """
    page_w, page_h = A4
    avail_w = page_w - 2 * MARGIN_X
    avail_h = page_h - MARGIN_TOP - MARGIN_BOTTOM

    iw = max(task.width, 1)
    ih = max(task.height, 1)
    scale_fit = min(avail_w / iw, avail_h / ih)
    scale = scale_fit if fit_to_page else min(72.0 / task.page.dpi, scale_fit)

    w, h = iw * scale, ih * scale
    x = (page_w - w) / 2
    y = page_h - MARGIN_TOP - h
    return x, y, w, h


def draw_grid(c, page_width, page_height, grid_size_mm=5):
    grid_size = grid_size_mm * mm
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.3)
    for x in np.arange(0, page_width, grid_size):
        c.line(x, 0, x, page_height)
    for y in np.arange(0, page_height, grid_size):
        c.line(0, y, page_width, y)


def create_pdf_with_tasks(tasks, pdf_filename, title_text, with_grid=True,
                          fit_to_page=False, progress=None):
    """Składa PDF: jedno zadanie na stronę, w kolejności z listy `tasks`."""
    c = pdfcanvas.Canvas(pdf_filename, pagesize=A4)
    width, height = A4
    total_pages = len(tasks)

    for page_num, task in enumerate(tasks, start=1):
        if progress is not None:
            progress(page_num, total_pages)

        if with_grid:
            draw_grid(c, width, height, grid_size_mm=5)

        img_bytes = io.BytesIO()
        task.crop().convert("RGB").save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        img_reader = ImageReader(img_bytes)

        x, y, w, h = task_layout(task, fit_to_page=fit_to_page)
        c.drawImage(img_reader, x, y, width=w, height=h)

        if title_text:
            c.setFont("DejaVu", 11)
            c.drawCentredString(width / 2, 15, title_text)

        c.setFont("DejaVu", 10)
        c.drawRightString(width - 20, 10, f"{page_num}/{total_pages}")

        c.showPage()

    c.save()


def wheel_units(delta):
    """Liczba jednostek przewinięcia — Windows daje wielokrotności 120, macOS małe wartości."""
    if abs(delta) >= 120:
        return int(-delta / 120)
    return -1 if delta > 0 else 1


# === Aplikacja ===

class App:
    def __init__(self, root):
        self.root = root
        self.documents = []
        self.pages = []          # płaska lista wszystkich stron, w kolejności wczytania
        self.tasks = []          # kolejność zadań = kolejność stron w wynikowym PDF
        self.undo_stack = []     # zadania w kolejności dodawania (do Ctrl+Z)
        self.current_page = None
        self.selected_task = None
        self.zoom = 1.0
        self.tk_image = None
        self.preview_image = None
        self.drag_start = None   # (x, y) w koordynatach obrazu
        self.dragging = False

        root.title("Generator list zadań")
        root.geometry("1280x820")
        root.minsize(1000, 640)

        try:
            ttk.Style().theme_use("clam" if sys.platform.startswith("linux") else
                                  ttk.Style().theme_use())
        except tk.TclError:
            pass

        # Kolejność ma znaczenie: pasek stanu rezerwuje miejsce zanim
        # obszar roboczy zajmie resztę okna (inaczej wypada poza ekran).
        self._build_toolbar()
        self._build_statusbar()
        self._build_body()
        self._bind_keys()

        self.refresh_all()

    # --- Budowa interfejsu ---

    def _build_toolbar(self):
        # Rząd 1 — co wczytujemy i jak oglądamy
        top = ttk.Frame(self.root, padding=(8, 6, 8, 2))
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(top, text="Wczytaj obraz…", command=self.choose_image).pack(side=tk.LEFT)
        ttk.Button(top, text="Wczytaj PDF…", command=self.choose_pdf).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Label(top, text="Powiększenie:").pack(side=tk.LEFT, padx=(0, 6))
        self.btn_zoom_out = ttk.Button(top, text="−", width=3, command=lambda: self.change_zoom(1 / ZOOM_FACTOR))
        self.btn_zoom_out.pack(side=tk.LEFT)
        self.lbl_zoom = ttk.Label(top, text="100%", width=6, anchor="center")
        self.lbl_zoom.pack(side=tk.LEFT, padx=2)
        self.btn_zoom_in = ttk.Button(top, text="+", width=3, command=lambda: self.change_zoom(ZOOM_FACTOR))
        self.btn_zoom_in.pack(side=tk.LEFT)
        self.btn_fit = ttk.Button(top, text="Dopasuj", command=self.zoom_to_fit)
        self.btn_fit.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_zoom_100 = ttk.Button(top, text="100%", command=lambda: self.set_zoom(1.0))
        self.btn_zoom_100.pack(side=tk.LEFT, padx=(4, 0))

        # Rząd 2 — co trafi do wynikowego PDF-u
        bottom = ttk.Frame(self.root, padding=(8, 2, 8, 6))
        bottom.pack(side=tk.TOP, fill=tk.X)

        self.btn_save = ttk.Button(bottom, text="Zapisz PDF…", command=self.save_pdf)
        self.btn_save.pack(side=tk.RIGHT)

        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text="Kratka", variable=self.grid_var).pack(side=tk.RIGHT, padx=(12, 12))

        self.fit_var = tk.StringVar(value=SIZE_NATURAL)
        self.fit_combo = ttk.Combobox(bottom, textvariable=self.fit_var, state="readonly",
                                      width=26, values=(SIZE_NATURAL, SIZE_FIT))
        self.fit_combo.pack(side=tk.RIGHT)
        self.fit_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_preview())
        ttk.Label(bottom, text="Rozmiar zadania:").pack(side=tk.RIGHT, padx=(12, 6))

        ttk.Label(bottom, text="Tytuł:").pack(side=tk.LEFT)
        self.title_entry = ttk.Entry(bottom)
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 12))

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)

    def _build_body(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        sidebar = ttk.Frame(paned, padding=(8, 8))
        paned.add(sidebar, weight=0)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        # -- Wczytane pliki --
        ttk.Label(sidebar, text="Wczytane pliki", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.lbl_files_empty = ttk.Label(sidebar, text="Nic nie wczytano", foreground="#888")
        self.lbl_files_empty.pack(anchor="w", pady=(2, 4))

        files_wrap = ttk.Frame(sidebar)
        files_wrap.pack(fill=tk.BOTH, expand=False)
        self.tree_files = ttk.Treeview(files_wrap, columns=("n",), height=6, selectmode="browse")
        self.tree_files.heading("#0", text="Plik / strona", anchor="w")
        self.tree_files.heading("n", text="Zad.", anchor="center")
        self.tree_files.column("#0", width=210, stretch=True)
        self.tree_files.column("n", width=46, anchor="center", stretch=False)
        files_scroll = ttk.Scrollbar(files_wrap, orient=tk.VERTICAL, command=self.tree_files.yview)
        self.tree_files.configure(yscrollcommand=files_scroll.set)
        self.tree_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_files.bind("<<TreeviewSelect>>", self.on_file_tree_select)
        self.tree_files.bind("<Button-3>", self.on_file_tree_menu)
        self.tree_files.bind("<Button-2>", self.on_file_tree_menu)

        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # -- Zaznaczone zadania --
        self.lbl_tasks_header = ttk.Label(sidebar, text="Zaznaczone zadania (0)",
                                          font=("TkDefaultFont", 10, "bold"))
        self.lbl_tasks_header.pack(anchor="w")
        self.lbl_tasks_empty = ttk.Label(
            sidebar, text="Przeciągnij myszką po stronie,\nżeby zaznaczyć zadanie.",
            foreground="#888", justify="left")
        self.lbl_tasks_empty.pack(anchor="w", pady=(2, 4))

        tasks_wrap = ttk.Frame(sidebar)
        self.tree_tasks = ttk.Treeview(tasks_wrap, columns=("src", "size"), height=8, selectmode="browse")
        self.tree_tasks.heading("#0", text="#", anchor="w")
        self.tree_tasks.heading("src", text="Skąd", anchor="w")
        self.tree_tasks.heading("size", text="Rozmiar", anchor="e")
        self.tree_tasks.column("#0", width=38, stretch=False)
        self.tree_tasks.column("src", width=140, stretch=True)
        self.tree_tasks.column("size", width=80, anchor="e", stretch=False)
        tasks_scroll = ttk.Scrollbar(tasks_wrap, orient=tk.VERTICAL, command=self.tree_tasks.yview)
        self.tree_tasks.configure(yscrollcommand=tasks_scroll.set)
        self.tree_tasks.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tasks_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_tasks.bind("<<TreeviewSelect>>", self.on_task_tree_select)
        self.tree_tasks.bind("<Delete>", lambda e: self.delete_selected_task())
        self.tree_tasks.bind("<BackSpace>", lambda e: self.delete_selected_task())

        task_btns = ttk.Frame(sidebar)
        self.btn_up = ttk.Button(task_btns, text="↑", width=3, command=lambda: self.move_task(-1))
        self.btn_up.pack(side=tk.LEFT)
        self.btn_down = ttk.Button(task_btns, text="↓", width=3, command=lambda: self.move_task(1))
        self.btn_down.pack(side=tk.LEFT, padx=(4, 0))
        self.btn_del = ttk.Button(task_btns, text="Usuń", command=self.delete_selected_task)
        self.btn_del.pack(side=tk.LEFT, padx=(10, 0))
        self.btn_clear = ttk.Button(task_btns, text="Wyczyść listę", command=self.clear_tasks)
        self.btn_clear.pack(side=tk.RIGHT)

        # -- Podgląd zadania --
        preview_header = ttk.Label(sidebar, text="Podgląd", font=("TkDefaultFont", 10, "bold"))
        self.preview_canvas = tk.Canvas(sidebar, width=280, height=140, bg="#f4f4f4",
                                        highlightthickness=1, highlightbackground="#ccc")
        self.lbl_preview_size = ttk.Label(sidebar, text="", foreground="#555")

        # Kolejność pack decyduje o podziale miejsca: podgląd i przyciski
        # rezerwują swoje, a lista zadań dostaje całą resztę. Odwrotnie
        # (lista pierwsza) podgląd wypadał poza okno na niskich ekranach.
        self.lbl_preview_size.pack(side=tk.BOTTOM, anchor="w", pady=(4, 0), fill=tk.X)
        self.preview_canvas.pack(side=tk.BOTTOM, fill=tk.X)
        preview_header.pack(side=tk.BOTTOM, anchor="w", pady=(12, 2))
        task_btns.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        tasks_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # -- Obszar strony --
        nav = ttk.Frame(right, padding=(8, 6))
        nav.pack(side=tk.TOP, fill=tk.X)
        self.btn_prev = ttk.Button(nav, text="←  Poprzednia", command=self.prev_page)
        self.btn_prev.pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav, text="—", font=("TkDefaultFont", 10, "bold"))
        self.lbl_page.pack(side=tk.LEFT, padx=12)
        self.btn_next = ttk.Button(nav, text="Następna  →", command=self.next_page)
        self.btn_next.pack(side=tk.LEFT)
        self.lbl_page_tasks = ttk.Label(nav, text="", foreground="#555")
        self.lbl_page_tasks.pack(side=tk.RIGHT)

        canvas_wrap = ttk.Frame(right)
        canvas_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_wrap, bg="#5a5a5a", highlightthickness=0, takefocus=True)
        vbar = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(canvas_wrap, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        canvas_wrap.rowconfigure(0, weight=1)
        canvas_wrap.columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Button-3>", self.on_canvas_menu)
        self.canvas.bind("<Button-2>", self.on_canvas_menu)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_wheel)
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        self.canvas.bind("<Delete>", lambda e: self.delete_selected_task())
        self.canvas.bind("<BackSpace>", lambda e: self.delete_selected_task())
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, padding=(8, 4))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_status = ttk.Label(bar, text="")
        self.lbl_status.pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(bar, length=180, mode="determinate")
        self.lbl_hint = ttk.Label(bar, text="", foreground="#666")
        self.lbl_hint.pack(side=tk.RIGHT)

    def _bind_keys(self):
        r = self.root
        r.bind("<Control-z>", lambda e: self.undo())
        r.bind("<Control-o>", lambda e: self.choose_image())
        r.bind("<Control-p>", lambda e: self.choose_pdf())
        r.bind("<Control-s>", lambda e: self.save_pdf())
        r.bind("<Prior>", lambda e: self.prev_page())
        r.bind("<Next>", lambda e: self.next_page())
        r.bind("<Control-plus>", lambda e: self.change_zoom(ZOOM_FACTOR))
        r.bind("<Control-minus>", lambda e: self.change_zoom(1 / ZOOM_FACTOR))
        r.bind("<Control-0>", lambda e: self.zoom_to_fit())

    # --- Wczytywanie plików ---

    def choose_image(self):
        paths = filedialog.askopenfilenames(
            title="Wybierz obraz (możesz zaznaczyć kilka)",
            filetypes=[("Obrazy", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff"), ("Wszystkie pliki", "*.*")],
        )
        if not paths:
            return

        first_new = None
        for path in paths:
            try:
                with Image.open(path) as opened:
                    pil = ImageOps.exif_transpose(opened).convert("RGB")
            except Exception as e:
                messagebox.showerror("Błąd odczytu obrazu", f"{os.path.basename(path)}:\n{e}")
                continue

            doc = Document(path, "image")
            page = Page(doc, doc.name, dpi=detect_dpi(pil))
            page._pil = pil
            doc.pages.append(page)
            self.documents.append(doc)
            self.pages.append(page)
            if first_new is None:
                first_new = page

        if first_new is not None:
            self.go_to_page(first_new, fit=True)
        self.refresh_all()

    def choose_pdf(self):
        path = filedialog.askopenfilename(
            title="Wybierz PDF", filetypes=[("Pliki PDF", "*.pdf"), ("Wszystkie pliki", "*.*")]
        )
        if not path:
            return

        try:
            pdf = pdfium.PdfDocument(path)
            n_pages = len(pdf)
        except Exception as e:
            messagebox.showerror("Błąd odczytu PDF", str(e))
            return

        if n_pages == 0:
            messagebox.showwarning("Pusty PDF", "Ten plik nie ma żadnych stron.")
            return

        doc = Document(path, "pdf")
        doc.pdf = pdf
        for i in range(n_pages):
            page = Page(doc, f"Strona {i + 1}", index_in_doc=i)
            doc.pages.append(page)
            self.pages.append(page)
        self.documents.append(doc)

        self.set_status(f"Wczytano „{doc.name}” — {n_pages} " + self._plural_pages(n_pages))
        self.go_to_page(doc.pages[0], fit=True)
        self.refresh_all()

    def close_document(self, doc):
        if not messagebox.askyesno(
            "Zamknąć plik?",
            f"Usunąć „{doc.name}” razem z zaznaczonymi na nim zadaniami?",
        ):
            return
        doc_pages = set(id(p) for p in doc.pages)
        self.tasks = [t for t in self.tasks if id(t.page) not in doc_pages]
        self.undo_stack = [t for t in self.undo_stack if id(t.page) not in doc_pages]
        self.pages = [p for p in self.pages if id(p) not in doc_pages]
        self.documents.remove(doc)
        if self.current_page is not None and id(self.current_page) in doc_pages:
            self.current_page = self.pages[0] if self.pages else None
            if self.current_page is not None:
                self.zoom_to_fit(redraw=False)
        self.selected_task = None
        self.refresh_all()

    # --- Nawigacja po stronach ---

    def page_index(self, page):
        for i, p in enumerate(self.pages):
            if p is page:
                return i
        return -1

    def go_to_page(self, page, fit=False):
        if page is None:
            return
        changed = page is not self.current_page
        self.current_page = page
        if fit or changed:
            self.zoom_to_fit(redraw=False)
        self.redraw()

    def prev_page(self):
        i = self.page_index(self.current_page)
        if i > 0:
            self.go_to_page(self.pages[i - 1])
            self.refresh_lists_selection()

    def next_page(self):
        i = self.page_index(self.current_page)
        if 0 <= i < len(self.pages) - 1:
            self.go_to_page(self.pages[i + 1])
            self.refresh_lists_selection()

    # --- Zoom ---

    def set_zoom(self, value, redraw=True):
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, value))
        self.lbl_zoom.config(text=f"{round(self.zoom * 100)}%")
        if redraw:
            self.redraw()

    def change_zoom(self, factor):
        if self.current_page is None:
            return
        self.set_zoom(self.zoom * factor)

    def zoom_to_fit(self, redraw=True):
        if self.current_page is None:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = self.current_page.pil.size
        self.set_zoom(min(cw / iw, ch / ih) * 0.98, redraw=redraw)

    def on_canvas_resize(self, event):
        if self.current_page is None:
            self.draw_empty_state()

    # --- Rysowanie ---

    def to_image_coords(self, event):
        x = self.canvas.canvasx(event.x) / self.zoom
        y = self.canvas.canvasy(event.y) / self.zoom
        return x, y

    def clamp_to_page(self, x, y):
        iw, ih = self.current_page.pil.size
        return max(0, min(iw, x)), max(0, min(ih, y))

    def draw_empty_state(self):
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, 0, 0))
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            cw / 2, ch / 2 - 30, text="Nie wczytano jeszcze żadnego pliku",
            fill="#ffffff", font=("TkDefaultFont", 15, "bold"))
        self.canvas.create_text(
            cw / 2, ch / 2 + 10,
            text=("1. Kliknij „Wczytaj obraz…” albo „Wczytaj PDF…”\n"
                  "2. Przeciągnij myszką prostokąt wokół zadania\n"
                  "3. Wpisz tytuł i kliknij „Zapisz PDF…”"),
            fill="#e0e0e0", font=("TkDefaultFont", 11), justify="center")

    def redraw(self):
        if self.current_page is None:
            self.draw_empty_state()
            self.refresh_controls()
            return

        pil = self.current_page.pil
        iw, ih = pil.size
        dw, dh = max(1, int(iw * self.zoom)), max(1, int(ih * self.zoom))

        resample = Image.LANCZOS if self.zoom < 1 else Image.BILINEAR
        self.tk_image = ImageTk.PhotoImage(pil.resize((dw, dh), resample))

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, dw, dh))
        self.draw_task_overlays()
        self.refresh_controls()

    def draw_task_overlays(self):
        self.canvas.delete("overlay")
        z = self.zoom
        for i, task in enumerate(self.tasks, start=1):
            if task.page is not self.current_page:
                continue
            is_sel = task is self.selected_task
            color = COLOR_RECT_SEL if is_sel else COLOR_RECT
            x1, y1 = task.x1 * z, task.y1 * z
            x2, y2 = task.x2 * z, task.y2 * z
            self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=color, width=3 if is_sel else 2, tags="overlay")
            # Numer zadania w rogu prostokąta
            self.canvas.create_rectangle(
                x1, y1, x1 + 26, y1 + 20, fill=color, outline=color, tags="overlay")
            self.canvas.create_text(
                x1 + 13, y1 + 10, text=str(i), fill="white",
                font=("TkDefaultFont", 10, "bold"), tags="overlay")

    # --- Mysz ---

    def on_mouse_down(self, event):
        if self.current_page is None:
            return
        self.canvas.focus_set()
        self.drag_start = self.clamp_to_page(*self.to_image_coords(event))
        self.dragging = True

    def on_mouse_move(self, event):
        if not self.dragging or self.current_page is None:
            return
        x, y = self.clamp_to_page(*self.to_image_coords(event))
        z = self.zoom
        self.canvas.delete("preview")
        self.canvas.create_rectangle(
            self.drag_start[0] * z, self.drag_start[1] * z, x * z, y * z,
            outline=COLOR_PREVIEW, width=2, dash=(4, 3), tags="preview")
        w = abs(int(x - self.drag_start[0]))
        h = abs(int(y - self.drag_start[1]))
        self.set_hint(f"Zaznaczenie: {w} × {h} px")

    def on_mouse_up(self, event):
        if not self.dragging or self.current_page is None:
            return
        self.dragging = False
        self.canvas.delete("preview")
        x, y = self.clamp_to_page(*self.to_image_coords(event))
        x0, y0 = self.drag_start
        self.drag_start = None

        if abs(x - x0) < MIN_RECT_PX or abs(y - y0) < MIN_RECT_PX:
            # Za małe przeciągnięcie — traktujemy jak kliknięcie w istniejące zadanie
            self.select_task(self.task_at(x, y))
            self.set_hint("")
            return

        task = Task(self.current_page, x0, y0, x, y)
        self.tasks.append(task)
        self.undo_stack.append(task)
        self.select_task(task)
        self.refresh_all()
        self.set_status(f"Dodano zadanie {len(self.tasks)} ({task.width} × {task.height} px)")
        self.set_hint("")

    def on_hover(self, event):
        if self.current_page is None or self.dragging:
            return
        x, y = self.to_image_coords(event)
        iw, ih = self.current_page.pil.size
        if not (0 <= x <= iw and 0 <= y <= ih):
            self.set_hint("")
            return
        task = self.task_at(x, y)
        if task is not None:
            self.set_hint(f"Zadanie {self.tasks.index(task) + 1} — kliknij, aby zaznaczyć")
        else:
            self.set_hint(f"x: {int(x)}, y: {int(y)}")

    def task_at(self, x, y):
        """Najmniejsze zadanie na tej stronie zawierające punkt (żeby dało się trafić w zagnieżdżone)."""
        hits = [t for t in self.tasks if t.page is self.current_page and t.contains(x, y)]
        if not hits:
            return None
        return min(hits, key=lambda t: t.width * t.height)

    def on_canvas_menu(self, event):
        if self.current_page is None:
            return
        task = self.task_at(*self.to_image_coords(event))
        if task is None:
            return
        self.select_task(task)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Usuń zadanie {self.tasks.index(task) + 1}",
                         command=lambda: self.delete_task(task))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_file_tree_menu(self, event):
        iid = self.tree_files.identify_row(event.y)
        if not iid or not iid.startswith("doc:"):
            return
        doc = self.documents[int(iid.split(":")[1])]
        self.tree_files.selection_set(iid)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Zamknij „{doc.name}”", command=lambda: self.close_document(doc))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_wheel(self, event):
        self.canvas.yview_scroll(wheel_units(event.delta), "units")

    def on_shift_wheel(self, event):
        self.canvas.xview_scroll(wheel_units(event.delta), "units")

    def on_ctrl_wheel(self, event):
        self.change_zoom(ZOOM_FACTOR if event.delta > 0 else 1 / ZOOM_FACTOR)
        return "break"

    # --- Operacje na zadaniach ---

    def select_task(self, task, scroll_into_view=False):
        self.selected_task = task
        if task is not None and task.page is not self.current_page:
            self.go_to_page(task.page)
        if task is not None and scroll_into_view:
            self.scroll_to_task(task)
        self.draw_task_overlays()
        self.refresh_lists_selection()
        self.refresh_preview()
        self.refresh_controls()

    def scroll_to_task(self, task):
        self.canvas.update_idletasks()
        dw = max(1, int(self.current_page.pil.size[0] * self.zoom))
        dh = max(1, int(self.current_page.pil.size[1] * self.zoom))
        cx = (task.x1 + task.x2) / 2 * self.zoom
        cy = (task.y1 + task.y2) / 2 * self.zoom
        self.canvas.xview_moveto(max(0.0, (cx - self.canvas.winfo_width() / 2) / dw))
        self.canvas.yview_moveto(max(0.0, (cy - self.canvas.winfo_height() / 2) / dh))

    def delete_task(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
        if task in self.undo_stack:
            self.undo_stack.remove(task)
        if self.selected_task is task:
            self.selected_task = None
        self.refresh_all()
        self.set_status("Usunięto zadanie.")

    def delete_selected_task(self):
        if self.selected_task is not None:
            self.delete_task(self.selected_task)

    def move_task(self, direction):
        task = self.selected_task
        if task is None or task not in self.tasks:
            return
        i = self.tasks.index(task)
        j = i + direction
        if not 0 <= j < len(self.tasks):
            return
        self.tasks[i], self.tasks[j] = self.tasks[j], self.tasks[i]
        self.refresh_all()

    def clear_tasks(self):
        if not self.tasks:
            return
        if not messagebox.askyesno("Wyczyścić listę?",
                                   f"Usunąć wszystkie zadania ({len(self.tasks)})?"):
            return
        self.tasks.clear()
        self.undo_stack.clear()
        self.selected_task = None
        self.refresh_all()
        self.set_status("Wyczyszczono listę zadań.")

    def undo(self):
        if not self.undo_stack:
            self.set_status("Nie ma czego cofnąć.")
            return
        task = self.undo_stack.pop()
        if task in self.tasks:
            self.tasks.remove(task)
        if self.selected_task is task:
            self.selected_task = None
        self.refresh_all()
        self.set_status("Cofnięto ostatnie zaznaczenie.")

    # --- Odświeżanie widoków ---

    def refresh_all(self):
        self.refresh_file_tree()
        self.refresh_task_tree()
        self.refresh_preview()
        self.redraw()

    def refresh_file_tree(self):
        selected_iid = None
        self.tree_files.delete(*self.tree_files.get_children())
        for di, doc in enumerate(self.documents):
            doc_tasks = sum(1 for t in self.tasks if t.page.doc is doc)
            suffix = f" ({len(doc.pages)} " + self._plural_pages(len(doc.pages)) + ")" if doc.kind == "pdf" else ""
            doc_iid = f"doc:{di}"
            self.tree_files.insert("", "end", iid=doc_iid, text=doc.name + suffix,
                                   values=(doc_tasks or "",), open=True)
            for page in doc.pages:
                pi = self.page_index(page)
                n = sum(1 for t in self.tasks if t.page is page)
                iid = f"page:{pi}"
                self.tree_files.insert(doc_iid, "end", iid=iid, text=page.label, values=(n or "",))
                if page is self.current_page:
                    selected_iid = iid

        self.lbl_files_empty.pack_forget()
        if not self.documents:
            self.lbl_files_empty.pack(anchor="w", pady=(2, 4), before=self.tree_files.master)

        if selected_iid:
            self.tree_files.selection_set(selected_iid)
            self.tree_files.see(selected_iid)

    def refresh_task_tree(self):
        self.tree_tasks.delete(*self.tree_tasks.get_children())
        for i, task in enumerate(self.tasks):
            src = task.page.doc.name
            if task.page.doc.kind == "pdf":
                src = f"{task.page.doc.name} · s.{task.page.index_in_doc + 1}"
            self.tree_tasks.insert("", "end", iid=str(i), text=str(i + 1),
                                   values=(src, f"{task.width}×{task.height}"))

        n = len(self.tasks)
        self.lbl_tasks_header.config(text=f"Zaznaczone zadania ({n})")
        self.lbl_tasks_empty.pack_forget()
        if n == 0:
            self.lbl_tasks_empty.pack(anchor="w", pady=(2, 4), before=self.tree_tasks.master)
        self.refresh_lists_selection()

    def refresh_lists_selection(self):
        if self.selected_task in self.tasks:
            iid = str(self.tasks.index(self.selected_task))
            if self.tree_tasks.exists(iid):
                self.tree_tasks.selection_set(iid)
                self.tree_tasks.see(iid)
        else:
            self.tree_tasks.selection_remove(*self.tree_tasks.selection())

        if self.current_page is not None:
            iid = f"page:{self.page_index(self.current_page)}"
            if self.tree_files.exists(iid) and iid not in self.tree_files.selection():
                self.tree_files.selection_set(iid)
                self.tree_files.see(iid)

    def refresh_preview(self):
        self.preview_canvas.delete("all")
        w = max(self.preview_canvas.winfo_width(), 280)
        h = max(self.preview_canvas.winfo_height(), 140)
        if self.selected_task is None:
            self.preview_canvas.create_text(
                w / 2, h / 2, text="Zaznacz zadanie z listy,\nżeby zobaczyć podgląd",
                fill="#999", justify="center")
            self.lbl_preview_size.config(text="")
            return
        self.lbl_preview_size.config(text=self.describe_print_size(self.selected_task))
        crop = self.selected_task.crop()
        if crop.width == 0 or crop.height == 0:
            return
        thumb = crop.copy()
        thumb.thumbnail((w - 8, h - 8), Image.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(thumb)
        self.preview_canvas.create_image(w / 2, h / 2, image=self.preview_image)

    def describe_print_size(self, task):
        """Jak duże będzie zadanie na papierze — i ile strony zostanie na rozwiązanie."""
        fit = self.fit_var.get() == SIZE_FIT
        _, _, w, h = task_layout(task, fit_to_page=fit)
        page_h = A4[1] - MARGIN_TOP - MARGIN_BOTTOM
        used = round(h / page_h * 100)
        text = f"Na stronie: {w / mm:.0f} × {h / mm:.0f} mm ({used}% wysokości)"
        if not fit:
            _, _, fw, _ = task_layout(task, fit_to_page=True)
            if w < fw - 0.5:
                return text
            return text + ", zmniejszone do strony"
        return text

    def refresh_controls(self):
        has_pages = bool(self.pages)
        has_tasks = bool(self.tasks)
        i = self.page_index(self.current_page)

        state = lambda ok: ("!disabled" if ok else "disabled")
        for btn in (self.btn_zoom_in, self.btn_zoom_out, self.btn_fit, self.btn_zoom_100):
            btn.state([state(has_pages)])
        self.btn_save.state([state(has_tasks)])
        self.btn_clear.state([state(has_tasks)])
        self.btn_prev.state([state(has_pages and i > 0)])
        self.btn_next.state([state(has_pages and 0 <= i < len(self.pages) - 1)])

        sel_ok = self.selected_task in self.tasks
        self.btn_del.state([state(sel_ok)])
        self.btn_up.state([state(sel_ok and self.tasks.index(self.selected_task) > 0)])
        self.btn_down.state([state(sel_ok and self.tasks.index(self.selected_task) < len(self.tasks) - 1)])

        if self.current_page is None:
            self.lbl_page.config(text="—")
            self.lbl_page_tasks.config(text="")
        else:
            doc = self.current_page.doc
            if doc.kind == "pdf":
                self.lbl_page.config(
                    text=f"{doc.name} — strona {self.current_page.index_in_doc + 1} "
                         f"z {len(doc.pages)}")
            else:
                self.lbl_page.config(text=doc.name)
            n = sum(1 for t in self.tasks if t.page is self.current_page)
            self.lbl_page_tasks.config(
                text=f"Na tej stronie: {n} " + self._plural_tasks(n))

    # --- Zdarzenia list ---

    def on_file_tree_select(self, event):
        sel = self.tree_files.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("page:"):
            page = self.pages[int(iid.split(":")[1])]
            if page is not self.current_page:
                self.go_to_page(page)
        elif iid.startswith("doc:"):
            doc = self.documents[int(iid.split(":")[1])]
            if doc.pages and doc.pages[0] is not self.current_page:
                self.go_to_page(doc.pages[0])

    def on_task_tree_select(self, event):
        sel = self.tree_tasks.selection()
        if not sel:
            return
        task = self.tasks[int(sel[0])]
        if task is not self.selected_task:
            self.select_task(task, scroll_into_view=True)

    # --- Pasek stanu ---

    def set_status(self, text):
        self.lbl_status.config(text=text)

    def set_hint(self, text):
        self.lbl_hint.config(text=text)

    @staticmethod
    def _plural_pages(n):
        if n == 1:
            return "strona"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "strony"
        return "stron"

    @staticmethod
    def _plural_tasks(n):
        if n == 1:
            return "zadanie"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "zadania"
        return "zadań"

    # --- Zapis ---

    def save_pdf(self):
        if not self.tasks:
            messagebox.showwarning(
                "Brak zadań",
                "Nie zaznaczono żadnego zadania.\n\n"
                "Wczytaj plik i przeciągnij myszką prostokąt wokół zadania.")
            return

        default_name = "zadania.pdf"
        title = self.title_entry.get().strip()
        if title:
            safe = "".join(ch for ch in title if ch not in '\\/:*?"<>|').strip()
            if safe:
                default_name = f"{safe}.pdf"

        pdf_path = filedialog.asksaveasfilename(
            title="Zapisz PDF z zadaniami",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("Pliki PDF", "*.pdf")],
        )
        if not pdf_path:
            return

        self.progress.pack(side=tk.LEFT, padx=12)
        self.progress["maximum"] = len(self.tasks)
        self.progress["value"] = 0

        def report(done, total):
            self.progress["value"] = done
            self.set_status(f"Zapisywanie… strona {done} z {total}")
            self.root.update_idletasks()

        try:
            create_pdf_with_tasks(self.tasks, pdf_path, title,
                                  with_grid=self.grid_var.get(),
                                  fit_to_page=self.fit_var.get() == SIZE_FIT,
                                  progress=report)
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))
            self.set_status("Zapis nie powiódł się.")
            return
        finally:
            self.progress.pack_forget()

        n = len(self.tasks)
        self.set_status(f"Zapisano {n} " + self._plural_tasks(n) + f" do: {pdf_path}")
        messagebox.showinfo("Gotowe", f"Zapisano {n} " + self._plural_tasks(n) + f":\n{pdf_path}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
