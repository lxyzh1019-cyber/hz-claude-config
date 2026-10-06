# Compare instructions (central, v3.1.30) — for workers whose task changes what the app shows or computes

Catch drift before the owner sees the build: compare the build with its reference in code, and look only at what differs. This file is general; each app names its own references in its `FEATURES.md` section `## References` (for example which figures to compare and which rule documents its tests must cover).

**When.** The task changes anything the owner sees, or figures the app computes or stores. Other tasks skip this file.

**References.**
- Screens: the approved mockup or prototype for a planned change; for every other screen, the same screen before the change. Reference pictures live in the app's `tests/reference/` as `<screen>-<phone|ipad|pc>.png`.
- Three sizes, always: phone 390×844, iPad 820×1180, PC 1440×900.
- Figures: the values the app shows for the same inputs before the change, as listed in the app's `## References`.

**Steps.**
1. Before you change anything, take the "before" pictures of every screen at the three sizes with the app's picture test, and save the figures named in `## References`.
2. After the change, take the "after" pictures and figures the same way.
3. Compare in code: a pixel compare with a small tolerance for pictures, an exact compare for figures. Do not open pictures of screens that did not change.
4. Each changed screen or figure must be in the plan. An unplanned change is a bug: fix it. A planned change is compared with its approved mockup; every difference the owner has not approved becomes a picture pair (mockup and build side by side, numbered) for the main session to ask about.
5. A planned change updates its reference pictures in the same pull request.
6. If the app has no picture test or no `## References` yet, say so in the report as a blocker; adding them is its own stage.

**Report line** (the regression table's Kept row and the reviewer use it):
`Proof: pictures <n> screens × 3 sizes, <k> changed (all planned) · figures <n> match, <m> changed by plan · tests <passed>/<total>`
