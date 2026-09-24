# Android — 53-mobile-experiment

Kotlin / Jetpack Compose implementation of the canonical
[mobile experiment specification](../application.md). It uses the
[LaunchDarkly Android SDK](https://launchdarkly.com/docs/sdk/client-side/android)
and [mobile Experimentation](https://launchdarkly.com/docs/sdk/features/experimentation).

Keywords: **Experimentation**, **boolean variation**, **contexts**, **exposure**,
**custom conversion event**, **platform analysis**.

## Prerequisites

- [Android Studio](https://developer.android.com/studio) (JDK **17** or **21**)
- Emulator or device, API **26+**
- Boolean feature flag `acme-mobile-onboarding-v2`, available to mobile SDKs

## Mobile key

Set the environment's mobile key in this folder's gitignored
`local.properties`:

```properties
ld.mobile.key=mob-...
```

Alternatively, export `LD_MOBILE_KEY` before Gradle configuration. Gradle bakes
the value into `BuildConfig.LD_MOBILE_KEY`; rerun Gradle after changing it.
Never use or commit an `LD_SDK_KEY` in a mobile app.

## Build and run

```bash
./gradlew :app:assembleDebug
./gradlew installDebug
adb shell am start -n com.lunchmarcoly.experiment53/.MainActivity
```

APK: `app/build/outputs/apk/debug/app-debug.apk`.

## Experiment flow

1. Login with a non-empty username. Its trimmed value is the stable user key.
2. Before SDK initialization, the app builds a context with
   `platform="android"` and `app-version="1.0.0"`.
3. Evaluating `acme-mobile-onboarding-v2` establishes exposure:
   - `false`: control opens the 2×2 grid immediately.
   - `true`: treatment shows **How to play**, then Continue opens the same grid.
4. The first successful orthogonal move tracks
   `mobile_onboarding_completed` once per login. Invalid and later taps do not.
5. Swipe from the left edge for flag, platform, exposure, conversion, key,
   status, and SDK-call diagnostics.
6. Logout closes the SDK client.

Platform is analysis metadata, never assignment logic. Android and iOS evaluate
the same flag and track the same conversion event. Shared classroom environments
also share targeting, allocation, and results; use separate environment mobile
keys when participants need isolation.
