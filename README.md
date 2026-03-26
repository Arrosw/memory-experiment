# Memory Experiment

A web-based human memory experiment testing whether people forget surface material textures faster than core category semantics.

## Hypothesis

> People actively forget **surface material textures** (wood, metal, glass…) but retain **core category semantics** (bowl, cup, vase…).

Validated by comparing category accuracy vs. material accuracy across three time delays: immediate, ~1 week, and ~1 month.

## How It Works

1. **Study phase** — participant views an image of an object (e.g., a wooden bowl) for 5 seconds
2. **Immediate recall** — shown a 6×6 grid (categories × materials), picks what they saw
3. **Week recall** — returns ~5–9 days later, recalls the same object
4. **Month recall** — returns ~25–40 days later, final recall

Accuracy on category vs. material dimensions is compared across phases to measure differential forgetting.

## Tech Stack

- **Backend**: Flask (single file), SQLite with WAL mode
- **Frontend**: Vanilla HTML/CSS/JS, Jinja2 templates, Apple HIG aesthetic
- **Image Generation**: FLUX.1-dev via diffusers on remote RTX 3090
- **Phase 1**: Dynamically generated placeholder images (Pillow)

## Project Structure

```
memory/
├── app.py                  # Flask app (routes, DB, session) — <400 lines
├── config.py               # Constants (categories, materials, windows)
├── generate_images.py      # FLUX.1-dev image generation (runs on GPU server)
├── templates/
│   ├── base.html           # Base layout with all CSS
│   ├── index.html          # Register / return page
│   ├── study.html          # Study phase (image display)
│   ├── recall.html         # Recall phase (2D grid)
│   ├── done.html           # Phase completion
│   └── admin.html          # Admin stats dashboard
├── static/images/          # {category}/{material}/study.png, thumb.png
├── data/experiment.db      # SQLite database (gitignored)
├── requirements.txt
└── plan.md                 # Full design plan and rationale
```

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Admin Dashboard

Visit `/admin` (HTTP Basic Auth). Exports response data as CSV at `/admin/export.csv`.

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | Current | Full flow with dynamically generated placeholder images |
| 2 | Pending | Generate real images on remote GPU via `generate_images.py` |
| 3 | Pending | Replace placeholders, run actual experiment |

## Image Generation (Remote GPU)

```bash
# Generate on remote RTX 3090
ssh gpu-server "cd ~/memory && python generate_images.py"

# Pull results locally
rsync -avz gpu-server:~/memory/output/ ./static/images/
```

Requires Phase 2 dependencies: `torch`, `diffusers`, `transformers`, `accelerate`.

## Categories & Materials

- **Categories** (rows): bowl, cup, plate, vase, box, pitcher
- **Materials** (columns): wood, plastic, metal, glass, ceramic, stone
