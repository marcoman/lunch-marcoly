import Combine
import Foundation
import LaunchDarkly

/// Owns one login's LaunchDarkly experiment lifecycle.
///
/// LaunchDarkly contexts: the stable, trimmed username is the user key;
/// `platform` and `app-version` are analysis attributes, never assignment logic.
/// https://launchdarkly.com/docs/home/contexts
final class ExperimentSession: ObservableObject {
    static let flagKey = "acme-mobile-onboarding-v2"
    static let eventKey = "mobile_onboarding_completed"

    @Published private(set) var variation = false
    @Published private(set) var exposureEvaluated = false
    @Published private(set) var conversionSent = false
    @Published private(set) var hasMobileKey = false
    @Published private(set) var status = "SDK not started"
    @Published private(set) var initializeCount = 0
    @Published private(set) var evaluationCount = 0
    @Published private(set) var trackCount = 0
    @Published private(set) var closeCount = 0

    private var completedThisLogin = false

    private static func mobileKey() -> String {
        (Bundle.main.object(forInfoDictionaryKey: "LDMobileKey") as? String ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Builds the complete context before starting the client, then evaluates
    /// the boolean variation before allowing either experience to render.
    ///
    /// Experimentation exposure comes from flag evaluation:
    /// https://launchdarkly.com/docs/sdk/features/experimentation
    func start(username: String, completion: @escaping () -> Void) {
        resetLoginState()

        let stableKey = username.trimmingCharacters(in: .whitespacesAndNewlines)
        var builder = LDContextBuilder(key: stableKey)
        builder.trySetValue("platform", .string("ios"))
        builder.trySetValue("app-version", .string("1.0.0"))

        guard case .success(let context) = builder.build() else {
            status = "Invalid context — serving control"
            completion()
            return
        }

        let mobileKey = Self.mobileKey()
        hasMobileKey = !mobileKey.isEmpty
        guard hasMobileKey else {
            status = "No LD_MOBILE_KEY — serving control"
            completion()
            return
        }

        status = "Initializing…"
        let config = LDConfig(mobileKey: mobileKey, autoEnvAttributes: .enabled)
        LDClient.start(config: config, context: context, startWaitSeconds: 5) { [weak self] _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.initializeCount += 1
                self.variation = LDClient.get()?.boolVariation(
                    forKey: Self.flagKey,
                    defaultValue: false
                ) ?? false
                self.evaluationCount += 1
                self.exposureEvaluated = true
                self.status = "Evaluated"
                completion()
            }
        }
    }

    /// Tracks the custom conversion once per login, and only after the first
    /// successful move. Invalid and later taps never reach this call.
    ///
    /// Custom events for Experimentation:
    /// https://launchdarkly.com/docs/home/experimentation/events
    func trackCompletedMove() {
        guard !completedThisLogin else { return }
        completedThisLogin = true
        guard let client = LDClient.get(), hasMobileKey else {
            status = "Move completed; SDK unavailable"
            return
        }
        client.track(key: Self.eventKey)
        trackCount += 1
        conversionSent = true
        status = "Conversion sent"
    }

    /// Closes the mobile client on logout and clears per-login experiment state.
    func stop() {
        if let client = LDClient.get() {
            client.close()
            closeCount += 1
        }
        resetLoginState()
        status = "Closed"
    }

    var sdkLog: String {
        "initialize ×\(initializeCount)\n" +
            "boolVariation:\(Self.flagKey) ×\(evaluationCount)\n" +
            "track:\(Self.eventKey) ×\(trackCount)\n" +
            "close ×\(closeCount)"
    }

    private func resetLoginState() {
        variation = false
        exposureEvaluated = false
        conversionSent = false
        completedThisLogin = false
    }
}
