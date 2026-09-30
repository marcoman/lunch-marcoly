# Android — 54-platform-rollout

Kotlin / Jetpack Compose twin of [54-platform-rollout](../application.md).
Uses the [LaunchDarkly Android SDK](https://launchdarkly.com/docs/sdk/client-side/android)
with a **mobile key**.

## Prerequisites

- [Android Studio](https://developer.android.com/studio) (JDK **17** or **21**)
- Flags from [../rest/](../rest/) or [../terraform/](../terraform/)
- Emulator or device, API **26+**

Command-line `./gradlew` needs JDK **17 or 21**, not Android Studio’s Java 25 JBR.

## Environment variables / local config

From `54-platform-rollout/` (not this folder):

```bash
export LD_MOBILE_KEY="mob-..."
./sync-mobile-key.sh
```

That sets `ld.mobile.key` in gitignored `local.properties` and does **not**
replace Studio’s `sdk.dir`. Gradle still accepts `LD_MOBILE_KEY` at configure
time if the property is missing.

The key is baked into `BuildConfig.LD_MOBILE_KEY`. Re-run Gradle after changing
it. Never put `LD_SDK_KEY` here.

## Build

```bash
./gradlew assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`.

## Run

Open this `android/` folder in Android Studio and Run `app`.

Application id: `com.lunchmarcoly.rollout54`.

```bash
./gradlew installDebug
adb shell am start -n com.lunchmarcoly.rollout54/.MainActivity
```

## What to expect

1. Login with a non-empty username. Context includes `platform=android`.
2. After `./rest/create-flag.sh`, the header says `Release: on` and the cell is green.
3. The first orthogonal tap logs one `track`. A second tap in that login does not.
4. `./rest/advance-rollout.sh` keeps Android on. The listener updates without restart.
5. Drawer: release, platform, `initialize` / `change:` / `track:` / `close`.
6. Logout then login: `initialize ×2`, and the next real tap can track again.
