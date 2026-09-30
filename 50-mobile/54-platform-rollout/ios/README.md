# iOS — 54-platform-rollout

SwiftUI twin of [54-platform-rollout](../application.md). Uses the
[LaunchDarkly iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios)
(Swift Package) with a **mobile key**.

## Prerequisites

- macOS and [Xcode](https://developer.apple.com/xcode/) **15+**
- Flags from [../rest/](../rest/) or [../terraform/](../terraform/)

## Environment / local config

From `54-platform-rollout/` (not this folder):

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
open 54-platform-rollout.xcodeproj
```

Command line compile (no simulator runtime required):

```bash
xcodebuild -project 54-platform-rollout.xcodeproj -scheme 54-platform-rollout \
  -sdk iphonesimulator -configuration Debug \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
```

## Run

Xcode → Run on Simulator. Bundle id: `com.lunchmarcoly.rollout54`.

## What to expect

1. Login with a non-empty username. Context includes `platform=ios`.
2. After `./rest/create-flag.sh`, the header says `Release: waiting` and the cell stays plain.
3. `./rest/advance-rollout.sh` adds `ios`. The listener flips the header to `Release: on` without restart.
4. The first orthogonal tap logs one `track`. A wall tap does not.
5. Drawer: release, platform, `initialize` / `change:` / `track:` / `close`.
