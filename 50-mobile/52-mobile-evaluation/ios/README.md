# iOS — 52-mobile-evaluation

SwiftUI twin of [52-mobile-evaluation](../application.md). Uses the
[LaunchDarkly iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios)
(Swift Package) with a **mobile key**.

## Prerequisites

- macOS and [Xcode](https://developer.apple.com/xcode/) **15+**
- Flags from [../rest/](../rest/) or [../terraform/](../terraform/)

## Environment / local config

From `52-mobile-evaluation/` (not this folder):

```bash
export LD_MOBILE_KEY="mob-..."
./sync-mobile-key.sh
```

That writes gitignored `LDMobileKey.xcconfig`. `Config.xcconfig` includes it
when present. The value lands in Info.plist as `LDMobileKey`. Rebuild after
changing it. Never put `LD_SDK_KEY` here.

Manual fallback: `cp LDMobileKey.xcconfig.example LDMobileKey.xcconfig` and
edit the key.

## Build

```bash
open 52-mobile-evaluation.xcodeproj
```

Command line compile (no simulator runtime required):

```bash
xcodebuild -project 52-mobile-evaluation.xcodeproj -scheme 52-mobile-evaluation \
  -sdk iphonesimulator -configuration Debug \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
```

## Run

Xcode → Run on Simulator. Bundle id: `com.lunchmarcoly.evaluation52`.

## What to expect

1. Login with a non-empty username (context `key`).
2. Grid starts at `t/l`. Dark theme. `X` only while highlight is off.
3. Turn `enable-mobile-grid-highlight` **on** in the dashboard — selected cell
   and username pick up the fallthrough color without restarting.
4. Turn `show-mobile-move-count` **on** — header shows `Count: N`.
5. Drawer: flag values + `initialize` / `change:` / `close` counts.
6. Logout then login again: `initialize ×2`. Move count is kept.
