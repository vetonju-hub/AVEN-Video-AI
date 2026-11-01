# AVEN Video AI — Schritt für Schritt installieren

**Für deinen Mac:** MacBook Pro 16 Zoll (2019), Intel i9, 16 GB RAM, macOS Tahoe 26.5.

## Das Wichtigste zuerst

- Das Projekt ist **komplett neu in Swift/SwiftUI** geschrieben, nicht in Python.
- Die ZIP-Datei, die du von ChatGPT erhältst, ist ein **Quellcode-Paket**. Sie ist **noch keine bereits kompilierte Mac-App**.
- Damit du später AVEN wie Firefox installieren kannst, baut ein kostenloser **GitHub-Actions-Intel-Mac** daraus eine `.dmg`-Installationsdatei.
- **Du musst dafür auf deinem Mac keinen Terminalbefehl eingeben.**
- Du brauchst für diesen einmaligen Online-Build einen GitHub-Account und Internet. Nach dem Download funktioniert die App selbst **offline**.
- Die `.dmg` ist **nicht von Apple notarisiert**. Daher kann eine einmalige Sicherheitsfreigabe erforderlich sein.

## A. App-Datei ohne Terminal erstellen

### 1. ZIP entpacken

1. `AVEN_Video_AI_Neustart.zip` herunterladen.
2. Im Ordner **Downloads** die ZIP-Datei doppelklicken.
3. Im entpackten Ordner findest du z. B. `Sources`, `Assets`, `scripts`, `Info.plist` und diese Anleitung.
4. Drücke im Finder **⌘ + ⇧ + .** (Command + Shift + Punkt), damit auch der versteckte Ordner **`.github`** sichtbar ist.

### 2. Kostenloses GitHub-Repository erstellen

1. Öffne **https://github.com/new** in Safari.
2. Melde dich an oder registriere einen kostenlosen GitHub-Account.
3. Als Repository-Namen `AVEN-Video-AI` eingeben.
4. Wähle **Public** nur, wenn dein Code öffentlich sein darf. Für öffentliche Repositories ist die Standard-Build-Nutzung von GitHub Actions kostenlos. Private Repositories können innerhalb des inkludierten Minutenkontingents funktionieren; zusätzliche Kosten sind möglich.
5. **NICHT** „Add a README file“ aktivieren.
6. Klicke auf **Create repository**.

### 3. Projekt hochladen

1. Auf der neuen Repository-Seite findest du den Link **uploading an existing file**. Alternativ: **Add file → Upload files**.
2. Ziehe den Inhalt des entpackten Ordners in die Uploadfläche. Es müssen **alle Projektdateien und Unterordner** dabei sein, insbesondere `.github/workflows/build-macos.yml`, `Sources/`, `scripts/`, `Assets/` und `Info.plist`.
3. Kontrolliere in der Vorschau die Dateipfade. Falls `.github/workflows/build-macos.yml` fehlt, füge die Datei noch hinzu. Der automatische Build startet sonst nicht.
4. Klicke unten auf **Commit changes**.

### 4. Mac-Installationsdatei bauen lassen

1. Öffne in deinem Repository oben den Tab **Actions**.
2. Falls GitHub nach einer Freigabe für Workflows fragt, aktiviere die Workflows für dieses Repository.
3. Wähle **AVEN Video AI - Intel Mac Installationsdatei**.
4. Normalerweise läuft der Build nach dem Hochladen automatisch. Alternativ kannst du **Run workflow → Run workflow** wählen.
5. Öffne den neuesten Durchlauf und prüfe, ob der Build mit einem **grünen Haken** abgeschlossen ist.
6. Ganz unten im Durchlauf findest du unter **Artifacts** den Download **AVEN-Video-AI-Intel-Installer**.
7. Lade ihn herunter. Du erhältst eine ZIP-Datei. Entpacke diese. Darin befindet sich `AVEN_Video_AI_Intel.dmg`.

**Hinweis:** Wenn der Build rot fehlschlägt, existiert keine funktionierende `.dmg`. Öffne die Fehlerdetails und verwende die darin angezeigte Fehlermeldung zur Korrektur. Der Quellcode wurde außerhalb eines Macs entwickelt und ist noch nicht auf deinem Gerät getestet.

## B. AVEN normal auf dem Mac installieren

1. Doppelklicke auf `AVEN_Video_AI_Intel.dmg`.
2. Ein Fenster mit `AVEN Video AI.app` und einer Verknüpfung zum Ordner **Programme** öffnet sich.
3. Ziehe `AVEN Video AI.app` auf **Programme**.
4. Öffne **Finder → Programme**.
5. Doppelklicke auf **AVEN Video AI**.

### Falls Apple den Start blockiert

Diese Version ist nicht mit einer kostenpflichtigen Apple-Developer-ID signiert und nicht von Apple notarisiert.

1. Starte AVEN einmal (Sicherheitsmeldung erscheint).
2. Öffne **Apple-Menü → Systemeinstellungen → Datenschutz & Sicherheit**.
3. Scrolle bis zum Hinweis über die blockierte App.
4. Wähle **Dennoch öffnen** und bestätige deine Entscheidung.
5. Starte AVEN nochmals.

**Deaktiviere Gatekeeper nicht global**. Diese Freigabe nur bei Dateien verwenden, deren Herkunft und Inhalt du geprüft hast.

## C. Dein erstes Video erstellen

1. Starte **AVEN Video AI** über den Ordner **Programme**.
2. Schreibe einen **Projekttitel** und optional eine Stimmung. Die Beschreibung wählt bei Titelvideos die Hintergrundfarbe, erzeugt aber **keine generativen KI-Szenen**.
3. Klicke auf **Bilder hinzufügen** und wähle mehrere Fotos.
4. Wähle **16:9** für YouTube, **9:16** für Shorts/Reels oder **1:1** für quadratische Videos.
5. Stelle die Länge über den Regler auf **5 bis 240 Sekunden**.
6. Optional auf **Musik hinzufügen** klicken und eine Audiodatei auswählen.
7. Optional **KI-Motiverkennung** klicken. Apples Vision analysiert das erste Bild lokal.
8. **MP4-Video erstellen** anklicken, Zielort auswählen und auf Fertigstellung warten.
9. **Im Finder anzeigen** öffnet die fertige MP4-Datei.

Die Szene jedes Fotos wird mit einem leichten Zoom und Kameraschwenk animiert. Benachbarte Bilder erhalten Überblendungen. Wenn du keine Bilder auswählst, entsteht ein animierter Farb-/Titelclip.

## D. Technische Eigenschaften

| Eigenschaft | Wert |
| --- | --- |
| Zielplattform | Intel-Mac, x86_64 |
| macOS | 14+ (unter Tahoe 26.5 vorgesehen) |
| Laufzeit | native SwiftUI / Apple AVFoundation |
| Python / pip / PyTorch | **nicht erforderlich** |
| Ausgabe | `.mp4` mit H.264 |
| Videoformat | 16:9, 9:16, 1:1 |
| Standardauflösung | 960×540 / 540×960 / 720×720 |
| Bildrate | 12 fps |
| Maximale Länge | 240 Sekunden |
| Musik | optional MP3 / M4A / WAV / AIFF, wird bei Bedarf geloopt |
| Lokale KI-Funktion | Apples Vision-Motiverkennung (ML-Klassifizierung) |
| Internet während Nutzung | nein |

## E. Ehrliche Grenzen

- **Keine echte generative Text-zu-Video-KI:** Diese erste native Version rendert Bildanimationen, Titelkarten und Musikvideos. Sie generiert nicht neue realistische Personen, Aktionen oder Szenen aus einem Textprompt.
- Die Bezeichnung Video AI bezieht sich in dieser Version auf die eingebaute lokale Vision-Bildanalyse. Ein generatives Videomodell ist nicht enthalten.
- Auf dem Intel-i9-Mac mit 16 GB RAM wäre die vierminütige Videoerzeugung mit großen aktuellen Videodiffusionsmodellen sehr langsam und oft nicht innerhalb des RAM-Limits möglich.
- Die Projektdateien sind auf Swift-Syntax geprüft; ein echter macOS-Build und ein Start auf deinem Computer können hier nicht vorgetäuscht werden. GitHub Actions macht einen echten Build und zeigt mögliche Compilerfehler.

## F. Hilfe bei Fehlermeldungen

**Actions zeigt keinen Workflow:** Prüfe, ob im GitHub-Repository die Datei `.github/workflows/build-macos.yml` vorhanden ist und ob Workflows aktiviert sind.

**Build ist rot:** Öffne Actions → Build-Lauf → `DMG für Intel-Mac erstellen` → `Programme bauen und DMG erstellen`. Kopiere die erste Fehlermeldung für die Fehlerbehebung.

**macOS blockiert die App:** Verwende die Freigabe unter Datenschutz & Sicherheit wie oben erklärt, nicht `sudo` oder globale Sicherheitsabschaltungen.

**Video startet, aber ohne Musik:** Prüfe, ob deine Audiodatei abspielbar ist. Die App verwendet AVFoundation, das manche exotischen Formate nicht unterstützt.

**Videoexport dauert lange:** Reduziere die Länge und verwende zunächst 2–3 Bilder. Für 4 Minuten verarbeitet dein Mac 2880 Frames bei 12 fps.
