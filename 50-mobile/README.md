# 50-mobile

LaunchDarkly **mobile SDK** examples. This series uses a **new application**: a
2×2 tap navigator for phones. It is **not** the 3×3 WASD grid from
[00-reference-code](../00-reference-code/) or
[02-reference-client-code](../02-reference-client-code/).

The device evaluates flags with the **Android / iOS (and later React Native)
mobile SDKs**. That is the client-side family, **not** the browser JavaScript
SDK in [30-client-sdk](../30-client-sdk/). Credential is a **mobile key**
(`LD_MOBILE_KEY`, typically `mob-…`), never `LD_SDK_KEY` and never the
client-side ID.

AgentControl ([20-agent-config](../20-agent-config/)) is **out of scope** for
this series.

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **51** | [51-reference/](51-reference/) | Touch 2×2 navigator — **no LaunchDarkly** |
| **52** | [52-mobile-evaluation/](52-mobile-evaluation/) | `init`, `variation`, listeners — **mobile key** |

There is no series HTTP portal. Run each app in an emulator or simulator.

## Credentials

| Variable | Role |
|----------|------|
| `LD_MOBILE_KEY` | Mobile SDK (51 does **not** use this; **52 does**) |
| `LD_SDK_KEY` | **Not used** — do not embed a server SDK key |
| `LD_CLIENT_SIDE_ID` | **Not used** — that is the browser 30-series |

SDK credentials: [environment keys](https://launchdarkly.com/docs/home/account/environment/keys).
Mobile SDKs: [Android](https://launchdarkly.com/docs/sdk/client-side/android) ·
[iOS](https://launchdarkly.com/docs/sdk/client-side/ios) ·
[React Native](https://launchdarkly.com/docs/sdk/client-side/react/react-native)
(language folder later).

Flags in later examples must be **available to client-side and mobile SDKs**.
See [client-side and mobile flags](https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks).

## Languages

| Directory | Platform | Status |
|-----------|----------|--------|
| `android/` | Kotlin + Jetpack Compose | 51 + 52 |
| `ios/` | Swift + SwiftUI | 51 + 52 |
| `react-native/` | React Native | Later — add after native twins exist |

## Prerequisites

- **Android:** [Android Studio](https://developer.android.com/studio) (JDK 17+, SDK, emulator)
- **iOS:** macOS + [Xcode](https://developer.apple.com/xcode/) 15+

## Further reading

- [51-reference/application.md](51-reference/application.md) — 2×2 tap navigator spec
- [52-mobile-evaluation/application.md](52-mobile-evaluation/application.md) — mobile SDK evaluation
- [project.md](../project.md) — `android/`, `ios/`, `react-native/` conventions
