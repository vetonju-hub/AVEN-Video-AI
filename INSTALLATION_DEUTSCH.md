# AVEN Video AI 3.4 installieren

Dieses Update setzt dein vorhandenes Projekt fort. Das Paket enthält **Quellcode, Tests und Builddateien**, keinen bereits auf macOS überprüften Installer. Der aktuelle GitHub-Zugriff hat Schreibversuche mit HTTP 403 abgelehnt. Deshalb müssen die Dateien einmal über GitHub Desktop hochgeladen werden, bevor GitHub den neuen Installer bauen kann.

## 1. Projektdateien ersetzen – ohne Terminalbefehle

1. ZIP entpacken. Darin den Ordner `AVEN-Video-AI` öffnen.
2. In **GitHub Desktop** dein Repository `AVEN-Video-AI` auswählen. Über **Repository → Show in Finder** den vorhandenen Projektordner öffnen. Auf deinem Mac war das `~/Documents/GitHub/AVEN-Video-AI`.
3. Falls dort noch eigene, nicht hochgeladene Änderungen liegen, zuerst eine Kopie des alten Projektordners aufheben. Anschließend die Ordner **Sources**, **scripts**, **tests**, **docs** und **Assets** sowie die Dateien **Info.plist**, **README.md**, **MODELLQUELLEN.md**, **INSTALLATION_DEUTSCH.md**, **START_HIER.txt**, **PRUEFBERICHT.md**, **build-macos.yml** und **tests_smoke.py** aus dem Update in dein Projekt kopieren. Vorhandene Versionen dieser Dateien/Ordner ersetzen.
4. Den Workflow gesondert aktualisieren: Im Finder **⌘ + ⇧ + G** drücken und `~/Documents/GitHub/AVEN-Video-AI/.github/workflows` eingeben. In diesen geöffneten Ordner die **sichtbare Datei `build-macos.yml`** aus dem Update kopieren und die vorhandene gleichnamige Datei ersetzen. Dafür müssen versteckte Dateien nicht eingeblendet werden.
5. Zurück in GitHub Desktop. Als Zusammenfassung beispielsweise **AVEN 3.4 – KI-Qualität und Musiklänge** eintragen. **Commit to main** und anschließend **Push origin** anklicken. Es werden keine Modellgewichte hochgeladen.

Der Workflow unter `.github/workflows/` ist entscheidend. Die sichtbare Datei im Projektstamm allein startet keinen Build. Beide Kopien im Update sind identisch.

## 2. Den richtigen Installer herunterladen

1. [GitHub Actions öffnen](https://github.com/vetonju-hub/AVEN-Video-AI/actions).
2. Den neuen Lauf **AVEN v3.4 – Adaptive Realism Intel und Apple Silicon** öffnen. Bei einem normalen Push startet er automatisch; alternativ **Run workflow** verwenden.
3. Beide Jobs müssen grün sein. Die Logik- und Medientests laufen vor dem App-Build. Bei Rot gibt es noch keinen geprüften neuen Installer; im fehlgeschlagenen Schritt den Fehlertext ansehen.
4. Unten bei **Artifacts** auswählen:

| Dein Mac | Artifact | Enthaltene DMG |
|---|---|---|
| MacBook Pro Intel i9 | AVEN-v3.4-x86_64-Mac-Installer | AVEN_Video_AI_v3.4_x86_64.dmg |
| Mac mit Apple-Chip | AVEN-v3.4-arm64-Mac-Installer | AVEN_Video_AI_v3.4_arm64.dmg |

5. Artifact-ZIP entpacken, DMG öffnen und **AVEN Video AI.app** in **Programme** ziehen. Eine laufende alte App vorher beenden. Vorhandene App ersetzen.
6. Die App ist lokal/ad-hoc signiert und nicht Apple-notarisiert. Falls macOS sie blockiert, nur für diesen selbst gebauten Download den Weg über **Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen** verwenden. Keine globalen Sicherheitseinstellungen abschalten.

Ein grüner Build belegt Kompilierung, Paketprüfungen und synthetische Medientests. Er belegt noch keine brauchbare KI-Generierung auf deinem Mac.

## 3. Zuerst den kurzen Qualitätstest ausführen

1. Neue App öffnen. Vorhandene gültige V3-Modelle werden weiterverwendet. Nur falls sie fehlen, **Kostenlose KI-Modelle herunterladen** anklicken.
2. **2-Sekunden-Qualitätstest** anklicken. Dieser verwendet automatisch einen englischen Katzen-Prompt, Seed 42, 832×480, 20 Schritte, 33 Originalframes und 16 FPS. Foto, Musik und aktuelle Prompt-Eingabe beeinflussen diesen Test nicht.
3. Warten, bis **Vorschau erstellt** erscheint. Die Berechnung ist echte lokale KI und kann auf Intel sehr lange dauern. 20 Schritte bei 480p benötigen erheblich mehr Zeit als der alte unbrauchbare Minimalmodus.
4. **KI-Vorschau anzeigen** öffnet den Finder. `AVEN_KI_VORSCHAU.mp4` abspielen. Zusätzlich **Szenenordner anzeigen → scene_001** öffnen und einige `generated_000.png` usw. ansehen. Die Bilder müssen bereits als Originalframes erkennbare Motive enthalten. Größerer Export oder Nachschärfen repariert keine fehlerhafte Diffusion.
5. Bei einem Fehler sind `engine.log`, `command.json`, `frame-report.json` (falls Frames vollständig lesbar waren) und ein Original-PNG die wichtigen Diagnose-Dateien. Ein neues `engine.log` ist aussagekräftiger als das alte Protokoll des fehlenden VACE-Tensors.

Fast einfarbige, unvollständige, beschädigte oder falsch dimensionierte Ausgabe wird nicht als fertiges Video übernommen. Andere schlechte Bilder können diese technischen Prüfungen bestehen: Motiverkennung, Rauschen und sichtbare Qualität müssen weiter visuell geprüft werden.

## 4. Eigene Musik und Referenzen

- Im großen Promptfeld Motiv, Bewegung, Licht und Kamera beschreiben. Für Wan empfiehlt sich Englisch. Unter den erweiterten Einstellungen kannst du negativen Prompt und Seed ändern.
- **Bilder hinzufügen** importiert Foto-Referenzen mit korrekter EXIF-Ausrichtung.
- **Video als Referenz** übernimmt pro ausgewähltem Clip ein Bild zur eingestellten Referenzzeit. Der Zeitwert gilt beim Import. Das Originalvideo wird nicht in seiner ganzen Bewegung umgestaltet. Fotos/Videobilder werden reihum je Szene als Motivvorlage verwendet.
- **Musik hinzufügen** und **Videolänge automatisch an die gesamte Musik anpassen** aktivieren. Die KI plant dann die volle gemessene Audiospurdauer; die frühere 240-Sekunden-Grenze ist entfernt. Bei manuell gewählter längerer Videodauer wird die Musik nicht wiederholt; der Rest bleibt stumm.
- Aufträge sichern Referenzen und Musik im Auftragsordner. Diese Kopien ermöglichen späteres Fortsetzen auch nach Verschieben der ursprünglichen Dateien.
- **Bilder / Titel animiert exportieren** ist der konventionelle Export. **ECHTES KI-VIDEO GENERIEREN** startet die neue Modellberechnung.

## 5. Realismus und Hardware

Beginne auf deinem Intel-i9-Mac mit Stufe 1 und dem kurzen Test. Die Stufen erhöhen Schritte und später Auflösung/Präzision. Es gibt keine automatische Herabstufung der angeforderten Qualität wegen wenig RAM. Stufe 8–10 verlangt Q8 und UMT5 Q5 und kann auf 16 GB scheitern. Die App nennt fehlende Gewichte ausdrücklich.

Unter 8 GB wird dieses Wan-Modell nicht gestartet. Auch mit 8–16 GB ist kein erfolgreicher Lauf garantiert. Starke Hardware kann schneller rechnen und größere Profile bewältigen; Fotorealismus und identische Bilder auf unterschiedlichen Backends sind nicht garantiert. Eine Windows-App ist in diesem Update nicht enthalten.

Alte Aufträge mit den v3.3-Minimalprofilen bitte **neu starten**. Die Dateien werden behalten, aber ihre problematischen Parameter werden nicht erneut verwendet.
