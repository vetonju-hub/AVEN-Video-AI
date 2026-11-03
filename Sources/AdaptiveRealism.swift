import Foundation
import Metal

/// The generator never promises a model will fit based solely on physical RAM.
/// It picks a starting point, displays it and lets a failed job be retried at a lower tier.
struct AVENHardware {
    let architecture: String
    let cpu: String
    let logicalCores: Int
    let memoryGB: Int
    let gpu: String
    let metalAvailable: Bool
    let appleSilicon: Bool

    static func detect() -> AVENHardware {
        let appleSilicon: Bool
        #if arch(arm64)
        appleSilicon = true
        #else
        appleSilicon = false
        #endif
        let device = MTLCreateSystemDefaultDevice()
        return AVENHardware(
            architecture: appleSilicon ? "Apple Silicon (arm64)" : "Intel (x86_64)",
            cpu: ProcessInfo.processInfo.processorCount.description + " logische Kerne",
            logicalCores: ProcessInfo.processInfo.activeProcessorCount,
            memoryGB: Int((ProcessInfo.processInfo.physicalMemory + 1_073_741_823) / 1_073_741_824),
            gpu: device?.name ?? "Keine unterstützte Metal-GPU erkannt",
            metalAvailable: device != nil,
            appleSilicon: appleSilicon
        )
    }

    var label: String { "\(architecture) · \(memoryGB) GB RAM · \(gpu)" }
    var performanceClass: Int {
        if appleSilicon && memoryGB >= 64 { return 3 }
        if memoryGB >= 48 { return 2 }
        if appleSilicon && memoryGB >= 24 { return 2 }
        if memoryGB >= 24 { return 1 }
        return 0
    }
}

struct AVENQualityPlan {
    let level: Int
    let steps: Int
    let width: Int
    let height: Int
    let frames: Int // Wan 4n+1
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
    var estimatedSegmentsFor240s: Int { Int(ceil(240.0 / clipSeconds)) }

    static func make(for machine: AVENHardware, level rawLevel: Int, portrait: Bool, fullPower: Bool, square: Bool = false) -> AVENQualityPlan {
        let level = min(10, max(1, rawLevel))
        let category = machine.performanceClass
        // All resolutions are multiples of 32 for video latent compatibility.
        let shortSide: Int
        switch category {
        case 0: shortSide = level <= 3 ? 192 : (level <= 7 ? 256 : 320)
        case 1: shortSide = level <= 3 ? 256 : (level <= 7 ? 320 : 384)
        case 2: shortSide = level <= 3 ? 320 : (level <= 7 ? 384 : 480)
        default: shortSide = level <= 3 ? 384 : (level <= 7 ? 480 : 576)
        }
        let longSide = ((Int(Double(shortSide) * (16.0 / 9.0)) + 16) / 32) * 32
        let width = square ? shortSide : (portrait ? shortSide : longSide)
        let height = square ? shortSide : (portrait ? longSide : shortSide)
        // Explicit quality/performance tradeoff: steps increase, quality NOT guaranteed to increase.
        let steps = [0, 6, 8, 10, 12, 14, 18, 22, 26, 32, 40][level]
        let frames = category == 0 ? (level <= 7 ? 9 : 17) : (level <= 5 ? 17 : 33)
        let fps = 6
        let modelTier = (machine.memoryGB >= 48 && level >= 8) ? "Q8 (höhere Präzision)" : "Q4 (kompakt)"
        let caution = category == 0
            ? "Intel/16 GB: KI-Videodiffusion kann trotz kleiner Auflösung zu langsam sein oder mit Speichermangel scheitern."
            : "Mehr Schritte und Auflösung verbrauchen mehr Speicher; längere Berechnung garantiert keinen Fotorealismus."
        return AVENQualityPlan(level: level, steps: steps, width: width, height: height,
                               frames: frames, fps: fps, cfg: 5.5,
                               threads: max(2, min(fullPower ? machine.logicalCores : machine.logicalCores / 2, 12)),
                               modelTier: modelTier,
                               backend: machine.appleSilicon && machine.metalAvailable ? "metal" : "cpu",
                               caution: caution)
    }
}
