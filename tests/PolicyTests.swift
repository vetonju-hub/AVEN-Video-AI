import Foundation

@main
struct PolicyTests {
    static func main() throws {
        let intel = AVENHardware(architecture: "Intel", cpu: "i9", logicalCores: 16, memoryGB: 16,
                                 gpu: "AMD", metalAvailable: true, appleSilicon: false)
        let arm = AVENHardware(architecture: "ARM", cpu: "M", logicalCores: 24, memoryGB: 96,
                               gpu: "Apple", metalAvailable: true, appleSilicon: true)
        for level in 1...10 {
            let a = AVENQualityPlan.make(for: intel, level: level, portrait: false, fullPower: false)
            let b = AVENQualityPlan.make(for: arm, level: level, portrait: false, fullPower: true)
            precondition(a.steps >= 20 && a.width >= 832 && a.height >= 480, "No unusable low-step/tiny preset")
            precondition(a.steps == b.steps && a.width == b.width && a.frames == b.frames && a.modelTier == b.modelTier,
                         "Hardware must not silently lower quality")
            precondition(a.fps == 16 && a.frames == 33 && a.frames % 4 == 1)
            let p = CodablePlan(a)
            let args = try GenerationPolicy.arguments(plan: p, prompt: "a cat; $(literal)", negativePrompt: "blur",
                seed: 42, model: "/models/wan.gguf", textEncoder: "/models/t5.gguf", vae: "/models/vae", reference: "/with spaces/ref.png", output: "/out/generated_%03d.png")
            func value(_ flag: String) -> String { args[args.firstIndex(of: flag)! + 1] }
            precondition(value("--flow-shift") == "16.0" && value("--fps") == "16")
            precondition(value("--cfg-scale") == "5.0" && value("--steps") == String(a.steps))
            precondition(value("-p") == "a cat; $(literal)" && value("--seed") == "42")
            precondition(value("-i") == "/with spaces/ref.png" && value("--scheduler") == "discrete")
            precondition(!args.contains("disk"), "Don't force untested disk streaming")
        }
        let songLength = try VideoTiming.resolve(manual: 2, music: 301.375, matchMusic: true)
        precondition(songLength == 301.375)
        let manualLength = try VideoTiming.resolve(manual: 45, music: 301, matchMusic: false)
        precondition(manualLength == 45)
        for value in [0.0, -1, Double.nan, Double.infinity] {
            do { _ = try VideoTiming.resolve(manual: value, music: nil, matchMusic: false); fatalError("invalid duration accepted") }
            catch { }
        }
        do { _ = try VideoTiming.resolve(manual: 2, music: nil, matchMusic: true); fatalError("missing music accepted") } catch { }
        precondition(VideoTiming.sceneCount(seconds: Double.greatestFiniteMagnitude, clipSeconds: 2) == 0)
        let gate = RenderCancellation()
        let queue = DispatchQueue(label: "aven-completion-race-test")
        let hold = DispatchSemaphore(value: 0)
        var published = false
        queue.async(execute: DispatchWorkItem { hold.wait() })
        queue.async(execute: DispatchWorkItem { gate.cancel() })
        queue.async(execute: DispatchWorkItem { _ = gate.commitIfActive { published = true } })
        hold.signal(); queue.sync { }
        precondition(!published, "Cancellation queued before result publication must win")
        let liveGate = RenderCancellation()
        precondition(liveGate.commitIfActive { published = true } && published)
        let legacyFrameCount = try VideoTiming.frameCount(seconds: 5.375, fps: 12)
        precondition(legacyFrameCount == 65, "Fractional music needs a final partial video frame")
        let files = ["generated_010.png", "reference.png", "generated_002.png", "generated_001.png", "generated_000.png"]
        do { _ = try GeneratedFrameSet.ordered(files: files.map { URL(fileURLWithPath: $0) }, expectedCount: 11); fatalError("missing frames accepted") } catch { }
        let ordered = try GeneratedFrameSet.ordered(files: ["generated_002.png", "generated_000.png", "generated_001.png", "preview.png"].map { URL(fileURLWithPath: $0) }, expectedCount: 3)
        precondition(ordered.map(\.lastPathComponent) == ["generated_000.png", "generated_001.png", "generated_002.png"])
        let plan = AVENQualityPlan.make(for: intel, level: 5, portrait: false, fullPower: false)
        precondition(VideoTiming.sceneCount(seconds: 301.375, clipSeconds: plan.clipSeconds) == 147)
        let validPNG = Data(base64Encoded: "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGP4z8DAAMIM/4EAAB/uBfsL2WiLAAAAAElFTkSuQmCC")!
        try PNGIntegrity.validate(validPNG)
        do { try PNGIntegrity.validate(Data(validPNG.dropLast(12))); fatalError("PNG without IEND accepted") } catch { }
        var damagedPNG = validPNG
        damagedPNG[45] ^= 1
        do { try PNGIntegrity.validate(damagedPNG); fatalError("PNG CRC corruption accepted") } catch { }
        let legacyJSON = #"{"level":1,"steps":6,"width":352,"height":192,"frames":9,"fps":6,"threads":8,"backend":"cpu","useQ8":false}"#
        let old = try JSONDecoder().decode(CodablePlan.self, from: Data(legacyJSON.utf8))
        precondition(!old.isSupported, "Old broken jobs must not continue silently")
        print("PASS: quality parity (20 hardware/level profiles), CLI, long/fractional timing, numeric frames, legacy-job rejection")
    }
}
