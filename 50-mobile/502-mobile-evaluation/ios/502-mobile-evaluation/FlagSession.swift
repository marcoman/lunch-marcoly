import Combine
import Foundation
import LaunchDarkly

/// LaunchDarkly capability: iOS mobile SDK — start, string/bool variation,
/// observe, close.
/// https://launchdarkly.com/docs/sdk/client-side/ios
///
/// Credential is Info.plist LDMobileKey from LD_MOBILE_KEY in xcconfig.
final class FlagSession: ObservableObject {
    static let highlightKey = "enable-mobile-grid-highlight"
    static let countKey = "show-mobile-move-count"

    @Published var highlight: String = "none"
    @Published var showCount: Bool = false
    @Published var initializeCount: Int = 0
    @Published var closeCount: Int = 0
    @Published var changeHighlightCount: Int = 0
    @Published var changeCountFlagCount: Int = 0
    @Published var hasMobileKey: Bool = false
    @Published var status: String = "SDK not started"

    private static func mobileKey() -> String {
        (Bundle.main.object(forInfoDictionaryKey: "LDMobileKey") as? String ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func start(username: String) {
        let key = Self.mobileKey()
        hasMobileKey = !key.isEmpty
        guard !key.isEmpty else {
            highlight = "none"
            showCount = false
            status = "No LD_MOBILE_KEY — serving code defaults"
            return
        }
        status = "Initializing…"
        let config = LDConfig(mobileKey: key, autoEnvAttributes: .enabled)
        let builder = LDContextBuilder(key: username)
        guard case .success(let context) = builder.build() else {
            status = "Invalid context — serving code defaults"
            return
        }
        LDClient.start(config: config, context: context, startWaitSeconds: 5) { [weak self] _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.initializeCount += 1
                self.observe()
                self.readFlags()
                self.status = "Connected"
            }
        }
    }

    func stop() {
        if let client = LDClient.get() {
            client.stopObserving(owner: self)
            client.close()
            closeCount += 1
        }
        highlight = "none"
        showCount = false
        status = "Closed"
    }

    var sdkLog: String {
        "initialize ×\(initializeCount)\n" +
            "change:\(Self.highlightKey) ×\(changeHighlightCount)\n" +
            "change:\(Self.countKey) ×\(changeCountFlagCount)\n" +
            "close ×\(closeCount)"
    }

    private func observe() {
        LDClient.get()?.observe(keys: [Self.highlightKey, Self.countKey], owner: self) { [weak self] changed in
            DispatchQueue.main.async {
                guard let self else { return }
                if changed[Self.highlightKey] != nil {
                    self.changeHighlightCount += 1
                }
                if changed[Self.countKey] != nil {
                    self.changeCountFlagCount += 1
                }
                self.readFlags()
            }
        }
    }

    private func readFlags() {
        guard let client = LDClient.get() else { return }
        highlight = client.stringVariation(forKey: Self.highlightKey, defaultValue: "none")
        showCount = client.boolVariation(forKey: Self.countKey, defaultValue: false)
    }
}
