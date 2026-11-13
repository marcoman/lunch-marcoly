#!/usr/bin/env python3
"""Generate the two workflow diagrams from the repository's own example folders.

    python3 diagrams/build.py            # writes the two .html files
    python3 diagrams/build.py --check    # reports unmapped examples, writes nothing
    python3 diagrams/build.py --local    # cite with relative links, for offline reading

Each diagram is a spine of stages with a second layer of boxes beneath it holding
the examples that belong to each stage. Citations use the repository's shorthand:
the top-level folder number, a slash, the example number, so
`10-feature-management/105-prerequisite-flags` is `10/105`.

The example list and each example's status (implemented or stub) are read from
disk on every run, so the diagrams follow the repository. WHERE an example lands
is editorial and lives in PLACEMENT below — one entry per numbered example. Add an
example to the repository and `--check` will name it as unmapped until it is placed.

Each diagram is written twice. The .html page lays the stages out left to right, which
is the shape to present from. The .svg stacks them vertically, because that is the shape
a fit-to-box viewer such as GitHub's file preview can show at a readable size. Same
stages, same citations, same geometry inside each box. See `standalone()` for what the
.svg gives up and `portrait()` for why it is stacked.

No external files: fonts degrade to system faces, and every mark is drawn inline.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(os.path.abspath(__file__))

# Citations link here by default. A relative link to a folder works when the page is
# opened from a clone, but 404s on GitHub Pages, which serves a directory only when it
# holds an index.html — these folders hold a README.md. Absolute links work everywhere:
# from Pages, from a clone, and from any raw-file viewer. `--local` switches them back.
REPO = "https://github.com/marcoman/lunch-marcoly"
BRANCH = "main"

# Series that hold numbered examples, in the order they appear in the citations.
SERIES = {
    "10": "feature flags",
    "20": "agent management",
    "30": "client SDK",
    "40": "do not do this",
    "50": "mobile",
    "60": "observability",
    "70": "model demos",
    "99": "use cases",
}
SERIES_DIR = {
    "10": "10-feature-management", "20": "20-agent-management",
    "30": "30-client-sdk", "40": "40-dont-do-this", "50": "50-mobile",
    "60": "60-observability", "70": "70-model-demos", "99": "99-use-cases",
}
BASELINES = ["00-reference-feature", "01-reference-agent", "02-reference-client-code"]

# example id -> (CI/CD stages, LLM steps). An example may land in several of each;
# an empty list means it has nothing to say about that workflow.
PLACEMENT = {
    "10/101": (["01", "03"], ["01"]),
    "10/102": (["04"], ["01"]),
    "10/103": (["04"], ["01"]),
    "10/104": (["04"], ["01"]),
    "10/105": (["04"], ["05"]),
    "10/106": (["04"], ["06"]),
    "10/107": (["03", "04"], []),
    "10/108": (["03"], []),
    "10/109": (["05"], []),
    "20/20":  ([], ["03", "04", "05"]),
    "20/201": ([], ["02", "03"]),
    "20/202": ([], ["02", "06"]),
    "20/203": ([], ["04"]),
    "20/204": ([], ["05"]),
    "20/205": ([], ["04"]),
    "20/206": (["01"], ["02", "03"]),
    "20/207": ([], ["02", "03"]),
    "20/208": ([], ["01"]),
    "20/209": (["04"], ["06"]),
    "30/301": (["04"], ["01"]),
    "30/302": (["04"], ["01"]),
    "30/303": (["04"], ["06"]),
    "30/304": (["04"], ["06"]),
    "30/305": (["02", "03"], []),
    "30/306": (["05"], ["06"]),
    "30/307": (["05"], []),
    "30/308": (["03"], []),
    "30/309": (["04"], ["01"]),
    "40/401": (["01"], []),
    "40/402": (["01", "03"], []),
    "50/501": (["01"], []),
    "50/502": (["04"], []),
    "50/503": (["05"], ["06"]),
    "50/504": (["04"], []),
    "50/505": (["04"], ["01"]),
    "50/506": (["02", "03"], []),
    "60/601": (["05"], []),
    "60/602": (["05"], ["03"]),
    "60/603": (["05"], ["04"]),
    "60/605": (["02", "05"], ["06"]),
    "60/606": (["05"], ["05"]),
    "70/701": ([], ["03"]),
    "70/702": ([], ["05"]),
    "70/703": ([], ["03"]),
    "70/704": (["01"], ["05"]),
    "70/705": ([], ["05"]),
    "99/01":  (["05"], ["06"]),
    "99/02":  (["04"], ["01"]),
    "99/11":  (["01", "03"], []),
    "99/14":  (["04"], ["02", "06"]),
    "99/15":  (["04"], ["06"]),
    "99/16":  (["04", "05"], ["05", "06"]),
    "99/17":  (["03"], []),
    "99/18":  (["03"], []),
    "99/19":  (["01", "02"], []),
    "99/20":  (["05"], ["06"]),
    "99/21":  (["04"], []),
    "99/22":  (["04"], ["06"]),
    "99/23":  (["04"], ["06"]),
    "99/24":  (["04"], []),
    "99/25":  (["04"], ["05"]),
    "99/26":  ([], ["05", "06"]),
    "99/27":  (["05"], []),
    "99/28":  (["04"], ["06"]),
    "99/29":  (["05"], []),
    "99/30":  (["01"], ["01"]),
}

CICD = [
    ("01", "Code", ["An engineer or an agent", "opens a pull request."], [
        ("what gets a flag", "flag", "feature flags / naming, provisioning"),
        ("who may create it", "flag", "REST API, CLI, Terraform"),
        ("what runs with no SDK", "flag", "SDK defaults, fallbacks"),
    ]),
    ("02", "Build/Test", ["One artifact, tested. Nothing", "environment-specific inside."], [
        ("baked in or fetched?", "flag", "environments, SDK keys"),
        ("what blocks a merge", "flag", "Terraform, policy"),
        ("which metrics exist", "flask", "metrics, metric groups"),
    ]),
    ("03", "Deploy", ["The flag exists first. The", "artifact lands dark."], [
        ("flag before the code", "flag", "Terraform, REST, CLI"),
        ("deploy, not release", "flag", "the flag is off"),
        ("who may change prod", "flag", "roles, approvals"),
    ]),
    ("04", "Release", ["On in stages, watched,", "reversed if it regresses."], [
        ("who goes first", "people", "targeting rules, segments"),
        ("how fast it widens", "flag", "percentage, progressive rollouts"),
        ("what rolls it back", "flask", "guarded rollouts, metrics"),
    ]),
    ("05", "Monitor", ["Measured in production,", "then the flag retires."], [
        ("what actually happened", "chart", "traces, errors, logs"),
        ("which variation won", "flask", "experiments"),
        ("when the flag retires", "flag", "archive, code references"),
    ]),
]

LLM = [
    ("01", "Input", ["A request or event arrives", "with who it is for."], [
        ("on for them at all?", "flag", "feature flags"),
        ("which experience", "flag", "targeting rules"),
        ("which context kinds", "flag", "contexts"),
    ]),
    ("02", "Assemble", ["Build the prompt: rules,", "prompts, facts."], [
        ("the prompt itself", "agent", "Agent Management / prompts"),
        ("which prompt wins", "flag", "progressive rollouts"),
        ("config, not code", "agent", "completion configs"),
    ]),
    ("03", "Generate", ["Pick the model and the", "parameters, then answer."], [
        ("which model", "agent", "Agent Management / model"),
        ("which parameters", "agent", "completion configs"),
        ("staged model swap", "flask", "guarded rollouts"),
    ]),
    ("04", "Act", ["Call a tool, read the", "result, decide again."], [
        ("which tools exist", "agent", "Agent Management / tools"),
        ("one tool off", "flag", "feature flags"),
        ("how far it may go", "agent", "agent graphs"),
    ]),
    ("05", "Check", ["Score the draft. Pass,", "rewrite, or refuse."], [
        ("judges, thresholds", "agent", "Agent Management / judges"),
        ("which evals run", "agent", "evaluations"),
        ("gate on or off", "flag", "prerequisites"),
    ]),
    ("06", "Output", ["The answer or action,", "plus proof it worked."], [
        ("which metric counts", "flask", "metrics, experiments"),
        ("promote or revert", "flask", "guarded rollouts"),
        ("who sees the new one", "people", "segments"),
    ]),
]

# ---------------------------------------------------------------- the repository

def scan():
    """Every numbered example on disk: id -> (folder name, is_stub)."""
    found = {}
    for num, folder in SERIES_DIR.items():
        base = os.path.join(ROOT, folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not os.path.isdir(os.path.join(base, name)):
                continue
            m = re.match(r"^(\d+)-", name)
            if not m:
                continue                       # portal, stories, playgrounds, stubs with no number
            readme = os.path.join(base, name, "README.md")
            text = ""
            if os.path.exists(readme):
                text = open(readme, encoding="utf-8", errors="replace").read(400)
            stub = bool(re.search(r"stub\b", text[:300], re.I))
            found["%s/%s" % (num, m.group(1))] = (name, stub)
    return found


# -------------------------------------------------------------------- the figure

PALETTE = """
  :root {
    --bg: #F8F8F8; --surface: #FFFFFF; --chip: #F1F2F7;
    --ink: #191919; --ink-2: #414042; --muted: #6D6E71; --line: #D1D6D9;
    --blue: #405BFF; --blue-ink: #2A3BA6; --cyan: #3DD6F5;
    --lane: rgba(25, 25, 25, 0.025); --ctrl-fill: rgba(64, 91, 255, 0.06);
    --cite-fill: rgba(61, 214, 245, 0.07); --cite-line: rgba(61, 214, 245, 0.5);
    --display: "Sora", "Trebuchet MS", sans-serif;
    --ui: "Inter", -apple-system, "Segoe UI", sans-serif;
    --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #191919; --surface: #222227; --chip: #2A2B33;
      --ink: #F8F8F8; --ink-2: #C9CDDA; --muted: #9AA0B2; --line: #35373F;
      --blue: #7084FF; --blue-ink: #9AA8FF;
      --lane: rgba(248, 248, 248, 0.03); --ctrl-fill: rgba(112, 132, 255, 0.09);
      --cite-fill: rgba(61, 214, 245, 0.1); --cite-line: rgba(61, 214, 245, 0.45);
      color-scheme: dark;
    }
  }
"""

GLYPHS = {
    "flag": '<path d="M 2.6 1.4 L 2.6 10.6 M 2.6 2 L 9.6 2 L 8.1 4.3 L 9.6 6.6 L 2.6 6.6"/>',
    "agent": ('<path d="M 2.4 4.4 h 7.2 v 5.2 h -7.2 Z M 6 4.4 V 2.2 M 4.4 6.6 v 0.9'
              ' M 7.6 6.6 v 0.9"/>'),
    "chart": '<path d="M 0.6 6 L 3 6 L 4.8 1.8 L 7.2 10.2 L 9 6 L 11.4 6"/>',
    "flask": ('<path d="M 4.4 1.6 h 3.2 M 4.9 1.6 v 3.3 L 2.6 9.6 h 6.8 L 7.1 4.9 V 1.6'
              ' M 4 7.4 h 4"/>'),
    "people": ('<path d="M 4.2 4.6 a 1.5 1.5 0 1 0 0.01 0 M 1.9 10.2 c 0.3 -1.7 1.2 -2.5 2.3 -2.5'
               ' s 2 0.8 2.3 2.5 M 8.6 3.6 a 1.2 1.2 0 1 0 0.01 0 M 7.6 10.2'
               ' c 0.2 -1.4 0.8 -2 1.7 -2 s 1.4 0.6 1.6 2"/>'),
}
FAMILY = {"flag": "feature flags", "agent": "agent management",
          "chart": "observability", "flask": "experimentation", "people": "segments"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def citations(stages, which, examples):
    """stage key -> [(series, [numbers], [stub flags])] in SERIES order."""
    out = {}
    for key, _, _, _ in stages:
        rows = []
        for series in SERIES:
            hits = []
            for eid, (cicd, llm) in sorted(PLACEMENT.items()):
                if not eid.startswith(series + "/"):
                    continue
                if key not in (cicd if which == "cicd" else llm):
                    continue
                if eid not in examples:
                    continue               # placed but no longer on disk
                folder, stub = examples[eid]
                hits.append((eid.split("/")[1], stub, series, folder))
            if hits:
                hits.sort(key=lambda h: (len(h[0]), h[0]))
                rows.append((series, hits))
        out[key] = rows
    return out


def href_for(series_n, folder, local):
    if local:
        return "../%s/%s/" % (SERIES_DIR[series_n], folder)
    return "%s/tree/%s/%s/%s" % (REPO, BRANCH, SERIES_DIR[series_n], folder)


def figure(which, stages, examples, lede, local=False):
    """Return the <svg> for one diagram."""
    n = len(stages)
    pitch = 370 if n == 5 else 308
    w = 340 if n == 5 else 280
    xs = [42 + pitch * i for i in range(n)]
    cites = citations(stages, which, examples)
    rows_max = max(len(v) for v in cites.values())
    cite_h = 30 + rows_max * 15 + 10
    cite_y = 500
    foot_y = cite_y + cite_h + 44
    height = foot_y + 76

    s = []
    add = s.append
    add('<svg viewBox="0 0 1904 %d" role="img" aria-label="%s">' % (height, esc(lede)))
    add('<defs>')
    add('<marker id="ar-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"'
        ' markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="ah-ink"/></marker>')
    add('<marker id="ar-mute" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"'
        ' markerHeight="5" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="ah-mute"/></marker>')
    add('<marker id="ar-cyan" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"'
        ' markerHeight="5" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="ah-cyan"/></marker>')
    for name, path in GLYPHS.items():
        add('<symbol id="g-%s" viewBox="0 0 12 12">%s</symbol>' % (name, path))
    add('</defs>')

    # key
    add('<text class="s-eyebrow-lg" x="42" y="32">A CELL READS SERIES / EXAMPLE, SO 10/105 IS '
        '10-FEATURE-MANAGEMENT/105-PREREQUISITE-FLAGS</text>')
    kx = 1862
    used = {g for _, _, _, choices in stages for _, g, _ in choices}
    order = ["people", "flask", "chart", "agent", "flag"]
    for name in [g for g in order if g in used]:
        label = FAMILY[name]
        kx -= len(label) * 6
        add('<text class="s-note" x="%d" y="32">%s</text>' % (kx, esc(label)))
        kx -= 15
        add('<use href="#g-%s" class="mark" x="%d" y="22" width="11" height="11"/>' % (name, kx))
        kx -= 22

    # the band above the spine
    if which == "cicd":
        add('<rect class="s-lane" x="42" y="60" width="1820" height="120" rx="12"/>')
        add('<text class="s-lane-label" x="58" y="84">ONE ARTIFACT, THREE ENVIRONMENTS</text>')
        for i, line in enumerate(["same binary everywhere",
                                  "different flag state per environment",
                                  "different people allowed to change it"]):
            add('<text class="s-claim" x="58" y="%d">%s</text>' % (108 + i * 18, line))
        for i, (px, name, gloss) in enumerate([
                (600, "dev", "flag on for everyone"),
                (1030, "test", "both variations exercised"),
                (1460, "prod", "off until released")]):
            add('<rect class="s-pill" x="%d" y="92" width="380" height="76" rx="8"/>' % px)
            add('<text class="s-pill-name" x="%d" y="120">%s</text>' % (px + 16, name))
            add('<text class="s-pill-gloss" x="%d" y="142">%s</text>' % (px + 16, gloss))
            if i < 2:
                add('<line class="s-flow" x1="%d" y1="130" x2="%d" y2="130"'
                    ' marker-end="url(#ar-ink)"/>' % (px + 386, px + 424))
        for fx, label in [(952, "same keys in each"), (1322, "released per environment")]:
            add('<line class="s-feed" x1="%d" y1="180" x2="%d" y2="250"'
                ' marker-end="url(#ar-mute)"/>' % (fx, fx))
            add('<text class="s-note" x="%d" y="220">%s</text>' % (fx + 12, label))
    else:
        for lx, label, pills, feed in [
                (180, "WHAT GOES INTO THE PROMPT",
                 [("Instructions", "the standing rules"), ("Prompts", "versioned in LD"),
                  ("Memory", "what carries over"), ("Retrieval", "fetched facts")], 490),
                (820, "WHAT THE MODEL CAN REACH",
                 [("Tools", "functions it calls"), ("MCP servers", "tools over a wire"),
                  ("Subagents", "a pipeline as a tool"), ("Data and APIs", "systems of record")],
                 1106)]:
            add('<rect class="s-lane" x="%d" y="60" width="600" height="100" rx="12"/>' % lx)
            add('<text class="s-lane-label" x="%d" y="84">%s</text>' % (lx + 16, label))
            for i, (name, gloss) in enumerate(pills):
                px = lx + 16 + i * 144
                add('<rect class="s-pill" x="%d" y="96" width="132" height="50" rx="8"/>' % px)
                add('<text class="s-pill-name" x="%d" y="117">%s</text>' % (px + 12, name))
                add('<text class="s-pill-gloss" x="%d" y="133">%s</text>' % (px + 12, gloss))
            add('<line class="s-feed" x1="%d" y1="160" x2="%d" y2="250"'
                ' marker-end="url(#ar-mute)"/>' % (feed, feed))

    # the spine
    for i, (key, title, desc, choices) in enumerate(stages):
        x = xs[i]
        add('<rect class="s-box" x="%d" y="260" width="%d" height="220" rx="10"/>' % (x, w))
        add('<rect class="s-ctrl" x="%d" y="350" width="%d" height="129"/>' % (x + 1, w - 2))
        add('<text class="s-num" x="%d" y="290">%s:</text>' % (x + 14, key))
        add('<text class="s-title" x="%d" y="290">%s</text>' % (x + 38, title))
        for j, line in enumerate(desc):
            add('<text class="s-desc" x="%d" y="%d">%s</text>' % (x + 14, 314 + j * 15, esc(line)))
        add('<line class="s-rule" x1="%d" y1="344" x2="%d" y2="344"/>' % (x + 14, x + w - 14))
        add('<text class="s-eyebrow" x="%d" y="366">CHOICE / CONTROLLED BY</text>' % (x + 14))
        for j, (choice, glyph, cap) in enumerate(choices):
            y = 382 + j * 34
            add('<text class="s-choice" x="%d" y="%d">%s</text>' % (x + 14, y, esc(choice)))
            add('<use href="#g-%s" class="mark" x="%d" y="%d" width="12" height="12"/>'
                % (glyph, x + 16, y + 5))
            add('<text class="s-cap" x="%d" y="%d">%s</text>' % (x + 31, y + 14, esc(cap)))
        if i < n - 1:
            add('<line class="s-flow" x1="%d" y1="353" x2="%d" y2="353"'
                ' marker-end="url(#ar-ink)"/>' % (x + w + 3, x + pitch - 3))

        # the second layer: citations for this stage
        add('<line class="s-cite-stem" x1="%d" y1="480" x2="%d" y2="%d"'
            ' marker-end="url(#ar-cyan)"/>' % (x + w // 2, x + w // 2, cite_y - 6))
        add('<rect class="s-cite-box" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
            % (x, cite_y, w, cite_h))
        rows = cites[key]
        total = sum(len(h) for _, h in rows)
        add('<text class="s-eyebrow" x="%d" y="%d">%d EXAMPLE%s IN THIS REPOSITORY</text>'
            % (x + 14, cite_y + 22, total, "" if total == 1 else "S"))
        for j, (series, hits) in enumerate(rows):
            y = cite_y + 42 + j * 15
            add('<text class="s-cite-series" x="%d" y="%d">%s/</text>' % (x + 14, y, series))
            tx = x + 14 + 24
            for num, stub, series_n, folder in hits:
                cls = "s-cite-stub" if stub else "s-cite-num"
                href = href_for(series_n, folder, local)
                add('<a href="%s"><title>%s/%s &#183; %s%s</title>'
                    '<text class="%s" x="%d" y="%d">%s</text></a>'
                    % (href, SERIES_DIR[series_n], folder, series_n + "/" + num,
                       " (stub)" if stub else "", cls, tx, y, num))
                tx += len(num) * 5.7 + 6
    # footer
    add('<line class="s-rule" x1="42" y1="%d" x2="1862" y2="%d"/>' % (foot_y - 20, foot_y - 20))
    add('<text class="s-note" x="42" y="%d">Muted numbers are stubs: the folder exists, '
        'the example is not built yet.</text>' % foot_y)
    add('<text class="s-note" x="42" y="%d">Baselines with no LaunchDarkly in them: %s.</text>'
        % (foot_y + 20, " · ".join(BASELINES)))
    counted = sorted({e for e, (c, l) in PLACEMENT.items()
                      if (c if which == "cicd" else l) and e in examples})
    add('<text class="s-note" x="1862" y="%d" text-anchor="end">%d of %d examples placed on '
        'this workflow</text>' % (foot_y, len(counted), len(examples)))
    add('</svg>')
    return "\n".join(s), height


# ------------------------------------------------------------- the portrait .svg
#
# The landscape figure is a 2.5:1 ribbon, which any fit-to-box viewer shrinks until the
# type is unreadable: GitHub's file preview lands it near a third of full size. Stacked
# vertically it renders at the container's full width instead, and it reads on a phone.
# Same stages, same citations, same geometry inside each box, turned ninety degrees.

P_W = 1120                 # canvas
P_MARGIN = 40
P_STAGE_W = 520            # the stage box, keeping the landscape box's internal offsets
P_CITE_W = 480
P_CITE_X = 600
P_BOX_H = 220
P_ROW_PITCH = 276          # box plus the gap the flow arrow lives in


def portrait(which, stages, examples, lede, local=False):
    """Return the <svg> for the stacked variant, plus its width and height."""
    cites = citations(stages, which, examples)
    s = []
    add = s.append

    top = 76
    if which == "cicd":
        band_h = 220
        spine_y = top + band_h + 40
    else:
        band_h = 296
        spine_y = top + band_h + 40
    spine_h = len(stages) * P_ROW_PITCH - (P_ROW_PITCH - P_BOX_H)
    foot_y = spine_y + spine_h + 48
    height = foot_y + 76

    add('<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (P_W, height, esc(lede)))
    add('<defs>')
    add('<marker id="ar-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"'
        ' markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="ah-ink"/></marker>')
    add('<marker id="ar-cyan" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"'
        ' markerHeight="5" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="ah-cyan"/></marker>')
    add('</defs>')

    # key
    add('<text class="s-eyebrow-lg" x="%d" y="32">A CELL READS SERIES / EXAMPLE, '
        'SO 10/105 IS 10-FEATURE-MANAGEMENT/105-PREREQUISITE-FLAGS</text>' % P_MARGIN)
    kx = P_W - P_MARGIN
    used = {g for _, _, _, choices in stages for _, g, _ in choices}
    for name in [g for g in ["people", "flask", "chart", "agent", "flag"] if g in used]:
        label = FAMILY[name]
        kx -= len(label) * 6
        add('<text class="s-note" x="%d" y="56">%s</text>' % (kx, esc(label)))
        kx -= 15
        add('<use href="#g-%s" class="mark" x="%d" y="46" width="11" height="11"/>'
            % (name, kx))
        kx -= 22

    inner = P_W - 2 * P_MARGIN
    if which == "cicd":
        add('<rect class="s-lane" x="%d" y="%d" width="%d" height="%d" rx="12"/>'
            % (P_MARGIN, top, inner, band_h))
        add('<text class="s-lane-label" x="%d" y="%d">ONE ARTIFACT, THREE ENVIRONMENTS</text>'
            % (P_MARGIN + 16, top + 24))
        for i, line in enumerate(["same binary everywhere",
                                  "different flag state per environment",
                                  "different people allowed to change it"]):
            add('<text class="s-claim" x="%d" y="%d">%s</text>'
                % (P_MARGIN + 16, top + 48 + i * 18, line))
        pw, gap = 310, 27
        for i, (name, gloss) in enumerate([("dev", "flag on for everyone"),
                                           ("test", "both variations exercised"),
                                           ("prod", "off until released")]):
            px = P_MARGIN + 16 + i * (pw + gap)
            add('<rect class="s-pill" x="%d" y="%d" width="%d" height="72" rx="8"/>'
                % (px, top + 118, pw))
            add('<text class="s-pill-name" x="%d" y="%d">%s</text>' % (px + 16, top + 144, name))
            add('<text class="s-pill-gloss" x="%d" y="%d">%s</text>'
                % (px + 16, top + 166, gloss))
            if i < 2:
                add('<line class="s-flow" x1="%d" y1="%d" x2="%d" y2="%d"'
                    ' marker-end="url(#ar-ink)"/>'
                    % (px + pw + 4, top + 154, px + pw + gap - 4, top + 154))
        add('<text class="s-note" x="%d" y="%d">the same flag keys in each &#183; '
            'released per environment</text>' % (P_MARGIN + 16, top + 206))
    else:
        for k, (label, pills) in enumerate([
                ("WHAT GOES INTO THE PROMPT",
                 [("Instructions", "the standing rules"), ("Prompts", "versioned in LD"),
                  ("Memory", "what carries over"), ("Retrieval", "fetched facts")]),
                ("WHAT THE MODEL CAN REACH",
                 [("Tools", "functions it calls"), ("MCP servers", "tools over a wire"),
                  ("Subagents", "a pipeline as a tool"), ("Data and APIs", "systems of record")]),
        ]):
            ly = top + k * 156
            add('<rect class="s-lane" x="%d" y="%d" width="%d" height="140" rx="12"/>'
                % (P_MARGIN, ly, inner))
            add('<text class="s-lane-label" x="%d" y="%d">%s</text>'
                % (P_MARGIN + 16, ly + 24, label))
            pw = (inner - 32 - 3 * 16) // 4
            for i, (name, gloss) in enumerate(pills):
                px = P_MARGIN + 16 + i * (pw + 16)
                add('<rect class="s-pill" x="%d" y="%d" width="%d" height="72" rx="8"/>'
                    % (px, ly + 46, pw))
                add('<text class="s-pill-name" x="%d" y="%d">%s</text>' % (px + 12, ly + 72, name))
                add('<text class="s-pill-gloss" x="%d" y="%d">%s</text>'
                    % (px + 12, ly + 94, gloss))

    # the spine, one row per stage
    for i, (key, title, desc, choices) in enumerate(stages):
        y = spine_y + i * P_ROW_PITCH
        add('<rect class="s-box" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
            % (P_MARGIN, y, P_STAGE_W, P_BOX_H))
        add('<rect class="s-ctrl" x="%d" y="%d" width="%d" height="129"/>'
            % (P_MARGIN + 1, y + 90, P_STAGE_W - 2))
        add('<text class="s-num" x="%d" y="%d">%s:</text>' % (P_MARGIN + 14, y + 30, key))
        add('<text class="s-title" x="%d" y="%d">%s</text>' % (P_MARGIN + 38, y + 30, title))
        for j, line in enumerate(desc):
            add('<text class="s-desc" x="%d" y="%d">%s</text>'
                % (P_MARGIN + 14, y + 54 + j * 15, esc(line)))
        add('<line class="s-rule" x1="%d" y1="%d" x2="%d" y2="%d"/>'
            % (P_MARGIN + 14, y + 84, P_MARGIN + P_STAGE_W - 14, y + 84))
        add('<text class="s-eyebrow" x="%d" y="%d">CHOICE / CONTROLLED BY</text>'
            % (P_MARGIN + 14, y + 106))
        for j, (choice, glyph, cap) in enumerate(choices):
            cy = y + 122 + j * 34
            add('<text class="s-choice" x="%d" y="%d">%s</text>'
                % (P_MARGIN + 14, cy, esc(choice)))
            add('<use href="#g-%s" class="mark" x="%d" y="%d" width="12" height="12"/>'
                % (glyph, P_MARGIN + 16, cy + 5))
            add('<text class="s-cap" x="%d" y="%d">%s</text>' % (P_MARGIN + 31, cy + 14, esc(cap)))

        # citations, beside the stage rather than beneath it, sized to what they hold
        rows = cites[key]
        cite_h = max(96, 30 + len(rows) * 17 + 16)
        add('<line class="s-cite-stem" x1="%d" y1="%d" x2="%d" y2="%d"'
            ' marker-end="url(#ar-cyan)"/>'
            % (P_MARGIN + P_STAGE_W + 4, y + cite_h // 2, P_CITE_X - 6, y + cite_h // 2))
        add('<rect class="s-cite-box" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
            % (P_CITE_X, y, P_CITE_W, cite_h))
        total = sum(len(h) for _, h in rows)
        add('<text class="s-eyebrow" x="%d" y="%d">%d EXAMPLE%s IN THIS REPOSITORY</text>'
            % (P_CITE_X + 14, y + 28, total, "" if total == 1 else "S"))
        for j, (series, hits) in enumerate(rows):
            ry = y + 52 + j * 17
            add('<text class="s-cite-series" x="%d" y="%d">%s/</text>'
                % (P_CITE_X + 14, ry, series))
            tx = P_CITE_X + 14 + 24
            for num, stub, series_n, folder in hits:
                cls = "s-cite-stub" if stub else "s-cite-num"
                href = href_for(series_n, folder, local)
                add('<a href="%s"><title>%s/%s &#183; %s%s</title>'
                    '<text class="%s" x="%d" y="%d">%s</text></a>'
                    % (href, SERIES_DIR[series_n], folder, series_n + "/" + num,
                       " (stub)" if stub else "", cls, tx, ry, num))
                tx += len(num) * 5.7 + 6
        if i < len(stages) - 1:
            ax = P_MARGIN + P_STAGE_W // 2
            add('<line class="s-flow" x1="%d" y1="%d" x2="%d" y2="%d"'
                ' marker-end="url(#ar-ink)"/>'
                % (ax, y + P_BOX_H + 6, ax, y + P_ROW_PITCH - 6))

    add('<line class="s-rule" x1="%d" y1="%d" x2="%d" y2="%d"/>'
        % (P_MARGIN, foot_y - 24, P_W - P_MARGIN, foot_y - 24))
    add('<text class="s-note" x="%d" y="%d">Muted numbers are stubs: the folder exists, '
        'the example is not built yet.</text>' % (P_MARGIN, foot_y))
    add('<text class="s-note" x="%d" y="%d">Baselines with no LaunchDarkly in them: %s.</text>'
        % (P_MARGIN, foot_y + 20, " \u00b7 ".join(BASELINES)))
    counted = sorted({e for e, (c, l) in PLACEMENT.items()
                      if (c if which == "cicd" else l) and e in examples})
    add('<text class="s-note" x="%d" y="%d">%d of %d examples placed on this workflow</text>'
        % (P_MARGIN, foot_y + 40, len(counted), len(examples)))
    add('</svg>')
    return "\n".join(s), P_W, height


# ---------------------------------------------------------- the standalone .svg
#
# GitHub renders a committed .svg, which is the only way to see these figures on
# github.com without turning on Pages. It renders them AS AN IMAGE, so: no external
# font loads, no dark-mode query, and the links are inert. The HTML keeps those.
# Styling therefore goes in presentation attributes rather than a <style> block or
# var() colors, the marks are inlined instead of referenced through <use>, and the
# figure carries its own light background so it stays legible on a dark theme.

MONO = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
SANS = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"
DISPLAY = "Sora, Trebuchet MS, Helvetica, Arial, sans-serif"

SVG_ATTRS = {
    # text
    "s-num": 'font-family="%s" font-size="11" fill="#6D6E71"' % MONO,
    "s-title": 'font-family="%s" font-size="15" font-weight="700" fill="#191919"' % DISPLAY,
    "s-desc": 'font-family="%s" font-size="11" fill="#414042"' % SANS,
    "s-eyebrow": 'font-family="%s" font-size="8.5" letter-spacing="0.85" fill="#6D6E71"' % MONO,
    "s-eyebrow-lg": 'font-family="%s" font-size="10" letter-spacing="1" fill="#6D6E71"' % MONO,
    "s-choice": 'font-family="%s" font-size="9.5" fill="#414042"' % MONO,
    "s-cap": 'font-family="%s" font-size="9.5" font-weight="500" fill="#2A3BA6"' % MONO,
    "s-lane-label": 'font-family="%s" font-size="10" letter-spacing="1.2" fill="#6D6E71"' % MONO,
    "s-claim": 'font-family="%s" font-size="10" fill="#414042"' % MONO,
    "s-pill-name": 'font-family="%s" font-size="15" font-weight="700" fill="#191919"' % DISPLAY,
    "s-pill-gloss": 'font-family="%s" font-size="9.5" fill="#6D6E71"' % MONO,
    "s-note": 'font-family="%s" font-size="10" fill="#6D6E71"' % MONO,
    "s-cite-series": 'font-family="%s" font-size="9.5" font-weight="500" fill="#6D6E71"' % MONO,
    "s-cite-num": 'font-family="%s" font-size="9.5" font-weight="500" fill="#2A3BA6"' % MONO,
    "s-cite-stub": 'font-family="%s" font-size="9.5" fill="#6D6E71"' % MONO,
    # shapes, with every translucent fill flattened onto the background it sits on
    "s-box": 'fill="#FFFFFF" stroke="#D1D6D9" stroke-width="1.25"',
    "s-ctrl": 'fill="#F4F5FF" stroke="none"',
    "s-lane": 'fill="#F2F2F2" stroke="#D1D6D9" stroke-width="1.25" stroke-dasharray="5 4"',
    "s-pill": 'fill="#F1F2F7" stroke="#D1D6D9" stroke-width="1"',
    "s-cite-box": 'fill="#EBF6F8" stroke="#9AE7F6" stroke-width="1"',
    "s-rule": 'stroke="#D1D6D9" stroke-width="1" fill="none"',
    "s-flow": 'stroke="#191919" stroke-width="1.5" fill="none"',
    "s-feed": 'stroke="#6D6E71" stroke-width="1.25" fill="none" stroke-dasharray="4 4"',
    "s-cite-stem": 'stroke="#3DD6F5" stroke-width="1.25" fill="none"',
    "mark": ('stroke="#414042" stroke-width="1.3" fill="none" stroke-linecap="round"'
             ' stroke-linejoin="round"'),
    "ah-ink": 'fill="#191919"', "ah-mute": 'fill="#6D6E71"', "ah-cyan": 'fill="#3DD6F5"',
}


def standalone(svg, width, height):
    """Turn a generated <svg> into a self-contained file GitHub can render."""
    def glyph(m):
        name, x, y, w = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
        scale = w / 12.0
        return ('<g transform="translate(%g, %g) scale(%g)" stroke="#414042"'
                ' stroke-width="%.2f" fill="none" stroke-linecap="round"'
                ' stroke-linejoin="round">%s</g>'
                % (x, y, scale, 1.3 / scale, GLYPHS[name]))

    svg = re.sub(r'<use href="#g-(\w+)" class="mark" x="([\d.]+)" y="([\d.]+)"'
                 r' width="([\d.]+)" height="[\d.]+"/>', glyph, svg)
    svg = re.sub(r'<symbol id="g-\w+".*?</symbol>', "", svg)
    for name, attrs in SVG_ATTRS.items():
        svg = svg.replace('class="%s"' % name, attrs)
    assert 'class="' not in svg, "a class survived the attribute pass"
    svg = svg.replace(
        "<svg viewBox=",
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ' width="%d" height="%d" viewBox=' % (width, height), 1)
    svg = svg.replace(
        ">\n<defs>",
        '>\n<rect x="0" y="0" width="%d" height="%d" fill="#F8F8F8"/>\n<defs>'
        % (width, height), 1)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + svg + "\n"


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s &middot; lunch-marcoly</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700&amp;family=Inter:wght@400;500;600&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap">
<style>
  /* Generated by diagrams/build.py. Edit that, not this file. */
%(palette)s
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--ui);
         font-size: 15px; line-height: 1.55; }
  .wrap { max-width: 1820px; margin: 0 auto; padding: 56px 16px 80px;
          display: flex; flex-direction: column; gap: 40px; }
  header { max-width: 1240px; }
  .eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: 0.14em;
             text-transform: uppercase; color: var(--muted); margin: 0 0 14px; }
  h1 { font-family: var(--display); font-weight: 700; font-size: clamp(32px, 5vw, 52px);
       letter-spacing: -0.03em; line-height: 1.02; margin: 0 0 20px; text-wrap: balance; }
  .lede { font-size: 19px; color: var(--ink-2); margin: 0; max-width: 78ch; }
  .lede a { color: var(--blue-ink); }
  .scroller { overflow-x: auto; }
  .scroller svg { display: block; min-width: 1520px; width: 100%%; height: auto; }
  figure { margin: 0; }
  figcaption { color: var(--muted); font-size: 13px; margin-top: 14px; max-width: 92ch; }
  .hint { display: none; font-family: var(--mono); font-size: 11px; color: var(--muted);
          margin-bottom: 10px; }
  @media (max-width: 1620px) { .hint { display: block; } }

  svg text { font-family: var(--ui); }
  .s-num { font-family: var(--mono); font-size: 11px; fill: var(--muted); }
  .s-title { font-family: var(--display); font-weight: 700; font-size: 15px; fill: var(--ink);
             letter-spacing: -0.02em; }
  .s-desc { font-size: 11px; fill: var(--ink-2); }
  .s-eyebrow { font-family: var(--mono); font-size: 8.5px; letter-spacing: 0.1em;
               fill: var(--muted); }
  .s-eyebrow-lg { font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
                  fill: var(--muted); }
  .s-choice { font-family: var(--mono); font-size: 9.5px; fill: var(--ink-2); }
  .s-cap { font-family: var(--mono); font-size: 9.5px; font-weight: 500; fill: var(--blue-ink); }
  .s-lane-label { font-family: var(--mono); font-size: 10px; letter-spacing: 0.12em;
                  fill: var(--muted); }
  .s-claim { font-family: var(--mono); font-size: 10px; fill: var(--ink-2); }
  .s-pill-name { font-family: var(--display); font-weight: 700; font-size: 15px; fill: var(--ink);
                 letter-spacing: -0.02em; }
  .s-pill-gloss { font-family: var(--mono); font-size: 9.5px; fill: var(--muted); }
  .s-note { font-family: var(--mono); font-size: 10px; fill: var(--muted); }
  .s-cite-series { font-family: var(--mono); font-size: 9.5px; font-weight: 500;
                   fill: var(--muted); }
  .s-cite-num { font-family: var(--mono); font-size: 9.5px; font-weight: 500;
                fill: var(--blue-ink); }
  .s-cite-stub { font-family: var(--mono); font-size: 9.5px; fill: var(--muted); }
  svg a { cursor: pointer; }
  svg a:hover text { fill: var(--blue); text-decoration: underline; }
  svg a:focus-visible text { fill: var(--blue); outline: 2px solid var(--blue);
                             outline-offset: 2px; }

  .s-box { fill: var(--surface); stroke: var(--line); stroke-width: 1.25; }
  .s-ctrl { fill: var(--ctrl-fill); stroke: none; }
  .s-lane { fill: var(--lane); stroke: var(--line); stroke-width: 1.25; stroke-dasharray: 5 4; }
  .s-pill { fill: var(--chip); stroke: var(--line); stroke-width: 1; }
  .s-cite-box { fill: var(--cite-fill); stroke: var(--cite-line); stroke-width: 1; }
  .s-rule { stroke: var(--line); stroke-width: 1; }
  .s-flow { stroke: var(--ink); stroke-width: 1.5; fill: none; }
  .s-feed { stroke: var(--muted); stroke-width: 1.25; fill: none; stroke-dasharray: 4 4; }
  .s-cite-stem { stroke: var(--cyan); stroke-width: 1.25; fill: none; }
  .mark { stroke: var(--ink-2); stroke-width: 1.3; fill: none; stroke-linecap: round;
          stroke-linejoin: round; }
  .ah-ink { fill: var(--ink); } .ah-mute { fill: var(--muted); } .ah-cyan { fill: var(--cyan); }
</style>

<div class="wrap">
  <header>
    <p class="eyebrow">lunch-marcoly</p>
    <h1>%(title)s</h1>
    <p class="lede">%(lede)s</p>
  </header>
  <figure>
    <p class="hint">Scroll the figure sideways &rarr;</p>
    <div class="scroller">
%(svg)s
    </div>
    <figcaption>%(caption)s</figcaption>
  </figure>
</div>
</html>
"""

PAGES = {
    "cicd-pipeline.html": dict(
        title="Anatomy of a CI/CD Pipeline",
        stages=CICD, which="cicd",
        lede=("Five stages, from a pull request to a retired flag, with the choice each stage "
              "hides and the LaunchDarkly capability that owns it. Beneath every stage sits a "
              "second box naming the examples in this repository that demonstrate it, so a "
              "stage you care about leads straight to runnable code."),
        caption=("Generated from the repository by <code>diagrams/build.py</code>. A citation "
                 "reads series/example: <code>10/105</code> is "
                 "<code>10-feature-management/105-prerequisite-flags</code>. An example that "
                 "fits more than one stage is cited at each of them."),
    ),
    "llm-workflow.html": dict(
        title="Anatomy of an LLM Workflow",
        stages=LLM, which="llm",
        lede=("Six steps, from an incoming request to a checked answer, with the runtime choice "
              "each step hides and the LaunchDarkly capability that owns it. Beneath every step "
              "sits a second box naming the examples in this repository that demonstrate it, so "
              "a step you care about leads straight to runnable code."),
        caption=("Generated from the repository by <code>diagrams/build.py</code>. A citation "
                 "reads series/example: <code>20/204</code> is "
                 "<code>20-agent-management/204-agent-judges</code>. An example that fits more "
                 "than one step is cited at each of them."),
    ),
}


def main():
    check_only = "--check" in sys.argv
    local = "--local" in sys.argv
    examples = scan()

    unmapped = sorted(e for e in examples if e not in PLACEMENT)
    ghosts = sorted(e for e in PLACEMENT if e not in examples)
    placed = {e for e, (c, l) in PLACEMENT.items() if (c or l) and e in examples}
    unplaced = sorted(e for e in examples if e in PLACEMENT and e not in placed)

    print("%d numbered examples on disk, %d stubs"
          % (len(examples), sum(1 for v in examples.values() if v[1])))
    if unmapped:
        print("UNMAPPED, add to PLACEMENT: " + ", ".join(unmapped))
    if ghosts:
        print("in PLACEMENT but not on disk: " + ", ".join(ghosts))
    if unplaced:
        print("mapped to no stage on purpose: " + ", ".join(unplaced))
    if check_only:
        return 1 if (unmapped or ghosts) else 0

    for name, spec in PAGES.items():
        svg, height = figure(spec["which"], spec["stages"], examples, spec["lede"], local)
        page = PAGE % dict(title=spec["title"], lede=spec["lede"], caption=spec["caption"],
                           palette=PALETTE, svg=svg)
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(page)
        tall, pw, ph = portrait(spec["which"], spec["stages"], examples, spec["lede"], local)
        flat = name.replace(".html", ".svg")
        open(os.path.join(OUT, flat), "w", encoding="utf-8").write(standalone(tall, pw, ph))
        print("wrote diagrams/%s (1904 x %d, landscape) and diagrams/%s (%d x %d, portrait)"
              " · %s links" % (name, height, flat, pw, ph,
                               "relative" if local else "github.com"))
    return 1 if (unmapped or ghosts) else 0


if __name__ == "__main__":
    sys.exit(main())
