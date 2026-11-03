import Foundation
import Metal

@main
struct AdaptiveTests {
    static func main() {
        let intel16 = AVENHardware(architecture: "Intel", cpu: "8 Core", logicalCores: 16,
            memoryGB: 16, gpu: "Intel", metalAvailable: true, appleSilicon: false)
        let arm96 = AVENHardware(architecture: "Apple Silicon", cpu: "16 Core", logicalCores: 16,
            memoryGB: 96, gpu: "Apple", metalAvailable: true, appleSilicon: true)
        for level in 1...10 {
            for machine in [intel16, arm96] {
                let p = AVENQualityPlan.make(for: machine, level: level, portrait: false, fullPower: false)
                assert(p.frames % 4 == 1)
                assert(p.width % 32 == 0 && p.height % 32 == 0)
                assert(p.steps >= 6 && p.threads >= 2)
                assert(p.estimatedSegmentsFor240s >= 1)
                let vertical = AVENQualityPlan.make(for: machine, level: level, portrait: true, fullPower: true)
                assert(vertical.height == p.width && vertical.width == p.height)
                let square = AVENQualityPlan.make(for: machine, level: level, portrait: false, fullPower: false, square: true)
                assert(square.width == square.height)
            }
        }
        let slow = AVENQualityPlan.make(for: intel16, level: 10, portrait: false, fullPower: false)
        let fast = AVENQualityPlan.make(for: intel16, level: 1, portrait: false, fullPower: false)
        assert(slow.steps > fast.steps)
        assert(slow.width >= fast.width)
        assert(slow.backend == "cpu")
        let strong = AVENQualityPlan.make(for: arm96, level: 10, portrait: false, fullPower: true)
        assert(strong.width > slow.width && strong.modelTier.contains("Q8"))
        assert(strong.backend == "metal")
        print("OK: 40 Hardware/Level combinations + quality and backend checks")
    }
}
