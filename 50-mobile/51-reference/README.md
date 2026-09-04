# 51-reference

The **mobile** reference app for [50-mobile](../README.md): username login, a
**2×2** tap grid, logout, and a leading-edge lab drawer.

See [application.md](application.md) for behavior and acceptance criteria.
Selection is **`X` only** — no highlight colors. **No LaunchDarkly.**

This is not [00-reference-code](../../00-reference-code/) (3×3, WASD).

## Prerequisites

- Android Studio **or** Xcode, depending on which twin you run
- No LaunchDarkly account

Set up toolchains using the [root README](../../README.md#building-code).

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Android | [android/](android/) | Mobile application | Done |
| iOS | [ios/](ios/) | Mobile application | Done |
| React Native | `react-native/` | Mobile application | Later |

## Further reading

- [application.md](application.md) — 2×2 tap navigator spec
- [50-mobile/README.md](../README.md) — series overview
- [project.md](../../project.md) — repository conventions
