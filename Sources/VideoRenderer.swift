import Foundation
import AVFoundation
import CoreGraphics
import CoreVideo
import CoreText

struct RenderJob {
    let images: [CGImage]
    let title: String
    let prompt: String
    let duration: Double
    let format: VideoFormat
    let soundtrack: URL?
}

enum VideoError: LocalizedError {
    case cancelled
    case cannotCreateWriter
    case cannotMakeFrame
    case writerFailed(String)
    case audioMissing
    case exportFailed(String)

    var errorDescription: String? {
        switch self {
        case .cancelled: return "Videoerstellung abgebrochen."
        case .cannotCreateWriter: return "Der MP4-Encoder konnte nicht geöffnet werden."
        case .cannotMakeFrame: return "Ein Videoframe konnte nicht erzeugt werden."
        case .writerFailed(let message): return "Videoencoder: \(message)"
        case .audioMissing: return "Keine lesbare Audiospur in der Musikdatei."
        case .exportFailed(let message): return "Musik-Export fehlgeschlagen: \(message)"
        }
    }
}

enum VideoRenderer {
    static let fps: Int32 = 12

    static func render(job: RenderJob, output: URL, cancellation: RenderCancellation,
                       progress: @escaping (Double) -> Void) throws {
        let fileManager = FileManager.default
        let tempDir = fileManager.temporaryDirectory.appendingPathComponent("aven-\(UUID().uuidString)", isDirectory: true)
        try fileManager.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: tempDir) }
        let silentVideo = tempDir.appendingPathComponent("silent.mp4")
        let (width, height) = job.format.dimensions
        let writer = try AVAssetWriter(outputURL: silentVideo, fileType: .mp4)
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 2_500_000,
                AVVideoExpectedSourceFrameRateKey: Int(fps),
                AVVideoMaxKeyFrameIntervalKey: Int(fps) * 2
            ]
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = false
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32ARGB),
            kCVPixelBufferWidthKey as String: width,
            kCVPixelBufferHeightKey as String: height,
            kCVPixelBufferCGImageCompatibilityKey as String: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
        ])
        guard writer.canAdd(input) else { throw VideoError.cannotCreateWriter }
        writer.add(input)
        guard writer.startWriting() else { throw VideoError.writerFailed(writer.error?.localizedDescription ?? "Unbekannter Fehler") }
        writer.startSession(atSourceTime: .zero)
        let frames = max(1, Int(job.duration * Double(fps)))
        do {
            for frameIndex in 0..<frames {
                if cancellation.isCancelled { throw VideoError.cancelled }
                while !input.isReadyForMoreMediaData {
                    if cancellation.isCancelled { throw VideoError.cancelled }
                    Thread.sleep(forTimeInterval: 0.015)
                    if writer.status == .failed { throw VideoError.writerFailed(writer.error?.localizedDescription ?? "Encoderfehler") }
                }
                guard let pool = adaptor.pixelBufferPool else { throw VideoError.cannotMakeFrame }
                var bufferOptional: CVPixelBuffer?
                let result = CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &bufferOptional)
                guard result == kCVReturnSuccess, let buffer = bufferOptional else { throw VideoError.cannotMakeFrame }
                try paint(job: job, pixelBuffer: buffer,
                          time: Double(frameIndex) / Double(fps), width: width, height: height)
                let presentationTime = CMTime(value: Int64(frameIndex), timescale: fps)
                guard adaptor.append(buffer, withPresentationTime: presentationTime) else {
                    throw VideoError.writerFailed(writer.error?.localizedDescription ?? "Frame konnte nicht angehängt werden")
                }
                if frameIndex % 12 == 0 { progress(Double(frameIndex) / Double(frames) * 0.9) }
            }
        } catch {
            input.markAsFinished()
            writer.cancelWriting()
            throw error
        }
        input.markAsFinished()
        let done = DispatchSemaphore(value: 0)
        writer.finishWriting { done.signal() }
        done.wait()
        guard writer.status == .completed else {
            throw VideoError.writerFailed(writer.error?.localizedDescription ?? "Finalisierung fehlgeschlagen")
        }
        if cancellation.isCancelled { throw VideoError.cancelled }
        progress(0.94)
        if let sound = job.soundtrack {
            let muxed = tempDir.appendingPathComponent("final.mp4")
            try mergeMusic(video: silentVideo, sound: sound, output: muxed, duration: job.duration)
            if cancellation.isCancelled { throw VideoError.cancelled }
            if fileManager.fileExists(atPath: output.path) { try fileManager.removeItem(at: output) }
            try fileManager.copyItem(at: muxed, to: output)
        } else {
            if fileManager.fileExists(atPath: output.path) { try fileManager.removeItem(at: output) }
            try fileManager.copyItem(at: silentVideo, to: output)
        }
        progress(1)
    }

    private static func paint(job: RenderJob, pixelBuffer: CVPixelBuffer,
                              time: Double, width: Int, height: Int) throws {
        CVPixelBufferLockBaseAddress(pixelBuffer, [])
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, []) }
        guard let base = CVPixelBufferGetBaseAddress(pixelBuffer),
              let context = CGContext(data: base, width: width, height: height,
                                      bitsPerComponent: 8,
                                      bytesPerRow: CVPixelBufferGetBytesPerRow(pixelBuffer),
                                      space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Big.rawValue)
        else { throw VideoError.cannotMakeFrame }
        let rect = CGRect(x: 0, y: 0, width: width, height: height)
        context.setFillColor(CGColor(red: 0.055, green: 0.055, blue: 0.09, alpha: 1))
        context.fill(rect)
        if job.images.isEmpty {
            drawProceduralBackground(context, width: width, height: height, time: time, prompt: job.prompt)
        } else {
            let sceneDuration = job.duration / Double(job.images.count)
            let sceneIndex = min(Int(time / sceneDuration), job.images.count - 1)
            let sceneT = time - sceneDuration * Double(sceneIndex)
            let progress = max(0, min(1, sceneT / sceneDuration))
            drawPhoto(job.images[sceneIndex], context: context, width: width, height: height, progress: progress, alpha: 1)
            let fadeLength = min(0.7, sceneDuration * 0.3)
            if sceneIndex + 1 < job.images.count && sceneT > sceneDuration - fadeLength {
                let fade = CGFloat((sceneT - (sceneDuration - fadeLength)) / fadeLength)
                drawPhoto(job.images[sceneIndex + 1], context: context, width: width, height: height,
                          progress: 0, alpha: fade)
            }
        }
        let title = job.title.trimmingCharacters(in: .whitespacesAndNewlines)
        if !title.isEmpty {
            drawTitle(String(title.prefix(38)), context: context, width: width, height: height)
        }
    }

    private static func drawPhoto(_ image: CGImage, context: CGContext,
                                  width: Int, height: Int, progress: Double, alpha: CGFloat) {
        let w = CGFloat(width), h = CGFloat(height)
        let scale = max(w / CGFloat(image.width), h / CGFloat(image.height))
        let zoom = CGFloat(1.03 + 0.12 * progress)
        let drawWidth = CGFloat(image.width) * scale * zoom
        let drawHeight = CGFloat(image.height) * scale * zoom
        let horizontalShift = (drawWidth - w) * CGFloat(progress - 0.5) * 0.18
        context.saveGState()
        context.clip(to: CGRect(x: 0, y: 0, width: w, height: h))
        context.setAlpha(alpha)
        context.draw(image, in: CGRect(x: (w - drawWidth) / 2 - horizontalShift,
                                      y: (h - drawHeight) / 2,
                                      width: drawWidth, height: drawHeight))
        context.restoreGState()
    }

    private static func drawProceduralBackground(_ ctx: CGContext, width: Int, height: Int,
                                                  time: Double, prompt: String) {
        let lower = prompt.lowercased()
        let warm = lower.contains("sonne") || lower.contains("feuer") || lower.contains("sunset")
        let base: [(CGFloat, CGFloat, CGFloat)] = warm
            ? [(0.39, 0.10, 0.23), (0.09, 0.06, 0.20)]
            : [(0.23, 0.10, 0.49), (0.035, 0.08, 0.22)]
        let colors = base.map { CGColor(red: $0.0, green: $0.1, blue: $0.2, alpha: 1) } as CFArray
        let space = CGColorSpaceCreateDeviceRGB()
        if let gradient = CGGradient(colorsSpace: space, colors: colors, locations: [0, 1]) {
            ctx.drawLinearGradient(gradient, start: CGPoint(x: 0, y: CGFloat(height)),
                                   end: .zero, options: [])
        }
        for n in 0..<14 {
            let x = (CGFloat(n * 173 % 977) / 977) * CGFloat(width) + CGFloat(sin(time * 0.16 + Double(n))) * 35
            let y = CGFloat(n * 263 % 997) / 997 * CGFloat(height)
            let radius = 9 + CGFloat(n % 5) * 10 + CGFloat(sin(time * 0.4 + Double(n))) * 2
            ctx.setFillColor(CGColor(red: warm ? 1 : 0.63, green: warm ? 0.42 : 0.48,
                                    blue: warm ? 0.35 : 1, alpha: CGFloat(0.05 + 0.02 * Double(n % 4))))
            ctx.fillEllipse(in: CGRect(x: x - radius, y: y - radius, width: radius * 2, height: radius * 2))
        }
    }

    private static func drawTitle(_ title: String, context: CGContext, width: Int, height: Int) {
        let fontSize = CGFloat(min(width / 19, 47))
        let font = CTFontCreateWithName("HelveticaNeue-Bold" as CFString, fontSize, nil)
        let shadowFont = CTFontCreateWithName("HelveticaNeue-Bold" as CFString, fontSize, nil)
        let shadowAttrs: [NSAttributedString.Key: Any] = [
            NSAttributedString.Key(kCTFontAttributeName as String): shadowFont,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: 0, alpha: 0.7)
        ]
        let attrs: [NSAttributedString.Key: Any] = [
            NSAttributedString.Key(kCTFontAttributeName as String): font,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: 1, alpha: 0.95)
        ]
        let line = CTLineCreateWithAttributedString(NSAttributedString(string: title, attributes: attrs))
        let shadowLine = CTLineCreateWithAttributedString(NSAttributedString(string: title, attributes: shadowAttrs))
        let lineWidth = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
        let x = max(20, (CGFloat(width) - lineWidth) / 2)
        let y = CGFloat(height) * 0.10
        context.saveGState()
        context.textMatrix = .identity
        context.textPosition = CGPoint(x: x + 2, y: y - 2)
        CTLineDraw(shadowLine, context)
        context.textPosition = CGPoint(x: x, y: y)
        CTLineDraw(line, context)
        context.restoreGState()
    }

    private static func mergeMusic(video: URL, sound: URL, output: URL, duration: Double) throws {
        let composition = AVMutableComposition()
        let videoAsset = AVURLAsset(url: video)
        let soundAsset = AVURLAsset(url: sound)
        let clipTime = CMTime(seconds: duration, preferredTimescale: 600)
        guard let sourceVideoTrack = videoAsset.tracks(withMediaType: .video).first,
              let videoTrack = composition.addMutableTrack(withMediaType: .video,
                                                           preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw VideoError.exportFailed("Videospur fehlt")
        }
        try videoTrack.insertTimeRange(CMTimeRange(start: .zero, duration: clipTime), of: sourceVideoTrack, at: .zero)
        videoTrack.preferredTransform = sourceVideoTrack.preferredTransform
        guard let sourceAudioTrack = soundAsset.tracks(withMediaType: .audio).first,
              let audioTrack = composition.addMutableTrack(withMediaType: .audio,
                                                           preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw VideoError.audioMissing
        }
        let audioDuration = soundAsset.duration
        guard audioDuration.isValid && CMTimeCompare(audioDuration, .zero) > 0 else { throw VideoError.audioMissing }
        var cursor = CMTime.zero
        while CMTimeCompare(cursor, clipTime) < 0 {
            let remaining = CMTimeSubtract(clipTime, cursor)
            let segment = CMTimeCompare(audioDuration, remaining) < 0 ? audioDuration : remaining
            try audioTrack.insertTimeRange(CMTimeRange(start: .zero, duration: segment),
                                           of: sourceAudioTrack, at: cursor)
            cursor = CMTimeAdd(cursor, segment)
        }
        guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
            throw VideoError.exportFailed("Export-Sitzung nicht verfügbar")
        }
        exporter.outputURL = output
        exporter.outputFileType = .mp4
        exporter.shouldOptimizeForNetworkUse = true
        let semaphore = DispatchSemaphore(value: 0)
        exporter.exportAsynchronously { semaphore.signal() }
        semaphore.wait()
        guard exporter.status == .completed else {
            throw VideoError.exportFailed(exporter.error?.localizedDescription ?? "Unbekannter Audiofehler")
        }
    }
}
