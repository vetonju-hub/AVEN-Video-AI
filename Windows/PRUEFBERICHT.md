# Windows-Prüfstand vom 5. November 2026

Zielsystem ist Windows 11 x64 mit RTX 3080 (10 GB) und 128 GB RAM.

## Ausgeführt

- 60 Python-Tests auf Linux mit Pillow 11.3.0 und echten PNG-, JPEG-, H.264-MP4-, WAV- und VBR-MP3-Dateien bestanden.
- Die gepackte Linux-Testversion mit PyInstaller 6.16.0 bestand den Exporttest sowie den GUI-Test unter Xvfb. Der GUI-Test prüfte Sprachwechsel, den Erhalt von Prompt, Seed und Länge, die Szenenbearbeitung und die Vorschau gespeicherter Projektbilder.
- Literal geprüfte CUDA0-/CPU-Zuweisung, alle Qualitätsstufen und Formate, ungültige Längen/Seeds, Unicode und Zeichen in Pfaden/Prompts, Manifestpfade, Prüfsummen und Abbruch.
- 33 Bilder werden geschrieben und tatsächlich dekodiert; Farben/Orientierung, genaue Clipdauer, exaktes 1,337-Sekunden-Ende, vollständiger Song, Tonhöhe und Ton am Ende sowie fehlende Musikschleifen geprüft.
- VBR-MP3 ohne Xing-Dauerheader: tatsächliche Samplezahl statt ungenauer Bitratenschätzung; rund 5,407 statt fälschlich 9,034 Sekunden.
- Gesicherte Referenzen, Integritätsprüfung und unterbrochene Aufträge mit vollständigen Szenen: Fortsetzen erhält deren Dateien.
- Regression eines ausgetauschten 64×64-Videocaches bei angeforderten 832×480: erkannt und aus den geprüften Originalbildern rekonstruiert, ohne neuen Modelllauf. Clipauflösung, Bildrate, Codec, Bildanzahl, Dauer und gespeicherte SHA256 werden geprüft.
- Download-Prüfsummen, keine Veröffentlichung beschädigter Archive, Archivpfade mit Traversal/Windows-Laufwerken und Kollisionen geprüft.
- Python-Syntax der Windows-Dateien und Windows-Pakettests wurden geprüft.
- Die Fortsetzungstests prüfen die vier Referenzbilder, Originalbild und Originalton am Anfang, Musik im neuen Teil, Dauer und Abbruch mit anschließendem Fortsetzen. Der Auftrag behält seinen Avatar auch nach Austausch des Profilbildes. Zusätzliche Tests decken kurze Hochkantclips sowie SDR- und HDR-Import ab.

## Neue Studio-Funktionen geprüft

- Live-Prozessausgabe kommt vor Prozessende an; getrennte UTF-8-Bytes, CR-/ANSI-Zeilen und Abbruch werden korrekt verarbeitet.
- Nur der verbose `sample WxHxT`-Marker aktiviert die Samplingzählung. VAE-Kacheln und Gewichts-Ladezähler dürfen die KI-Schrittanzeige nicht vorzeitig fortschalten, auch bei derselben Gesamtzahl.
- Unbekannte Zeiten bleiben unbekannt. GPU-Messfehler blockieren den Auftrag nicht.
- RTX-10-GB-Profil setzt RAM-Gewichte und 8 GiB verwaltetes CUDA-Budget. Residentes Vergleichsprofil und 8-GB-Gerät mit 6-GiB-Budget geprüft; Qualitätsparameter bleiben gleich.
- Aufsteigende endliche Abschnittszeiten, kurze Songs, gemeinsame Motiv-/Stiltexte, abschnittsabhängige Prompts und feste/wechselnde Referenzen geprüft. Die Auftragspipeline behält ihren gesicherten Plan beim Fortsetzen, auch wenn das ursprüngliche Formular geändert wird.
- Projektübersicht isoliert beschädigte Metadaten; Originalbilder und Referenzen bleiben im gewählten Auftragspfad. Symlinks außerhalb werden nicht als Originalbilder angezeigt.
- Manuelle Qualitätsbewertung ändert die Messwerte nicht; synthetische Testfixtures werden im Bericht ausdrücklich gekennzeichnet.
- Unabhängige Nachprüfung: ungültige JSON-Wurzeltypen in Projekten und beschädigte Berichtfelder werden isoliert behandelt; Regressionen einschließlich sehr großer Zahlen geprüft. Abschluss-/Abbruchphasen erscheinen auch innerhalb des Drosselungsfensters. Offene Szenenplan-Vorschauen wechseln ihre erzeugten Beschriftungen sofort zwischen DE/EN, ohne Prompt-Inhalt zu ändern.
- Die GUI-Prüfung umfasst Szeneneditor, ImageTk-Vorschauen, A/B-Vergleich, Referenzanzeige, Originalgröße und Bewertungsspeicherung. Der native Windows-Lauf steht aus.

## Noch nicht ausgeführt

Der letzte native Windows-Lauf bestand 48 Tests und erzeugte die EXE. Beim Start von `sd-cli.exe` meldete der Windows-Loader `0xC0000135`. Die korrigierte Paketierung bindet die zu `ggml-base.dll` gehörende OpenMP-Bibliothek ein und lädt die treiberunabhängigen Bibliotheken im Pakettest. Die CUDA-Engine benötigt außerdem `nvcuda.dll` aus dem installierten NVIDIA-Treiber. Wenn der Treiber auf dem Runner fehlt, meldet der Pakettest den CLI-Test ausdrücklich als `not_run_no_nvidia_driver`. [Nativer Windows-Lauf](https://github.com/vetonju-hub/AVEN-Video-AI/actions/runs/41944809640)

Die korrigierte Windows-EXE muss im nativen Workflow noch gebaut und gestartet werden. CUDA-Modellgenerierung, VRAM-Verbrauch, Renderzeit und sichtbare Motivqualität benötigen einen Lauf auf dem RTX-PC.

Die Engine in den Auftragstests erzeugt ausdrücklich synthetische Testbilder. Das ist kein KI-Inferenzbeleg. Ein früherer Linux-Einzelbildtest verwendete eine andere Engine-Revision und ersetzt keinen Windows/CUDA-Videotest.

## Entscheidungen

Die Windows-Oberfläche verwendet Tk/ttk und Pillow und wird gemeinsam mit dem Python-Laufzeitsystem in eine portable App gepackt; Endnutzer benötigen keine Python-Installation. Die offizielle Windows-CUDA12-Engine ist auf `master-1043-3be2378` festgeschrieben, ihre Archive und das FFmpeg-Archiv auf veröffentlichte SHA256. Diese Engine-Revision muss im Windows/CUDA-Betrieb geprüft werden.

## Nächster Nachweis

Nach dem Upload muss **AVEN Windows CUDA** alle Tests und den nativen Build erfolgreich abschließen. Das Artifact enthält dann die vollständige portable App. Erst danach den 2-Sekunden-Qualitätstest auf dem Windows-PC starten und die Original-PNGs sowie `engine.log` beurteilen.
