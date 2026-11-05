import Foundation

@main
struct AdaptiveTests {
    static func main() {
        for memory in [4, 8, 16, 24, 48, 96, 124] {
            for silicon in [false, true] {
                let machine = AVENHardware(architecture: "test", cpu: "test", logicalCores: 1,
                    memoryGB: memory, gpu: "test", metalAvailable: silicon, appleSilicon: silicon)
                for level in 1...10 {
                    let plan = AVENQualityPlan.make(for: machine, level: level, portrait: false, fullPower: false)
                    let vertical = AVENQualityPlan.make(for: machine, level: level, portrait: true, fullPower: true)
                    let square = AVENQualityPlan.make(for: machine, level: level, portrait: false, fullPower: false, square: true)
                    precondition(CodablePlan(plan).isSupported)
                    precondition(plan.width == vertical.height && plan.height == vertical.width)
                    precondition(square.width == square.height && square.width % 16 == 0)
                    precondition(plan.threads == 1 && plan.steps >= 20 && plan.fps == 16)
                    precondition(plan.backend.contains("metal") == silicon)
                }
            }
        }
        print("PASS: 140 hardware/level profiles in all three formats; single-core thread limits")
    }
}
