# Design QA

## Evidence

- Source visual truth:
  - `C:\Users\cz\AppData\Local\Temp\codex-clipboard-8a42a283-b420-4e64-87e0-28a7b25d23fb.png` (1285 × 689)
  - `C:\Users\cz\AppData\Local\Temp\codex-clipboard-31b1261e-a88d-40de-8863-4ea6f6c29073.png` (1549 × 326)
  - `C:\Users\cz\AppData\Local\Temp\codex-clipboard-aa0d68b7-49b1-4515-b2b3-6f0e057c6761.png` (450 × 187)
  - `C:\Users\cz\AppData\Local\Temp\codex-clipboard-3ae1f234-20af-4221-befa-dd16f3964d4c.png` (2075 × 256)
- Implementation capture: Codex in-app Browser at `http://127.0.0.1:4173/qa.html`, using a temporary local mock-data harness that was removed after verification.
- Viewport: 1565 × 900 CSS pixels at device scale 1.
- State: dark theme; overview metrics, dashboard with two active sites, normal retirement route, and wealthy-retirement sidebar entry.

## Full-view comparison evidence

- The overview metric row contains only each title and its primary value; no helper text nodes remain.
- The dashboard root resolves to the Vuetify surface color instead of a transparent background.
- Both dashboard site rows resolve to the same five-column grid, and each of the three data columns measures 214 px in the verification viewport.
- The retirement route keeps the existing rail, marker, badge, and date layout.

## Focused region comparison evidence

- Route labels render Chinese and English as separate child rows. Browser measurements placed the two rows at distinct vertical positions (14 px apart) for all four sampled levels.
- The removed upgrade helper sentence is absent from rendered text.
- The wealthy-retirement sidebar entry contains no inline title status, while its right-hand status remains `富贵养老`.
- The overview contains zero `.metric-card .text-truncate` helper rows.

## Findings

- No actionable P0, P1, or P2 mismatch remains for the requested regions.
- Fonts and typography: existing MoviePilot/Vuetify typography is preserved; only the bilingual level label gains a controlled second line.
- Spacing and layout rhythm: metric columns are equal-width and numeric values use tabular figures; existing card padding and radii are unchanged.
- Colors and visual tokens: the dashboard background now uses `--v-theme-surface`, matching the adjacent surface treatment.
- Image quality and asset fidelity: existing site avatars and Vuetify icons are unchanged; no replacement assets were introduced.
- Copy and content: helper metric text and the requested upgrade sentence are removed; the right-hand wealthy-retirement label is retained.

## Comparison history

- Initial findings: transparent dashboard background, uneven metric columns, bilingual level names wrapping inconsistently, duplicated wealthy-retirement status, and unwanted helper copy.
- Fixes made: surface background token, three equal metric tracks, explicit bilingual label rows, conditional suppression of the duplicate status, and removal of helper copy.
- Post-fix evidence: browser-computed layout and rendered text checks above; no remaining P0/P1/P2 issue in the changed regions.

## Implementation checklist

- [x] Match dashboard background to the surrounding surface.
- [x] Use equal-width upload, download, and share columns.
- [x] Split Chinese and English level labels into two rows.
- [x] Remove the upgrade helper sentence.
- [x] Keep only the right-side wealthy-retirement status in the site card.
- [x] Remove overview metric helper text.

## Follow-up polish

- None required for this scope.

final result: passed
