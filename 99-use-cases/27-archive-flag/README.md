# 27-archive-flag

**Status: stub — not implemented yet.**

Archive a feature flag, using the old HTML `<blink>` element as the thing you
can see. While the flag is on, the **selected cell** blinks. After the flag
is archived, the blink stops, because the SDK no longer has the flag and
falls back to its default.

The page steps through the stages. It does not play them on a timer. Each
step waits so you can look at the cell and the flag state before the next one.

Keywords: **archive** · **feature flags** · **temporary flag** · **SDK default**

Docs: [Archive a flag](https://launchdarkly.com/docs/home/flags/archive)

## Stages

The first pass is three stages. Add interstitial steps in `application.md`
when a gap shows up (for example, turn the flag on as its own step, or show
the flag still listed before it is archived).

1. **Setup.** Create the flag. The cell does not blink.
2. **Run.** The flag is on. The selected cell blinks.
3. **Archive.** Archive the flag. The cell stops blinking. Evaluation is the
   SDK default, not an application `if` that notices the archive.

A REST script owns the LaunchDarkly calls. The page has a control that runs
the next stage and then stops.

## Intended flag

| Attribute | Starting value |
|-----------|----------------|
| **Key** | `enable-selection-blink` |
| **Type** | boolean, temporary |
| **On** | selected cell blinks |
| **Off / SDK default** | selected cell does not blink |

Dedicated key. Do not reuse a 101 or 105 flag.

## Do not

- Blink the username or a header word. The selected cell is the blink.
- Autoplay the stages. The operator advances them.
- Treat archive as "turn the flag off." Off is stage 2's opposite. Archive
  removes the flag from evaluation.

## When implementing

1. Write `application.md`: the flag, the default value, what the cell does
   on each stage, and which extra steps belong between the three above.
2. One web app. Python is enough for the first pass.
3. REST script with one command per stage. The page calls the next command
   and renders the result.
