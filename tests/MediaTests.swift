import Foundation
import AppKit
import AVFoundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import AudioToolbox

@main
struct MediaTests {
    static func main() throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: folder) }
        let w = 64, h = 64
        func image(_ frame: Int, solid: Bool = false) -> CGImage {
            let context = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            context.setFillColor(CGColor(red: 0.8, green: 0.05, blue: 0.05, alpha: 1))
            context.fill(CGRect(x: 0, y: 0, width: w, height: h))
            if !solid {
                context.setFillColor(CGColor(red: 0.05, green: 0.8, blue: 0.05, alpha: 1))
                context.fill(CGRect(x: 0, y: h / 2, width: w, height: h / 2))
                context.setFillColor(CGColor(red: 0.05, green: 0.05, blue: 0.9, alpha: 1))
                context.fill(CGRect(x: frame % 16, y: 10, width: 16, height: 16))
            }
            return context.makeImage()!
        }
        var frames: [URL] = []
        for i in 0..<33 {
            let file = folder.appendingPathComponent(String(format: "generated_%03d.png", i))
            try MediaImport.writePNG(image(i), to: file)
            frames.append(file)
        }
        let report = try FrameValidation.inspect(frames: frames, width: w, height: h)
        precondition(report.count == 33 && report.meanTemporalDifference > 0)
        let first = try MediaImport.decodeImage(frames[0])
        precondition(first.width == w && first.height == h)
        let rotatedJPEG = folder.appendingPathComponent("rotated.jpg")
        let cropped = image(0).cropping(to: CGRect(x: 0, y: 0, width: 64, height: 32))!
        let jpeg = CGImageDestinationCreateWithURL(rotatedJPEG as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(jpeg, cropped, [kCGImagePropertyOrientation: 6] as CFDictionary)
        precondition(CGImageDestinationFinalize(jpeg))
        let oriented = try MediaImport.decodeImage(rotatedJPEG)
        precondition(oriented.width == 32 && oriented.height == 64, "Honor EXIF photo orientation")
        let truncated = folder.appendingPathComponent("truncated.png")
        try Data(try Data(contentsOf: frames[0]).dropLast(24)).write(to: truncated)
        do { _ = try FrameValidation.inspect(frames: [truncated], width: w, height: h); fatalError("truncated image accepted") } catch { }
        let corrupt = folder.appendingPathComponent("bad.png")
        try Data("not a png".utf8).write(to: corrupt)
        do { _ = try FrameValidation.inspect(frames: [corrupt], width: w, height: h); fatalError("corrupt image accepted") } catch { }
        do { _ = try FrameValidation.inspect(frames: frames, width: 32, height: h); fatalError("wrong dimensions accepted") } catch { }
        let solid = folder.appendingPathComponent("solid.png")
        try MediaImport.writePNG(image(0, solid: true), to: solid)
        do { _ = try FrameValidation.inspect(frames: [solid, solid], width: w, height: h); fatalError("blank output accepted") } catch { }
        let cancel = RenderCancellation()
        cancel.cancel()
        do { try AIFrameEncoder.encode(images: frames, fps: 16, output: folder.appendingPathComponent("cancel.mp4"), cancellation: cancel); fatalError("cancel ignored") } catch { }
        let clip = folder.appendingPathComponent("clip.mp4")
        try AIFrameEncoder.encode(images: frames, fps: 16, output: clip, cancellation: RenderCancellation())
        let asset = AVURLAsset(url: clip)
        precondition(abs(asset.duration.seconds - 33.0 / 16.0) < 0.02, "Exact final frame duration is required")
        let reader = try AVAssetReader(asset: asset)
        let track = asset.tracks(withMediaType: .video).first!
        let samples = AVAssetReaderTrackOutput(track: track, outputSettings: nil)
        reader.add(samples); precondition(reader.startReading())
        var count = 0
        while samples.copyNextSampleBuffer() != nil { count += 1 }
        precondition(count == 33, "No decoded frames may silently disappear")
        for invalid in [Double.nan, -1] {
            do { _ = try MediaImport.referenceFromVideo(clip, seconds: invalid); fatalError("invalid reference time accepted") } catch { }
        }
        let generated = try MediaImport.referenceFromVideo(clip, seconds: 0)
        precondition(generated.width == w && generated.height == h)
        // Pixel comparison catches encoder channel swaps and vertical inversion.
        let originalPixels = try FrameValidation.lumaAndRGB(first)
        let roundtrip = try FrameValidation.lumaAndRGB(generated)
        let mae = zip(originalPixels.rgb, roundtrip.rgb).map { abs(Double($0) - Double($1)) }.reduce(0,+) / Double(originalPixels.rgb.count)
        precondition(mae < 22, "Frame roundtrip color/orientation changed: \(mae)")
        let combined = folder.appendingPathComponent("combined.mp4")
        try AIFrameEncoder.combine(clips: [clip, clip], output: combined, limit: 3.375, soundtrack: nil, cancellation: RenderCancellation())
        precondition(abs(AVURLAsset(url: combined).duration.seconds - 3.375) < 0.03)
        do { try AIFrameEncoder.combine(clips: [clip], output: folder.appendingPathComponent("short.mp4"), limit: 10, soundtrack: nil, cancellation: RenderCancellation()); fatalError("short video accepted") } catch { }
        // 5.375 seconds PCM music: preserve its entire duration and fractional end.
        let audio = folder.appendingPathComponent("song.wav")
        try writeWAV(seconds: 5.375, to: audio)
        let audioDuration = try MediaImport.audioDuration(audio)
        precondition(abs(audioDuration - 5.375) < 0.002)
        let withMusic = folder.appendingPathComponent("song-video.mp4")
        try AIFrameEncoder.combine(clips: [clip, clip, clip], output: withMusic, limit: audioDuration, soundtrack: audio, cancellation: RenderCancellation())
        let musicAsset = AVURLAsset(url: withMusic)
        precondition(abs(musicAsset.duration.seconds - audioDuration) < 0.04)
        let musicTrack = musicAsset.tracks(withMediaType: .audio).first!
        precondition(abs(musicTrack.timeRange.duration.seconds - audioDuration) < 0.08)
        try verifyTone(musicAsset, expectedSeconds: audioDuration)
        let manual = folder.appendingPathComponent("manual-longer-than-song.mp4")
        try AIFrameEncoder.combine(clips: [clip, clip, clip], output: manual, limit: 6, soundtrack: audio, cancellation: RenderCancellation())
        let manualAsset = AVURLAsset(url: manual, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        precondition(manualAsset.tracks(withMediaType: .audio).first!.timeRange.duration.seconds < 5.5, "Music must not loop")
        let slideshow = folder.appendingPathComponent("slideshow.mp4")
        try VideoRenderer.render(job: RenderJob(images: [image(0)], title: "test", prompt: "test",
            duration: audioDuration, format: .widescreen, soundtrack: audio), output: slideshow, cancellation: RenderCancellation()) { _ in }
        let slideAsset = AVURLAsset(url: slideshow, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        precondition(abs(slideAsset.duration.seconds - audioDuration) < 0.04, "Slideshow must preserve fractional song end")
        if CommandLine.arguments.count > 1 {
            let fixtures = URL(fileURLWithPath: CommandLine.arguments[1])
            let expected = Double(try String(contentsOf: fixtures.appendingPathComponent("vbr-duration.txt")).trimmingCharacters(in: .whitespacesAndNewlines))!
            let vbr = try MediaImport.audioDuration(fixtures.appendingPathComponent("vbr-no-xing.mp3"))
            precondition(abs(vbr - expected) < 0.04, "VBR MP3 without Xing must use precise duration: \(vbr) vs \(expected)")
        }
        let duringEncode = RenderCancellation()
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.02) { duringEncode.cancel() }
        let interrupted = folder.appendingPathComponent("interrupted.mp4")
        do { try AIFrameEncoder.encode(images: frames, fps: 16, output: interrupted, cancellation: duringEncode); fatalError("encoding cancellation ignored") } catch { }
        precondition(!FileManager.default.fileExists(atPath: interrupted.path), "No partial MP4 may be published")
        print("PASS: 33-frame PNG/MP4 roundtrip, colors/orientation, exact durations, reference extraction, corruption, cancellation, complete music")
    }

    static func verifyTone(_ asset: AVAsset, expectedSeconds: Double) throws {
        let reader = try AVAssetReader(asset: asset)
        let track = asset.tracks(withMediaType: .audio).first!
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
            AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1, AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true, AVLinearPCMIsNonInterleaved: false
        ])
        reader.add(output); precondition(reader.startReading())
        var decoded: [Float] = []
        while let sample = output.copyNextSampleBuffer() {
            guard let block = CMSampleBufferGetDataBuffer(sample) else { continue }
            let count = CMBlockBufferGetDataLength(block)
            var data = Data(count: count)
            let status = data.withUnsafeMutableBytes { CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: count, destination: $0.baseAddress!) }
            precondition(status == noErr)
            data.withUnsafeBytes { decoded.append(contentsOf: $0.bindMemory(to: Float.self)) }
        }
        precondition(reader.status == .completed)
        precondition(abs(Double(decoded.count) / 16_000 - expectedSeconds) < 0.08)
        let tail = Array(decoded.suffix(800))
        let rms = sqrt(tail.map { Double($0 * $0) }.reduce(0,+) / Double(tail.count))
        precondition(rms > 0.03, "Audio content must reach the end")
        let middle = Array(decoded.dropFirst(16_000).prefix(16_000))
        let positiveCrossings = zip(middle, middle.dropFirst()).filter { $0 <= 0 && $1 > 0 }.count
        precondition(abs(positiveCrossings - 440) < 8, "Music pitch/speed changed")
    }

    static func writeWAV(seconds: Double, to url: URL) throws {
        let rate = 16000
        let count = Int(seconds * Double(rate))
        var data = Data()
        func word<T: FixedWidthInteger>(_ n: T) { var v = n.littleEndian; withUnsafeBytes(of: &v) { data.append(contentsOf: $0) } }
        data.append(Data("RIFF".utf8)); word(UInt32(36 + count * 2)); data.append(Data("WAVEfmt ".utf8))
        word(UInt32(16)); word(UInt16(1)); word(UInt16(1)); word(UInt32(rate)); word(UInt32(rate * 2)); word(UInt16(2)); word(UInt16(16))
        data.append(Data("data".utf8)); word(UInt32(count * 2))
        for i in 0..<count { word(Int16(sin(Double(i) * 2 * .pi * 440 / Double(rate)) * 5000)) }
        try data.write(to: url)
    }
}
