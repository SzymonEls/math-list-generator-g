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

## Instalator dla Windows

Dla osób, które nie chcą instalować Pythona, jest instalator `.exe`: skrót
w menu Start, opcjonalny skrót na pulpicie i odinstalowanie przez
"Aplikacje i funkcje". Nie wymaga uprawnień administratora (domyślnie instaluje
się dla bieżącego użytkownika).

Gotowy plik `MathListGenerator-<wersja>-setup.exe` znajduje się w zakładce
[Releases](https://github.com/SzymonEls/math-list-generator-g/releases).

### Zbudowanie nowej wersji instalatora

Najprościej przez GitHub Actions - instalator powstaje automatycznie po
wypchnięciu taga:

```
git tag v1.0.0
git push origin v1.0.0
```

Plik trafia do artefaktów przebiegu i do release'u dla tego taga. Można też
uruchomić workflow ręcznie z zakładki **Actions → Instalator Windows → Run workflow**.

Lokalnie (na maszynie z Windowsem, Pythonem i [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```
powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 -Version 1.0.0
```

Wynik: `dist\installer\MathListGenerator-1.0.0-setup.exe`.

Uwaga: instalatora nie da się zbudować na macOS ani Linuksie - PyInstaller nie
robi kompilacji skrośnej, `.exe` musi powstać na Windowsie.

## Uruchomienie

```
python main.py
```

## Użycie

1. **Wczytaj obraz** lub **Wczytaj PDF**.
2. Myszką zaznacz prostokątami kolejne zadania (strzałki ← → przechodzą między stronami PDF).
3. `Ctrl+Z` cofa ostatnie zaznaczenie.
4. Wpisz tytuł (pojawi się na dole każdej strony) i kliknij **Zapisz PDF**.
