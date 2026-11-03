import Foundation
import AppKit
import SwiftUI
import AVFoundation
import UniformTypeIdentifiers

/// Genuine local Wan VACE video diffusion; only downloading weights ever uses the network.
/// Frames are rendered by the bundled open-source sd-cli engine, never synthesized by zooming photos.
final class AVENLocalAI: NSObject, ObservableObject, URLSessionDownloadDelegate {
    @Published var isDownloading = false
    @Published var isGenerating = false
    @Published var isReady = false
    @Published var highPrecisionReady = false
    @Published var downloadProgress = 0.0
    @Published var message = "Modelle nicht installiert – bitte einmalig herunterladen"
    @Published var resultURL: URL?
    @Published var canResume = false

    private struct Weight {
        let name: String
        let source: String
        let minimumBytes: Int64
        let exactBytes: Int64?
        init(name: String, source: String, minimumBytes: Int64, exactBytes: Int64? = nil) {
            self.name = name
            self.source = source
            self.minimumBytes = minimumBytes
            self.exactBytes = exactBytes
        }
    }
    // Source filenames confirmed against official hosting repositories. Size checks detect HTTP error documents.
    private let q4 = Weight(name: "wan2.1-vace-1.3b-q4_0.gguf",
        source: "https://huggingface.co/calcuis/wan-1.3b-gguf/resolve/main/wan2.1-vace-1.3b-q4_0.gguf",
        minimumBytes: 1_000_000_000, exactBytes: 1_345_134_272)
    private let q8 = Weight(name: "wan2.1-vace-1.3b-q8_0.gguf",
        source: "https://huggingface.co/calcuis/wan-1.3b-gguf/resolve/main/wan2.1-vace-1.3b-q8_0.gguf",
        minimumBytes: 2_000_000_000)
    private let t5Q3 = Weight(name: "umt5-xxl-encoder-Q3_K_S.gguf",
        source: "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q3_K_S.gguf",
        minimumBytes: 2_000_000_000, exactBytes: 2_858_489_696)
    private let t5Q5 = Weight(name: "umt5-xxl-encoder-Q5_K_M.gguf",
        source: "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q5_K_M.gguf",
        minimumBytes: 3_500_000_000)
    private let vae = Weight(name: "wan_2.1_vae.safetensors",
        source: "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
        minimumBytes: 200_000_000, exactBytes: 253_815_318)

    private var downloadSession: URLSession?
    private var downloadItems: [Weight] = []
    private var downloadIndex = 0
    private var downloadTask: URLSessionDownloadTask?
    private var process: Process?
    private var abortRequested = false
    private var currentJob: AIJobManifest?
    private var currentFolder: URL?
    private var lastErrorLines: [String] = []
    private let defaultsKey = "AVEN.v3.lastAIJob"

    private var modelDirectory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("AVEN Video AI/Models", isDirectory: true)
    }
    private var jobsDirectory: URL {
        (FileManager.default.urls(for: .moviesDirectory, in: .userDomainMask).first ?? FileManager.default.homeDirectoryForCurrentUser)
            .appendingPathComponent("AVEN Video AI/KI Aufträge", isDirectory: true)
    }
    private var engine: URL? { Bundle.main.resourceURL?.appendingPathComponent("AIEngine/sd-cli") }

    override init() {
        super.init()
        updateAvailability()
        if let raw = UserDefaults.standard.string(forKey: defaultsKey) {
            let url = URL(fileURLWithPath: raw)
            canResume = FileManager.default.fileExists(atPath: url.appendingPathComponent("job.json").path)
            currentFolder = canResume ? url : nil
        }
    }

    private func sizeOf(_ weight: Weight) -> Int64 {
        let url = modelDirectory.appendingPathComponent(weight.name)
        return (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? NSNumber)?.int64Value ?? 0
    }

    private func ready(_ weight: Weight) -> Bool {
        let bytes = sizeOf(weight)
        if let exact = weight.exactBytes { return bytes == exact }
        return bytes >= weight.minimumBytes
    }

    private func corruptModelDescription() -> String? {
        for weight in [q4, t5Q3, vae] {
            let bytes = sizeOf(weight)
            if bytes > 0 && !ready(weight) {
                let expected = weight.exactBytes.map(String.init) ?? "mindestens \(weight.minimumBytes)"
                return "Modell-Datei unvollständig oder verändert: \(weight.name) (\(bytes) statt \(expected) Bytes). Bitte im Modellordner nur diese Datei löschen und erneut über AVEN herunterladen."
            }
        }
        return nil
    }

    func updateAvailability() {
        isReady = ready(q4) && ready(t5Q3) && ready(vae)
        highPrecisionReady = ready(q8) && ready(t5Q5) && ready(vae)
        if isReady && !isGenerating && !isDownloading {
            message = "Wan VACE Q4 einsatzbereit · KI-Berechnung erfolgt vollständig offline"
        }
    }

    func installModels(useHighPrecision: Bool = false) {
        guard !isDownloading && !isGenerating else { return }
        guard let binary = engine, FileManager.default.isExecutableFile(atPath: binary.path) else {
            message = "KI-Engine fehlt im App-Paket. Bitte den vollständigen v3-Mac-Build installieren."
            return
        }
        do { try FileManager.default.createDirectory(at: modelDirectory, withIntermediateDirectories: true) }
        catch { message = "Modellordner nicht beschreibbar: \(error.localizedDescription)"; return }
        downloadItems = useHighPrecision ? [q8, t5Q5, vae, q4, t5Q3] : [q4, t5Q3, vae]
        downloadIndex = 0
        downloadProgress = 0
        isDownloading = true
        downloadSession = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        nextDownload()
    }

    private func nextDownload() {
        while isDownloading && downloadIndex < downloadItems.count {
            let item = downloadItems[downloadIndex]
            if ready(item) { downloadIndex += 1; continue }
            let remote = URL(string: item.source)!
            message = "Modell \(downloadIndex + 1)/\(downloadItems.count) laden: \(item.name)"
            downloadTask = downloadSession?.downloadTask(with: remote)
            downloadTask?.resume()
            return
        }
        guard isDownloading else { return }
        isDownloading = false
        downloadSession?.finishTasksAndInvalidate()
        downloadSession = nil
        downloadTask = nil
        updateAvailability()
    }

    func stopDownload() {
        isDownloading = false
        downloadTask?.cancel()
        downloadSession?.invalidateAndCancel()
        downloadSession = nil
        message = "Modell-Download gestoppt"
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didWriteData bytesWritten: Int64, totalBytesWritten: Int64,
                    totalBytesExpectedToWrite: Int64) {
        guard totalBytesExpectedToWrite > 0 else { return }
        DispatchQueue.main.async {
            guard self.isDownloading else { return }
            self.downloadProgress = (Double(self.downloadIndex) + Double(totalBytesWritten) / Double(totalBytesExpectedToWrite)) / Double(self.downloadItems.count)
        }
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        guard isDownloading && downloadIndex < downloadItems.count else { return }
        let item = downloadItems[downloadIndex]
        do {
            let status = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
            guard (200...299).contains(status) else { throw NSError(domain: "AVEN", code: status, userInfo: [NSLocalizedDescriptionKey: "HTTP \(status)"]) }
            let bytes = (try FileManager.default.attributesOfItem(atPath: location.path)[.size] as? NSNumber)?.int64Value ?? 0
            guard (item.exactBytes.map { bytes == $0 } ?? (bytes >= item.minimumBytes)) else {
                throw NSError(domain: "AVEN", code: 50, userInfo: [NSLocalizedDescriptionKey: "Modell ist unvollständig oder verändert: \(item.name) (\(bytes) Bytes)"])
            }
            let target = modelDirectory.appendingPathComponent(item.name)
            if FileManager.default.fileExists(atPath: target.path) { try FileManager.default.removeItem(at: target) }
            try FileManager.default.moveItem(at: location, to: target)
            DispatchQueue.main.async { self.downloadIndex += 1; self.nextDownload() }
        } catch {
            DispatchQueue.main.async { self.failDownload(error.localizedDescription) }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error = error else { return }
        DispatchQueue.main.async { if self.isDownloading { self.failDownload(error.localizedDescription) } }
    }
    private func failDownload(_ reason: String) {
        isDownloading = false
        downloadSession?.invalidateAndCancel()
        downloadSession = nil
        message = "Modelldownload fehlgeschlagen: \(reason)"
    }

    func generateAdaptive(firstImage: CGImage?, prompt: String, format: VideoFormat,
                          soundtrack: URL?, plan: AVENQualityPlan, targetSeconds: Double) {
        guard !isDownloading && !isGenerating else { return }
        updateAvailability()
        guard isReady else { message = corruptModelDescription() ?? "Bitte erst KI-Modelle herunterladen."; return }
        guard let engine = engine, FileManager.default.isExecutableFile(atPath: engine.path) else {
            message = "KI-Engine fehlt. Bitte den vollständigen Installer bauen."; return
        }
        let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { message = "Bitte eine englische Szenenbeschreibung eingeben."; return }
        if targetSeconds > 30 && AVENHardware.detect().memoryGB <= 16 {
            message = "Langer CPU-Auftrag gestartet. Je nach Modell kann die Berechnung viele Tage dauern. Jede fertige Szene bleibt gespeichert."
        }
        let folder = jobsDirectory.appendingPathComponent("Job-\(Int(Date().timeIntervalSince1970))", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let imageName: String?
            if let cg = firstImage {
                let url = folder.appendingPathComponent("reference.png")
                let rep = NSBitmapImageRep(cgImage: cg)
                guard let png = rep.representation(using: .png, properties: [:]) else {
                    throw NSError(domain: "AVEN", code: 3, userInfo: [NSLocalizedDescriptionKey: "Referenzbild nicht lesbar"])
                }
                try png.write(to: url)
                imageName = "reference.png"
            } else { imageName = nil }
            let manifest = AIJobManifest(prompt: text, targetSeconds: min(240, max(2, targetSeconds)),
                plan: CodablePlan(plan), format: format.rawValue, referenceName: imageName,
                soundtrackPath: soundtrack?.path, completed: 0, created: Date())
            try save(manifest, to: folder)
            currentJob = manifest
            currentFolder = folder
            UserDefaults.standard.set(folder.path, forKey: defaultsKey)
            canResume = true
            abortRequested = false
            isGenerating = true
            resultURL = nil
            launchNextScene()
        } catch { message = "Auftrag konnte nicht angelegt werden: \(error.localizedDescription)" }
    }

    func resumeLastJob() {
        guard !isGenerating && !isDownloading else { return }
        guard let folder = currentFolder,
              let data = try? Data(contentsOf: folder.appendingPathComponent("job.json")),
              let job = try? JSONDecoder().decode(AIJobManifest.self, from: data) else {
            message = "Kein gespeicherter KI-Auftrag gefunden"
            return
        }
        guard isReady else { message = "Zuerst Modelle herunterladen"; return }
        currentJob = job
        abortRequested = false
        isGenerating = true
        launchNextScene()
    }

    private func launchNextScene() {
        guard !abortRequested, let job = currentJob, let folder = currentFolder,
              let engine = engine else {
            isGenerating = false
            return
        }
        let total = Int(ceil(job.targetSeconds / job.plan.clipSeconds))
        if job.completed >= total { finalize(job: job, folder: folder); return }
        let index = job.completed
        let segmentFolder = folder.appendingPathComponent(String(format: "scene_%03d", index + 1), isDirectory: true)
        do { try FileManager.default.createDirectory(at: segmentFolder, withIntermediateDirectories: true) }
        catch { isGenerating = false; message = "Szenenordner fehlgeschlagen"; return }
        // Explicit printf placeholder forces sd-cli to save each new model-generated frame as PNG.
        // Without it, sd-cli writes a single AVI file which this pipeline does not decode.
        let base = segmentFolder.appendingPathComponent("generated_%03d.png").path
        var args = ["-M", "vid_gen", "--diffusion-model", modelDirectory.appendingPathComponent(job.plan.useQ8 && ready(q8) ? q8.name : q4.name).path,
            "--t5xxl", modelDirectory.appendingPathComponent(job.plan.useQ8 && ready(t5Q5) ? t5Q5.name : t5Q3.name).path,
            "--vae", modelDirectory.appendingPathComponent(vae.name).path,
            "-p", job.prompt + ", realistic natural movement, consistent lighting, detailed cinematic motion, shot " + String(index + 1),
            "-n", "flicker, blurry faces, deformed anatomy, oversaturated, bad motion, artifacts, text, watermark",
            "--video-frames", String(job.plan.frames), "--steps", String(job.plan.steps),
            "-W", String(job.plan.width), "-H", String(job.plan.height),
            "--cfg-scale", "5.5", "--flow-shift", "3.0", "--sampling-method", "euler",
            "--vae-tiling", "--backend", job.plan.backend,
            "-t", String(job.plan.threads), "--seed", String(10000 + index * 9973),
            "-v", "-o", base]
        if let name = job.referenceName { args += ["-i", folder.appendingPathComponent(name).path] }
        // Low-RAM mode uses parameter streaming from disk. This can be extremely slow,
        // but it lowers resident model weight usage. It does not guarantee the model fits.
        if AVENHardware.detect().memoryGB <= 16 && job.plan.backend == "cpu" {
            args += ["--params-backend", "disk"]
        }
        let proc = Process()
        proc.executableURL = engine
        proc.currentDirectoryURL = segmentFolder
        proc.arguments = args
        let sceneNumber = index + 1
        message = "KI Szene \(sceneNumber)/\(total) läuft. Vollständiges engine.log wird im Szenenordner gespeichert."
        let logURL = segmentFolder.appendingPathComponent("engine.log")
        let header = "AVEN KI Diagnose\nArchitektur: \(AVENHardware.detect().architecture), RAM: \(AVENHardware.detect().memoryGB) GB\n" +
            "Modellgroessen (Bytes): VACE=\(sizeOf(q4)), UMT5=\(sizeOf(t5Q3)), VAE=\(sizeOf(vae))\n" +
            "Backend=\(job.plan.backend), Aufloesung=\(job.plan.width)x\(job.plan.height), Frames=\(job.plan.frames)\n" +
            "Ausfuehrbare Datei: \(engine.path)\n--- CLI-Ausgabe ---\n"
        do {
            try Data(header.utf8).write(to: logURL, options: .atomic)
            let logHandle = try FileHandle(forWritingTo: logURL)
            logHandle.seekToEndOfFile()
            // Save both stdout and stderr, including the IMPORTANT errors before
            // the generic 'new_sd_ctx_t failed' trailer. No Terminal is required.
            proc.standardOutput = logHandle
            proc.standardError = logHandle
            proc.terminationHandler = { [weak self] finished in
                try? logHandle.close()
                DispatchQueue.main.async {
                    self?.finishScene(status: finished.terminationStatus, job: job, folder: folder, segmentFolder: segmentFolder)
                }
            }
            try proc.run()
            process = proc
        } catch {
            isGenerating = false
            message = "KI-Start fehlgeschlagen: \(error.localizedDescription). Fehlerprotokoll im Szenenordner."
        }
    }

    private func finishScene(status: Int32, job: AIJobManifest, folder: URL, segmentFolder: URL) {
        process = nil
        if abortRequested { isGenerating = false; message = "Angehalten. Bisherige KI-Szenen gespeichert. Über 'Fortsetzen' weiter."; return }
        guard status == 0 else {
            isGenerating = false
            let logURL = segmentFolder.appendingPathComponent("engine.log")
            let lines = ((try? String(contentsOf: logURL, encoding: .utf8)) ?? "").components(separatedBy: .newlines)
            let matches = lines.filter { line in
                let l = line.lowercased()
                return l.contains("error") || l.contains("failed") || l.contains("out of memory") ||
                    l.contains("unsupported") || l.contains("invalid") || l.contains("not enough")
            }
            // The final new_sd_ctx_t failure is generic, so display the preceding specific error.
            let detail = matches.reversed().first { !$0.contains("new_sd_ctx_t failed") } ?? matches.last ?? "Keine Detailmeldung gefunden"
            message = "KI-Fehler \(status): \(String(detail.prefix(160))). 'Szenenordner anzeigen' > scene_001 > engine.log öffnen und den Fehlertext senden."
            return
        }
        let urls = ((try? FileManager.default.contentsOfDirectory(at: segmentFolder, includingPropertiesForKeys: nil)) ?? [])
        let frames = urls.filter { $0.pathExtension.lowercased() == "png" && $0.lastPathComponent != "reference.png" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        let videos = urls.filter { $0.pathExtension.lowercased() == "mp4" }
        let clipURL = segmentFolder.appendingPathComponent("clip.mp4")
        DispatchQueue.global(qos: .utility).async {
            do {
                if frames.count >= 2 {
                    try AIFrameEncoder.encode(images: frames, fps: job.plan.fps, output: clipURL)
                } else if let source = videos.first(where: { $0 != clipURL }) {
                    try FileManager.default.copyItem(at: source, to: clipURL)
                } else {
                    throw NSError(domain: "AVEN", code: 24, userInfo: [NSLocalizedDescriptionKey: "Keine Videoframes erzeugt; CLI-Ausgabe überprüfen"])
                }
                DispatchQueue.main.async {
                    var updated = job
                    updated.completed += 1
                    self.currentJob = updated
                    do { try self.save(updated, to: folder) }
                    catch { self.message = "Szenenindex konnte nicht gesichert werden: \(error.localizedDescription)"; self.isGenerating = false; return }
                    self.message = "KI-Szene \(updated.completed) gespeichert · nächste Szene wird berechnet"
                    self.launchNextScene()
                }
            } catch { DispatchQueue.main.async { self.isGenerating = false; self.message = "KI-Clip konnte nicht kodiert werden: \(error.localizedDescription)" } }
        }
    }

    private func finalize(job: AIJobManifest, folder: URL) {
        message = "Alle Szenen fertig – echtes KI-Video wird zusammengesetzt"
        let clips = (1...job.completed).map { folder.appendingPathComponent(String(format: "scene_%03d/clip.mp4", $0)) }
        let output = folder.appendingPathComponent("AVEN_KI_FERTIG.mp4")
        if FileManager.default.fileExists(atPath: output.path) {
            isGenerating = false
            resultURL = output
            message = "Bereits fertig: " + output.lastPathComponent
            return
        }
        DispatchQueue.global(qos: .utility).async {
            do {
                try AIFrameEncoder.combine(clips: clips, output: output, limit: job.targetSeconds,
                    soundtrack: job.soundtrackPath.map { URL(fileURLWithPath: $0) })
                DispatchQueue.main.async {
                    self.isGenerating = false
                    self.resultURL = output
                    self.message = "Fertig: KI-Video liegt in 'KI Aufträge' – " + output.lastPathComponent
                }
            } catch { DispatchQueue.main.async { self.isGenerating = false; self.message = "Clips gespeichert; Zusammenfügen fehlgeschlagen: \(error.localizedDescription)" } }
        }
    }

    private func save(_ job: AIJobManifest, to folder: URL) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let bytes = try encoder.encode(job)
        try bytes.write(to: folder.appendingPathComponent("job.json"), options: .atomic)
    }

    func cancelGeneration() {
        abortRequested = true
        if let p = process, p.isRunning { p.terminate() }
        else { isGenerating = false }
        message = "Anhalten angefordert. Fertige Szenen bleiben gespeichert."
    }
    func showResult() {
        if let output = resultURL { NSWorkspace.shared.activateFileViewerSelecting([output]) }
    }
    func showWorkFolder() {
        let path = currentFolder ?? jobsDirectory
        NSWorkspace.shared.open(path)
    }
}

struct CodablePlan: Codable {
    let level: Int
    let steps: Int
    let width: Int
    let height: Int
    let frames: Int
    let fps: Int
    let threads: Int
    let backend: String
    let useQ8: Bool
    var clipSeconds: Double { Double(frames) / Double(fps) }
    init(_ source: AVENQualityPlan) {
        level = source.level; steps = source.steps; width = source.width; height = source.height
        frames = source.frames; fps = source.fps; threads = source.threads; backend = source.backend
        useQ8 = source.modelTier.hasPrefix("Q8")
    }
}

struct AIJobManifest: Codable {
    let prompt: String
    let targetSeconds: Double
    let plan: CodablePlan
    let format: String
    let referenceName: String?
    let soundtrackPath: String?
    var completed: Int
    let created: Date
}
