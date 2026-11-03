# AVEN Video AI 3.4

Native macOS-App mit SwiftUI, AVFoundation und lokalem Wan2.1 VACE 1.3B über stable-diffusion.cpp. Intel und Apple Silicon ab macOS 14.

## Änderungen gegenüber v3.3

- Mindestens 480p, 20 Sampling-Schritte und 33 Modellframes bei 16 FPS. Die früheren 352×192-/6-Schritt-/6-FPS-Profile sind entfernt.
- VACE-spezifisch: CFG 5, Flow-Shift 16, Euler/discrete. Engine-Revision und Modellquellen sind festgeschrieben.
- Qualitätsstufe bestimmt Schritte, Auflösung und Gewichte; Hardware bestimmt CPU-/Metal-Ausführung und Threads. Automatische Gewichtsänderung ist deaktiviert. Gleiches Profil ist keine Garantie für bitidentische Ergebnisse auf verschiedenen Backends.
- SHA256 für alle fünf Gewichte; Prüfung vor Generierung. Q8/Q5 wird nicht still durch Q4/Q3 ersetzt.
- Vollständige, nummerierte, lesbare PNGs in exakter Zielgröße erforderlich. Fast einfarbige Ausgabe wird abgelehnt. Bildstatistiken zertifizieren keine erkennbare Szene oder fotorealistische Qualität.
- Originalframes, Aufrufparameter und Diagnosebericht bleiben erhalten. MP4-Ausgabe heißt bewusst **AVEN_KI_VORSCHAU.mp4** und muss visuell beurteilt werden.
- Abbruch und Fortsetzen mit gespeicherten Szenen; alte fehlerhafte Aufträge müssen neu gestartet werden. Unterbrochene Szenen werden vor einem neuen Versuch archiviert.
- Mehrzeiliger Prompt, negativer Prompt, Seed und ein reproduzierbarer 2-Sekunden-Test.
- Fotos berücksichtigen EXIF-Ausrichtung. Videoimport extrahiert **ein Referenzbild** zur gewählten Zeit pro Clip. Das ist keine Übertragung der Originalbewegung und kein vollständiger Video-zu-Video-Modus. Wan VACE verwendet Referenzen als Motivvorlage, nicht als garantiert unveränderten Startframe. Mehrere Motive werden abwechselnd je KI-Szene genutzt.
- Musikmodus übernimmt die komplette gemessene Audiospurdauer einschließlich Nachkommastellen. Kein stilles Abschneiden bei 240 Sekunden; höchstens 24 Stunden als Eingabegrenze. Musik läuft einmal mit Originaltempo. Bei manuell längeren Videos bleibt der Rest stumm.

## Hardware und Qualität

Stufe 1–7: 832×480 (hochkant 480×832, quadratisch 640×640), Q4 + UMT5 Q3, 20–36 Schritte. Stufe 8–10: 1024×576 (bzw. Hochkant/768²), Q8 + UMT5 Q5, 40–50 Schritte. Jede Sequenz hat 33 Frames. Intel läuft auf CPU; Apple Silicon nutzt Metal für Diffusion und CPU für Textencoder/VAE.

Ab 8 GB kann ein Versuch gestartet werden, ohne Speicher- oder Erfolgsgarantie. Unter 8 GB ist dieses Modell blockiert. Ein Intel-i9-Mac mit 16 GB kann sehr langsam sein; höhere Stufen können an Speichergrenzen scheitern. Mehr RAM allein macht keine besseren Bilder. Ein anderer Backend kann numerisch andere Ergebnisse erzeugen. Kein Veo-Qualitätsversprechen.

## Start und Installation

Siehe [INSTALLATION_DEUTSCH.md](INSTALLATION_DEUTSCH.md). Der Build erzeugt `AVEN_Video_AI_v3.4_x86_64.dmg` und `AVEN_Video_AI_v3.4_arm64.dmg` in zwei GitHub-Actions-Jobs. Die sichtbare `build-macos.yml` ist eine identische Kopie für das manuelle Einsetzen in `.github/workflows/`.

## Prüfungen

```sh
bash tests/test_logic.sh        # echte Swift-Logiktests; auch auf Linux mit Swift
python3 tests/smoke_static.py   # Paketdaten, Shellsyntax und Swift-Syntax
bash tests/test_on_mac.sh      # echte PNG/MP4/Musik-Integration; nur macOS
bash scripts/build_macos.sh    # vollständige App/Engine, Architektur, Signatur und DMG
```

Native Medientests verwenden synthetische Frames/Audio und eine kleine VBR-MP3-Testdatei ohne Xing-Header. Sie testen keine neurale Bildqualität. Ein erfolgreicher CI-Build beweist keine erfolgreiche Wan-Generierung. Ein realer Linux-CPU-Test erzeugte mit den kompakten Gewichten ein erkennbares 480p-Einzelbild; Original und Log liegen unter `docs/validation/linux-single-frame/`. Das ersetzt keinen Videotest. Aktueller Prüfstatus und Grenzen stehen in [PRUEFBERICHT.md](PRUEFBERICHT.md).

## Grenzen

Die Szenen sind eigenständige Modellberechnungen; zwischen ihnen sind Schnitte und Motivänderungen möglich. Keine nahtlose minutenlange Kontinuität, kein garantierter Fotorealismus und kein garantierter Lauf auf jedem Mac. Der aktuelle Quellcode ist eine macOS-App; Windows ist noch nicht implementiert.
