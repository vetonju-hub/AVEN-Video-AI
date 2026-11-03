import Foundation
import AppKit
import AVFoundation
import CoreGraphics
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
