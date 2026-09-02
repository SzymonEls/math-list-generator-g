# math-list-generator

Narzędzie do wycinania zadań z obrazów i plików PDF i składania ich w nowy PDF
(jedno zadanie na stronę, kratka w tle, tytuł i numeracja stron).

## Instalacja

Wymagany Python 3.9 lub nowszy.

```
python -m pip install -r requirements.txt
```

To wszystko — nie trzeba instalować Popplera ani żadnych innych programów
systemowych. Czcionka `DejaVuSans.ttf` (polskie znaki w PDF) jest dołączona
do repozytorium.

Na Linuksie `tkinter` bywa osobnym pakietem systemowym:

```
sudo apt install python3-tk
```

Zalecane (żeby nie mieszać w systemowym Pythonie) — środowisko wirtualne:

```
python -m venv .venv
```

Aktywacja: `source .venv/bin/activate` (Linux/macOS) lub
`.venv\Scripts\activate` (Windows), a potem `python -m pip install -r requirements.txt`.

## Uruchomienie

```
python main.py
```

## Użycie

1. **Wczytaj obraz** lub **Wczytaj PDF**.
2. Myszką zaznacz prostokątami kolejne zadania (strzałki ← → przechodzą między stronami PDF).
3. `Ctrl+Z` cofa ostatnie zaznaczenie.
4. Wpisz tytuł (pojawi się na dole każdej strony) i kliknij **Zapisz PDF**.
