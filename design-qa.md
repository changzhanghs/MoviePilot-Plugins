# Design QA — PTDataStatistics v1.0.0

- Source visual truth: `C:\Users\cz\.codex\codex-remote-attachments\01a06dde-3ead-78b0-9af3-51dd41fad0fd\F3C71127-66DB-46BF-885E-72727438D705\1-照片-1.jpg`
- Implementation capture: Codex in-app browser live capture of the local Vite QA page; the temporary harness and mock data were removed after verification.
- Checked state: dark theme, daily scope, aggregate hourly chart, station selected, station-specific main chart, and inline historical record table.
- Viewport: 669 px wide responsive app panel. The photographed desktop state supplied the interaction and hierarchy target; the constrained capture verified responsive containment and overflow behavior.

## Comparison evidence

- The main chart remains above the station list after a station is selected and changes its title and dataset to the selected station.
- The selected station row remains highlighted and exposes an explicit collapse action.
- The inline region now contains historical data rows rather than a second chart.
- Historical columns include date, cumulative upload and download, daily upload and download, ratio, points or bonus, and seeding count and size.
- Daily selection displays `00:00–23:59`; weekly and monthly selection reuse the same table with one record per available date in descending order.
- The inline table is contained within the station panel and uses local horizontal overflow only at constrained widths; it does not widen the page.

## Interaction and accessibility checks

- Clicking a station updates the main chart and opens that station's historical rows in one action.
- Clicking the selected row again, the close button, or the selected-station chip collapses the history region and restores the aggregate chart.
- Station rows remain keyboard focusable and respond to Enter.
- The main chart exposes a station-aware `aria-label`; the expanded records remain semantic table content.

## Findings

- The previous v0.1.0 implementation incorrectly placed a second line chart inside the expanded row.
- Replaced that chart with the historical record table while retaining station filtering on the main chart.
- No actionable P0, P1, or P2 issues remain.

final result: passed
