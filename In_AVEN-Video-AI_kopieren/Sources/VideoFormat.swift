import Foundation

enum VideoFormat: String, CaseIterable, Identifiable {
    case widescreen = "16:9"
    case portrait = "9:16"
    case square = "1:1"
    var id: String { rawValue }
    var dimensions: (Int, Int) {
        switch self {
        case .widescreen: return (960, 540)
        case .portrait: return (540, 960)
        case .square: return (720, 720)
        }
    }
}

