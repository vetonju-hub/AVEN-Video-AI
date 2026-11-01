# AVEN Video AI — Neuentwicklung für Intel Mac

Neue native macOS-App in SwiftUI/AppKit/AVFoundation. Kein Python, pip, PyTorch oder Terminal für die normale Nutzung.

**Installation ohne Terminal:** [INSTALLATION_DEUTSCH.md](INSTALLATION_DEUTSCH.md)

Projektaufbau:

- `Sources/AVENApp.swift`: Design, Szenenliste, Bildimport, Vision-Klassifizierung, Export-UI
- `Sources/VideoRenderer.swift`: H.264-Video mit Kamerabewegungen, Übergängen, Titel und Musik
- `Assets/AVEN.iconset/`: eigenes App-Symbol
- `Info.plist`: macOS-App-Metadaten
- `scripts/build_macos.sh`: Swift-Compiler und DMG-Paketierung auf einem Mac-Build-System
- `.github/workflows/build-macos.yml`: automatischer Intel-Runner und Installer-Download

### Reproduzierbarer Build

GitHub Actions nutzt `macos-26-intel` und Apples `swiftc`, um `AVEN Video AI.app` und `AVEN_Video_AI_Intel.dmg` zu erstellen. Die App ist ad-hoc-signiert und nicht notarisiert.

### Funktionsumfang

- Videos aus Bildern / animierten Hintergründen (keine generativen Szenen)
- 5–240 Sekunden, 12 fps, H.264 MP4
- 16:9 / 9:16 / 1:1
- optional Musikunterlegung
- lokale Vision-Bildklassifikation
- vollständig offline in der Verwendung

### Einschränkungen

Ein lauffähiger macOS-Build wurde in dieser Linux-Umgebung **nicht** verifiziert. Die echte Prüfung erfolgt durch GitHub Actions. Ohne GitHub-Build oder macOS-Compiler kann kein ehrliches fertiges `.dmg` in diesem ZIP liegen. Generative Text-zu-Video-KI ist nicht enthalten.
