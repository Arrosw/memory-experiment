## 2026-04-16 — Add Demographic Timeline Tables
- Changed admin demographic statistics from all-phase summaries to phase-by-phase matrices for immediate, 1 day, 1 week, and 2 weeks.
- Shows complete-round counts plus object low/high and biological low/high accuracy for each demographic group.
- Uses collapsible demographic panels to keep gender, age group, and education statistics easier to scan.

## 2026-04-16 — Rename Higher Education Option
- Renamed the highest education choice from 本科及以上 to 大专/本科及以上.
- Added startup migration so existing participant rows and SQLite CHECK constraints accept the new label.

## 2026-04-16 — Use Age Group Registration
- Replaced free-text numeric age entry with fixed age group choices: 20岁及以下, 40岁及以下, and 40岁以上.
- Updated admin demographic statistics to report age groups in the same format as gender and education.
- Added startup migration to bucket existing numeric ages into the new age group values.

## 2026-04-16 — Finalize Four Phase Demographics
- Added required registration demographics for name, gender, age, and education.
- Switched experiment timing to Beijing time for registration, study start, and recall responses.
- Updated admin demographics to report complete-round counts and four accuracy measures: object low-frequency, object high-frequency, biological low-frequency, and biological high-frequency.
- Reduced the final recall schedule to immediate, 1 day, 1 week, and 2 weeks.

## 2026-04-15 — Add Diffusion Evolution Plot
- Added an admin evolution chart that overlays combined-trial covariance ellipses from all recall phases in one low-frequency/high-frequency offset space.
- Includes phase colors, mean points, and a dashed mean trajectory to show how memory diffusion changes over time.

## 2026-04-15 — Add Low High Diffusion Trend
- Added an admin trend chart that compares low-frequency semantic drift against high-frequency surface drift over time.
- Uses the combined object plus dog diffusion metrics so the core memory-stability hypothesis is easier to read before inspecting the ellipse plots.

## 2026-04-15 — Add Dog And Combined Diffusion Charts
- Added separate admin diffusion charts for dog breed/background trials and for combined object plus dog trials.
- Uses the agreed dog breed order `german shepherd, husky, shiba inu, labrador, golden retriever`.
- Uses the agreed background order `sand_ground, dusty_ground, dry_grassy_ground, slightly_damp_dirt, fine_gravel_ground`.

## 2026-04-15 — Adjust Diffusion Category Order
- Changed the admin diffusion chart category coding to `vase, bowl, mug, pitcher, tray` so visually similar vase and bowl responses are adjacent in the offset space.
- Kept the experiment configuration and recall UI order unchanged.

## 2026-04-15 — Add Memory Diffusion Chart
- Added an admin-only memory diffusion visualization for object trials.
- Computes target-relative category and material deltas, dispersion metrics, mean points, and covariance ellipses across all recall phases.
- Renders the chart with vanilla canvas without adding dependencies or changing participant flow.
