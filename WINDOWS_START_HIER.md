# AVEN Windows-Version vorbereiten

Die Mac-Version bleibt erhalten. Dieses Update ergänzt `Windows/` und einen eigenen CUDA-Build. Ziel ist dein Windows-11-PC mit RTX 3080 10 GB und 128 GB RAM.

## Einmal über GitHub Desktop hochladen

1. In GitHub Desktop das bestehende Repository **AVEN-Video-AI** auswählen und **Repository → Show in Finder** öffnen.
2. Den vollständigen Ordner **Windows** aus diesem Update in den Projektordner kopieren. `WINDOWS_START_HIER.md` ebenfalls übernehmen.
3. Die sichtbare Datei **build-windows.yml** zusätzlich in den Workflow-Ordner kopieren. Im Finder mit **⌘ + ⇧ + G** den Pfad `~/Documents/GitHub/AVEN-Video-AI/.github/workflows` öffnen und die Datei dort einfügen. Der vorhandene Mac-Workflow bleibt dort erhalten.
4. In GitHub Desktop die Windows-Dateien und `.github/workflows/build-windows.yml` auswählen. Als Summary **AVEN Windows CUDA 3.5** eintragen, committen und **Push origin** klicken. Keine heruntergeladenen Modelle, `.cache`, `engine` oder `dist` hinzufügen.
5. [GitHub Actions](https://github.com/vetonju-hub/AVEN-Video-AI/actions) öffnen. Der neue Lauf heißt **AVEN Windows CUDA**. Erst nach erfolgreichem Test, App-Build und Upload ist der Windows-Download verfügbar.
6. Das Artifact **AVEN-v3.5-Windows-CUDA-x64** herunterladen und alle ZIP-Ebenen vollständig entpacken. Den Ordner auf den Windows-PC kopieren und **AVEN Video AI.exe** starten. Ausführliche Bedienung: [Windows/README_DEUTSCH.md](Windows/README_DEUTSCH.md).

Das Update-ZIP selbst ist Quellcode und noch kein fertiger Windows-Installer. Die portable Windows-EXE entsteht durch den Windows-Build. Das große Paket enthält CUDA-Runtime und FFmpeg; Modelle werden anschließend separat geladen oder importiert. Artifacts werden wegen ihrer Größe nach drei Tagen gelöscht; heruntergeladene App und Modelle bleiben bei dir erhalten.

## Tatsächlicher Prüfstand

Die lokale Umgebung ist Linux. Die Windows-Logik und Medienpipeline wurden mit echten PNGs, FFmpeg-MP4s, EXIF-Fotos und Musik geprüft. Die Modell-Engine in den Auftragstests ist ausdrücklich eine synthetische Testfixture. Windows-Start, Windows-Paketprüfung und echte CUDA-Generierung sind hier nicht ausgeführt und müssen im Workflow bzw. auf deinem PC bestätigt werden.

Die bestehenden Swift-Dateien und der erfolgreiche Intel-Mac-Installer bleiben unverändert. Der erste Windows-KI-Test verwendet bewusst dasselbe Katzenmotiv und dieselben Qualitätsparameter, damit die erzeugten Originalbilder beurteilt werden können.
