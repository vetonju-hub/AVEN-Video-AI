"""Offline German/English UI text. Workers carry templates, never a global locale."""
import json
import os
from pathlib import Path
import uuid


ENGLISH = {
    'Deutsch':'Deutsch', 'English':'English', 'AVEN  /  VIDEO AI':'AVEN  /  VIDEO AI',
    'Windows · NVIDIA CUDA · lokale Verarbeitung':'Windows · NVIDIA CUDA · local processing',
    'RTX-Profil: Diffusion über CUDA0 · Textencoder und VAE über CPU/RAM':'RTX profile: diffusion on CUDA0 · text encoder and VAE on CPU/RAM',
    'Szenenbeschreibung':'Scene description',
    'Motiv, Bewegung, Licht und Kamera beschreiben. Englische Prompts funktionieren mit Wan meist besser.':'Describe the subject, motion, lighting and camera. English prompts usually work better with Wan.',
    'Negativer Prompt':'Negative prompt', 'Seed':'Seed', 'Format':'Format',
    'Eigene Länge (Sekunden)':'Custom duration (seconds)',
    'Zusätzliche Länge (Sekunden)':'Additional duration (seconds)',
    'Video fortsetzen':'Extend video', 'Clip auswählen':'Select clip', 'Clip entfernen':'Remove clip',
    'Kein Clip zur Fortsetzung ausgewählt':'No clip selected to extend',
    'Clip zur Fortsetzung: {name}':'Clip to extend: {name}',
    'Beschreibe oben, was nach dem Clip passieren soll. Die letzten Bilder dienen als Ausgangspunkt. Musik und Länge gelten für den neuen Teil.':'Describe what happens next in the prompt above. The final frames guide the extension. Music and duration apply to the new footage.',
    'Fester Avatar':'Recurring avatar', 'Avatarbild auswählen':'Select avatar image', 'Avatar entfernen':'Remove avatar',
    'Kein Avatar gespeichert':'No saved avatar', 'Avatar gespeichert.':'Avatar saved.',
    'Gespeicherten Avatar für alle Szenen verwenden':'Use the saved avatar in every scene',
    'Der Avatar bleibt lokal gespeichert. Ist er aktiv, hat er bei jeder KI-Szene Vorrang vor anderen Motivbildern. Sein Aussehen kann zwischen Szenen variieren.':'The avatar is stored locally. When enabled, it takes priority over other reference images in every AI scene. Appearance can vary between scenes.',
    'Gespeichertes Avatarbild ist nicht lesbar. Bitte erneut auswählen.':'The saved avatar image cannot be read. Select it again.',
    'Avatarbild konnte nicht gespeichert werden: {detail}':'Could not save the avatar image: {detail}',
    'Avatar konnte nicht entfernt werden: {detail}':'Could not remove the avatar: {detail}',
    'Clip und Referenzen werden vorbereitet …':'Preparing the clip and references …',
    'Videolänge automatisch an die gesamte Musik anpassen':'Match video duration to the entire music track',
    'Fortsetzung automatisch an die gesamte Musik anpassen':'Match the extension to the entire music track',
    'Keine Musik ausgewählt':'No music selected', 'Musik hinzufügen':'Add music', 'Musik entfernen':'Remove music',
    'Foto- und Videoreferenzen':'Photo and video references', 'Fotos hinzufügen':'Add photos',
    'Video als Referenz':'Video reference', 'Auswahl entfernen':'Remove selection', '  Videozeit (s)':'  Video time (s)',
    'Pro Video wird ein Einzelbild zur gewählten Zeit übernommen. Die KI verwendet Referenzen reihum je Szene.':'One still is extracted from each video at the selected time. References alternate between AI scenes.',
    'Realismus / Rechenaufwand':'Realism / processing effort',
    'Auf der RTX 3080 zuerst Stufe 1 testen. Höhere Profile können die 10 GB Grafikspeicher überschreiten. Einzelne Szenen können sichtbare Schnitte haben.':'Test level 1 first on the RTX 3080. Higher profiles may exceed its 10 GB of VRAM. Separate scenes may have visible cuts.',
    'Modelle herunterladen':'Download models', 'Modelle importieren':'Import models', 'NVIDIA prüfen':'Check NVIDIA',
    'Modelle werden in deinem Windows-Benutzerordner gespeichert. Jeder Auftrag prüft die vollständigen SHA256-Prüfsummen.':'Models are stored in your Windows user folder. Every job verifies their full SHA256 checksums.',
    '2-Sekunden-Qualitätstest':'2-second quality test', 'KI-Video generieren':'Generate AI video', 'Anhalten':'Stop',
    'Auftrag fortsetzen':'Resume job', 'Szenenordner / Protokolle':'Scene folder / logs', 'KI-Vorschau öffnen':'Open AI preview',
    'Bereit. Zuerst Modelle laden oder importieren, dann den kurzen Qualitätstest starten.':'Ready. Download or import models, then start the short quality test.',
    'Stufe {level}/10 · {width}×{height} · {steps} Schritte · 33 Originalbilder · 16 FPS · {tier} · CUDA0 + CPU':'Level {level}/10 · {width}×{height} · {steps} steps · 33 original frames · 16 FPS · {tier} · CUDA0 + CPU',
    'Musik: {name} · {seconds:.3f} Sekunden':'Music: {name} · {seconds:.3f} seconds',
    '{name} · Video bei {seconds:g} s':'{name} · video at {seconds:g} s',
    'Angehalten. Fertige Szenen sind gespeichert.':'Stopped. Completed scenes have been saved.',
    'KI-Vorschau erstellt. Originalbilder und Motivqualität bitte prüfen.':'AI preview created. Please check the original frames and visual quality.',
    'Anhalten angefordert …':'Stop requested …',
    'Laufenden Vorgang anhalten und danach die App schließen?':'Stop the current operation and then close the app?',
    'Musik auswählen':'Select music', 'Musik':'Music', 'Alle Dateien':'All files',
    'Musikdauer wird vollständig geprüft …':'Measuring the complete audio duration …', 'Musik importiert.':'Music imported.',
    'Bitte eine gültige Referenzzeit eingeben.':'Please enter a valid reference time.',
    'Referenzen auswählen':'Select references', 'Videos':'Videos', 'Fotos':'Photos',
    'Ordner mit vorhandenen AVEN-Modellen':'Folder containing existing AVEN models',
    'Modelle vollständig geprüft. Jetzt den 2-Sekunden-Qualitätstest starten.':'Models fully verified. Start the 2-second quality test now.',
    '{name} · {memory} MB Grafikspeicher · NVIDIA-Treiber {driver}':'{name} · {memory} MB VRAM · NVIDIA driver {driver}',
    'Referenzen und Musik werden im Auftrag gesichert …':'Saving reference and music copies in the job folder …',
    'Eingabe prüfen':'Check input', 'Gespeicherten Auftrag wählen':'Select a saved job', 'AVEN-Auftrag':'AVEN job',
    'Noch keine entsprechende Ausgabe vorhanden.':'No corresponding output is available yet.',
    'Sprache konnte nicht gespeichert werden: {detail}':'Could not save the language preference: {detail}',
    'Ein Fehler ist aufgetreten: {detail}':'An error occurred: {detail}',
    'Bitte gültige Zahlen für Länge und Seed eingeben.':'Please enter valid numbers for duration and seed.',
    'Eine gültige Länge zwischen 0 und 24 Stunden ist erforderlich. Musik zuerst importieren.':'A valid duration between 0 and 24 hours is required. Import music first.',
    'Realismusstufe muss zwischen 1 und 10 liegen.':'The realism level must be between 1 and 10.',
    'Unbekanntes Videoformat.':'Unknown video format.',
    'Veraltetes oder ungültiges Qualitätsprofil. Neuen Auftrag starten.':'Outdated or invalid quality profile. Start a new job.',
    'Bitte eine Szenenbeschreibung eingeben.':'Please enter a scene description.',
    'Seed muss zwischen 0 und 2147483647 liegen.':'The seed must be between 0 and 2147483647.',
    'Unvollständige Bildfolge: {actual} statt {expected} fortlaufender PNGs.':'Incomplete frame sequence: {actual} instead of {expected} consecutive PNGs.',
    'Auftrag angehalten. Fertige Szenen bleiben erhalten.':'Job stopped. Completed scenes are preserved.',
    'Ungültiger Auftragspfad.':'Invalid job path.', 'Auftragspfad liegt außerhalb des Auftrags.':'A job path points outside the job folder.',
    'Prozess-Zeitlimit überschritten.':'Process timed out.',
    '{name}: Fehlercode {code}. {detail}':'{name}: Error code {code}. {detail}',
    'Bitte engine.log im Szenenordner prüfen.':'Please check engine.log in the scene folder.',
    '{name} fehlt im App-Paket. Bitte das vollständige Windows-Paket entpacken.':'{name} is missing from the app bundle. Extract the complete Windows package.',
    'NVIDIA-Treiber nicht gefunden. NVIDIA-Treiber installieren und die App neu starten.':'NVIDIA driver not found. Install the NVIDIA driver and restart the app.',
    'Keine NVIDIA-Grafikkarte gefunden.':'No NVIDIA graphics card found.',
    'Dieses CUDA-Profil benötigt mindestens 6 GB Grafikspeicher. Kein automatischer Qualitätsverlust.':'This CUDA profile requires at least 6 GB of VRAM. Quality will not be reduced automatically.',
    'Die gebündelte KI-Engine findet CUDA0 nicht. NVIDIA-Treiber und engine.log prüfen. CPU-Ersatz wurde nicht gestartet.':'The bundled AI engine cannot find CUDA0. Check the NVIDIA driver and engine.log. CPU fallback was not started.',
    'Falsche Dateigröße: {name}':'Incorrect file size: {name}', 'Prüfsumme ungültig: {name}':'Invalid checksum: {name}',
    'Prüfe {name}':'Verifying {name}', 'Importiere {name}':'Importing {name}', 'Lade {name}':'Downloading {name}',
    'Modelldownload ist größer als erwartet.':'The model download is larger than expected.',
    'Modell fehlt: {name}. Modelle über die App herunterladen oder importieren.':'Model missing: {name}. Download or import models using the app.',
    'Auftragsdatei ist zu groß.':'The job file is too large.',
    'Veralteter Auftrag. Bitte einen neuen Auftrag starten.':'Outdated job. Please start a new job.',
    'Ungültiger Szenenstand.':'Invalid scene progress.', 'Ungültige Referenzen.':'Invalid references.',
    'Eine gesicherte Mediendatei fehlt oder wurde verändert.':'A saved media file is missing or has changed.',
    'Auftragsdatei ist ungültig oder unvollständig.':'The job file is invalid or incomplete.',
    'Prüfe NVIDIA-Treiber und CUDA …':'Checking the NVIDIA driver and CUDA …',
    'Videocache wurde verändert.':'The video cache has changed.',
    'Szene {number}: Videocache wird aus geprüften Originalbildern neu erstellt …':'Scene {number}: rebuilding the video cache from verified original frames …',
    'KI-Szene {number}/{total} wird berechnet. Fortschritt steht in engine.log.':'Generating AI scene {number}/{total}. Progress is recorded in engine.log.',
    'Szene {number}: Originalbilder werden als MP4 gespeichert …':'Scene {number}: encoding original frames as MP4 …',
    'Szene {number} gespeichert.':'Scene {number} saved.',
    'Szenen und Musik werden zusammengefügt …':'Combining scenes and music …',
    'Die Datei enthält keine lesbare Audiospur.':'The file does not contain a readable audio track.',
    'Ungültige PNG-Signatur.':'Invalid PNG signature.', 'Abgeschnittenes PNG ohne IEND.':'Truncated PNG without IEND.',
    'Ungültige PNG-Chunkgröße.':'Invalid PNG chunk size.', 'PNG-Chunks oder Prüfsumme beschädigt.':'Corrupt PNG chunks or checksum.',
    'PNG-Header fehlt.':'Missing PNG header.', 'Ungültiges PNG-Ende.':'Invalid PNG end.',
    'Ein KI-Bild hat die falsche Größe.':'An AI frame has incorrect dimensions.',
    'Fast einfarbige KI-Ausgabe. Originalbilder und engine.log prüfen.':'Almost solid-color AI output. Check the original frames and engine.log.',
    'Keine Originalbilder vorhanden.':'No original frames found.',
    'Referenzzeit muss eine positive Sekundenzahl sein.':'The reference time must be a non-negative number of seconds.',
    'Keine Videospur vorhanden.':'No video track found.', 'Referenzzeit liegt hinter dem Videoende.':'The reference time is beyond the end of the video.',
    'MP4 ist unvollständig oder hat eine falsche Dauer.':'The MP4 is incomplete or has an incorrect duration.',
    'MP4 enthält nicht alle Originalbilder.':'The MP4 does not contain all original frames.',
    'MP4 hat eine falsche Auflösung.':'The MP4 has an incorrect resolution.',
    'MP4 enthält nicht den erwarteten H.264-Videocodec.':'The MP4 does not contain the expected H.264 video codec.',
    'MP4-Bildrate ist ungültig.':'The MP4 frame rate is invalid.', 'MP4 hat eine falsche Bildrate.':'The MP4 has an incorrect frame rate.',
    'Ungültige Videobildfolge.':'Invalid video frame sequence.',
    'Die fertigen Szenen decken die gewünschte Videolänge nicht ab.':'The completed scenes do not cover the requested video duration.',
    'AVEN konnte nicht starten. Details: {path}':'AVEN could not start. Details: {path}',
}


ENGLISH.update({'CUDA prüfen': 'Check CUDA',
 'Modelle prüfen': 'Verify models',
 'Modelle laden / Referenzen vorbereiten': 'Load models / prepare references',
 'KI-Schritte': 'AI sampling',
 'Originalbilder decodieren': 'Decode original frames',
 'Originalbilder prüfen': 'Verify original frames',
 'MP4 speichern': 'Save MP4',
 'Musik und Szenen verbinden': 'Combine music and scenes',
 'Fertig': 'Complete',
 'Angehalten': 'Stopped',
 'GPU-Messung nicht verfügbar': 'GPU measurement unavailable',
 'Restzeit unbekannt': 'Remaining time unknown',
 'VRAM {used}/{total} MB · GPU {util} %': 'VRAM {used}/{total} MB · GPU {util} %',
 'Restzeit dieser KI-Schritte: ca. {time} (ohne Laden/VAE/MP4)': 'These sampling steps remaining: about {time} (excludes '
                                                                 'loading/VAE/MP4)',
 'Szene {scene}/{scenes} · {stage} · Schritt {step}/{steps} · Laufzeit {elapsed}\n{gpu}\n{eta}': 'Scene {scene}/{scenes} · '
                                                                                                 '{stage} · Step '
                                                                                                 '{step}/{steps} · Elapsed '
                                                                                                 '{elapsed}\n'
                                                                                                 '{gpu}\n'
                                                                                                 '{eta}',
 'Unbekanntes Speicherprofil.': 'Unknown memory profile.',
 'Mindestens 6 GB Grafikspeicher erforderlich.': 'At least 6 GB VRAM required.',
 'KI-Szene {number}/{total} wird berechnet.': 'Generating AI scene {number}/{total}.',
 'Szenenplan ungültig. Zeiten müssen bei 0 beginnen, aufsteigen und innerhalb der Videolänge liegen.': 'Invalid scene plan. '
                                                                                                       'Times must start at '
                                                                                                       '0, increase and '
                                                                                                       'fall within the '
                                                                                                       'video duration.',
 'Szenenplan, Zeile {number}: Startsekunde | Abschnitt | Szenenprompt eingeben.': 'Scene plan, line {number}: enter start '
                                                                                  'seconds | section | scene prompt.',
 'Ungültige Szenennummer.': 'Invalid scene number.',
 'Prompt ist zu lang (maximal 12000 Zeichen).': 'Prompt is too long (maximum 12000 characters).'})


ENGLISH.update({'Gemeinsamer Stil und wiederkehrendes Motiv': 'Shared style and recurring subject',
 'Gemeinsamer Stil': 'Shared style',
 'Motiv / Figur (Merkmale, Kleidung, Farben)': 'Subject / character (features, clothing, colors)',
 'Erste Referenz als festes Hauptmotiv für alle Szenen': 'Use the first reference as the fixed main subject in every scene',
 'Wiederkehrende Beschreibung und feste Referenz unterstützen den Zusammenhang. Identische Gesichter oder Kleidung sind nicht garantiert.': 'A '
                                                                                                                                            'shared '
                                                                                                                                            'description '
                                                                                                                                            'and '
                                                                                                                                            'fixed '
                                                                                                                                            'reference '
                                                                                                                                            'support '
                                                                                                                                            'continuity. '
                                                                                                                                            'Identical '
                                                                                                                                            'faces '
                                                                                                                                            'or '
                                                                                                                                            'clothing '
                                                                                                                                            'are '
                                                                                                                                            'not '
                                                                                                                                            'guaranteed.',
 'Musik-Szenenplan': 'Music scene plan',
 'Abschnitte vorschlagen': 'Suggest sections',
 'Szenenplan prüfen': 'Check scene plan',
 'Optional: Startsekunde | Abschnitt | Szenenprompt. Vorschläge richten sich nach der Laufzeit, nicht nach erkannten Beats. Änderungen greifen ab dem nächsten KI-Szenenbeginn (ca. 2,06 s). Leer = nur Hauptprompt.': 'Optional: '
                                                                                                                                                                                                                       'start '
                                                                                                                                                                                                                       'seconds '
                                                                                                                                                                                                                       '| '
                                                                                                                                                                                                                       'section '
                                                                                                                                                                                                                       '| '
                                                                                                                                                                                                                       'scene '
                                                                                                                                                                                                                       'prompt. '
                                                                                                                                                                                                                       'Suggestions '
                                                                                                                                                                                                                       'use '
                                                                                                                                                                                                                       'duration, '
                                                                                                                                                                                                                       'not '
                                                                                                                                                                                                                       'detected '
                                                                                                                                                                                                                       'beats. '
                                                                                                                                                                                                                       'Changes '
                                                                                                                                                                                                                       'apply '
                                                                                                                                                                                                                       'at '
                                                                                                                                                                                                                       'the '
                                                                                                                                                                                                                       'next '
                                                                                                                                                                                                                       'AI '
                                                                                                                                                                                                                       'scene '
                                                                                                                                                                                                                       'start '
                                                                                                                                                                                                                       '(about '
                                                                                                                                                                                                                       '2.06 '
                                                                                                                                                                                                                       's). '
                                                                                                                                                                                                                       'Empty '
                                                                                                                                                                                                                       '= '
                                                                                                                                                                                                                       'main '
                                                                                                                                                                                                                       'prompt '
                                                                                                                                                                                                                       'only.',
 'Vorhandenen Szenenplan durch Vorschläge ersetzen?': 'Replace the existing scene plan with suggestions?',
 'Szene {number} · {time} s · {title}': 'Scene {number} · {time} s · {title}',
 'Noch keine Originalbilder vorhanden.': 'No original frames available yet.',
 'Szene': 'Scene',
 'Referenz zeigen': 'Show reference',
 'Originalgröße (100 %)': 'Original size (100%)',
 '{job} · {width}×{height} · {file}': '{job} · {width}×{height} · {file}',
 'Bild nicht lesbar: {detail}': 'Cannot read image: {detail}',
 'Projekte und Originalbilder': 'Projects and original frames',
 'Aktualisieren': 'Refresh',
 'Als Vergleich B wählen': 'Set as comparison B',
 'Ausgewählten Auftrag fortsetzen': 'Resume selected job',
 'Video öffnen': 'Open video',
 'Messbericht / Qualität bewerten': 'Measurement report / assess quality',
 'Projekt': 'Project',
 'Szenen': 'Scenes',
 'Status': 'Status',
 'Original-PNGs vergleichen: A und B unabhängig wählen. Die Anzeige ist verkleinert; „Originalgröße“ zeigt echte Pixel. MP4 spielt im Standard-Videoplayer.': 'Compare '
                                                                                                                                                              'original '
                                                                                                                                                              'PNGs: '
                                                                                                                                                              'choose '
                                                                                                                                                              'A '
                                                                                                                                                              'and '
                                                                                                                                                              'B '
                                                                                                                                                              'independently. '
                                                                                                                                                              'This '
                                                                                                                                                              'view '
                                                                                                                                                              'is '
                                                                                                                                                              'reduced; '
                                                                                                                                                              '“Original '
                                                                                                                                                              'size” '
                                                                                                                                                              'shows '
                                                                                                                                                              'actual '
                                                                                                                                                              'pixels. '
                                                                                                                                                              'MP4 '
                                                                                                                                                              'opens '
                                                                                                                                                              'in '
                                                                                                                                                              'the '
                                                                                                                                                              'default '
                                                                                                                                                              'video '
                                                                                                                                                              'player.',
 'A · ausgewähltes Projekt': 'A · selected project',
 'B · Vergleich': 'B · comparison',
 'Auftragsdatei prüfen': 'Check job file',
 'MP4 vorhanden': 'MP4 available',
 'Noch kein MP4': 'No MP4 yet',
 'Messbericht ist ungültig.': 'Invalid measurement report.',
 'Noch kein Messbericht vorhanden. Zuerst den Qualitätstest ausführen.': 'No measurement report yet. Run the quality test '
                                                                         'first.',
 'Status: {status} · Laufzeit: {elapsed} · Szenen: {scenes}\nGPU: {gpu}\nGemessener VRAM-Höchstwert: {peak} MB ({samples} Messungen, gesamte GPU)\nProfil: {width}×{height}, {steps} Schritte, {mode}\nBildqualität und natürliche Bewegung bitte selbst anhand der Originalbilder und des Videos prüfen.': 'Status: '
                                                                                                                                                                                                                                                                                                            '{status} '
                                                                                                                                                                                                                                                                                                            '· '
                                                                                                                                                                                                                                                                                                            'Elapsed: '
                                                                                                                                                                                                                                                                                                            '{elapsed} '
                                                                                                                                                                                                                                                                                                            '· '
                                                                                                                                                                                                                                                                                                            'Scenes: '
                                                                                                                                                                                                                                                                                                            '{scenes}\n'
                                                                                                                                                                                                                                                                                                            'GPU: '
                                                                                                                                                                                                                                                                                                            '{gpu}\n'
                                                                                                                                                                                                                                                                                                            'Highest '
                                                                                                                                                                                                                                                                                                            'sampled '
                                                                                                                                                                                                                                                                                                            'VRAM: '
                                                                                                                                                                                                                                                                                                            '{peak} '
                                                                                                                                                                                                                                                                                                            'MB '
                                                                                                                                                                                                                                                                                                            '({samples} '
                                                                                                                                                                                                                                                                                                            'samples, '
                                                                                                                                                                                                                                                                                                            'whole '
                                                                                                                                                                                                                                                                                                            'GPU)\n'
                                                                                                                                                                                                                                                                                                            'Profile: '
                                                                                                                                                                                                                                                                                                            '{width}×{height}, '
                                                                                                                                                                                                                                                                                                            '{steps} '
                                                                                                                                                                                                                                                                                                            'steps, '
                                                                                                                                                                                                                                                                                                            '{mode}\n'
                                                                                                                                                                                                                                                                                                            'Please '
                                                                                                                                                                                                                                                                                                            'assess '
                                                                                                                                                                                                                                                                                                            'image '
                                                                                                                                                                                                                                                                                                            'quality '
                                                                                                                                                                                                                                                                                                            'and '
                                                                                                                                                                                                                                                                                                            'natural '
                                                                                                                                                                                                                                                                                                            'motion '
                                                                                                                                                                                                                                                                                                            'using '
                                                                                                                                                                                                                                                                                                            'the '
                                                                                                                                                                                                                                                                                                            'original '
                                                                                                                                                                                                                                                                                                            'frames '
                                                                                                                                                                                                                                                                                                            'and '
                                                                                                                                                                                                                                                                                                            'video.',
 'Messwerte sind keine automatische Qualitätsbewertung. Fehlende GPU-Werte bedeuten „nicht gemessen“. Bei Fehlern bleiben Protokolle erhalten.': 'Measurements '
                                                                                                                                                 'are '
                                                                                                                                                 'not '
                                                                                                                                                 'an '
                                                                                                                                                 'automatic '
                                                                                                                                                 'quality '
                                                                                                                                                 'assessment. '
                                                                                                                                                 'Missing '
                                                                                                                                                 'GPU '
                                                                                                                                                 'values '
                                                                                                                                                 'mean '
                                                                                                                                                 '“not '
                                                                                                                                                 'measured”. '
                                                                                                                                                 'Logs '
                                                                                                                                                 'are '
                                                                                                                                                 'preserved '
                                                                                                                                                 'on '
                                                                                                                                                 'errors.',
 'Motiv und Bewegung gut': 'Subject and motion look good',
 'Unscharf / falsches Motiv / Bewegung fehlerhaft': 'Blurred / wrong subject / motion problems',
 'Später prüfen': 'Review later',
 'Berichtdatei öffnen': 'Open report file',
 'Als Hauptmotiv wählen': 'Set as main subject',
 'Pro Video wird ein Einzelbild zur gewählten Zeit übernommen. Im festen Modus zählt die erste Referenz, sonst wechseln die Referenzen je Szene.': 'One '
                                                                                                                                                   'still '
                                                                                                                                                   'is '
                                                                                                                                                   'extracted '
                                                                                                                                                   'per '
                                                                                                                                                   'video '
                                                                                                                                                   'at '
                                                                                                                                                   'the '
                                                                                                                                                   'selected '
                                                                                                                                                   'time. '
                                                                                                                                                   'Fixed '
                                                                                                                                                   'mode '
                                                                                                                                                   'uses '
                                                                                                                                                   'the '
                                                                                                                                                   'first '
                                                                                                                                                   'reference; '
                                                                                                                                                   'otherwise '
                                                                                                                                                   'references '
                                                                                                                                                   'alternate '
                                                                                                                                                   'between '
                                                                                                                                                   'scenes.',
 'Diffusionsgewichte dauerhaft im VRAM halten (Vergleichsprofil)': 'Keep diffusion weights in VRAM (comparison profile)',
 'Projekte / Bildvergleich': 'Projects / frame comparison',
 'Messbericht': 'Measurement report',
 'Messwerte erscheinen während eines KI-Auftrags. Restzeit gilt nur für die aktuelle KI-Berechnung.': 'Measurements appear '
                                                                                                      'during an AI job. '
                                                                                                      'Remaining time '
                                                                                                      'applies only to the '
                                                                                                      'current sampling '
                                                                                                      'steps.',
 'RTX-Speicherprofil: {mode} · verwaltetes CUDA-Budget {budget:g} GiB · 2 GiB Reserve eingeplant. Kein harter VRAM-Grenzwert.': 'RTX '
                                                                                                                                'memory '
                                                                                                                                'profile: '
                                                                                                                                '{mode} '
                                                                                                                                '· '
                                                                                                                                'managed '
                                                                                                                                'CUDA '
                                                                                                                                'budget '
                                                                                                                                '{budget:g} '
                                                                                                                                'GiB '
                                                                                                                                '· '
                                                                                                                                '2 '
                                                                                                                                'GiB '
                                                                                                                                'reserved. '
                                                                                                                                'This '
                                                                                                                                'is '
                                                                                                                                'not '
                                                                                                                                'a '
                                                                                                                                'physical '
                                                                                                                                'VRAM '
                                                                                                                                'cap.',
 'Gewichte im VRAM': 'Weights in VRAM',
 'Gewichte im Arbeitsspeicher': 'Weights in system RAM',
 'Ungültige Qualitätsbewertung.': 'Invalid quality assessment.',
 'Nicht gemessen': 'Not measured',
 'Abgeschlossen': 'Completed',
 'Fehlgeschlagen': 'Failed'})


class Text(str):
    def __new__(cls, source, **values):
        obj=super().__new__(cls,source.format(**values))
        obj.source=source; obj.values=values
        return obj


def message(source, **values):
    return Text(source,**values)


class Locale:
    def __init__(self, path):
        self.path=Path(path); self.code='de'
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data,dict) and data.get('language') in ('de','en'): self.code=data['language']
        except (OSError,ValueError): pass

    def select(self, code):
        if code not in ('de','en'): raise ValueError('Unsupported language')
        self.code=code
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_name('.language-'+uuid.uuid4().hex+'.json')
        try:
            temp.write_text(json.dumps({'language':code}),encoding='utf-8')
            os.replace(temp,self.path)
        finally: temp.unlink(missing_ok=True)

    def render(self, value):
        if isinstance(value,BaseException):
            value=value.args[0] if len(value.args)==1 else str(value)
        if isinstance(value,Text):
            source=ENGLISH.get(value.source,value.source) if self.code=='en' else value.source
            values={k:self.render(v) if isinstance(v,(Text,BaseException)) else v for k,v in value.values.items()}
            return source.format(**values)
        text=str(value)
        return ENGLISH.get(text,text) if self.code=='en' else text


class Binding:
    def __init__(self, locale, setter, source): self.locale=locale; self.setter=setter; self.source=source
    def refresh(self): self.setter(self.locale.render(self.source))
    def set(self, source): self.source=source; self.refresh()


class Bindings:
    def __init__(self, locale): self.locale=locale; self.items=[]
    def bind(self, setter, source):
        binding=Binding(self.locale,setter,source); self.items.append(binding); binding.refresh(); return binding
    def refresh(self):
        for item in self.items: item.refresh()
