import Foundation
import AppKit
import SwiftUI
import AVFoundation
import UniformTypeIdentifiers
import CryptoKit

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
        let expectedSHA256: String?
        let requiredTensor: String?
        init(name: String, source: String, minimumBytes: Int64,
             exactBytes: Int64? = nil, expectedSHA256: String? = nil,
             requiredTensor: String? = nil) {
            self.name = name
            self.source = source
            self.minimumBytes = minimumBytes
            self.exactBytes = exactBytes
            self.expectedSHA256 = expectedSHA256
            self.requiredTensor = requiredTensor
        }
    }
    // GGUF variant V3 includes the VACE patch-embedding tensor required by
    // stable-diffusion.cpp. The older v1 GGUF had 1263 tensors and caused
    // "model.diffusion_model.vace_patch_embedding.weight not in model metadata".
    // New filenames preserve the old downloaded model for safe rollback.
    // Source SHA256 values were published on the Hugging Face file pages.
    private let q4 = Weight(name: "wan2.1-v3-vace-1.3b-q4_0.gguf",
        source: "https://huggingface.co/calcuis/wan-1.3b-gguf/resolve/0652f175f44055eb60cca26dd7cd89c14abe22ce/wan2.1-v3-vace-1.3b-q4_0.gguf",
        minimumBytes: 1_250_000_000, exactBytes: 1_346_314_016,
        expectedSHA256: "c9d2ad33427cef0e485c0c32b105c3cca8a33f6bfd8249b41b9685756aed4a74",
        requiredTensor: "vace_patch_embedding.weight")
    private let q8 = Weight(name: "wan2.1-v3-vace-1.3b-q8_0.gguf",
        source: "https://huggingface.co/calcuis/wan-1.3b-gguf/resolve/0652f175f44055eb60cca26dd7cd89c14abe22ce/wan2.1-v3-vace-1.3b-q8_0.gguf",
        minimumBytes: 2_000_000_000, exactBytes: 2_370_469_664,
        expectedSHA256: "ac0dcf0f1dd271352be972ce4b425e994a061cc0c650410dcd8d9fdf7f4940dc",
        requiredTensor: "vace_patch_embedding.weight")
    private let t5Q3 = Weight(name: "umt5-xxl-encoder-Q3_K_S.gguf",
        source: "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7/umt5-xxl-encoder-Q3_K_S.gguf",
        minimumBytes: 2_000_000_000, exactBytes: 2_858_489_696,
        expectedSHA256: "f64f8d6dc4d8a24276df69d0ccea789aae686f7417950a41e6568c30cb478a5c")
    private let t5Q5 = Weight(name: "umt5-xxl-encoder-Q5_K_M.gguf",
        source: "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7/umt5-xxl-encoder-Q5_K_M.gguf",
        minimumBytes: 3_500_000_000, exactBytes: 4_145_878_880,
        expectedSHA256: "eaea358bb438c5d211721a4feecc162000e3636e9cb96f51e216f1f44ebd12ce")
    private let vae = Weight(name: "wan_2.1_vae.safetensors",
        source: "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/123acf1cc74bccbb9bfff8ac1ee72edc08c2341d/split_files/vae/wan_2.1_vae.safetensors",
        minimumBytes: 200_000_000, exactBytes: 253_815_318,
        expectedSHA256: "2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b")

    private var downloadSession: URLSession?
    private var downloadItems: [Weight] = []
    private var downloadIndex = 0
    private var downloadTask: URLSessionDownloadTask?
    private var process: Process?
    private var abortRequested = false
    private var cancellation = RenderCancellation()
    private var operationID = UUID()
    private var backgroundWork = false
    private var currentJob: AIJobManifest?
    private var currentFolder: URL?
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

    /// Fast GGUF header preflight. This is NOT a full model-inference test;
    /// it prevents a known-invalid VACE checkpoint from being selected.
    private func headerContainsRequiredTensor(_ url: URL, name: String?) -> Bool {
        guard let name = name else { return true }
        guard let reader = try? FileHandle(forReadingFrom: url) else { return false }
        defer { try? reader.close() }
        guard let header = try? reader.read(upToCount: 8 * 1024 * 1024),
              header.starts(with: [0x47, 0x47, 0x55, 0x46]) else { return false }
        return header.range(of: Data(name.utf8)) != nil
    }

    /// Verify each selected weight after download and before a job starts.
    /// Stream data in chunks instead of loading gigabytes into RAM.
    private func verifyDownloadedChecksum(_ url: URL, expected: String?) throws -> Bool {
        guard let expected = expected else { return true }
        let reader = try FileHandle(forReadingFrom: url)
        defer { try? reader.close() }
        var checksum = SHA256()
        while true {
            let chunk = try reader.read(upToCount: 4 * 1024 * 1024) ?? Data()
            if chunk.isEmpty { break }
            checksum.update(data: chunk)
        }
        let actual = checksum.finalize().map { String(format: "%02x", $0) }.joined()
        return actual.lowercased() == expected.lowercased()
    }

    private func ready(_ weight: Weight) -> Bool {
        let bytes = sizeOf(weight)
        if let exact = weight.exactBytes {
            guard bytes == exact else { return false }
        } else {
            guard bytes >= weight.minimumBytes else { return false }
        }
        let modelURL = modelDirectory.appendingPathComponent(weight.name)
        return headerContainsRequiredTensor(modelURL, name: weight.requiredTensor)
    }

    private func corruptModelDescription() -> String? {
        for weight in [q4, t5Q3, vae] {
            let bytes = sizeOf(weight)
            if bytes > 0 && !ready(weight) {
                let expected = weight.exactBytes.map(String.init) ?? "mindestens \(weight.minimumBytes)"
                return "Modelldatei ungültig: \(weight.name) (\(bytes) Bytes; erwartet \(expected) und gültige Tensor-Metadaten). Bitte diese Datei im Modellordner löschen und das V3-Modell erneut herunterladen."
            }
        }
        return nil
    }

    func updateAvailability() {
        isReady = ready(q4) && ready(t5Q3) && ready(vae)
        highPrecisionReady = ready(q8) && ready(t5Q5) && ready(vae)
        if !isGenerating && !isDownloading {
            if isReady {
                message = "Wan VACE V3 gefunden · vollständige Prüfsummenprüfung erfolgt vor dem Start"
            } else if FileManager.default.fileExists(atPath:
                modelDirectory.appendingPathComponent("wan2.1-vace-1.3b-q4_0.gguf").path) {
                message = "Altes VACE-Modell erkannt (fehlender vace_patch_embedding-Tensor). Bitte über 'Kostenlose KI-Modelle herunterladen' das korrigierte V3-Modell laden. Die alten Dateien bleiben erhalten."
            }
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
            guard session === self.downloadSession, downloadTask === self.downloadTask, self.isDownloading else { return }
            self.downloadProgress = (Double(self.downloadIndex) + Double(totalBytesWritten) / Double(totalBytesExpectedToWrite)) / Double(self.downloadItems.count)
        }
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        let selected: Weight? = DispatchQueue.main.sync {
            guard session === self.downloadSession, downloadTask === self.downloadTask,
                  self.isDownloading, self.downloadIndex < self.downloadItems.count else { return nil }
            return self.downloadItems[self.downloadIndex]
        }
        guard let item = selected else { return }
        do {
            let status = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
            guard (200...299).contains(status) else { throw GenerationError.invalid("HTTP \(status)") }
            let bytes = (try FileManager.default.attributesOfItem(atPath: location.path)[.size] as? NSNumber)?.int64Value ?? 0
            guard (item.exactBytes.map { bytes == $0 } ?? (bytes >= item.minimumBytes)),
                  headerContainsRequiredTensor(location, name: item.requiredTensor),
                  try verifyDownloadedChecksum(location, expected: item.expectedSHA256) else {
                throw GenerationError.invalid("Modelldatei unvollständig oder Prüfsumme/Tensor-Metadaten ungültig: \(item.name)")
            }
            // URLSession deletes its temporary URL when this delegate returns.
            let staged = modelDirectory.appendingPathComponent(".download-" + UUID().uuidString)
            try FileManager.default.moveItem(at: location, to: staged)
            DispatchQueue.main.async {
                defer { try? FileManager.default.removeItem(at: staged) }
                guard session === self.downloadSession, downloadTask === self.downloadTask, self.isDownloading else { return }
                do {
                    let target = self.modelDirectory.appendingPathComponent(item.name)
                    if FileManager.default.fileExists(atPath: target.path) { try FileManager.default.removeItem(at: target) }
                    try FileManager.default.moveItem(at: staged, to: target)
                    self.downloadIndex += 1
                    self.nextDownload()
                } catch { self.failDownload(error.localizedDescription) }
            }
        } catch {
            DispatchQueue.main.async {
                guard session === self.downloadSession, downloadTask === self.downloadTask else { return }
                self.failDownload(error.localizedDescription)
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error = error else { return }
        DispatchQueue.main.async {
            guard session === self.downloadSession, task === self.downloadTask, self.isDownloading else { return }
            self.failDownload(error.localizedDescription)
        }
    }
    private func failDownload(_ reason: String) {
        isDownloading = false
        downloadSession?.invalidateAndCancel()
        downloadSession = nil
        message = "Modelldownload fehlgeschlagen: \(reason)"
    }

    func generateAdaptive(references: [CGImage], prompt: String, negativePrompt: String,
                          seed: Int64, format: VideoFormat, soundtrack: URL?,
                          plan: AVENQualityPlan, targetSeconds: Double, avatar: CGImage? = nil, sourceVideo: URL? = nil) {
        guard !isDownloading && !isGenerating else { return }
        updateAvailability()
        guard isReady else { message = corruptModelDescription() ?? "Bitte erst KI-Modelle herunterladen."; return }
        guard let engine = engine, FileManager.default.isExecutableFile(atPath: engine.path) else {
            message = "KI-Engine fehlt. Bitte den vollständigen Installer bauen."; return
        }
        let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { message = "Bitte eine englische Szenenbeschreibung eingeben."; return }
        guard AVENHardware.detect().memoryGB >= 8 else {
            message = "Dieses Wan-Modell benötigt mindestens 8 GB RAM; auch damit ist ein erfolgreicher Lauf nicht garantiert."
            return
        }
        let policy = CodablePlan(plan)
        guard policy.isSupported, (0...2_147_483_647).contains(seed),
              targetSeconds.isFinite, targetSeconds > 0, targetSeconds <= 86_400 else {
            message = "Ungültige Länge, Seed oder Qualitätsstufe."; return
        }
        guard !policy.useQ8 || highPrecisionReady else {
            message = "Diese Stufe benötigt Q8 und UMT5 Q5. Bitte das Qualitätsmodell nachladen; keine automatische Herabstufung."
            return
        }
        let folder = jobsDirectory.appendingPathComponent("Job-\(UUID().uuidString)", isDirectory: true)
        operationID = UUID()
        let id = operationID
        cancellation = RenderCancellation()
        let token = cancellation
        abortRequested = false
        isGenerating = true
        backgroundWork = true
        resultURL = nil
        message = "Auftrag vorbereiten und Modell-Prüfsummen kontrollieren …"
        DispatchQueue.global(qos: .utility).async {
            do {
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                var imageNames: [String] = []
                if avatar == nil {
                    for (i, image) in references.enumerated() {
                        try token.check()
                        let name = String(format: "reference_%03d.png", i)
                        try MediaImport.writePNG(image, to: folder.appendingPathComponent(name))
                        imageNames.append(name)
                    }
                }
                var avatarName: String?
                if let avatar = avatar {
                    try token.check()
                    let name = "avatar.png"
                    try MediaImport.writePNG(avatar, to: folder.appendingPathComponent(name))
                    avatarName = name
                }
                var sourceVideoName: String?
                if let sourceVideo = sourceVideo {
                    try token.check()
                    let file = sourceVideo.resolvingSymlinksInPath()
                    let name = file.pathExtension.isEmpty ? "source-video" : "source-video." + file.pathExtension
                    let snapshot = folder.appendingPathComponent(name)
                    try FileManager.default.copyItem(at: file, to: snapshot)
                    try token.check()
                    _ = try MediaImport.continuationAsset(snapshot)
                    sourceVideoName = name
                }
                var audioName: String?
                if let sound = soundtrack {
                    _ = try MediaImport.audioDuration(sound)
                    let name = "soundtrack." + sound.pathExtension
                    try FileManager.default.copyItem(at: sound, to: folder.appendingPathComponent(name))
                    audioName = name
                }
                try token.check()
                try self.verifyModels(useQ8: policy.useQ8, cancellation: token)
                let version = avatarName == nil && sourceVideoName == nil ? 4 : 5
                let manifest = AIJobManifest(version: version, prompt: text, negativePrompt: negativePrompt, seed: seed,
                    targetSeconds: targetSeconds, plan: policy, format: format.rawValue, referenceName: nil,
                    referenceNames: imageNames, soundtrackPath: audioName, avatarName: avatarName,
                    sourceVideoName: sourceVideoName, completed: 0, created: Date())
                try self.save(manifest, to: folder)
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.currentJob = manifest
                    self.currentFolder = folder
                    UserDefaults.standard.set(folder.path, forKey: self.defaultsKey)
                    self.canResume = true
                    if token.isCancelled { self.isGenerating = false; self.message = "Angehalten. Auftrag gespeichert."; return }
                    self.launchNextScene()
                }
            } catch {
                // The folder is unique to this attempt. A failed preparation has no resumable manifest.
                if !FileManager.default.fileExists(atPath: folder.appendingPathComponent("job.json").path) {
                    try? FileManager.default.removeItem(at: folder)
                }
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    self.message = "Auftrag nicht gestartet: \(error.localizedDescription)"
                }
            }
        }
    }

    private func verifyModels(useQ8: Bool, cancellation: RenderCancellation) throws {
        for weight in [useQ8 ? q8 : q4, useQ8 ? t5Q5 : t5Q3, vae] {
            try cancellation.check()
            guard ready(weight), try verifyDownloadedChecksum(modelDirectory.appendingPathComponent(weight.name), expected: weight.expectedSHA256) else {
                throw GenerationError.invalid("Modelldatei fehlt oder Prüfsumme ungültig: \(weight.name). Datei im Modellordner prüfen und erneut laden.")
            }
        }
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
        guard AVENHardware.detect().memoryGB >= 8 else { message = "Mindestens 8 GB RAM für dieses Modell erforderlich."; return }
        guard job.isSupported else {
            message = "Dieser Auftrag verwendet veraltete Einstellungen. Bitte einen neuen Auftrag starten; die bisherigen Dateien bleiben erhalten."
            return
        }
        guard !job.plan.backend.contains("metal") || AVENHardware.detect().appleSilicon else {
            message = "Dieser Auftrag benötigt Apple Silicon. Auf diesem Mac bitte neu starten."; return
        }
        guard !job.plan.useQ8 || highPrecisionReady else { message = "Q8 und UMT5 Q5 für diesen Auftrag nachladen."; return }
        currentJob = job
        abortRequested = false
        cancellation = RenderCancellation()
        let token = cancellation
        operationID = UUID()
        let id = operationID
        isGenerating = true
        backgroundWork = true
        resultURL = nil
        message = "Gespeicherte Szenen und Modelle werden geprüft …"
        DispatchQueue.global(qos: .utility).async {
            do {
                for name in job.referenceNames ?? [] {
                    try token.check()
                    _ = try MediaImport.decodeImage(folder.appendingPathComponent(name))
                }
                try token.check()
                if let name = job.avatarName { _ = try MediaImport.decodeImage(folder.appendingPathComponent(name)) }
                if let name = job.sourceVideoName { _ = try MediaImport.continuationAsset(folder.appendingPathComponent(name)) }
                if let name = job.soundtrackPath { _ = try MediaImport.audioDuration(folder.appendingPathComponent(name)) }
                try self.verifyModels(useQ8: job.plan.useQ8, cancellation: token)
                for index in 0..<job.completed {
                    try token.check()
                    let clip = folder.appendingPathComponent(String(format: "scene_%03d/clip.mp4", index + 1))
                    try AIFrameEncoder.validateClip(clip, expectedDuration: job.plan.clipSeconds)
                }
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    if token.isCancelled { self.isGenerating = false; self.message = "Angehalten."; return }
                    self.launchNextScene()
                }
            } catch {
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    self.message = "Fortsetzen fehlgeschlagen: \(error.localizedDescription)"
                }
            }
        }
    }

    private func launchNextScene() {
        guard !abortRequested, let job = currentJob, let folder = currentFolder,
              let engine = engine else {
            isGenerating = false
            return
        }
        let total = job.totalScenes
        if job.completed >= total { finalize(job: job, folder: folder); return }
        let index = job.completed
        let segmentFolder = folder.appendingPathComponent(String(format: "scene_%03d", index + 1), isDirectory: true)
        let selectedModel = job.plan.useQ8 ? q8 : q4
        let selectedText = job.plan.useQ8 ? t5Q5 : t5Q3
        let token = cancellation
        let id = operationID
        backgroundWork = true
        if job.sourceVideoName != nil { message = "Videobilder für KI-Szene \(index + 1)/\(total) vorbereiten …" }
        DispatchQueue.global(qos: .utility).async {
            do {
                try token.check()
                // Retry only the unfinished scene; archive its partial output for diagnostics.
                if FileManager.default.fileExists(atPath: segmentFolder.path) {
                    let archive = folder.appendingPathComponent(segmentFolder.lastPathComponent + "-interrupted-" + UUID().uuidString)
                    try FileManager.default.moveItem(at: segmentFolder, to: archive)
                }
                try FileManager.default.createDirectory(at: segmentFolder, withIntermediateDirectories: true)
                var reference = job.reference(at: index).map { folder.appendingPathComponent($0).path }
                if let ref = reference, !FileManager.default.fileExists(atPath: ref) {
                    throw GenerationError.invalid("Gespeichertes Referenzbild fehlt.")
                }
                var controlVideo: String?
                if let controlSource = job.controlSource(at: index) {
                    let directory = segmentFolder.appendingPathComponent("control", isDirectory: true)
                    let frames = try MediaImport.writeContinuationFrames(from: folder.appendingPathComponent(controlSource), to: directory,
                        width: job.plan.width, height: job.plan.height, fps: job.plan.fps, cancellation: token)
                    if reference == nil { reference = frames.last?.path }
                    controlVideo = directory.path
                }
                try token.check()
                let args = try GenerationPolicy.arguments(plan: job.plan, prompt: job.prompt,
                    negativePrompt: job.negativePrompt ?? GenerationPolicy.defaultNegative,
                    seed: GenerationPolicy.sceneSeed(base: job.seed ?? 42, index: index),
                    model: self.modelDirectory.appendingPathComponent(selectedModel.name).path,
                    textEncoder: self.modelDirectory.appendingPathComponent(selectedText.name).path,
                    vae: self.modelDirectory.appendingPathComponent(self.vae.name).path, reference: reference,
                    output: segmentFolder.appendingPathComponent("generated_%03d.png").path, controlVideo: controlVideo)
                let json = try JSONSerialization.data(withJSONObject: ["executable": engine.path, "arguments": args], options: [.prettyPrinted, .sortedKeys])
                try json.write(to: segmentFolder.appendingPathComponent("command.json"))
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    if token.isCancelled { self.isGenerating = false; self.message = "Angehalten. Auftrag gespeichert."; return }
                    self.startScene(job: job, folder: folder, segmentFolder: segmentFolder, engine: engine, args: args,
                        selectedModel: selectedModel, selectedText: selectedText)
                }
            } catch {
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    self.message = "Szene nicht gestartet: \(error.localizedDescription)"
                }
            }
        }
    }

    private func startScene(job: AIJobManifest, folder: URL, segmentFolder: URL, engine: URL, args: [String],
                            selectedModel: Weight, selectedText: Weight) {
        let id = operationID
        let proc = Process()
        proc.executableURL = engine
        proc.currentDirectoryURL = segmentFolder
        proc.arguments = args
        message = "KI Szene \(job.completed + 1)/\(job.totalScenes) läuft. Vollständiges engine.log wird im Szenenordner gespeichert."
        let logURL = segmentFolder.appendingPathComponent("engine.log")
        let header = "AVEN KI Diagnose\nArchitektur: \(AVENHardware.detect().architecture), RAM: \(AVENHardware.detect().memoryGB) GB\n" +
            "Modell: \(selectedModel.name), Textencoder: \(selectedText.name)\n" +
            "Modellgroessen (Bytes): VACE=\(sizeOf(selectedModel)), UMT5=\(sizeOf(selectedText)), VAE=\(sizeOf(vae))\n" +
            "Schritte=\(job.plan.steps), CFG=\(job.plan.cfg), Flow-Shift=\(job.plan.flowShift), FPS=\(job.plan.fps)\n" +
            "Engine-Revision: \((try? String(contentsOf: engine.deletingLastPathComponent().appendingPathComponent("upstream-commit.txt"), encoding: .utf8)) ?? "unbekannt")\n" +
            "Backend=\(job.plan.backend), Aufloesung=\(job.plan.width)x\(job.plan.height), Frames=\(job.modelFrameCount), Kontextframes=\(job.contextFrameCount)\n" +
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
                    guard let self = self, self.operationID == id else { return }
                    self.finishScene(status: finished.terminationStatus, job: job, folder: folder, segmentFolder: segmentFolder)
                }
            }
            try proc.run()
            process = proc
        } catch {
            process = nil
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
            message = "KI-Fehler \(status): \(String(detail.prefix(160))). 'Szenenordner anzeigen' > aktuelle Szene > engine.log öffnen und den Fehlertext senden."
            return
        }
        let token = cancellation
        let id = operationID
        backgroundWork = true
        message = "Originalframes prüfen und Vorschau kodieren …"
        DispatchQueue.global(qos: .utility).async {
            do {
                try token.check()
                let files = try FileManager.default.contentsOfDirectory(at: segmentFolder, includingPropertiesForKeys: nil)
                let frames = try GeneratedFrameSet.ordered(files: files, expectedCount: job.modelFrameCount,
                    droppingFirst: job.contextFrameCount)
                let report = try FrameValidation.inspect(frames: frames, width: job.plan.width, height: job.plan.height)
                let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                try encoder.encode(report).write(to: segmentFolder.appendingPathComponent("frame-report.json"), options: .atomic)
                let clip = segmentFolder.appendingPathComponent("clip.mp4")
                try AIFrameEncoder.encode(images: frames, fps: job.plan.fps, output: clip, cancellation: token)
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    guard !token.isCancelled else { self.isGenerating = false; self.message = "Angehalten; Originalframes bleiben erhalten."; return }
                    var updated = job
                    updated.completed += 1
                    do { try self.save(updated, to: folder) }
                    catch { self.message = "Szenenindex konnte nicht gesichert werden: \(error.localizedDescription)"; self.isGenerating = false; return }
                    self.currentJob = updated
                    self.launchNextScene()
                }
            } catch {
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    self.message = "KI-Ausgabe nicht übernommen: \(error.localizedDescription). Originalframes und engine.log bleiben im Szenenordner."
                }
            }
        }
    }

    private func finalize(job: AIJobManifest, folder: URL) {
        let continuation = job.sourceVideoName.map {
            AIFrameEncoder.Continuation(source: folder.appendingPathComponent($0), width: job.plan.width,
                height: job.plan.height, fps: job.plan.fps)
        }
        message = continuation == nil ? "Szenen werden zur Vorschau mit Musik zusammengesetzt …" : "Originalvideo und Fortsetzung werden als MP4 exportiert …"
        let clips = (1...job.completed).map { folder.appendingPathComponent(String(format: "scene_%03d/clip.mp4", $0)) }
        let output = folder.appendingPathComponent(continuation == nil ? "AVEN_KI_VORSCHAU.mp4" : "AVEN_FORTSETZUNG.mp4")
        let token = cancellation
        let id = operationID
        backgroundWork = true
        DispatchQueue.global(qos: .utility).async {
            do {
                try token.check()
                if FileManager.default.fileExists(atPath: output.path) {
                    let originalSeconds = try continuation.map { try MediaImport.continuationAsset($0.source).range.duration.seconds } ?? 0
                    try AIFrameEncoder.validateClip(output, expectedDuration: originalSeconds + job.targetSeconds)
                } else {
                    try AIFrameEncoder.combine(clips: clips, output: output, limit: job.targetSeconds,
                        soundtrack: job.soundtrackPath.map { folder.appendingPathComponent($0) },
                        continuation: continuation, cancellation: token)
                }
                try token.check()
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    let published = token.commitIfActive {
                        self.resultURL = output
                        self.message = continuation == nil
                            ? "Vorschau erstellt. Bitte Originalframes und Video auf erkennbare Motive, Schärfe und Bewegung prüfen. frame-report.json bestätigt nur technische Integrität."
                            : "MP4 erstellt: Originalvideo und KI-Fortsetzung. Bitte den Übergang und die neuen Szenen prüfen."
                    }
                    if !published { self.message = "Angehalten. Vorschau und Szenen bleiben im Auftragsordner erhalten." }
                }
            } catch {
                DispatchQueue.main.async {
                    guard self.operationID == id else { return }
                    self.backgroundWork = false
                    self.isGenerating = false
                    self.message = "Zusammensetzen nicht abgeschlossen: \(error.localizedDescription). Fertige Szenen bleiben gespeichert."
                }
            }
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
        cancellation.cancel()
        if let p = process, p.isRunning { p.terminate() }
        else if !backgroundWork { isGenerating = false }
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
