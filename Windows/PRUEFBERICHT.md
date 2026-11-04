# Windows-Prüfstand vom 4. November 2026

Ziel: Windows 11 x64, NVIDIA RTX 3080 10 GB, 128 GB RAM. Vorhandene Mac-Version bleibt unverändert.

## Ausgeführt

- 45 Python-unittest-Tests auf Linux mit echten PNG-, JPEG-, H.264-MP4-, WAV- und VBR-MP3-Dateien und dem installierten FFmpeg.
- Sprachumschaltung Deutsch/Englisch: gespeicherte Auswahl, beschädigte Einstellungen, aktuelle Sprache für dynamische Status-/Fehlermeldungen, passende Formatplatzhalter und aktive Textbindungen ohne Neuerstellen der Steuerelemente geprüft. Der native Windows-GUI-Smoketest prüft zusätzlich echte Sprachbutton-Klicks und den Erhalt von Prompt, Seed, Länge und deaktivierten Steuerelementen; dieser GUI-Test ist lokal mangels Displayserver weiterhin nicht ausgeführt.
- Literal geprüfte CUDA0-/CPU-Zuweisung, alle Qualitätsstufen und Formate, ungültige Längen/Seeds, Unicode und Zeichen in Pfaden/Prompts, Manifestpfade, Prüfsummen und Abbruch.
- 33 Bilder werden geschrieben und tatsächlich dekodiert; Farben/Orientierung, genaue Clipdauer, exaktes 1,337-Sekunden-Ende, vollständiger Song, Tonhöhe und Ton am Ende sowie fehlende Musikschleifen geprüft.
- VBR-MP3 ohne Xing-Dauerheader: tatsächliche Samplezahl statt ungenauer Bitratenschätzung; rund 5,407 statt fälschlich 9,034 Sekunden.
- Gesicherte Referenzen, Integritätsprüfung und unterbrochene Aufträge mit vollständigen Szenen: Fortsetzen erhält deren Dateien.
- Regression eines ausgetauschten 64×64-Videocaches bei angeforderten 832×480: erkannt und aus den geprüften Originalbildern rekonstruiert, ohne neuen Modelllauf. Clipauflösung, Bildrate, Codec, Bildanzahl, Dauer und gespeicherte SHA256 werden geprüft.
- Download-Prüfsummen, keine Veröffentlichung beschädigter Archive, Archivpfade mit Traversal/Windows-Laufwerken und Kollisionen geprüft.
- Python-Syntax aller Windows-Dateien; bestehende Paket-/Shell-/Workflowprüfungen: vier bestanden, Swift-Compilerprüfung mangels Compiler übersprungen.
- PyInstaller 6.16.0 erzeugte hier ein Linux-Testbundle desselben Programmkerns. Sein Medientest, das Laden der gebündelten Modellquellen und der Sprach-/Einstellungstest liefen erfolgreich. Dies ist keine Windows-EXE und wird nicht als solche ausgeliefert.
- Frische unabhängige Codeprüfung mit reproduzierten Tests. Beide relevanten Befunde sind durch zuvor fehlgeschlagene Regressionstests korrigiert. Der zuerst angefragte Reviewer war wegen eines Nutzungslimits nicht verfügbar; ein anderer Reviewer hat die Prüfung durchgeführt.

## Neue Studio-Funktionen geprüft

- Live-Prozessausgabe kommt vor Prozessende an; getrennte UTF-8-Bytes, CR-/ANSI-Zeilen und Abbruch werden korrekt verarbeitet.
- Nur der verbose `sample WxHxT`-Marker aktiviert die Samplingzählung. VAE-Kacheln und Gewichts-Ladezähler dürfen die KI-Schrittanzeige nicht vorzeitig fortschalten, auch bei derselben Gesamtzahl.
- Unbekannte Zeiten bleiben unbekannt. GPU-Messfehler blockieren den Auftrag nicht.
- RTX-10-GB-Profil setzt RAM-Gewichte und 8 GiB verwaltetes CUDA-Budget. Residentes Vergleichsprofil und 8-GB-Gerät mit 6-GiB-Budget geprüft; Qualitätsparameter bleiben gleich.
- Aufsteigende endliche Abschnittszeiten, kurze Songs, gemeinsame Motiv-/Stiltexte, abschnittsabhängige Prompts und feste/wechselnde Referenzen geprüft. Die Auftragspipeline behält ihren gesicherten Plan beim Fortsetzen, auch wenn das ursprüngliche Formular geändert wird.
- Projektübersicht isoliert beschädigte Metadaten; Originalbilder und Referenzen bleiben im gewählten Auftragspfad. Symlinks außerhalb werden nicht als Originalbilder angezeigt.
- Manuelle Qualitätsbewertung ändert die Messwerte nicht; synthetische Testfixtures werden im Bericht ausdrücklich gekennzeichnet.
- Unabhängige Nachprüfung: ungültige JSON-Wurzeltypen in Projekten und beschädigte Berichtfelder werden isoliert behandelt; Regressionen einschließlich sehr großer Zahlen geprüft. Abschluss-/Abbruchphasen erscheinen auch innerhalb des Drosselungsfensters. Offene Szenenplan-Vorschauen wechseln ihre erzeugten Beschriftungen sofort zwischen DE/EN, ohne Prompt-Inhalt zu ändern.
- Native Windows-GUI-Prüfung wurde um Szeneneditor, echte ImageTk-Vorschauen, A/B-Vergleich, Referenzanzeige, Originalgröße und Bewertungsspeicherung erweitert. Ihr tatsächlicher Lauf steht noch aus.

## Noch nicht ausgeführt

Der Windows-Build ist implementiert, aber noch nicht auf GitHub hochgeladen/ausgeführt. Daher gibt es für dieses Update noch keine bestätigte Windows-EXE. Die vorhandene GitHub-Verbindung hat keine nutzbaren Schreibrechte; als Übergabe wird das geprüfte Quellcode-Update über GitHub Desktop hochgeladen.

Die lokale Umgebung hat keinen Displayserver und keine NVIDIA-GPU. Windows-GUI, tatsächliches Laden aller CUDA-/CRT-DLLs, Windows-Prozessabbruch und der native Paketstart müssen im Windows-Workflow geprüft werden. Echte CUDA-Modellgenerierung, VRAM-Verbrauch, Renderzeit und sichtbare Motivqualität benötigen anschließend den kurzen Test auf dem RTX-PC.

Die Engine in den Auftragstests erzeugt ausdrücklich synthetische Testbilder. Das ist kein KI-Inferenzbeleg. Der frühere Linux-Einzelbildtest verwendete eine andere, für den Mac festgeschriebene Engine-Revision und ersetzt keinen Windows/CUDA-Videotest.

## Entscheidungen

Die zusätzliche Windows-Oberfläche verwendet Tk/ttk und Pillow. Sie unterscheidet sich optisch von SwiftUI und wird gemeinsam mit dem Python-Laufzeitsystem in eine portable App gepackt; Endnutzer benötigen keine Python-Installation. Die offizielle Windows-CUDA12-Engine ist auf `master-1043-3be2378` festgeschrieben, ihre Archive und das FFmpeg-Archiv auf veröffentlichte SHA256. Diese Engine-Revision ist eigenständig gegenüber dem Mac zu prüfen.

## Nächster Nachweis

Nach dem Upload muss **AVEN Windows CUDA** alle Tests und den nativen Build erfolgreich abschließen. Das Artifact enthält dann die vollständige portable App. Erst danach den 2-Sekunden-Qualitätstest auf dem Windows-PC starten und die Original-PNGs sowie `engine.log` beurteilen.
