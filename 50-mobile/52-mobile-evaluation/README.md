# 52-mobile-evaluation

Mobile **feature flags**: initialize an Android or iOS SDK with a **mobile
key**, mark flags **available to mobile SDKs**, evaluate variations, and
listen for streaming updates.

Baseline UI: [51-reference](../51-reference/). Behavior spec:
[application.md](application.md).

Keywords: **feature flags** · **mobile key** · **boolean variation** ·
**string variation** · **flag listeners** · **Android SDK** · **iOS SDK**

Docs: [Android SDK](https://launchdarkly.com/docs/sdk/client-side/android) ·
[iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios) ·
[environment keys](https://launchdarkly.com/docs/home/account/environment/keys) ·
[client-side and mobile availability](https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks)

## What this demonstrates

| Flag key | Off | On |
|----------|-----|-----|
| `enable-mobile-grid-highlight` | `none` — `X` only | Fallthrough color on the selected cell |
| `show-mobile-move-count` | Count hidden | `Count: N` in the header |

**Not in 52:** browser client-side ID, in-app REST Controls, `identify()`
without logout, AgentControl.

## Prerequisites

1. Same LaunchDarkly **project and environment** you already use for lunch-marcoly.
2. **`LD_MOBILE_KEY`** for that environment (starts with `mob-`, not `sdk-`).
3. Provision the two flags (`rest/` or `terraform/`) so they are **available
   to mobile SDKs** (`usingMobileKey`).

```bash
export LD_MOBILE_KEY="mob-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."    # rest/ / terraform only
chmod +x sync-mobile-key.sh
./sync-mobile-key.sh
```

`sync-mobile-key.sh` writes the mobile key into gitignored
`android/local.properties` (`ld.mobile.key`, leaves `sdk.dir` alone) and
`ios/LDMobileKey.xcconfig`. Rebuild Android / Xcode after running it.

Do **not** put `LD_SDK_KEY` or the API token in the Android / iOS app.

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Run provisioning before launching the app. Toggle flags in the dashboard to
see listeners fire.

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Android | [android/](android/) | Mobile application | Done |
| iOS | [ios/](ios/) | Mobile application | Done |
| React Native | `react-native/` | Mobile application | Later |

## Further reading

- [application.md](application.md)
- [50-mobile](../README.md)
- [51-reference](../51-reference/)
- [31-client-evaluation](../../30-client-sdk/31-client-evaluation/) — browser analog
