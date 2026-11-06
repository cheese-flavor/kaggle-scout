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

## v0.6.0 · Educational competitions

Actual fixture captures: `docs/dashboard-v060.png`, `docs/education-v060.png`, `docs/collection-settings-v060.png` (1180 × 820), and `docs/education-small-v060.png` (960 × 680). The app retains the selected v0.5.0 design, with a general/education switch below search. Existing screenshots remain unchanged in the version gallery.

The first compact capture left too little detail space after adding the group switch. Summary/full-information controls now move into More below 760px height, preserving title/description and the primary action. The final compact capture and the normal education/settings captures were opened and checked; no overlapping controls were found in those views. Long practice deadlines retain the API date with a “장기 운영” label instead of a very large countdown.

63 tests pass, including classification evidence, long-deadline false positives, legacy profile defaults, storage retention, notification opt-in and queued-alert checks, group/filter/pagination behavior, education bookmarking, exclusion navigation, imported settings and compact information access. High-DPI and full accessibility limitations above still apply.

v0.6.0 packaged verification: both clean build and installed executable start/render/exit successfully with isolated data. The packaged empty state was inspected. Shortcut and executable metadata resolve to 0.6.0. Existing user DB existence and SHA256 are unchanged after installation.
