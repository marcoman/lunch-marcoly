# 28-big-segment

**Status: stub — not implemented yet.**

A **big segment** on the server SDK. Membership lives in a DynamoDB table in
our account. The flag rule is `segmentMatch`. The grid shows a badge when the
logged-in user is in the segment.

This is viable. It is a different lesson from
[303-synced-segments](../../30-client-sdk/303-synced-segments/). 303 is the
browser. The client SDK does not need a store. A server-side big segment does:
LaunchDarkly keeps the membership in infrastructure we run, and the SDK
consults that store during evaluation.

Keywords: **big segments** · **synced segments** · **persistent store** ·
**DynamoDB** · **segmentMatch**

Docs: [Big segments](https://launchdarkly.com/docs/sdk/features/big-segments) ·
[SDK and integration configuration for segments](https://launchdarkly.com/docs/home/flags/segment-config) ·
[DynamoDB persistent store](https://launchdarkly.com/docs/sdk/features/storing-data/dynamodb)

## What to provision

One region: **us-east-1**. One table. No Relay Proxy.

| Piece | Why it is here |
|-------|----------------|
| DynamoDB table, **Standard** class, **on-demand** | LaunchDarkly's persistent store for the segment. Partition key `namespace` (string), sort key `key` (string). The SDK does not create the table. |
| IAM role LaunchDarkly can assume | The DynamoDB integration writes membership into the table. LaunchDarkly supplies the external ID when the integration is created. |
| Nothing else | Relay Proxy, ElastiCache, ECS, a NAT gateway, global tables, PITR, and DAX are not part of this demo. The docs allow a store integration without the Relay Proxy, and they recommend DynamoDB over Redis on AWS because the table scales without a host we size. |

IAM roles have no hourly charge.

## Default prices, us-east-1

List prices from the [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
examples for US East (N. Virginia). Those examples use:

| Meter | List price |
|-------|------------|
| On-demand writes | **$0.625** per million write request units |
| On-demand reads | **$0.125** per million read request units |
| Standard storage | **$0.25** per GB-month |

The same examples treat the first **25 GB** of Standard storage as included
in the AWS Free Tier. Whether this account still has that allowance is an
account fact, not a property of the table. Confirm the live page before
quoting a bill. Prices move.

A lab that writes a few thousand membership keys and reads them while people
click around stays under a million request units and under a gigabyte. The
request charge is cents. An idle on-demand table with no traffic is storage
only. The costs to avoid are the ones this stub leaves out: a NAT gateway, a
Relay host, or a cache cluster, which bill while the demo is closed.

## Intended aha

Add a username through the big-segment API. The server SDK's flag turns on
for that user because the membership was read from DynamoDB, not because the
flag payload listed them. Remove them, and the badge goes away. 303 keeps
doing this in the browser without the table.

## Do not

- Rebuild 303 here.
- Put the Relay Proxy in front "just in case."
- Turn on PITR, global tables, or provisioned capacity for a table this small.

## When implementing

1. Write `application.md`: flag key, segment key, and the badge.
2. A short setup note for the table and the IAM role. Do not paste the role ARN.
3. One server-side web app. Python is enough. The page adds and removes the
   current user and shows the evaluation.
