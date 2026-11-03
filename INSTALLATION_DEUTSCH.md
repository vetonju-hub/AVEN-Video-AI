# AVEN Video AI v3 — Installation ohne Terminal (Intel & Apple Silicon)

## Wichtig vorab

Das ZIP ist **der Quellcode**, nicht die fertige `.app`. Da der Build nur auf macOS erfolgen kann, erzeugt GitHub Actions für dich eine echte `.dmg`-Installationsdatei. Die **erste KI-Generierung auf Intel i9 mit 16 GB RAM ist experimentell** und kann sehr viel Zeit benötigen oder an RAM scheitern.

## A. Bestehendes GitHub-Projekt aktualisieren

Du hast bereits das GitHub-Repository `vetonju-hub/AVEN-Video-AI`.

**Ohne Terminal mit GitHub Desktop:**

1. Öffne https://desktop.github.com/ und installiere GitHub Desktop.
2. Melde dich mit deinem GitHub-Konto an.
3. File → Clone repository → `AVEN-Video-AI` → Clone.
4. Entpacke `AVEN_Video_AI_v3_Adaptive_Realism_Projekt.zip` in Downloads.
5. Öffne in GitHub Desktop Repository → Show in Finder.
6. Kopiere den **Inhalt** des entpackten v3-Ordners (`Sources`, `scripts`, `Assets`, `.github`, `Info.plist`, `README.md` usw.) in den soeben geöffneten geklonten Repository-Ordner; vorhandene Projektdateien ersetzen/Ordner zusammenführen.
7. **Nicht** den Git-Versionsordner `.git` verändern. Der versteckte Ordner `.github` muss mitkommen; Finder zeigt ihn mit `⌘⇧.` an.
8. In GitHub Desktop alle Änderungen kontrollieren; links unten als Summary `AVEN v3 Adaptive Realism` eingeben → **Commit to main** → **Push origin**.
9. Öffne https://github.com/vetonju-hub/AVEN-Video-AI/actions.

**Alternative per Browser:** Lade einzelne Projektdateien in der richtigen Unterordner-Struktur hoch und ersetze gleichnamige Dateien. Bei `.github/workflows/build-macos.yml` muss der Dateipfad genauso bleiben.

## B. Installationsdatei herunterladen

1. In GitHub → **Actions** den neuesten Eintrag `AVEN v3 - Adaptive Realism Intel und Apple Silicon` öffnen.
2. Der Build wird für zwei Architekturen gestartet. Prüfe, ob der jeweilige Job einen **grünen Haken** hat.
3. Für das MacBook Pro 2019 (Intel) unten unter **Artifacts** auf `AVEN-v3-x86_64-Mac-Installer` klicken.
4. Das heruntergeladene ZIP entpacken. `AVEN_Video_AI_v3_x86_64.dmg` doppelklicken.
5. `AVEN Video AI.app` per Maus in den Ordner **Programme** ziehen.
6. `AVEN Video AI.app` in **Programme** öffnen. Wenn macOS die unsignierte App blockiert: Systemeinstellungen → Datenschutz & Sicherheit → dennoch öffnen, **nur wenn du deinem selbstgebauten App-Artefakt vertraust**. Nicht die allgemeine Sicherheit deaktivieren.

Für neuere Apple-Silicon-Macs nimm entsprechend `AVEN-v3-arm64-Mac-Installer`.

**Wenn der Job rot ist:** Nicht installieren. Öffne den roten Job, kopiere die erste Fehlermeldung aus dem Build-Protokoll und sende sie zur Fehlerbehebung. Ein grüner CI-Build ersetzt keinen echten KI-Render-Test.

## C. Erstes echtes KI-Video erstellen

1. Starte AVEN. Im KI-Bereich steht deine erkannte Hardware.
2. Gib einen englischen Prompt ein, z. B.: `A singer wearing a black jacket slowly turns toward camera, subtle natural head motion, cinematic moonlight, realistic face.`
3. Optional **Bilder hinzufügen** und **Erstes Bild als Referenz verwenden** aktivieren.
4. **Realismusstufe 2–3** und eine sehr kurze Gesamtdauer (2–4 Sekunden) für den ersten Test verwenden.
5. Klicke **Kostenlose KI-Modelle herunterladen**. Rund 4,5 GB Daten müssen einmalig geladen werden. Danach ist die Berechnung offline. Die KI-Engine liegt bereits in der App.
6. Klicke **ECHTES KI-VIDEO GENERIEREN**. AVEN erstellt `~/Movies/AVEN Video AI/KI Aufträge/Job-...` und speichert jede erzeugte Szene separat.
7. Wenn der erste Test klappt, erhöhe den Regler auf 5, dann 8, dann 10. Es gibt keine Qualitätsgarantie. Bei Speichermangel niedrigere Stufe verwenden.
8. Für mehrminütige Videos Dauer auf bis zu 240 Sekunden setzen; AVEN generiert viele Clips nacheinander und fügt sie zusammen.
9. Bei Unterbrechung **Letzten Auftrag fortsetzen** drücken. Erstellte Szenen werden nicht neu berechnet.

**Nicht verwechseln:** `MP4-Video erstellen` ist der bisherige Bild-Animator. Der Button **ECHTES KI-VIDEO GENERIEREN** startet das neuronale Videomodell.

## Hardwaregrenzen

Auf einem Intel i9 mit 16 GB RAM findet die KI-Berechnung ausschließlich auf der CPU statt. Das kann extrem langsam sein und manche Einstellungen können durch RAM-Limits scheitern. Mehr Zeit allein kann fehlenden Arbeitsspeicher nicht ersetzen. Die Stufe 10 bedeutet „höchster unterstützter Rechenaufwand“, nicht Nano-Banana-/Veo-Qualität.
