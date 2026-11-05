import Foundation
#if canImport(Metal)
import Metal
#endif

struct AVENHardware {
    let architecture: String
    let cpu: String
    let logicalCores: Int
    let memoryGB: Int
    let gpu: String
    let metalAvailable: Bool
    let appleSilicon: Bool

    static func detect() -> AVENHardware {
        #if arch(arm64)
        let appleSilicon = true
        let architecture = "Apple Silicon (arm64)"
        #else
        let appleSilicon = false
        let architecture = "Intel (x86_64)"
        #endif
        #if canImport(Metal)
        let device = MTLCreateSystemDefaultDevice()
        let gpu = device?.name ?? "Keine unterstützte Metal-GPU erkannt"
        let metal = device != nil
        #else
        let gpu = "CPU"
        let metal = false
        #endif
        return AVENHardware(architecture: architecture,
            cpu: "\(ProcessInfo.processInfo.processorCount) logische Kerne",
            logicalCores: ProcessInfo.processInfo.activeProcessorCount,
            memoryGB: Int((ProcessInfo.processInfo.physicalMemory + 1_073_741_823) / 1_073_741_824),
            gpu: gpu, metalAvailable: metal, appleSilicon: appleSilicon)
    }
    var label: String { "\(architecture) · \(memoryGB) GB RAM · \(gpu)" }
}

/// Quality is selected by the user. Hardware changes execution, never the requested
/// resolution, precision, steps or timing. Matching seeds are not bit-identical across backends.
struct AVENQualityPlan {
    let level: Int
    let steps: Int
    let width: Int
    let height: Int
    let frames: Int
    let fps: Int
    let cfg: Double
    let threads: Int
    let modelTier: String
    let backend: String
    let caution: String
    var clipSeconds: Double { Double(frames) / Double(fps) }
    var shortDescription: String {
        "\(width)×\(height) · \(frames) KI-Frames · \(steps) Schritte · \(fps) FPS · \(modelTier)"
    }
    var estimatedSegmentsFor240s: Int { VideoTiming.sceneCount(seconds: 240, clipSeconds: clipSeconds) }

    static func make(for machine: AVENHardware, level rawLevel: Int, portrait: Bool,
                     fullPower: Bool, square: Bool = false) -> AVENQualityPlan {
        let level = min(10, max(1, rawLevel))
        // VACE is trained at 480p/720p. Tiny 352x192/6-step jobs are not a usable quality preset.
        let shortSide = level >= 8 ? 576 : 480
        let longSide = level >= 8 ? 1024 : 832
        let width = square ? (level >= 8 ? 768 : 640) : (portrait ? shortSide : longSide)
        let height = square ? width : (portrait ? longSide : shortSide)
        let steps = [0, 20, 22, 24, 26, 28, 32, 36, 40, 44, 50][level]
        let caution: String
        if machine.memoryGB < 8 {
            caution = "Weniger als 8 GB RAM: Dieses Wan-Modell wird hier nicht gestartet. Mehr Speicher oder ein anderes Modell ist nötig."
        } else if machine.memoryGB <= 16 {
            caution = "8–16 GB: 480p kann sehr langsam sein oder an Speichermangel scheitern. Erst den 2-Sekunden-Test ausführen; Stufe 8–10 benötigt deutlich mehr Speicher."
        } else {
            caution = "Mehr Schritte und höhere Präzision erhöhen den Aufwand. Erkennbare Motive und Fotorealismus müssen im Ergebnis geprüft werden."
        }
        return AVENQualityPlan(level: level, steps: steps, width: width, height: height,
            frames: 33, fps: 16, cfg: 5.0,
            threads: max(1, min(fullPower ? machine.logicalCores : max(1, machine.logicalCores / 2), 16)),
            modelTier: level >= 8 ? "Q8 + UMT5 Q5 (höhere Präzision)" : "Q4 + UMT5 Q3 (kompakt)",
            backend: machine.appleSilicon && machine.metalAvailable ? "diffusion=metal,te=cpu,vae=cpu" : "cpu",
            caution: caution)
    }
}
