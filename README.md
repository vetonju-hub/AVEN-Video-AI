# AVEN Video AI – Windows CUDA

AVEN Video AI wird aktuell **ausschließlich für Windows 11 x64** entwickelt.
Die lokale Video-KI verwendet NVIDIA CUDA; zur Bedienung der fertig gebauten App
werden keine Python-Installation und kein Terminal benötigt.

## Die einzige aktive Codebasis

- `Windows/aven/` – Oberfläche, KI-Pipeline, Medien, Musik, Projekte, Avatar
- `Windows/main.py` – Programmstart
- `Windows/build.py` – Windows-Paket erstellen
- `Windows/assets/aven-icon.png` – Windows-App-Icon
- `Windows/tests/` – Tests
- `.github/workflows/build-windows.yml` – automatischer Windows-Build

Die alte zweite Kopie und die plattformfremde Implementierung sind aus dem
aktuellen Projekt entfernt. Der frühere Stand bleibt im Git-Verlauf verfügbar.

## Die Windows-App herunterladen

1. [GitHub Actions](https://github.com/vetonju-hub/AVEN-Video-AI/actions/workflows/build-windows.yml) öffnen.
2. Einen **erfolgreichen** Lauf von **AVEN Windows CUDA** auswählen.
3. Unter Artifacts `AVEN-v3.5-Windows-CUDA-x64` herunterladen.
4. Beide ZIP-Ebenen vollständig entpacken.
5. `AVEN Video AI.exe` starten. Die Ordner `engine` und `_internal` nicht entfernen.
6. Den NVIDIA-Treiber prüfen und die Modelle laden oder importieren.
7. Erst den 2-Sekunden-Test ausführen und Originalbilder sowie `engine.log` prüfen.

Genauer Ablauf: [Windows/README_DEUTSCH.md](Windows/README_DEUTSCH.md).

## Automatische Tests (Windows-Entwicklung)

Im Ordner `Windows` mit Python 3.12:

```powershell
python -m pip install -r requirements-build.txt
python prepare_tests.py
python -m unittest discover -s tests -v
python build.py
```

Der Windows-Workflow kompiliert und prüft das Paket. **Ein erfolgreicher Build
belegt keine brauchbare CUDA-Bildqualität:** Ein echtes Rendering auf dem PC ist
weiter erforderlich. Aktueller Prüfstand: [Windows/PRUEFBERICHT.md](Windows/PRUEFBERICHT.md).
