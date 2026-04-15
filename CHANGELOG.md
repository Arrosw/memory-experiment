## 2026-04-15 — Adjust Diffusion Category Order
- Changed the admin diffusion chart category coding to `vase, bowl, mug, pitcher, tray` so visually similar vase and bowl responses are adjacent in the offset space.
- Kept the experiment configuration and recall UI order unchanged.

## 2026-04-15 — Add Memory Diffusion Chart
- Added an admin-only memory diffusion visualization for object trials.
- Computes target-relative category and material deltas, dispersion metrics, mean points, and covariance ellipses across all recall phases.
- Renders the chart with vanilla canvas without adding dependencies or changing participant flow.
