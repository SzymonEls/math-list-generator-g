"""Generuje assets/icon.ico - kartka z kratką i zielonym zaznaczeniem zadania.

Uruchom po zmianie wyglądu ikony:  python assets/make_icon.py
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]

BG = (37, 99, 145)          # granatowe tło
PAPER = (252, 252, 250)     # kartka
GRID = (196, 214, 228)      # kratka
SELECT = (34, 160, 70)      # zielony prostokąt zaznaczenia


def render(size):
    s = 256  # rysujemy duże i skalujemy w dół - gładsze krawędzie
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=48, fill=BG)

    page = [40, 28, s - 40, s - 28]
    d.rounded_rectangle(page, radius=10, fill=PAPER)

    step = 22
    for x in range(page[0] + step, page[2], step):
        d.line([x, page[1], x, page[3]], fill=GRID, width=3)
    for y in range(page[1] + step, page[3], step):
        d.line([page[0], y, page[2], y], fill=GRID, width=3)

    d.rounded_rectangle([62, 84, s - 62, 172], radius=6, outline=SELECT, width=11)

    return img.resize((size, size), Image.LANCZOS)


images = [render(n) for n in SIZES]
images[-1].save(OUT, format="ICO", sizes=[(n, n) for n in SIZES], append_images=images[:-1])
print(f"Zapisano {OUT}")
