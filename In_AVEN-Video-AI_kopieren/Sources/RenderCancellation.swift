import Foundation

final class RenderCancellation {
    struct Cancelled: LocalizedError {
        var errorDescription: String? { "Berechnung angehalten. Fertige Szenen bleiben gespeichert." }
    }

    private let lock = NSLock()
    private var cancelled = false
    func cancel() { lock.lock(); cancelled = true; lock.unlock() }
    var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return cancelled }
    /// Atomically publish a completed result only if cancellation has not won.
    /// Callbacks must not call back into this cancellation token.
    func commitIfActive(_ publish: () throws -> Void) rethrows -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard !cancelled else { return false }
        try publish()
        return true
    }
    func check() throws { if isCancelled { throw Cancelled() } }
}
