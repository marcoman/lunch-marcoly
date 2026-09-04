# Android — 52-mobile-evaluation

Kotlin / Jetpack Compose twin of [52-mobile-evaluation](../application.md).
Uses the [LaunchDarkly Android SDK](https://launchdarkly.com/docs/sdk/client-side/android)
with a **mobile key**.

## Prerequisites

- [Android Studio](https://developer.android.com/studio) (JDK **17** or **21**)
- Flags from [../rest/](../rest/) or [../terraform/](../terraform/)
- Emulator or device, API **26+**

Command-line `./gradlew` needs JDK **17 or 21**, not Android Studio’s Java 25 JBR.

## Environment variables / local config

From `52-mobile-evaluation/` (not this folder):

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

Application id: `com.lunchmarcoly.evaluation52`.

```bash
./gradlew installDebug
adb shell am start -n com.lunchmarcoly.evaluation52/.MainActivity
```

## What to expect

1. Login with a non-empty username (context `key`).
2. Grid starts at `t/l`. Dark theme. `X` only while highlight is off.
3. Turn `enable-mobile-grid-highlight` **on** in the dashboard — selected cell
   and username pick up the fallthrough color without restarting.
4. Turn `show-mobile-move-count` **on** — header shows `Count: N` for successful taps.
5. Drawer: flag values + `initialize` / `change:` / `close` counts.
6. Logout then login again: `initialize ×2`. Move count is kept.
