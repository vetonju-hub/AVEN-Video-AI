import Foundation
import AVFoundation
import CoreGraphics
import CoreVideo
import ImageIO

/// Encode the original pixels without scaling, interpolation or skipped corrupt frames.
enum AIFrameEncoder {
    static func encode(images: [URL], fps: Int, output: URL,
                       cancellation: RenderCancellation = RenderCancellation()) throws {
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
            }
            writer.endSession(atSourceTime: CMTime(value: Int64(images.count), timescale: Int32(fps)))
            input.markAsFinished()
            let done = DispatchSemaphore(value: 0)
            writer.finishWriting { done.signal() }
            while done.wait(timeout: .now() + 0.1) == .timedOut { try cancellation.check() }
            try cancellation.check()
            guard writer.status == .completed else { throw writer.error ?? GenerationError.invalid("Videoabschluss fehlgeschlagen.") }
            try validateClip(temporary, expectedDuration: Double(images.count) / Double(fps))
            try FileManager.default.moveItem(at: temporary, to: output)
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
                        cancellation: RenderCancellation = RenderCancellation()) throws {
        _ = try VideoTiming.resolve(manual: limit, music: nil, matchMusic: false)
        try cancellation.check()
        let composition = AVMutableComposition()
        guard let video = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw GenerationError.invalid("Videospur konnte nicht angelegt werden.")
        }
        let total = CMTime(seconds: limit, preferredTimescale: 48_000)
        var cursor = CMTime.zero
        for clip in clips {
            try cancellation.check()
            if CMTimeCompare(cursor, total) >= 0 { break }
            let asset = AVURLAsset(url: clip, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
            guard let source = asset.tracks(withMediaType: .video).first, source.timeRange.duration.seconds > 0 else {
                throw GenerationError.invalid("Keine Videospur: \(clip.lastPathComponent)")
            }
            let remain = CMTimeSubtract(total, cursor)
            let amount = CMTimeMinimum(source.timeRange.duration, remain)
            try video.insertTimeRange(CMTimeRange(start: source.timeRange.start, duration: amount), of: source, at: cursor)
            video.preferredTransform = source.preferredTransform
            cursor = CMTimeAdd(cursor, amount)
        }
        guard abs(cursor.seconds - limit) < 1.0 / 48_000 else {
            throw GenerationError.invalid("Die fertigen KI-Szenen decken die gewünschte Länge noch nicht vollständig ab.")
        }
        if let sound = soundtrack {
            let asset = AVURLAsset(url: sound, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
            guard let source = asset.tracks(withMediaType: .audio).first,
                  let audio = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid),
                  source.timeRange.duration.seconds.isFinite, source.timeRange.duration.seconds > 0 else {
                throw GenerationError.invalid("Musikdatei fehlt oder enthält keine lesbare Audiospur.")
            }
            // Preserve the original speed. No looping; manual videos longer than the song end in silence.
            let amount = CMTimeMinimum(total, source.timeRange.duration)
            try audio.insertTimeRange(CMTimeRange(start: source.timeRange.start, duration: amount), of: source, at: .zero)
        }
        let temporary = output.deletingLastPathComponent().appendingPathComponent(".combine-\(UUID().uuidString).mp4")
        defer { try? FileManager.default.removeItem(at: temporary) }
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            throw GenerationError.invalid("MP4-Export nicht verfügbar.")
        }
        exporter.outputURL = temporary
        exporter.outputFileType = .mp4
        exporter.timeRange = CMTimeRange(start: .zero, duration: total)
        let done = DispatchSemaphore(value: 0)
        exporter.exportAsynchronously { done.signal() }
        while done.wait(timeout: .now() + 0.1) == .timedOut {
            if cancellation.isCancelled { exporter.cancelExport() }
        }
        try cancellation.check()
        guard exporter.status == .completed else { throw exporter.error ?? GenerationError.invalid("MP4-Export fehlgeschlagen.") }
        try validateClip(temporary, expectedDuration: limit)
        try FileManager.default.moveItem(at: temporary, to: output)
    }
}
