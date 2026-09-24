# iOS — 53-mobile-experiment

SwiftUI implementation of the native mobile
[Experimentation lesson](../application.md). It uses the
[LaunchDarkly iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios)
with a **mobile key**.

## Prerequisites

- macOS and [Xcode](https://developer.apple.com/xcode/) **15+**
- The shared `acme-mobile-onboarding-v2` boolean feature flag and
  `mobile_onboarding_completed` custom metric

## Local mobile key

From `53-mobile-experiment/`:

```bash
export LD_MOBILE_KEY="mob-..."
./sync-mobile-key.sh
```

This writes the gitignored `ios/LDMobileKey.xcconfig`. `Config.xcconfig`
passes the value to Info.plist as `LDMobileKey`. Never use or embed an
`LD_SDK_KEY` in this client-side app.

Manual fallback:

```bash
cp ios/LDMobileKey.xcconfig.example ios/LDMobileKey.xcconfig
```

## Build and run

```bash
open ios/53-mobile-experiment.xcodeproj
```

Command-line simulator compile without signing:

```bash
cd ios
xcodebuild -project 53-mobile-experiment.xcodeproj \
  -scheme 53-mobile-experiment \
  -sdk iphonesimulator -configuration Debug \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
```

Bundle identifier: `com.lunchmarcoly.experiment53`.

## What to expect

1. Log in with a stable username. Its trimmed value is the LaunchDarkly
   **user context** key; `platform=ios` and `app-version=1.0.0` are custom
   analysis attributes.
2. The app evaluates `acme-mobile-onboarding-v2` before rendering:
   `false` opens the 2×2 grid; `true` shows **How to play**, then Continue
   opens the same grid.
3. The first successful orthogonal move tracks
   `mobile_onboarding_completed` once for that login. Invalid and repeated
   taps do not send an event.
4. Swipe from the left edge or tap its edge to open the lab drawer. It shows
   variation, platform, exposure, conversion, key/status, and SDK calls.
5. Logout closes the SDK client.

The flag variation—not the platform—assigns the experience. Platform is only a
result-analysis dimension. See
[mobile Experimentation](https://launchdarkly.com/docs/sdk/features/experimentation),
[contexts](https://launchdarkly.com/docs/home/contexts), and
[Experimentation events](https://launchdarkly.com/docs/home/experimentation/events).

## Classroom caveat

The repository defaults to project `lunch-marcoly`, but provisioning uses
`LD_PROJECT_KEY`. Concurrent classes in one environment share flag targeting,
experiment allocation, and results. For isolation, use a distinct
`LD_ENVIRONMENT_KEY` and that environment's `LD_MOBILE_KEY`.
