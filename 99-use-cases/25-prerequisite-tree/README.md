# 25-prerequisite-tree

**Status: stub — not implemented yet.**

A six-flag **prerequisite tree** on the grid navigator. This extends
[105-prerequisite-flags](../../10-feature-management/105-prerequisite-flags/),
which stops at one parent and two children. Here the tree has depth: one
grandparent, two parents, and three children.

```text
grandparent
├── parent 1
│   └── child
└── parent 2
    ├── child
    └── child
```

That is six flags. Parent 1 has one child. Parent 2 has two.

Keywords: **flag prerequisites** · **flag hierarchy** · **dependent flag** ·
**PREREQUISITE_FAILED**

Docs: [Flag prerequisites](https://launchdarkly.com/docs/home/flags/prereqs) ·
[Flag hierarchy](https://launchdarkly.com/docs/guides/flags/flag-hierarchy)

## Intended aha

The drawer shows the tree, and the tree changes when a flag is toggled.

- Grandparent off: every descendant serves its off variation. Each reason is
  `PREREQUISITE_FAILED`. The whole tree reads as blocked.
- Grandparent on, parent 1 off: parent 1's child is blocked. Parent 2 and its
  two children still evaluate.
- Grandparent on, parent 2 off: parent 2's two children are blocked. Parent 1's
  child still evaluates.
- A grandchild stays blocked when its own parent is off, even if the
  grandparent is serving the required variation.

105 already shows that one parent can gate two siblings. This stub is the
next picture: depth, and two different branch shapes side by side.

## Intended flags

Dedicated keys, suffix `tree`, so 105's `-prereq` flags stay independent.
Names below are the starting set. Change them in `application.md` when this
is built if a clearer grid surface shows up.

| Role | Cites | Visible when eligible |
|------|-------|------------------------|
| Grandparent | 101 highlight, must serve `green` | Selection color |
| Parent 1 | 101 move count | `Count: N` |
| Parent 1's child | 102 host emoji | Emoji before the username |
| Parent 2 | previous-position line | `Previous position` |
| Parent 2's child | a coordinate badge on the selected cell | Badge |
| Parent 2's child | a move-limit warning | Warning |

Parent 1 requires the grandparent. Parent 1's child requires parent 1.
Parent 2 requires the grandparent. Parent 2's children require parent 2.
No child depends on its sibling.

## Do not

- Add a third level. Six flags is the lesson.
- Chain parent 2's children onto each other.
- Rebuild 105. 105 stays the one-parent, two-child case.

## When implementing

1. Write `application.md` with the six keys, the required variation on each
   edge, and the drawer states above.
2. One web app is enough to start. The drawer tree is the screen that matters.
3. REST creates the six flags and attaches each prerequisite. Controls toggle
   on/off and never edit the edges.
