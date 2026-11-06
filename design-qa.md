# Design QA · v0.5.0

Final result: **passed for the documented native Qt scope**.

## Reference and evidence

- Selected reference: `docs/design-exploration-v050/option-1.png`.
- Final implementation: `docs/design-qa-v050/implementation.png`.
- Same-size comparison: `docs/design-qa-v050/comparison-final.png`; both source images are 1487 × 1058 pixels, with no crop or scaling before assembly.
- Default window: `docs/dashboard-final-v050.png` (1180 × 820).
- Minimum window: `docs/design-qa-v050/small-window.png` (960 × 680).
- Settings: `docs/settings-v050.png` and `docs/notifications-v050.png`.
- Captures use local, fictional competition fixtures. No account credentials or private records are shown.

The app is PySide6, so verification used actual Qt widgets and QtTest rather than a browser reconstruction. Source and implementation were opened together; the minimum window and settings were also inspected separately.

## Findings and resolution

The first pass had undersized type and overlapping detail actions at the minimum height (P2). The final pass increases body and card-title sizes and moves secondary actions into a More menu below 760px height. The post-fix minimum-window capture has a separate scrollable detail area and unobstructed actions. No unresolved P0–P2 finding remains in the captured views.

| Surface | Result |
|---|---|
| Layout | Narrow icon rail, capsule search, topic chips, selected cyan list item, and right detail panel follow option 1. Default and minimum sizes remain usable. |
| Typography | Bundled Pretendard with consistent title, body, and muted hierarchy; Korean titles wrap within the card. |
| Color and state | Pale background, navy text, cyan selection/primary action, purple NLP and mint time-series accents; disabled actions and keyboard focus remain visible. |
| Assets | Existing Kaggle Scout app identity and local licensed Lucide SVGs. Icons render without network access. |
| Copy and behavior | Fixture mode is labeled. Summary/full information, pagination, exclusions, bookmark, rule lookup, notification preferences, and account controls remain available. |

## Intentional adaptations

This is a faithful adaptation of the selected direction, not a pixel-identical reproduction of the generated concept. The existing Kaggle Scout name and logo replace “Pocket Calm.” Header spacing is denser for the requested smaller PC window, surfaces use flat colors rather than glow, and real pagination/filter/status controls remain. The detail panel includes actual rule-based reasons and unconfirmed eligibility rather than invented suitability claims. These decisions are recorded in `DESIGN_SYSTEM.md`.

## Functional checks and limits

`python -m unittest -q`: **51 tests passed**. New checks cover recommended/all/LLM–NLP chips, keyboard card selection, independent bookmarking, shared settings across tabs, local icon rendering, and compact-window controls. Existing collection, exclusion, notification, storage, and safety regression checks also pass.

This does not establish full accessibility compliance, high-DPI behavior on another display, real-account permissions, or delivery of Windows notifications. Those remain separate verification items in `ROADMAP.md`.

Packaged verification: clean PyInstaller build and installed v0.5.0 both render the native GUI and exit successfully with isolated preview data. The packaged empty state was visually inspected. Desktop shortcut and executable metadata point to 0.5.0; user DB existence and SHA256 remain unchanged after installation.
