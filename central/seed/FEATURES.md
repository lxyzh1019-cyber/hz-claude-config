<!-- feature-list: by-screen -->
# FEATURES — <app or plan name> — manifest v1 — confirmed <date>

Locked features of the current version, one section per screen. Each line says what you see or what it does, then its proof: a test name or a reference picture (`tests/reference/<screen>-<phone|ipad|pc>.png`). Every edit is checked against this list and ends with a regression table whose Kept row names its proof. Update this file in the same change that alters a feature. History stays in git and `docs/archive/`, not here.

## <Screen, e.g. Today>
- <what you see or what it does — one line> — Proof: <test name | picture tests/reference/today-phone.png>

## <Screen, e.g. Settings>
- … — Proof: …

## Data and rules
- <rule — one line> — Proof: <test name>

## References
- Sizes: <e.g. phone 390×844, iPad 1194×834> · Looks: <e.g. Pop, Calm — or one look>
- <figure or rule document the comparisons and tests must cover — one line each>

## Regression table (paste at the end of every edit)
| Regression table | Result |
|---|---|
| Kept | <n> features · Proof: pictures <n> screens × <sizes> sizes, <k> changed (all planned) · tests <passed>/<total> |
| Added | … |
| Intentionally removed | … |
| Missing | … |
