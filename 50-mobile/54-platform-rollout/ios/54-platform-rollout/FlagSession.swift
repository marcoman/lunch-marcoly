import Combine
import Foundation
import LaunchDarkly

/// Mobile SDK session for a platform-staggered release.
/// The device sends platform=ios. A targeting rule decides the variation.
/// https://launchdarkly.com/docs/home/flags/target-with-rules
/// https://launchdarkly.com/docs/sdk/client-side/ios
final class FlagSession: ObservableObject {
    static let flagKey = "enable-mobile-platform-rollout"
    static let eventKey = "mobile_platform_rollout_move"
    static let platform = "ios"

    @Published var released: Bool = false
    @Published var initializeCount: Int = 0
    @Published var closeCount: Int = 0
    @Published var changeCount: Int = 0
    @Published var trackCount: Int = 0
    @Published var hasMobileKey: Bool = false
    @Published var status: String = "SDK not started"

    private var moveTracked = false

    private static func mobileKey() -> String {
        (Bundle.main.object(forInfoDictionaryKey: "LDMobileKey") as? String ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Build the user context, including platform, before start.
    /// https://launchdarkly.com/docs/home/observability/contexts
    func start(username: String) {
        stopObserving(countClose: false)
        released = false
        moveTracked = false
        let key = Self.mobileKey()
        hasMobileKey = !key.isEmpty
        guard !key.isEmpty else {
            status = "No LD_MOBILE_KEY — serving the previous experience"
            return
        }
        status = "Initializing…"
        let config = LDConfig(mobileKey: key, autoEnvAttributes: .enabled)
        var builder = LDContextBuilder(key: username)
        builder.trySetValue("platform", .string(Self.platform))
        guard case .success(let context) = builder.build() else {
            status = "Invalid context — serving the previous experience"
            return
        }
        LDClient.start(config: config, context: context, startWaitSeconds: 5) { [weak self] _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.initializeCount += 1
                self.observe()
                self.readFlag()
                self.status = "Connected · platform=\(Self.platform)"
            }
        }
    }

    /// One custom event per login, after a real cell change.
    /// https://launchdarkly.com/docs/sdk/features/events
    func trackMove() {
        if moveTracked { return }
        guard let client = LDClient.get() else { return }
        client.track(key: Self.eventKey)
        moveTracked = true
        trackCount += 1
    }

    func stop() {
        stopObserving(countClose: true)
        released = false
        moveTracked = false
        status = "Closed"
    }

    var sdkLog: String {
        "initialize ×\(initializeCount)\n" +
            "change:\(Self.flagKey) ×\(changeCount)\n" +
            "track:\(Self.eventKey) ×\(trackCount)\n" +
            "close ×\(closeCount)"
    }

    private func observe() {
        LDClient.get()?.observe(keys: [Self.flagKey], owner: self) { [weak self] _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.changeCount += 1
                self.readFlag()
            }
        }
    }

    private func readFlag() {
        guard let client = LDClient.get() else { return }
        released = client.boolVariation(forKey: Self.flagKey, defaultValue: false)
    }

    private func stopObserving(countClose: Bool) {
        guard let client = LDClient.get() else { return }
        client.stopObserving(owner: self)
        client.close()
        if countClose { closeCount += 1 }
    }
}
