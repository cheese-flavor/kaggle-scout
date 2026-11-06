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

## v0.7.0 · Trash, readable metadata, personal headings

Actual fixture captures: `docs/dashboard-v070.png`, `docs/bookmarks-v070.png`, `docs/education-v070.png`, and settings at 1180 × 820; education at 960 × 680; `docs/trash-v070.png` at 740 × 590. These use a synthetic display name and an isolated database. The captured profile page is scrolled to the name/hardware controls. Previous release images remain intact.

The main heading is “대회 탐색.” Interest headings use a configured display name, an already-stored Kaggle username, or “관심 대회.” Long names are elided while retaining the functional suffix, with full text in a tooltip. The sidebar name is also elided so it cannot enlarge the minimum window. Headings and empty-state classifications use nouns.

Card titles remain 24px. Description/date increase to 17px, topic to 14px, and D-day to 18px bold. Topic and date occupy separate rows to prevent narrow-window collisions. The normal and minimum captures, personalized interest page, recovery dialog and name settings were opened and inspected. Primary actions and enlarged date badges remain unobstructed in those captures.

84 tests pass. New coverage includes concurrent sync/expiry suppression, KST calendar-day expiry (rather than a 24-hour offset), expiry at midnight, unknown deadlines, updated deadlines, resync suppression, tombstone retention, legacy schema migration, cancelled pending alerts, restart cleanup, UI restoration/bookmarks, cancelled nonrecoverable deletion, display-name priority, token non-disclosure and long names at 960 × 680. This does not establish high-DPI or full assistive-technology compliance.

v0.7.0 packaged verification: clean build and installed executable both render and exit normally with isolated data. Shortcut and executable metadata point to 0.7.0. User DB existence and SHA256 remain unchanged after installation; schema migration is exercised by legacy-database tests and occurs at the next real launch.

## v0.8.0 · Semantic color and compact tray

Current-run Qt fixture captures include normal discovery/bookmarks/settings at 1180 × 820, education at 960 × 680, urgency examples at 1180 × 1058 and the actual compact two-action QMenu at 74 × 64 pixels in this environment. The discovery, bookmark, minimum education, recovery, notification and urgency captures were opened and inspected. All contain synthetic data. The selected v0.5.0 structure remains, with the color changes requested in v0.8.0; this is not an attempt to reproduce the old palette.

General selection is blue, bookmarks violet, education/recovery teal, imminent deadlines amber/red, image topics rose, LLM indigo and neutral dates slate. Labels/icons/countdowns remain present alongside color. The icon used for audio is the pinned Lucide audio-lines asset. Disabled actions retain neutral styling. The compact tray menu contains only app open and quit; manual refresh remains in the main window.

All eight semantic ink/surface pairs were calculated at approximately 5.30–6.25:1 (rounded to two decimals). Primary text pairs also exceed 4.5:1. The measured RGB tokens are in `docs/color-contrast-v080.json`. This checks token contrast, not every antialiased pixel or full accessibility compliance.

85 tests pass, including a new tray interaction check that opens the window, calls quit, and does not refresh. Notification target/time/queue semantics are unchanged; the settings now explain new recommendations versus bookmarked changes/deadlines. Actual Windows notification delivery, another display's DPI and assistive technologies remain outside this validation scope.

v0.8.0 packaged verification: clean build starts, renders and exits normally with isolated preview data. The packaged empty state was inspected. After the user closed v0.7.0, local v0.8.0 installation completed. The installed executable also renders and exits normally with isolated data. Desktop and Start menu shortcuts and executable metadata resolve to 0.8.0; user DB existence and SHA256 remain unchanged after installation.

## v0.8.1 · A single location for competition actions

Current fixture captures: `docs/dashboard-v081.png`, `docs/bookmarks-v081.png` (1180 × 820), and `docs/education-small-v081.png` (960 × 680). List bookmark/delete buttons are removed. Summary and full-information share the existing detail footer actions, and the same actions remain directly visible at the minimum size. More contains information/rules actions at compact size; duplicate bookmark/delete menu entries are removed. Legacy hidden entries still expose an unhide action.

The first minimum-size pass clipped the bookmark label; reducing horizontal padding in the compact footer resolved it. The final 960 × 680 capture was opened and inspected with both labels readable and the primary action unobstructed. Normal discovery and bookmark captures were also inspected. The existing 85 regression checks pass, including compact information switching and bookmark/deletion/restore behavior. No new screenshot-only test was added for this layout change.

v0.8.1 direct interaction check: no QPushButton remains in list cards; the common footer toggles bookmarks from summary and full information and deletes into trash at compact size. Clean build and installed executable both render and exit normally in isolated preview data. Shortcuts and metadata resolve to 0.8.1; existing user DB existence and SHA256 remain unchanged after installation.

## v0.9.0 · One full-information document

Actual current fixture captures: `docs/dashboard-v090.png`, `docs/detail-information-v090.png`, `docs/bookmarks-v090.png` at 1180 × 820; minimum education at 960 × 680; deadline examples at 1180 × 1058. The first and scrolled detail views, minimum window and deadline state were opened and inspected. These use fictional data; no real account is captured. Existing gallery images remain unchanged.

The summary/full tabs and their More actions are removed. One escaped rich-text document presents the title/topic/description, highlighted final deadline, calendar dates, participation/submission metadata, eligibility/GPU/API, recommendation reasons, exclusions, additional rules and last-check record. Labels and values occupy separate columns; values/body are 17px, labels 14px, section titles 18px. Word-boundary-or-anywhere wrapping prevents long unbroken text from forcing horizontal clipping. The existing footer actions remain directly accessible and separate from scrolling content.

89 regression checks pass. Four new checks verify preservation of supplied metadata and a zero team count, escaped external markup, explicit education/exclusion/unknown states, and bookmark reading-position retention plus reset on selecting another competition. The former compact-view test now checks all information without a view switch. Token privacy, real-account permissions, another display's DPI and full accessibility compliance are not inferred from these captures.

v0.9.0 packaged verification: clean build starts/renders/exits successfully with isolated preview data. Installation is pending the running v0.8.1 app closing.
