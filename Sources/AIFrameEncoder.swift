import Foundation
import AVFoundation
import CoreGraphics
import CoreVideo
import ImageIO

/// Encode the original pixels without scaling, interpolation or skipped corrupt frames.
enum AIFrameEncoder {
    struct Continuation {
        let source: URL
        let width: Int
        let height: Int
        let fps: Int
    }

    static func encode(images: [URL], fps: Int, output: URL,
                       cancellation: RenderCancellation = RenderCancellation(),
                       onFrameSubmitted: (Int) -> Void = { _ in }) throws {
        guard images.count >= 2, fps > 0,
              let source = CGImageSourceCreateWithURL(images[0] as CFURL, nil),
              let first = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw GenerationError.invalid("Keine lesbare Folge von KI-Frames.")
        }
        try cancellation.check()
        let w = first.width, h = first.height
        guard w >= 32, h >= 32, w % 2 == 0, h % 2 == 0 else { throw GenerationError.invalid("Ungültige Framegröße.") }
        let temporary = output.deletingLastPathComponent().appendingPathComponent(".encode-\(UUID().uuidString).mp4")
        defer { try? FileManager.default.removeItem(at: temporary) }
        let writer = try AVAssetWriter(outputURL: temporary, fileType: .mp4)
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: w, AVVideoHeightKey: h,
            AVVideoColorPropertiesKey: [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2
            ],
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: max(4_000_000, w * h * fps),
                AVVideoExpectedSourceFrameRateKey: fps,
                AVVideoMaxKeyFrameIntervalKey: fps * 2,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel
            ]
        ])
        input.expectsMediaDataInRealTime = false
        input.mediaTimeScale = Int32(fps)
        let adapter = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA),
            kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h,
            kCVPixelBufferCGImageCompatibilityKey as String: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
        ])
        guard writer.canAdd(input) else { throw GenerationError.invalid("H.264-Encoder nicht verfügbar.") }
        writer.add(input)
        guard writer.startWriting() else { throw writer.error ?? GenerationError.invalid("Encoderstart fehlgeschlagen.") }
        writer.startSession(atSourceTime: .zero)
        do {
            for (index, file) in images.enumerated() {
                try cancellation.check()
                let deadline = Date().addingTimeInterval(60)
                while !input.isReadyForMoreMediaData {
                    try cancellation.check()
                    guard writer.status == .writing, Date() < deadline else {
                        throw writer.error ?? GenerationError.invalid("Encoder wartet zu lange auf Daten.")
                    }
                    Thread.sleep(forTimeInterval: 0.01)
                }
                guard let source = CGImageSourceCreateWithURL(file as CFURL, nil),
                      let image = CGImageSourceCreateImageAtIndex(source, 0, nil), image.width == w, image.height == h else {
                    throw GenerationError.invalid("Frame beschädigt oder falsche Größe: \(file.lastPathComponent)")
                }
                guard let pool = adapter.pixelBufferPool else { throw GenerationError.invalid("Pixelbuffer fehlt.") }
                var optional: CVPixelBuffer?
                guard CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &optional) == kCVReturnSuccess,
                      let buffer = optional else { throw GenerationError.invalid("Nicht genug Speicher für Videoframe.") }
                CVPixelBufferLockBaseAddress(buffer, [])
                guard let base = CVPixelBufferGetBaseAddress(buffer),
                      let context = CGContext(data: base, width: w, height: h, bitsPerComponent: 8,
                        bytesPerRow: CVPixelBufferGetBytesPerRow(buffer), space: CGColorSpace(name: CGColorSpace.sRGB)!,
                        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue) else {
                    CVPixelBufferUnlockBaseAddress(buffer, [])
                    throw GenerationError.invalid("Frame-Kontext konnte nicht angelegt werden.")
                }
                context.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
                CVPixelBufferUnlockBaseAddress(buffer, [])
                guard adapter.append(buffer, withPresentationTime: CMTime(value: Int64(index), timescale: Int32(fps))) else {
                    throw writer.error ?? GenerationError.invalid("Frame konnte nicht geschrieben werden.")
                }
                onFrameSubmitted(index + 1)
            }
            writer.endSession(atSourceTime: CMTime(value: Int64(images.count), timescale: Int32(fps)))
            input.markAsFinished()
            let done = DispatchSemaphore(value: 0)
            writer.finishWriting { done.signal() }
            while done.wait(timeout: .now() + 0.1) == .timedOut { try cancellation.check() }
            try cancellation.check()
            guard writer.status == .completed else { throw writer.error ?? GenerationError.invalid("Videoabschluss fehlgeschlagen.") }
            try validateClip(temporary, expectedDuration: Double(images.count) / Double(fps))
            guard try cancellation.commitIfActive({
                try FileManager.default.moveItem(at: temporary, to: output)
            }) else { throw RenderCancellation.Cancelled() }
        } catch {
            writer.cancelWriting()
            throw error
        }
    }

    static func validateClip(_ url: URL, expectedDuration: Double) throws {
        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        guard asset.isReadable, let track = asset.tracks(withMediaType: .video).first,
              asset.duration.seconds.isFinite,
              abs(track.timeRange.duration.seconds - expectedDuration) < 0.08 else {
            throw GenerationError.invalid("MP4 ist unvollständig oder hat eine falsche Dauer: \(url.lastPathComponent)")
        }
    }

    static func combine(clips: [URL], output: URL, limit: Double, soundtrack: URL?,
                        continuation: Continuation? = nil,
                        cancellation: RenderCancellation = RenderCancellation()) throws {
        _ = try VideoTiming.resolve(manual: limit, music: nil, matchMusic: false)
        try cancellation.check()
        let original = try continuation.map { try MediaImport.continuationAsset($0.source) }
        let added = CMTime(seconds: limit, preferredTimescale: 48_000)
        let cut = original?.range.duration ?? .zero
        let total = CMTimeAdd(cut, added)
        let composition = AVMutableComposition()
        guard let video = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw GenerationError.invalid("Videospur konnte nicht angelegt werden.")
        }
        var videoComposition: AVVideoComposition?
        if let continuation = continuation, let original = original {
            guard let prefix = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {
                throw GenerationError.invalid("Original-Videospur konnte nicht angelegt werden.")
            }
            try prefix.insertTimeRange(original.range, of: original.track, at: .zero)
            let canvas = CGSize(width: continuation.width, height: continuation.height)
            let fitted = try MediaImport.fittedTransform(naturalSize: original.track.naturalSize,
                preferredTransform: original.track.preferredTransform, canvas: canvas)
            let originalInstruction = instruction(for: prefix, transform: fitted, range: CMTimeRange(start: .zero, duration: cut))
            let addedInstruction = instruction(for: video, transform: .identity, range: CMTimeRange(start: cut, duration: added))
            let rendered = AVMutableVideoComposition()
            rendered.renderSize = canvas
            let nominal = Double(original.track.nominalFrameRate)
            let sourceFPS = nominal.isFinite ? Int(min(60, max(0, ceil(nominal)))) : 0
            rendered.frameDuration = CMTime(value: 1, timescale: Int32(max(continuation.fps, sourceFPS)))
            rendered.instructions = [originalInstruction, addedInstruction]
            videoComposition = rendered
        }
        var cursor = cut
        for clip in clips {
            try cancellation.check()
            if CMTimeCompare(cursor, total) >= 0 { break }
            let asset = AVURLAsset(url: clip, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
            guard let source = asset.tracks(withMediaType: .video).first,
                  source.timeRange.duration.seconds.isFinite, source.timeRange.duration.seconds > 0 else {
                throw GenerationError.invalid("Keine Videospur: \(clip.lastPathComponent)")
            }
            let remain = CMTimeSubtract(total, cursor)
            let amount = CMTimeMinimum(source.timeRange.duration, remain)
            try video.insertTimeRange(CMTimeRange(start: source.timeRange.start, duration: amount), of: source, at: cursor)
            if continuation == nil { video.preferredTransform = source.preferredTransform }
            cursor = CMTimeAdd(cursor, amount)
        }
        guard abs(CMTimeSubtract(cursor, total).seconds) < 1.0 / 48_000 else {
            throw GenerationError.invalid("Die fertigen KI-Szenen decken die gewünschte Länge noch nicht vollständig ab.")
        }
        let originalAudio = original?.asset.tracks(withMediaType: .audio).first
        if originalAudio != nil || soundtrack != nil {
            guard let audio = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
                throw GenerationError.invalid("Audiospur konnte nicht angelegt werden.")
            }
            if let source = originalAudio, let original = original {
                let range = CMTimeRangeGetIntersection(source.timeRange, otherRange: original.range)
                if range.duration.seconds > 0 {
                    let offset = CMTimeSubtract(range.start, original.range.start)
                    try audio.insertTimeRange(range, of: source, at: offset)
                }
            }
            if let sound = soundtrack {
                let asset = AVURLAsset(url: sound, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
                guard let source = asset.tracks(withMediaType: .audio).first,
                      source.timeRange.duration.seconds.isFinite, source.timeRange.duration.seconds > 0 else {
                    throw GenerationError.invalid("Musikdatei fehlt oder enthält keine lesbare Audiospur.")
                }
                // The selected music starts at the cut and plays once at its original speed.
                let amount = CMTimeMinimum(added, source.timeRange.duration)
                try audio.insertTimeRange(CMTimeRange(start: source.timeRange.start, duration: amount), of: source, at: cut)
            }
        }
        let temporary = output.deletingLastPathComponent().appendingPathComponent(".combine-\(UUID().uuidString).mp4")
        defer { try? FileManager.default.removeItem(at: temporary) }
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            throw GenerationError.invalid("MP4-Export nicht verfügbar.")
        }
        exporter.outputURL = temporary
        exporter.outputFileType = .mp4
        exporter.timeRange = CMTimeRange(start: .zero, duration: total)
        exporter.videoComposition = videoComposition
        let done = DispatchSemaphore(value: 0)
        exporter.exportAsynchronously { done.signal() }
        while done.wait(timeout: .now() + 0.1) == .timedOut {
            if cancellation.isCancelled { exporter.cancelExport() }
        }
        try cancellation.check()
        guard exporter.status == .completed else { throw exporter.error ?? GenerationError.invalid("MP4-Export fehlgeschlagen.") }
        try validateClip(temporary, expectedDuration: total.seconds)
        guard try cancellation.commitIfActive({
            try FileManager.default.moveItem(at: temporary, to: output)
        }) else { throw RenderCancellation.Cancelled() }
    }

    private static func instruction(for track: AVAssetTrack, transform: CGAffineTransform,
                                    range: CMTimeRange) -> AVMutableVideoCompositionInstruction {
        let layer = AVMutableVideoCompositionLayerInstruction(assetTrack: track)
        layer.setTransform(transform, at: range.start)
        let instruction = AVMutableVideoCompositionInstruction()
        instruction.timeRange = range
        instruction.layerInstructions = [layer]
        return instruction
    }
}
