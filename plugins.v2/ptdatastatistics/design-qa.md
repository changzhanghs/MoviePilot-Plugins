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
- Current proportion/glass reference: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-417c836f-5ad5-4fc4-8a4b-d34e3a5cbbc5.png` (2162 × 840), comparing the compact fixed-height rows with the incorrectly stretched rows.
- Current implementation capture: Codex in-app Browser at `http://127.0.0.1:4173/qa.html`, 1141 × 789 viewport with three active sites.
- Fidelity/data reference: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-1f91824f-4aad-485b-aed8-e181486e9b29.png` (2119 × 759), comparing the desired dark glass surfaces and binary capacity values with the prior bright cards and decimal values.
- Current fidelity capture: Codex in-app Browser at `http://127.0.0.1:4173/qa.html`, 1060 × 760 viewport with four active sites and the same capacity values as the reference.

## Full-view comparison evidence

- The title/divider, three summary capsules, left donut, and three right-hand site rows occupy the same primary regions as the reference.
- The component frame measured exactly 1035 × 696 with no horizontal or vertical document overflow.
- Site rows start within 3 px of the source vertically and 1 px horizontally; the donut aligns to the source left edge and vertical center.
- User-directed differences from the source are intentional: the title is `今日流量`, the title uses an `mdi-finance` statistics icon, and the date capsule is first.
- The user comparison composite confirms the required responsive proportions: approximately 210 px rendered donut, 78 px rendered summary capsules, and 90 px rendered site rows after MoviePilot scaling.

## Focused region comparison evidence

- Summary capsules reproduce the 80 px height, full-pill radius, icon medallion, two-line label/value structure, and equal-width three-column rhythm.
- Site rows reproduce the 90 px height, bordered surface, fixed upload/download capsules, and compact contribution pill.
- Computed browser measurements confirm all three site rows remain exactly 90 px tall inside a 503 px list area; unused height stays blank instead of being redistributed into the rows.
- Summary capsules and site rows use translucent host-theme surfaces, 16–18 px backdrop blur, mild saturation, an inset highlight, and a restrained shadow for the requested glass treatment.
- Browser output confirms the reference values now render as `14.43 GB` total, `10.00 GB` and `4.35 GB` per site under the unified binary conversion.
- Site names render at 16 px / weight 700 in the host foreground color; summary values use weight 700 and the same foreground color.
- The upload, download, and contribution controls form a fixed-width group aligned to the right edge of every site row.
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
- Pass 6 finding: CSS Grid stretched three site rows to consume the entire available list height, making the card proportions depend on the dashboard height.
- Fix: top-align the grid tracks and use fixed 90 px desktop / 60 px compact row tracks, while retaining natural-height rows below 480 px. The 1141 × 789 browser capture and computed styles confirmed fixed row heights and the requested glass surface treatment.
- Pass 7 finding: `surface-variant` produced opaque-looking light gray cards in MoviePilot, capacity values used decimal 1000 conversion, and typography/alignment remained lighter than the reference.
- Fix: use a 4% theme-foreground translucent glass surface, unify all plugin capacity conversion to 1024, increase summary/site-name typography, and pin the three row metrics to the right. Browser measurements confirmed 126/126/80 px right-aligned controls and no console warnings or errors.
- Pass 8 finding: the two dominant donut segments used adjacent green hues and visually merged; repeated backdrop filters on scrolling rows and nested metric pills could produce GPU compositing flicker; traffic values and arrows retained semantic colors.
- Fix: use a high-contrast green/blue/amber/purple dashboard palette, remove blur layers from repeated scrolling surfaces while retaining translucent fills, borders, inset highlights, and shadows, and use the host foreground color for every traffic value and arrow, including all three top summary cards. Browser computed styles confirmed four distinct donut segments, `backdrop-filter: none` on rows and metric pills, white metric text/icons, and no console warnings or errors.

## Implementation checklist

- [x] Match the reference card frame and header divider.
- [x] Place the date first, followed by upload and download totals.
- [x] Align the donut and right-side content to the reference grid.
- [x] Match capsule and site-row dimensions.
- [x] Add the finance statistics icon and final Chinese copy.
- [x] Preserve responsive behavior without an internal scrollbar.
- [x] Preserve the two-column structure in MoviePilot's scaled medium-width dashboard slot.
- [x] Restore vertical scrolling for long site lists without moving the summary area.
- [x] Prevent site rows from stretching with the dashboard card height.
- [x] Apply a theme-safe glass treatment to summary and site data surfaces.
- [x] Unify dashboard, workbench, history, notification, export, and rule capacity values on binary conversion.
- [x] Match the reference typography and right-aligned row metrics.
- [x] Distinguish real traffic categories and eliminate scrolling-card compositing flicker.
- [x] Use white traffic text and arrows in site rows and all three top summary cards.

## Follow-up polish

- Production avatars will be visually richer than the standalone QA fallbacks because MoviePilot supplies the actual site icons.

final result: passed

## 2026-11-03 workbench follow-up

- Scope: compact retirement sort selector at the left, horizontal site navigation at the right, and clearer site data surfaces under glass themes.
- Browser verification: local Vite harness with API-shaped mock data, headless Edge, 1440 × 1050 and 390 × 844 viewports, dark and light Vuetify themes. Production MoviePilot was not exercised.
- Retirement toolbar: selector measured 220 px in a 1302 px toolbar; navigation aligned with the right edge. Both directions, keyboard activation, disabled boundaries, unchanged site selection, single-site disabled state, and the regular desktop sidebar passed.
- Site data: all ten metrics remained visible in ten desktop columns and two mobile columns; labels used 74% theme foreground with 3.5% foreground translucent metric surfaces. No document horizontal overflow or browser runtime errors occurred.
- Visually inspected dark/light site cards and mobile retirement toolbar captures. Repeated cards use translucent fills and inset highlights without additional backdrop-filter layers.

## Issue #7: independent retirement scrolling

- Confirmed the previous wide-screen explorer had automatic height and visible overflow, so neither pane independently scrolled.
- Restored bounded wide-screen pane height, independent list/detail scroll containers, fixed list heading and toolbar, contained scroll boundaries, and keyboard-focusable scroll regions. Compact/narrow layouts retain natural page height with a horizontal site strip and the previously requested right-aligned navigation.
- Added mouse-only horizontal dragging after 5 px of intentional horizontal movement, delayed pointer capture, cleanup on release/cancel/lost capture/unmount, and a 320 ms click guard. Touch and keyboard clicks retain native behavior; a fresh pointer press immediately permits a deliberate selection.
- Headless Edge with 45 mock sites, 1600 × 1000: sidebar scrollTop 0 → 400 while page scrollY stayed 207 and detail scrollTop stayed 0. Scrolling the detail to 350 preserved both page scrollY and sidebar scrollTop. Additional wheel input at the sidebar boundary did not scroll the page.
- 1280 px compact, 900 px narrow and 390 px mobile: real mouse drag moved scrollLeft 0 → 200 with the page position and selection unchanged; normal clicks selected the next site; both navigation directions and boundary disabled states passed. Single-site and wide/narrow resize cases passed without runtime errors or horizontal document overflow.
- CDP touch input moved the narrow strip by 268 px with page position and selection unchanged. Smooth navigation also passed without reduced motion. Visually inspected wide/compact captures; verification used a local Vue/Vuetify mock host, not a live MoviePilot instance.
- Frontend regression suite: 19 passing tests, including drag intent, click suppression, native gesture preservation, capture cleanup and boundary clamping. Production build passed.
