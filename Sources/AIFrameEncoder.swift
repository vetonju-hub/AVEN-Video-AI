import Foundation
import AVFoundation
import CoreGraphics
import CoreVideo
import AppKit

/// Writes the model's actual generated frames into a video (no pan/zoom interpolation).
enum AIFrameEncoder {
    static func encode(images: [URL], fps: Int, output: URL) throws {
        guard images.count >= 2 else { throw NSError(domain: "AVEN", code: 1, userInfo: [NSLocalizedDescriptionKey: "Mindestens zwei KI-Frames nötig"]) }
        let first = NSImage(contentsOf: images[0])?.cgImage(forProposedRect: nil, context: nil, hints: nil)
        guard let cgFirst = first else { throw NSError(domain: "AVEN", code: 2, userInfo: [NSLocalizedDescriptionKey: "KI-Bild ist beschädigt"]) }
        let w = (max(32, cgFirst.width) / 2) * 2
        let h = (max(32, cgFirst.height) / 2) * 2
        let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: w, AVVideoHeightKey: h,
            AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 2_500_000]
        ])
        input.expectsMediaDataInRealTime = false
        let adapter = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32ARGB),
            kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h,
            kCVPixelBufferCGImageCompatibilityKey as String: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
        ])
        guard writer.canAdd(input) else { throw NSError(domain: "AVEN", code: 3, userInfo: [NSLocalizedDescriptionKey: "Encoder nicht verfügbar"]) }
        writer.add(input)
        guard writer.startWriting() else { throw writer.error ?? NSError(domain: "AVEN", code: 4) }
        writer.startSession(atSourceTime: .zero)
        for (index, imageURL) in images.enumerated() {
            guard let image = NSImage(contentsOf: imageURL)?.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
            while !input.isReadyForMoreMediaData {
                Thread.sleep(forTimeInterval: 0.025)
                if writer.status == .failed { throw writer.error ?? NSError(domain: "AVEN", code: 5) }
            }
            guard let pool = adapter.pixelBufferPool else { throw NSError(domain: "AVEN", code: 6) }
            var bufferOptional: CVPixelBuffer?
            guard CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &bufferOptional) == kCVReturnSuccess,
                  let buffer = bufferOptional else { throw NSError(domain: "AVEN", code: 7) }
            CVPixelBufferLockBaseAddress(buffer, [])
            guard let base = CVPixelBufferGetBaseAddress(buffer),
                  let ctx = CGContext(data: base, width: w, height: h, bitsPerComponent: 8,
                    bytesPerRow: CVPixelBufferGetBytesPerRow(buffer), space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Big.rawValue) else {
                CVPixelBufferUnlockBaseAddress(buffer, [])
                throw NSError(domain: "AVEN", code: 8)
            }
            ctx.setFillColor(CGColor(gray: 0, alpha: 1))
            ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
            CVPixelBufferUnlockBaseAddress(buffer, [])
            guard adapter.append(buffer, withPresentationTime: CMTime(value: Int64(index), timescale: Int32(fps))) else {
                throw writer.error ?? NSError(domain: "AVEN", code: 9)
            }
        }
        input.markAsFinished()
        let semaphore = DispatchSemaphore(value: 0)
        writer.finishWriting { semaphore.signal() }
        semaphore.wait()
        guard writer.status == .completed else { throw writer.error ?? NSError(domain: "AVEN", code: 10) }
    }

    static func combine(clips: [URL], output: URL, limit: Double, soundtrack: URL?) throws {
        let composition = AVMutableComposition()
        guard let videoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw NSError(domain: "AVEN", code: 30)
        }
        let total = CMTime(seconds: limit, preferredTimescale: 600)
        var cursor = CMTime.zero
        for clip in clips {
            guard CMTimeCompare(cursor, total) < 0 else { break }
            let asset = AVURLAsset(url: clip)
            guard let source = asset.tracks(withMediaType: .video).first else { throw NSError(domain: "AVEN", code: 31, userInfo: [NSLocalizedDescriptionKey: "Keine Videospur: \(clip.lastPathComponent)"]) }
            let remain = CMTimeSubtract(total, cursor)
            let amount = CMTimeCompare(asset.duration, remain) > 0 ? remain : asset.duration
            try videoTrack.insertTimeRange(CMTimeRange(start: .zero, duration: amount), of: source, at: cursor)
            videoTrack.preferredTransform = source.preferredTransform
            cursor = CMTimeAdd(cursor, amount)
        }
        if let sound = soundtrack, FileManager.default.fileExists(atPath: sound.path),
           let audioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
            let asset = AVURLAsset(url: sound)
            if let track = asset.tracks(withMediaType: .audio).first, CMTimeCompare(asset.duration, .zero) > 0 {
                var position = CMTime.zero
                while CMTimeCompare(position, cursor) < 0 {
                    let left = CMTimeSubtract(cursor, position)
                    let part = CMTimeCompare(asset.duration, left) > 0 ? left : asset.duration
                    try audioTrack.insertTimeRange(CMTimeRange(start: .zero, duration: part), of: track, at: position)
                    position = CMTimeAdd(position, part)
                }
            }
        }
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            throw NSError(domain: "AVEN", code: 32)
        }
        exporter.outputURL = output
        exporter.outputFileType = .mp4
        let sem = DispatchSemaphore(value: 0)
        exporter.exportAsynchronously { sem.signal() }
        sem.wait()
        guard exporter.status == .completed else { throw exporter.error ?? NSError(domain: "AVEN", code: 33) }
    }
}
