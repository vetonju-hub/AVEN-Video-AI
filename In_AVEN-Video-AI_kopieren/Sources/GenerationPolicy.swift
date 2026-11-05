import Foundation

enum GenerationError: LocalizedError {
    case invalid(String)
    var errorDescription: String? { if case .invalid(let reason) = self { return reason }; return nil }
}

enum VideoTiming {
    static func resolve(manual: Double, music: Double?, matchMusic: Bool) throws -> Double {
        let seconds: Double
        if matchMusic {
            guard let song = music else { throw GenerationError.invalid("Bitte zuerst eine lesbare Musikdatei importieren.") }
            seconds = song
        } else { seconds = manual }
        guard seconds.isFinite, seconds > 0, seconds <= 86_400 else {
            throw GenerationError.invalid("Videolänge muss größer als 0 und höchstens 24 Stunden sein.")
        }
        return seconds
    }
    static func frameCount(seconds: Double, fps: Int) throws -> Int {
        _ = try resolve(manual: seconds, music: nil, matchMusic: false)
        guard (1...240).contains(fps) else { throw GenerationError.invalid("Ungültige Bildrate.") }
        return max(1, Int(ceil(seconds * Double(fps))))
    }
    static func sceneCount(seconds: Double, clipSeconds: Double) -> Int {
        guard seconds.isFinite, clipSeconds.isFinite, seconds > 0, seconds <= 86_400, clipSeconds >= 1.0 / 240.0 else { return 0 }
        return Int(ceil(seconds / clipSeconds))
    }
}

struct CodablePlan: Codable {
    let version: Int
    let level: Int
    let steps: Int
    let width: Int
    let height: Int
    let frames: Int
    let fps: Int
    let threads: Int
    let backend: String
    let useQ8: Bool
    let cfg: Double
    let flowShift: Double
    var clipSeconds: Double { Double(frames) / Double(fps) }
    var isSupported: Bool {
        version == 4 && (20...100).contains(steps) && width >= 480 && height >= 480 &&
        width <= 2048 && height <= 2048 && width % 16 == 0 && height % 16 == 0 &&
        frames == 33 && fps == 16 && (1...64).contains(threads) &&
        cfg == 5.0 && flowShift == 16.0 &&
        ["cpu", "diffusion=metal,te=cpu,vae=cpu"].contains(backend)
    }
    init(_ source: AVENQualityPlan) {
        version = 4; level = source.level; steps = source.steps; width = source.width; height = source.height
        frames = source.frames; fps = source.fps; threads = source.threads; backend = source.backend
        useQ8 = source.modelTier.hasPrefix("Q8"); cfg = source.cfg; flowShift = 16.0
    }
    private enum CodingKeys: String, CodingKey {
        case version, level, steps, width, height, frames, fps, threads, backend, useQ8, cfg, flowShift
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        version = try c.decodeIfPresent(Int.self, forKey: .version) ?? 0
        level = try c.decode(Int.self, forKey: .level); steps = try c.decode(Int.self, forKey: .steps)
        width = try c.decode(Int.self, forKey: .width); height = try c.decode(Int.self, forKey: .height)
        frames = try c.decode(Int.self, forKey: .frames); fps = try c.decode(Int.self, forKey: .fps)
        threads = try c.decode(Int.self, forKey: .threads); backend = try c.decode(String.self, forKey: .backend)
        useQ8 = try c.decode(Bool.self, forKey: .useQ8)
        cfg = try c.decodeIfPresent(Double.self, forKey: .cfg) ?? 5.5
        flowShift = try c.decodeIfPresent(Double.self, forKey: .flowShift) ?? 3.0
    }
}

struct AIJobManifest: Codable {
    let version: Int?
    let prompt: String
    let negativePrompt: String?
    let seed: Int64?
    let targetSeconds: Double
    let plan: CodablePlan
    let format: String
    let referenceName: String? // legacy decode only
    let referenceNames: [String]?
    let soundtrackPath: String? // v4 stores a path relative to the job directory
    let avatarName: String?
    let sourceVideoName: String?
    var completed: Int
    let created: Date
    var totalScenes: Int { VideoTiming.sceneCount(seconds: targetSeconds, clipSeconds: plan.clipSeconds) }
    var contextFrameCount: Int { sourceVideoName == nil ? 0 : GenerationPolicy.continuationContextFrames }
    var modelFrameCount: Int { plan.frames + contextFrameCount }

    func reference(at scene: Int) -> String? {
        if let avatarName = avatarName { return avatarName }
        guard scene >= 0 else { return nil }
        let names = referenceNames ?? referenceName.map { [$0] } ?? []
        return names.isEmpty ? nil : names[scene % names.count]
    }

    func controlSource(at scene: Int) -> String? {
        guard let sourceVideoName = sourceVideoName, scene >= 0 else { return nil }
        return scene == 0 ? sourceVideoName : String(format: "scene_%03d/clip.mp4", scene)
    }

    var isSupported: Bool {
        let hasNewInputs = avatarName != nil || sourceVideoName != nil
        let safeSource = sourceVideoName.map {
            URL(fileURLWithPath: $0).lastPathComponent == $0 && ($0 == "source-video" || $0.hasPrefix("source-video."))
        } ?? true
        return version == (hasNewInputs ? 5 : 4) && (avatarName == nil || avatarName == "avatar.png") && safeSource &&
        plan.isSupported && targetSeconds.isFinite && targetSeconds > 0 &&
        targetSeconds <= 86_400 && completed >= 0 && completed <= totalScenes &&
        (seed ?? -1) >= 0 && (seed ?? Int64.max) <= 2_147_483_647
    }
}

enum GenerationPolicy {
    static let continuationContextFrames = 4
    static let defaultNegative = "blurry, out of focus, low quality, noise, flicker, deformed anatomy, bad motion, oversaturated, text, watermark"
    static let smokePrompt = "A ginger cat sitting on a wooden table in a sunlit room. The cat slowly turns its head. Sharp focus, natural colors, static camera."
    static func arguments(plan: CodablePlan, prompt: String, negativePrompt: String, seed: Int64,
                          model: String, textEncoder: String, vae: String, reference: String?, output: String,
                          controlVideo: String? = nil) throws -> [String] {
        guard plan.isSupported else {
            throw GenerationError.invalid("Veraltetes oder ungültiges KI-Profil. Bitte mit dieser App einen neuen Auftrag starten; alte Szenen bleiben erhalten.")
        }
        guard !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw GenerationError.invalid("Bitte eine Szenenbeschreibung eingeben.")
        }
        guard (0...2_147_483_647).contains(seed) else { throw GenerationError.invalid("Seed muss zwischen 0 und 2147483647 liegen.") }
        let frameCount = plan.frames + (controlVideo == nil ? 0 : continuationContextFrames)
        var args = ["-M", "vid_gen", "--diffusion-model", model, "--t5xxl", textEncoder, "--vae", vae,
            "-p", prompt, "-n", negativePrompt, "--video-frames", String(frameCount), "--fps", String(plan.fps),
            "--steps", String(plan.steps), "-W", String(plan.width), "-H", String(plan.height),
            "--cfg-scale", String(plan.cfg), "--flow-shift", String(plan.flowShift),
            "--sampling-method", "euler", "--scheduler", "discrete", "--rng", "cpu", "--auto-fit", "off",
            "--vae-tiling", "--vae-tile-size", "256x256", "--temporal-tiling",
            "--backend", plan.backend, "-t", String(plan.threads), "--seed", String(seed),
            "-v", "-o", output]
        if let image = reference { args += ["-i", image] }
        if let directory = controlVideo { args += ["--control-video", directory] }
        return args
    }
    static func sceneSeed(base: Int64, index: Int) -> Int64 {
        (base + Int64(index) * 9973) % 2_147_483_648
    }
}

enum GeneratedFrameSet {
    static func ordered(files: [URL], expectedCount: Int, droppingFirst: Int = 0) throws -> [URL] {
        let regex = try NSRegularExpression(pattern: #"^generated_([0-9]+)\.png$"#)
        var numbered: [(Int, URL)] = []
        for file in files {
            let name = file.lastPathComponent
            let range = NSRange(name.startIndex..., in: name)
            guard let match = regex.firstMatch(in: name, range: range), let digits = Range(match.range(at: 1), in: name),
                  let n = Int(name[digits]) else { continue }
            numbered.append((n, file))
        }
        numbered.sort { $0.0 < $1.0 }
        guard droppingFirst >= 0, droppingFirst < expectedCount, numbered.count == expectedCount,
              numbered.enumerated().allSatisfy({ $0.offset == $0.element.0 }) else {
            throw GenerationError.invalid("Unvollständige KI-Ausgabe: \(numbered.count) statt \(expectedCount) fortlaufender PNG-Frames. engine.log prüfen.")
        }
        return numbered.dropFirst(droppingFirst).map { $0.1 }
    }
}
