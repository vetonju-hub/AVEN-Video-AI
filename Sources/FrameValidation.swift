import Foundation
import CoreGraphics
import ImageIO

struct FrameReport: Codable {
    let count: Int
    let width: Int
    let height: Int
    let meanLumaDeviation: Double
    let meanEdgeEnergy: Double
    let meanTemporalDifference: Double
    let warnings: [String]
    let assessment: String
}

/// Integrity checks and diagnostic metrics. No metric here certifies semantic quality.
enum FrameValidation {
    static func inspect(frames: [URL], width: Int, height: Int) throws -> FrameReport {
        guard !frames.isEmpty else { throw GenerationError.invalid("Keine Originalframes gefunden.") }
        var variance = 0.0, edges = 0.0, temporal = 0.0
        var previous: [UInt8]?
        for file in frames {
            try PNGIntegrity.validate(Data(contentsOf: file, options: .mappedIfSafe))
            guard let source = CGImageSourceCreateWithURL(file as CFURL, nil),
                  let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary),
                  CGImageSourceGetStatus(source) == .statusComplete,
                  CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete,
                  image.width == width && image.height == height else {
                throw GenerationError.invalid("Originalframe beschädigt oder falsche Größe: \(file.lastPathComponent). Erwartet \(width)×\(height).")
            }
            let pixels = try lumaAndRGB(image, sampleSize: 64)
            let values = pixels.luma.map(Double.init)
            let mean = values.reduce(0,+) / Double(values.count)
            variance += sqrt(values.map { ($0 - mean) * ($0 - mean) }.reduce(0,+) / Double(values.count))
            let side = pixels.width
            var e = 0.0
            for y in 1..<(pixels.height - 1) {
                for x in 1..<(side - 1) {
                    let k = y * side + x
                    e += abs(4 * values[k] - values[k-1] - values[k+1] - values[k-side] - values[k+side])
                }
            }
            edges += e / Double((side - 2) * (pixels.height - 2))
            if let p = previous {
                temporal += zip(p, pixels.luma).map { abs(Double($0) - Double($1)) }.reduce(0,+) / Double(p.count)
            }
            previous = pixels.luma
        }
        let deviation = variance / Double(frames.count)
        guard deviation >= 1.0 else {
            throw GenerationError.invalid("KI-Ausgabe enthält nur nahezu einfarbige Frames. Ausgabe bleibt zur Diagnose erhalten; kein fertiges Video erstellt.")
        }
        let change = frames.count > 1 ? temporal / Double(frames.count - 1) : 0
        let edge = edges / Double(frames.count)
        var warnings: [String] = []
        if change < 0.15 { warnings.append("Kaum Bewegung; möglicherweise identische Frames.") }
        if edge < 2 { warnings.append("Wenig Bildstruktur; Originalframes auf Unschärfe prüfen.") }
        return FrameReport(count: frames.count, width: width, height: height, meanLumaDeviation: deviation,
            meanEdgeEnergy: edge, meanTemporalDifference: change, warnings: warnings,
            assessment: "Technische Integrität geprüft. Motiv, Schärfe, Rauschen und zeitliche Konsistenz müssen visuell beurteilt werden.")
    }

    static func lumaAndRGB(_ image: CGImage, sampleSize: Int? = nil) throws -> (width: Int, height: Int, luma: [UInt8], rgb: [UInt8]) {
        let w = sampleSize ?? image.width, h = sampleSize ?? image.height
        var bytes = [UInt8](repeating: 0, count: w * h * 4)
        let success = bytes.withUnsafeMutableBytes { raw -> Bool in
            guard let context = CGContext(data: raw.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                space: CGColorSpace(name: CGColorSpace.sRGB)!,
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue | CGBitmapInfo.byteOrder32Big.rawValue) else { return false }
            context.interpolationQuality = .high
            context.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard success else { throw GenerationError.invalid("Frame-Pixel konnten nicht gelesen werden.") }
        var luma = [UInt8](), rgb = [UInt8]()
        luma.reserveCapacity(w * h); rgb.reserveCapacity(w * h * 3)
        for k in stride(from: 0, to: bytes.count, by: 4) {
            let r = bytes[k], g = bytes[k+1], b = bytes[k+2]
            rgb += [r,g,b]
            // Separate concrete Int expressions keep newer macOS SDK overloads
            // from exhausting Swift's type checker. The arithmetic is unchanged.
            let redContribution: Int = Int(r) * 54
            let greenContribution: Int = Int(g) * 183
            let blueContribution: Int = Int(b) * 19
            let weightedLuma: Int = redContribution + greenContribution + blueContribution
            let value: UInt8 = UInt8(weightedLuma / 256)
            luma.append(value)
        }
        return (w, h, luma, rgb)
    }
}
