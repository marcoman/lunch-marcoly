# 29-rollout-notifications

**Status: stub — not implemented yet.**

Follow one flag through a short **progressive rollout**. A targeting change
sends an **email**. If the LaunchDarkly Slack app is installed, the same
follow also sends a **Slack** message.

This stays in [99-use-cases](../README.md). **101–109** are already taken, and
[106-percentage-rollout](../../10-feature-management/106-percentage-rollout/)
is a static percentage. The rollout itself already exists:
[14-progressive-rollout](../14-progressive-rollout/) in the UI, and
[22-api-progressive-rollout](../22-api-progressive-rollout/) from the API.
This example adds the two messages. It does not add a tenth feature-management
child.

Keywords: **follow flags** · **notifications** · **progressive rollout** ·
**Slack**

Docs: [Following flags](https://launchdarkly.com/docs/home/flags/follow) ·
[Slack](https://launchdarkly.com/docs/integrations/slack) ·
[Progressive rollouts](https://launchdarkly.com/docs/home/releases/progressive-rollouts)

## What actually sends both

Follow the flag on its Targeting tab, in the environment the rollout runs in.
LaunchDarkly emails the follower when someone makes a targeting change. With
the Slack app installed, that same follow also notifies in Slack. If Slack is
not installed, the email still counts and the page says Slack was not
configured.

A channel subscription (`/launchdarkly subscribe`) is a second Slack path.
Use it only if a channel message is wanted in addition to the follow.
[Slack notifications](https://launchdarkly.com/docs/integrations/slack/notifications).

## Which rollout

Use the short progressive rollout. [22-api-progressive-rollout](../22-api-progressive-rollout/)
already steps 10% → 100% in one-minute stages. Follow that flag. Do not
create another highlight flag and do not rebuild 14 or 22.

Guarded rollouts notify on a regression or a rollback, by email and, when
configured, Slack, Teams, or PagerDuty. They are not a message at every
healthy stage.
[Managing guarded rollouts](https://launchdarkly.com/docs/home/releases/managing-guarded-rollouts).
Leave that path in [15-guarded-rollout](../15-guarded-rollout/) and
[23-api-guarded-rollout](../23-api-guarded-rollout/).

Check, when this is built, whether an automatic stage advance counts as the
targeting change that follow notifies on. If it does, each stage is the
message. If it does not, the two sure events are starting the rollout and
stopping it, and the page says that.

## Do not

- Put this in `10-feature-management`. There is no free child number.
- Treat a guarded-rollout regression email as the stage message.
- Require Slack. Email is the channel that is always there.

## When implementing

1. `application.md`: which existing flag is followed, and the two channels.
2. A Python page is enough if the stage needs to sit next to the channel
   list. Intended port **:8789**. Otherwise the clicks live in this README
   and 22 stays the app.
3. Do not paste a Slack webhook URL or a member id.
