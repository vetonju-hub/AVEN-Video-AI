import Foundation

/// Check structural completeness and every chunk CRC before handing a generated
/// PNG to ImageIO, whose decoder can otherwise recover pixels from partial files.
enum PNGIntegrity {
    private static let crcTable: [UInt32] = (0..<256).map { value in
        var crc = UInt32(value)
        for _ in 0..<8 { crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xedb88320 : crc >> 1 }
        return crc
    }

    static func validate(_ data: Data) throws {
        let bytes = [UInt8](data)
        func invalid() -> GenerationError { .invalid("Original-PNG ist unvollständig oder seine Prüfsumme ist ungültig.") }
        guard bytes.count >= 45, bytes.prefix(8).elementsEqual([137,80,78,71,13,10,26,10]) else { throw invalid() }
        func word(_ offset: Int) -> UInt32 {
            UInt32(bytes[offset]) << 24 | UInt32(bytes[offset + 1]) << 16 | UInt32(bytes[offset + 2]) << 8 | UInt32(bytes[offset + 3])
        }
        var offset = 8, header = false, pixels = false
        while offset <= bytes.count - 12 {
            let length = Int(word(offset))
            guard length <= bytes.count - offset - 12 else { throw invalid() }
            let typeStart = offset + 4, payloadEnd = offset + 8 + length
            var crc: UInt32 = 0xffffffff
            for i in typeStart..<payloadEnd { crc = (crc >> 8) ^ crcTable[Int((crc ^ UInt32(bytes[i])) & 255)] }
            guard (crc ^ 0xffffffff) == word(payloadEnd) else { throw invalid() }
            let type = String(bytes: bytes[typeStart..<(typeStart + 4)], encoding: .ascii) ?? ""
            if !header { guard type == "IHDR", length == 13 else { throw invalid() }; header = true }
            else if type == "IHDR" { throw invalid() }
            if type == "IDAT" { pixels = true }
            if type == "IEND" {
                guard length == 0, pixels, payloadEnd + 4 == bytes.count else { throw invalid() }
                return
            }
            offset = payloadEnd + 4
        }
        throw invalid()
    }
}
