import Foundation

final class RenderCancellation {
    private let lock = NSLock()
    private var cancelled = false
    func cancel() { lock.lock(); cancelled = true; lock.unlock() }
    var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return cancelled }
    /// Atomically publish a completed result only if cancellation has not won.
    /// Callbacks must not call back into this cancellation token.
    func commitIfActive(_ publish: () -> Void) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard !cancelled else { return false }
        publish()
        return true
    }
    func check() throws { if isCancelled { throw GenerationError.invalid("Berechnung angehalten. Fertige Szenen bleiben gespeichert.") } }
}
