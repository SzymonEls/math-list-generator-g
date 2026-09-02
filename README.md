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

Dla osób, które nie chcą instalować Pythona, jest zwykły instalator `.exe`:
skrót w menu Start, opcjonalny skrót na pulpicie i odinstalowanie przez
"Aplikacje i funkcje". Nie wymaga uprawnień administratora (domyślnie instaluje
się dla bieżącego użytkownika, można przełączyć na "dla wszystkich").

Gotowy plik do pobrania:
[Releases](https://github.com/SzymonEls/math-list-generator-g/releases).

### Jak zbudować instalator

Instalator trzeba złożyć **na komputerze z Windowsem** - PyInstaller nie robi
kompilacji skrośnej, więc `.exe` nie powstanie na macOS ani Linuksie.

Jednorazowo, na tym komputerze:

1. [Python 3.9 lub nowszy](https://www.python.org/downloads/windows/) -
   przy instalacji zaznacz **"Add python.exe to PATH"**.
2. Inno Setup 6 (wersja 6.3 lub nowsza):

   ```
   winget install -e --id JRSoftware.InnoSetup
   ```

   albo ręcznie z [jrsoftware.org](https://jrsoftware.org/isdl.php) -
   instalacja domyślna, nic nie trzeba zmieniać.

Potem, w katalogu projektu, w PowerShellu:

```
powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1
```

Skrypt sam doinstaluje zależności i PyInstallera, zbuduje aplikację i złoży
instalator. Numer wersji bierze z `APP_VERSION` w `main.py`. Wynik:

```
dist\installer\MathListGenerator-1.0.0-setup.exe
```

Przydatne flagi:

| Flaga | Do czego |
| --- | --- |
| `-SkipDeps` | pomija `pip install` - kolejne buildy idą szybciej |
| `-SkipInstaller` | buduje samą aplikację do `dist\MathListGenerator\`, bez Inno Setup |
| `-Version X.Y.Z` | wersja inna niż `APP_VERSION` (np. build testowy) |

Uruchamiać zawsze `.exe` z katalogu `dist`. Katalog `build` to śmieci robocze
PyInstallera - leży w nim druga kopia `MathListGenerator.exe`, która jest samym
bootloaderem bez `python3xx.dll` i przy uruchomieniu daje
"Failed to load Python DLL". Skrypt kasuje ten katalog po udanym buildzie.

### Wydanie nowej wersji

1. Podnieś `APP_VERSION` w [`main.py`](main.py) do `X.Y.Z` i zacommituj.
   To jedyne miejsce z numerem wersji - stąd bierze go tytuł okna, właściwości
   `.exe` i nazwa pliku instalatora.
2. Zbuduj instalator (polecenie wyżej).
3. Zainstaluj wynikowy `.exe` u siebie i sprawdź, czy działa skrót w menu Start
   i czy da się odinstalować.
4. Otaguj i wypchnij tag:

   ```
   git tag -a v1.0.0 -m "Wersja 1.0.0"
   git push origin v1.0.0
   ```

5. Na GitHubie: **Releases** -> **Draft a new release** -> wybierz tag `v1.0.0`,
   dołącz plik `MathListGenerator-1.0.0-setup.exe`, opisz co się zmieniło
   i **Publish release**.

Uwaga: instalator nie jest podpisany certyfikatem, więc przy pierwszym
uruchomieniu Windows pokaże ostrzeżenie SmartScreen - trzeba kliknąć
"Więcej informacji" i "Uruchom mimo to". Warto o tym uprzedzić w opisie wydania.

## Uruchomienie

```
python main.py
```

## Użycie

1. **Wczytaj obraz…** (można zaznaczyć kilka plików naraz) albo **Wczytaj PDF…**.
   Wczytane pliki pojawią się na liście po lewej — przy każdej stronie widać,
   ile zadań już na niej zaznaczono.
2. Przeciągnij myszką prostokąt wokół zadania. Zaznaczenie dostaje numer,
   trafia na listę **Zaznaczone zadania** i widać je w **Podglądzie**.
   Zaznaczone zadanie można jeszcze poprawić — patrz niżej.
3. Wpisz tytuł (pojawi się na dole każdej strony) i kliknij **Zapisz PDF…**.
   Zadania trafią do PDF-u w kolejności z listy — po jednym na stronę.

### Rozmiar zadania na stronie

- **Naturalny (bez powiększania)** — domyślnie. Zadanie trafia na stronę
  w rozmiarze wynikającym z rozdzielczości źródła, więc małe zadanie zostaje
  małe, a reszta strony zostaje wolna na rozwiązanie. Wycinek, który nie
  mieści się w marginesach, jest zmniejszany.
- **Dopasuj do strony** — zadanie rozciągane na całą szerokość, także
  powiększane. Przydatne przy słabo czytelnych skanach.

Pod podglądem widać, ile milimetrów zajmie zadanie na papierze i jaki to
procent wysokości strony.

Rozdzielczość stron PDF jest znana dokładnie. Dla obrazów program czyta DPI
z metadanych pliku, a gdy ich nie ma (albo są bezsensownie niskie), zakłada
200 dpi — typowy skan. Jeśli zadania wychodzą za małe lub za duże, przełącz
tryb na **Dopasuj do strony**.

### Poprawianie zaznaczenia

Zaznaczone zadanie ma białe uchwyty w rogach i na środkach boków:

- **przeciągnij wnętrze** prostokąta, żeby przesunąć zadanie po stronie,
- **przeciągnij uchwyt**, żeby zmienić rozmiar (róg zmienia dwa boki naraz),
- **strzałki** przesuwają co 1 piksel, **Shift + strzałki** co 10.

Kursor podpowiada, co się stanie: krzyżyk rysuje nowy prostokąt, dłoń
przesuwa, strzałka na krawędzi zmienia rozmiar. Zadanie nie wyjedzie poza
stronę, a `Ctrl+Z` cofa też przesunięcia i zmiany rozmiaru (cała seria
przesunięć strzałkami to jeden krok cofania).

Żeby narysować nowy prostokąt w obrębie istniejącego zadania, najpierw
kliknij poza nim — przesuwa się tylko zadanie aktualnie zaznaczone.

### Panel boczny

- **Wczytane pliki** — co jest załadowane i ile zadań przypada na każdą stronę.
  Kliknięcie strony przechodzi do niej. Prawy przycisk myszy na nazwie pliku
  pozwala go zamknąć.
- **Zaznaczone zadania** — pełna lista w kolejności, w jakiej trafią do PDF-u.
  Kliknięcie przeskakuje do zadania na stronie, `↑` / `↓` zmieniają kolejność,
  **Usuń** kasuje pojedyncze zadanie.
- **Podgląd** — wycinek, który faktycznie trafi na stronę PDF-u.

### Skróty klawiszowe

| Skrót | Działanie |
| --- | --- |
| `Ctrl+O` / `Ctrl+P` | wczytaj obraz / PDF |
| `Ctrl+S` | zapisz PDF |
| `Ctrl+Z` | cofnij ostatnie zaznaczenie |
| `Delete` | usuń zaznaczone zadanie |
| strzałki | przesuń zaznaczone zadanie o 1 px |
| `Shift` + strzałki | przesuń zaznaczone zadanie o 10 px |
| `PgUp` / `PgDn` | poprzednia / następna strona |
| `Ctrl` + kółko myszy | powiększanie |
| `Ctrl+0` | dopasuj stronę do okna |
| kółko myszy, `Shift` + kółko | przewijanie w pionie / poziomie |

### Wskazówki

- Kliknięcie w istniejący prostokąt zaznacza go (bez tworzenia nowego).
- Po zaznaczeniu prostokąt można przesuwać i skalować — nie trzeba go
  kasować i rysować od nowa.
- Prawy przycisk myszy na prostokącie pozwala go usunąć.
- Strony PDF-u renderują się dopiero przy pierwszym wyświetleniu, więc nawet
  duże pliki otwierają się od razu.
- **Kratka** wyłącza szarą siatkę na stronach wynikowego PDF-u.
