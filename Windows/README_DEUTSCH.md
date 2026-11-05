# AVEN Video AI 3.5 – Windows CUDA

Windows-Version des vorhandenen AVEN-Projekts, ausgelegt für deinen Windows-11-PC mit RTX 3080 10 GB und 128 GB RAM. Die Mac-App bleibt als eigene Version im Repository erhalten.

## Sprache umschalten

Oben im Fenster stehen die beiden Schaltflächen **Deutsch** und **English**. Ein Klick stellt Beschriftungen, Hinweise, Dialogtitel, Status- und eigene Fehlermeldungen sofort um. Die gewählte Sprache wird in `%LOCALAPPDATA%\AVEN Video AI\settings.json` gespeichert und beim nächsten Start geladen. Die Umschaltung funktioniert auch während einer laufenden Berechnung. Prompts, Seeds und ausgewählte Medien bleiben dabei erhalten. Technische Originalprotokolle der KI-Engine und Meldungen des Betriebssystems behalten ihre ursprüngliche Sprache.

## Fertige App starten

1. In GitHub Actions den erfolgreichen Lauf **AVEN Windows CUDA** öffnen.
2. Das Artifact **AVEN-v3.5-Windows-CUDA-x64** herunterladen. Das äußere GitHub-Artifact-ZIP enthält das eigentliche portable ZIP.
3. Beide ZIPs vollständig entpacken. Den gesamten Ordner **AVEN Video AI** behalten; die EXE benötigt die Unterordner **engine** und **_internal**.
4. **AVEN Video AI.exe** doppelklicken. Python, CUDA-Toolkit und Terminal sind für die fertige App nicht nötig. Ein funktionsfähiger NVIDIA-Treiber muss installiert sein.
5. **NVIDIA prüfen** anklicken. Danach bei Realismusstufe 1 die **Modelle herunterladen** oder vorhandene AVEN-Modellgewichte **importieren**. Der Download umfasst mehrere GB. Prüfsummen werden vollständig geprüft.
6. **2-Sekunden-Qualitätstest** starten. Er verwendet automatisch den Katzen-Prompt, Seed 42, 832×480, 20 Schritte und 33 Bilder bei 16 FPS. Das ist die Videolänge, keine Zusage zur Berechnungsdauer.
7. Nach Abschluss **KI-Vorschau öffnen**. Über **Szenenordner / Protokolle** die Original-PNGs und `engine.log` prüfen. Scharfe, erkennbare Originalmotive müssen tatsächlich vorhanden sein.

Wenn Windows die noch nicht kommerziell signierte App überprüft, Herausgeber, Download und Prüfprotokoll kontrollieren. Keine Windows-Sicherheitsfunktionen global abschalten.

## Video fortsetzen und Avatar verwenden

1. Unter **Video fortsetzen** auf **Clip auswählen** klicken und das Video öffnen.
2. Unter **Szenenbeschreibung** eingeben, was danach passieren soll. Für den ersten Versuch **Zusätzliche Länge (Sekunden)** auf `2` und Realismus auf Stufe `1` setzen.
3. Bei Bedarf unter **Fester Avatar** ein Bild auswählen und **Gespeicherten Avatar für alle Szenen verwenden** aktivieren. Das Bild steht auch beim nächsten App-Start zur Verfügung.
4. **KI-Video generieren** starten und nach Abschluss **KI-Vorschau öffnen** wählen.

AVEN verwendet die letzten vier Bilder des Clips für den Übergang. Die exportierte MP4 beginnt mit dem Originalinhalt und seinem Ton und hängt die neue Handlung an. Das gewählte Format gilt für den gesamten Export. Importierte Musik und die Längeneinstellung gelten für den angehängten Teil. Die Quelldatei bleibt erhalten.

Das Avatarbild hat Vorrang vor anderen Motivbildern und kann auch ohne Fortsetzungsclip verwendet werden. Das Modell kann Gesicht, Kleidung und Übergänge unterschiedlich darstellen. Gespeicherte Aufträge behalten ihre jeweilige Kopie der Referenz.

## Eigene Videos

Mehrzeiligen englischen Prompt, negativen Prompt, Seed und Format wählen. Fotos werden mit EXIF-Ausrichtung übernommen. **Video als Referenz** extrahiert pro Video ein Bild zur eingestellten Zeit; es überträgt keine Originalbewegung. Standardmäßig wird die erste Referenz als Hauptmotiv in allen Szenen verwendet. Mit **Als Hauptmotiv wählen** die ausgewählte Referenz an die erste Stelle setzen. Den festen Modus ausschalten, damit Referenzen je Szene wechseln. Identische Gesichter sind dadurch nicht garantiert.

Musik importieren und **Videolänge automatisch an die gesamte Musik anpassen** einschalten, um die volle dekodierte Audiodauer zu verwenden. Ohne Musik gilt die eigene Länge. Bei einem manuell längeren Video bleibt die Zeit nach dem Songende stumm. Musik wird nicht wiederholt oder beschleunigt. Die Eingabegrenze beträgt 24 Stunden, nicht 240 Sekunden.

**Anhalten** beendet nur die eigenen Unterprozesse. **Auftrag fortsetzen** öffnet die gespeicherte `job.json`; vollständige, erneut geprüfte Szenen werden weiterverwendet. Unterbrochene Szenen werden archiviert und neu berechnet. Referenzen und Musik liegen als gesicherte Kopien im Auftragsordner. Änderungen an diesen Kopien werden erkannt.

Modelle und Aufträge: `%LOCALAPPDATA%\AVEN Video AI\Models` und `%LOCALAPPDATA%\AVEN Video AI\Jobs`. Eine neue App-Version ersetzt diese Dateien nicht.

## Qualität und Hardware

Stufen 1–7 entsprechen den Mac-Profilen: 480p, Q4/UMT5 Q3, 20–36 Schritte. Stufen 8–10: höhere Auflösung, Q8/UMT5 Q5, 40–50 Schritte. Höhere Stufen benötigen zusätzliche Modellgewichte und können 10 GB VRAM überschreiten.

Diffusion läuft ausdrücklich auf **CUDA0**, Textencoder und VAE auf CPU/RAM. Standardmäßig liegen auch die Diffusionsgewichte im Arbeitsspeicher und werden segmentweise zur RTX übertragen. Auf einer 10-GB-Karte wird ein verwaltetes CUDA-Budget von 8 GiB gesetzt; zwei GiB sind als Reserve eingeplant. Das ist kein harter physischer Grenzwert und garantiert nicht, dass jedes Profil passt. **Diffusionsgewichte dauerhaft im VRAM halten** ist ein Vergleichsprofil für den gleichen kurzen Test, ohne Auflösung, Schritte oder Bilderzahl zu ändern. Das nutzt die RTX für die zentrale Modellberechnung und entlastet den Grafikspeicher. Fehlendes CUDA führt zu einer verständlichen Fehlermeldung, nicht zu einem stillen CPU-Ersatz oder einer schlechteren Qualitätsstufe. 128 GB RAM ersetzen die 10 GB Grafikspeicher nicht. Ergebnisse verschiedener Backends sind nicht garantiert pixelgleich.

## Entwicklungs- und Prüfstatus

Der Quellcode enthält vollständige Oberfläche, Auftragspipeline, Modellverwaltung, Medienexport und Windows-Build. Lokale Tests laufen auf Linux mit echten PNGs, MP4s und Musik sowie einer ausdrücklich synthetischen Engine-Testfixture. Sie beweisen keine Windows-Ausführung und keine CUDA-Modellgenerierung.

Der Windows-Workflow prüft diese Tests auf Windows, erzeugt die portable EXE und startet die gebündelte App für Medien- und GUI-Smoketests. Ein normaler GitHub-Runner hat keine RTX 3080; die echte CUDA-Berechnung und Bildqualität müssen anschließend auf deinem PC geprüft werden. Ein Installer wird erst als vorhanden bezeichnet, wenn der Windows-Lauf und der Artifact-Upload tatsächlich erfolgreich waren.

Das Paket enthält die x64-CRT- und OpenMP-Bibliotheken aus dem Visual-Studio-Redistributable. Der Paketselbsttest lädt die treiberunabhängigen Engine-DLLs auch auf einem Rechner ohne Grafikkarte; Fehler stoppen den Build. Die CUDA-Engine selbst importiert den NVIDIA-Systemtreiber `nvcuda.dll` bereits beim CLI-Hilfeaufruf. Fehlt dieser Treiber auf dem Build-Rechner, steht im Prüfbericht ausdrücklich `engine_cli: not_run_no_nvidia_driver`. Das ersetzt keinen CUDA-Test. Auf dem RTX-PC prüft **NVIDIA prüfen** den installierten Treiber und die CUDA-Geräte; die echte Generierung benötigt weiterhin diesen Systemtreiber.

Für Entwickler: `python -m pip install -r requirements-build.txt`, `python -m unittest discover -s tests -v`, anschließend auf Windows `python build.py`. Diese Befehle sind nicht zur Bedienung der fertig gebauten App nötig.


## Fortschritt und geführter RTX-Test

Die Anzeige trennt Modellprüfung, Laden/Referenzvorbereitung, KI-Schritte, VAE-Decodierung, Bildprüfung und MP4-Export. Während der KI-Schritte stehen Szene, Schritt, Laufzeit und eine aus den Engine-Schrittzeiten abgeleitete Restzeit dort. Diese Restzeit gilt nur für die aktuelle Samplingphase, nicht für den gesamten Auftrag. Ohne messbare Schritte bleibt sie unbekannt.

VRAM-Belegung und GPU-Auslastung werden etwa alle zwei Sekunden über den NVIDIA-Treiber abgefragt. Die Werte betreffen die gesamte GPU einschließlich anderer Programme; der höchste Stichprobenwert ist kein exakter Prozesshöchstwert. Nicht verfügbare Messungen stoppen die Berechnung nicht.

Nach dem **2-Sekunden-Qualitätstest** öffnen sich Projektübersicht und Messbericht. Prüfe die Originalbilder bei **Originalgröße (100 %)** sowie die Bewegungen über **Video öffnen**. Halte über die Bewertungsbuttons und das Notizfeld fest, ob Motiv und Bewegung brauchbar sind. Der Bericht schreibt keine automatische Qualitätsfreigabe. `benchmark.json` enthält den aktuellen Versuch; zusätzliche `benchmark-….json` bewahren frühere Messversuche. `frame-report.json` pro Szene enthält technische Bildabweichungen, keinen Nachweis von Realismus.

Zum Vergleich den kurzen Test einmal mit dem Standardprofil und einmal mit eingeschaltetem VRAM-Vergleichsprofil ausführen. Derselbe Prompt/Seed und dieselben Qualitätsparameter bleiben erhalten. Erst die gemessenen Zeiten, Fehler und sichtbaren Ergebnisse auf dem echten PC entscheiden, welches Speicherprofil besser ist.

## Szenenplan und gemeinsamer Stil

**Gemeinsamer Stil** und **Motiv / Figur** werden in allen Szenen zusätzlich zum Hauptprompt verwendet. Unter **Abschnitte vorschlagen** entsteht eine bearbeitbare Zeitaufteilung in Intro, Verse, Chorus und Outro. Das ist keine automatische Erkennung der tatsächlichen Songstruktur. Für passende Schnitte die Startzeiten anhand des eigenen Songs bearbeiten.

Pro Zeile: `Startsekunde | Abschnitt | englischer Szenenprompt`, beispielsweise:

```
0 | Intro | A slow wide establishing shot in the neon-lit street.
12 | Verse | A medium tracking shot of the same person walking slowly.
28 | Chorus | A close-up, expressive motion, preserve the same lighting and colors.
```

Die erste Zeit muss 0 sein. Weitere Zeiten müssen aufsteigen und vor dem Videoende liegen. Ein Abschnitt wirkt ab dem nächsten KI-Szenenbeginn (alle 33/16 Sekunden). **Szenenplan prüfen** zeigt die zusammengesetzten Prompts an diesen Übergängen. Ein leeres Feld verwendet den gemeinsamen Hauptprompt ohne zusätzliche Abschnittsprompts. Aufträge sichern den Plan; spätere Änderungen im Formular verändern einen fortgesetzten Auftrag nicht.

## Projekte und Bildvergleich

**Projekte / Bildvergleich** listet bis zu 500 gespeicherte Aufträge, ihre Szenenzahl und die vorhandene MP4-Datei. Auswahl lädt Bild A. Über **Als Vergleich B wählen** einen zweiten Auftrag festhalten; danach einen anderen für A auswählen. Beide Seiten können unabhängig Szene und Originalbild wählen. **Referenz zeigen** zeigt die für diese Szene verwendete Motivvorlage. **Originalgröße (100 %)** zeigt die unveränderten Pixel mit Scrollleisten. Die verkleinerte Vorschau verändert die gespeicherten PNGs nicht.

**Ausgewählten Auftrag fortsetzen** prüft den gespeicherten Auftrag und seine Medien erneut. **Video öffnen** verwendet den Windows-Videoplayer. Eine vorhandene MP4-Datei allein beweist keine gute KI-Bildqualität. Beschädigte Projektmetadaten werden als **Auftragsdatei prüfen** angezeigt.
