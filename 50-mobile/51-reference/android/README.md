# Android — 51-reference

Kotlin / Jetpack Compose twin of the [51-reference](../application.md) 2×2 tap
navigator. **No LaunchDarkly.**

## Prerequisites

- [Android Studio](https://developer.android.com/studio) (or Android SDK + JDK **17** or **21**)
- An emulator or USB-debuggable device (API **26+**)

Command-line `./gradlew` needs JDK **17 or 21**. Current Android Studio JBR is
**Java 25**, which Gradle 8.11 rejects. Point `JAVA_HOME` at Corretto 21 (or
similar) if the wrapper fails with a bare version number.

## Environment variables

None. 51 does not use `LD_MOBILE_KEY`.

## Build

From this directory:

```bash
./gradlew assembleDebug
```

The Gradle Wrapper downloads Gradle on first run. APK:
`app/build/outputs/apk/debug/app-debug.apk`.

This machine must have an Android SDK. Install [Android Studio](https://developer.android.com/studio)
once, then either set `ANDROID_HOME` to the SDK path or let Studio write
`local.properties` (gitignored) with `sdk.dir=...`.

## Run

Open this `android/` folder in Android Studio and Run the `app` configuration
on an emulator or device.

Application id: `com.lunchmarcoly.reference51`.

Command line (device already selected via `adb`):

```bash
./gradlew installDebug
adb shell am start -n com.lunchmarcoly.reference51/.MainActivity
```

## What to expect

1. Login: enter a non-empty username. Empty names are rejected.
2. Grid starts at `t/l` with Previous `—`. Selected cell shows **X** (no color).
3. Tap an orthogonally adjacent cell to move. Diagonal taps do nothing.
4. Logout in the header returns to login and resets the grid.
5. Swipe from the left edge (or tap the handle) for the lab drawer.
