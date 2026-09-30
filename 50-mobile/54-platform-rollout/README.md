# 54-platform-rollout

Stagger a mobile release by **platform**. Android gets the new experience
first. A REST script then adds iOS to the same targeting rule. Both apps
send `track("mobile_platform_rollout_move")` on the first real tap of a login.

This is not [53-mobile-experiment](../53-mobile-experiment/). Users are not
randomized. Counts by platform are release traffic, not experiment lift.

Baseline UI: [51-reference](../51-reference/). Behavior spec:
[application.md](application.md).

Keywords: **targeting rules** · **platform** · **mobile SDK** · **track**

Docs: [Target with rules](https://launchdarkly.com/docs/home/flags/target-with-rules) ·
[Android SDK](https://launchdarkly.com/docs/sdk/client-side/android) ·
[iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios) ·
[Custom events](https://launchdarkly.com/docs/sdk/features/events)

## What this demonstrates

| Flag | `true` | `false` |
|------|--------|---------|
| `enable-mobile-platform-rollout` | Green cell, `Release: on` | Plain `X`, `Release: waiting` |

| State | Clause values | Android | iOS |
|-------|---------------|---------|-----|
| 1 | `android` | on | waiting |
| 2 | `android`, `ios` | on | on |

The context attribute is `platform` (`android` or `ios`). Code default is
`false`. Move count is always visible.

Confirm events on [Live events](https://launchdarkly.com/docs/home/releases/live-events)
(Custom). There is no public API that returns them.

## Prerequisites

1. Same LaunchDarkly **project and environment** you already use for lunch-marcoly.
2. **`LD_MOBILE_KEY`** for that environment (starts with `mob-`).
3. Provision the flag so it is **available to mobile SDKs**.

```bash
export LD_MOBILE_KEY="mob-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."    # rest/ only
chmod +x sync-mobile-key.sh rest/*.sh
./sync-mobile-key.sh
./rest/create-flag.sh
```

`sync-mobile-key.sh` writes the mobile key into gitignored
`android/local.properties` (`ld.mobile.key`) and `ios/LDMobileKey.xcconfig`.
Rebuild after running it. Do not put `LD_SDK_KEY` or the API token in the app.

## Advance

With both apps logged in:

```bash
./rest/status.sh            # platform values: android
./rest/advance-rollout.sh   # adds ios
./rest/status.sh            # platform values: android, ios
```

The flag listener updates a running app. iOS flips to `Release: on`. Android
stays on. A later Terraform apply returns the rule to Android only — see
[terraform/README.md](terraform/README.md).

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Android | [android/](android/) | Mobile application | Done |
| iOS | [ios/](ios/) | Mobile application | Done |
| React Native | `react-native/` | Mobile application | Later |

## Further reading

- [application.md](application.md)
- [50-mobile](../README.md)
- [52-mobile-evaluation](../52-mobile-evaluation/) — init, variation, listeners
- [53-mobile-experiment](../53-mobile-experiment/) — experiment, platform is analysis only
