# 108-flag-approvals

A grid hides **Count** until one boolean flag is on. The page cannot turn that flag on itself. It creates an **approval request**. A person approves it in LaunchDarkly. The page then **applies** the request, and the next evaluation shows the count.

This is not [101-flag-enablement](../101-flag-enablement/). That example's count flag stays independent.

Keywords: **approvals** · **feature flags** · **boolean variations**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)

## Flag

| | |
|---|---|
| Key | `show-navigation-move-count-approval` |
| Kind | Boolean, temporary |
| Off | `false` — count hidden |
| On, after apply | `true` — `Count: N` in the header |
| Instruction | `turnFlagOn` |

The count itself is application state. The flag only shows it.

## Steps

1. Log in. The count row is hidden. The evaluation reason is the SDK default or `OFF`.
2. **Request approval.** The name is `Turn on the move count` plus the next number from `.request-count`, shared by the four web servers. The rail says pending and shows **Open in LaunchDarkly**. Apply is disabled. The Approvals dashboard hides the request until a reviewer is named. The link opens that request's review screen in the project's approvals (`/projects/{project}/approvals/{id}`). If it lands on the Approvals dashboard instead, use the flag's Pending changes panel.
3. In LaunchDarkly, approve that request. Do not apply it there.
4. The rail polls. When the review is approved, **Apply** enables.
5. Click Apply. The next evaluation is true, and the count row appears. Moves increment it.
6. The trace records each step and labels it Lab UI, Lab API, or LaunchDarkly. While nothing has changed, the last line stays **polling**.
7. **Reset** deletes the approval requests for this flag, turns the flag off, and clears the count. The name counter stays where it is.

A declined request can be requested again. An open request is reused. The page does not approve its own request.

## Acceptance

- [ ] Web on **:8180** Python, **:8181** Node, **:8182** Java, **:8183** .NET
- [ ] Dedicated flag key, not `show-navigation-move-count`
- [ ] Request creates an approval. It does not patch targeting
- [ ] Apply stays disabled until LaunchDarkly reports the review approved
- [ ] After apply, the count row is visible
- [ ] Reset deletes the request, turns the flag off, and hides the count
- [ ] The trace names Lab UI, Lab API, and LaunchDarkly
- [ ] About sits under **LaunchDarkly · lab** and links the approvals docs
