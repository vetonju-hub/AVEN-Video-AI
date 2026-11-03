import SwiftUI
import AppKit
import AVFoundation
import Vision
import UniformTypeIdentifiers
import CoreText
import CoreGraphics
import CoreVideo

@main
struct AVENApp: App {
    @StateObject private var studio = StudioModel()

    var body: some Scene {
        WindowGroup("AVEN Video AI") {
            StudioView()
                .environmentObject(studio)
                .frame(minWidth: 980, minHeight: 680)
                .preferredColorScheme(.dark)
        }
        .defaultSize(width: 1180, height: 770)
    }
}

struct SceneImage: Identifiable {
    let id = UUID()
    let name: String
    let thumbnail: NSImage
    let cgImage: CGImage
    let sourceLabel: String
}



final class StudioModel: ObservableObject {
    @Published var prompt = "A quiet city street at night, purple neon reflected on wet pavement. A slow forward camera movement, sharp focus, natural lighting."
    @Published var negativePrompt = GenerationPolicy.defaultNegative
    @Published var seed: Int64 = 42
    @Published var matchMusicLength = true
    @Published var musicDuration: Double?
    @Published var isImporting = false
    @Published var referenceTime = 0.0
    @Published var projectTitle = "Mein AVEN Video"
    @Published var duration = 30.0
    @Published var format: VideoFormat = .widescreen
    @Published var scenes: [SceneImage] = []
    @Published var soundtrack: URL?
    @Published var status = "Bereit – komplett offline"
    @Published var progress = 0.0
    @Published var isRendering = false
    @Published var lastOutput: URL?
    @Published var visionResult = ""
    private var cancellation: RenderCancellation?

    var targetSeconds: Double {
        (try? VideoTiming.resolve(manual: duration, music: musicDuration, matchMusic: matchMusicLength && soundtrack != nil)) ?? duration
    }

    func addImages() {
        let panel = NSOpenPanel()
        panel.title = "Fotos als Motiv-Referenzen importieren"
        panel.allowedContentTypes = [.image]
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        if panel.runModal() == .OK { importReferences(panel.urls, video: false) }
    }

    func addVideos() {
        let panel = NSOpenPanel()
        panel.title = "Video auswählen – ein Referenzbild pro Clip"
        panel.allowedContentTypes = [.movie, .mpeg4Movie, .quickTimeMovie]
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        if panel.runModal() == .OK { importReferences(panel.urls, video: true) }
    }

    private func importReferences(_ urls: [URL], video: Bool) {
        guard !isImporting else { return }
        let seconds = referenceTime
        isImporting = true
        status = "Medien werden lokal gelesen …"
        DispatchQueue.global(qos: .userInitiated).async {
            var added: [SceneImage] = []
            var errors: [String] = []
            for url in urls {
                do {
                    let cg = try video ? MediaImport.referenceFromVideo(url, seconds: seconds) : MediaImport.decodeImage(url, maxPixelSize: 1920)
                    added.append(SceneImage(name: url.lastPathComponent,
                        thumbnail: NSImage(cgImage: cg, size: .zero), cgImage: cg,
                        sourceLabel: video ? "Video-Referenz bei \(String(format: "%.1f", seconds)) s" : "Foto-Referenz"))
                } catch { errors.append("\(url.lastPathComponent): \(error.localizedDescription)") }
            }
            DispatchQueue.main.async {
                self.scenes.append(contentsOf: added)
                self.isImporting = false
                self.status = "\(added.count) Referenz(en) importiert" + (errors.isEmpty ? "" : " · " + errors.joined(separator: "; "))
            }
        }
    }

    func removeScene(_ id: UUID) { scenes.removeAll { $0.id == id } }

    func chooseAudio() {
        guard !isImporting else { return }
        let panel = NSOpenPanel()
        panel.title = "Musikdatei auswählen"
        panel.allowedContentTypes = [.mp3, .mpeg4Audio, .wav, .aiff, .audio]
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        isImporting = true
        DispatchQueue.global(qos: .utility).async {
            do {
                let length = try MediaImport.audioDuration(url)
                DispatchQueue.main.async {
                    self.soundtrack = url
                    self.musicDuration = length
                    self.isImporting = false
                    self.status = "Musik importiert: \(String(format: "%.3f", length)) Sekunden"
                }
            } catch {
                DispatchQueue.main.async { self.isImporting = false; self.status = error.localizedDescription }
            }
        }
    }

    func removeAudio() { soundtrack = nil; musicDuration = nil }

    func analyzeFirstImage() {
        guard let image = scenes.first?.cgImage else {
            visionResult = "Bitte zuerst ein Bild hinzufügen."
            return
        }
        let request = VNClassifyImageRequest()
        do {
            try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
            let labels = (request.results ?? []).prefix(3).map { "\($0.identifier) (\(Int($0.confidence * 100)) %)" }
            visionResult = labels.isEmpty ? "Keine Motive erkannt." : "Lokale KI-Bildanalyse: " + labels.joined(separator: " · ")
        } catch {
            visionResult = "Bildanalyse nicht verfügbar: \(error.localizedDescription)"
        }
    }

    func exportVideo() {
        guard !isRendering else { return }
        do { _ = try VideoTiming.resolve(manual: duration, music: musicDuration, matchMusic: matchMusicLength && soundtrack != nil) }
        catch { status = error.localizedDescription; return }
        let panel = NSSavePanel()
        panel.title = "Video exportieren"
        panel.allowedContentTypes = [.mpeg4Movie]
        panel.nameFieldStringValue = "AVEN_Video.mp4"
        if panel.runModal() != .OK { return }
        guard let output = panel.url else { return }
        let job = RenderJob(images: scenes.map(\.cgImage),
                            title: projectTitle, prompt: prompt,
                            duration: targetSeconds, format: format, soundtrack: soundtrack)
        let token = RenderCancellation()
        cancellation = token
        isRendering = true
        progress = 0
        status = "Rendern gestartet …"
        lastOutput = nil
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try VideoRenderer.render(job: job, output: output, cancellation: token) { p in
                    DispatchQueue.main.async {
                        guard self.isRendering && !token.isCancelled else { return }
                        self.progress = p
                        self.status = "Video wird erstellt: \(Int(p * 100)) %"
                    }
                }
                DispatchQueue.main.async {
                    self.isRendering = false
                    self.cancellation = nil
                    let published = token.commitIfActive {
                        self.progress = 1
                        self.status = "Fertig: \(output.lastPathComponent)"
                        self.lastOutput = output
                    }
                    if !published { self.status = "Export angehalten. Eine bereits geschriebene Datei bleibt erhalten." }
                }
            } catch {
                DispatchQueue.main.async {
                    self.isRendering = false
                    self.cancellation = nil
                    self.status = "Fehler: \(error.localizedDescription)"
                }
            }
        }
    }

    func cancelExport() { cancellation?.cancel(); status = "Abbruch angefordert …" }
    func revealOutput() { if let url = lastOutput { NSWorkspace.shared.activateFileViewerSelecting([url]) } }
}

struct StudioView: View {
    @EnvironmentObject var studio: StudioModel
    @StateObject private var localAI = AVENLocalAI()
    @State private var realismLevel = 5.0
    @State private var fullPower = false
    @State private var useReference = true
    private let machine = AVENHardware.detect()
    private let accent = Color(red: 0.64, green: 0.43, blue: 1)

    var body: some View {
        HStack(spacing: 0) {
            sidebar
                .frame(width: 230)
            Rectangle().fill(.white.opacity(0.1)).frame(width: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 23) {
                    header
                    preview
                    controls.disabled(localAI.isGenerating || localAI.isDownloading || studio.isRendering)
                    aiControls
                    timeline.disabled(localAI.isGenerating || studio.isRendering)
                    footer.disabled(localAI.isGenerating || localAI.isDownloading || studio.isImporting)
                }
                .padding(28)
            }
        }
        .background(Color(red: 0.065, green: 0.075, blue: 0.11))
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 25) {
            HStack(spacing: 10) {
                Image(systemName: "sparkles.tv.fill")
                    .font(.system(size: 27)).foregroundStyle(accent)
                VStack(alignment: .leading, spacing: 2) {
                    Text("AVEN").font(.system(size: 24, weight: .black, design: .rounded))
                    Text("VIDEO AI · LOCAL").font(.system(size: 10, weight: .semibold)).tracking(2).foregroundStyle(.secondary)
                }
            }
            .padding(.top, 8)
            Divider()
            Label("Video Studio", systemImage: "film.stack.fill")
                .fontWeight(.bold).foregroundStyle(accent)
            Label("Deine Bilder", systemImage: "photo.on.rectangle")
                .foregroundStyle(.secondary)
            Label("Musik & Audio", systemImage: "waveform")
                .foregroundStyle(.secondary)
            Spacer()
            VStack(alignment: .leading, spacing: 10) {
                Label("100 % lokale Verarbeitung", systemImage: "checkmark.shield.fill")
                    .font(.system(size: 12)).foregroundStyle(.green)
                Text(machine.architecture + " · " + String(machine.memoryGB) + " GB RAM\nKeine Cloud · Keine API-Kosten")
                    .font(.system(size: 11)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 13))
        }
        .padding(21)
        .frame(maxHeight: .infinity, alignment: .topLeading)
        .background(Color(red: 0.085, green: 0.095, blue: 0.14))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("Dein Video. Dein Mac.")
                .font(.system(size: 32, weight: .bold, design: .rounded))
            Text("Lokale KI-Szenen und Musikvideos erstellen. Nach dem Modelldownload vollständig offline.")
                .foregroundStyle(.secondary)
        }
    }

    private var preview: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20)
                .fill(LinearGradient(colors: [Color(red: 0.21, green: 0.14, blue: 0.4),
                                              Color(red: 0.05, green: 0.08, blue: 0.18)],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
            if let image = studio.scenes.first?.thumbnail {
                Image(nsImage: image).resizable().scaledToFit()
                    .padding(12).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 14) {
                    Image(systemName: "play.rectangle.on.rectangle.fill")
                        .font(.system(size: 64)).foregroundStyle(.white.opacity(0.75))
                    Text("VIDEO VORSCHAU")
                        .font(.system(size: 12, weight: .semibold)).tracking(3).foregroundStyle(.white.opacity(0.75))
                    Text("Füge Bilder hinzu oder erstelle ein animiertes Titelvideo")
                        .font(.system(size: 12)).foregroundStyle(.white.opacity(0.7))
                }
            }
        }
        .frame(height: 260)
        .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(.white.opacity(0.12)))
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("PROJEKT-EINSTELLUNGEN").font(.system(size: 11, weight: .bold)).tracking(2).foregroundStyle(.secondary)
            TextField("Projekttitel", text: $studio.projectTitle)
                .textFieldStyle(.roundedBorder)
            Text("Szenenbeschreibung").font(.caption).foregroundStyle(.secondary)
            TextEditor(text: $studio.prompt)
                .font(.body)
                .scrollContentBackground(.hidden)
                .padding(10)
                .frame(minHeight: 110)
                .background(.black.opacity(0.2), in: RoundedRectangle(cornerRadius: 10))
            Text("Beschreibe Motiv, Bewegung, Licht und Kamera. Englische Beschreibungen funktionieren mit Wan meist besser; es wird kein Online-Übersetzer verwendet.")
                .font(.caption).foregroundStyle(.secondary)
            DisclosureGroup("Erweiterter Prompt und reproduzierbarer Seed") {
                TextEditor(text: $studio.negativePrompt).frame(height: 65).font(.caption)
                HStack {
                    Text("Seed")
                    TextField("0–2147483647", value: $studio.seed, format: .number.grouping(.never))
                        .textFieldStyle(.roundedBorder).frame(width: 160)
                    Button("Zufällig") { studio.seed = Int64.random(in: 0...2_147_483_647) }
                }
            }
            HStack(spacing: 18) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Videoformat").font(.caption).foregroundStyle(.secondary)
                    Picker("Format", selection: $studio.format) {
                        ForEach(VideoFormat.allCases) { format in
                            Text(format.rawValue).tag(format)
                        }
                    }.labelsHidden().pickerStyle(.segmented)
                }
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("Eigene Länge").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text("\(String(format: "%.1f", studio.targetSeconds)) s")
                            .monospacedDigit().font(.caption).foregroundStyle(accent)
                    }
                    TextField("Sekunden", value: $studio.duration, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .disabled(studio.matchMusicLength && studio.soundtrack != nil)
                }
            }
            HStack(spacing: 10) {
                Button { studio.addImages() } label: { Label("Bilder hinzufügen", systemImage: "plus.rectangle.on.rectangle") }
                Button { studio.addVideos() } label: { Label("Video als Referenz", systemImage: "film") }
                Button { studio.chooseAudio() } label: { Label("Musik hinzufügen", systemImage: "music.note") }
                Button { studio.analyzeFirstImage() } label: { Label("KI-Motiverkennung", systemImage: "viewfinder") }
            }
            .buttonStyle(.bordered)
            .disabled(studio.isImporting)
            HStack {
                Text("Referenzzeit im Video (Sekunden)").font(.caption)
                TextField("Sekunden", value: $studio.referenceTime, format: .number).frame(width: 90)
                    .textFieldStyle(.roundedBorder)
            }
            Text("Videoimport übernimmt ein Einzelbild als Motiv-Referenz. Bewegungen des Originalvideos werden nicht übertragen. Fotos und Videoreferenzen werden in der Szenenreihenfolge verwendet.")
                .font(.caption).foregroundStyle(.secondary)
            Toggle("Videolänge automatisch an die gesamte Musik anpassen", isOn: $studio.matchMusicLength)
            if let soundtrack = studio.soundtrack {
                HStack {
                    Text("Musik: \(soundtrack.lastPathComponent) · \(String(format: "%.3f", studio.musicDuration ?? 0)) s")
                        .font(.caption).foregroundStyle(.secondary)
                    Button("Entfernen") { studio.removeAudio() }
                }
            }
            if !studio.visionResult.isEmpty {
                Text(studio.visionResult).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(20)
        .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 17))
    }

    private var aiControls: some View {
        let plan = AVENQualityPlan.make(for: machine, level: Int(realismLevel),
                                        portrait: studio.format == .portrait, fullPower: fullPower, square: studio.format == .square)
        return VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "cpu.fill").foregroundStyle(accent)
                Text("ADAPTIVE REALISM ENGINE · LOKALE KI")
                    .font(.system(size: 12, weight: .bold)).tracking(1)
            }
            Text("Hardware erkannt: " + machine.label)
                .font(.caption).foregroundStyle(.secondary)
                .textSelection(.enabled)
            HStack {
                Text("Realismus / Rechenaufwand").fontWeight(.semibold)
                Spacer()
                Text("\(Int(realismLevel))/10" + (realismLevel >= 10 ? " · MAX REALISM" : ""))
                    .foregroundStyle(accent).fontWeight(.bold)
            }
            Slider(value: $realismLevel, in: 1...10, step: 1)
                .tint(accent)
                .accessibilityLabel("Realismusstufe 1 bis 10")
            HStack {
                Text("480p · mindestens 20 Schritte").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Text("Maximale lokale Qualität").font(.caption2).foregroundStyle(.secondary)
            }
            Text(plan.shortDescription + " · Backend: " + plan.backend)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(.white.opacity(0.85))
            Text(plan.caution).font(.caption).foregroundStyle(.orange)
            Toggle("Volle Prozessorleistung verwenden", isOn: $fullPower)
                .toggleStyle(.switch)
            Toggle("Importierte Motive als Referenzen verwenden", isOn: $useReference)
                .toggleStyle(.switch)
            let seconds = studio.targetSeconds
            let segmentCount = VideoTiming.sceneCount(seconds: seconds, clipSeconds: plan.clipSeconds)
            Text("Ziel: \(String(format: "%.3f", seconds)) Sekunden · \(segmentCount) KI-Sequenzen")
                .font(.caption).foregroundStyle(.secondary)
            Text("Jede Sequenz verwendet eine eigene Berechnung und einen eigenen Seed. Zwischen Szenen sind Schnitte möglich; ein langer Song kann auf Intel viele Tage benötigen. Erst den kurzen Qualitätstest prüfen.")
                .font(.caption).foregroundStyle(.secondary)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), alignment: .leading)], alignment: .leading, spacing: 10) {
                if localAI.isDownloading {
                    ProgressView(value: localAI.downloadProgress)
                    Button("Download abbrechen") { localAI.stopDownload() }
                } else if !localAI.isReady {
                    Button { localAI.installModels(useHighPrecision: plan.modelTier.hasPrefix("Q8")) } label: {
                        Label("Kostenlose KI-Modelle herunterladen", systemImage: "arrow.down.circle")
                    }.buttonStyle(.borderedProminent).tint(accent)
                } else if localAI.isGenerating {
                    ProgressView()
                    Button("KI-Berechnung abbrechen") { localAI.cancelGeneration() }
                    Button("Szenenordner anzeigen") { localAI.showWorkFolder() }
                } else {
                    Button {
                        do {
                            let seconds = try VideoTiming.resolve(manual: studio.duration, music: studio.musicDuration,
                                matchMusic: studio.matchMusicLength && studio.soundtrack != nil)
                            localAI.generateAdaptive(references: useReference ? studio.scenes.map(\.cgImage) : [],
                                prompt: studio.prompt, negativePrompt: studio.negativePrompt, seed: studio.seed,
                                format: studio.format, soundtrack: studio.soundtrack, plan: plan, targetSeconds: seconds)
                        } catch { studio.status = error.localizedDescription }
                    } label: {
                        Label("ECHTES KI-VIDEO GENERIEREN", systemImage: "sparkles.tv")
                    }.buttonStyle(.borderedProminent).tint(accent)
                    Button("2-Sekunden-Qualitätstest") {
                        let smokePlan = AVENQualityPlan.make(for: machine, level: 1, portrait: false, fullPower: fullPower)
                        localAI.generateAdaptive(references: [], prompt: GenerationPolicy.smokePrompt,
                            negativePrompt: GenerationPolicy.defaultNegative, seed: 42, format: .widescreen,
                            soundtrack: nil, plan: smokePlan, targetSeconds: 2)
                    }
                    if localAI.resultURL != nil {
                        Button("KI-Vorschau anzeigen") { localAI.showResult() }
                    }
                    if localAI.canResume {
                        Button("Letzten Auftrag fortsetzen") { localAI.resumeLastJob() }
                    }
                    if realismLevel >= 8 && !localAI.highPrecisionReady {
                        Button("Q8-Qualitätsmodell nachladen") { localAI.installModels(useHighPrecision: true) }
                    }
                    Button("Szenenordner anzeigen") { localAI.showWorkFolder() }
                }
            }
            .disabled(studio.isImporting || studio.isRendering || machine.memoryGB < 8)
            Text(localAI.message).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            Text("Wan VACE nutzt das Bild als Motiv-Referenz, nicht als garantiert unveränderten Startframe. Jeder Durchlauf erzeugt neue Modell-Frames. Max Realism ist ein Rechenprofil, kein Versprechen für perfekte Gesichter oder Filmqualität. Alle KI-Aufträge laufen nach Modelldownload ohne Netzwerk.")
                .font(.system(size: 11)).foregroundStyle(.secondary)
        }
        .padding(20)
        .background(.purple.opacity(0.08), in: RoundedRectangle(cornerRadius: 17))
        .overlay(RoundedRectangle(cornerRadius: 17).strokeBorder(accent.opacity(0.25)))
    }

    private var timeline: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("SZENEN").font(.system(size: 11, weight: .bold)).tracking(2).foregroundStyle(.secondary)
                Spacer()
                Text("\(studio.scenes.count) Referenzen").font(.caption).foregroundStyle(.secondary)
            }
            if studio.scenes.isEmpty {
                Text("Keine Referenzen ausgewählt. Die KI kann allein aus deiner Szenenbeschreibung generieren.")
                    .font(.system(size: 12)).foregroundStyle(.secondary)
                    .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 12))
            } else {
                ScrollView(.horizontal) {
                    HStack(spacing: 12) {
                        ForEach(studio.scenes) { scene in
                            VStack(spacing: 5) {
                                Image(nsImage: scene.thumbnail)
                                    .resizable().scaledToFill().frame(width: 126, height: 76).clipped()
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                                Text(scene.sourceLabel).lineLimit(1).font(.system(size: 9)).foregroundStyle(.secondary)
                                HStack(spacing: 4) {
                                    Text(scene.name).lineLimit(1).font(.system(size: 10)).frame(maxWidth: 104)
                                    Button { studio.removeScene(scene.id) } label: { Image(systemName: "xmark.circle.fill") }
                                        .buttonStyle(.plain).foregroundStyle(.secondary)
                                }
                            }
                            .frame(width: 132)
                        }
                    }
                }
            }
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 12) {
            if studio.isRendering {
                ProgressView(value: studio.progress)
                Button("Rendern abbrechen", role: .destructive) { studio.cancelExport() }
            } else {
                HStack(spacing: 12) {
                    Button { studio.exportVideo() } label: {
                        Label("Bilder / Titel animiert exportieren", systemImage: "video.badge.checkmark")
                            .font(.system(size: 15, weight: .bold)).frame(minWidth: 195)
                    }
                    .buttonStyle(.borderedProminent).tint(accent).controlSize(.large)
                    if studio.lastOutput != nil {
                        Button("Im Finder anzeigen") { studio.revealOutput() }
                            .buttonStyle(.bordered)
                    }
                }
            }
            Text(studio.status).font(.caption).foregroundStyle(.secondary)
            Text("Hinweis: Animierte Bilder und Titel sind keine generativ erzeugten KI-Filmszenen. Die Motiverkennung verwendet lokal Apples Vision-ML.")
                .font(.system(size: 11)).foregroundStyle(.orange.opacity(0.85))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
