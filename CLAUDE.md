# Memory Experiment — Development Guide

## Project Overview
Human memory experiment: test whether people forget surface material textures faster than core category semantics. Flask web app + remote GPU image generation.

## Tech Stack
- **Backend**: Flask (single file `app.py`), SQLite, Python 3.10+
- **Frontend**: Vanilla HTML/CSS/JS, Jinja2 templates, no frameworks
- **Image Gen**: FLUX.1-dev via diffusers on remote 3090 GPU
- **Style**: Apple HIG aesthetic (see plan.md Section 6)

## Development Rules

### Architecture
- Single-file Flask app (`app.py`), keep under 400 lines
- No ORM — use raw SQL with `sqlite3`
- No frontend frameworks — vanilla JS only
- Minimize dependencies: flask, pillow for Phase 1

### Code Style
- Python: snake_case, type hints on public functions only
- SQL: UPPERCASE keywords, lowercase identifiers
- JS: camelCase, const by default, no var
- CSS: BEM-lite naming (`.grid-cell`, `.grid-cell.active`)
- Keep functions short (<30 lines)

### Database
- SQLite with WAL mode (`PRAGMA journal_mode=WAL` at startup)
- Use `db = sqlite3.connect('data/experiment.db')` with `row_factory = sqlite3.Row`
- Always parameterize queries (never f-string SQL)

### UI Design
- Apple aesthetic: see plan.md Section 6 for exact CSS variables
- Max content width: 480px, centered
- Font: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif`
- Buttons: pill shape (`border-radius: 9999px`), `#007AFF` blue
- Cards: white, `border-radius: 12px`, subtle shadow
- No borders on cards — use shadow only
- Transitions: 150ms for hover, 250ms for state changes
- Spacing: 4pt grid (4, 8, 12, 16, 20, 24, 32, 40px)

### Image Paths Convention
- Study image: `static/images/{category}/{material}/study.png`
- Recall image: `static/images/{category}/{material}/recall.png`
- Thumbnail: `static/images/{category}/{material}/thumb.jpg` (256x256)
- Phase 1 placeholder: served dynamically via `/placeholder/<cat>/<mat>`

### Template Structure
- `base.html`: all CSS inline in `<style>` (single-file simplicity), common layout
- Each page extends base, has single `.card` container
- No external CSS files needed for Phase 1 (embed in base.html)

### Key Constants
```python
CATEGORIES = ['bowl', 'cup', 'plate', 'vase', 'box', 'pitcher']
MATERIALS  = ['wood', 'plastic', 'metal', 'glass', 'ceramic', 'stone']
TRIALS_PER_PARTICIPANT = 1
STUDY_DURATION_SECONDS = 5
WEEK_WINDOW = (5, 9)    # days
MONTH_WINDOW = (25, 40)  # days
```

### Development Phases
1. **Phase 1 (current)**: Demo with placeholder images — full flow works end-to-end
2. **Phase 2**: Generate real images on remote 3090 via `generate_images.py`
3. **Phase 3**: Replace placeholders, run actual experiment

### Testing
- Test with `python app.py` (debug mode)
- Manual end-to-end: register → study 1 image → recall 1 → check admin stats
- For delayed recall testing: temporarily set `WEEK_WINDOW = (0, 999)` in config

### Remote GPU (Image Generation)
```bash
# Generate on remote 3090
ssh gpu-server "cd ~/memory && python generate_images.py"
# Pull results
rsync -avz gpu-server:~/memory/output/ ./static/images/
```

### File Reference
- `plan.md` — full design plan with all decisions, code snippets, and rationale
- `app.py` — Flask app (routes, DB, session)
- `config.py` — constants and configuration
- `generate_images.py` — FLUX.1-dev image generation (runs on GPU server)
- `templates/base.html` — base template with all CSS
- `templates/{index,study,recall,done,admin}.html` — page templates
- `CHANGELOG.md` — update log, one entry per meaningful change

### Git & GitHub Workflow
- **Commit often**: one logical change per commit, conventional commit messages
  - Format: `type(scope): short description` (e.g. `feat(app): add recall route`, `fix(db): parameterize participant query`)
  - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- **Branch strategy**: `main` is always runnable; feature work on `feat/<name>` branches
- **Push on milestone**: push to GitHub after each Phase milestone or significant feature
- **CHANGELOG.md**: append an entry every time you commit a meaningful change
  - Format: `## [date] — short title\n- bullet points of what changed and why`
- **Never commit**: `data/experiment.db`, `static/images/` (real images), `.env`, `__pycache__`
- Add `.gitignore` covering the above before first commit

### Code Generation & Review Process
- **Codex GPT5.4** writes code (via MCP tool) — provide full context from CLAUDE.md + plan.md
- **Claude Code** reviews all generated code before committing:
  - Check security (SQL injection, XSS, session fixation)
  - Check adherence to architecture rules (file size, no ORM, vanilla JS)
  - Check correctness against experiment design in plan.md
- Do not commit code that has not been reviewed

### First Principles
Please think using first principles. You cannot always assume that I am fully aware of what I want and how to obtain it. Please be cautious and start from the original needs and problems. If the motives and goals are not clear, stop and discuss with me. 

### Scheme Specification
When you are required to provide a modification or reconfiguration plan, the following specifications must be followed:
- It is not allowed to provide compatibility or patch-based solutions.
- Excessive design is prohibited. The shortest path implementation must be maintained and the first requirement must not be violated.
- It is not permitted to propose solutions beyond the requirements provided by me, such as some fallback and downgrade plans, as this may cause issues with the business logic.
- The logic of the plan must be correct and must undergo full-chain logic verification.