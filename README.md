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

### Jak zbudować instalator

Instalator trzeba złożyć **na komputerze z Windowsem** - PyInstaller nie robi
kompilacji skrośnej, więc `.exe` nie powstanie na macOS ani Linuksie.

Jednorazowo, na tym komputerze:

1. [Python 3.9 lub nowszy](https://www.python.org/downloads/windows/) -
   przy instalacji zaznacz **"Add python.exe to PATH"**.
2. [Inno Setup 6](https://jrsoftware.org/isdl.php) (wersja 6.3 lub nowsza) -
   instalacja domyślna, nic nie trzeba zmieniać.

Potem, w katalogu projektu, w PowerShellu:

```
powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 -Version 1.0.0
```

Skrypt sam doinstaluje zależności i PyInstallera, zbuduje aplikację i złoży
instalator. Wynik:

```
dist\installer\MathListGenerator-1.0.0-setup.exe
```

Kolejne buildy tej samej wersji można przyspieszyć flagą `-SkipDeps`
(pomija instalację zależności).

Uwaga: instalator nie jest podpisany certyfikatem, więc przy pierwszym
uruchomieniu Windows pokaże ostrzeżenie SmartScreen - trzeba kliknąć
"Więcej informacji" i "Uruchom mimo to".

## Uruchomienie

```
python main.py
```

## Użycie

1. **Wczytaj obraz** lub **Wczytaj PDF**.
2. Myszką zaznacz prostokątami kolejne zadania (strzałki ← → przechodzą między stronami PDF).
3. `Ctrl+Z` cofa ostatnie zaznaczenie.
4. Wpisz tytuł (pojawi się na dole każdej strony) i kliknij **Zapisz PDF**.
