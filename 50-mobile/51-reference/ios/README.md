# iOS — 51-reference

SwiftUI twin of the [51-reference](../application.md) 2×2 tap navigator.
**No LaunchDarkly.**

## Prerequisites

- macOS
- [Xcode](https://developer.apple.com/xcode/) **15+**

```bash
xcodebuild -version
```

## Environment variables

None. 51 does not use `LD_MOBILE_KEY`.

## Build

Open the Xcode project:

```bash
open 51-reference.xcodeproj
```

Select an iPhone Simulator and press Run. This machine needs an **iOS Simulator
runtime** (Xcode → Settings → Components). Command line compile (no runtime
required):

```bash
xcodebuild -project 51-reference.xcodeproj -target 51-reference \
  -sdk iphonesimulator -configuration Debug \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
```

If a simulator exists:

```bash
xcodebuild -scheme 51-reference -destination 'platform=iOS Simulator,name=iPhone 16' build
```

## Run

Xcode → Run. Bundle id: `com.lunchmarcoly.reference51`.

## What to expect

1. Login: enter a non-empty username. Empty names are rejected.
2. Grid starts at `t/l` with Previous `—`. Selected cell shows **X** (no color).
3. Tap an orthogonally adjacent cell to move. Diagonal taps do nothing.
4. Logout in the header returns to login and resets the grid.
5. Swipe from the left edge (or tap the handle) for the lab drawer.
