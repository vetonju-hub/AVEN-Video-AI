import Foundation
import AppKit
import AVFoundation
import CoreGraphics
import CoreMedia
import ImageIO
import UniformTypeIdentifiers

enum MediaImport {
    /// Decode EXIF orientation before passing pixels to either Vision or Wan.
    static func decodeImage(_ url: URL, maxPixelSize: Int = 4096) throws -> CGImage {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: maxPixelSize,
                kCGImageSourceShouldCacheImmediately: true
              ] as CFDictionary) else {
            throw GenerationError.invalid("Bild kann nicht gelesen werden: \(url.lastPathComponent)")
        }
        return image
    }

    static func writePNG(_ image: CGImage, to url: URL) throws {
        guard let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
            throw GenerationError.invalid("PNG-Datei kann nicht angelegt werden.")
        }
        CGImageDestinationAddImage(destination, image, nil)
        guard CGImageDestinationFinalize(destination) else { throw GenerationError.invalid("PNG konnte nicht gespeichert werden.") }
    }

    static func saveAvatar(from source: URL, to destination: URL) throws -> CGImage {
        let decoded = try decodeImage(source, maxPixelSize: 1920)
        let image = try fittedImage(decoded, width: decoded.width, height: decoded.height)
        guard let bytes = CFDataCreateMutable(nil, 0),
              let writer = CGImageDestinationCreateWithData(bytes, UTType.png.identifier as CFString, 1, nil) else {
            throw GenerationError.invalid("Avatar konnte nicht als PNG vorbereitet werden.")
        }
        CGImageDestinationAddImage(writer, image, nil)
        guard CGImageDestinationFinalize(writer), let pointer = CFDataGetBytePtr(bytes) else {
            throw GenerationError.invalid("Avatar konnte nicht kodiert werden.")
        }
        let png = withExtendedLifetime(bytes) { Data(bytes: pointer, count: CFDataGetLength(bytes)) }
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        try png.write(to: destination, options: .atomic)
        return image
    }

    static func continuationAsset(_ url: URL) throws -> (asset: AVURLAsset, track: AVAssetTrack, range: CMTimeRange) {
        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        let duration = asset.duration
        guard asset.isReadable, duration.seconds.isFinite, duration.seconds > 0,
              let track = asset.tracks(withMediaType: .video).first else {
            throw GenerationError.invalid("Keine lesbare Videospur: \(url.lastPathComponent)")
        }
        var presentation = track.timeRange
        let segments = track.segments
        // An edit list can include empty leading or trailing video segments.
        if segments.first?.isEmpty == true || segments.last?.isEmpty == true {
            guard let first = segments.first(where: { !$0.isEmpty }),
                  let last = segments.last(where: { !$0.isEmpty }) else {
                throw GenerationError.invalid("Das Video enthält keine abspielbaren Bilder: \(url.lastPathComponent)")
            }
            let start = first.timeMapping.target.start
            let end = last.timeMapping.target.end
            let visible = CMTimeRange(start: start, duration: CMTimeSubtract(end, start))
            presentation = CMTimeRangeGetIntersection(presentation, visible)
        }
        let range = CMTimeRangeGetIntersection(presentation, CMTimeRange(start: .zero, duration: duration))
        guard range.duration.seconds.isFinite, range.duration.seconds > 0 else {
            throw GenerationError.invalid("Das Video enthält keine abspielbaren Bilder: \(url.lastPathComponent)")
        }
        _ = try VideoTiming.resolve(manual: range.duration.seconds, music: nil, matchMusic: false)
        return (asset, track, range)
    }

    static func writeContinuationFrames(from url: URL, to directory: URL, width: Int, height: Int, fps: Int,
                                        cancellation: RenderCancellation) throws -> [URL] {
        try cancellation.check()
        guard (1...240).contains(fps) else { throw GenerationError.invalid("Ungültige Bildrate.") }
        let video = try continuationAsset(url)
        let generator = AVAssetImageGenerator(asset: video.asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: width, height: height)
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let count = GenerationPolicy.continuationContextFrames
        let end = video.range.end
        let last = CMTimeSubtract(end, CMTime(value: 1, timescale: max(48_000, end.timescale)))
        let nominalFPS = Double(video.track.nominalFrameRate)
        let sourceStep = nominalFPS.isFinite && nominalFPS > 1 ? 1.0 / nominalFPS : 1.0 / Double(fps)
        let nearbyTolerance = CMTime(seconds: sourceStep, preferredTimescale: 48_000)
        var frames: [URL] = []
        for index in 0..<count {
            try cancellation.check()
            let offset = CMTime(value: Int64(count - 1 - index), timescale: Int32(fps))
            let time = CMTimeMaximum(video.range.start, CMTimeSubtract(last, offset))
            let image: CGImage
            do {
                image = try generator.copyCGImage(at: time, actualTime: nil)
            } catch {
                generator.requestedTimeToleranceBefore = nearbyTolerance
                defer {
                    generator.requestedTimeToleranceBefore = .zero
                    generator.requestedTimeToleranceAfter = .zero
                }
                if let nearby = try? generator.copyCGImage(at: time, actualTime: nil) {
                    image = nearby
                } else {
                    // A sparse variable-rate clip can have no sample near a requested time.
                    generator.requestedTimeToleranceBefore = .positiveInfinity
                    generator.requestedTimeToleranceAfter = CMTime(value: 1, timescale: Int32(fps))
                    image = try generator.copyCGImage(at: time, actualTime: nil)
                }
            }
            let frame = try fittedImage(image, width: width, height: height)
            let file = directory.appendingPathComponent(String(format: "frame_%03d.png", index))
            try writePNG(frame, to: file)
            frames.append(file)
        }
        return frames
    }

    static func fittedTransform(naturalSize: CGSize, preferredTransform: CGAffineTransform, canvas: CGSize) throws -> CGAffineTransform {
        let bounds = CGRect(origin: .zero, size: naturalSize).applying(preferredTransform).standardized
        let fit = try fittedRect(source: bounds.size, canvas: canvas)
        let scale = fit.width / bounds.width
        return preferredTransform
            .concatenating(CGAffineTransform(translationX: -bounds.minX, y: -bounds.minY))
            .concatenating(CGAffineTransform(scaleX: scale, y: scale))
            .concatenating(CGAffineTransform(translationX: fit.minX, y: fit.minY))
    }

    private static func fittedImage(_ image: CGImage, width: Int, height: Int) throws -> CGImage {
        let canvas = CGSize(width: width, height: height)
        let fit = try fittedRect(source: CGSize(width: image.width, height: image.height), canvas: canvas)
        guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
                space: colorSpace, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            throw GenerationError.invalid("Bild konnte nicht für die KI vorbereitet werden.")
        }
        context.setFillColor(CGColor(gray: 0, alpha: 1))
        context.fill(CGRect(origin: .zero, size: canvas))
        context.interpolationQuality = .high
        context.draw(image, in: fit)
        guard let result = context.makeImage() else { throw GenerationError.invalid("Bild konnte nicht erzeugt werden.") }
        return result
    }

    private static func fittedRect(source: CGSize, canvas: CGSize) throws -> CGRect {
        guard source.width.isFinite, source.height.isFinite, source.width > 0, source.height > 0,
              canvas.width.isFinite, canvas.height.isFinite, canvas.width > 0, canvas.height > 0 else {
            throw GenerationError.invalid("Ungültige Video- oder Bildgröße.")
        }
        let scale = min(canvas.width / source.width, canvas.height / source.height)
        let width = source.width * scale
        let height = source.height * scale
        return CGRect(x: (canvas.width - width) / 2, y: (canvas.height - height) / 2, width: width, height: height)
    }

    static func referenceFromVideo(_ url: URL, seconds: Double) throws -> CGImage {
        guard seconds.isFinite, seconds >= 0 else { throw GenerationError.invalid("Referenzzeit muss eine gültige positive Sekundenangabe sein.") }
        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        guard !asset.tracks(withMediaType: .video).isEmpty,
              asset.duration.seconds.isFinite, asset.duration.seconds > 0 else {
            throw GenerationError.invalid("Keine lesbare Videospur: \(url.lastPathComponent)")
        }
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 1920, height: 1920)
        generator.requestedTimeToleranceBefore = CMTime(seconds: 0.05, preferredTimescale: 600)
        generator.requestedTimeToleranceAfter = CMTime(seconds: 0.05, preferredTimescale: 600)
        let time = CMTime(seconds: max(0, min(seconds, max(0, asset.duration.seconds - 0.1))), preferredTimescale: 600)
        return try generator.copyCGImage(at: time, actualTime: nil)
    }

    static func audioDuration(_ url: URL) throws -> Double {
        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        guard let track = asset.tracks(withMediaType: .audio).first else {
            throw GenerationError.invalid("Keine lesbare Audiospur: \(url.lastPathComponent)")
        }
        let seconds = track.timeRange.duration.seconds
        return try VideoTiming.resolve(manual: seconds, music: nil, matchMusic: false)
    }
}
