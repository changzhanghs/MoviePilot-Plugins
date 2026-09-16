# Design QA

## Evidence

- Source visual truth: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-7d379452-577c-43e6-a7b2-dea7419276fb.png` (1141 × 789).
- Implementation screenshot: `C:\codex\站点数据\plugins.v2\ptdatastatistics\qa-dashboard-final.png` (1141 × 789; temporary QA artifact removed after verification).
- Side-by-side comparison: `C:\codex\站点数据\plugins.v2\ptdatastatistics\qa-dashboard-comparison.png` (2298 × 837; temporary QA artifact removed after verification).
- Viewport: 1141 × 789 CSS pixels at device scale 1.
- Component frame: 1035 × 696 CSS pixels at x=73, y=57, matching the source crop.
- State: dark theme; three active sites; API-shaped mock data; normal loaded state.
- Reported regression capture: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-392e2f82-1fde-4d18-a413-90c882355a2b.png` (1080 × 784), showing the unintended stacked layout in MoviePilot.
- User comparison composite: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-26ebf06c-7e39-4ee1-a4e2-0a40b5f8527f.png` (1308 × 1550), with the oversized stacked production state above and the intended compact two-column state below.
- Responsive implementation capture: Codex in-app Browser at `http://127.0.0.1:4173/qa.html`, 590 × 480 component state inside the available browser surface, verified with seven active sites.

## Full-view comparison evidence

- The title/divider, three summary capsules, left donut, and three right-hand site rows occupy the same primary regions as the reference.
- The component frame measured exactly 1035 × 696 with no horizontal or vertical document overflow.
- Site rows start within 3 px of the source vertically and 1 px horizontally; the donut aligns to the source left edge and vertical center.
- User-directed differences from the source are intentional: the title is `今日流量`, the title uses an `mdi-finance` statistics icon, and the date capsule is first.
- The user comparison composite confirms the required responsive proportions: approximately 210 px rendered donut, 78 px rendered summary capsules, and 90 px rendered site rows after MoviePilot scaling.

## Focused region comparison evidence

- Summary capsules reproduce the 80 px height, full-pill radius, icon medallion, two-line label/value structure, and equal-width three-column rhythm.
- Site rows reproduce the 90 px height, bordered surface, fixed upload/download capsules, and compact contribution pill.
- The donut uses the source's bright-green dominant segment, centered count, and matching 210 px diameter.

## Findings

- No actionable P0, P1, or P2 mismatch remains.
- Fonts and typography: MoviePilot/Vuetify typography is retained; title, labels, values, and tabular numerals preserve the source hierarchy without wrapping.
- Spacing and layout rhythm: header divider, three-column summary, left/right split, row heights, gaps, padding, and radii match the reference structure.
- Colors and visual tokens: host surface/border tokens remain theme-safe; the donut uses a local bright-green dashboard palette to match the source.
- Image quality and asset fidelity: production continues to use MoviePilot's real site avatars and MDI icons. The standalone QA harness showed text fallbacks only because it did not call the host icon endpoint.
- Copy and content: `今日流量`, `今天 00:00 起`, `统计时间`, `上传增量`, and `下载增量` match the final user instructions.
- Responsive behavior: 481–820 px uses a compact two-column layout; only 480 px and below stacks the content. At 590 px, the title, donut, summaries, avatars, rows, and metrics use compact sizing.
- Overflow behavior: the station list alone scrolls vertically when more rows exist, while the title, donut, and summary capsules remain fixed. The seven-site QA state visibly exposed the thin scrollbar and clipped no persistent controls.

## Comparison history

- Pass 1 finding: the right-hand summary and site list were vertically centered too low, while cards were too compact.
- Fix: top-align the detail column and set summary/site row heights to 80/90 px.
- Pass 2 finding: the donut was 9 px right and 13 px low; metric capsules were too narrow and too far right.
- Fix: left-align and vertically offset the donut, then use fixed 126 px traffic capsules and an 80 px contribution track.
- Pass 3 finding: summary icons and contribution values lacked the source's pill/medallion treatment.
- Fix: add circular icon surfaces and compact contribution pills; the final comparison showed no remaining P0/P1/P2 issue.
- Pass 4 finding: MoviePilot reported a roughly 690 px effective container that crossed the old 700 px breakpoint, stacking the donut above oversized content.
- Fix: add a compact 481–820 px two-column mode, reduce its title, donut, summary, avatar, row, and metric sizes, and defer stacking until 480 px. The in-app Browser at 590 px confirmed the intended left-donut/right-data structure with all rows visible.
- Pass 5 finding: a fixed-height dashboard with more site rows had no vertical navigation because the root clipped overflow.
- Fix: make only the site list keyboard-focusable and vertically scrollable, add a thin themed scrollbar, and retain natural page scrolling below 480 px. The seven-site capture confirmed multiple visible rows and an active list scrollbar.

## Implementation checklist

- [x] Match the reference card frame and header divider.
- [x] Place the date first, followed by upload and download totals.
- [x] Align the donut and right-side content to the reference grid.
- [x] Match capsule and site-row dimensions.
- [x] Add the finance statistics icon and final Chinese copy.
- [x] Preserve responsive behavior without an internal scrollbar.
- [x] Preserve the two-column structure in MoviePilot's scaled medium-width dashboard slot.
- [x] Restore vertical scrolling for long site lists without moving the summary area.

## Follow-up polish

- Production avatars will be visually richer than the standalone QA fallbacks because MoviePilot supplies the actual site icons.

final result: passed
