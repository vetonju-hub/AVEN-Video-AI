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
}

final class RenderCancellation {
    private let lock = NSLock()
    private var cancelled = false
    func cancel() { lock.lock(); cancelled = true; lock.unlock() }
    var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return cancelled }
}

enum VideoFormat: String, CaseIterable, Identifiable {
    case widescreen = "16:9"
    case portrait = "9:16"
    case square = "1:1"
    var id: String { rawValue }
    var dimensions: (Int, Int) {
        switch self {
        case .widescreen: return (960, 540)
        case .portrait: return (540, 960)
        case .square: return (720, 720)
        }
    }
}

final class StudioModel: ObservableObject {
    @Published var prompt = "Eine nächtliche Stadt mit violetten Lichtern"
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

    func addImages() {
        let panel = NSOpenPanel()
        panel.title = "Bilder für deine Szenen wählen"
        panel.allowedContentTypes = [.image]
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        if panel.runModal() == .OK {
            for url in panel.urls {
                guard let image = NSImage(contentsOf: url),
                      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
                scenes.append(SceneImage(name: url.lastPathComponent, thumbnail: image, cgImage: cgImage))
            }
            status = "\(scenes.count) Bild(er) hinzugefügt"
        }
    }

    func removeScene(_ id: UUID) { scenes.removeAll { $0.id == id } }

    func chooseAudio() {
        let panel = NSOpenPanel()
        panel.title = "Musikdatei auswählen"
        panel.allowedContentTypes = [.mp3, .mpeg4Audio, .wav, .aiff, .audio]
        if panel.runModal() == .OK { soundtrack = panel.url }
    }

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
        let panel = NSSavePanel()
        panel.title = "Video exportieren"
        panel.allowedContentTypes = [.mpeg4Movie]
        panel.nameFieldStringValue = "AVEN_Video.mp4"
        if panel.runModal() != .OK { return }
        guard let output = panel.url else { return }
        let job = RenderJob(images: scenes.map(\.cgImage),
                            title: projectTitle, prompt: prompt,
                            duration: duration, format: format, soundtrack: soundtrack)
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
                        self.progress = p
                        self.status = "Video wird erstellt: \(Int(p * 100)) %"
                    }
                }
                DispatchQueue.main.async {
                    self.isRendering = false
                    self.cancellation = nil
                    self.progress = 1
                    self.status = "Fertig: \(output.lastPathComponent)"
                    self.lastOutput = output
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
    @State private var secondsToGenerate = 4.0
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
                    controls
                    aiControls
                    timeline
                    footer
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
            Text("Bilder animieren, Clips gestalten und bis zu 4 Minuten als MP4 exportieren – vollständig offline.")
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
            TextField("Stimmung / Szenenbeschreibung", text: $studio.prompt)
                .textFieldStyle(.roundedBorder)
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
                        Text("Länge").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int(studio.duration / 60)):\(String(format: "%02d", Int(studio.duration) % 60)) min")
                            .monospacedDigit().font(.caption).foregroundStyle(accent)
                    }
                    Slider(value: $studio.duration, in: 5...240, step: 5)
                }
            }
            HStack(spacing: 10) {
                Button { studio.addImages() } label: { Label("Bilder hinzufügen", systemImage: "plus.rectangle.on.rectangle") }
                Button { studio.chooseAudio() } label: { Label("Musik hinzufügen", systemImage: "music.note") }
                Button { studio.analyzeFirstImage() } label: { Label("KI-Motiverkennung", systemImage: "viewfinder") }
            }
            .buttonStyle(.bordered)
            if let soundtrack = studio.soundtrack {
                Text("Musik: \(soundtrack.lastPathComponent)").font(.caption).foregroundStyle(.secondary)
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
                Text("Schneller Test").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Text("Maximale lokale Qualität").font(.caption2).foregroundStyle(.secondary)
            }
            Text(plan.shortDescription + " · Backend: " + plan.backend)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(.white.opacity(0.85))
            Text(plan.caution).font(.caption).foregroundStyle(.orange)
            Toggle("Volle Prozessorleistung verwenden", isOn: $fullPower)
                .toggleStyle(.switch)
            Toggle("Erstes importiertes Bild als Referenz verwenden", isOn: $useReference)
                .toggleStyle(.switch)
            HStack {
                Text("Gesamtlänge der KI-Szenen").font(.caption)
                Slider(value: $secondsToGenerate, in: 2...240, step: 2)
                Text("\(Int(secondsToGenerate)) s").monospacedDigit().frame(width: 48)
            }
            let segmentCount = Int(ceil(secondsToGenerate / plan.clipSeconds))
            Text("\(segmentCount) echte KI-Sequenzen geplant. Je nach Gerät können bereits einzelne Sequenzen viele Stunden benötigen. Fertige Szenen werden einzeln gespeichert.")
                .font(.caption).foregroundStyle(.secondary)
            HStack(spacing: 10) {
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
                        localAI.generateAdaptive(firstImage: useReference ? studio.scenes.first?.cgImage : nil,
                                                 prompt: studio.prompt, format: studio.format,
                                                 soundtrack: studio.soundtrack, plan: plan,
                                                 targetSeconds: secondsToGenerate)
                    } label: {
                        Label("ECHTES KI-VIDEO GENERIEREN", systemImage: "sparkles.tv")
                    }.buttonStyle(.borderedProminent).tint(accent)
                    if localAI.resultURL != nil {
                        Button("Fertiges Video anzeigen") { localAI.showResult() }
                    }
                    if localAI.canResume {
                        Button("Letzten Auftrag fortsetzen") { localAI.resumeLastJob() }
                    }
                    if machine.memoryGB >= 48 && realismLevel >= 8 && !localAI.highPrecisionReady {
                        Button("Q8-Qualitätsmodell nachladen") { localAI.installModels(useHighPrecision: true) }
                    }
                    Button("Szenenordner anzeigen") { localAI.showWorkFolder() }
                }
            }
            Text(localAI.message).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            Text("Jeder Durchlauf erzeugt neue Modell-Frames; keine Zoomanimation. Max Realism ist ein Rechenprofil, kein Versprechen für perfekte Gesichter oder Filmqualität. Alle KI-Aufträge laufen nach Modelldownload ohne Netzwerk.")
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
                Text("\(studio.scenes.count) Bilder").font(.caption).foregroundStyle(.secondary)
            }
            if studio.scenes.isEmpty {
                Text("Keine Bilder ausgewählt. Das Programm kann alternativ einen animierten Hintergrund mit deinem Titel erstellen.")
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
                        Label("MP4-Video erstellen", systemImage: "video.badge.checkmark")
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
